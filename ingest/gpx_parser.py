"""解析 .gpx（bonus）。依赖 gpxpy（延迟导入）。

GPX 通常只有 时间/经纬度/海拔；心率/步频缺失。
速度与累计距离由轨迹点推导。
"""
from __future__ import annotations

import math
from datetime import datetime

from .base import Activity, Record, iso, parse_dt


def _haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parse(path: str, filename: str) -> Activity:
    import gpxpy  # 延迟导入

    with open(path, encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    pts = []
    for track in gpx.tracks:
        for seg in track.segments:
            pts.extend(seg.points)

    records: list[Record] = []
    start_dt = None
    if pts:
        start_dt = pts[0].time

    cum = 0.0
    prev = None
    for p in pts:
        t = p.time
        if prev is not None:
            cum += _haversine(prev.latitude, prev.longitude, p.latitude, p.longitude)
        elapsed = 0.0
        speed = None
        if t is not None and start_dt is not None:
            elapsed = max(0.0, (t - start_dt).total_seconds())
            if prev is not None and prev.time is not None:
                dt = (t - prev.time).total_seconds()
                if dt > 0:
                    speed = _haversine(prev.latitude, prev.longitude, p.latitude, p.longitude) / dt
        records.append(
            Record(
                elapsed_s=elapsed, hr=None, cadence=None, speed_mps=speed,
                distance_m=cum, altitude_m=p.elevation, lat=p.latitude, lon=p.longitude,
            )
        )
        prev = p

    sport = "running"
    if gpx.tracks and gpx.tracks[0].type:
        sport = gpx.tracks[0].type.lower()

    return Activity(
        filename=filename,
        source="gpx",
        sport=sport,
        start_time=iso(start_dt or datetime.now()),
        duration_s=records[-1].elapsed_s if records else 0.0,
        records=records,
    )
