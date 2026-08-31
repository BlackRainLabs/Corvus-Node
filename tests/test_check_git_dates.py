"""Refuse frozen GIT_AUTHOR_DATE / GIT_COMMITTER_DATE.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "check-git-dates.sh"


def _run(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.pop("GIT_AUTHOR_DATE", None)
    merged.pop("GIT_COMMITTER_DATE", None)
    merged.update(env)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=merged,
    )


def test_check_git_dates_ok_when_unset() -> None:
    result = _run({})
    assert result.returncode == 0, result.stderr


def test_check_git_dates_refuses_author_date() -> None:
    result = _run({"GIT_AUTHOR_DATE": "Mon, 31 Aug 2026 01:50:57 -0500"})
    assert result.returncode == 1
    assert "Refuse frozen git timestamps" in result.stderr


def test_check_git_dates_refuses_committer_date() -> None:
    result = _run({"GIT_COMMITTER_DATE": "2026-08-31T01:56:12-05:00"})
    assert result.returncode == 1
    assert "Unset GIT_AUTHOR_DATE" in result.stderr
