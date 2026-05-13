from __future__ import annotations

import json
from typing import Any

from backend.config import APP_SETTINGS_PATH


DEFAULT_APP_SETTINGS: dict[str, Any] = {
    "remember_last_page": True,
    "confirm_destructive_actions": True,
    "double_click_behavior": "viewer",
    "include_subfolders_by_default": True,
    "skip_hidden_folders": True,
    "face_detection_enabled": True,
    "compact_sidebar": False,
    "thumbnail_density": "comfortable",
}


def get_default_app_settings() -> dict[str, Any]:
    """
    Returns the default application settings.
    """
    return dict(DEFAULT_APP_SETTINGS)


def load_app_settings() -> dict[str, Any]:
    """
    Loads application settings from disk.
    """
    if not APP_SETTINGS_PATH.exists():
        return get_default_app_settings()
    try:
        with APP_SETTINGS_PATH.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return get_default_app_settings()

    if not isinstance(loaded, dict):
        return get_default_app_settings()

    settings = get_default_app_settings()
    settings.update({
        key: value
        for key, value in loaded.items()
        if key in DEFAULT_APP_SETTINGS
    })
    return settings


def save_app_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """
    Saves application settings to disk.
    """
    merged = get_default_app_settings()
    merged.update({
        key: value
        for key, value in settings.items()
        if key in DEFAULT_APP_SETTINGS
    })
    APP_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with APP_SETTINGS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(merged, handle, indent=2)
    return merged


def update_app_settings(changes: dict[str, Any]) -> dict[str, Any]:
    """
    Updates application settings.
    """
    settings = load_app_settings()
    settings.update({
        key: value
        for key, value in changes.items()
        if key in DEFAULT_APP_SETTINGS and value is not None
    })
    return save_app_settings(settings)
