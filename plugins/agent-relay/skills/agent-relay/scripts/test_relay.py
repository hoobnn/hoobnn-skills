import tempfile
import json
import signal
import io
from contextlib import redirect_stdout
import subprocess
import unittest
from pathlib import Path
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
            self.assertIn('--answer', result['error'])
            self.assertTrue(result['questions'])

    def test_questions_preserve_relay_cancellation_reason(self):
        for exception, kind in ((TimeoutError, 'timeout'), (relay.IdleError, 'idle'),
                                (relay.StallError, 'stalled'), (relay.KilledError, 'killed')):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp, \
                 patch.object(relay, 'STATE_DIR', Path(tmp)), patch.object(relay, 'KILL_SIGNAL', signal.SIGTERM), \
                 patch.object(relay.Session, 'start'), patch.object(relay.Session, 'open'), \
                 patch.object(relay.Session, 'configure'):
                def fail(session, prompt, deadline):
                    session.questions.append({'message': '是否提交？', 'fields': {}})
                    raise exception()
                with patch.object(relay.Session, 'prompt', fail):
                    result = relay.execute(relay._ns(cli='opencode', cwd=tmp), 'test')
                self.assertEqual(result['error_kind'], kind)
                self.assertTrue(result['questions'])
                self.assertNotIn('--answer', result['error'])

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

    def test_show_result_and_running_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / 'status.json').write_text(json.dumps({'cli': 'grok', 'state': 'running', 'steps': list(range(9))}))
            status = relay._show_data(run, 3)
            self.assertEqual(status['state'], 'running')
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

    def test_long_work_timeout_warns(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(relay, 'STATE_DIR', Path(tmp)), \
             patch.object(relay.Session, 'start', side_effect=RuntimeError('failed')):
            result = relay.execute(relay._ns(cli='opencode', cwd=tmp, timeout=7200, work_timeout=7200), 'test')
            self.assertTrue(any('空转检测实际上已关闭' in w for w in result['warnings']))


if __name__ == '__main__':
    unittest.main()
