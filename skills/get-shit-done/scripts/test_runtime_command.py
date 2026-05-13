#!/usr/bin/env python3
from __future__ import annotations

import os
import unittest
from unittest import mock

from run_loop import runtime_command


class RuntimeCommandTest(unittest.TestCase):
    def test_hermes_command(self) -> None:
        command = runtime_command("hermes", "Do the task", model="anthropic/claude-sonnet-4", hermes_skills=["codex"])
        self.assertEqual(command, ["hermes", "chat", "-s", "codex", "--model", "anthropic/claude-sonnet-4", "-q", "Do the task"])

    def test_hermes_defaults_to_best_model(self) -> None:
        with mock.patch.dict(os.environ, {"TODO_SKILL_MODEL": "", "GSD_HERMES_MODEL": "", "HERMES_MODEL": ""}):
            command = runtime_command("hermes", "Do the task")
        self.assertEqual(command, ["hermes", "chat", "--model", "opus", "-q", "Do the task"])

    def test_openclaw_command(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENCLAW_THINKING", None)
            command = runtime_command("openclaw", "Do the task", openclaw_agent="ops", openclaw_local=True, timeout=120)
        self.assertEqual(
            command,
            ["openclaw", "agent", "--agent", "ops", "--local", "--thinking", "xhigh", "--timeout", "120", "--message", "Do the task"],
        )

    def test_openclaw_honors_thinking_override(self) -> None:
        command = runtime_command("openclaw", "Do the task", openclaw_agent="ops", openclaw_thinking="medium")
        self.assertEqual(command, ["openclaw", "agent", "--agent", "ops", "--thinking", "medium", "--message", "Do the task"])


if __name__ == "__main__":
    unittest.main()
