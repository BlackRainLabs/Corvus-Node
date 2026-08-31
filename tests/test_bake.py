"""guest/bake.sh: mmdebstrap unshare must not target a 0700 unpack dir.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mmdebstrap_streams_tar_via_world_writable_tmp() -> None:
    text = (ROOT / "guest" / "bake.sh").read_text()
    assert "mmdebstrap_tmpdir" in text
    assert "--format=tar" in text
    assert "bookworm - " in text or "bookworm -" in text
    assert "printf '/tmp'" in text
    mm_block = text.split("baking rootfs with mmdebstrap", 1)[1].split(
        "baking rootfs with debootstrap", 1
    )[0]
    assert 'bookworm "$tree"' not in mm_block
    assert "--format=tar" in mm_block
