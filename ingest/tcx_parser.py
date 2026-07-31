"""解析 .tcx（Garmin Training Center XML）。依赖 lxml（延迟导入）。

结构：TrainingCenterDatabase > Activities > Activity[Sport] > Id
      > Lap[StartTime] > (TotalTimeSeconds, DistanceMeters, ...,
                          AverageHeartRateBpm/Value, Track > Trackpoint* )
Trackpoint: Time, Position{Lat,Lon}, AltitudeMeters, DistanceMeters,
            HeartRateBpm/Value, Extensions > TPX{Speed, RunCadence}
"""
from __future__ import annotations

from typing import Optional

from .base import Activity, Lap, Record, iso, num, parse_dt

NS = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
TPX = "http://www.garmin.com/xmlschemas/ActivityExtension/v2"


def _q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _text(parent, path: str) -> Optional[str]:
    if parent is None:
        return None
    el = parent.find(path)
    return el.text.strip() if el is not None and el.text else None


def parse(path: str, filename: str) -> Activity:
    from lxml import etree  # 延迟导入

    tree = etree.parse(path)
    root = tree.getroot()
    activity_el = root.find(f".//{_q('Activity')}")
    if activity_el is None:
        raise ValueError("未找到 Activity 节点")

    sport_raw = activity_el.get("Sport", "running") or "running"
    sport = sport_raw.lower()

    id_el = activity_el.find(_q("Id"))
    start_dt = parse_dt(_text(activity_el, _q("Id")) or "") if id_el is not None else None

    records: list[Record] = []
    laps: list[Lap] = []

    for li, lap_el in enumerate(activity_el.findall(_q("Lap"))):
        lap_start = parse_dt(lap_el.get("StartTime") or "")
        laps.append(
            Lap(
                lap_index=li,
                start_time=iso(lap_start),
                duration_s=num(_text(lap_el, _q("TotalTimeSeconds"))),
                distance_m=num(_text(lap_el, _q("DistanceMeters"))),
                avg_hr=num(_text(lap_el.find(_q("AverageHeartRateBpm")), _q("Value")))
                if lap_el.find(_q("AverageHeartRateBpm")) is not None else None,
                max_hr=num(_text(lap_el.find(_q("MaximumHeartRateBpm")), _q("Value")))
                if lap_el.find(_q("MaximumHeartRateBpm")) is not None else None,
                avg_speed_mps=None,  # 末尾由距离/时长计算
                calories=num(_text(lap_el, _q("Calories"))),
            )
        )

        for tp in lap_el.findall(f".//{_q('Trackpoint')}"):
            t = parse_dt(_text(tp, _q("Time")) or "")
            pos = tp.find(_q("Position"))
            lat = lon = None
            if pos is not None:
                lat = num(_text(pos, _q("LatitudeDegrees")))
                lon = num(_text(pos, _q("LongitudeDegrees")))
            hr = None
            hrel = tp.find(_q("HeartRateBpm"))
            if hrel is not None:
                hr = num(_text(hrel, _q("Value")))
            speed = cadence = None
            ext = tp.find(_q("Extensions"))
            if ext is not None:
                tpx_el = ext.find(f"{{{TPX}}}TPX")
                if tpx_el is not None:
                    speed = num(_text(tpx_el, f"{{{TPX}}}Speed"))
                    cadence = num(_text(tpx_el, f"{{{TPX}}}RunCadence"))
            # 也可能直接有 Cadence 节点
            if cadence is None:
                cadence = num(_text(tp, _q("Cadence")))

            elapsed = 0.0
            if t is not None and start_dt is not None:
                elapsed = max(0.0, (t - start_dt).total_seconds())
            records.append(
                Record(
                    elapsed_s=elapsed, hr=hr, cadence=cadence, speed_mps=speed,
                    distance_m=num(_text(tp, _q("DistanceMeters"))),
                    altitude_m=num(_text(tp, _q("AltitudeMeters"))),
                    lat=lat, lon=lon,
                )
            )

    # 由距离/时长计算每圈均速
    for lap in laps:
        if lap.duration_s and lap.distance_m:
            lap.avg_speed_mps = lap.distance_m / lap.duration_s

    return Activity(
        filename=filename,
        source="tcx",
        sport=sport,
        start_time=iso(start_dt),
        duration_s=records[-1].elapsed_s if records else 0.0,
        records=records,
        laps=laps,
    )
