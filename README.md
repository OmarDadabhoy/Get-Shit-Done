# TodoSkill

Framework-agnostic "get shit done" skill for Codex and Claude Code.

This is V1: a lightweight skill plus source adapters. It teaches an agent to pick the next todo, set or emulate a goal, execute one item, verify the result, and leave an audit trail.

## Install

Clone the repo:

```bash
git clone git@github.com:OmarDadabhoy/TodoSkill.git
cd TodoSkill
```

Install the Codex skill symlink:

```bash
scripts/install-codex-symlink.sh
```

That links:

```text
~/.codex/skills/get-shit-done -> ./skills/get-shit-done
```

Claude Code does not need a symlink. It should read `CLAUDE.md` and `skills/get-shit-done/SKILL.md` from this repo.

## First Run

Add a real task to `inbox/todo.md`:

```markdown
- [ ] Draft the launch email
```

Check what the skill sees:

```bash
python3 skills/get-shit-done/scripts/todo_source.py next --config config/todo_sources.json
```

In Codex, run:

```text
Use $get-shit-done
```

The skill will load the next task, set a Codex goal when goal tools are available, execute the task, verify it, and mark it complete when the source supports write-back.

## Polling

Check once and generate a prompt:

```bash
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --once
```

Poll every 20-30 minutes:

```bash
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --interval 1800 --jitter 600
```

By default, polling writes prompt files under `state/prompts/`. To make it invoke an agent, provide a command template:

```bash
TODO_SKILL_AGENT_CMD='your-agent-command {prompt_file}' \
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json
```

Use `{prompt_file}` instead of interpolating task text into shell commands.

## Sources

Configure sources in `config/todo_sources.json`.

Supported source types:

- `text_file`: local Markdown or text file. Supports read and mark-complete.
- `google_docs`: Google Docs plain-text export. Read-only by default.
- `notion_page`: Notion page blocks. Supports read and write-back.
- `apple_notes`: Apple Notes via macOS AppleScript. Read-only by default.

Supported task formats:

```markdown
- [ ] Do the thing
TODO: Do the other thing
```

Completed or blocked formats are ignored:

```markdown
- [x] Already done
- [!] Blocked
```

## Google Docs Setup

For a public or published read-only Google Doc:

```json
{
  "id": "google-docs",
  "type": "google_docs",
  "enabled": true,
  "url": "https://docs.google.com/document/d/YOUR_DOCUMENT_ID/edit",
  "auth": "public",
  "writeback": "none"
}
```

For a private Google Doc using `gcloud`:

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

Other private auth options:

- `token_env`: environment variable containing a Bearer token.
- `token_command`: command that prints a Bearer token.

Google Docs write-back modes:

- `mark_done`: replace `[ ]` with `[x]`, or replace `TODO` with `DONE`.
- `delete`: clear the task paragraph text while leaving the paragraph break in place.
- `none`: read only.

Write-back uses the Google Docs API, so the token needs Docs read/write access.

## Apple Notes Setup

Apple Notes is disabled by default because macOS automation permissions are sensitive.

Enable it by setting:

```json
{
  "id": "apple-notes",
  "type": "apple_notes",
  "enabled": true,
  "title": "Codex Todo"
}
```

macOS may prompt for automation permission. Completion write-back is intentionally not enabled because Notes stores rich HTML bodies.

## Notion Setup

Create a Notion integration, share the target page with it, then export the token:

```bash
export NOTION_TOKEN='secret_...'
```

Enable the source:

```json
{
  "id": "notion-page",
  "type": "notion_page",
  "enabled": true,
  "url": "https://www.notion.so/YOUR_PAGE_ID",
  "token_env": "NOTION_TOKEN",
  "writeback": "mark_done",
  "recursive": false
}
```

Supported Notion task blocks:

- unchecked Notion `to_do` blocks
- paragraph/list blocks containing `- [ ] Task`
- paragraph/list blocks containing `TODO: Task`

Notion write-back modes:

- `mark_done`: check Notion `to_do` blocks, replace `[ ]` with `[x]`, or replace `TODO` with `DONE`.
- `delete`: archive the Notion block.

## Email Notifications

Notifications are configured in `config/notifications.json` and disabled by default.

Command-based email example:

```json
{
  "enabled": true,
  "method": "command",
  "to": ["you@example.com"],
  "subject_prefix": "[Get Shit Done]",
  "command": "mail -s {subject} {to} < {body_file}"
}
```

SMTP example:

```json
{
  "enabled": true,
  "method": "smtp",
  "to": ["you@example.com"],
  "subject_prefix": "[Get Shit Done]",
  "smtp": {
    "host": "smtp.gmail.com",
    "port": 587,
    "starttls": true,
    "from": "you@example.com",
    "username_env": "SMTP_USERNAME",
    "password_env": "SMTP_PASSWORD"
  }
}
```

Agents call `notify.py done` after verified completion and `notify.py needs_human` when blocked or waiting for input.

## Privacy Boundaries

This repo does not read iMessage by default. Direct access to `~/Library/Messages/chat.db` is intentionally not implemented.

Recommended private source flow:

1. Put tasks in `inbox/todo.md`, Google Docs, or Apple Notes.
2. Let the skill read only configured sources.
3. Require approval before sending messages, sending emails, deleting data, purchasing anything, deploying, or contacting third parties.

## Files

- `skills/get-shit-done/SKILL.md`: main Codex skill.
- `CLAUDE.md`: Claude Code behavior mirror.
- `AGENTS.md`: Codex repo instructions.
- `skills/get-shit-done/scripts/todo_source.py`: source reader and mark-complete helper.
- `skills/get-shit-done/scripts/run_loop.py`: polling runner.
- `skills/get-shit-done/scripts/notify.py`: email notification helper.
- `config/todo_sources.json`: source configuration.
- `config/notifications.json`: email notification configuration.
- `inbox/todo.md`: default local todo inbox.

## Verify

Run these before pushing changes:

```bash
python3 -m py_compile skills/get-shit-done/scripts/todo_source.py skills/get-shit-done/scripts/run_loop.py skills/get-shit-done/scripts/notify.py
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/get-shit-done
python3 skills/get-shit-done/scripts/todo_source.py list --config config/todo_sources.json
```

## Troubleshooting

If Codex does not see `$get-shit-done`, rerun:

```bash
scripts/install-codex-symlink.sh
```

If Google Docs returns 401 or 403, make the doc public/published for read-only mode, or configure `auth: "gcloud"`, `token_env`, or `token_command` with Docs read/write scope for write-back.

If Notion returns 401, 403, or 404, confirm `NOTION_TOKEN` is set and the page has been shared with the integration.

If the watcher only writes prompts and does not run an agent, set `TODO_SKILL_AGENT_CMD`.
