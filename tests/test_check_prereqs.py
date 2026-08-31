"""Host check script used by make check.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "check-prereqs.sh"


def test_check_prereqs_runs() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "Corvus-Node host check" in result.stdout
    assert result.returncode in {0, 1}
    if result.returncode == 1:
        assert "Not ready to run a guest" in result.stdout
    else:
        assert "Ready for:" in result.stdout
