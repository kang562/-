from app.models import format_key, format_mouse_button


class CharacterKey:
    char = "a"
    name = ""


class SpecialKey:
    char = None
    name = "space"


class MouseButton:
    name = "left"


def test_keyboard_labels_are_single_events() -> None:
    assert format_key(CharacterKey()) == "A"
    assert format_key(SpecialKey()) == "空格"


def test_mouse_button_is_readable() -> None:
    assert format_mouse_button(MouseButton()) == "鼠标左键"
