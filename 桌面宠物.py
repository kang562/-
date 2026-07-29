"""Windows 桌面电子宠物。

功能：透明置顶窗口、PNG 宠物图片、兜底手绘形象、全局键鼠提示、
拖拽、右键菜单和自动/点击台词。程序不保存任何键盘或鼠标输入。
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QPoint, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from pynput import keyboard, mouse
except ImportError:
    keyboard = None
    mouse = None


# ============================================================================
# 关键配置区：可直接修改以下参数，不需要改动后面的功能代码。
# ============================================================================
WINDOW_WIDTH = 320
WINDOW_HEIGHT = 400
PET_IMAGE_PATH = Path("assets") / "sandrone_q.png"  # 替换为透明 PNG 的相对路径。
BUBBLE_DURATION_MS = 1800  # 键鼠气泡自动消失时间，单位毫秒。
AUTO_DIALOG_INTERVAL_MS = 12000  # 自动台词间隔，单位毫秒。
INITIAL_ALWAYS_ON_TOP = True
WINDOW_SCALE_MIN = 0.65
WINDOW_SCALE_MAX = 1.60
WINDOW_SCALE_STEP = 0.15

# 黑、红、金配色，匹配木偶的礼服风格。
BUBBLE_BACKGROUND = QColor(30, 25, 35, 236)
BUBBLE_BORDER = QColor(211, 170, 92)
BUBBLE_TEXT = QColor(255, 239, 205)

DIALOG_TEXTS = [
    "咦？你在敲什么呢？",
    "别乱点我，木偶会生气。",
    "键盘敲得这么快，是在忙吗？",
    "我的裙子好看吗？",
    "别盯着我看呀。",
    "又按鼠标了，轻一点。",
]
# ============================================================================


def application_root() -> Path:
    """返回源码目录；PyInstaller 单文件模式下返回临时资源目录。"""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def readable_key_name(key: object) -> str:
    """把 pynput 按键对象转成短名称，始终只显示当前一个事件。"""
    character = getattr(key, "char", None)
    if isinstance(character, str) and len(character) == 1 and character.isprintable():
        return character.upper()

    name = getattr(key, "name", "")
    special_names = {
        "space": "空格",
        "enter": "回车",
        "tab": "Tab",
        "esc": "Esc",
        "backspace": "退格",
        "delete": "Delete",
        "up": "上方向键",
        "down": "下方向键",
        "left": "左方向键",
        "right": "右方向键",
        "shift": "Shift",
        "shift_l": "Shift",
        "shift_r": "Shift",
        "ctrl": "Ctrl",
        "ctrl_l": "Ctrl",
        "ctrl_r": "Ctrl",
        "alt": "Alt",
        "alt_l": "Alt",
        "alt_r": "Alt",
        "caps_lock": "Caps Lock",
        "cmd": "Win",
        "cmd_l": "Win",
        "cmd_r": "Win",
    }
    if name in special_names:
        return special_names[name]
    if name.startswith("f") and name[1:].isdigit():
        return name.upper()
    return str(key).replace("Key.", "").upper() or "按键"


class InputBridge(QObject):
    """把 pynput 的后台回调安全地转换为 Qt 主线程信号。"""

    event_received = pyqtSignal(str)
    listener_error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._keyboard_listener: object | None = None
        self._mouse_listener: object | None = None

    def start(self) -> None:
        """启动 Windows 全局键盘和鼠标监听，不写入文件也不保留历史。"""
        if keyboard is None or mouse is None:
            self.listener_error.emit("未安装 pynput，无法启用键鼠提示。")
            return
        try:
            self._keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
            self._mouse_listener = mouse.Listener(
                on_click=self._on_mouse_click,
                on_scroll=self._on_mouse_scroll,
            )
            self._keyboard_listener.start()
            self._mouse_listener.start()
        except Exception as error:
            self.listener_error.emit(f"键鼠监听启动失败：{error}")

    def stop(self) -> None:
        """退出前释放原生监听钩子，避免后台残留。"""
        for listener in (self._keyboard_listener, self._mouse_listener):
            stop = getattr(listener, "stop", None)
            if callable(stop):
                stop()
        self._keyboard_listener = None
        self._mouse_listener = None

    def _on_key_press(self, key: object) -> None:
        self.event_received.emit(f"按下 {readable_key_name(key)}")

    def _on_mouse_click(self, _x: int, _y: int, button: object, pressed: bool) -> None:
        if not pressed:
            return
        button_name = getattr(button, "name", "")
        labels = {"left": "鼠标左键", "right": "鼠标右键", "middle": "鼠标中键"}
        self.event_received.emit(f"点击 {labels.get(button_name, '鼠标按键')}")

    def _on_mouse_scroll(self, _x: int, _y: int, _dx: int, dy: int) -> None:
        if dy:
            self.event_received.emit("滚轮上" if dy > 0 else "滚轮下")


class DesktopPet(QWidget):
    """透明桌宠窗口：负责绘制、交互、气泡与自动台词。"""

    def __init__(self) -> None:
        super().__init__()
        self.current_scale = 1.0
        self.always_on_top = INITIAL_ALWAYS_ON_TOP
        self.tip_text = ""
        self.drag_offset: QPoint | None = None
        self.pet_pixmap: QPixmap | None = None
        self.pending_input = ""

        self._configure_window()
        self._load_pet_image()

        # 气泡与自动台词各自使用独立计时器，避免互相干扰。
        self.bubble_timer = QTimer(self)
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self.clear_tip)
        self.auto_dialog_timer = QTimer(self)
        self.auto_dialog_timer.setInterval(AUTO_DIALOG_INTERVAL_MS)
        self.auto_dialog_timer.timeout.connect(self.show_random_dialog)
        self.auto_dialog_timer.start()

        # 高频输入先合并 100ms，只显示最新事件，防止气泡频闪。
        self.input_debounce_timer = QTimer(self)
        self.input_debounce_timer.setSingleShot(True)
        self.input_debounce_timer.setInterval(100)
        self.input_debounce_timer.timeout.connect(self._show_pending_input)

        self.input_bridge = InputBridge()
        self.input_bridge.event_received.connect(self.queue_input_event)
        self.input_bridge.listener_error.connect(lambda message: self.show_tip(message, 3500))
        self.input_bridge.start()

    def _configure_window(self) -> None:
        """应用无边框、透明、置顶和不抢焦点的窗口属性。"""
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._apply_window_flags()
        self._apply_size()

    def _apply_window_flags(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _apply_size(self) -> None:
        self.setFixedSize(round(WINDOW_WIDTH * self.current_scale), round(WINDOW_HEIGHT * self.current_scale))

    def _load_pet_image(self) -> None:
        """尝试验证并加载 PNG；任一步失败都回退到程序手绘木偶。"""
        image_path = application_root() / PET_IMAGE_PATH
        self.pet_pixmap = None
        if not image_path.is_file():
            return
        try:
            # Pillow 先验证文件，损坏/伪装格式不会让 Qt 绘制流程崩溃。
            if Image is not None:
                with Image.open(image_path) as image:
                    image.verify()
            pixmap = QPixmap(str(image_path))
            if not pixmap.isNull():
                self.pet_pixmap = pixmap
        except Exception:
            self.pet_pixmap = None

    def queue_input_event(self, event_name: str) -> None:
        """接收键鼠事件，只保留短时间内最新的一次显示。"""
        self.pending_input = event_name
        if not self.input_debounce_timer.isActive():
            self.input_debounce_timer.start()

    def _show_pending_input(self) -> None:
        if self.pending_input:
            self.show_tip(self.pending_input)
        self.pending_input = ""

    def show_tip(self, text: str, duration: int = BUBBLE_DURATION_MS) -> None:
        self.tip_text = text
        self.bubble_timer.start(duration)
        self.update()

    def clear_tip(self) -> None:
        self.tip_text = ""
        self.update()

    def show_random_dialog(self) -> None:
        self.show_tip(random.choice(DIALOG_TEXTS))

    def change_scale(self, delta: float) -> None:
        """按右键菜单增减大小，缩放受配置区上下限保护。"""
        self.current_scale = max(WINDOW_SCALE_MIN, min(WINDOW_SCALE_MAX, self.current_scale + delta))
        self._apply_size()
        self.update()

    def toggle_always_on_top(self) -> None:
        self.always_on_top = not self.always_on_top
        self._apply_window_flags()
        self.show()  # 更改窗口 flag 后需要重新显示。

    def show_context_menu(self, global_position: QPoint) -> None:
        """右键菜单：缩放、置顶开关和退出。"""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e1923; color: #ffefcd; border: 1px solid #d3aa5c; padding: 5px; }"
            "QMenu::item { padding: 7px 28px 7px 12px; border-radius: 4px; }"
            "QMenu::item:selected { background: #7d2637; }"
            "QMenu::separator { height: 1px; background: #5c3d33; margin: 4px 8px; }"
        )
        larger = menu.addAction("放大宠物")
        larger.triggered.connect(lambda: self.change_scale(WINDOW_SCALE_STEP))
        smaller = menu.addAction("缩小宠物")
        smaller.triggered.connect(lambda: self.change_scale(-WINDOW_SCALE_STEP))
        menu.addSeparator()
        top_action = menu.addAction("取消置顶" if self.always_on_top else "开启置顶")
        top_action.triggered.connect(self.toggle_always_on_top)
        menu.addSeparator()
        exit_action = menu.addAction("退出程序")
        exit_action.triggered.connect(self.close)
        menu.exec(global_position)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.show_random_dialog()
        elif event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def closeEvent(self, event: object) -> None:
        self.input_bridge.stop()
        event.accept()  # type: ignore[union-attr]

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(self.current_scale, self.current_scale)
        if self.pet_pixmap is None:
            self._draw_fallback_sandrone(painter)
        else:
            # 保持 PNG 原始比例，不会拉伸变形。
            scaled = self.pet_pixmap.scaled(
                WINDOW_WIDTH,
                WINDOW_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (WINDOW_WIDTH - scaled.width()) // 2
            y = WINDOW_HEIGHT - scaled.height()
            painter.drawPixmap(x, y, scaled)
        self._draw_bubble(painter)
        painter.end()

    def _draw_fallback_sandrone(self, painter: QPainter) -> None:
        """无素材时绘制 Q 版木偶：灰发、蓝眼、白花、黑红金礼服。"""
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(18, 13, 21, 55))
        painter.drawEllipse(QRectF(72, 367, 176, 16))
        # 礼服与披肩。
        painter.setBrush(QColor("#1d1b25"))
        painter.drawRoundedRect(QRectF(76, 230, 168, 140), 52, 52)
        painter.setBrush(QColor("#8f263b"))
        painter.drawRoundedRect(QRectF(102, 248, 116, 111), 36, 36)
        painter.setBrush(QColor("#d3aa5c"))
        painter.drawEllipse(QRectF(148, 250, 24, 42))
        painter.setBrush(QColor("#29303a"))
        painter.drawRoundedRect(QRectF(51, 272, 59, 30), 15, 15)
        painter.drawRoundedRect(QRectF(210, 272, 59, 30), 15, 15)
        # 头发和脸。
        painter.setBrush(QColor("#b8b8c0"))
        painter.drawEllipse(QRectF(60, 66, 200, 190))
        painter.setBrush(QColor("#f3e6df"))
        painter.drawEllipse(QRectF(88, 91, 144, 139))
        painter.setBrush(QColor("#a4a3aa"))
        for x in (82, 111, 140, 169, 198):
            painter.drawRoundedRect(QRectF(x, 66, 40, 80), 20, 20)
        # 蓝眼和嘴。
        painter.setBrush(QColor("#5d9be8"))
        painter.drawEllipse(QRectF(108, 137, 36, 47))
        painter.drawEllipse(QRectF(176, 137, 36, 47))
        painter.setBrush(QColor("#182337"))
        painter.drawEllipse(QRectF(120, 152, 15, 25))
        painter.drawEllipse(QRectF(188, 152, 15, 25))
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(123, 154, 6, 8))
        painter.drawEllipse(QRectF(191, 154, 6, 8))
        painter.setPen(QPen(QColor("#8d5260"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(145, 184, 30, 18), 20 * 16, 140 * 16)
        # 白色花饰与金色花心。
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#fffaf5"))
        for x, y in ((88, 55), (102, 43), (117, 55), (102, 68)):
            painter.drawEllipse(QRectF(x, y, 28, 28))
        painter.setBrush(QColor("#d3aa5c"))
        painter.drawEllipse(QRectF(101, 55, 22, 22))

    def _draw_bubble(self, painter: QPainter) -> None:
        if not self.tip_text:
            return
        font = QFont("Microsoft YaHei UI", 12)
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        bubble_width = min(292, max(106, metrics.horizontalAdvance(self.tip_text) + 30))
        bubble = QRectF((WINDOW_WIDTH - bubble_width) / 2, 8, bubble_width, 42)
        painter.setBrush(BUBBLE_BACKGROUND)
        painter.setPen(QPen(BUBBLE_BORDER, 1.5))
        painter.drawRoundedRect(bubble, 10, 10)
        painter.setPen(BUBBLE_TEXT)
        painter.drawText(bubble, Qt.AlignmentFlag.AlignCenter, self.tip_text)


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    pet = DesktopPet()
    screen = app.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        pet.move(area.right() - pet.width() - 20, area.bottom() - pet.height() - 20)
    pet.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
