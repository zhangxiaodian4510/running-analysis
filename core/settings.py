"""单行 key/value 设置。"""
from __future__ import annotations

from config import DEFAULT_HR_MAX, DEFAULT_UNITS
from core.db import execute, query_one

DEFAULTS = {
    "units": DEFAULT_UNITS,
    "hr_max": str(DEFAULT_HR_MAX),
}


def get(key: str, default=None):
    row = query_one("SELECT value FROM settings WHERE key=?", (key,))
    if row:
        return row["value"]
    d = DEFAULTS.get(key)
    return d if d is not None else default


def get_int(key: str, default: int = 0) -> int:
    v = get(key)
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def set(key: str, value) -> None:
    execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def hr_max() -> int:
    return get_int("hr_max", DEFAULT_HR_MAX)


def units() -> str:
    return get("units", DEFAULT_UNITS)
