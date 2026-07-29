from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QPixmap


class FrameAnimator(QObject):
    frame_changed = Signal(QPixmap)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._frames: list[QPixmap] = []
        self._index = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.setInterval(260)

    def load(self, skin_dir: Path, relative_paths: list[object]) -> bool:
        frames: list[QPixmap] = []
        for relative_path in relative_paths:
            if not isinstance(relative_path, str):
                continue
            pixmap = QPixmap(str(skin_dir / relative_path))
            if not pixmap.isNull():
                frames.append(pixmap)
        self._frames = frames
        self._index = 0
        self._timer.stop()
        if not frames:
            return False
        self.frame_changed.emit(frames[0])
        if len(frames) > 1:
            self._timer.start()
        return True

    def _advance(self) -> None:
        if not self._frames:
            return
        self._index = (self._index + 1) % len(self._frames)
        self.frame_changed.emit(self._frames[self._index])
