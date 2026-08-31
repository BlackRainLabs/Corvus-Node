"""Local splash. Does not talk to Node and does not write launch rules.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from __future__ import annotations

import math
import os
import sys

from corvus_node import __version__

DEFAULT_MS = 8000
_FADE_IN_MS = 900
_FADE_OUT_MS = 1000


def _duration_ms() -> int:
    raw = os.environ.get("CORVUS_NODE_GUI_MS", "").strip()
    if not raw:
        return DEFAULT_MS
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_MS


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if value < lo else hi if value > hi else value


def _stagger(elapsed: float, start_ms: float, ramp_ms: float = 500.0) -> float:
    return _clamp((elapsed - start_ms) / ramp_ms)


def run_splash() -> int:
    """Show the Corvus-Node splash, then close. Returns 0 or 2."""
    try:
        from PySide6.QtCore import QElapsedTimer, Qt, QTimer
        from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
        from PySide6.QtWidgets import QApplication, QWidget
    except ImportError:
        print(
            f"corvus: v{__version__} GUI needs PySide6; ./install.sh or corvus update",
            file=sys.stderr,
        )
        return 2

    duration_ms = _duration_ms()

    class Splash(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Corvus-Node")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
            )
            self.setFixedSize(520, 300)
            self.setStyleSheet("background-color: #07080a;")
            self._clock = QElapsedTimer()
            self._clock.start()
            self._tick = QTimer(self)
            self._tick.setInterval(16)
            self._tick.timeout.connect(self._on_tick)
            self._tick.start()

        def _elapsed(self) -> int:
            return self._clock.elapsed()

        def _on_tick(self) -> None:
            elapsed = self._elapsed()
            if elapsed >= duration_ms:
                self._tick.stop()
                app = QApplication.instance()
                if app is not None:
                    app.quit()
                return
            remain = duration_ms - elapsed
            fade_out = _clamp(remain / _FADE_OUT_MS) if remain < _FADE_OUT_MS else 1.0
            fade_in = _clamp(elapsed / _FADE_IN_MS)
            self.setWindowOpacity(fade_in * fade_out)
            self.update()

        def paintEvent(self, event: object) -> None:
            del event
            elapsed = float(self._elapsed())
            pulse = 0.55 + 0.45 * math.sin(elapsed / 280.0)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), QColor("#07080a"))
            inset = 10
            outer = self.rect().adjusted(inset, inset, -inset, -inset)
            chrome = QColor("#8a9199")
            chrome.setAlpha(int(80 + 175 * pulse))
            painter.setPen(QPen(chrome, 1.5))
            painter.drawRect(outer)
            inner = QColor("#3a3f46")
            inner.setAlpha(int(120 + 80 * pulse))
            painter.setPen(QPen(inner, 1))
            painter.drawRect(outer.adjusted(3, 3, -3, -3))

            scan_h = outer.height() - 8
            if scan_h > 0:
                band = outer.adjusted(4, 4, -4, -4)
                painter.setClipRect(band)
                y = band.top() + int((elapsed * 0.18) % max(1, band.height()))
                grad = QLinearGradient(band.left(), y - 18, band.left(), y + 18)
                sweep = QColor("#c5ccd4")
                sweep.setAlpha(int(90 * pulse))
                clear = QColor("#c5ccd4")
                clear.setAlpha(0)
                grad.setColorAt(0.0, clear)
                grad.setColorAt(0.5, sweep)
                grad.setColorAt(1.0, clear)
                painter.fillRect(band.left(), y - 18, band.width(), 36, QBrush(grad))
                painter.setClipping(False)

            word_a = _stagger(elapsed, 180, 550)
            title_a = _stagger(elapsed, 700, 550)
            line_a = _stagger(elapsed, 1300, 600)

            word = QFont("sans-serif")
            word.setPointSize(9)
            word.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
            painter.setFont(word)
            wc = QColor("#6b7280")
            wc.setAlpha(int(255 * word_a))
            painter.setPen(wc)
            painter.drawText(
                outer.adjusted(0, 36, 0, 0),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                "BLACK RAIN LABS",
            )

            title = QFont("sans-serif")
            title.setPointSize(22)
            title.setBold(True)
            painter.setFont(title)
            tc = QColor("#e8eaed")
            tc.setAlpha(int(255 * title_a))
            painter.setPen(tc)
            painter.drawText(
                outer.adjusted(0, 88, 0, 0),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                "Corvus-Node",
            )

            body = QFont("sans-serif")
            body.setPointSize(12)
            painter.setFont(body)
            lc = QColor("#9aa0a6")
            lc.setAlpha(int(255 * line_a))
            painter.setPen(lc)
            painter.drawText(
                outer.adjusted(0, 150, 0, 0),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                "User Interface in Development",
            )

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        assert app is not None
        window = Splash()
        screen = app.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            window.move(geo.center() - window.rect().center())
        window.show()
        app.exec()
    except Exception as exc:
        print(
            f"corvus: v{__version__} GUI Qt failed ({exc}); ./install.sh",
            file=sys.stderr,
        )
        return 2
    return 0
