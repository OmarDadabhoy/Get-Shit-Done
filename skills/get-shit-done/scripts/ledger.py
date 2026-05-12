#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = REPO_ROOT / "config" / "ledger.json"
DEFAULT_COLUMNS = [
    "timestamp",
    "event",
    "task",
    "source_id",
    "item_id",
    "agent",
    "status",
    "summary",
    "prompt_file",
    "run_ref",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"enabled": False}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def token_from_config(config: dict[str, Any]) -> str:
    token_env = config.get("token_env")
    if token_env and os.environ.get(token_env):
        return os.environ[token_env].strip()

    token_command = config.get("token_command")
    if token_command:
        result = subprocess.run(token_command, shell=True, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or result.stdout.strip() or "Ledger token command failed.")
        return result.stdout.strip()

    if config.get("auth") == "gcloud":
        result = subprocess.run(["gcloud", "auth", "print-access-token"], text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or result.stdout.strip() or "Unable to get gcloud access token.")
        return result.stdout.strip()

    raise SystemExit("Google Sheets ledger requires auth: gcloud, token_env, or token_command.")


def row_from_args(args: argparse.Namespace) -> dict[str, str]:
    return {
        "timestamp": now(),
        "event": args.event,
        "task": args.task,
        "source_id": args.source_id,
        "item_id": args.item_id,
        "agent": args.agent,
        "status": args.status,
        "summary": args.summary,
        "prompt_file": args.prompt_file,
        "run_ref": args.run_ref,
    }


def append_csv(config: dict[str, Any], row: dict[str, str]) -> dict[str, Any]:
    path_value = config.get("path", "state/task_ledger.csv")
    path = Path(os.path.expanduser(os.path.expandvars(path_value)))
    if not path.is_absolute():
        path = REPO_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)

    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DEFAULT_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)

    return {"status": "written", "type": "local_csv", "path": str(path)}


def append_google_sheet(config: dict[str, Any], row: dict[str, str]) -> dict[str, Any]:
    spreadsheet_id = config.get("spreadsheet_id")
    value_range = config.get("range", "AgentRuns!A:J")
    if not spreadsheet_id:
        raise SystemExit("Google Sheets ledger requires spreadsheet_id.")

    token = token_from_config(config)
    values = [[row[column] for column in DEFAULT_COLUMNS]]
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/"
        f"{urllib.parse.quote(value_range, safe='')}:append?valueInputOption=USER_ENTERED"
    )
    request = urllib.request.Request(
        url,
        data=json.dumps({"values": values}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code in {401, 403, 404}:
            raise SystemExit(
                "Google Sheets ledger was not authorized or the sheet was not shared with the caller. "
                f"Detail: {detail}"
            ) from exc
        raise SystemExit(f"Google Sheets ledger failed with HTTP {exc.code}: {detail}") from exc

    return {
        "status": "written",
        "type": "google_sheets",
        "updatedRange": payload.get("updates", {}).get("updatedRange", ""),
    }


def append_ledger(config_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(config_path)
    if not config.get("enabled", False):
        return {"status": "disabled"}

    row = row_from_args(args)
    ledger_type = config.get("type", "local_csv")
    if ledger_type == "local_csv":
        return append_csv(config, row)
    if ledger_type == "google_sheets":
        return append_google_sheet(config, row)
    raise SystemExit(f"Unsupported ledger type: {ledger_type}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Append task/agent state to the Get Shit Done ledger.")
    parser.add_argument("event", choices=["queued", "assigned", "running", "done", "blocked", "needs_human"])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--task", required=True)
    parser.add_argument("--source-id", default="")
    parser.add_argument("--item-id", default="")
    parser.add_argument("--agent", default="")
    parser.add_argument("--status", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--prompt-file", default="")
    parser.add_argument("--run-ref", default="")
    args = parser.parse_args()

    result = append_ledger(Path(args.config).expanduser().resolve(), args)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
