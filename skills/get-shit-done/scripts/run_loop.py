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

from todo_source import collect_items, mark_item


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = REPO_ROOT / "skills" / "get-shit-done"
STATE_DIR = REPO_ROOT / "state"
ATTEMPTS_PATH = STATE_DIR / "attempts.json"
OVERARCHING_GOAL_JSON = STATE_DIR / "overarching_goal.json"
OVERARCHING_GOAL_MD = STATE_DIR / "overarching_goal.md"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_attempts() -> dict[str, dict[str, str]]:
    if not ATTEMPTS_PATH.exists():
        return {}
    return json.loads(ATTEMPTS_PATH.read_text(encoding="utf-8"))


def write_attempts(attempts: dict[str, dict[str, str]]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ATTEMPTS_PATH.write_text(json.dumps(attempts, indent=2) + "\n", encoding="utf-8")


def write_overarching_goal(status: str, summary: str = "") -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "task": "Clear all actionable tasks from the configured todo sources",
        "summary": summary,
        "updated_at": now(),
    }
    OVERARCHING_GOAL_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    OVERARCHING_GOAL_MD.write_text(
        "\n".join(
            [
                "# Overarching Goal",
                "",
                f"Status: {status}",
                "Task: Clear all actionable tasks from the configured todo sources",
                f"Updated: {payload['updated_at']}",
                "",
                summary,
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_goal_state(*args: str) -> None:
    subprocess.run(
        ["python3", str(SKILL_PATH / "scripts" / "goal_state.py"), *args],
        cwd=str(REPO_ROOT),
        check=False,
        text=True,
        capture_output=True,
    )


def send_notification(event: str, task: str, body: str) -> None:
    subprocess.run(
        [
            "python3",
            str(SKILL_PATH / "scripts" / "notify.py"),
            event,
            "--config",
            str(REPO_ROOT / "config" / "notifications.json"),
            "--task",
            task,
            "--body",
            body,
        ],
        cwd=str(REPO_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )


def build_prompt(task: dict[str, str], config_path: Path) -> str:
    current_goal_path = STATE_DIR / "current_goal.md"

    return f"""Use $get-shit-done.

Task: {task['title']}

Source:
- source_id: {task['source_id']}
- item_id: {task['item_id']}
- location: {task['location']}

Instructions:
1. Read {SKILL_PATH / 'SKILL.md'} if the skill is not already loaded.
2. This source item has already been claimed in-progress by the watcher. Do not start a different task until this one is done, blocked, or needs human input.
3. Activate goal mode before doing any work:
   - In Codex, call create_goal with this exact task if goal tools are available.
   - In Claude Code, use Claude Code native goal mode with this exact task.
   - In other agents, treat {current_goal_path} as the active fallback goal.
4. Load the local operating context for the workspace before task work: AGENTS.md, CLAUDE.md, SKILL.md, user-level agent instructions, installed skills, MCP/app connectors, and authenticated CLIs. Use those environment tools first unless they conflict with the claim-first/done-or-blocked protocol.
5. Delegate execution to a worker/sub-agent when the environment supports it:
   - In Codex, spawn exactly one worker sub-agent for this task if spawn_agent is available.
   - Tell the worker not to mark the source done, close the goal, or send notifications; the watcher owns those forced closeout steps.
   - If no sub-agent mechanism exists, execute the task inline.
6. Verify the result with the narrowest meaningful check.
7. Return a concise final answer with status, summary, and verification. Exit 0 only when the task is done.
"""


def write_prompt(task: dict[str, str], config_path: Path) -> Path:
    prompt_dir = STATE_DIR / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prompt_path = prompt_dir / f"{stamp}-{task['fingerprint']}.md"
    prompt_path.write_text(build_prompt(task, config_path), encoding="utf-8")
    return prompt_path


def run_agent(command_template: str, prompt_path: Path, task: dict[str, str]) -> subprocess.CompletedProcess[str]:
    command = command_template.format(
        prompt_file=str(prompt_path),
        skill_path=str(SKILL_PATH),
        repo_root=str(REPO_ROOT),
        task_json=json.dumps(task),
    )
    return subprocess.run(command, shell=True, cwd=str(REPO_ROOT), check=False, text=True, capture_output=True)


def claim_task(config_path: Path, task: dict[str, str], dry_run: bool) -> bool:
    if dry_run:
        print(f"Dry run; would claim: {task['title']}")
        return True
    try:
        mark_item(config_path, task["item_id"], "in-progress")
        print(f"Claimed in-progress: {task['title']}")
        return True
    except SystemExit as exc:
        print(f"Skipped claim for {task['title']}: {exc}", file=sys.stderr)
        return False


def finalize_completed_task(config_path: Path, task: dict[str, str], result: subprocess.CompletedProcess[str], prompt_path: Path) -> None:
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
    verification = output[-4000:] if output else "agent command exited 0"
    mark_item(config_path, task["item_id"], "done")
    run_goal_state("close", "--status", "done", "--summary", "agent completed", "--verification", verification)
    subprocess.run(
        [
            "python3",
            str(SKILL_PATH / "scripts" / "ledger.py"),
            "done",
            "--config",
            str(REPO_ROOT / "config" / "ledger.json"),
            "--task",
            task["title"],
            "--source-id",
            task["source_id"],
            "--item-id",
            task["item_id"],
            "--agent",
            "watcher",
            "--status",
            "done",
            "--summary",
            "agent completed",
            "--prompt-file",
            str(prompt_path),
        ],
        cwd=str(REPO_ROOT),
        check=False,
        text=True,
        capture_output=True,
    )
    send_notification("done", task["title"], verification)


def finalize_blocked_task(config_path: Path, task: dict[str, str], result: subprocess.CompletedProcess[str], prompt_path: Path) -> None:
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
    reason = output[-4000:] if output else f"agent command exited {result.returncode}"
    try:
        mark_item(config_path, task["item_id"], "blocked")
    finally:
        run_goal_state("close", "--status", "needs_human", "--summary", reason, "--verification", "")
        subprocess.run(
            [
                "python3",
                str(SKILL_PATH / "scripts" / "ledger.py"),
                "needs_human",
                "--config",
                str(REPO_ROOT / "config" / "ledger.json"),
                "--task",
                task["title"],
                "--source-id",
                task["source_id"],
                "--item-id",
                task["item_id"],
                "--agent",
                "watcher",
                "--status",
                "needs_human",
                "--summary",
                reason,
                "--prompt-file",
                str(prompt_path),
            ],
            cwd=str(REPO_ROOT),
            check=False,
            text=True,
            capture_output=True,
        )
        send_notification("needs_human", task["title"], reason)


def handle_once(config_path: Path, agent_command: str | None, repeat_seen: bool, dry_run: bool) -> int:
    items = collect_items(config_path)
    if not items:
        print("No incomplete todo items found.")
        return 1

    attempts = read_attempts()
    task = None
    for candidate in items:
        key = candidate["fingerprint"]
        if key in attempts and not repeat_seen:
            print(f"Todo already prompted: {candidate['title']}")
            continue
        if claim_task(config_path, candidate, dry_run):
            task = candidate
            break

    if task is None:
        print("No unclaimed todo items found.")
        return 1

    if not dry_run:
        run_goal_state(
            "activate",
            "--task",
            task["title"],
            "--source-id",
            task["source_id"],
            "--item-id",
            task["item_id"],
            "--location",
            task["location"],
        )

    prompt_path = write_prompt(task, config_path)
    key = task["fingerprint"]
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

    result = run_agent(agent_command, prompt_path, task)
    if result.returncode == 0:
        finalize_completed_task(config_path, task, result, prompt_path)
        return 0

    finalize_blocked_task(config_path, task, result, prompt_path)
    return 0


def handle_drain(config_path: Path, agent_command: str | None, repeat_seen: bool) -> int:
    write_overarching_goal("active")
    handled = 0
    while True:
        exit_code = handle_once(config_path, agent_command, repeat_seen, False)
        if exit_code != 0:
            summary = f"Drain finished after {handled} task(s); no unclaimed actionable tasks remain."
            write_overarching_goal("done", summary)
            print(summary)
            return 0 if handled else exit_code
        handled += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll configured todo sources and prompt an agent for new work.")
    parser.add_argument("--config", default=str(REPO_ROOT / "config" / "todo_sources.json"))
    parser.add_argument("--interval", type=int, default=1800, help="Seconds between polls.")
    parser.add_argument("--jitter", type=int, default=600, help="Random extra seconds added to each wait.")
    parser.add_argument("--once", action="store_true", help="Check once and exit.")
    parser.add_argument("--repeat-seen", action="store_true", help="Prompt even if this task was already seen.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--drain", action="store_true", help="Keep claiming and dispatching tasks until no actionable todos remain.")
    parser.add_argument("--agent-command", default=os.environ.get("TODO_SKILL_AGENT_CMD"))
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()

    if not args.agent_command and not args.dry_run:
        raise SystemExit("--agent-command or TODO_SKILL_AGENT_CMD is required unless --dry-run is set.")
    if args.drain and args.dry_run:
        raise SystemExit("--drain is not supported with --dry-run because dry-run does not claim or complete tasks.")

    while True:
        if args.drain:
            exit_code = handle_drain(config_path, args.agent_command, args.repeat_seen)
        else:
            exit_code = handle_once(config_path, args.agent_command, args.repeat_seen, args.dry_run)
        if args.once:
            return exit_code
        wait_seconds = args.interval + (random.randint(0, args.jitter) if args.jitter > 0 else 0)
        print(f"Sleeping for {wait_seconds} seconds.")
        time.sleep(wait_seconds)


if __name__ == "__main__":
    sys.exit(main())
