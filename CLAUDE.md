# Claude Code Instructions

When the user asks to "get shit done" or invokes `/get-shit-done`, read and follow `skills/get-shit-done/SKILL.md`.

Use Claude Code native goal mode (`/goal`) for the overarching drain and for each claimed task. The files `state/overarching_goal.md` and `state/current_goal.md` are audit records only, not substitutes for native goal mode.

On any interactive `/get-shit-done` invocation, set up a recurring drain check (default every 15 min, range 10-20 min, tweakable) using `/schedule` or `/loop` before exiting. Skip if the user requested one-shot or a schedule is already active.

Before task work, load the local project/user instructions and installed skills that apply to the workspace. Use `todo_source.py claim` before execution, create one dedicated worker/sub-agent per claimed task when available, then mark each task done or blocked after execution. Use `skills/get-shit-done/scripts/run_loop.py --drain` when the user wants polling; the watcher supports `--runtime hermes`, `--runtime openclaw`, and custom `--agent-command`.
