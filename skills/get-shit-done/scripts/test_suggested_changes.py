#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from suggested_changes import append_suggestions


class SuggestedChangesTest(unittest.TestCase):
    def test_text_file_suggestions_append_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            todo = root / "todo.md"
            todo.write_text("- [>] Do this\n", encoding="utf-8")
            config = root / "sources.json"
            config.write_text(
                json.dumps({"sources": [{"id": "local", "type": "text_file", "enabled": True, "path": str(todo)}]}),
                encoding="utf-8",
            )

            result = append_suggestions(config, "local", "Do this", ["Try a shorter onboarding flow."])

            self.assertEqual(result["status"], "appended")
            text = todo.read_text(encoding="utf-8")
            self.assertIn("## Suggested Changes", text)
            self.assertIn("Do this", text)
            self.assertIn("Try a shorter onboarding flow.", text)


if __name__ == "__main__":
    unittest.main()
