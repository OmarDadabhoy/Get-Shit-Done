#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re
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
DEFAULT_BEST_MODELS = {
    "hermes": "opus",
}


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


def create_handoff_report(
    status: str,
    task: dict[str, str],
    summary: str,
    verification: str,
    needs_from_user: str,
    prompt_path: Path,
) -> Path | None:
    result = subprocess.run(
        [
            "python3",
            str(SKILL_PATH / "scripts" / "handoff_report.py"),
            "--status",
            status,
            "--task",
            task["title"],
            "--summary",
            summary,
            "--verification",
            verification,
            "--needs-from-user",
            needs_from_user,
            "--source-id",
            task["source_id"],
            "--item-id",
            task["item_id"],
            "--location",
            task["location"],
            "--prompt-file",
            str(prompt_path),
        ],
        cwd=str(REPO_ROOT),
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stderr or result.stdout or "failed to create handoff report", file=sys.stderr)
        return None
    return Path(result.stdout.strip())


def extract_suggestions(output: str) -> list[str]:
    try:
        parsed = json.loads(output)
        values = parsed.get("suggested_changes") or parsed.get("suggestions") or []
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            return [str(value).strip() for value in values if str(value).strip()]
    except json.JSONDecodeError:
        pass

    match = re.search(r"(?ims)^\s*suggested[_ ]changes\s*:?\s*(.*)$", output)
    if not match:
        return []
    suggestions: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped:
            if suggestions:
                break
            continue
        if re.match(r"(?i)^(status|summary|verification|needs_from_user|follow_up)\s*:", stripped):
            break
        cleaned = re.sub(r"^[-*]\s+", "", stripped)
        cleaned = re.sub(r"^\d+[.)]\s+", "", cleaned).strip()
        if cleaned.lower() not in {"none", "n/a", "nothing"}:
            suggestions.append(cleaned)
    return suggestions


def append_suggestions(config_path: Path, task: dict[str, str], suggestions: list[str]) -> dict[str, str] | None:
    if not suggestions:
        return None
    command = [
        "python3",
        str(SKILL_PATH / "scripts" / "suggested_changes.py"),
        "--config",
        str(config_path),
        "--source-id",
        task["source_id"],
        "--task",
        task["title"],
    ]
    for suggestion in suggestions:
        command.extend(["--suggestion", suggestion])
    result = subprocess.run(command, cwd=str(REPO_ROOT), check=False, text=True, capture_output=True)
    if result.returncode != 0:
        print(result.stderr or result.stdout or "failed to append suggested changes", file=sys.stderr)
        return {"status": "failed"}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "appended", "output": result.stdout.strip()}


def build_prompt(task: dict[str, str], config_path: Path) -> str:
    current_goal_path = STATE_DIR / "current_goal.md"

    return f"""Use the AI Slaves skill.

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
5. Delegate execution to exactly one dedicated worker/sub-agent:
   - In Codex, spawn exactly one worker sub-agent for this task if spawn_agent is available, and set the worker to the best available Codex model, currently gpt-5.5, unless the user explicitly requested another model.
   - In Claude Code, use Claude Code's native sub-agent/task-worker mechanism when available, defaulting to the opus model alias or the best available Claude Code model unless the user explicitly requested another model.
   - In Hermes or OpenClaw, treat this one-shot agent run as the dedicated worker boundary; use the best available runtime model when model selection exists, and use OpenClaw xhigh thinking unless the user explicitly requested another thinking level.
   - Tell the worker not to mark the source done, close the goal, or send notifications; the watcher owns those forced closeout steps.
   - If no sub-agent or task-worker mechanism exists, return status needs_human with "No sub-agent mechanism available" instead of executing inline, unless the user explicitly allowed inline fallback for this run.
6. Verify the worker result with the narrowest meaningful check.
7. If useful improvements occur while the worker is working, return them under suggested_changes as a short bullet list. These can be code, marketing, sales, ops, or process suggestions.
8. Return a concise final answer with status, summary, verification, needs_from_user, and suggested_changes. Exit 0 only when the task is done by the worker/sub-agent.
"""


