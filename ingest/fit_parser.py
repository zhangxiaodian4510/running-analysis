"""解析 .fit（Garmin Flexible and Interoperable Data Transfer）。

依赖 fitparse（按需导入，缺失时仅影响 .fit 导入）。
position_lat/long 是 semicircles：度 = semicircles × 180 / 2^31。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .base import Activity, Lap, Record, iso, num

SEMICIRCLES = 180.0 / (2 ** 31)


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    """fitparse 返回的是 UTC naive 时间；这里打上 UTC tzinfo，交由 base.iso() 转为本地时间。"""
    if dt is None:
        return None
    if isinstance(dt, datetime) and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _record_dict(msg) -> dict:
    d = {}
    for f in msg:
        # f.name 可能重复（dev 字段），后值覆盖通常无碍
        d[f.name] = f.value
    return d


def _read_record(msg) -> Optional[Record]:
    d = _record_dict(msg)
    ts = _utc(d.get("timestamp"))
    lat = num(d.get("position_lat"))
    lon = num(d.get("position_long"))
    # 0 经纬度视为无效
    if lat == 0:
        lat = None
    if lon == 0:
        lon = None
    return Record(
        elapsed_s=0.0,
        ts=ts,
        hr=num(d.get("heart_rate")),
        cadence=num(d.get("cadence")),
        speed_mps=num(d.get("enhanced_speed")) or num(d.get("speed")),
        distance_m=num(d.get("distance")),
        altitude_m=num(d.get("enhanced_altitude")) or num(d.get("altitude")),
        lat=(lat * SEMICIRCLES) if lat is not None else None,
        lon=(lon * SEMICIRCLES) if lon is not None else None,
        power=num(d.get("power")),
    )


def _read_lap(msg) -> Optional[Lap]:
    d = _record_dict(msg)
    return Lap(
        lap_index=int(num(d.get("message_index")) or 0),
        start_time=iso(_utc(d.get("start_time"))),
        duration_s=num(d.get("total_elapsed_time")) or num(d.get("total_timer_time")),
        distance_m=num(d.get("total_distance")),
        avg_hr=num(d.get("avg_heart_rate")),
        max_hr=num(d.get("max_heart_rate")),
        avg_speed_mps=num(d.get("enhanced_avg_speed")) or num(d.get("avg_speed")),
        calories=num(d.get("total_calories")),
    )


def _sport_of(value) -> str:
    if value is None:
        return "running"
    s = str(value)
    # fitparse 有时返回 'running'，有时返回枚举名/数字
    return s.lower().split(".")[-1] if s else "running"


def parse(path: str, filename: str) -> Activity:
    from fitparse import FitFile  # 延迟导入

    fit = FitFile(path)
    records: list[Record] = []
    laps: list[Lap] = []
    session: dict = {}
    sport = "running"
    first_ts = None

    for msg in fit.get_messages():
        name = msg.name
        if name == "session":
            session = _record_dict(msg)
            if "sport" in session:
                sport = _sport_of(session.get("sport"))
        elif name == "sport":
            sp = _record_dict(msg).get("sport")
            if sp:
                sport = _sport_of(sp)
        elif name == "lap":
            lap = _read_lap(msg)
            if lap:
                laps.append(lap)
        elif name == "record":
            rec = _read_record(msg)
            if rec is not None:
                records.append(rec)
                if first_ts is None and rec.ts is not None:
                    first_ts = rec.ts

    # 计算 elapsed_s
    start_ts = first_ts or _utc(session.get("start_time"))
    for r in records:
        if r.ts is not None and start_ts is not None:
            r.elapsed_s = max(0.0, (r.ts - start_ts).total_seconds())
        r.ts = None

    start_time = iso(start_ts) or (iso(_utc(session.get("start_time"))) if session else "")

    act = Activity(
        filename=filename,
        source="fit",
        sport=sport,
        start_time=start_time,
        duration_s=0.0,
        records=records,
        laps=laps,
        # session 汇总（records 为空时兜底；非空时 derive 会覆盖为更准的值）
        timer_s=num(session.get("total_timer_time")) or num(session.get("total_elapsed_time")),
        distance_m=num(session.get("total_distance")),
        avg_speed_mps=num(session.get("enhanced_avg_speed")) or num(session.get("avg_speed")),
        max_speed_mps=num(session.get("enhanced_max_speed")) or num(session.get("max_speed")),
        avg_hr=num(session.get("avg_heart_rate")),
        max_hr=num(session.get("max_heart_rate")),
        avg_cadence=num(session.get("avg_running_cadence")) or num(session.get("avg_cadence")),
        avg_power=num(session.get("avg_power")),
        calories=num(session.get("total_calories")),
        ele_gain_m=num(session.get("total_ascent")),
        ele_loss_m=num(session.get("total_descent")),
    )
    return act
