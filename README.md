# AI Slaves

The AI that drains your todo list while you sleep. Slash-command skill for Codex or Claude Code. It reads a todo source, claims one item, runs it as a goal in a dedicated worker/sub-agent, marks it done or blocked, emails you, then keeps draining.

Live at [ai-slaves.com](https://ai-slaves.com). For the multi-worker orchestrator variant, see [ai-slaves-sweeper](https://github.com/OmarDadabhoy/ai-slaves-sweeper).

## Install

```bash
git clone git@github.com:OmarDadabhoy/ai-slaves.git
cd ai-slaves
cp config/todo_sources.example.json config/todo_sources.json
cp config/notifications.example.json config/notifications.json
cp config/ledger.example.json config/ledger.json
scripts/install-codex-symlink.sh
```

## Use

```text
/ai-slaves
/ai-slaves https://www.notion.so/...
/ai-slaves https://docs.google.com/document/d/...
/get-shit-done
```

Use `/ai-slaves` as the primary command. `/get-shit-done` remains as a legacy alias. The command uses existing Codex/Claude access first: MCP/app connectors, installed skills, browser tools, and authenticated CLIs.

## Config

- For polling, edit `config/todo_sources.json` from `config/todo_sources.example.json`.
- Supports `google_docs`, `notion_page`, and `text_file`.
- For email, edit `config/notifications.json` or set:

```bash
export TODO_SKILL_EMAIL_TO='you@example.com'
```

## Poll

```bash
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --once --dry-run

TODO_SKILL_AGENT_CMD='your-agent-command {prompt_file}' \
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --drain --interval 1800 --jitter 600

python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --drain --runtime hermes
python3 skills/get-shit-done/scripts/run_loop.py --config config/todo_sources.json --drain --runtime openclaw --openclaw-agent ops
```

## Rules

Uses goal mode, claims items before work, creates one worker/sub-agent per task on the best available model unless overridden, marks them done or blocked, appends useful suggestions under `Suggested Changes`, opens an HTML handoff report, emails on completion, and skips in-progress/done/blocked items.

Real config files are gitignored. Commit only `config/*.example.json`.
