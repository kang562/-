from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from .models import InputEvent, InputKind, format_key, format_mouse_button

try:
    from pynput import keyboard, mouse
except ImportError:  # Allows a clear in-app diagnostic before dependencies are installed.
    keyboard = None
    mouse = None


class GlobalInputListener(QObject):
    input_received = Signal(object)
    listener_error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._keyboard_listener: object | None = None
        self._mouse_listener: object | None = None

    def start(self) -> None:
        if keyboard is None or mouse is None:
            self.listener_error.emit("未安装 pynput，键鼠提示不可用。")
            return
        try:
            self._keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
            self._mouse_listener = mouse.Listener(on_click=self._on_mouse_click, on_scroll=self._on_mouse_scroll)
            self._keyboard_listener.start()
            self._mouse_listener.start()
        except Exception as exc:  # Platform hook failures must not stop the pet window.
            self.listener_error.emit(f"键鼠监听无法启动：{exc}")

    def stop(self) -> None:
        for listener in (self._keyboard_listener, self._mouse_listener):
            stop = getattr(listener, "stop", None)
            if callable(stop):
                stop()
        self._keyboard_listener = None
        self._mouse_listener = None

    def _on_key_press(self, key: object) -> None:
        label = format_key(key)
        if label:
            self.input_received.emit(InputEvent(InputKind.KEYBOARD, label))

    def _on_mouse_click(self, _x: int, _y: int, button: object, pressed: bool) -> None:
        if not pressed:
            return
        label = format_mouse_button(button)
        if label:
            self.input_received.emit(InputEvent(InputKind.MOUSE, label))

    def _on_mouse_scroll(self, _x: int, _y: int, _dx: int, dy: int) -> None:
        if dy:
            label = "滚轮上" if dy > 0 else "滚轮下"
            self.input_received.emit(InputEvent(InputKind.MOUSE, label))