def write_prompt(task: dict[str, str], config_path: Path) -> Path:
    prompt_dir = STATE_DIR / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prompt_path = prompt_dir / f"{stamp}-{task['fingerprint']}.md"
    prompt_path.write_text(build_prompt(task, config_path), encoding="utf-8")
    return prompt_path


def run_agent(
    command_template: str | None,
    prompt_path: Path,
    task: dict[str, str],
    runtime: str,
    openclaw_agent: str | None = None,
    openclaw_to: str | None = None,
    openclaw_local: bool = False,
    openclaw_thinking: str | None = None,
    timeout: int | None = None,
    model: str | None = None,
    hermes_skills: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    if command_template:
        return run_custom_agent(command_template, prompt_path, task)

    prompt = prompt_path.read_text(encoding="utf-8")
    command = runtime_command(
        runtime,
        prompt,
        openclaw_agent=openclaw_agent,
        openclaw_to=openclaw_to,
        openclaw_local=openclaw_local,
        openclaw_thinking=openclaw_thinking,
        timeout=timeout,
        model=model,
        hermes_skills=hermes_skills or [],
    )
    return subprocess.run(command, cwd=str(REPO_ROOT), check=False, text=True, capture_output=True)


def run_custom_agent(command_template: str, prompt_path: Path, task: dict[str, str]) -> subprocess.CompletedProcess[str]:
    command = command_template.format(
        prompt_file=str(prompt_path),
        skill_path=str(SKILL_PATH),
        repo_root=str(REPO_ROOT),
        task_json=json.dumps(task),
    )
    return subprocess.run(command, shell=True, cwd=str(REPO_ROOT), check=False, text=True, capture_output=True)


def runtime_command(
    runtime: str,
    prompt: str,
    openclaw_agent: str | None = None,
    openclaw_to: str | None = None,
    openclaw_local: bool = False,
    openclaw_thinking: str | None = None,
    timeout: int | None = None,
    model: str | None = None,
    hermes_skills: list[str] | None = None,
) -> list[str]:
    if runtime == "hermes":
        command = ["hermes", "chat"]
        for skill in hermes_skills or []:
            if skill:
                command.extend(["-s", skill])
        effective_model = model if model is not None else default_best_model(runtime)
        if effective_model:
            command.extend(["--model", effective_model])
        command.extend(["-q", prompt])
        return command

    if runtime == "openclaw":
        agent = openclaw_agent or os.environ.get("OPENCLAW_AGENT")
        target = openclaw_to or os.environ.get("OPENCLAW_TO")
        thinking = openclaw_thinking if openclaw_thinking is not None else os.environ.get("OPENCLAW_THINKING", "xhigh")
        if not agent and not target:
            raise SystemExit("--runtime openclaw requires --openclaw-agent/OPENCLAW_AGENT or --openclaw-to/OPENCLAW_TO.")
        command = ["openclaw", "agent"]
        if agent:
            command.extend(["--agent", agent])
        if target:
            command.extend(["--to", target])
        if openclaw_local:
            command.append("--local")
        if thinking:
            command.extend(["--thinking", thinking])
        if timeout:
            command.extend(["--timeout", str(timeout)])
        command.extend(["--message", prompt])
        return command

    raise SystemExit(f"Unsupported runtime: {runtime}. Use custom, hermes, or openclaw.")


def default_best_model(runtime: str) -> str | None:
    if runtime == "hermes":
        return (
            os.environ.get("TODO_SKILL_MODEL")
            or os.environ.get("GSD_HERMES_MODEL")
            or os.environ.get("HERMES_MODEL")
            or DEFAULT_BEST_MODELS["hermes"]
        )
    return os.environ.get("TODO_SKILL_MODEL")


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
    suggestions = extract_suggestions(output)
    suggestion_result = append_suggestions(config_path, task, suggestions)
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
    report_path = create_handoff_report(
        "done",
        task,
        "agent completed",
        verification,
        "Nothing needed from you right now.",
        prompt_path,
    )
    body = verification
    if report_path:
        body = f"Handoff report: {report_path}\n\n{verification}"
    if suggestion_result:
        body = f"{body}\n\nSuggested changes: {json.dumps(suggestion_result)}"
    send_notification("done", task["title"], body)


def finalize_blocked_task(config_path: Path, task: dict[str, str], result: subprocess.CompletedProcess[str], prompt_path: Path) -> None:
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
    reason = output[-4000:] if output else f"agent command exited {result.returncode}"
    suggestions = extract_suggestions(output)
    suggestion_result = append_suggestions(config_path, task, suggestions)
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
        report_path = create_handoff_report("needs_human", task, reason, "", reason, prompt_path)
        body = reason
        if report_path:
            body = f"Handoff report: {report_path}\n\n{reason}"
        if suggestion_result:
            body = f"{body}\n\nSuggested changes: {json.dumps(suggestion_result)}"
        send_notification("needs_human", task["title"], body)


def handle_once(args: argparse.Namespace, config_path: Path, repeat_seen: bool, dry_run: bool) -> int:
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
    if not args.agent_command and args.runtime == "custom":
        print(prompt_path.read_text(encoding="utf-8"))
        return 0

    if dry_run:
        print("Dry run; agent command was not executed.")
        return 0

    result = run_agent(
        args.agent_command,
        prompt_path,
        task,
        args.runtime,
        openclaw_agent=args.openclaw_agent,
        openclaw_to=args.openclaw_to,
        openclaw_local=args.openclaw_local,
        timeout=args.runtime_timeout,
        openclaw_thinking=args.openclaw_thinking,
        model=args.model,
        hermes_skills=args.hermes_skill,
    )
    if result.returncode == 0:
        finalize_completed_task(config_path, task, result, prompt_path)
        return 0

    finalize_blocked_task(config_path, task, result, prompt_path)
    return 0


def handle_drain(args: argparse.Namespace, config_path: Path, repeat_seen: bool) -> int:
    write_overarching_goal("active")
    handled = 0
    while True:
        exit_code = handle_once(args, config_path, repeat_seen, False)
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
    parser.add_argument("--runtime", choices=["custom", "hermes", "openclaw"], default=os.environ.get("TODO_SKILL_RUNTIME", "custom"))
    parser.add_argument("--model", default=os.environ.get("TODO_SKILL_MODEL"))
    parser.add_argument("--runtime-timeout", type=int, default=int(os.environ.get("TODO_SKILL_RUNTIME_TIMEOUT", "0")) or None)
    parser.add_argument("--hermes-skill", action="append", default=os.environ.get("HERMES_SKILLS", "").split(",") if os.environ.get("HERMES_SKILLS") else [])
    parser.add_argument("--openclaw-agent", default=os.environ.get("OPENCLAW_AGENT"))
    parser.add_argument("--openclaw-to", default=os.environ.get("OPENCLAW_TO"))
    parser.add_argument("--openclaw-local", action="store_true", default=os.environ.get("OPENCLAW_LOCAL", "").lower() in {"1", "true", "yes"})
    parser.add_argument("--openclaw-thinking", default=os.environ.get("OPENCLAW_THINKING"))
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()

    if not args.agent_command and args.runtime == "custom" and not args.dry_run:
        raise SystemExit("--agent-command, TODO_SKILL_AGENT_CMD, or --runtime hermes|openclaw is required unless --dry-run is set.")
    if args.drain and args.dry_run:
        raise SystemExit("--drain is not supported with --dry-run because dry-run does not claim or complete tasks.")

    while True:
        if args.drain:
            exit_code = handle_drain(args, config_path, args.repeat_seen)
        else:
            exit_code = handle_once(args, config_path, args.repeat_seen, args.dry_run)
        if args.once:
            return exit_code
        wait_seconds = args.interval + (random.randint(0, args.jitter) if args.jitter > 0 else 0)
        print(f"Sleeping for {wait_seconds} seconds.")
        time.sleep(wait_seconds)


if __name__ == "__main__":
    sys.exit(main())
