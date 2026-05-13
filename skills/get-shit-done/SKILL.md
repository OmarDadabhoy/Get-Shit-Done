---
name: ai-slaves
description: This skill should be used when the user invokes "/ai-slaves", "/get-shit-done", "AI Slaves", "get shit done", asks Codex or Claude Code to drain a todo list, Google Doc, Notion page, Apple Notes note, exported Messages/iMessage note, or configured inbox, or wants an agent to keep polling for new tasks and execute them with verification.
---

# AI Slaves

## Operating Contract

Drain the configured todo source until no actionable item remains. For every item: claim it in the source first, make it the active goal, delegate execution to exactly one dedicated worker/sub-agent, verify the result, mark it done or blocked in the source, send email when available, and leave a concise audit trail.

These are hard gates:

- Do not execute a task until the source item is marked in-progress.
- Do not execute a claimed task inline when Codex, Claude Code, or the configured runtime can create a worker/sub-agent. Every Notion, Google Docs, and local-file task gets its own worker/sub-agent.
- If no worker/sub-agent mechanism exists, stop with `needs_human` or blocked status instead of silently executing inline, unless the user explicitly permits inline fallback for that run.
- Do not mark a task done until it was already in-progress.
- Do not leave a completed or blocked task without updating the source.
- Do not skip goal mode. Codex must use native goal mode with `create_goal` when available. Claude Code must use Claude Code native goal mode (`/goal`). Other agents use `goal_state.py`.
- Do not skip the recurring schedule. On any interactive invocation, ensure a recurring drain check is scheduled (default every 15 min, allowed range 10-20 min, user-tweakable). If one is already active, leave it alone.
- Do not finish a task without creating and opening an HTML handoff report that states what was done, what was verified, and what the user still needs to do.
- Do not skip completion email when `config/notifications.json` or email env vars provide a recipient.
- Do not stop after one task when the user invoked drain/watch mode; keep going until the configured source has no unclaimed actionable items.
- When useful improvements appear during work, append them to the source document under `Suggested Changes`.

This skill is agent-framework agnostic. In Codex and Claude Code, use native goal mode for the overarching drain objective and for every task. For other agents, emulate goal mode with `skills/get-shit-done/scripts/goal_state.py` and `state/overarching_goal.md`.

## Recurring Schedule (Required)

When invoked interactively, the skill must keep polling. Before exiting the first drain cycle, ensure a recurring check is scheduled:

- Default interval: **15 minutes**. Allowed range: **10-20 minutes**.
- Tweakable: if the user names an interval (e.g. "every 30 min", "hourly", "every 5 min"), honor it. Otherwise default to 15.
- In Claude Code: use `/schedule` to create a routine that re-invokes `/ai-slaves`, or `/loop 15m /ai-slaves` for the lighter-weight in-session variant. Prefer `/schedule` for persistence across sessions.
- In Codex or headless runtimes: use `skills/get-shit-done/scripts/run_loop.py --drain --interval 900 --jitter 180` (900s = 15 min).
- If a recurring schedule for `/ai-slaves` or `/get-shit-done` is already active for this user, do not create a duplicate; report the existing schedule instead.
- The user can disable polling by saying "no schedule", "one-shot", or "just this once". In that case, skip scheduling.

State the chosen interval in the final response so the user can override.

## Quick Start

From the TodoSkill repo, discover the next item:

```bash
python3 skills/get-shit-done/scripts/todo_source.py next --config config/todo_sources.json
```

For a background watcher that drains the source every cycle, use:

```bash
TODO_SKILL_AGENT_CMD='your-agent-command {prompt_file}' \
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --drain --interval 1800 --jitter 600
```

Built-in external runtimes are also available:

```bash
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --drain --runtime hermes
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --drain --runtime openclaw --openclaw-agent ops
```

The watcher requires `TODO_SKILL_AGENT_CMD`, `--agent-command`, or `--runtime hermes|openclaw` for live execution. Use `--dry-run` when you only want rendered prompts. A skill alone cannot keep an agent alive.

## Workflow

