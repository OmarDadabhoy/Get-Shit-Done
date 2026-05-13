#!/usr/bin/env python3
from __future__ import annotations

import unittest

from run_loop import runtime_command


class RuntimeCommandTest(unittest.TestCase):
    def test_hermes_command(self) -> None:
        command = runtime_command("hermes", "Do the task", model="anthropic/claude-sonnet-4", hermes_skills=["codex"])
        self.assertEqual(command, ["hermes", "chat", "-s", "codex", "--model", "anthropic/claude-sonnet-4", "-q", "Do the task"])

    def test_openclaw_command(self) -> None:
        command = runtime_command("openclaw", "Do the task", openclaw_agent="ops", openclaw_local=True, timeout=120)
        self.assertEqual(command, ["openclaw", "agent", "--agent", "ops", "--local", "--timeout", "120", "--message", "Do the task"])


if __name__ == "__main__":
    unittest.main()
