"""Strip Cursor / AI credit trailers from commit messages.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "strip-ai-trailers.sh"


def _strip(text: str, tmp_path: Path) -> str:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(text, encoding="utf-8")
    result = subprocess.run(
        ["bash", str(SCRIPT), str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return path.read_text(encoding="utf-8")


def test_strip_removes_cursor_coauthor(tmp_path: Path) -> None:
    out = _strip(
        "Stamp commits with the wall clock.\n\nCo-authored-by: Cursor <cursoragent@cursor.com>\n",
        tmp_path,
    )
    assert "Cursor" not in out
    assert "Stamp commits" in out


def test_strip_keeps_human_coauthor(tmp_path: Path) -> None:
    out = _strip(
        "Fix the installer.\n"
        "\n"
        "Co-authored-by: Alice <alice@example.com>\n"
        "Co-authored-by: Cursor <cursoragent@cursor.com>\n",
        tmp_path,
    )
    assert "Alice" in out
    assert "Cursor" not in out


def test_strip_removes_made_by_cursor(tmp_path: Path) -> None:
    out = _strip("Docs.\n\nMade by Cursor\nCreated by Cursor Agent\n", tmp_path)
    assert "Cursor" not in out
    assert "Docs." in out
