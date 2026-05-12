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

Google Docs support is read-only by default and disabled in `config/todo_sources.json`.

To enable a public or published doc, set `enabled` to `true` and set either `url` or `document_id`:

```json
{
  "id": "google-docs",
  "type": "google_docs",
  "enabled": true,
  "url": "https://docs.google.com/document/d/YOUR_DOCUMENT_ID/edit",
  "auth": "public"
}
```

For a private doc, configure one authentication path:

```json
{
  "id": "google-docs",
  "type": "google_docs",
  "enabled": true,
  "document_id": "YOUR_DOCUMENT_ID",
  "auth": "gcloud"
}
```

`auth: "gcloud"` runs `gcloud auth print-access-token`. You can also use `token_env` for an environment variable containing a Bearer token, or `token_command` for a custom command that prints one.

The adapter fetches `https://docs.google.com/document/d/<id>/export?format=txt` and parses the same Markdown checkbox or TODO formats. Completion write-back is not implemented yet; when a Google Docs task is completed, record the result in `state/completions.md` and leave the source item unchanged unless the current agent also has explicit Google Docs editing tools available.

## Messages or iMessage

Do not scrape `~/Library/Messages/chat.db` by default. It usually requires Full Disk Access, contains sensitive private messages, and is easy to parse incorrectly.

Prefer one of these safer approaches:

- Copy or forward tasks into `inbox/todo.md`.
- Use Apple Notes as the shared inbox.
- Add a deliberate, scoped source adapter later after confirming the exact chat, sender, and task format.

## Polling

Use `run_loop.py` for polling. The loop creates one prompt per newly seen item and can invoke any agent command through a template:

```bash
TODO_SKILL_AGENT_CMD='your-agent-command {prompt_file}' \
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --interval 1800 --jitter 600
```

Prefer `{prompt_file}` over interpolating task text directly into a shell command.
