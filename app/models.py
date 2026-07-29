from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InputKind(str, Enum):
    KEYBOARD = "keyboard"
    MOUSE = "mouse"


@dataclass(frozen=True, slots=True)
class InputEvent:
    kind: InputKind
    label: str


def format_key(key: object) -> str | None:
    """Return a single, privacy-preserving label for a pressed key."""
    character = getattr(key, "char", None)
    if isinstance(character, str) and len(character) == 1:
        if character.isprintable():
            return character.upper()
        return None

    name = getattr(key, "name", "")
    labels = {
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
        "cmd": "Win",
        "cmd_l": "Win",
        "cmd_r": "Win",
        "caps_lock": "Caps Lock",
    }
    if name in labels:
        return labels[name]
    if name.startswith("f") and name[1:].isdigit():
        return name.upper()
    return None


def format_mouse_button(button: object) -> str | None:
    name = getattr(button, "name", "")
    labels = {"left": "鼠标左键", "right": "鼠标右键", "middle": "鼠标中键"}
    return labels.get(name)
