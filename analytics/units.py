"""单位与配速格式化。内部一律用公制秒/米；显示时按设置换算。"""
from __future__ import annotations

from typing import Optional


def pace_from_speed(speed_mps: Optional[float]) -> Optional[float]:
    """m/s → 秒/公里。"""
    if not speed_mps or speed_mps <= 0:
        return None
    return 1000.0 / speed_mps


def pace_from_duration_distance(duration_s, distance_m) -> Optional[float]:
    if not duration_s or not distance_m:
        return None
    return duration_s / (distance_m / 1000.0)


def fmt_pace(sec_per_km: Optional[float]) -> str:
    """秒/公里 → '5:23'。"""
    if sec_per_km is None or sec_per_km != sec_per_km:
        return "—"
    sec_per_km = max(0.0, sec_per_km)
    m = int(sec_per_km // 60)
    s = int(round(sec_per_km % 60))
    if s == 60:
        m += 1
        s = 0
    return f"{m}:{s:02d}"


def fmt_duration(sec: Optional[float]) -> str:
    """秒 → 'h:mm:ss' 或 'm:ss'。"""
    if sec is None or sec != sec:
        return "—"
    sec = int(round(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def fmt_distance(m: Optional[float], units: str = "metric") -> str:
    if m is None or m != m:
        return "—"
    if units == "imperial":
        return f"{m / 1609.344:.2f} mi"
    return f"{m / 1000:.2f} km"


def fmt_speed(mps: Optional[float], units: str = "metric") -> str:
    if not mps or mps != mps:
        return "—"
    if units == "imperial":
        return f"{mps * 2.236936:.1f} mph"
    return f"{mps * 3.6:.1f} km/h"


def fmt_int(x, suffix: str = "") -> str:
    if x is None or x != x:
        return "—"
    return f"{int(round(x))}{suffix}"


def fmt_stride(m) -> str:
    """米 → '1.18 m'。"""
    if m is None or m != m:
        return "—"
    return f"{m:.2f} m"


def fmt_vertical_oscillation(cm) -> str:
    """厘米 → '7.4 cm'。"""
    if cm is None or cm != cm:
        return "—"
    return f"{cm:.1f} cm"


def fmt_ratio(pct) -> str:
    """百分比 → '6.2 %'。"""
    if pct is None or pct != pct:
        return "—"
    return f"{pct:.1f} %"


def fmt_ms(ms) -> str:
    """毫秒 → '242 ms'。"""
    if ms is None or ms != ms:
        return "—"
    return f"{int(round(ms))} ms"


def fmt_calories(kcal) -> str:
    if not kcal or kcal != kcal:
        return "—"
    return f"{int(round(kcal))} kcal"


def fmt_grade(pct) -> str:
    if pct is None or pct != pct:
        return "—"
    return f"{pct:+.1f}%"