1. Prefer existing agent capabilities before local credentials:
   - If Codex/Claude already has a relevant MCP server, app connector, installed skill, first-party tool, authenticated CLI, or local session for the requested source, use that directly.
   - Examples: Notion tools, Google Drive/Docs/Sheets tools, Gmail tools, GitHub tools, browser tools, existing repo skills, `gh`, `gcloud`, or other already-authenticated CLIs.
   - Before executing each claimed task, load the local operating context that applies to the current workspace: project `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, user-level agent instructions, installed skills, MCP/app connectors, and authenticated CLIs.
   - Follow the user's local environment instructions unless they conflict with this skill's claim-first, goal-mode, source-writeback, or completion-email gates.
   - Do not ask the user to reconnect a source that is already available through the agent runtime.
   - Local JSON config is for headless scripts, polling, or agent runtimes that do not expose the needed capability.
2. Activate the overarching drain goal:
   - Codex: call `create_goal` for "Clear all actionable tasks from the configured todo sources" when goal tools are available and no active goal exists.
   - Claude Code: use Claude Code native goal mode for the same overarching objective.
   - Other agents: write or use `state/overarching_goal.md`.
3. Load the next incomplete todo:
   - Capability mode: read the configured or user-mentioned page/doc/sheet/inbox with the best existing runtime capability and skip items already marked in-progress/done/blocked.
   - Local mode: read `config/todo_sources.json` and load the next incomplete todo with `todo_source.py next`.
4. If no todo exists, report that the inbox is empty and stop or sleep until the next scheduled poll.
5. Claim the todo before any execution:
   - Capability mode: update the source item to in-progress using the same connector/tool that read it.
   - Local mode:

```bash
python3 skills/get-shit-done/scripts/todo_source.py claim --config config/todo_sources.json --item-id '<item-id>'
```

   If the claim fails because the item is already in-progress/done/blocked, skip it and pick the next item.
6. Turn the claimed todo into the active task goal before execution:
   - Codex: call `create_goal` with the todo as the concrete objective when goal tools are available and no active goal already exists.
   - Claude Code: use Claude Code native goal mode with the claimed todo as the active objective.
   - Other agents: run `goal_state.py activate` with the todo, source id, item id, and location.
7. Clarify only when the task cannot be executed safely or meaningfully without more input.
8. Assign execution to a dedicated worker/sub-agent:
   - Codex: spawn exactly one worker sub-agent for the claimed task when `spawn_agent` is available. Tell the worker it is not alone in the codebase and must not mark the source done, close the goal, or send notifications.
   - Claude Code: use Claude Code's native sub-agent/task-worker mechanism when available with the same boundaries.
   - Hermes: use `--runtime hermes` or an equivalent Hermes one-shot `hermes chat -q` worker command. Preload Hermes skills with `--hermes-skill` when needed.
   - OpenClaw: use `--runtime openclaw --openclaw-agent <name>` or `OPENCLAW_AGENT=<name>` so each claimed task is sent as one OpenClaw agent turn.
   - Headless watcher mode: treat the configured `TODO_SKILL_AGENT_CMD` or `--agent-command` invocation as the worker boundary; that worker must create a sub-agent when its runtime supports one.
   - If no worker/sub-agent mechanism exists, mark the task blocked or `needs_human` with "No sub-agent mechanism available" unless the user explicitly allowed inline fallback.
9. Track the assignment in the ledger when `config/ledger.json` is enabled:

```bash
python3 skills/get-shit-done/scripts/ledger.py assigned --config config/ledger.json --task '<task>' --source-id '<source>' --item-id '<item>' --agent '<worker id>' --status running
```

10. Review the worker result, then verify with the narrowest meaningful check: tests, command output, file diff, browser QA, sent/draft status, or source-specific proof.
11. If the worker or inline execution surfaces useful next-step ideas, append them to the source under `Suggested Changes`:

```bash
python3 skills/get-shit-done/scripts/suggested_changes.py --config config/todo_sources.json --source-id '<source>' --task '<task>' --suggestion '<suggestion>'
```

In capability mode, use the same Notion/Google Docs/Sheets connector or tool that read the source.
12. Create and open the HTML handoff report:

```bash
python3 skills/get-shit-done/scripts/handoff_report.py --status done --task '<task>' --summary '<what happened>' --verification '<verification>' --needs-from-user '<anything needed from the user>'
```

13. Mark the claimed item complete when the source supports it:
   - Capability mode: use the same tool/skill/connector that claimed the task.
   - Local mode: run:

```bash
python3 skills/get-shit-done/scripts/todo_source.py mark --config config/todo_sources.json --item-id '<item-id>' --status done
```

14. Close the active task goal:

```bash
python3 skills/get-shit-done/scripts/goal_state.py close --status done --summary '<result>' --verification '<verification>'
```

15. Append a short note to `state/completions.md` with the task, result, verification, handoff report path, suggestions, and any follow-up.
16. Append a final ledger row:

```bash
python3 skills/get-shit-done/scripts/ledger.py done --config config/ledger.json --task '<task>' --source-id '<source>' --item-id '<item>' --agent '<worker id>' --status done --summary '<result>'
```

17. Send a completion email when a recipient is available through `config/notifications.json`, `TODO_SKILL_EMAIL_TO`, `GSD_EMAIL_TO`, `NOTIFY_EMAIL_TO`, `USER_EMAIL`, or `EMAIL`:

```bash
python3 skills/get-shit-done/scripts/notify.py done --config config/notifications.json --task '<task>' --body '<verification summary>'
```

18. If blocked or human input is required, append any useful suggestions, create and open an HTML handoff report with the exact request for the user, mark the source item blocked, close the local goal as blocked or `needs_human`, append a ledger row with `blocked` or `needs_human`, then send:

```bash
python3 skills/get-shit-done/scripts/handoff_report.py --status needs_human --task '<task>' --summary '<blocker>' --needs-from-user '<exact request for the user>'
```

```bash
python3 skills/get-shit-done/scripts/todo_source.py mark --config config/todo_sources.json --item-id '<item-id>' --status blocked
```

```bash
python3 skills/get-shit-done/scripts/notify.py needs_human --config config/notifications.json --task '<task>' --body '<exact blocker or question>'
```

19. Repeat from step 3 until no actionable item remains. If a continuous watcher is running, sleep for the configured interval, then drain again.

## Task Selection

Choose the first incomplete item returned by the configured sources unless the user states another priority rule. Treat these as actionable:

- Markdown checkbox items like `- [ ] Email Sam the contract`
- TODO lines like `TODO: check production deploy`

Skip items that are already complete, in-progress, blocked, waiting on someone else, or phrased as vague buckets with no executable next step. If the top item is vague but a reasonable first action is obvious, do that first action and record the interpretation.

## Safety Rules

Do not access Apple Notes, Messages, iMessage, email, calendars, or other private apps unless the user configured that source or explicitly asks for it in the current session.

Ask before externally visible or destructive actions, including sending messages or emails, deleting data, buying anything, changing billing, force-pushing, deploying to production, or contacting third parties.

If a task requires credentials, paid services, 2FA, or production access that is not already available, stop with a concise blocker note and do not mark the item complete.

## Source Notes

Use `references/sources.md` for source setup details. The default source is a local Markdown file at `inbox/todo.md`.

Google Docs, Notion, and Apple Notes support are opt-in sources. Google Docs and Notion can mark completed tasks when configured with write auth and `writeback: "mark_done"` or clear/archive task content with `writeback: "delete"`. Apple Notes uses macOS AppleScript, so macOS may prompt for automation permission. Direct iMessage database access is not enabled by default; prefer exporting or mirroring iMessage todos into the local Markdown inbox unless the user explicitly configures a safer source adapter.

MCP servers, app connectors, installed skills, and authenticated CLIs are runtime capabilities, not repo credentials. Use them when the current Codex/Claude session exposes them. Scripts in this repo cannot automatically see those capabilities unless they are run through an agent command that has them.
