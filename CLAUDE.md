# Claude Code Instructions

When the user asks to "get shit done" or invokes `/get-shit-done`, read and follow `skills/get-shit-done/SKILL.md`.

Claude Code does not have Codex goal tools. Emulate goal mode with `state/overarching_goal.md` for the drain and `state/current_goal.md` for each claimed task.

Before task work, load the local project/user instructions and installed skills that apply to the workspace. Use `todo_source.py claim` before execution, then mark each task done or blocked after execution. Use `skills/get-shit-done/scripts/run_loop.py --drain` when the user wants polling.
