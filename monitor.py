#!/usr/bin/env python3
"""Track stargazer removals across repositories owned by one GitHub user."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"
API_VERSION = "2026-03-10"
OWNER = os.environ.get("TARGET_OWNER", "macistone71-jpg")
TOKEN = os.environ.get("GH_TOKEN", "")
STATE_PATH = Path(os.environ.get("STATE_PATH", "data/stargazers.json"))
EVENTS_PATH = Path(os.environ.get("EVENTS_PATH", "data/unstar-events.jsonl"))
EXCLUDED_REPOSITORIES = {
    item.strip().lower()
    for item in os.environ.get(
        "EXCLUDED_REPOSITORIES", f"{OWNER}/github-star-monitor"
    ).split(",")
    if item.strip()
}


def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    if params:
        path = f"{path}?{urlencode(params)}"

    request = Request(
        f"{API_ROOT}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "User-Agent": "github-star-monitor",
            "X-GitHub-Api-Version": API_VERSION,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API request failed ({error.code}) for {path}: {detail}"
        ) from error


def paginated(path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = api_get(path, {"per_page": 100, "page": page})
        if not isinstance(batch, list):
            raise RuntimeError(f"Expected a list from {path}, received {type(batch)}")
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1


def owned_public_repositories() -> list[str]:
    repositories = paginated(f"/users/{OWNER}/repos")
    names = []
    for repository in repositories:
        full_name = repository["full_name"]
        if repository["owner"]["login"].lower() != OWNER.lower():
            continue
        if full_name.lower() in EXCLUDED_REPOSITORIES:
            continue
        names.append(full_name)
    return sorted(names, key=str.lower)


def stargazers(full_name: str) -> dict[str, str]:
    users = paginated(f"/repos/{full_name}/stargazers")
    return {
        str(user["id"]): user["login"]
        for user in users
        if user.get("id") is not None and user.get("login")
    }


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"owner": OWNER, "repositories": {}}
    with STATE_PATH.open("r", encoding="utf-8") as handle:
        state = json.load(handle)
    if state.get("owner", "").lower() != OWNER.lower():
        raise RuntimeError("State file belongs to a different GitHub owner")
    return state


def append_unstar_events(events: list[dict[str, str]]) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVENTS_PATH.touch(exist_ok=True)
    if not events:
        return
    with EVENTS_PATH.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    if not TOKEN:
        print("GH_TOKEN is required", file=sys.stderr)
        return 2

    checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    previous = load_state()
    previous_repositories = previous.get("repositories", {})
    current_repositories: dict[str, dict[str, str]] = {}
    events: list[dict[str, str]] = []

    repository_names = owned_public_repositories()
    for full_name in repository_names:
        current_users = stargazers(full_name)
        current_repositories[full_name] = current_users

        old_users = previous_repositories.get(full_name)
        if old_users is None:
            continue

        for user_id in sorted(set(old_users) - set(current_users), key=int):
            events.append(
                {
                    "detected_at": checked_at,
                    "event": "unstar",
                    "repository": full_name,
                    "user_id": user_id,
                    "user_login": old_users[user_id],
                }
            )

    append_unstar_events(events)

    state_changed = current_repositories != previous_repositories
    if state_changed:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        next_state = {
            "captured_at": checked_at,
            "owner": OWNER,
            "repositories": current_repositories,
        }
        with STATE_PATH.open("w", encoding="utf-8") as handle:
            json.dump(next_state, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")

    print(
        f"Checked {len(repository_names)} repositories; "
        f"detected {len(events)} unstar event(s); state_changed={state_changed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
