from app.config import DEFAULT_SETTINGS, SettingsStore, merge_settings


def test_merge_settings_uses_safe_defaults() -> None:
    settings = merge_settings({"bubble_duration_ms": 99999, "window_scale": 9, "position": {"x": 12}})
    assert settings["bubble_duration_ms"] == 5000
    assert settings["window_scale"] == 1.5
    assert settings["position"] == {"x": 12, "y": None}


def test_store_creates_a_default_file(tmp_path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    assert store.load() == DEFAULT_SETTINGS
    assert store.path.exists()
