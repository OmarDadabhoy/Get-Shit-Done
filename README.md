# Get Shit Done

A Codex/Claude skill that drains a todo source. It claims each task, runs it as a goal, marks it done or blocked, emails you, then keeps checking on a schedule.

## Install

```bash
git clone git@github.com:OmarDadabhoy/Get-Shit-Done.git
cd Get-Shit-Done
cp config/todo_sources.example.json config/todo_sources.json
cp config/notifications.example.json config/notifications.json
cp config/ledger.example.json config/ledger.json
scripts/install-codex-symlink.sh
```

Run it with:

```text
/get-shit-done
```

## Required Setup

Edit `config/todo_sources.json` and enable your source.

Google Docs:

```json
{
  "id": "google-docs",
  "type": "google_docs",
  "enabled": true,
  "document_id": "YOUR_DOCUMENT_ID",
  "auth": "gcloud",
  "writeback": "mark_done"
}
```

Notion:

```json
{
  "id": "notion-page",
  "type": "notion_page",
  "enabled": true,
  "url": "https://www.notion.so/YOUR_PAGE_ID",
  "token_env": "NOTION_TOKEN",
  "writeback": "mark_done"
}
```

Private Google Docs usually need:

```bash
gcloud auth application-default login
```

Notion usually needs:

```bash
export NOTION_TOKEN='secret_...'
```

For email, put your address in `config/notifications.json` or set one env var:

```bash
export TODO_SKILL_EMAIL_TO='you@example.com'
```

## How It Runs

- Loads your local environment first: `AGENTS.md`, `CLAUDE.md`, installed skills, MCP/app connectors, and authenticated CLIs.
- Uses one overarching goal: clear all actionable tasks from the source.
- Uses a task goal for every single claimed item.
- Claims first by marking the source item in-progress: `[>]` or `WIP`.
- Only claimed items can become done or blocked.
- Marks completion as `[x]` or `DONE`; marks blockers as `[!]` or `BLKD`.
- Sends an email after every completed task when an email recipient is available.
- Skips tasks already in-progress, done, or blocked so multiple agents do not intentionally collide.

Google Docs claims use revision checks. Notion and local files re-check the current marker before each transition.

## Polling

Dry run:

```bash
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --once --dry-run
```

Run continuously every 20-30 minutes:

```bash
TODO_SKILL_AGENT_CMD='your-agent-command {prompt_file}' \
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --drain --interval 1800 --jitter 600
```

Real config files are gitignored. Commit only `config/*.example.json`.
