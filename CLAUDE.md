# Claude Code Instructions

When the user asks for "AI Slaves", asks to "get shit done", or invokes `/ai-slaves` or `/get-shit-done`, read and follow `skills/get-shit-done/SKILL.md`.

Use Claude Code native goal mode for the overarching drain and for each claimed task. The primitive is the `TaskCreate` tool (there is no `/goal` slash command in Claude Code): call `TaskCreate({subject, description, activeForm})` followed by `TaskUpdate(taskId, status: "in_progress")` before each worker dispatch, and `TaskUpdate(taskId, status: "completed")` after verification. The files `state/overarching_goal.md` and `state/current_goal.md` are audit records only, not substitutes for native goal mode.

On any interactive `/ai-slaves` or `/get-shit-done` invocation, set up a recurring drain check (default every 15 min, range 10-20 min, tweakable) using `/schedule` or `/loop` before exiting. Skip if the user requested one-shot or a schedule is already active.

Before task work, load the local project/user instructions and installed skills that apply to the workspace. Use `todo_source.py claim` before execution, create one dedicated worker/sub-agent per claimed task when available, default that worker to the best available model unless the user explicitly requested another model, then mark each task done or blocked after execution. Use `skills/get-shit-done/scripts/run_loop.py --drain` when the user wants polling; the watcher supports `--runtime hermes`, `--runtime openclaw`, and custom `--agent-command`.
