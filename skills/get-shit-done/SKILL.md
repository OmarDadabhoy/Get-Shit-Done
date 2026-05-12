---
name: get-shit-done
description: Work through the user's todo inbox. Use when the user invokes "/get-shit-done", "get shit done", "$get-shit-done", asks Codex or Claude Code to drain a todo list, Google Doc, Notion page, Apple Notes note, exported Messages/iMessage note, or configured inbox, or wants an agent to keep polling for new tasks and execute them with verification.
---

# Get Shit Done

## Operating Contract

Drain the configured todo source until no actionable item remains. For every item: claim it in the source first, make it the active goal, delegate execution to one worker/sub-agent when available, verify the result, mark it done or blocked in the source, send email when available, and leave a concise audit trail.

These are hard gates:

- Do not execute a task until the source item is marked in-progress.
- Do not mark a task done until it was already in-progress.
- Do not leave a completed or blocked task without updating the source.
- Do not skip goal mode. Codex must call `create_goal` when available; other agents must use `goal_state.py`.
- Do not skip completion email when `config/notifications.json` or email env vars provide a recipient.
- Do not stop after one task when the user invoked drain/watch mode; keep going until the configured source has no unclaimed actionable items.

This skill is agent-framework agnostic. In Codex, use goal mode for the overarching drain objective and for every task when goal tools are available. In Claude Code or other agents, emulate goal mode with `skills/get-shit-done/scripts/goal_state.py` and `state/overarching_goal.md`.

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

The watcher requires `TODO_SKILL_AGENT_CMD` or `--agent-command` for live execution. Use `--dry-run` when you only want rendered prompts. A skill alone cannot keep an agent alive.

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
   - Claude Code or other agents: run `goal_state.py activate` with the todo, source id, item id, and location.
7. Clarify only when the task cannot be executed safely or meaningfully without more input.
8. Assign execution to a worker:
   - Codex: spawn one worker sub-agent for the task when `spawn_agent` is available. Tell the worker it is not alone in the codebase and must not mark the source done or send notifications.
   - Other agents: invoke the configured watcher agent command or perform the task inline if no delegation mechanism exists.
9. Track the assignment in the ledger when `config/ledger.json` is enabled:

```bash
python3 skills/get-shit-done/scripts/ledger.py assigned --config config/ledger.json --task '<task>' --source-id '<source>' --item-id '<item>' --agent '<worker id>' --status running
```

10. Review the worker result, then verify with the narrowest meaningful check: tests, command output, file diff, browser QA, sent/draft status, or source-specific proof.
11. Mark the claimed item complete when the source supports it:
   - Capability mode: use the same tool/skill/connector that claimed the task.
   - Local mode: run:

```bash
python3 skills/get-shit-done/scripts/todo_source.py mark --config config/todo_sources.json --item-id '<item-id>' --status done
```

12. Close the active task goal:

```bash
python3 skills/get-shit-done/scripts/goal_state.py close --status done --summary '<result>' --verification '<verification>'
```

13. Append a short note to `state/completions.md` with the task, result, verification, and any follow-up.
14. Append a final ledger row:

```bash
python3 skills/get-shit-done/scripts/ledger.py done --config config/ledger.json --task '<task>' --source-id '<source>' --item-id '<item>' --agent '<worker id>' --status done --summary '<result>'
```

15. Send a completion email when a recipient is available through `config/notifications.json`, `TODO_SKILL_EMAIL_TO`, `GSD_EMAIL_TO`, `NOTIFY_EMAIL_TO`, `USER_EMAIL`, or `EMAIL`:

```bash
python3 skills/get-shit-done/scripts/notify.py done --config config/notifications.json --task '<task>' --body '<verification summary>'
```

16. If blocked or human input is required, mark the source item blocked, close the local goal as blocked or `needs_human`, append a ledger row with `blocked` or `needs_human`, then send:

```bash
python3 skills/get-shit-done/scripts/todo_source.py mark --config config/todo_sources.json --item-id '<item-id>' --status blocked
```

```bash
python3 skills/get-shit-done/scripts/notify.py needs_human --config config/notifications.json --task '<task>' --body '<exact blocker or question>'
```

17. Repeat from step 3 until no actionable item remains. If a continuous watcher is running, sleep for the configured interval, then drain again.

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
