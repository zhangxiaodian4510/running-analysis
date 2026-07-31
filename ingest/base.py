"""归一化数据结构 + 小工具。所有解析器都产出这些对象。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Record:
    elapsed_s: float
    hr: Optional[float] = None
    cadence: Optional[float] = None
    speed_mps: Optional[float] = None
    distance_m: Optional[float] = None
    altitude_m: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    power: Optional[float] = None
    ts: Optional[datetime] = None  # 解析期临时用，不入库


@dataclass
class Lap:
    lap_index: int = 0
    start_time: Optional[str] = None
    duration_s: Optional[float] = None
    distance_m: Optional[float] = None
    avg_hr: Optional[float] = None
    max_hr: Optional[float] = None
    avg_speed_mps: Optional[float] = None
    calories: Optional[float] = None


@dataclass
class Activity:
    filename: str
    source: str  # fit | tcx | gpx
    sport: str = "running"
    start_time: str = ""  # ISO 本地
    duration_s: float = 0.0
    timer_s: Optional[float] = None
    distance_m: Optional[float] = None
    records: list = field(default_factory=list)  # list[Record]
    laps: list = field(default_factory=list)      # list[Lap]
    avg_speed_mps: Optional[float] = None
    max_speed_mps: Optional[float] = None
    avg_hr: Optional[float] = None
    max_hr: Optional[float] = None
    avg_cadence: Optional[float] = None
    avg_power: Optional[float] = None
    calories: Optional[float] = None
    ele_gain_m: Optional[float] = None
    ele_loss_m: Optional[float] = None
    avg_grade: Optional[float] = None


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def num(v) -> Optional[float]:
    """转 float；None / 非数 / 0-sentinel 返回 None。"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    # fitparse 常用 0xFFFF 或 0 作“无值”
    if f != f:  # NaN
        return None
    return f


def iso(dt: Optional[datetime]) -> str:
    """datetime → 本地 ISO 字符串。"""
    if dt is None:
        return ""
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt.isoformat(sep=" ", timespec="seconds")


def parse_dt(s: str) -> Optional[datetime]:
    """解析 TCX/GPX 时间字符串（带 Z）。"""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
