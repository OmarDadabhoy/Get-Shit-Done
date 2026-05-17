---
description: Drain configured todo sources with AI Slaves
argument-hint: [--once|--watch]
---

Read and follow the AI Slaves skill.

Use `/Users/omardadabhoy/Desktop/Ai-slaves/skills/get-shit-done/SKILL.md` as the source of truth for this command.

This invocation is drain mode:

- Treat "Clear all actionable tasks from the configured todo sources" as the overarching goal.
- Use goal mode for the overarching drain and for every task.
- Load the user's local environment first: project `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, user-level instructions, installed skills, MCP/app connectors, and authenticated CLIs.
- Fetch the queued/actionable batch, then claim source items in-progress in priority/order before doing any work.
- For each claimed task, create exactly one dedicated worker/sub-agent when the runtime supports it; run claimed-task workers concurrently instead of draining one task at a time.
- Default each worker/sub-agent to the best available model unless the user explicitly requested a different model, cheaper mode, faster mode, or runtime default. For Codex sub-agents, use `gpt-5.5` with `xhigh` reasoning unless Omar requests otherwise.
- In dashboard mode, post one `/api/agents` row per spawned worker and reconcile each worker result as it finishes.
- For polling, OpenClaw and Hermes can be used as external worker runtimes through `run_loop.py --runtime openclaw|hermes`.
- Never execute an unclaimed task.
- Never mark a task done unless it was in-progress first.
- Mark each task done or blocked in the source as its worker result is reconciled.
- Before exiting the first drain cycle, ensure a recurring drain check is scheduled (default 15 min, allowed 10-20 min, user-tweakable) via `/schedule` or `/loop`. Skip only if the user said one-shot or a schedule is already active.
- If the agent sees useful improvements while working, append them to the source under `Suggested Changes`.
- Create and open an HTML handoff report for every completed, blocked, or needs-human task.
- Send a completion email after every finished task when any recipient email is configured or available in env.
- Continue until the configured sources have no unclaimed actionable tasks.

If the user asked for watch/polling, use the configured watcher interval and keep checking after each drain cycle.
