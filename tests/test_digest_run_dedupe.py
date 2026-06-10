"""Tests for digest workflow send de-duplication."""

from __future__ import annotations

from datetime import date

from scripts.digest_run_dedupe import find_prior_successful_run


def test_find_prior_successful_run_matches_same_shanghai_day():
    runs = [
        {
            "databaseId": 101,
            "status": "completed",
            "conclusion": "success",
            "created_at": "2026-06-09T17:49:05Z",
            "html_url": "https://example.com/runs/101",
        },
        {
            "databaseId": 102,
            "status": "completed",
            "conclusion": "success",
            "created_at": "2026-06-10T03:22:03Z",
        },
    ]

    result = find_prior_successful_run(
        runs=runs,
        current_run_id="102",
        local_day=date(2026, 6, 10),
        timezone_name="Asia/Shanghai",
    )

    assert result == runs[0]


def test_find_prior_successful_run_ignores_current_failed_and_other_days():
    runs = [
        {
            "databaseId": 201,
            "status": "completed",
            "conclusion": "failure",
            "created_at": "2026-06-10T00:30:00Z",
        },
        {
            "databaseId": 202,
            "status": "completed",
            "conclusion": "success",
            "created_at": "2026-06-10T03:22:03Z",
        },
        {
            "databaseId": 203,
            "status": "completed",
            "conclusion": "success",
            "created_at": "2026-06-08T16:30:00Z",
        },
    ]

    result = find_prior_successful_run(
        runs=runs,
        current_run_id="202",
        local_day=date(2026, 6, 10),
        timezone_name="Asia/Shanghai",
    )

    assert result is None
