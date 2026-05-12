---
description: Drain configured todo sources with Get Shit Done
argument-hint: [--once|--watch]
---

Read and follow the Get Shit Done skill.

Use `/Users/omardadabhoy/Desktop/TodoSkill/skills/get-shit-done/SKILL.md` as the source of truth for this command.

This invocation is drain mode:

- Treat "Clear all actionable tasks from the configured todo sources" as the overarching goal.
- Use goal mode for the overarching drain and for every task.
- Load the user's local environment first: project `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, user-level instructions, installed skills, MCP/app connectors, and authenticated CLIs.
- For each task, claim the source item in-progress before doing any work.
- Never execute an unclaimed task.
- Never mark a task done unless it was in-progress first.
- Mark each task done or blocked in the source before moving on.
- Create and open an HTML handoff report for every completed, blocked, or needs-human task.
- Send a completion email after every finished task when any recipient email is configured or available in env.
- Continue until the configured sources have no unclaimed actionable tasks.

If the user asked for watch/polling, use the configured watcher interval and keep checking after each drain cycle.
