# Get Shit Done Skill

Codex/Claude skill that pulls the next task from a todo source, makes it the active goal, does the work, marks the source item done, and emails you if it finishes or needs help.

## Install

```bash
git clone git@github.com:OmarDadabhoy/Get-Shit-Done.git
cd Get-Shit-Done
scripts/install-codex-symlink.sh
```

Then in Codex:

```text
Use $get-shit-done
```

Claude Code can use the repo directly; it reads `CLAUDE.md` and `skills/get-shit-done/SKILL.md`.

## Add Tasks

Fastest option: edit `inbox/todo.md`.

```markdown
- [ ] Draft the launch email
TODO: Follow up with Sam
```

Check what the skill sees:

```bash
python3 skills/get-shit-done/scripts/todo_source.py next --config config/todo_sources.json
```

## Connect Google Docs

Edit `config/todo_sources.json`:

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

Write-back options:

- `mark_done`: `[ ]` becomes `[x]`, `TODO` becomes `DONE`
- `delete`: clears the task paragraph
- `none`: read only

For private docs, authenticate with one of:

```bash
gcloud auth application-default login
```

or set `token_env` / `token_command` in the source config.

## Connect Notion

Create a Notion integration, share the page with it, then:

```bash
export NOTION_TOKEN='secret_...'
```

Edit `config/todo_sources.json`:

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

Notion supports unchecked `to_do` blocks, `- [ ] Task`, and `TODO: Task`.

## Email Me

Edit `config/notifications.json` and set `enabled` to `true`.

Simple local mail example:

```json
{
  "enabled": true,
  "method": "command",
  "to": ["you@example.com"],
  "command": "mail -s {subject} {to} < {body_file}"
}
```

SMTP is also supported with `SMTP_USERNAME` and `SMTP_PASSWORD`.

## Polling

Check once:

```bash
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --once
```

Poll every 20-30 minutes:

```bash
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --interval 1800 --jitter 600
```

To have the watcher invoke an agent:

```bash
TODO_SKILL_AGENT_CMD='your-agent-command {prompt_file}' \
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json
```

## Verify

```bash
python3 -m py_compile skills/get-shit-done/scripts/*.py
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/get-shit-done
```
