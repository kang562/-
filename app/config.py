from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "skin": "default",
    "always_on_top": True,
    "input_display_enabled": True,
    "bubble_duration_ms": 1800,
    "window_scale": 1.0,
    "position": {"x": None, "y": None},
}


def resource_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def user_data_root() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "DesktopPet"


def merge_settings(saved: object) -> dict[str, Any]:
    result = deepcopy(DEFAULT_SETTINGS)
    if not isinstance(saved, dict):
        return result
    for key in ("skin", "always_on_top", "input_display_enabled", "bubble_duration_ms", "window_scale"):
        if key in saved:
            result[key] = saved[key]
    if isinstance(saved.get("position"), dict):
        result["position"].update(saved["position"])
    result["skin"] = str(result["skin"])
    result["always_on_top"] = bool(result["always_on_top"])
    result["input_display_enabled"] = bool(result["input_display_enabled"])
    result["bubble_duration_ms"] = max(800, min(int(result["bubble_duration_ms"]), 5000))
    result["window_scale"] = max(0.7, min(float(result["window_scale"]), 1.5))
    return result


@dataclass
class SettingsStore:
    path: Path

    @classmethod
    def create_default(cls) -> "SettingsStore":
        return cls(user_data_root() / "settings.json")

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        settings = merge_settings(data)
        if data is None:
            self.save(settings)
        return settings

    def save(self, settings: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(merge_settings(settings), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def skin_manifest(skin_name: str) -> tuple[Path, dict[str, Any]]:
    skin_dir = resource_root() / "assets" / "skins" / skin_name
    manifest_path = skin_dir / "manifest.json"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    canvas = data.get("canvas") if isinstance(data.get("canvas"), dict) else {}
    width = int(canvas.get("width", 320))
    height = int(canvas.get("height", 400))
    normalized = {
        "name": str(data.get("name", skin_name)),
        "canvas": {"width": max(160, min(width, 800)), "height": max(160, min(height, 800))},
        "idle": data.get("idle", []) if isinstance(data.get("idle"), list) else [],
        "typing": data.get("typing", []) if isinstance(data.get("typing"), list) else [],
        "click": data.get("click", []) if isinstance(data.get("click"), list) else [],
    }
    return skin_dir, normalized


def available_skins() -> list[str]:
    skins_root = resource_root() / "assets" / "skins"
    if not skins_root.exists():
        return ["default"]
    return sorted(item.name for item in skins_root.iterdir() if item.is_dir() and (item / "manifest.json").exists())
