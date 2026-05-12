#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHECKBOX_RE = re.compile(r"^(?P<indent>\s*)(?P<bullet>[-*]\s+)\[(?P<mark>[ xX>!~-])\]\s+(?P<title>.+?)\s*$")
TODO_RE = re.compile(r"^(?P<indent>\s*)(?:(?P<bullet>[-*]\s+))?TODO[:\s]+(?P<title>.+?)\s*$", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
GOOGLE_DOC_ID_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config.get("sources"), list):
        raise SystemExit("Config must contain a 'sources' array.")
    return config


def resolve_path(config_path: Path, value: str) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(value))
    path = Path(expanded)
    if not path.is_absolute():
        path = config_path.parent / path
    return path.resolve()


def fingerprint(source_id: str, title: str) -> str:
    raw = f"{source_id}\0{title.strip()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def item(source_id: str, item_id: str, title: str, source_type: str, location: str) -> dict[str, Any]:
    clean_title = title.strip()
    return {
        "source_id": source_id,
        "item_id": item_id,
        "title": clean_title,
        "source_type": source_type,
        "location": location,
        "fingerprint": fingerprint(source_id, clean_title),
    }


def parse_tasks(text: str, source_id: str, source_type: str, location: str) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        checkbox = CHECKBOX_RE.match(line)
        if checkbox:
            mark = checkbox.group("mark")
            if mark == " ":
                tasks.append(item(source_id, f"{source_id}:line:{line_number}", checkbox.group("title"), source_type, f"{location}:{line_number}"))
            continue

        todo = TODO_RE.match(line)
        if todo:
            tasks.append(item(source_id, f"{source_id}:line:{line_number}", todo.group("title"), source_type, f"{location}:{line_number}"))
    return tasks


def read_text_file(source: dict[str, Any], config_path: Path) -> list[dict[str, Any]]:
    source_id = source["id"]
    path = resolve_path(config_path, source["path"])
    if not path.exists():
        return []
    return parse_tasks(path.read_text(encoding="utf-8"), source_id, "text_file", str(path))


def applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def strip_notes_html(value: str) -> str:
    value = value.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    value = re.sub(r"</p>\s*<p[^>]*>", "\n", value)
    value = HTML_TAG_RE.sub("", value)
    return html.unescape(value)


def read_apple_notes(source: dict[str, Any]) -> list[dict[str, Any]]:
    source_id = source["id"]
    title = source.get("title")
    if not title:
        raise SystemExit(f"Apple Notes source '{source_id}' requires a title.")

    note_name = applescript_string(title)
    script = f'''
set noteName to {note_name}
tell application "Notes"
    repeat with accountRef in accounts
        repeat with folderRef in folders of accountRef
            repeat with noteRef in notes of folderRef
                if name of noteRef is noteName then
                    return body of noteRef
                end if
            end repeat
        end repeat
    end repeat
end tell
error "Note not found: " & noteName
'''
    result = subprocess.run(["osascript", "-e", script], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip() or f"Unable to read Apple Notes source '{source_id}'.")
    return parse_tasks(strip_notes_html(result.stdout), source_id, "apple_notes", f"Apple Notes:{title}")


def google_doc_id(source: dict[str, Any]) -> str:
    if source.get("document_id"):
        return str(source["document_id"])

    url = source.get("url")
    if not url:
        raise SystemExit(f"Google Docs source '{source['id']}' requires document_id, url, or export_url.")
    match = GOOGLE_DOC_ID_RE.search(url)
    if not match:
        raise SystemExit(f"Could not extract Google Docs document id from source '{source['id']}'.")
    return match.group(1)


def bearer_token(source: dict[str, Any]) -> str | None:
    token_env = source.get("token_env")
    if token_env and os.environ.get(token_env):
        return os.environ[token_env].strip()

    token_command = source.get("token_command")
    if token_command:
        result = subprocess.run(token_command, shell=True, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or result.stdout.strip() or f"Token command failed for Google Docs source '{source['id']}'.")
        return result.stdout.strip()

    if source.get("auth") == "gcloud":
        result = subprocess.run(["gcloud", "auth", "print-access-token"], text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or result.stdout.strip() or "Unable to get a gcloud access token.")
        return result.stdout.strip()

    return None


