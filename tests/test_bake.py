"""guest/bake.sh: mmdebstrap unshare and Debian keys on Ubuntu.

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
    assert "printf '/tmp'" in text
    mm_block = text.split("baking rootfs with mmdebstrap", 1)[1].split(
        "baking rootfs with debootstrap", 1
    )[0]
    assert 'bookworm "$tree"' not in mm_block
    assert "--format=tar" in mm_block
    assert "--keyring=" in mm_block
    assert 'mkdir -p "$1/etc/apt/trusted.gpg.d"' in mm_block
    assert "copy-in" in mm_block
    assert "signed-by=" not in mm_block
    assert "fetching Debian archive keyring" in text
    assert 'echo "fetching Debian archive keyring' in text
    assert ">&2" in text.split("fetching Debian archive keyring", 1)[1][:80]


def test_bake_pins_debian_archive_keyring() -> None:
    text = (ROOT / "guest" / "bake.sh").read_text()
    assert "debian-archive-keyring_2025.1_all.deb" in text
    assert "9ea7778e443144ca490668737a8ab22dd3e748bb99e805e22ec055abeb3c7fac" in text
    assert "debian_keyring_for_unshare" in text
    install = (ROOT / "packaging" / "operator-install.sh").read_text()
    assert "debian-archive-keyring" in install


def test_bake_copies_payload_without_host_pydantic() -> None:
    text = (ROOT / "guest" / "bake.sh").read_text()
    assert "spec_from_file_location" in text
    assert "from corvus_node.vm.guest_payload" not in text
    payload = text.split("install_payload()", 1)[1].split("install_pydantic()", 1)[0]
    assert "PYTHONPATH=" not in payload
