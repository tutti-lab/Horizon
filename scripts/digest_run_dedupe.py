#!/usr/bin/env python3
"""Guard a digest workflow so it sends at most once per local day."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


def _parse_run_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _run_created_at(run: dict[str, Any]) -> str:
    return str(run.get("created_at") or run.get("createdAt") or "")


def _run_id(run: dict[str, Any]) -> str:
    return str(run.get("databaseId") or run.get("id") or "")


def find_prior_successful_run(
    *,
    runs: list[dict[str, Any]],
    current_run_id: str,
    local_day: date,
    timezone_name: str,
) -> dict[str, Any] | None:
    """Return a successful earlier run from the same local day, if one exists."""
    tz = ZoneInfo(timezone_name)
    for run in runs:
        if _run_id(run) == str(current_run_id):
            continue
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            continue

        created_at = _run_created_at(run)
        if not created_at:
            continue
        if _parse_run_time(created_at).astimezone(tz).date() == local_day:
            return run

    return None


def fetch_workflow_runs(repo: str, workflow: str, token: str | None) -> list[dict[str, Any]]:
    workflow_path = quote(workflow, safe="")
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_path}/runs?per_page=50"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
    return list(payload.get("workflow_runs", []))


def write_github_output(values: dict[str, str]) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return

    with open(output_path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"), required=False)
    parser.add_argument("--workflow", default="ai-digest.yml")
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", ""))
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    if not args.repo:
        raise SystemExit("--repo or GITHUB_REPOSITORY is required")

    tz = ZoneInfo(args.timezone)
    local_day = datetime.now(tz).date()
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    runs = fetch_workflow_runs(args.repo, args.workflow, token)
    prior = find_prior_successful_run(
        runs=runs,
        current_run_id=args.run_id,
        local_day=local_day,
        timezone_name=args.timezone,
    )

    if prior:
        url = str(prior.get("html_url") or prior.get("url") or "")
        reason = f"Prior successful {args.workflow} run already exists for {local_day}: {url}"
        print(reason)
        write_github_output({"should_run": "false", "reason": reason})
        return

    reason = f"No successful {args.workflow} run found for {local_day}; continuing."
    print(reason)
    write_github_output({"should_run": "true", "reason": reason})


if __name__ == "__main__":
    main()
