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
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHECKBOX_RE = re.compile(r"^(?P<indent>\s*)(?P<bullet>[-*]\s+)\[(?P<mark>[ xX>!~-])\]\s+(?P<title>.+?)\s*$")
TODO_RE = re.compile(r"^(?P<indent>\s*)(?:(?P<bullet>[-*]\s+))?TODO[:\s]+(?P<title>.+?)\s*$", re.IGNORECASE)
STATUS_RE = re.compile(r"^(?P<indent>\s*)(?:(?P<bullet>[-*]\s+))?(?P<keyword>TODO|WIP|DONE|BLKD)[:\s]+(?P<title>.+?)\s*$", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
GOOGLE_DOC_ID_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")
NOTION_PAGE_ID_RE = re.compile(r"([a-fA-F0-9]{32}|[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})")


CHECKBOX_STATUS = {" ": "todo", ">": "in-progress", "!": "blocked", "x": "done", "X": "done"}
KEYWORD_STATUS = {"TODO": "todo", "WIP": "in-progress", "DONE": "done", "BLKD": "blocked"}


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


def item_with_writeback(
    source_id: str,
    item_id: str,
    title: str,
    source_type: str,
    location: str,
    writeback: dict[str, Any],
) -> dict[str, Any]:
    task = item(source_id, item_id, title, source_type, location)
    task["writeback"] = writeback
    return task


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


def require_bearer_token(source: dict[str, Any]) -> str:
    token = bearer_token(source)
    if not token:
        raise SystemExit(
            f"Google Docs source '{source['id']}' requires auth for write-back. "
            "Configure auth: 'gcloud', token_env, or token_command."
        )
    return token


def google_docs_export_url(source: dict[str, Any]) -> str:
    if source.get("export_url"):
        return str(source["export_url"])
    return f"https://docs.google.com/document/d/{google_doc_id(source)}/export?format=txt"


def google_json_request(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code in {401, 403}:
            raise SystemExit(
                f"Google Docs API request was not authorized for source access. "
                f"Configure a token with Docs read/write scope. Detail: {detail}"
            ) from exc
        raise SystemExit(f"Google Docs API request failed with HTTP {exc.code}: {detail}") from exc


def google_document(source: dict[str, Any], token: str) -> dict[str, Any]:
    doc_id = google_doc_id(source)
    return google_json_request("GET", f"https://docs.googleapis.com/v1/documents/{doc_id}", token)


def paragraph_text(paragraph: dict[str, Any]) -> str:
    parts = []
    for element in paragraph.get("elements", []):
        text_run = element.get("textRun")
        if text_run:
            parts.append(text_run.get("content", ""))
    return "".join(parts)


def google_doc_paragraph_tasks(
    source: dict[str, Any],
    document: dict[str, Any],
    include_claimed: bool = False,
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    source_id = source["id"]
    doc_id = google_doc_id(source)
    location = source.get("url") or f"Google Docs:{doc_id}"

    for element in document.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue

        start_index = element.get("startIndex")
        end_index = element.get("endIndex")
        if not isinstance(start_index, int) or not isinstance(end_index, int):
            continue

        text = paragraph_text(paragraph)
        line = text.rstrip("\n")

        checkbox = CHECKBOX_RE.match(line)
        if checkbox:
            mark = checkbox.group("mark")
            task_status = CHECKBOX_STATUS.get(mark, "unknown")
            if task_status == "todo" or include_claimed:
                marker_offset = line.find("[ ]")
                if marker_offset < 0:
                    marker_offset = line.find(f"[{mark}]")
                tasks.append(
                    item_with_writeback(
                        source_id,
                        f"{source_id}:paragraph:{start_index}",
                        checkbox.group("title"),
                        "google_docs",
                        f"{location}:{start_index}",
                        {
                            "document_id": doc_id,
                            "paragraph_start": start_index,
                            "paragraph_end": end_index,
                            "marker_start": start_index + marker_offset,
                            "marker_end": start_index + marker_offset + 3,
                            "kind": "checkbox",
                            "status": task_status,
                        },
                    )
                )
            continue

        status_line = STATUS_RE.match(line)
        if status_line:
            keyword = status_line.group("keyword").upper()
            task_status = KEYWORD_STATUS.get(keyword, "unknown")
            if task_status != "todo" and not include_claimed:
                continue
            keyword_match = re.search(r"\b(TODO|WIP|DONE|BLKD)\b", line, re.IGNORECASE)
            if not keyword_match:
                continue
            tasks.append(
                item_with_writeback(
                    source_id,
                    f"{source_id}:paragraph:{start_index}",
                    status_line.group("title"),
                    "google_docs",
                    f"{location}:{start_index}",
                    {
                        "document_id": doc_id,
                        "paragraph_start": start_index,
                        "paragraph_end": end_index,
                        "marker_start": start_index + keyword_match.start(),
                        "marker_end": start_index + keyword_match.end(),
                        "kind": "todo",
                        "status": task_status,
                    },
                )
            )

    return tasks


def read_google_docs(source: dict[str, Any]) -> list[dict[str, Any]]:
    if source.get("writeback", "none") != "none":
        token = require_bearer_token(source)
        return google_doc_paragraph_tasks(source, google_document(source, token))

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


def find_google_doc_task_for_item(source: dict[str, Any], item_id: str, token: str) -> dict[str, Any]:
    document = google_document(source, token)
    for task in google_doc_paragraph_tasks(source, document, include_claimed=True):
        if task["item_id"] == item_id:
            return task

    if ":line:" in item_id:
        line_number = int(item_id.rsplit(":", 1)[1])
        tasks = google_doc_paragraph_tasks(source, document, include_claimed=True)
        if 1 <= line_number <= len(tasks):
            return tasks[line_number - 1]

    raise SystemExit(f"Could not find current Google Docs task for item id: {item_id}")


def google_docs_batch_update(source: dict[str, Any], token: str, requests: list[dict[str, Any]]) -> dict[str, Any]:
    doc_id = google_doc_id(source)
    return google_json_request(
        "POST",
        f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
        token,
        {"requests": requests},
    )


def mark_google_docs_item(config_path: Path, source: dict[str, Any], item_id: str, status: str) -> dict[str, Any]:
    token = require_bearer_token(source)
    task = find_google_doc_task_for_item(source, item_id, token)
    writeback = task.get("writeback", {})
    mode = source.get("writeback", "mark_done")

    if mode == "delete" and status == "done":
        paragraph_start = int(writeback["paragraph_start"])
        paragraph_end = int(writeback["paragraph_end"])
        # Leave the paragraph break in place. Deleting the final newline can be invalid in Docs.
        requests = [
            {
                "deleteContentRange": {
                    "range": {
                        "startIndex": paragraph_start,
                        "endIndex": max(paragraph_start, paragraph_end - 1),
                    }
                }
            }
        ]
    elif mode in {"mark_done", "mark-done", True, "delete"}:
        marker_start = int(writeback["marker_start"])
        marker_end = int(writeback["marker_end"])
        if writeback.get("kind") == "checkbox":
            replacement = {"in-progress": "[>]", "blocked": "[!]", "done": "[x]"}.get(status)
        else:
            replacement = {"in-progress": "WIP ", "blocked": "BLKD", "done": "DONE"}.get(status)
        if not replacement:
            raise SystemExit(f"Unsupported Google Docs status: {status}")
        requests = [
            {"deleteContentRange": {"range": {"startIndex": marker_start, "endIndex": marker_end}}},
            {"insertText": {"location": {"index": marker_start}, "text": replacement}},
        ]
    else:
        raise SystemExit(f"Unsupported Google Docs writeback mode for source '{source['id']}': {mode}")

    google_docs_batch_update(source, token, requests)
    return {
        "item_id": item_id,
        "status": status,
        "source_type": "google_docs",
        "source_id": source["id"],
        "writeback": mode,
        "config": str(config_path),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def notion_page_id(source: dict[str, Any]) -> str:
    raw = source.get("page_id") or source.get("url")
    if not raw:
        raise SystemExit(f"Notion source '{source['id']}' requires page_id or url.")
    match = NOTION_PAGE_ID_RE.search(str(raw))
    if not match:
        compact_match = NOTION_PAGE_ID_RE.search(str(raw).replace("-", ""))
        match = compact_match
    if not match:
        raise SystemExit(f"Could not extract Notion page id from source '{source['id']}'.")
    value = match.group(1).replace("-", "")
    return f"{value[0:8]}-{value[8:12]}-{value[12:16]}-{value[16:20]}-{value[20:32]}"


def notion_token(source: dict[str, Any]) -> str:
    token_env = source.get("token_env", "NOTION_TOKEN")
    if token_env and os.environ.get(token_env):
        return os.environ[token_env].strip()

    token_command = source.get("token_command")
    if token_command:
        result = subprocess.run(token_command, shell=True, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or result.stdout.strip() or f"Token command failed for Notion source '{source['id']}'.")
        return result.stdout.strip()

    raise SystemExit(f"Notion source '{source['id']}' requires token_env or token_command. Default token_env is NOTION_TOKEN.")


def notion_request(
    method: str,
    url: str,
    token: str,
    source: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": str(source.get("notion_version", "2022-06-28")),
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code in {401, 403, 404}:
            raise SystemExit(
                "Notion API request was not authorized or the page was not shared with the integration. "
                f"Detail: {detail}"
            ) from exc
        raise SystemExit(f"Notion API request failed with HTTP {exc.code}: {detail}") from exc


def rich_text_plain(rich_text: list[dict[str, Any]]) -> str:
    return "".join(part.get("plain_text", "") for part in rich_text)


def notion_block_text(block: dict[str, Any]) -> str:
    block_type = block.get("type")
    payload = block.get(block_type, {}) if block_type else {}
    return rich_text_plain(payload.get("rich_text", []))


def notion_children(source: dict[str, Any], token: str, block_id: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cursor = None
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={urllib.parse.quote(cursor)}"
        response = notion_request("GET", url, token, source)
        results.extend(response.get("results", []))
        if not response.get("has_more"):
            return results
        cursor = response.get("next_cursor")


def notion_block_tasks(
    source: dict[str, Any],
    blocks: list[dict[str, Any]],
    include_claimed: bool = False,
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    source_id = source["id"]
    page_ref = source.get("url") or f"Notion:{notion_page_id(source)}"

    for block in blocks:
        block_id = block.get("id")
        block_type = block.get("type")
        if not block_id or block.get("archived"):
            continue

        if block_type == "to_do":
            payload = block.get("to_do", {})
            title = rich_text_plain(payload.get("rich_text", [])).strip()
            prefixed_status = None
            clean_title = title
            if title.startswith("[>] "):
                prefixed_status = "in-progress"
                clean_title = title[4:]
            elif title.startswith("[!] "):
                prefixed_status = "blocked"
                clean_title = title[4:]
            elif title.startswith("[x] "):
                prefixed_status = "done"
                clean_title = title[4:]
            task_status = "done" if payload.get("checked", False) else (prefixed_status or "todo")
            if clean_title and (task_status == "todo" or include_claimed):
                tasks.append(
                    item_with_writeback(
                        source_id,
                        f"{source_id}:block:{block_id}",
                        clean_title,
                        "notion_page",
                        f"{page_ref}:{block_id}",
                        {
                            "type": "notion_page",
                            "block_id": block_id,
                            "block_type": block_type,
                            "mode": source.get("writeback", "mark_done"),
                            "status": task_status,
                        },
                    )
                )
            continue

        if block_type not in {"paragraph", "bulleted_list_item", "numbered_list_item"}:
            continue

        line = notion_block_text(block).strip()
        checkbox = CHECKBOX_RE.match(line)
        if checkbox:
            task_status = CHECKBOX_STATUS.get(checkbox.group("mark"), "unknown")
            if task_status != "todo" and not include_claimed:
                continue
            marker_offset = line.find("[ ]")
            if marker_offset < 0:
                marker_offset = line.find(f"[{checkbox.group('mark')}]")
            tasks.append(
                item_with_writeback(
                    source_id,
                    f"{source_id}:block:{block_id}",
                    checkbox.group("title"),
                    "notion_page",
                    f"{page_ref}:{block_id}",
                    {
                        "type": "notion_page",
                        "block_id": block_id,
                        "block_type": block_type,
                        "kind": "checkbox",
                        "text": line,
                        "marker_start": marker_offset,
                        "marker_end": marker_offset + 3,
                        "mode": source.get("writeback", "mark_done"),
                        "status": task_status,
                    },
                )
            )
            continue

        status_line = STATUS_RE.match(line)
        if status_line:
            keyword = status_line.group("keyword").upper()
            task_status = KEYWORD_STATUS.get(keyword, "unknown")
            if task_status != "todo" and not include_claimed:
                continue
            keyword_match = re.search(r"\b(TODO|WIP|DONE|BLKD)\b", line, re.IGNORECASE)
            if not keyword_match:
                continue
            tasks.append(
                item_with_writeback(
                    source_id,
                    f"{source_id}:block:{block_id}",
                    status_line.group("title"),
                    "notion_page",
                    f"{page_ref}:{block_id}",
                    {
                        "type": "notion_page",
                        "block_id": block_id,
                        "block_type": block_type,
                        "kind": "todo",
                        "text": line,
                        "marker_start": keyword_match.start(),
                        "marker_end": keyword_match.end(),
                        "mode": source.get("writeback", "mark_done"),
                        "status": task_status,
                    },
                )
            )

    return tasks


def read_notion_page(source: dict[str, Any]) -> list[dict[str, Any]]:
    token = notion_token(source)
    page_id = notion_page_id(source)
    blocks = notion_children(source, token, page_id)
    tasks = notion_block_tasks(source, blocks)

    if source.get("recursive", False):
        queue = [block for block in blocks if block.get("has_children")]
        while queue:
            block = queue.pop(0)
            children = notion_children(source, token, block["id"])
            tasks.extend(notion_block_tasks(source, children))
            queue.extend(child for child in children if child.get("has_children"))

    return tasks


def notion_rich_text(content: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": content}}]


def update_notion_text_block(
    source: dict[str, Any],
    token: str,
    block_id: str,
    block_type: str,
    content: str,
) -> dict[str, Any]:
    return notion_request(
        "PATCH",
        f"https://api.notion.com/v1/blocks/{block_id}",
        token,
        source,
        {block_type: {"rich_text": notion_rich_text(content)}},
    )


def mark_notion_item(config_path: Path, source: dict[str, Any], item_id: str, status: str) -> dict[str, Any]:
    parts = item_id.split(":")
    if len(parts) != 3 or parts[1] != "block":
        raise SystemExit(f"Unsupported Notion item id: {item_id}")

    token = notion_token(source)
    block_id = parts[2]
    mode = source.get("writeback", "mark_done")

    if mode == "delete" and status == "done":
        notion_request("DELETE", f"https://api.notion.com/v1/blocks/{block_id}", token, source)
    else:
        block = notion_request("GET", f"https://api.notion.com/v1/blocks/{block_id}", token, source)
        block_type = block.get("type")
        if block_type == "to_do":
            current = notion_block_text(block).strip()
            clean = re.sub(r"^\[[>!xX]\]\s+", "", current)
            if status == "done":
                payload = {"to_do": {"checked": True, "rich_text": notion_rich_text(clean)}}
            elif status == "in-progress":
                payload = {"to_do": {"checked": False, "rich_text": notion_rich_text(f"[>] {clean}")}}
            elif status == "blocked":
                payload = {"to_do": {"checked": False, "rich_text": notion_rich_text(f"[!] {clean}")}}
            else:
                raise SystemExit(f"Unsupported Notion status: {status}")
            notion_request("PATCH", f"https://api.notion.com/v1/blocks/{block_id}", token, source, payload)
        elif block_type in {"paragraph", "bulleted_list_item", "numbered_list_item"}:
            line = notion_block_text(block)
            checkbox = CHECKBOX_RE.match(line.strip())
            if checkbox:
                marker = {"in-progress": "[>]", "blocked": "[!]", "done": "[x]"}.get(status)
                if not marker:
                    raise SystemExit(f"Unsupported Notion status: {status}")
                replacement = re.sub(r"\[[ xX>!~-]\]", marker, line, count=1)
            else:
                marker = {"in-progress": "WIP ", "blocked": "BLKD", "done": "DONE"}.get(status)
                if not marker:
                    raise SystemExit(f"Unsupported Notion status: {status}")
                replacement = re.sub(r"\b(TODO|WIP|DONE|BLKD)\b", marker, line, count=1, flags=re.IGNORECASE)
            update_notion_text_block(source, token, block_id, block_type, replacement)
        else:
            raise SystemExit(f"Unsupported Notion block type for write-back: {block_type}")

    return {
        "item_id": item_id,
        "status": status,
        "source_type": "notion_page",
        "source_id": source["id"],
        "writeback": mode,
        "config": str(config_path),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


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
        elif source_type == "notion_page":
            items.extend(read_notion_page(source))
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
    if len(parts) != 3 or parts[1] not in {"line", "paragraph", "block"}:
        raise SystemExit(f"Unsupported item id: {item_id}")
    if parts[1] in {"line", "paragraph"} and not parts[2].isdigit():
        raise SystemExit(f"Unsupported item id: {item_id}")

    source_id = parts[0]
    source = next((candidate for candidate in config["sources"] if candidate.get("id") == source_id), None)
    if not source:
        raise SystemExit(f"Unknown source id: {source_id}")
    if source.get("type") == "google_docs":
        return mark_google_docs_item(config_path, source, item_id, status)
    if source.get("type") == "notion_page":
        return mark_notion_item(config_path, source, item_id, status)

    if parts[1] != "line":
        raise SystemExit(f"Source '{source_id}' does not support item id type: {parts[1]}")

    if source.get("type") != "text_file":
        raise SystemExit(
            f"Marking items is only supported for text_file, google_docs, and notion_page sources. "
            f"Source '{source_id}' is {source.get('type')}."
        )

    line_number = int(parts[2])
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
