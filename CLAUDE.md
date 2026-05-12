# Claude Code Instructions

When the user asks to "get shit done" or invokes `/get-shit-done`, read and follow `skills/get-shit-done/SKILL.md`.

Use Claude Code native goal mode for the overarching drain and for each claimed task. The files `state/overarching_goal.md` and `state/current_goal.md` are audit records only, not substitutes for native goal mode.

Before task work, load the local project/user instructions and installed skills that apply to the workspace. Use `todo_source.py claim` before execution, then mark each task done or blocked after execution. Use `skills/get-shit-done/scripts/run_loop.py --drain` when the user wants polling.
