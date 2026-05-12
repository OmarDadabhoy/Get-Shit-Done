# Claude Code Instructions

When the user asks to "get shit done", read and follow `skills/get-shit-done/SKILL.md`.

Claude Code does not have Codex goal tools. Emulate goal mode by writing the active todo to `state/current_goal.md`, then execute one task at a time, verify it, mark it complete when supported, and append a short result to `state/completions.md`.

Use `skills/get-shit-done/scripts/todo_source.py next --config config/todo_sources.json` to pick the next item. Use `skills/get-shit-done/scripts/run_loop.py` only when the user wants polling.
