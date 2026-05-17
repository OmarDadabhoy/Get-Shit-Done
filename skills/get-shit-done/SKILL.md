---
name: ai-slaves
description: This skill should be used when the user invokes "/ai-slaves", "/get-shit-done", "AI Slaves", "get shit done", asks Codex or Claude Code to drain a todo list, Google Doc, Notion page, Apple Notes note, exported Messages/iMessage note, or configured inbox, or wants an agent to keep polling for new tasks and execute them with verification.
---

# AI Slaves

## Operating Contract

Drain the configured todo source until no actionable item remains. For every drain cycle: fetch the queued/actionable batch, claim the batch in source priority/order, spawn exactly one dedicated worker/sub-agent per claimed task concurrently, verify and reconcile each result as workers finish, mark each task done or blocked in the source, send email when available, and leave a concise audit trail.

These are hard gates:

- Do not execute a task until the source item is marked in-progress.
- Do not drain queues one task at a time when multiple queued tasks can be claimed. Claim the current batch in priority/order, then run one dedicated worker/sub-agent per claimed task concurrently.
- Do not execute a claimed task inline when Codex, Claude Code, or the configured runtime can create a worker/sub-agent. Every Notion, Google Docs, and local-file task gets its own worker/sub-agent.
- Do not create lower-tier workers by default. Every worker/sub-agent must use the best available model unless the user explicitly requests a different model, cheaper mode, faster mode, or runtime default.
- In Codex, every worker/sub-agent must use model `gpt-5.5` with `xhigh` reasoning unless Omar explicitly requests a different model, cheaper mode, faster mode, or runtime default.
- If no worker/sub-agent mechanism exists, stop with `needs_human` or blocked status instead of silently executing inline, unless the user explicitly permits inline fallback for that run.
- Do not mark a task done until it was already in-progress.
- Do not leave a completed or blocked task without updating the source.
- Do not skip goal mode. Codex must use native goal mode with `create_goal` when available. Claude Code must use the `TaskCreate` tool (Claude Code's goal-mode primitive: each task is a persistent named objective with `pending` / `in_progress` / `completed` lifecycle). Other agents use `goal_state.py`.
- Do not skip the recurring schedule. On any interactive invocation, ensure a recurring drain check is scheduled (default every 15 min, allowed range 10-20 min, user-tweakable). If one is already active, leave it alone.
- Do not finish a task without creating AND OPENING an HTML handoff report that states what was done, what was verified, and what the user still needs to do. **Opening is mandatory, not optional.** On macOS use `open -g <path>` (background, no focus steal). On Linux use `xdg-open <path>`. **Never pass `--no-open` to `handoff_report.py`** in the orchestrator path; the helper defaults to open and the orchestrator must let it open. For analysis, audit, research, or progress-check tickets, the worker must also produce a content-rich HTML at `/tmp/<slug>.html` (the actual readable artifact, not just the meta handoff) and open it the same way. Both files get opened. The dashboard's `done_log` row links to the handoff path; the content HTML is what Omar actually reads.
- Do not skip completion email when `config/notifications.json` or email env vars provide a recipient.
- Do not stop after one task when the user invoked drain/watch mode; keep going until the configured source has no unclaimed actionable items.
- Every drain cycle must write three things back to the dashboard: `suggested_changes` rows, `followups` rows, and `done_log` rows. Their roles:
  - `Suggested Changes` (`POST /api/suggested_changes`) = revenue-first proposals for new work Omar may want to promote into the checklist.
  - `Follow-up` (`POST /api/followups`) = outstanding questions, decisions, or blockers that need Omar's input before the orchestrator can move forward. One row per item, written as a question or imperative directed at Omar. Format: `<task name>: <specific question or decision Omar needs to make>.` Example: `CTA placement: pick recommended (kill banner + nav button + empty-state link) / alt1 (footer) / alt2 (dedicated /for-farmers page) / keep current.`
  - `Done` (`POST /api/done_log`) = 1-line summary per completed task in the cycle. Omar reads these in the dashboard for triage and clicks into the HTML handoff only when he needs detail. Format: `<task name>: <verb-led one-phrase outcome>. <handoff path>.` Keep prose 50-80 chars before the path. No padding, no recap sentences. Examples:
    - GOOD: `VC list spot-check: 64 of 1041 firms pass (Battery/Menlo/First Round/etc top 10). state/reports/<file>.html`
    - GOOD: `Stripe Alt tweaks: 3 edits proposed, 5 pre-activation checks flagged. state/reports/<file>.html`
    - BAD: `Reviewed the campaign and proposed some tweaks that I think will work well, plus flagged some things to check before activating.` (padded, no numbers, no path)
  The `PATCH /api/tasks/<id> {"status":"done","handoff":"<path>"}` write on the original ticket stays as the source-of-truth ledger. The `done_log` rows are the human-readable index that lets Omar scan the cycle without expanding every ticket.
- When useful improvements appear during work, append them to the source document under `Suggested Changes`. **North Star: every suggested change must increase revenue.** Filter first: if a candidate cannot trace to revenue in one sentence (more leads, higher reply rate, higher conversion, faster cycle, retention, expansion, freed calendar for revenue work, fixed prospect-facing surface), drop it. **Plain-language rule for surviving suggestions:** Sentence 1 = the concrete change in plain English (what code, copy, or action, and where, in 1 sentence a non-technical reader could explain back). Sentence 2 = the revenue mechanism in plain English, max 1 hop of causation. No "X drives Y drives Z" chains. Optional sentence 3 = a number if available (e.g. "current claim rate is ~3/week"). Two sentences max otherwise. Lead with the change, not the framing.

  **Good SC examples:**
  - "Send Omar an email each time someone claims a farm. Faster follow-up means more claims convert into active farmers, which is the revenue mechanism."
  - "Add a 'My farm got claimed by X people this month' line to the claim banner. If a farmer sees their neighbors signing up, they sign up too."
  - "Expose a /farms.csv download so HN commenters can poke at the data without scraping. Data nerds posting good comments on HN posts is how farm-to-door grows."

  **Bad SC examples (do not produce these):**
  - "Add a claims-this-month counter on the home /claim banner. Social proof drives more claims; claims drive supply density; density is the SEO moat that defends against LocalHarvest." (3-link causation chain, abstract, buries the change)
  - "Wire a POST /farm-listings webhook that pings omar@potarix.com on every new claim. Manual follow-up within an hour is the conversion lever for cold farmers who claimed on impulse but will ghost without response." (concrete change buried behind jargon; rewrite as the first good example)
  - "Turns the Show HN into a tools-and-data conversation, which converts to higher-quality inbound." (leads with framing, no concrete change stated)
- Do not pad write-ups. Every handoff field, `Suggested Changes` item, completion email, and `state/completions.md` entry must follow **Write-Up Style (Required)** below: skimmable in 10 seconds, lead with the result, numbers and names over adjectives, no hedges or recap sentences.

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

## Write-Up Style (Required)

Omar reads handoffs and completion notes in bulk and discards anything padded. Every user-facing field must be skimmable in under 10 seconds. This covers handoff `--summary`, `--verification`, `--needs-from-user`; `Suggested Changes` items; completion email body; and `state/completions.md` entries.

Rules:

- Lead with the result, not the process. "Sent draft to Sam." beats "I went to Gmail and composed a message and then..."
- One short paragraph or 3-5 bullets max per field. If it does not fit, you are padding.
- Cut hedges, recap sentences, and "I successfully..." openers. State facts.
- Numbers and names over adjectives. "47 leads uploaded, 0 errors" beats "uploaded a good number of leads with no major issues".
- Verification means the actual check, not a description of checking. Paste the count, URL, test name, command output, or file path.
- `--needs-from-user` is the literal next action(s) in imperative voice. If nothing is needed, write "Nothing." Do not pad.
- No em dashes or en dashes. Use commas, periods, or rewrite the sentence.
- Plain English. Define or expand acronyms the first time unless they are obvious to Omar (Instantly, Apollo, AMF, Clay, Notion, Supabase are fine).

Examples:

- Bad summary: "I went through the list of leads carefully and uploaded each one to the campaign, making sure to validate the email addresses along the way."
- Good summary: "Uploaded 47 leads to campaign c575ab6e. 0 errors. 2 skipped (already in workspace)."
- Bad verification: "Verified that everything is working correctly by checking the campaign in Instantly."
- Good verification: "GET /api/v2/campaigns/c575ab6e/leads returned 47 active leads."
- Bad needs-from-user: "Whenever you have a moment, it would be great if you could go ahead and unpause the campaign at your convenience."
- Good needs-from-user: "Unpause campaign c575ab6e in Instantly."

The same style applies to anything the orchestrator writes back to the source (status notes, comments) and to the worker's reply that the orchestrator extracts text from. If the worker returns padded prose, the orchestrator must condense it before writing the handoff, not just paste it through.

## Quick Start

Pick one of four source modes. Step 0 in the Workflow auto-selects. **If you do not already have a setup, use Dashboard mode.** See "Why the dashboard is the recommended setup" below for why.

**Dashboard mode** (recommended, Omar's setup). Source = `http://127.0.0.1:5176` (UI at `http://127.0.0.1:5179`). Discover the queued batch:

```bash
curl -sf http://127.0.0.1:5176/api/tasks | jq '[.[] | select(.status == "queued") | {id, text, assigned_next, created_at}] | sort_by(.assigned_next == true | not, .created_at)'
```

Claim the returned batch in that order. `assigned_next: true` items come first.

**Google Docs mode**. Source = a Google Doc passed as the `/ai-slaves` argument (URL or id) or named in `config/todo_sources.json`. Discover the actionable batch with the runtime's Google Docs reader (`gws-docs`, `documents.get`, or equivalent) and collect unchecked checkbox bullets under the Tasks section. See "Google Docs source" in Source Notes for the discriminator and writeback patterns.

**Notion mode**. Source = a Notion page passed as the `/ai-slaves` argument (any `notion.so` URL) or named in `config/todo_sources.json`. Discover the actionable batch with `mcp__claude_ai_Notion__fetch` and collect unchecked `to_do` blocks under the Tasks section. See "Notion source" in Source Notes for the discriminator and writeback patterns.

**Local Markdown mode** (zero setup). Source = `inbox/todo.md` (or whatever the config names). Discover claimable items with the configured helper. If the helper only returns one item, repeat discover/claim until no unclaimed item remains, then dispatch the claimed set together:

```bash
python3 skills/get-shit-done/scripts/todo_source.py next --config config/todo_sources.json
```

For a background watcher that drains every cycle, use:

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

0. Determine source mode before doing anything. Probe the dashboard, then branch:

   ```bash
   curl -sf --max-time 3 http://127.0.0.1:5176/api/health
   ```

   Selection rules (apply in order, first match wins):

   ```
   if curl /api/health succeeds:                  source_mode = "dashboard"
   elif arg is a Google Doc URL or doc id:        source_mode = "google_docs"
   elif arg contains "notion.so":                 source_mode = "notion"
   elif arg is a file path (e.g. inbox/todo.md):  source_mode = "local_markdown"
   elif config/todo_sources.json names a doc:     source_mode = "google_docs"
   elif config/todo_sources.json names a notion:  source_mode = "notion"
   elif config/todo_sources.json names a file:    source_mode = "local_markdown"
   else:                                          needs_human "no source configured"
   ```

   Precedence: explicit user argument beats dashboard reachability beats config default beats local markdown fallback. State the selected `source_mode` in the first user-facing line so the user can override.

   The four supported modes:

   - **Dashboard mode** (recommended for new users, Omar's setup). Reads and writes go to the Express server at `http://127.0.0.1:5176`. UI at `http://127.0.0.1:5179`. State files in `~/Desktop/Ai-slaves-dashboard/data/*.json`.
   - **Google Docs mode** (alternative for users who prefer Docs over a local app). Reads and writes go through the `gws-docs` / Google Docs API against the configured Doc id. Checkbox bullets are tasks, disc bullets are Suggested Changes / Follow-up / Done sections.
   - **Notion mode** (alternative for users who live in Notion). Reads and writes go through the Notion MCP (`mcp__claude_ai_Notion__*`). `to_do` blocks are tasks, `bulleted_list_item` blocks under output headings are Suggested Changes / Follow-up / Done sections.
   - **Local Markdown mode** (always works, zero setup). Reads `inbox/todo.md`, writes status via in-place rewrites of the checkbox lines. Best for offline use or unit tests.

   Do not silently fall back from one mode to another mid-cycle. If the chosen source was reachable at Step 0 and goes down later, stop with `needs_human` (state drift risk). The branch is locked at Step 0 for the remainder of the cycle.

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
3. Load the currently queued/actionable batch from the active source.

   **Dashboard mode:**

   ```bash
   curl -sf http://127.0.0.1:5176/api/tasks \
     | jq '[.[] | select(.status == "queued")] | sort_by(.assigned_next == true | not, .created_at)'
   ```

   Use the full returned batch. The sort puts `assigned_next: true` items ahead of the rest. Omar uses that flag in the dashboard UI to inject tickets to the head of the queue.

   **Or in Google Docs mode:** fetch the Doc via `gws-docs` or `documents.get`, walk `body.content[].paragraph` in order, collect every paragraph whose `bullet.listId` resolves to a checkbox list (see discriminator rule below) and whose checkbox is unchecked (`bullet.textStyle.strikethrough != true` and the line does not begin with `(done)` or `(in-progress`). Skip lines under the `Suggested Changes`, `Follow-up`, or `Done` headers, those are output sections, not task input. Capture each paragraph's `startIndex` and `endIndex` for use in Steps 5 and 13.

   **Or in Notion mode:** fetch the page block children via `mcp__claude_ai_Notion__fetch` against the configured page id, walk the block list in order, collect every block whose `type == "to_do"` and whose `to_do.checked == false` and whose rich text does not begin with `(done)` or `(in-progress`. Skip blocks under the `Suggested Changes`, `Follow-up`, or `Done` headings, those are `bulleted_list_item` output rows. Capture each block id for use in Steps 5 and 13.

   **Or in Local Markdown mode:** list all actionable `- [ ]` lines in source order. If only `todo_source.py next` is available, claim one item at a time only for the claim primitive, then dispatch the successfully claimed set together.

   Skip items whose text starts with `(ack)` or that explicitly require human-in-the-loop steps not yet approved (see Safety Rules).
4. If no queued/actionable item exists, report that the inbox is empty and stop or sleep until the next scheduled poll.
5. Claim the batch before any execution.

   **Dashboard mode:** PATCH each dashboard ticket to `in_progress` in the sorted order from Step 3:

   ```bash
   curl -sf -X PATCH http://127.0.0.1:5176/api/tasks/<id> \
     -H 'Content-Type: application/json' \
     -d '{"status":"in_progress"}'
   ```

   If a PATCH 4xx/5xxs (already claimed, deleted, server error), skip that row and continue claiming the rest of the current batch. If the dashboard is unreachable mid-drain, stop with `needs_human` per Step 0.

   **Or in Google Docs mode:** stamp each claimed line with `(in-progress YYYY-MM-DD)` via `documents.batchUpdate` using `replaceAllText` requests scoped to the captured paragraph ranges. Pattern:

   ```json
   {
     "replaceAllText": {
       "containsText": { "text": "<original line text>", "matchCase": true },
       "replaceText": "(in-progress 2026-05-15) <original line text>"
     }
   }
   ```

   The checkbox glyph stays untouched, the stamp is the lock. Re-read the Doc after the batchUpdate to confirm each stamp landed; if another claimant got there first (no stamp applied), skip that item and keep the successfully claimed set.

   **Or in Notion mode:** call `mcp__claude_ai_Notion__notion-update-page` on each captured `to_do` block id. Keep `to_do.checked` false (Notion's checkbox toggle is reserved for the done state in Step 13), and replace the block's rich text with `(in-progress YYYY-MM-DD) <original text>`. The leading stamp is the lock. Re-fetch each block to confirm; if another claimant got there first (the stamp is missing or differs), skip that item and keep the successfully claimed set.

   **Or in Local Markdown mode:** run `python3 skills/get-shit-done/scripts/todo_source.py claim --config config/todo_sources.json --item-id '<item-id>'` for each selected item and keep the successfully claimed set.
6. Prepare one per-task goal context for each claimed task before workers are spawned. Same runtime-specific rule as Step 2, but scoped to each worker. Always also write or render a `state/current_goal.md` equivalent into that worker's prompt so the worker can reference it.
   - Codex: the parent drain keeps the overarching drain goal active. Each Codex worker must call `create_goal` with its claimed todo title as its first action from the preamble. Use model `gpt-5.5` with `xhigh` reasoning unless Omar explicitly requested a different model, cheaper mode, faster mode, or runtime default.
   - Claude Code: call `TaskCreate({subject: "<claimed todo title>", description: "<one-line context>", activeForm: "<present-continuous phrasing>"})`, then `TaskUpdate(taskId, status: "in_progress")` before dispatching the worker. This is Claude Code's `create_goal` analog and is what shows up in the harness task tracker. For sub-agents spawned via the Agent tool (which inherit the parent task list but cannot create their own top-level tasks reliably), embed the goal text verbatim as the first line of the sub-agent prompt and tell the worker "this is your only objective for this turn, do not expand scope."
   - Hermes: `goal_state.py activate --task '<todo>' --source-id '<source>' --item-id '<item>'` then pass the resulting `state/current_goal.md` into the Hermes worker prompt's system block.
   - OpenClaw: `goal_state.py activate ...` then include the contents of `state/current_goal.md` inline in the OpenClaw agent turn (run_loop.py embeds it in the prompt body, no separate flag needed).
   - Any other runtime: `goal_state.py activate ...` and include the goal text at the top of the worker prompt.

   The per-task goal must be unique per claimed task. Do not serialize a drain just to keep one parent-side task goal active; parallel task goals are required when a batch has multiple claimed tasks.
7. Clarify only when the task cannot be executed safely or meaningfully without more input.
8. Spawn one dedicated worker/sub-agent for each claimed task concurrently. Every worker prompt MUST begin with the goal-mode preamble below before any task instruction. The preamble is what makes goal mode actually fire inside the worker, not just inside the orchestrator.

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

   Then dispatch the full claimed batch with the runtime-appropriate spawner:
   - Codex: spawn exactly one worker sub-agent per claimed task when `spawn_agent` is available. Run those workers concurrently. Set every Codex worker to model `gpt-5.5` with `xhigh` reasoning unless Omar explicitly requested a different model, cheaper mode, faster mode, or runtime default. Tell the worker it is not alone in the codebase and must not mark the source done or send notifications.
   - Claude Code: use Claude Code's native sub-agent/task-worker mechanism (e.g. the Agent tool) with the same boundaries. Use the `opus` model alias or the best available Claude Code model, and set `CLAUDE_CODE_SUBAGENT_MODEL=opus` when that environment control is available, unless the user explicitly requested something else. The preamble above is the substitute for `/goal` since sub-agents cannot run slash commands.
   - Hermes: use `--runtime hermes` or an equivalent Hermes one-shot `hermes chat -q` worker command. Default model selection to the best available model when the runtime accepts a model flag, and preload Hermes skills with `--hermes-skill` when needed.
   - OpenClaw: use `--runtime openclaw --openclaw-agent <name>` or `OPENCLAW_AGENT=<name>` so each claimed task is sent as one OpenClaw agent turn. Use the configured best OpenClaw model and default to `--thinking xhigh` unless the user explicitly requested another thinking level.
   - Headless watcher mode: treat the configured `TODO_SKILL_AGENT_CMD` or `--agent-command` invocation as the worker boundary; that worker must create a sub-agent when its runtime supports one.
   - If no worker/sub-agent mechanism exists, mark the task blocked or `needs_human` with "No sub-agent mechanism available" unless the user explicitly allowed inline fallback.

   **Agent visibility (dashboard mode only).** At the moment you spawn each worker, POST a row to `/api/agents` so Omar can see live agents in the dashboard:

   ```bash
   curl -sf -X POST http://127.0.0.1:5176/api/agents \
     -H 'Content-Type: application/json' \
     -d '{"agentId":"<worker id>","drain_cycle_id":"<ISO timestamp of this drain cycle>","task_title":"<claimed todo text>","status":"running","spawned_at":"<ISO now>"}'
   ```

   Capture each response body's `id` (dashboard assigns `ag-NNN`). Stash it in that worker context. As each worker returns:

   ```bash
   curl -sf -X PATCH http://127.0.0.1:5176/api/agents/<ag-id> \
     -H 'Content-Type: application/json' \
     -d '{"status":"completed","completed_at":"<ISO now>"}'
   ```

   On worker errors, PATCH `{"status":"errored","completed_at":"<ISO now>"}`. If a POST fails, log the failure to the handoff and continue, the agent row is best-effort and must not block worker dispatch.

   **Or in Google Docs mode / Notion mode / Local Markdown mode:** skip the agent rows (no dashboard to write to). The ledger row in Step 9 is the audit trail in those modes.
9. Track the assignment in the ledger when `config/ledger.json` is enabled:

```bash
python3 skills/get-shit-done/scripts/ledger.py assigned --config config/ledger.json --task '<task>' --source-id '<source>' --item-id '<item>' --agent '<worker id>' --status running
```

10. As workers finish, review each result and verify with the narrowest meaningful check: tests, command output, file diff, browser QA, sent/draft status, or source-specific proof.
11. If the worker or inline execution surfaces useful next-step ideas, append them to the source under `Suggested Changes`. **North Star = revenue.** Every suggestion must trace to revenue in one sentence or be dropped. Categories that pass: (a) more or higher-quality leads in pipeline, (b) higher open/reply/meeting/close rate on active campaigns, (c) faster sales cycle or larger deal size, (d) better retention or expansion on existing customers, (e) product/site quality fixes on prospect-facing surfaces, (f) automation that frees the user's calendar for revenue work, (g) killing or descoping money-losing efforts. Categories that fail and should be dropped: pure aesthetics, abstract refactors with no revenue link, busy-work cleanup, hobby ideas, advice the user already knows.

   **Plain-language rule for surviving suggestions (mandatory):** Sentence 1 = the concrete change in plain English (what code, copy, or action, and where, in 1 sentence a non-technical reader could explain back). Sentence 2 = the revenue mechanism in plain English, max 1 hop of causation. No "X drives Y drives Z" chains. Optional sentence 3 = a number if available. Two sentences max otherwise. Lead with the change, not the framing.

   **Good SC examples:**
   - "Send Omar an email each time someone claims a farm. Faster follow-up means more claims convert into active farmers, which is the revenue mechanism."
   - "Add a 'My farm got claimed by X people this month' line to the claim banner. If a farmer sees their neighbors signing up, they sign up too."
   - "Expose a /farms.csv download so HN commenters can poke at the data without scraping. Data nerds posting good comments on HN posts is how farm-to-door grows."

   **Bad SC examples (do not produce these):**
   - "Add a claims-this-month counter on the home /claim banner. Social proof drives more claims; claims drive supply density; density is the SEO moat that defends against LocalHarvest." (3-link causation chain, abstract, buries the change)
   - "Wire a POST /farm-listings webhook that pings omar@potarix.com on every new claim. Manual follow-up within an hour is the conversion lever for cold farmers who claimed on impulse but will ghost without response." (concrete change buried behind jargon; rewrite as the first good example)
   - "Turns the Show HN into a tools-and-data conversation, which converts to higher-quality inbound." (leads with framing, no concrete change stated)

   **Dashboard mode:** POST each surviving suggestion:

   ```bash
   curl -sf -X POST http://127.0.0.1:5176/api/suggested_changes \
     -H 'Content-Type: application/json' \
     -d '{"text":"<suggestion>","cycle":<N>,"status":"pending"}'
   ```

   Omar reviews these in the dashboard UI and promotes the ones he wants via `POST /api/suggested_changes/<id>/promote`, which atomically creates a queued ticket. The orchestrator does not promote SC items itself.

   **Or in Google Docs mode:** append each suggestion to the `Suggested Changes` section as a disc bullet. Find the section header `Suggested Changes` in the Doc, locate its containing segment, and append via `documents.batchUpdate` using `insertText` at `endOfSegmentLocation` for that section, followed by `createParagraphBullets` with `bulletPreset: "BULLET_DISC_CIRCLE_SQUARE"` over the inserted range. The bold section header must remain a regular paragraph (no checkbox glyph), the bullets under it are disc-style.

   ```json
   {
     "requests": [
       { "insertText": { "endOfSegmentLocation": { "segmentId": "" }, "text": "<suggestion>\n" } },
       { "createParagraphBullets": { "range": { "startIndex": <s>, "endIndex": <e> }, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE" } }
     ]
   }
   ```

   The `endOfSegmentLocation` form is mandatory (cycle 14): the indexed-location form drifts when concurrent batchUpdates land between read and write, `endOfSegmentLocation` is the only stable anchor for appends.

   **Or in Notion mode:** append a `bulleted_list_item` child block under the `Suggested Changes` heading block via `mcp__claude_ai_Notion__notion-update-page` (block-append on the parent page id, with the new block placed after the heading's existing children). Block payload:

   ```json
   {
     "type": "bulleted_list_item",
     "bulleted_list_item": {
       "rich_text": [{"type": "text", "text": {"content": "<suggestion>"}}]
     }
   }
   ```

   Notion's block-type discriminator is exact: `to_do` is for tasks, `bulleted_list_item` is for output rows. No glyph parsing, no list-id lookup, no ambiguity (this is the win over Google Docs' listId glyph hack).

   **Or in Local Markdown mode:** `python3 skills/get-shit-done/scripts/suggested_changes.py --config config/todo_sources.json --source-id '<source>' --task '<task>' --suggestion '<suggestion>'`.

12. Create AND OPEN the HTML handoff report (all modes). Opening is mandatory.

```bash
python3 skills/get-shit-done/scripts/handoff_report.py --status done --task '<task>' --summary '<what happened>' --verification '<verification>' --needs-from-user '<anything needed from the user>'
```

   **Do NOT pass `--no-open`.** The helper defaults to opening the file in the background on macOS (`open -g <path>`) and via `xdg-open` on Linux. The orchestrator must let the open happen. If you suppress it, Omar never sees the handoff.

   **For analysis / audit / research / progress-check tickets**, the WORKER additionally generates a content-rich HTML (the actual readable artifact: tables, stats, recommendations) at `/tmp/<slug>.html` and opens it with the same `open -g` (macOS) / `xdg-open` (Linux) command. The handoff_report.py file is a meta summary; the content HTML is what Omar actually reads. Both get opened. The worker's reply must include both paths so the orchestrator can reference them in the done_log entry and handoff `--summary`. If the worker forgets the content HTML, the orchestrator must generate one before calling the task done.

   Then write the human-readable Done index entry.

   **Dashboard mode:** POST a `done_log` row to the dashboard:

   ```bash
   curl -sf -X POST http://127.0.0.1:5176/api/done_log \
     -H 'Content-Type: application/json' \
     -d '{"title":"<task name>: <verb-led one-phrase outcome>","cycle":<N>,"task_id":"<ticket id>","handoff":"<handoff path>"}'
   ```

   **Or in Google Docs mode:** append a disc bullet under the `Done` section header with the same `<task name>: <verb-led one-phrase outcome>. <handoff path>.` format, via `insertText` at the section's `endOfSegmentLocation` + `createParagraphBullets BULLET_DISC_CIRCLE_SQUARE` (same pattern as Step 11).

   **Or in Notion mode:** append a `bulleted_list_item` child block under the `Done` heading with the same format, via `mcp__claude_ai_Notion__notion-update-page` (same block-append pattern as Step 11). Block type is `bulleted_list_item`, not `to_do`.

   **Or in Local Markdown mode:** append the same line under a `## Done` header in `inbox/todo.md`.

   Format the title exactly like the legacy Done bullet: `<task name>: <verb-led one-phrase outcome>` (50-80 chars, no padding). The handoff path is the report path. If the task surfaced an outstanding decision that needs Omar's input, also write a follow-up row (see Step 12a below).

12a. Write outstanding decisions for Omar to resolve.

   **Dashboard mode:** POST to `/api/followups`, one row per decision:

   ```bash
   curl -sf -X POST http://127.0.0.1:5176/api/followups \
     -H 'Content-Type: application/json' \
     -d '{"text":"<task name>: <specific question or decision Omar needs to make>","cycle":<N>,"status":"pending"}'
   ```

   These show up in the dashboard Follow-up panel. Omar resolves each by PATCHing `{"status":"decided","decision":"<his choice>"}`. The orchestrator does not pick decisions itself.

   **Or in Google Docs mode:** append a disc bullet under the `Follow-up` section header (same `insertText` + `endOfSegmentLocation` + `createParagraphBullets` pattern as Step 11). Format: `<task name>: <specific question or decision Omar needs to make>.`

   **Or in Notion mode:** append a `bulleted_list_item` child block under the `Follow-up` heading (same block-append pattern as Step 11). Format: `<task name>: <specific question or decision Omar needs to make>.`

   **Or in Local Markdown mode:** append the same line under a `## Follow-up` header in `inbox/todo.md`.

13. Mark the claimed ticket done in the source.

   **Dashboard mode:** PATCH the ticket:

   ```bash
   curl -sf -X PATCH http://127.0.0.1:5176/api/tasks/<id> \
     -H 'Content-Type: application/json' \
     -d '{"status":"done","handoff":"<handoff path>"}'
   ```

   This PATCH is the source-of-truth ledger update. The `done_log` POST from Step 12 is the human-readable index. Do both, in that order.

   **Or in Google Docs mode:** rewrite the claimed line via `documents.batchUpdate`. Two requests in one batch: (a) `replaceAllText` to swap `(in-progress YYYY-MM-DD)` for `(done YYYY-MM-DD)`, (b) `updateTextStyle` over the paragraph range with `textStyle: {"strikethrough": true}` and `fields: "strikethrough"`. The checkbox glyph stays as-is, the line is now visually struck through and stamped done.

   ```json
   {
     "requests": [
       { "replaceAllText": { "containsText": { "text": "(in-progress 2026-05-15)", "matchCase": true }, "replaceText": "(done 2026-05-15)" } },
       { "updateTextStyle": { "range": { "startIndex": <s>, "endIndex": <e> }, "textStyle": { "strikethrough": true }, "fields": "strikethrough" } }
     ]
   }
   ```

   **Or in Notion mode:** call `mcp__claude_ai_Notion__notion-update-page` on the claimed `to_do` block id. Set `to_do.checked: true` and replace the rich text with `(done YYYY-MM-DD, see <handoff path>) <original text>`. Notion's checkbox toggle IS exposed in the API, so the block visually flips to a checked state in addition to the leading stamp. No strikethrough hack needed (this is the win over Google Docs' updateTextStyle dance).

   **Or in Local Markdown mode:** `python3 skills/get-shit-done/scripts/todo_source.py mark --config config/todo_sources.json --item-id '<item-id>' --status done`.

14. Close the completed worker's active task goal in the runtime, then write the fallback file for that task:
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

   **Self-notification rule (recipient == omar@potarix.com):** SEND, do not draft. Drafts pile up in the Drafts folder and never surface as inbox events, so they are useless as notifications.
   - Claude Code: use the `gws-gmail-send` skill directly (it sends, not drafts). Subject prefix `[GSD]`. contentType: text/html.
   - Codex / headless / any runtime where `gws-gmail-send` is not exposed: fall back to `scripts/notify.py`, which sends via SMTP or shell mail command (it does not draft). Ensure `config/notifications.json` has `enabled: true` and a real recipient.
   - Last-resort runtimes that only expose `mcp__claude_ai_Gmail__create_draft` (no send tool): a draft is the only option; flag this in the handoff so the user knows to check Drafts.
   - For non-self recipients (other people, not Omar): drafts are still acceptable so the user can review before sending.

18. If blocked or human input is required, append any useful suggestions, create and open an HTML handoff report with the exact request for the user, mark the source item blocked, close the per-task goal per Step 14 (in Claude Code this is still `TaskUpdate(taskId, status: "completed")` so the row clears; capture the blocked or `needs_human` outcome in the handoff and ledger), append a ledger row with `blocked` or `needs_human`, then send the notification.

Handoff (all modes):

```bash
python3 skills/get-shit-done/scripts/handoff_report.py --status needs_human --task '<task>' --summary '<blocker>' --needs-from-user '<exact request for the user>'
```

Mark blocked in source:

**Dashboard mode:**

```bash
curl -sf -X PATCH http://127.0.0.1:5176/api/tasks/<id> \
  -H 'Content-Type: application/json' \
  -d '{"status":"blocked","note":"<reason in one line>"}'
```

**Or in Google Docs mode:** `replaceAllText` to swap `(in-progress YYYY-MM-DD)` for `(blocked YYYY-MM-DD) <reason in one line>:`. No strikethrough, the line stays as an open task so a future drain sees it.

**Or in Notion mode:** `mcp__claude_ai_Notion__notion-update-page` on the claimed `to_do` block. Keep `to_do.checked: false` (the block stays as an open task so a future drain sees it) and replace the rich text with `(blocked YYYY-MM-DD) <reason in one line>: <original text>`.

**Or in Local Markdown mode:** `python3 skills/get-shit-done/scripts/todo_source.py mark --config config/todo_sources.json --item-id '<item-id>' --status blocked`.

Notify (all modes):

```bash
python3 skills/get-shit-done/scripts/notify.py needs_human --config config/notifications.json --task '<task>' --body '<exact blocker or question>'
```

19. After all workers from the claimed batch have been reconciled, repeat from step 3 until no actionable item remains. When the queue is empty, close the overarching drain goal so a future invocation starts clean. In Codex call `close_goal`. In Claude Code call `TaskUpdate(drainTaskId, status: "completed")` on the parent drain task you opened in Step 2 (Claude Code's `close_goal` analog). In any runtime also run:

```bash
python3 skills/get-shit-done/scripts/goal_state.py close-drain --status done --summary '<count> tasks cleared, <count> blocked'
```

If a continuous watcher is running, sleep for the configured interval, then drain again. On the next non-empty cycle, re-activate the drain goal via Step 2 before claiming the next batch.

## Task Selection

Choose all incomplete items returned by the configured sources, preserving the source priority/order unless the user states another priority rule. Treat these as actionable:

- Markdown checkbox items like `- [ ] Email Sam the contract`
- TODO lines like `TODO: check production deploy`

Skip items that are already complete, in-progress, blocked, waiting on someone else, or phrased as vague buckets with no executable next step. If an item is vague but a reasonable first action is obvious, do that first action and record the interpretation.

## Safety Rules

Do not access Apple Notes, Messages, iMessage, email, calendars, or other private apps unless the user configured that source or explicitly asks for it in the current session.

Ask before externally visible or destructive actions, including sending messages or emails, deleting data, buying anything, changing billing, force-pushing, deploying to production, or contacting third parties.

If a task requires credentials, paid services, 2FA, or production access that is not already available, stop with a concise blocker note and do not mark the item complete.

## Source Notes

### Source priority (4 supported modes)

This skill is open-source. Different users have different setups. The drain picks one mode per cycle at Step 0 and stays in it for the whole cycle.

The four modes, in precedence order:

1. **Dashboard mode** (recommended, Omar's setup). Activated when `curl http://127.0.0.1:5176/api/health` returns 200, OR when `config/todo_sources.json` explicitly sets dashboard mode. All reads and writes go to the Express server at `http://127.0.0.1:5176`. The UI at `http://127.0.0.1:5179` auto-refreshes every 5s, so Omar sees orchestrator state changes in real time. State files live in `~/Desktop/Ai-slaves-dashboard/data/*.json`. Supports `assigned_next`, agent visibility rows, atomic SC-to-ticket promotion, and the followups / done_log split.
2. **Google Docs mode**. Activated when no dashboard is reachable AND the `/ai-slaves` argument is a Google Doc URL/id, or `config/todo_sources.json` names a Doc. All reads and writes go through the Google Docs API. One Doc, no servers to run, accessible from mobile.
3. **Notion mode**. Activated when no dashboard is reachable AND the `/ai-slaves` argument is a Notion URL (any `notion.so` host), or `config/todo_sources.json` names a Notion page. All reads and writes go through the Notion MCP. One Notion page, no servers to run, accessible from mobile, and the block-type discriminator (`to_do` vs `bulleted_list_item`) is cleaner than Google Docs' listId glyph hack.
4. **Local Markdown mode** (always works, zero setup). Activated when nothing else is configured. All reads and writes go to a local `inbox/todo.md` (or whatever the config names). Best for offline use, CI tests, or quick first-run.

Precedence rule (explicit argument > dashboard reachable > config default > local markdown fallback) is applied at Step 0. Once the mode is locked, do not switch mid-cycle. If the chosen source goes unreachable mid-drain, stop with `needs_human` to avoid state drift.

### Why the dashboard is the recommended setup

If you do not already have a Doc or Notion page wired up, set up the dashboard. It is the best way to use this skill, and the rest of the modes exist as fallbacks for users who already live in a different tool.

Concrete wins over the other modes:

- **One-click drain trigger.** The UI has a Run drain now button that fires a real `claude -p /ai-slaves` invocation per cycle. Docs and Notion need you to remember to type the command or wait for the scheduled poll.
- **Fast UI, no API hops.** The dashboard auto-refreshes every 5 seconds, supports search, filter, and color-coding by campaign. Doc and Notion polling is comparatively slow and gives you less visibility into what the orchestrator is doing.
- **Local persistence.** All state lives in `~/Desktop/Ai-slaves-dashboard/data/*.json` on your Mac. Nothing leaves the machine, no OAuth, no third-party permissions.
- **No glyph or checkbox hacks.** Tasks, suggested changes, follow-ups, and done rows are separate JSON collections, so the orchestrator never has to disambiguate them by inspecting bullet styles or block types.
- **30-second setup:** `cd ~/Desktop/Ai-slaves-dashboard && npm run app`. Then re-invoke `/ai-slaves` and the skill auto-selects dashboard mode at Step 0.

### Dashboard API (canonical)

All endpoints return JSON, loopback-only, no auth.

- `GET /api/tasks` — list tasks. Fields: `id`, `text`, `status` (`queued` | `in_progress` | `blocked` | `done`), `cycle`, `created_at`, `handoff?`, `assigned_next?`, `source?`, `note?`, `promoted_from?`. Sort the queue with `assigned_next: true` ahead of the rest.
- `POST /api/tasks` `{text, cycle, status?, source?}` — create a ticket. Returns the row including server-assigned `id` (`t-NNN`).
- `PATCH /api/tasks/:id` `{status?, handoff?, assigned_next?, note?}` — update.
- `DELETE /api/tasks/:id` — remove.
- `GET/POST/PATCH/DELETE /api/suggested_changes` — fields `text`, `cycle`, `status` (`pending` | `promoted` | `dropped`), `promoted_to?`.
- `POST /api/suggested_changes/:id/promote` — atomic promotion: creates a queued ticket with `promoted_from: <sc-id>` and flips the SC to `promoted` with `promoted_to: <t-id>`. Only Omar uses this from the UI. The orchestrator does not promote.
- `GET/POST/PATCH/DELETE /api/followups` — fields `text`, `cycle`, `status` (`pending` | `decided`), `decision?`.
- `GET/POST/PATCH/DELETE /api/done_log` — fields `title`, `cycle`, `task_id?`, `handoff?`.
- `GET/POST/PATCH/DELETE /api/agents` — fields `agentId`, `drain_cycle_id`, `task_title`, `status` (`running` | `completed` | `errored`), `spawned_at`, `completed_at?`. Server assigns row `id` `ag-NNN` on POST.
- `GET /api/health` → `{"ok":true}`.

Write summary (mapped to Workflow steps):

| Event | Endpoint | Workflow step |
| --- | --- | --- |
| Read queue | `GET /api/tasks` (filter `status==queued`) | 3 |
| Claim | `PATCH /api/tasks/<id> {"status":"in_progress"}` | 5 |
| Worker spawned | `POST /api/agents {"status":"running",...}` | 8 |
| Worker returned | `PATCH /api/agents/<ag-id> {"status":"completed"|"errored"}` | 8 |
| Suggested change | `POST /api/suggested_changes {"text":...,"status":"pending"}` | 11 |
| Done index | `POST /api/done_log {"title":...,"task_id":...,"handoff":...}` | 12 |
| Follow-up | `POST /api/followups {"text":...,"status":"pending"}` | 12a |
| Mark done | `PATCH /api/tasks/<id> {"status":"done","handoff":...}` | 13 |
| Mark blocked | `PATCH /api/tasks/<id> {"status":"blocked","note":...}` | 18 |

`assigned_next: true` is Omar's UI lever to inject a ticket ahead of the queue. Step 3's sort must respect it. The orchestrator does not set `assigned_next` on its own.

### Google Docs source (default for new users)

Setup: create a Google Doc, share it with the runtime's Google identity (or paste it into a runtime with a Google Docs MCP / connector), pass its URL or id as the `/ai-slaves` argument, or add it to `config/todo_sources.json`. The Doc is the single source-of-truth for that user's drain.

Doc layout (one Doc, four sections, in order):

1. **Tasks.** Each task is one checkbox-bulleted line. Unchecked = queued. New tasks get appended at the end of this section.
2. **Suggested Changes.** Disc-bulleted lines. Orchestrator appends here in Step 11.
3. **Follow-up.** Disc-bulleted lines. Orchestrator appends here in Step 12a.
4. **Done.** Disc-bulleted lines. Orchestrator appends here in Step 12.

Section headers are bold-styled regular paragraphs (no bullet). The bullet list type under each header is the discriminator the orchestrator uses to tell tasks apart from output sections.

**Checkbox vs disc discriminator (cycle 11, do not skip this).** Google Docs does not return a clean "bullet kind" enum. The orchestrator must inspect the Doc's `lists` map and read `lists.<listId>.listProperties.nestingLevels[<level>]`:

- Checkbox list: `glyphType == "GLYPH_TYPE_UNSPECIFIED"` (the API leaves it unset for checkbox glyphs). These are tasks.
- Disc list: `glyphSymbol == "●"` (literal U+25CF black circle). These are Suggested Changes / Follow-up / Done output rows.

Any other bullet style is treated as undefined and skipped. Do not rely on `nestingLevels[<level>].glyphFormat` or visual inspection of the rendered Doc; the discriminator above is the only one that survived round-tripping through `gws-docs` and the raw Docs API.

**Append rule (cycle 14, do not skip this).** When writing to any of the three output sections (Suggested Changes / Follow-up / Done), use `documents.batchUpdate` with:

- `insertText.endOfSegmentLocation: { "segmentId": "" }` (the empty `segmentId` targets the body), then
- `createParagraphBullets` over the just-inserted range with `bulletPreset: "BULLET_DISC_CIRCLE_SQUARE"`.

The indexed-location form (`{ "location": { "index": N } }`) drifts when concurrent batchUpdates land between read and write; `endOfSegmentLocation` is the only stable anchor. This was earned the hard way in cycle 14, do not regress.

The bold section header itself must be a regular paragraph, not a bullet. If a new user's Doc does not yet have section headers, the first cycle creates them as plain bold paragraphs followed by an empty disc bullet so subsequent appends find a valid list to extend.

**Per-step write patterns (recap of the mode-aware Workflow):**

| Event | Doc operation |
| --- | --- |
| Read queue | walk `body.content[].paragraph`, collect unchecked checkbox bullets not under an output header |
| Claim | `replaceAllText` to prepend `(in-progress YYYY-MM-DD) ` to the line |
| Suggested change | `insertText endOfSegmentLocation` + `createParagraphBullets BULLET_DISC_CIRCLE_SQUARE` under `Suggested Changes` |
| Done index | same pattern under `Done` |
| Follow-up | same pattern under `Follow-up` |
| Mark done | `replaceAllText` `(in-progress YYYY-MM-DD)` → `(done YYYY-MM-DD)` + `updateTextStyle {"strikethrough": true}` over the paragraph range |
| Mark blocked | `replaceAllText` `(in-progress YYYY-MM-DD)` → `(blocked YYYY-MM-DD) <reason>:` (no strikethrough, the line stays open) |

Mobile capture works out of the box: add a checkbox bullet from the Google Docs mobile app, the next drain picks it up.

### Notion source (resurfaced for new users 2026-05-15)

Setup: create a Notion page, share it with the integration that backs the runtime's Notion MCP (or paste the URL into a runtime with `mcp__claude_ai_Notion__*` exposed), pass its URL as the `/ai-slaves` argument, or add it to `config/todo_sources.json`. The page is the single source-of-truth for that user's drain.

Page layout (one page, four headings, in order):

1. **Tasks.** Each task is one `to_do` block. Unchecked = queued. New tasks get appended as child `to_do` blocks under this heading.
2. **Suggested Changes.** `bulleted_list_item` blocks. Orchestrator appends here in Step 11.
3. **Follow-up.** `bulleted_list_item` blocks. Orchestrator appends here in Step 12a.
4. **Done.** `bulleted_list_item` blocks. Orchestrator appends here in Step 12.

Section headings are Notion `heading_2` or `heading_3` blocks. The child block type under each heading is the discriminator the orchestrator uses to tell tasks apart from output sections.

**Discovery and reading.** Use `mcp__claude_ai_Notion__search` to locate the configured page when only a name is given. Use `mcp__claude_ai_Notion__fetch` to read the page's block children in order; the orchestrator walks them and applies the discriminator below.

**`to_do` vs `bulleted_list_item` discriminator (cycle 17).** Notion exposes the block type directly on every block, so there is no glyph parsing or list-id lookup. The rules:

- `block.type == "to_do"` and the block lives under (or before) the `Suggested Changes` / `Follow-up` / `Done` headings = task input. Unchecked (`to_do.checked == false`) and no leading `(done)` / `(in-progress)` stamp = queued.
- `block.type == "bulleted_list_item"` under any of the three output headings = output row (Suggested Changes / Follow-up / Done).
- Any other block type is treated as undefined and skipped.

This is much cleaner than Google Docs' listId glyph hack: Notion's block-type field IS the discriminator, no `lists.<listId>.listProperties.nestingLevels[<level>].glyphSymbol` parsing needed. Document this so new users do not try to mix `to_do` blocks under the output headings.

**Writeback.** Use `mcp__claude_ai_Notion__notion-update-page` for both claim/done state transitions on existing `to_do` blocks and for appending new `bulleted_list_item` blocks under the output headings. Use `mcp__claude_ai_Notion__notion-create-pages` only if a brand-new sub-page is needed (not the normal write path).

**Per-step write patterns (recap of the mode-aware Workflow):**

| Event | Notion operation |
| --- | --- |
| Read queue | `notion-fetch` page block children, collect unchecked `to_do` blocks not under an output heading |
| Claim | `notion-update-page` on the `to_do` block, replace rich text with `(in-progress YYYY-MM-DD) <original>`, keep `checked: false` |
| Suggested change | `notion-update-page` block-append a new `bulleted_list_item` under the `Suggested Changes` heading |
| Done index | same block-append pattern under `Done` |
| Follow-up | same block-append pattern under `Follow-up` |
| Mark done | `notion-update-page` on the `to_do` block, set `checked: true` and replace rich text with `(done YYYY-MM-DD, see <handoff>) <original>` |
| Mark blocked | `notion-update-page` on the `to_do` block, keep `checked: false`, replace rich text with `(blocked YYYY-MM-DD) <reason>: <original>` |

**Migration history.** Omar's personal Agent TODO page lived in Notion until 2026-05-14, when it migrated to a Google Doc. The migration reason was Notion-specific to Omar's workflow: Notion was rewriting `file://` paths in handoff links, which broke the local-file open behavior on his Mac. That is not a problem for users whose tasks are not centered on local-file handoffs, so Notion is fine as a supported source for new users on regular task lists. The migration note is preserved in `reference_agent_todo_page.md` in MEMORY.md.

Mobile capture works out of the box: add a `to_do` block from the Notion mobile app, the next drain picks it up.

### Local Markdown source (zero setup)

`inbox/todo.md` is the simplest source. `- [ ]` lines are queued tasks. The orchestrator uses `scripts/todo_source.py` for claim / mark / next operations. Suggested Changes, Follow-up, and Done are written as plain markdown bullets under `## Suggested Changes`, `## Follow-up`, `## Done` headers in the same file.

Use this mode for offline runs, CI tests, or first-time users who do not want to wire up a Google identity or run the dashboard server.

### Other legacy sources

Apple Notes is an opt-in legacy source. See `references/sources.md` for setup. The orchestrator supports it through `todo_source.py` but it is not the recommended path for new users.

MCP servers, app connectors, installed skills, and authenticated CLIs are runtime capabilities, not repo credentials. Use them when the current Codex/Claude session exposes them. Scripts in this repo cannot automatically see those capabilities unless they are run through an agent command that has them.
