from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SETTINGS_PATH = Path(__file__).resolve().parents[1] / "styles" / "app_settings.json"

DEFAULTS: dict[str, Any] = {
    "ui_scaling": 1.0,
    "accent": "primary",
    "inventory_low_stock_threshold": 5,
    "scan_default_action": "Receive (+)",
    "scan_default_qty": 1,
    "monitor_auto_refresh": True,
    "monitor_refresh_interval_ms": 2000,
    "backup_dir": "",
}


def load_settings() -> dict[str, Any]:
    try:
        raw = SETTINGS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_settings() -> dict[str, Any]:
    data = DEFAULTS.copy()
    data.update(load_settings())
    return data


def get_setting(key: str, default: Any = None) -> Any:
    data = get_settings()
    if key in data:
        return data[key]
    return default


def update_settings(patch: dict[str, Any]) -> dict[str, Any]:
    data = get_settings()
    data.update(patch)
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data, indent=4), encoding="utf-8")
    return data

