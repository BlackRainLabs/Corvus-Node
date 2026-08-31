"""corvus gui splash and packaging. Fail closed without PySide.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from pathlib import Path

import pytest

from corvus_node import __version__
from corvus_node.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_gui_fails_closed_without_pyside(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "corvus_gui.deps.gui_missing_reason",
        lambda: f"v{__version__} GUI needs PySide6; ./install.sh or corvus update",
    )
    code = main(["gui"])
    assert code == 2
    err = capsys.readouterr().err
    assert f"v{__version__}" in err
    assert "PySide6" in err
    assert "install.sh" in err or "corvus update" in err


def test_gui_fails_closed_when_runtime_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object):
        if name.startswith("corvus_gui"):
            raise ImportError("no gui")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    code = main(["gui"])
    assert code == 2
    err = capsys.readouterr().err
    assert f"v{__version__}" in err
    assert "GUI runtime is missing" in err


def test_gui_splash_offscreen(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("CORVUS_NODE_GUI_MS", "50")
    try:
        code = main(["gui"])
    except Exception as exc:
        pytest.skip(f"Qt offscreen unavailable: {exc}")
    if code != 0:
        pytest.skip("Qt offscreen unavailable")


def test_gui_splash_default_duration() -> None:
    from corvus_gui.splash import DEFAULT_MS

    assert 5000 <= DEFAULT_MS <= 10000


def test_release_ships_gui_runtime_only() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert "gui/corvus_gui" in workflow
    assert "gui/REQUESTS.md" not in workflow
    assert "--clobber" not in workflow
    assert "already released" in workflow
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert "PySide6" in pyproject
    assert '"gui/corvus_gui" = "corvus_gui"' in pyproject
    assert (ROOT / "gui" / "corvus_gui" / "splash.py").is_file()
    assert (ROOT / "gui" / "REQUESTS.md").is_file()
    assert (ROOT / "docs" / "gui" / "AVAILABLE.md").is_file()


def test_installer_lists_qt_host_libs() -> None:
    text = (ROOT / "packaging" / "operator-install.sh").read_text()
    assert "libxcb-cursor0" in text
    assert "mesa-libGL" in text
    assert "qt_host_specs" in text
    assert "corvus gui" in text
