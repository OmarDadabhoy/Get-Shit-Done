---
name: get-shit-done
description: Work through the user's todo inbox one item at a time. Use when the user invokes "get shit done", "$get-shit-done", asks Codex or Claude Code to take the next task from a todo list, Google Doc, Notion page, Apple Notes note, exported Messages/iMessage note, or configured inbox, or wants an agent to keep polling for new tasks and execute them with verification.
---

# Get Shit Done

## Operating Contract

Pick the next actionable todo, make it the active objective, delegate execution to one worker/sub-agent when available, verify the result, and leave a concise audit trail. Do not batch unrelated todos unless the user explicitly asks.

This skill is agent-framework agnostic. In Codex, activate goal mode for every task when goal tools are available. In Claude Code or other agents, emulate the active goal with `skills/get-shit-done/scripts/goal_state.py`.

## Quick Start

From the TodoSkill repo, discover the next item:

```bash
python3 skills/get-shit-done/scripts/todo_source.py next --config config/todo_sources.json
```

For a background watcher, use:

```bash
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --interval 1800 --jitter 600
```

The watcher only prepares prompts unless `TODO_SKILL_AGENT_CMD` or `--agent-command` is configured. A skill alone cannot keep an agent alive.

## Workflow

1. Read `config/todo_sources.json` and load the next incomplete todo with `todo_source.py next`.
2. If no todo exists, report that the inbox is empty and stop.
3. Turn the todo into the active goal before any execution:
   - Codex: call `create_goal` with the todo as the concrete objective when goal tools are available and no active goal already exists.
   - Claude Code or other agents: run `goal_state.py activate` with the todo, source id, item id, and location.
4. Clarify only when the task cannot be executed safely or meaningfully without more input.
5. Assign execution to a worker:
   - Codex: spawn one worker sub-agent for the task when `spawn_agent` is available. Tell the worker it is not alone in the codebase and must not mark the source done or send notifications.
   - Other agents: invoke the configured watcher agent command or perform the task inline if no delegation mechanism exists.
6. Track the assignment in the ledger when `config/ledger.json` is enabled:

```bash
python3 skills/get-shit-done/scripts/ledger.py assigned --config config/ledger.json --task '<task>' --source-id '<source>' --item-id '<item>' --agent '<worker id>' --status running
```

7. Review the worker result, then verify with the narrowest meaningful check: tests, command output, file diff, browser QA, sent/draft status, or source-specific proof.
8. Mark the item complete when the source supports it:

```bash
python3 skills/get-shit-done/scripts/todo_source.py mark --config config/todo_sources.json --item-id '<item-id>' --status done
```

9. Close the active goal:

```bash
python3 skills/get-shit-done/scripts/goal_state.py close --status done --summary '<result>' --verification '<verification>'
```

10. Append a short note to `state/completions.md` with the task, result, verification, and any follow-up.
11. Append a final ledger row:

```bash
python3 skills/get-shit-done/scripts/ledger.py done --config config/ledger.json --task '<task>' --source-id '<source>' --item-id '<item>' --agent '<worker id>' --status done --summary '<result>'
```

12. Send a notification if `config/notifications.json` is enabled:

```bash
python3 skills/get-shit-done/scripts/notify.py done --config config/notifications.json --task '<task>' --body '<verification summary>'
```

13. If blocked or human input is required, first close the local goal as blocked or `needs_human`, append a ledger row with `blocked` or `needs_human`, then send:

```bash
python3 skills/get-shit-done/scripts/notify.py needs_human --config config/notifications.json --task '<task>' --body '<exact blocker or question>'
```

14. If a continuous watcher is running, let it poll again after the configured interval.

## Task Selection

Choose the first incomplete item returned by the configured sources unless the user states another priority rule. Treat these as actionable:

- Markdown checkbox items like `- [ ] Email Sam the contract`
- TODO lines like `TODO: check production deploy`

Skip items that are already complete, blocked, waiting on someone else, or phrased as vague buckets with no executable next step. If the top item is vague but a reasonable first action is obvious, do that first action and record the interpretation.

## Safety Rules

Do not access Apple Notes, Messages, iMessage, email, calendars, or other private apps unless the user configured that source or explicitly asks for it in the current session.

Ask before externally visible or destructive actions, including sending messages or emails, deleting data, buying anything, changing billing, force-pushing, deploying to production, or contacting third parties.

If a task requires credentials, paid services, 2FA, or production access that is not already available, stop with a concise blocker note and do not mark the item complete.

## Source Notes

Use `references/sources.md` for source setup details. The default source is a local Markdown file at `inbox/todo.md`.

Google Docs, Notion, and Apple Notes support are opt-in sources. Google Docs and Notion can mark completed tasks when configured with write auth and `writeback: "mark_done"` or clear/archive task content with `writeback: "delete"`. Apple Notes uses macOS AppleScript, so macOS may prompt for automation permission. Direct iMessage database access is not enabled by default; prefer exporting or mirroring iMessage todos into the local Markdown inbox unless the user explicitly configures a safer source adapter.
