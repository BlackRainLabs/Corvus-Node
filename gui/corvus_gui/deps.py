"""PySide/Qt presence check. Fail closed before any window.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

from corvus_node import __version__


def gui_missing_reason() -> str | None:
    """Return a fail-closed message if PySide6 cannot be imported."""
    try:
        import PySide6  # noqa: F401
    except ImportError:
        return f"v{__version__} GUI needs PySide6; ./install.sh or corvus update"
    return None
