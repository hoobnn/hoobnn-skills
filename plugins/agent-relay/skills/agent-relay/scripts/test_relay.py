import tempfile
import json
import signal
import io
from contextlib import redirect_stdout
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import relay


class RelayTests(unittest.TestCase):
    def test_cancelled_after_question_is_asked(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(relay, 'STATE_DIR', Path(tmp)), \
             patch.object(relay.Session, 'start'), patch.object(relay.Session, 'open'), \
             patch.object(relay.Session, 'configure'), patch.object(relay.Session, 'prompt') as prompt:
            def ask(session_prompt, deadline):
                session = prompt_session[0]
                session.questions.append({'message': '是否提交？', 'fields': {}})
                session.stop_reason = 'cancelled'
            original = relay.Session.__init__
            prompt_session = []
            def init(session, *args):
                original(session, *args)
                prompt_session.append(session)
            with patch.object(relay.Session, '__init__', init):
                prompt.side_effect = ask
                result = relay.execute(relay._ns(cli='opencode', cwd=tmp), 'test')
            self.assertEqual(result['error_kind'], 'asked')
            self.assertIn('--answer', result['hint'])
            self.assertTrue(result['questions'])

    def test_questions_preserve_relay_cancellation_reason(self):
        for exception, kind in ((TimeoutError, 'timeout'), (relay.IdleError, 'idle'),
                                (relay.StallError, 'stalled'), (relay.KilledError, 'killed')):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp, \
                 patch.object(relay, 'STATE_DIR', Path(tmp)), patch.object(relay, 'KILL_SIGNAL', signal.SIGTERM), \
                 patch.object(relay.Session, 'open'), patch.object(relay.Session, 'configure'), \
                 patch.object(relay.Session, 'close'), patch.object(relay.Session, 'cancel') as cancel:
                def start(session, run_dir):
                    session.conn = SimpleNamespace(proc=SimpleNamespace(returncode=0))
                def fail(session, prompt, deadline):
                    session.questions.append({'message': '是否提交？', 'fields': {}})
                    raise exception()
                with patch.object(relay.Session, 'start', start), patch.object(relay.Session, 'prompt', fail):
                    result = relay.execute(relay._ns(cli='opencode', cwd=tmp), 'test')
                cancel.assert_called_once_with()
                self.assertEqual(result['error_kind'], kind)
                self.assertTrue(result['questions'])
                self.assertNotIn('--answer', result['hint'] or '')

    def test_auto_answer_choices_and_explicit_override(self):
        s = relay.Session(relay._ns(cli='opencode', auto_answer='recommended', answers={'x': 'manual'}), Path('/tmp'))
        form = {'mode': 'form', 'requestedSchema': {'required': ['x', 'y'], 'properties': {
            'x': {'oneOf': [{'const': 'yes', 'title': 'Recommended'}]},
            'y': {'oneOf': [{'const': 'a'}, {'const': 'b', 'title': '推荐'}]}}}}
        self.assertEqual(s._elicit(form)['content'], {'x': 'manual', 'y': 'b'})
        self.assertEqual(s.auto_answers[0]['content'], {'y': 'b'})
        self.assertIsNone(relay._auto_choice({'enum': ['a']}, 'recommended'))
        self.assertEqual(relay._auto_choice({'enum': ['a']}, 'first'), 'a')

    def test_recommended_title_is_conservative(self):
        for title in ('不推荐，等用户确认', 'Not recommended', '推荐，但不要提交',
                      'Recommended: no action', '请选择推荐方案', '建议 (not recommended)'):
            with self.subTest(title=title):
                self.assertIsNone(relay._auto_choice({'oneOf': [{'const': 'wait', 'title': title}]}, 'recommended'))
        for title in ('Recommended: submit', '推荐提交', '提交（Recommended）', '提交(推荐)'):
            with self.subTest(title=title):
                self.assertEqual(relay._auto_choice({'oneOf': [{'const': 'yes', 'title': title}]}, 'recommended'), 'yes')
        self.assertIsNone(relay._auto_choice({'enum': ['提交（Recommended）']}, 'recommended'))
        self.assertEqual(relay._auto_choice({'oneOf': [{'const': 'wait', 'title': '不推荐'}]}, 'first'), 'wait')

    def test_grouped_model_options_match_by_suffix(self):
        opt = {'options': [{'name': 'provider', 'options': [{'value': 'provider/sonnet', 'name': 'Sonnet'}]}]}
        self.assertEqual(relay._flat_values(opt), ['provider/sonnet'])
        self.assertEqual(relay._match('sonnet', opt), ('provider/sonnet', ['provider/sonnet']))

    def test_resume_mismatch_does_not_start_agent(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(relay, 'STATE_DIR', Path(tmp)):
            old = Path(tmp) / 'runs' / '20260101-opencode-old'
            old.mkdir(parents=True)
            (old / 'result.json').write_text(json.dumps({'session_id': 's', 'cwd': '/elsewhere'}))
            with patch.object(relay.Session, 'start') as start:
                result = relay.execute(relay._ns(cli='opencode', cwd=tmp, resume='s'), 'test')
            start.assert_not_called()
            self.assertEqual(result['error_kind'], 'resume_cwd')
            self.assertIn('/elsewhere', result['error'])
            self.assertEqual(relay._error_kind('session does not belong to cwd'), 'resume_cwd')

    def test_resume_cwd_matches_cli_and_legacy_record(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(relay, 'STATE_DIR', Path(tmp)):
            for name, cli, cwd in (('20261031-100000-opencode-aaaaaa', None, '/legacy'),
                                   ('20261031-110000-opencode-bbbbbb', 'opencode', '/correct'),
                                   ('20261031-120000-grok-cccccc', 'grok', '/wrong')):
                run = Path(tmp, 'runs', name)
                run.mkdir(parents=True)
                (run / 'result.json').write_text(json.dumps({'session_id': 'same', 'cli': cli, 'cwd': cwd}))
            self.assertEqual(relay._resume_cwd('same', 'opencode'), '/correct')
            self.assertEqual(relay._resume_cwd('same', 'codex'), '/legacy')

    def test_uncommitted_excludes_committed_and_includes_deleted(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as state:
            def git(*args):
                subprocess.run(['git', '-C', tmp, *args], check=True, capture_output=True)
            git('init', '-q')
            git('config', 'commit.gpgsign', 'false')
            git('config', 'core.hooksPath', '/dev/null')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.com')
            Path(tmp, 'deleted').write_text('before')
            git('add', 'deleted')
            git('commit', '-qm', 'initial')
            def work(*args):
                Path(tmp, 'deleted').unlink()
                Path(tmp, 'committed').write_text('done')
                git('add', 'committed')
                git('commit', '-qm', 'work')
                raise RuntimeError('failed')
            with patch.object(relay, 'STATE_DIR', Path(state)), patch.object(relay.Session, 'start', side_effect=work):
                result = relay.execute(relay._ns(cli='opencode', cwd=tmp), 'test')
            self.assertEqual(result['uncommitted'], ['deleted'])
            self.assertIn('committed', result['files_changed'])
            self.assertEqual(result['commits'][0]['subject'], 'work')

    def test_uncommitted_only_changes_from_this_run(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as state:
            subprocess.run(['git', 'init', '-q', tmp], check=True)
            Path(tmp, 'old').write_text('old')
            def work(*args):
                Path(tmp, 'new').write_text('new')
                raise RuntimeError('failed')
            with patch.object(relay, 'STATE_DIR', Path(state)), patch.object(relay.Session, 'start', side_effect=work):
                result = relay.execute(relay._ns(cli='opencode', cwd=tmp), 'test')
            self.assertEqual(result['uncommitted'], ['new'])
            self.assertTrue(any('1 个未提交' in w for w in result['warnings']))

    def test_full_agent_message_replaces_chunked_text(self):
        s = relay.Session(relay._ns(cli='opencode'), Path('/tmp'))
        s.prompting = True
        for kind, content in (('agent_message_chunk', {'type': 'text', 'text': '草稿'}),
                              ('agent_message', [{'type': 'text', 'text': '最终'},
                                                 [{'type': 'text', 'text': '不应展开'}],
                                                 {'type': 'text', 'text': '回答'}])):
            s.on_notify('session/update', {'update': {'sessionUpdate': kind, 'messageId': 'm', 'content': content}})
        self.assertEqual(s.text(), '最终回答')
        s.on_notify('session/update', {'update': {'sessionUpdate': 'agent_message', 'messageId': 'm',
                                                 'content': {'type': 'text', 'text': '非列表'}}})
        self.assertIsNone(s.text())

    def test_thought_content_list_and_non_list_forms(self):
        s = relay.Session(relay._ns(cli='opencode'), Path('/tmp'))
        s.prompting = True
        cases = [([{'type': 'text', 'text': '分析'},
                   [{'type': 'text', 'text': '不应展开'}],
                   {'type': 'text', 'text': '完成'}], '分析完成'),
                 ({'type': 'text', 'text': '单块思考'}, '单块思考')]
        for content, expected in cases:
            s.on_notify('session/update', {'update': {'sessionUpdate': 'agent_thought', 'content': content}})
            self.assertEqual(s.steps[-1], {'type': 'thought', 'text': expected})

    def test_show_result_and_running_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / 'status.json').write_text(json.dumps({'cli': 'grok', 'state': 'working', 'steps': list(range(9))}))
            status = relay._show_data(run, 3)
            self.assertEqual(status['state'], 'working')
            self.assertEqual(status['steps'], [4, 5, 6, 7, 8])
            (run / 'result.json').write_text(json.dumps({'ok': False, 'questions': [{'fields': {'x': {'options': ['a']}}}],
                                                         'uncommitted': ['a'], 'text': 'abcdef', 'commands': ['omitted']}))
            result = relay._show_data(run, 3)
            self.assertEqual(result['text'], 'def')
            self.assertEqual(result['uncommitted'], ['a'])
            self.assertIn('questions', result)
            self.assertNotIn('commands', result)

    def test_show_human_format(self):
        data = {'timing': {'total_s': 12, 'first_edit_s': None, 'first_commit_s': 9},
                'commits': [{'sha': 'abc', 'subject': 'feat: x'}], 'uncommitted': ['a'],
                'warnings': ['检查'], 'questions': [{'message': '确认？', 'fields': {
                    'confirm': {'title': '提交', 'description': '现在提交吗', 'required': True, 'options': ['yes', 'no']}}}],
                'auto_answers': [{'message': '问题', 'content': {'confirm': 'yes'}}], 'text': '完成'}
        output = relay._format_show(data)
        for text in ('总 12s · 首次编辑 — · 首次提交 9s', 'abc feat: x', 'confirm · 提交 · 必填 · 可选：yes / no',
                     '现在提交吗', 'confirm: yes', '检查', 'text（末尾）：\n完成'):
            self.assertIn(text, output)
        self.assertNotIn('{', output)

    def test_show_latest_filter_and_infer_cli(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(relay, 'STATE_DIR', Path(tmp)):
            for name, state in (('20261031-100000-opencode-aaaaaa', 'old'),
                                ('20261031-110000-grok-bbbbbb', 'other'),
                                ('20261031-120000-opencode-cccccc', 'new')):
                run = Path(tmp, 'runs', name)
                run.mkdir(parents=True)
                (run / 'result.json').write_text(json.dumps({'text': state}))
            output = io.StringIO()
            with redirect_stdout(output):
                relay.cmd_show(relay.argparse.Namespace(path=None, latest='opencode', tail=2000, json=True))
            data = json.loads(output.getvalue())
            self.assertEqual((data['cli'], data['text']), ('opencode', 'new'))

    def test_template_defaults_yield_to_explicit_flags(self):
        def args(**kw):
            base = dict(template='reviewer', asks=None, auto_answer=None, timeout=None, idle_timeout=None, work_timeout=None)
            return relay.argparse.Namespace(**{**base, **kw})
        a = args()
        prompt = relay._apply_template(a, '审 x.py')
        self.assertTrue(prompt.endswith('任务：\n审 x.py'))
        self.assertEqual((a.asks, a.work_timeout, a.timeout), ('deny', 0, 1200))
        a = args(asks='allow', template='implementer')
        relay._apply_template(a, 'x')
        self.assertEqual((a.asks, a.timeout), ('allow', 3600))
        with self.assertRaises(SystemExit):
            relay._apply_template(args(template='missing'), 'x')

    def test_exit_code_by_error_kind(self):
        ok, asked, quota = {'ok': True, 'error_kind': None}, {'ok': False, 'error_kind': 'asked'}, {'ok': False, 'error_kind': 'quota'}
        self.assertEqual(relay._exit_code([ok]), 0)
        self.assertEqual(relay._exit_code([ok, asked, dict(asked)]), relay.EXIT_CODES['asked'])
        self.assertEqual(relay._exit_code([asked, quota]), 1)

    def test_worktree_carries_local_state_and_drops_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp, 'repo')
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            (repo / 'sub').mkdir()
            (repo / 'sub' / 'a.txt').write_text('a')
            (repo / '.gitignore').write_text('.env\nnode_modules/\n')
            subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'init'], check=True)
            (repo / 'sub' / 'a.txt').write_text('changed')
            (repo / 'sub' / 'new.txt').write_text('new')
            (repo / '.env').write_text('K=1')
            (repo / 'node_modules').mkdir()
            (repo / 'node_modules' / 'x.js').write_text('x')
            seen = {}
            def fake(ns, prompt, git_diff=True):
                cwd = Path(ns.cwd)
                seen[ns.cli] = (cwd, git_diff, prompt)
                self.assertEqual((cwd / 'a.txt').read_text(), 'changed')
                self.assertTrue((cwd / 'new.txt').exists() and (cwd.parent / '.env').exists())
                self.assertFalse((cwd.parent / 'node_modules').exists())
                return {'ok': True, 'error_kind': None, 'warnings': [], 'uncommitted': ['b'] if ns.cli == 'codex' else []}
            out = io.StringIO()
            a = relay.argparse.Namespace(cli='grok,codex', resume=None, worktree=True, prompt='x', prompt_file=None,
                                         template=None, files=[], answer=[], cwd=str(repo / 'sub'), model=[], effort=[],
                                         asks=None, auto_answer=None, timeout=None, idle_timeout=None, work_timeout=None)
            with patch.object(relay, '_installed', return_value=True), patch.object(relay, 'execute', fake), \
                 redirect_stdout(out), self.assertRaises(SystemExit) as code:
                relay.cmd_run(a)
            self.assertEqual(code.exception.code, 0)
            results = {r['cli']: r for r in json.loads(out.getvalue())}
            self.assertTrue(all(git_diff and 'node_modules/' in prompt for _, git_diff, prompt in seen.values()))
            self.assertIsNone(results['grok']['worktree'])  # 没改动：worktree 和分支都删掉
            self.assertFalse(seen['grok'][0].exists())
            branches = subprocess.run(['git', '-C', str(repo), 'branch', '--list', 'relay/*'],
                                      capture_output=True, text=True).stdout
            self.assertNotIn('grok', branches)
            self.assertEqual(Path(results['codex']['worktree']) / 'sub', seen['codex'][0])
            self.assertIn(results['codex']['branch'], branches)
            self.assertEqual((repo / 'sub' / 'a.txt').read_text(), 'changed')  # 主工作区不动

if __name__ == '__main__':
    unittest.main()
