# Codex Instructions

When the user asks for "AI Slaves", asks to "get shit done", or invokes `/ai-slaves` or `/get-shit-done`, use `skills/get-shit-done/SKILL.md`.

Use native goal mode for the overarching drain and each active todo in Codex and Claude Code. If a long-running watcher is needed, use `skills/get-shit-done/scripts/run_loop.py --drain`; it can dispatch workers through `--runtime hermes`, `--runtime openclaw`, or a custom `--agent-command`.

Before task work, read the local project/user instructions and installed skills that apply to the workspace. Never skip the skill's claim-first, one-worker-per-task, best-model-by-default, source-writeback, goal-mode, or notification gates.

Do not access Apple Notes, Messages, iMessage, email, calendars, or other private apps unless the user configured that source or explicitly asks for it in the current session.
