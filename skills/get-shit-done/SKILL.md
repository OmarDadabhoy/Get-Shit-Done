---
name: get-shit-done
description: Work through the user's todo inbox one item at a time. Use when the user invokes "get shit done", "$get-shit-done", asks Codex or Claude Code to take the next task from a todo list, Google Doc, Apple Notes note, exported Messages/iMessage note, or configured inbox, or wants an agent to keep polling for new tasks and execute them with verification.
---

# Get Shit Done

## Operating Contract

Pick the next actionable todo, make it the active objective, execute it end to end, verify the result, and leave a concise audit trail. Do not batch unrelated todos unless the user explicitly asks.

This skill is agent-framework agnostic. In Codex, use goal mode when available. In Claude Code or other agents, emulate the active goal by writing `state/current_goal.md` in the TodoSkill repo.

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
3. Turn the todo into the active goal:
   - Codex: call `create_goal` with the todo as the concrete objective when goal tools are available and no active goal already exists.
   - Claude Code or other agents: write `state/current_goal.md` with the todo, source id, item id, and timestamp.
4. Clarify only when the task cannot be executed safely or meaningfully without more input.
5. Execute the task using the normal tools available in the current agent environment.
6. Verify with the narrowest meaningful check: tests, command output, file diff, browser QA, sent/draft status, or source-specific proof.
7. Mark the item complete when the source supports it:

```bash
python3 skills/get-shit-done/scripts/todo_source.py mark --config config/todo_sources.json --item-id '<item-id>' --status done
```

8. Append a short note to `state/completions.md` with the task, result, verification, and any follow-up.
9. If a continuous watcher is running, let it poll again after the configured interval.

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

Google Docs and Apple Notes support are opt-in read sources. Google Docs uses plain-text export and may require a public/published doc or a configured access token. Apple Notes uses macOS AppleScript, so macOS may prompt for automation permission. Direct iMessage database access is not enabled by default; prefer exporting or mirroring iMessage todos into the local Markdown inbox unless the user explicitly configures a safer source adapter.
