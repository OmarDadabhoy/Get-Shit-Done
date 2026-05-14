#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import smtplib
import subprocess
import sys
import tempfile
from email.message import EmailMessage
from pathlib import Path


def load_config(path: Path) -> dict:
    if not path.exists():
        return {"enabled": False}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def recipients(config: dict) -> list[str]:
    values = config.get("to", [])
    if isinstance(values, str):
        values = [values]
    env_values = []
    for name in ("TODO_SKILL_EMAIL_TO", "GSD_EMAIL_TO", "NOTIFY_EMAIL_TO", "USER_EMAIL", "EMAIL"):
        if os.environ.get(name):
            env_values.extend(os.environ[name].split(","))
    all_values = [str(value).strip() for value in [*values, *env_values] if str(value).strip()]
    return [value for value in all_values if value.lower() != "you@example.com"]


def enabled(config: dict, message_to: list[str]) -> bool:
    return bool(config.get("enabled", False) or message_to)


def subject(config: dict, event: str, task: str, explicit: str) -> str:
    if explicit:
        base = explicit
    elif event == "done":
        base = f"Task completed: {task}"
    else:
        base = f"Input needed: {task}"
    return f"{config.get('subject_prefix', '[AI Slaves]')} {base}".strip()


def body_text(event: str, task: str, body: str) -> str:
    lines = [
        f"Event: {event}",
        f"Task: {task}",
        "",
        body.strip() or "(no details provided)",
    ]
    return "\n".join(lines).strip() + "\n"


def send_command(config: dict, message_subject: str, message_body: str, message_to: list[str]) -> None:
    template = config.get("command")
    if not template:
        raise SystemExit("Notification method 'command' requires a command template.")

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(message_body)
        body_file = handle.name

    try:
        command = template.format(
            subject=shlex.quote(message_subject),
            body=shlex.quote(message_body),
            body_file=shlex.quote(body_file),
            to=shlex.quote(",".join(message_to)),
        )
        result = subprocess.run(command, shell=True, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or result.stdout.strip() or "Notification command failed.")
    finally:
        try:
            os.unlink(body_file)
        except OSError:
            pass


def send_smtp(config: dict, message_subject: str, message_body: str, message_to: list[str]) -> None:
    smtp = config.get("smtp", {})
    host = smtp.get("host")
    if not host:
        raise SystemExit("Notification method 'smtp' requires smtp.host.")

    username = os.environ.get(smtp.get("username_env", ""), smtp.get("username", ""))
    password = os.environ.get(smtp.get("password_env", ""), smtp.get("password", ""))
    sender = smtp.get("from") or config.get("from") or username
    if not sender:
        raise SystemExit("SMTP notification requires from or username.")

    message = EmailMessage()
    message["Subject"] = message_subject
    message["From"] = sender
    message["To"] = ", ".join(message_to)
    message.set_content(message_body)

    port = int(smtp.get("port", 587))
    with smtplib.SMTP(host, port, timeout=30) as server:
        if smtp.get("starttls", True):
            server.starttls()
        if username or password:
            server.login(username, password)
        server.send_message(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Send AI Slaves email notifications.")
    parser.add_argument("event", choices=["done", "needs_human"])
    parser.add_argument("--config", default="config/notifications.json")
    parser.add_argument("--task", required=True)
    parser.add_argument("--subject", default="")
    parser.add_argument("--body", default="")
    args = parser.parse_args()

    config = load_config(Path(args.config).expanduser().resolve())
    message_to = recipients(config)
    if not enabled(config, message_to):
        print("Notifications disabled.")
        return 0

    if not message_to:
        raise SystemExit("Notification config must include at least one recipient in 'to'.")

    message_subject = subject(config, args.event, args.task, args.subject)
    message_body = body_text(args.event, args.task, args.body)
    method = config.get("method", "command")
    if method == "command" and not config.get("command"):
        config["command"] = "mail -s {subject} {to} < {body_file}"

    if method == "smtp":
        send_smtp(config, message_subject, message_body, message_to)
    elif method == "command":
        send_command(config, message_subject, message_body, message_to)
    else:
        raise SystemExit(f"Unsupported notification method: {method}")

    print(f"Sent {args.event} notification to {', '.join(message_to)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
