#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = REPO_ROOT / "state" / "reports"


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:80] or "task"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def render(args: argparse.Namespace) -> str:
    needs = args.needs_from_user.strip()
    if not needs:
        needs = "Nothing needed from you right now." if args.status == "done" else args.summary

    data = {
        "status": args.status,
        "task": args.task,
        "summary": args.summary,
        "verification": args.verification,
        "needs_from_user": needs,
        "source_id": args.source_id,
        "item_id": args.item_id,
        "location": args.location,
        "prompt_file": args.prompt_file,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    escaped = {key: html.escape(str(value)) for key, value in data.items()}
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escaped['task']} - {escaped['status']}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; max-width: 920px; color: #17202a; }}
    h1 {{ font-size: 28px; margin-bottom: 8px; }}
    h2 {{ font-size: 16px; margin-top: 28px; }}
    .status {{ display: inline-block; padding: 4px 8px; border: 1px solid #b8c2cc; border-radius: 6px; text-transform: uppercase; font-size: 12px; }}
    pre {{ white-space: pre-wrap; background: #f6f8fa; padding: 14px; border-radius: 6px; overflow-wrap: anywhere; }}
    dl {{ display: grid; grid-template-columns: 120px 1fr; gap: 8px 16px; }}
    dt {{ font-weight: 700; }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <span class="status">{escaped['status']}</span>
  <h1>{escaped['task']}</h1>
  <h2>What Happened</h2>
  <pre>{escaped['summary']}</pre>
  <h2>What You Need To Do</h2>
  <pre>{escaped['needs_from_user']}</pre>
  <h2>Verification</h2>
  <pre>{escaped['verification']}</pre>
  <h2>Details</h2>
  <dl>
    <dt>Source</dt><dd>{escaped['source_id']}</dd>
    <dt>Item</dt><dd>{escaped['item_id']}</dd>
    <dt>Location</dt><dd>{escaped['location']}</dd>
    <dt>Prompt</dt><dd>{escaped['prompt_file']}</dd>
    <dt>Created</dt><dd>{escaped['created_at']}</dd>
  </dl>
  <script type="application/json" id="handoff-data">{html.escape(json.dumps(data, indent=2))}</script>
</body>
</html>
"""


def should_open(args: argparse.Namespace) -> bool:
    if args.no_open:
        return False
    value = os.environ.get("TODO_SKILL_OPEN_HTML", "1").lower()
    return value not in {"0", "false", "no"}


def open_report(path: Path) -> None:
    macos_open = shutil.which("open")
    if macos_open:
        subprocess.Popen([macos_open, "-g", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    xdg = shutil.which("xdg-open")
    if not xdg:
        return
    subprocess.Popen([xdg, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and open an HTML handoff report.")
    parser.add_argument("--status", choices=["done", "blocked", "needs_human"], required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--verification", default="")
    parser.add_argument("--needs-from-user", default="")
    parser.add_argument("--source-id", default="")
    parser.add_argument("--item-id", default="")
    parser.add_argument("--location", default="")
    parser.add_argument("--prompt-file", default="")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"{utc_stamp()}-{slug(args.task)}-{args.status}.html"
    report_path.write_text(render(args), encoding="utf-8")
    if should_open(args):
        open_report(report_path)
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
