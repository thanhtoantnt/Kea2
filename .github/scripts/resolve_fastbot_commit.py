#!/usr/bin/env python3
"""Resolve the Fastbot3 repository and commit requested by a PR or dispatch."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


DEFAULT_REPOSITORY = "zhangzhao4444/Fastbot3"
COMMIT_RE = re.compile(
    r"(?:fastbot3[-_\s]*commit|fastbot[-_\s]*commit|fb[-_\s]*commit)\s*[:=]\s*`?([0-9a-fA-F]{7,40})`?",
    re.IGNORECASE,
)
REPOSITORY_RE = re.compile(
    r"(?:fastbot3[-_\s]*repo(?:sitory)?|fastbot[-_\s]*repo(?:sitory)?)\s*[:=]\s*`?(?:https://github\.com/)?([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:\.git)?`?",
    re.IGNORECASE,
)
COMMIT_URL_RE = re.compile(
    r"github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/(?:commit|tree)/([0-9a-fA-F]{7,40})",
    re.IGNORECASE,
)
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def write_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def load_event() -> dict:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return {}
    path = Path(event_path)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def event_text(event: dict) -> str:
    pull_request = event.get("pull_request") or {}
    parts = [
        str(pull_request.get("title") or ""),
        str(pull_request.get("body") or ""),
    ]
    return "\n".join(parts)


def normalize_repository(value: str) -> str:
    value = value.strip().strip("`")
    value = re.sub(r"^https://github\.com/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\.git$", "", value, flags=re.IGNORECASE)
    return value


def load_fastbot_version() -> dict:
    path = Path("fastbot_version.json")
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    event = load_event()
    text = event_text(event)
    fastbot_version = load_fastbot_version()
    is_manual_dispatch = bool((os.environ.get("FASTBOT3_COMMIT_INPUT") or "").strip())

    commit = (os.environ.get("FASTBOT3_COMMIT_INPUT") or "").strip()
    if not commit:
        commit = str(fastbot_version.get("commit") or "").strip()
    if not commit:
        match = COMMIT_RE.search(text)
        if match:
            commit = match.group(1)
        else:
            match = COMMIT_URL_RE.search(text)
            if match:
                commit = match.group(2)

    repository = normalize_repository(os.environ.get("FASTBOT3_REPOSITORY_INPUT") or "")
    if not repository:
        repository = normalize_repository(str(fastbot_version.get("repository") or ""))
    if not repository:
        match = REPOSITORY_RE.search(text)
        if match:
            repository = match.group(1)
        else:
            match = COMMIT_URL_RE.search(text)
            repository = match.group(1) if match else DEFAULT_REPOSITORY

    if not commit:
        if is_manual_dispatch:
            print(
                "Fastbot3 commit is required. Set `fastbot_version.json` -> `commit`, "
                "add `Fastbot3-Commit: <sha>` to the PR title/body, or use workflow_dispatch.",
                file=sys.stderr,
            )
            return 2
        write_output("should_run", "false")
        write_output(
            "skip_reason",
            "No Fastbot3 commit found in fastbot_version.json or pull request title/body.",
        )
        return 0
    if not SHA_RE.fullmatch(commit):
        print(f"Invalid Fastbot3 commit: {commit!r}. Expected a 7-40 character hex SHA.", file=sys.stderr)
        return 2
    if not REPO_RE.fullmatch(repository):
        print(f"Invalid Fastbot3 repository: {repository!r}. Expected owner/repo.", file=sys.stderr)
        return 2

    write_output("should_run", "true")
    write_output("commit", commit.lower())
    write_output("short_commit", commit[:12].lower())
    write_output("repository", repository)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
