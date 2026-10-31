import tempfile
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


if __name__ == '__main__':
    unittest.main()
