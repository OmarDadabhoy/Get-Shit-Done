#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from todo_source import collect_items


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = REPO_ROOT / "skills" / "get-shit-done"
STATE_DIR = REPO_ROOT / "state"
ATTEMPTS_PATH = STATE_DIR / "attempts.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_attempts() -> dict[str, dict[str, str]]:
    if not ATTEMPTS_PATH.exists():
        return {}
    return json.loads(ATTEMPTS_PATH.read_text(encoding="utf-8"))


def write_attempts(attempts: dict[str, dict[str, str]]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ATTEMPTS_PATH.write_text(json.dumps(attempts, indent=2) + "\n", encoding="utf-8")


def build_prompt(task: dict[str, str], config_path: Path) -> str:
    completion_command = (
        f"python3 {SKILL_PATH / 'scripts' / 'todo_source.py'} mark "
        f"--config {config_path} --item-id {task['item_id']!r} --status done"
    )
    activate_goal_command = (
        f"python3 {SKILL_PATH / 'scripts' / 'goal_state.py'} activate "
        f"--task {task['title']!r} --source-id {task['source_id']!r} "
        f"--item-id {task['item_id']!r} --location {task['location']!r}"
    )
    close_goal_command = (
        f"python3 {SKILL_PATH / 'scripts' / 'goal_state.py'} close "
        "--status done --summary '<result>' --verification '<verification summary>'"
    )
    blocked_goal_command = (
        f"python3 {SKILL_PATH / 'scripts' / 'goal_state.py'} close "
        "--status needs_human --summary '<blocker>' --verification ''"
    )
    current_goal_path = STATE_DIR / "current_goal.md"
    completions_path = STATE_DIR / "completions.md"

    return f"""Use $get-shit-done.

Task: {task['title']}

Source:
- source_id: {task['source_id']}
- item_id: {task['item_id']}
- location: {task['location']}

Instructions:
1. Read {SKILL_PATH / 'SKILL.md'} if the skill is not already loaded.
2. Activate goal mode before doing any work:
   - In Codex, call create_goal with this exact task if goal tools are available.
   - In Claude Code or other agents, run:
     {activate_goal_command}
   This writes the fallback goal file at {current_goal_path}.
3. Execute the task end to end, asking only for blockers or approval before externally visible/destructive actions.
4. Verify the result.
5. If the source supports completion, mark it done with:
   {completion_command}
6. Close the active goal after completion:
   - In Codex, mark the goal complete if goal tools are available.
   - In every agent, run:
     {close_goal_command}
7. Append a short result and verification note to {completions_path}.
8. If notifications are enabled, send completion email:
   python3 {SKILL_PATH / 'scripts' / 'notify.py'} done --config {REPO_ROOT / 'config' / 'notifications.json'} --task {task['title']!r} --body '<verification summary>'
9. If blocked or waiting for input, run this goal closeout first:
   {blocked_goal_command}
10. Then send needs-human email:
   python3 {SKILL_PATH / 'scripts' / 'notify.py'} needs_human --config {REPO_ROOT / 'config' / 'notifications.json'} --task {task['title']!r} --body '<exact blocker or question>'
"""


def write_prompt(task: dict[str, str], config_path: Path) -> Path:
    prompt_dir = STATE_DIR / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prompt_path = prompt_dir / f"{stamp}-{task['fingerprint']}.md"
    prompt_path.write_text(build_prompt(task, config_path), encoding="utf-8")
    return prompt_path


def run_agent(command_template: str, prompt_path: Path, task: dict[str, str]) -> int:
    command = command_template.format(
        prompt_file=str(prompt_path),
        skill_path=str(SKILL_PATH),
        repo_root=str(REPO_ROOT),
        task_json=json.dumps(task),
    )
    return subprocess.run(command, shell=True, cwd=str(REPO_ROOT), check=False).returncode


def handle_once(config_path: Path, agent_command: str | None, repeat_seen: bool, dry_run: bool) -> int:
    items = collect_items(config_path)
    if not items:
        print("No incomplete todo items found.")
        return 1

    attempts = read_attempts()
    task = items[0]
    key = task["fingerprint"]
    if key in attempts and not repeat_seen:
        print(f"Next todo already prompted: {task['title']}")
        return 0

    prompt_path = write_prompt(task, config_path)
    attempts[key] = {
        "task": task["title"],
        "item_id": task["item_id"],
        "prompt_file": str(prompt_path),
        "last_prompted_at": now(),
    }
    if not dry_run:
        write_attempts(attempts)

    print(f"Prepared prompt: {prompt_path}")
    if not agent_command:
        print(prompt_path.read_text(encoding="utf-8"))
        return 0

    if dry_run:
        print("Dry run; agent command was not executed.")
        return 0

    return run_agent(agent_command, prompt_path, task)


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll configured todo sources and prompt an agent for new work.")
    parser.add_argument("--config", default=str(REPO_ROOT / "config" / "todo_sources.json"))
    parser.add_argument("--interval", type=int, default=1800, help="Seconds between polls.")
    parser.add_argument("--jitter", type=int, default=600, help="Random extra seconds added to each wait.")
    parser.add_argument("--once", action="store_true", help="Check once and exit.")
    parser.add_argument("--repeat-seen", action="store_true", help="Prompt even if this task was already seen.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--agent-command", default=os.environ.get("TODO_SKILL_AGENT_CMD"))
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()

    while True:
        exit_code = handle_once(config_path, args.agent_command, args.repeat_seen, args.dry_run)
        if args.once:
            return exit_code
        wait_seconds = args.interval + (random.randint(0, args.jitter) if args.jitter > 0 else 0)
        print(f"Sleeping for {wait_seconds} seconds.")
        time.sleep(wait_seconds)


if __name__ == "__main__":
    sys.exit(main())
