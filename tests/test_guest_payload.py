"""Guest payload must not include the host TCB.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from pathlib import Path

from corvus_node.vm.guest_payload import FORBIDDEN_GUEST_NAMES, assert_slim, install_into


def test_install_into_excludes_host_tcb(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    tree = tmp_path / "root"
    install_into(tree, repo)
    base = tree / "opt" / "corvus" / "src" / "corvus_node"
    assert (base / "protocol").is_dir()
    assert (base / "runtime").is_dir()
    assert (base / "tools").is_dir()
    assert (tree / "opt" / "corvus" / "guest" / "init.sh").is_file()
    assert (tree / "workspace").is_dir()
    for name in FORBIDDEN_GUEST_NAMES:
        assert not (base / name).exists()
    assert_slim(tree)
    passwd = (tree / "etc" / "passwd").read_text(encoding="utf-8")
    assert "corvus:x:1000:1000:" in passwd
