# Todo Sources

## Local Markdown

The default source is `inbox/todo.md`, configured through `config/todo_sources.json`.

Supported incomplete formats:

```markdown
- [ ] Ship the launch email
TODO: check whether CI passed
```

Supported completion update:

```bash
python3 skills/get-shit-done/scripts/todo_source.py mark --config config/todo_sources.json --item-id '<item-id>' --status done
```

## Apple Notes

Apple Notes support is read-only by default and disabled in `config/todo_sources.json`.

To enable it, set the source `enabled` value to `true` and set `title` to the exact note title. Optional `account` and `folder` fields may be added later if needed. macOS may prompt for permission because the adapter uses AppleScript.

The note body can contain the same Markdown checkbox or TODO formats as the local inbox. Completion write-back is intentionally not implemented yet because Apple Notes bodies are HTML and write-back can damage formatting.

## Google Docs

Google Docs support is disabled in `config/todo_sources.json` by default. It supports read-only mode for public docs and write-back mode for authenticated docs.

To enable a public or published read-only doc, set `enabled` to `true` and set either `url` or `document_id`:

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

For write-back, configure one authentication path and set `writeback`:

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

`auth: "gcloud"` runs `gcloud auth print-access-token`. You can also use `token_env` for an environment variable containing a Bearer token, or `token_command` for a custom command that prints one.

Write-back modes:

- `mark_done`: replace `[ ]` with `[x]`, or replace `TODO` with `DONE`.
- `delete`: clear the task paragraph text while leaving the paragraph break in place.
- `none`: read only.

Read-only mode fetches `https://docs.google.com/document/d/<id>/export?format=txt`. Write-back mode uses the Google Docs API `documents.get` and `documents.batchUpdate` endpoints so the adapter can target the exact paragraph.

## Messages or iMessage

Do not scrape `~/Library/Messages/chat.db` by default. It usually requires Full Disk Access, contains sensitive private messages, and is easy to parse incorrectly.

Prefer one of these safer approaches:

- Copy or forward tasks into `inbox/todo.md`.
- Use Apple Notes as the shared inbox.
- Add a deliberate, scoped source adapter later after confirming the exact chat, sender, and task format.

## Notion

Notion page support is disabled in `config/todo_sources.json` by default. Share the target Notion page with your Notion integration, then set a token:

```bash
export NOTION_TOKEN='secret_...'
```

Enable a page source:

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

Write-back modes:

- `mark_done`: check Notion `to_do` blocks, replace `[ ]` with `[x]`, or replace `TODO` with `DONE`.
- `delete`: archive the Notion block.

Use `recursive: true` to scan child blocks under nested blocks. Keep it false for faster, simpler page-level inboxes.

## Email Notifications

Notifications are configured in `config/notifications.json` and disabled by default. Agents should call `notify.py done` after verified completion and `notify.py needs_human` when blocked or waiting for input.

Supported notification methods:

- `command`: shell command template, for example `mail -s {subject} {to} < {body_file}`.
- `smtp`: SMTP host/port/from plus username/password environment variables.

## Polling

Use `run_loop.py` for polling. The loop creates one prompt per newly seen item and can invoke any agent command through a template:

```bash
TODO_SKILL_AGENT_CMD='your-agent-command {prompt_file}' \
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --interval 1800 --jitter 600
```

Prefer `{prompt_file}` over interpolating task text directly into a shell command.
