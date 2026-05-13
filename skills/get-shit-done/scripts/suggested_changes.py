#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from todo_source import (
    google_docs_batch_update,
    google_document,
    google_doc_id,
    load_config,
    notion_children,
    notion_page_id,
    notion_request,
    notion_rich_text,
    notion_token,
    paragraph_text,
    require_bearer_token,
    resolve_path,
)


HEADING = "Suggested Changes"


def find_source(config_path: Path, source_id: str) -> dict[str, Any]:
    config = load_config(config_path)
    source = next((candidate for candidate in config["sources"] if candidate.get("id") == source_id), None)
    if not source:
        raise SystemExit(f"Unknown source id: {source_id}")
    return source


def clean_suggestions(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value and value.strip()]


def entry_lines(task: str, suggestions: list[str]) -> list[str]:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"- {stamp} - {task}"]
    lines.extend(f"  - {suggestion}" for suggestion in suggestions)
    return lines


def append_text_file(config_path: Path, source: dict[str, Any], task: str, suggestions: list[str]) -> dict[str, Any]:
    path = resolve_path(config_path, source["path"])
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    needs_heading = HEADING.lower() not in text.lower()
    suffix = []
    if not text.endswith("\n"):
        suffix.append("")
    if needs_heading:
        suffix.extend(["", f"## {HEADING}", ""])
    suffix.extend(entry_lines(task, suggestions))
    path.write_text(text + "\n".join(suffix).lstrip("\n") + "\n", encoding="utf-8")
    return {"status": "appended", "source_type": "text_file", "path": str(path), "count": len(suggestions)}


def append_google_docs(source: dict[str, Any], task: str, suggestions: list[str]) -> dict[str, Any]:
    token = require_bearer_token(source)
    document = google_document(source, token)
    body = document.get("body", {}).get("content", [])
    full_text = "\n".join(paragraph_text(element.get("paragraph", {})) for element in body if element.get("paragraph"))
    end_index = max((element.get("endIndex", 1) for element in body), default=1)
    insert_index = max(1, int(end_index) - 1)
    parts = []
    if HEADING.lower() not in full_text.lower():
        parts.extend(["", HEADING, ""])
    parts.extend(entry_lines(task, suggestions))
    text = "\n".join(parts) + "\n"
    google_docs_batch_update(
        source,
        token,
        [{"insertText": {"location": {"index": insert_index}, "text": text}}],
        document.get("revisionId"),
    )
    return {"status": "appended", "source_type": "google_docs", "document_id": google_doc_id(source), "count": len(suggestions)}


def append_notion(source: dict[str, Any], task: str, suggestions: list[str]) -> dict[str, Any]:
    token = notion_token(source)
    page_id = notion_page_id(source)
    children = notion_children(source, token, page_id)
    has_heading = any(
        child.get("type") in {"heading_1", "heading_2", "heading_3"}
        and HEADING.lower() in "".join(part.get("plain_text", "") for part in child.get(child["type"], {}).get("rich_text", [])).lower()
        for child in children
    )
    blocks: list[dict[str, Any]] = []
    if not has_heading:
        blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": notion_rich_text(HEADING)}})
    blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": notion_rich_text(entry_lines(task, [])[0])}})
    blocks.extend(
        {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": notion_rich_text(f"- {suggestion}")}}
        for suggestion in suggestions
    )
    notion_request("PATCH", f"https://api.notion.com/v1/blocks/{page_id}/children", token, source, {"children": blocks})
    return {"status": "appended", "source_type": "notion_page", "page_id": page_id, "count": len(suggestions)}


def append_suggestions(config_path: Path, source_id: str, task: str, suggestions: list[str]) -> dict[str, Any]:
    cleaned = clean_suggestions(suggestions)
    if not cleaned:
        return {"status": "skipped", "reason": "no suggestions"}

    source = find_source(config_path, source_id)
    source_type = source.get("type")
    if source_type == "text_file":
        return append_text_file(config_path, source, task, cleaned)
    if source_type == "google_docs":
        return append_google_docs(source, task, cleaned)
    if source_type == "notion_page":
        return append_notion(source, task, cleaned)
    return {"status": "skipped", "reason": f"unsupported source type: {source_type}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Append Get Shit Done suggestions to the source document.")
    parser.add_argument("--config", default="config/todo_sources.json")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--suggestion", action="append", default=[])
    args = parser.parse_args()

    result = append_suggestions(Path(args.config).expanduser().resolve(), args.source_id, args.task, args.suggestion)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
