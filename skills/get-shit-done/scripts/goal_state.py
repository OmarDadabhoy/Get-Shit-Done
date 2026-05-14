#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
STATE_DIR = REPO_ROOT / "state"
CURRENT_JSON = STATE_DIR / "current_goal.json"
CURRENT_MD = STATE_DIR / "current_goal.md"
DRAIN_JSON = STATE_DIR / "overarching_goal.json"
DRAIN_MD = STATE_DIR / "overarching_goal.md"
HISTORY_JSONL = STATE_DIR / "goal_history.jsonl"
DRAIN_TASK = "Clear all actionable tasks from the configured todo sources"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _render_md(goal: dict, heading: str) -> str:
    return "\n".join(
        [
            heading,
            "",
            f"Status: {goal['status']}",
            f"Task: {goal['task']}",
            f"Source: {goal.get('source_id', '')}",
            f"Item: {goal.get('item_id', '')}",
            f"Started: {goal.get('started_at', '')}",
            "",
        ]
    )


def write_current(goal: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_JSON.write_text(json.dumps(goal, indent=2) + "\n", encoding="utf-8")
    CURRENT_MD.write_text(_render_md(goal, "# Current Goal"), encoding="utf-8")


def write_drain(goal: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    DRAIN_JSON.write_text(json.dumps(goal, indent=2) + "\n", encoding="utf-8")
    DRAIN_MD.write_text(_render_md(goal, "# Overarching Goal"), encoding="utf-8")


def append_history(goal: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with HISTORY_JSONL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(goal, sort_keys=True) + "\n")


def read_current() -> dict:
    if not CURRENT_JSON.exists():
        return {}
    return json.loads(CURRENT_JSON.read_text(encoding="utf-8"))


def read_drain() -> dict:
    if not DRAIN_JSON.exists():
        return {}
    return json.loads(DRAIN_JSON.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintain file-backed goal state for AI Slaves.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    activate = subparsers.add_parser("activate")
    activate.add_argument("--task", required=True)
    activate.add_argument("--source-id", default="")
    activate.add_argument("--item-id", default="")
    activate.add_argument("--location", default="")

    close = subparsers.add_parser("close")
    close.add_argument("--status", choices=["done", "blocked", "needs_human"], required=True)
    close.add_argument("--summary", default="")
    close.add_argument("--verification", default="")

    activate_drain = subparsers.add_parser("activate-drain")
    activate_drain.add_argument("--task", default=DRAIN_TASK)

    close_drain = subparsers.add_parser("close-drain")
    close_drain.add_argument("--status", choices=["done", "blocked", "needs_human"], required=True)
    close_drain.add_argument("--summary", default="")
    close_drain.add_argument("--verification", default="")

    subparsers.add_parser("show")
    subparsers.add_parser("show-drain")
    subparsers.add_parser("clear")
    subparsers.add_parser("clear-drain")

    args = parser.parse_args()

    if args.command == "activate":
        goal = {
            "status": "active",
            "task": args.task,
            "source_id": args.source_id,
            "item_id": args.item_id,
            "location": args.location,
            "started_at": now(),
            "goal_type": "current",
        }
        write_current(goal)
        print(json.dumps(goal, indent=2))
        return 0

    if args.command == "close":
        goal = read_current()
        if not goal:
            goal = {"task": "", "started_at": ""}
        goal.update(
            {
                "status": args.status,
                "summary": args.summary,
                "verification": args.verification,
                "finished_at": now(),
                "goal_type": "current",
            }
        )
        append_history(goal)
        write_current(goal)
        print(json.dumps(goal, indent=2))
        return 0

    if args.command == "activate-drain":
        goal = {
            "status": "active",
            "task": args.task,
            "started_at": now(),
            "goal_type": "overarching",
        }
        write_drain(goal)
        print(json.dumps(goal, indent=2))
        return 0

    if args.command == "close-drain":
        goal = read_drain()
        if not goal:
            goal = {"task": DRAIN_TASK, "started_at": ""}
        goal.update(
            {
                "status": args.status,
                "summary": args.summary,
                "verification": args.verification,
                "finished_at": now(),
                "goal_type": "overarching",
            }
        )
        append_history(goal)
        write_drain(goal)
        print(json.dumps(goal, indent=2))
        return 0

    if args.command == "show":
        print(json.dumps(read_current(), indent=2))
        return 0

    if args.command == "show-drain":
        print(json.dumps(read_drain(), indent=2))
        return 0

    if args.command == "clear":
        for path in (CURRENT_JSON, CURRENT_MD):
            path.unlink(missing_ok=True)
        return 0

    if args.command == "clear-drain":
        for path in (DRAIN_JSON, DRAIN_MD):
            path.unlink(missing_ok=True)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
