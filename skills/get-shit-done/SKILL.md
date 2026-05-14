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
- Do not create lower-tier workers by default. Every worker/sub-agent must use the best available model unless the user explicitly requests a different model, cheaper mode, faster mode, or runtime default.
- If no worker/sub-agent mechanism exists, stop with `needs_human` or blocked status instead of silently executing inline, unless the user explicitly permits inline fallback for that run.
- Do not mark a task done until it was already in-progress.
- Do not leave a completed or blocked task without updating the source.
- Do not skip goal mode. Codex must use native goal mode with `create_goal` when available. Claude Code must use the `TaskCreate` tool (Claude Code's goal-mode primitive: each task is a persistent named objective with `pending` / `in_progress` / `completed` lifecycle). Other agents use `goal_state.py`.
- Do not skip the recurring schedule. On any interactive invocation, ensure a recurring drain check is scheduled (default every 15 min, allowed range 10-20 min, user-tweakable). If one is already active, leave it alone.
- Do not finish a task without creating and opening an HTML handoff report that states what was done, what was verified, and what the user still needs to do. On macOS, open the handoff in the background so it does not steal focus: `open -g <path>`. On Linux use `xdg-open <path>` (no background flag needed). The `handoff_report.py` helper already handles this.
- Do not skip completion email when `config/notifications.json` or email env vars provide a recipient.
- Do not stop after one task when the user invoked drain/watch mode; keep going until the configured source has no unclaimed actionable items.
- When useful improvements appear during work, append them to the source document under `Suggested Changes`. **North Star: every suggested change must increase revenue.** Filter every candidate suggestion through: does this drive revenue up, directly (more qualified leads, higher reply rate, higher conversion, higher price capture, faster sales cycle, more expansion or retention) or indirectly (product quality that compounds into retention, removing a blocker that frees the user's time for revenue work, fixing a public surface that prospects see)? If a suggestion cannot trace to revenue in one sentence, drop it. Lead each suggestion with the revenue mechanism (e.g. "Raises reply rate on X campaign because...", "Frees Y hours/week for outbound by..."), not the aesthetic or cleanup motivation.

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
2. Activate the overarching drain goal. This step is mandatory and runtime-specific. Pick the row that matches the runtime you are in and execute the listed call before reading any todo. Always also write the fallback file so other tooling can inspect goal state:
   - Codex: call the `create_goal` tool with title `"Clear all actionable tasks from the configured todo sources"` as your very next action. If goal tools are not exposed in this Codex session, say so out loud and continue with the fallback file only.
   - Claude Code: call the `TaskCreate` tool with `subject: "Drain Agent TODO Notion page"` (or the configured source name) and `description: "Clear all actionable tasks from the configured todo sources"`, then `TaskUpdate(taskId, status: "in_progress")` so the drain shows as active in the harness task list. This is Claude Code's `create_goal` analog. Mark it `completed` only at Step 19. If `TaskCreate` is not exposed in this sub-agent context, restate the goal verbatim in your first user-facing line and treat it as your only objective.
   - Hermes: write the goal to `state/overarching_goal.md` via `goal_state.py activate-drain` and include the goal text in the first system block of every Hermes worker prompt so the runtime carries it across turns.
   - OpenClaw: use `goal_state.py activate-drain`, then include the contents of `state/overarching_goal.md` inline in every OpenClaw agent turn (`run_loop.py` already embeds the goal in the prompt body, since OpenClaw has no separate context-file flag).
   - Any other runtime: `python3 skills/get-shit-done/scripts/goal_state.py activate-drain` and include the goal text at the top of the worker prompt.

   Whichever runtime is active, the fallback file `state/overarching_goal.md` must exist and be current for the duration of the drain; close it with `goal_state.py close-drain` only after the queue is empty.
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
6. Turn the claimed todo into the active task goal before any worker is spawned. Same runtime-specific rule as Step 2, but for the per-task goal. Always also write `state/current_goal.md` via `goal_state.py activate` so the worker prompt can reference it.
   - Codex: call `create_goal` with the claimed todo title as the concrete objective. If a goal is already open, close it first with `close_goal` so the new task is the sole active objective.
   - Claude Code: call `TaskCreate({subject: "<claimed todo title>", description: "<one-line context>", activeForm: "<present-continuous phrasing>"})`, then `TaskUpdate(taskId, status: "in_progress")` before dispatching the worker. This is Claude Code's `create_goal` analog and is what shows up in the harness task tracker. For sub-agents spawned via the Agent tool (which inherit the parent task list but cannot create their own top-level tasks reliably), embed the goal text verbatim as the first line of the sub-agent prompt and tell the worker "this is your only objective for this turn, do not expand scope."
   - Hermes: `goal_state.py activate --task '<todo>' --source-id '<source>' --item-id '<item>'` then pass the resulting `state/current_goal.md` into the Hermes worker prompt's system block.
   - OpenClaw: `goal_state.py activate ...` then include the contents of `state/current_goal.md` inline in the OpenClaw agent turn (run_loop.py embeds it in the prompt body, no separate flag needed).
   - Any other runtime: `goal_state.py activate ...` and include the goal text at the top of the worker prompt.

   The goal must be closed (Step 14) before claiming the next todo. Never run two task-goals in parallel for the same drain.
7. Clarify only when the task cannot be executed safely or meaningfully without more input.
8. Assign execution to a dedicated worker/sub-agent. Every worker prompt MUST begin with the goal-mode preamble below before any task instruction. The preamble is what makes goal mode actually fire inside the worker, not just inside the orchestrator.

   **Worker prompt preamble (required, verbatim block at top of every worker prompt):**

   ```
   ## Goal Mode (do this first, before reading anything else)
   Your active goal: <claimed todo title>
   Parent drain goal: Clear all actionable tasks from the configured todo sources.
   Goal file (fallback): state/current_goal.md
   Drain goal file (fallback): state/overarching_goal.md

   Activation, runtime-specific:
   - Codex: call create_goal("<claimed todo title>") as your first action.
   - Claude Code: call TaskCreate({subject: "<claimed todo title>", description: "<one-line context>"}) then TaskUpdate(taskId, status: "in_progress") as your first action. This is Claude Code's create_goal analog.
   - Hermes: read state/current_goal.md and acknowledge the goal in your first reply line.
   - OpenClaw: acknowledge the goal in your first turn and reference state/current_goal.md.
   Then proceed to the task below. Do not start a second task in this turn. Do not expand scope.
   ```

   Then dispatch with the runtime-appropriate spawner:
   - Codex: spawn exactly one worker sub-agent for the claimed task when `spawn_agent` is available. Set the worker model to the best available Codex model unless the user explicitly requested a different model, cheaper mode, faster mode, or runtime default. Tell the worker it is not alone in the codebase and must not mark the source done, close the goal, or send notifications.
   - Claude Code: use Claude Code's native sub-agent/task-worker mechanism (e.g. the Agent tool) with the same boundaries. Use the `opus` model alias or the best available Claude Code model, and set `CLAUDE_CODE_SUBAGENT_MODEL=opus` when that environment control is available, unless the user explicitly requested something else. The preamble above is the substitute for `/goal` since sub-agents cannot run slash commands.
   - Hermes: use `--runtime hermes` or an equivalent Hermes one-shot `hermes chat -q` worker command. Default model selection to the best available model when the runtime accepts a model flag, and preload Hermes skills with `--hermes-skill` when needed.
   - OpenClaw: use `--runtime openclaw --openclaw-agent <name>` or `OPENCLAW_AGENT=<name>` so each claimed task is sent as one OpenClaw agent turn. Use the configured best OpenClaw model and default to `--thinking xhigh` unless the user explicitly requested another thinking level.
   - Headless watcher mode: treat the configured `TODO_SKILL_AGENT_CMD` or `--agent-command` invocation as the worker boundary; that worker must create a sub-agent when its runtime supports one.
   - If no worker/sub-agent mechanism exists, mark the task blocked or `needs_human` with "No sub-agent mechanism available" unless the user explicitly allowed inline fallback.
9. Track the assignment in the ledger when `config/ledger.json` is enabled:

```bash
python3 skills/get-shit-done/scripts/ledger.py assigned --config config/ledger.json --task '<task>' --source-id '<source>' --item-id '<item>' --agent '<worker id>' --status running
```

10. Review the worker result, then verify with the narrowest meaningful check: tests, command output, file diff, browser QA, sent/draft status, or source-specific proof.
11. If the worker or inline execution surfaces useful next-step ideas, append them to the source under `Suggested Changes`. **North Star = revenue.** Every suggestion must answer "how does this move revenue?" in its first clause. Categories that pass: (a) more or higher-quality leads in pipeline, (b) higher open/reply/meeting/close rate on active campaigns, (c) faster sales cycle or larger deal size, (d) better retention or expansion on existing customers, (e) product/site quality fixes on prospect-facing surfaces, (f) automation that frees the user's calendar for revenue work, (g) killing or descoping money-losing efforts. Categories that fail and should be dropped: pure aesthetics, abstract refactors with no revenue link, busy-work cleanup, hobby ideas, advice the user already knows. Phrase each surviving suggestion revenue-first, not chore-first. Bad: "Add Vercel analytics to the landing page." Good: "Add Vercel analytics to the landing page so we can see which referrer drives Enricher signups and double down on the converting channel."

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

14. Close the active task goal in the runtime, then write the fallback file:
   - Codex: call `close_goal` with the completion summary.
   - Claude Code: call `TaskUpdate(taskId, status: "completed")` for the per-task goal you opened in Step 6. This is Claude Code's `close_goal` analog. For blocked/needs_human outcomes, still mark `completed` so the goal row clears, and capture the actual outcome in the handoff report + ledger row.
   - Hermes / OpenClaw / generic: nothing runtime-specific; the fallback file write below is sufficient.

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

19. Repeat from step 3 until no actionable item remains. When the queue is empty, close the overarching drain goal so a future invocation starts clean. In Codex call `close_goal`. In Claude Code call `TaskUpdate(drainTaskId, status: "completed")` on the parent drain task you opened in Step 2 (Claude Code's `close_goal` analog). In any runtime also run:

```bash
python3 skills/get-shit-done/scripts/goal_state.py close-drain --status done --summary '<count> tasks cleared, <count> blocked'
```

If a continuous watcher is running, sleep for the configured interval, then drain again. On the next non-empty cycle, re-activate the drain goal via Step 2 before claiming the next todo.

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