def google_docs_export_url(source: dict[str, Any]) -> str:
    if source.get("export_url"):
        return str(source["export_url"])
    return f"https://docs.google.com/document/d/{google_doc_id(source)}/export?format=txt"


def read_google_docs(source: dict[str, Any]) -> list[dict[str, Any]]:
    source_id = source["id"]
    url = google_docs_export_url(source)
    token = bearer_token(source)

    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(request, timeout=int(source.get("timeout_seconds", 30))) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            text = response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise SystemExit(
                f"Google Docs source '{source_id}' was not readable. Make the doc public/published, "
                "or configure auth: 'gcloud', token_env, or token_command."
            ) from exc
        raise SystemExit(f"Google Docs source '{source_id}' failed with HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Google Docs source '{source_id}' could not be fetched: {exc.reason}") from exc

    location = source.get("url") or source.get("export_url") or f"Google Docs:{google_doc_id(source)}"
    return parse_tasks(text, source_id, "google_docs", str(location))


def collect_items(config_path: Path) -> list[dict[str, Any]]:
    config = load_config(config_path)
    items: list[dict[str, Any]] = []
    for source in config["sources"]:
        if not source.get("enabled", True):
            continue
        source_type = source.get("type")
        if not source.get("id"):
            raise SystemExit("Every source requires an id.")
        if source_type == "text_file":
            items.extend(read_text_file(source, config_path))
        elif source_type == "apple_notes":
            items.extend(read_apple_notes(source))
        elif source_type == "google_docs":
            items.extend(read_google_docs(source))
        elif source_type in {"imessage", "messages", "messages_sqlite"}:
            raise SystemExit("Messages/iMessage sources are intentionally not implemented. Mirror those todos into a text file or Apple Notes source first.")
        else:
            raise SystemExit(f"Unsupported source type: {source_type}")
    return items


def update_text_line(line: str, status: str) -> str:
    marker_by_status = {
        "todo": "[ ]",
        "in-progress": "[>]",
        "done": "[x]",
        "blocked": "[!]",
    }
    marker = marker_by_status[status]
    checkbox = CHECKBOX_RE.match(line)
    if checkbox:
        return re.sub(r"\[[ xX>!~-]\]", marker, line, count=1)

    todo = TODO_RE.match(line)
    if todo:
        indent = todo.group("indent") or ""
        bullet = todo.group("bullet") or "- "
        title = todo.group("title").strip()
        return f"{indent}{bullet}{marker} {title}"

    return line


def mark_item(config_path: Path, item_id: str, status: str) -> dict[str, Any]:
    config = load_config(config_path)
    parts = item_id.split(":")
    if len(parts) != 3 or parts[1] != "line" or not parts[2].isdigit():
        raise SystemExit(f"Unsupported item id: {item_id}")

    source_id = parts[0]
    line_number = int(parts[2])
    source = next((candidate for candidate in config["sources"] if candidate.get("id") == source_id), None)
    if not source:
        raise SystemExit(f"Unknown source id: {source_id}")
    if source.get("type") != "text_file":
        raise SystemExit(f"Marking items is only supported for text_file sources. Source '{source_id}' is {source.get('type')}.")

    path = resolve_path(config_path, source["path"])
    lines = path.read_text(encoding="utf-8").splitlines()
    if line_number < 1 or line_number > len(lines):
        raise SystemExit(f"Line {line_number} is out of range for {path}.")

    old_line = lines[line_number - 1]
    lines[line_number - 1] = update_text_line(old_line, status)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "item_id": item_id,
        "status": status,
        "path": str(path),
        "line": line_number,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read and update Get Shit Done todo sources.")
    parser.add_argument("command", choices=["list", "next", "mark"])
    parser.add_argument("--config", default="config/todo_sources.json")
    parser.add_argument("--item-id")
    parser.add_argument("--status", choices=["todo", "in-progress", "done", "blocked"])
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()

    if args.command == "list":
        print(json.dumps(collect_items(config_path), indent=2))
        return 0

    if args.command == "next":
        items = collect_items(config_path)
        if not items:
            return 1
        print(json.dumps(items[0], indent=2))
        return 0

    if args.command == "mark":
        if not args.item_id or not args.status:
            raise SystemExit("mark requires --item-id and --status.")
        print(json.dumps(mark_item(config_path, args.item_id, args.status), indent=2))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
