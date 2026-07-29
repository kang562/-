from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

from .animation import FrameAnimator
from .models import InputEvent, InputKind


DIALOG_TEXT = [
    "咦？你在敲什么呢",
    "别乱点我，木偶会生气。",
    "键盘敲得这么快，是在忙吗？",
    "我的裙子好看吗？",
    "别盯着我看呀。",
    "又按鼠标了，轻一点。",
]


class PetWindow(QWidget):
    settings_changed = Signal(dict)
    exit_requested = Signal()

    def __init__(self, settings: dict[str, Any], skin_dir: Path, manifest: dict[str, Any]) -> None:
        super().__init__()
        self.settings = settings
        self.skin_dir = skin_dir
        self.manifest = manifest
        self.canvas_width = int(manifest["canvas"]["width"])
        self.canvas_height = int(manifest["canvas"]["height"])
        self.tip_text = ""
        self._drag_offset: QPoint | None = None
        self._current_frame: QPixmap | None = None
        self._pending_input: InputEvent | None = None
        self._active_state = "idle"
        self._pulse = 0

        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self._clear_tip)
        self._input_delay_timer = QTimer(self)
        self._input_delay_timer.setSingleShot(True)
        self._input_delay_timer.setInterval(100)
        self._input_delay_timer.timeout.connect(self._display_pending_input)
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(650)
        self._idle_timer.timeout.connect(self._advance_idle)
        self._idle_timer.start()
        self._animator = FrameAnimator(self)
        self._animator.frame_changed.connect(self._set_frame)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._apply_window_flags()
        self._apply_scale()
        self._load_idle_frames()

    def _apply_window_flags(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus
        if self.settings["always_on_top"]:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _apply_scale(self) -> None:
        scale = float(self.settings["window_scale"])
        self.setFixedSize(round(self.canvas_width * scale), round(self.canvas_height * scale))

    def _load_idle_frames(self) -> None:
        if not self._animator.load(self.skin_dir, self.manifest.get("idle", [])):
            self._current_frame = None
            self.update()

    def set_skin(self, skin_dir: Path, manifest: dict[str, Any]) -> None:
        self.skin_dir = skin_dir
        self.manifest = manifest
        self.canvas_width = int(manifest["canvas"]["width"])
        self.canvas_height = int(manifest["canvas"]["height"])
        self._apply_scale()
        self._load_idle_frames()

    def set_always_on_top(self, enabled: bool) -> None:
        self.settings["always_on_top"] = enabled
        self._apply_window_flags()
        self.show()
        self.settings_changed.emit(self.settings)

    def set_scale(self, scale: float) -> None:
        self.settings["window_scale"] = scale
        self._apply_scale()
        self.settings_changed.emit(self.settings)

    def show_input(self, event: InputEvent) -> None:
        if not self.settings["input_display_enabled"]:
            return
        # Keep only the final event in a short burst to prevent bubble flicker.
        self._pending_input = event
        if not self._input_delay_timer.isActive():
            self._input_delay_timer.start()

    def _display_pending_input(self) -> None:
        event = self._pending_input
        self._pending_input = None
        if event is None or not self.settings["input_display_enabled"]:
            return
        prefix = "按下" if event.kind is InputKind.KEYBOARD else "触发"
        self._show_tip(f"{prefix} {event.label}")
        self._active_state = "typing" if event.kind is InputKind.KEYBOARD else "click"
        self._pulse = 2
        self.update()

    def show_listener_error(self, message: str) -> None:
        self._show_tip(message, duration=3600)

    def _show_tip(self, text: str, duration: int | None = None) -> None:
        self.tip_text = text
        self._bubble_timer.start(duration or int(self.settings["bubble_duration_ms"]))
        self.update()

    def _clear_tip(self) -> None:
        self.tip_text = ""
        self.update()

    def _advance_idle(self) -> None:
        if self._pulse:
            self._pulse -= 1
            if not self._pulse:
                self._active_state = "idle"
        self.update()

    def _set_frame(self, frame: QPixmap) -> None:
        self._current_frame = frame
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._show_tip(random.choice(DIALOG_TEXT))
            self._active_state = "click"
            self._pulse = 2
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.settings["position"] = {"x": self.x(), "y": self.y()}
            self.settings_changed.emit(self.settings)
        super().mouseReleaseEvent(event)

    def _show_context_menu(self, position: QPoint) -> None:
        menu = QMenu(self)
        toggle_input = menu.addAction("暂停输入显示" if self.settings["input_display_enabled"] else "恢复输入显示")
        toggle_input.triggered.connect(self._toggle_input)
        top_action = menu.addAction("取消置顶" if self.settings["always_on_top"] else "保持置顶")
        top_action.triggered.connect(lambda: self.set_always_on_top(not self.settings["always_on_top"]))
        menu.addSeparator()
        exit_action = menu.addAction("退出桌宠")
        exit_action.triggered.connect(self.exit_requested.emit)
        menu.exec(position)

    def _toggle_input(self) -> None:
        self.settings["input_display_enabled"] = not self.settings["input_display_enabled"]
        self.settings_changed.emit(self.settings)

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = self.width() / self.canvas_width
        painter.scale(scale, scale)
        if self._current_frame and not self._current_frame.isNull():
            painter.drawPixmap(0, 0, self.canvas_width, self.canvas_height, self._current_frame)
        else:
            self._draw_default_mascot(painter)
        self._draw_bubble(painter)
        painter.end()

    def _draw_default_mascot(self, painter: QPainter) -> None:
        bob = -3 if self._active_state == "idle" and self._pulse == 0 else -8
        painter.save()
        painter.translate(0, bob)
        painter.setPen(Qt.PenStyle.NoPen)
        # Ground shadow.
        painter.setBrush(QColor(20, 14, 22, 50))
        painter.drawEllipse(QRectF(77, 365, 168, 18))
        # Black and crimson dress.
        painter.setBrush(QColor("#1d1b25"))
        painter.drawRoundedRect(QRectF(78, 230, 164, 140), 48, 48)
        painter.setBrush(QColor("#8e2437"))
        painter.drawRoundedRect(QRectF(104, 248, 112, 106), 34, 34)
        painter.setBrush(QColor("#d2a95a"))
        painter.drawEllipse(QRectF(148, 248, 24, 42))
        # Arms respond subtly to a click or typing event.
        arm_y = 276 if self._active_state == "idle" else 262
        painter.setBrush(QColor("#29303a"))
        painter.drawRoundedRect(QRectF(54, arm_y, 52, 30), 15, 15)
        painter.drawRoundedRect(QRectF(214, arm_y, 52, 30), 15, 15)
        # Pale hair and face.
        painter.setBrush(QColor("#b9b9bf"))
        painter.drawEllipse(QRectF(62, 66, 196, 190))
        painter.setBrush(QColor("#f3e6df"))
        painter.drawEllipse(QRectF(88, 91, 144, 139))
        # Hair fringe.
        painter.setBrush(QColor("#a5a4aa"))
        for x in (83, 112, 141, 170, 199):
            painter.drawRoundedRect(QRectF(x, 67, 39, 79), 19, 19)
        # Blue eyes.
        painter.setBrush(QColor("#5d9be8"))
        painter.drawEllipse(QRectF(109, 137, 35, 46))
        painter.drawEllipse(QRectF(176, 137, 35, 46))
        painter.setBrush(QColor("#182337"))
        painter.drawEllipse(QRectF(120, 151, 15, 25))
        painter.drawEllipse(QRectF(187, 151, 15, 25))
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(123, 154, 6, 8))
        painter.drawEllipse(QRectF(190, 154, 6, 8))
        # Mouth.
        painter.setPen(QPen(QColor("#8d5260"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(145, 184, 30, 18), 20 * 16, 140 * 16)
        # White flower hair ornament.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#fffaf5"))
        for x, y in ((88, 55), (102, 43), (117, 55), (102, 68)):
            painter.drawEllipse(QRectF(x, y, 28, 28))
        painter.setBrush(QColor("#d2a95a"))
        painter.drawEllipse(QRectF(101, 55, 22, 22))
        painter.restore()

    def _draw_bubble(self, painter: QPainter) -> None:
        if not self.tip_text:
            return
        font = QFont("Microsoft YaHei UI", 12)
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        text_width = min(280, max(92, metrics.horizontalAdvance(self.tip_text) + 30))
        rect = QRectF((self.canvas_width - text_width) / 2, 8, text_width, 42)
        painter.setPen(QPen(QColor("#d2a95a"), 1.5))
        painter.setBrush(QColor(29, 27, 37, 232))
        painter.drawRoundedRect(rect, 8, 8)
        painter.setPen(QColor("#fff2ce"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.tip_text)
