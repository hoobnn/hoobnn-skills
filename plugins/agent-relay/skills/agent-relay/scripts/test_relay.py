import tempfile
import json
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

    def test_auto_answer_choices_and_explicit_override(self):
        s = relay.Session(relay._ns(cli='opencode', auto_answer='recommended', answers={'x': 'manual'}), Path('/tmp'))
        form = {'mode': 'form', 'requestedSchema': {'required': ['x', 'y'], 'properties': {
            'x': {'oneOf': [{'const': 'yes', 'title': 'Recommended'}]},
            'y': {'oneOf': [{'const': 'a'}, {'const': 'b', 'title': '推荐'}]}}}}
        self.assertEqual(s._elicit(form)['content'], {'x': 'manual', 'y': 'b'})
        self.assertEqual(s.auto_answers[0]['content'], {'y': 'b'})
        self.assertIsNone(relay._auto_choice({'enum': ['a']}, 'recommended'))
        self.assertEqual(relay._auto_choice({'enum': ['a']}, 'first'), 'a')

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


if __name__ == '__main__':
    unittest.main()
