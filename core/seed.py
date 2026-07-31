"""生成逼真的假跑步数据，让应用开箱即见完整界面。

无真实文件时调用 run() 写入约 90 天跑步活动（配速随时间提升 → 趋势图可见进步）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from config import DEFAULT_HR_MAX, DEFAULT_UNITS
from core import db, settings

N_DAYS = 120          # 时间跨度（天）
CENTER_LAT = 31.2304  # 轨迹中心
CENTER_LON = 121.4737


def _smooth(x: np.ndarray, w: int) -> np.ndarray:
    if len(x) < w:
        return x
    kernel = np.ones(w) / w
    return np.convolve(x, kernel, mode="same")


def _make_one(rng: np.random.Generator, day_index: int, n_days: int, start_dt: datetime):
    """返回 (records, summary, laps)。"""
    frac = day_index / n_days
    # 配速随天数提升：6:00 → 约 5:15（秒/公里）
    pace_sec = float(np.clip((360.0 - 45.0 * frac) + rng.normal(0, 8), 285, 420))
    distance_km = float(rng.uniform(4.5, 11.5))

    dt_step = 3  # 采样间隔（秒）
    duration_s = pace_sec * distance_km
    n = max(24, int(duration_s // dt_step))
    t = np.arange(n) * dt_step

    # 速度（m/s）带噪声
    base_speed = 1000.0 / pace_sec
    speed = np.clip(base_speed + rng.normal(0, 0.25, n), 0.8, 6.0)
    dist = np.cumsum(np.concatenate([[0.0], speed[:-1] * dt_step]))

    # 心率：热身上升 → 平台 → 末段略升
    avg_hr = int(rng.integers(148, 168))
    warmup = np.clip(t / 180.0, 0, 1)
    hr = 110 + (avg_hr - 110) * warmup + rng.normal(0, 3, n)
    fatigue = np.where(t > duration_s * 0.7, (t - duration_s * 0.7) / duration_s * 6, 0)
    hr = np.clip(hr + fatigue, 90, 195)

    # 海拔：起伏山路
    alt = 12 + 9 * np.sin(t / 700.0) + 5 * np.sin(t / 230.0 + 1) + rng.normal(0, 0.8, n)

    # 步频
    cad = np.clip(174 + rng.normal(0, 3, n), 150, 192)

    # 轨迹：以总距离为周长的一个环（首尾接近闭合）
    circumference = dist[-1] if dist[-1] > 0 else distance_km * 1000
    radius = max(circumference / (2 * np.pi), 200.0)
    angle = 2 * np.pi * (dist / max(circumference, 1)) + float(rng.uniform(0, 6.28))
    dlat = (radius / 111320.0) * np.cos(angle)
    dlon = (radius / (111320.0 * np.cos(np.radians(CENTER_LAT)))) * np.sin(angle)
    lat = CENTER_LAT + dlat + rng.normal(0, 0.00003, n)
    lon = CENTER_LON + dlon + rng.normal(0, 0.00003, n)

    records = [
        dict(
            elapsed_s=float(t[i]), hr=float(hr[i]), cadence=float(cad[i]),
            speed_mps=float(speed[i]), distance_m=float(dist[i]),
            altitude_m=float(alt[i]), lat=float(lat[i]), lon=float(lon[i]), power=None,
        )
        for i in range(n)
    ]

    # 汇总
    alt_s = _smooth(alt, 15)
    dalt = np.diff(alt_s, prepend=alt_s[0])
    ele_gain = float(dalt[dalt > 0].sum())
    ele_loss = float(-dalt[dalt < 0].sum())
    summary = dict(
        sport="running",
        source="seed",
        start_time=start_dt.isoformat(),
        duration_s=float(t[-1]),
        timer_s=float(t[-1]),
        distance_m=float(dist[-1]),
        avg_speed_mps=float(speed.mean()),
        max_speed_mps=float(speed.max()),
        avg_hr=float(hr.mean()),
        max_hr=float(hr.max()),
        avg_cadence=float(cad.mean()),
        avg_power=None,
        calories=float(distance_km * 62 * float(rng.uniform(0.9, 1.1))),
        ele_gain_m=ele_gain,
        ele_loss_m=ele_loss,
        avg_grade=(ele_gain / max(dist[-1], 1)) * 100,
    )

    # 每公里一圈
    laps = []
    full_km = int(dist[-1] // 1000)
    for k in range(full_km):
        laps.append(
            dict(
                lap_index=k, start_time=None, duration_s=float(pace_sec), distance_m=1000.0,
                avg_hr=float(avg_hr + rng.normal(0, 2)), max_hr=float(summary["max_hr"]),
                avg_speed_mps=float(base_speed), calories=62.0,
            )
        )
    return records, summary, laps


def run(force: bool = False) -> bool:
    """写入假数据。库非空且未 force 时跳过。返回是否实际写入。"""
    db.init_db()
    if db.activity_count() > 0 and not force:
        return False

    rng = np.random.default_rng(42)
    today = datetime.now().replace(hour=7, minute=15, second=0, microsecond=0)

    idx = 0
    next_run = 0.0
    day = 0
    while day < N_DAYS:
        if day >= next_run:
            start = today - timedelta(days=(N_DAYS - day)) + timedelta(
                minutes=int(rng.integers(-10, 45))
            )
            records, summary, laps = _make_one(rng, day, N_DAYS, start)
            summary["filename"] = f"seed_{idx:03d}"
            aid = db.insert_activity(summary)
            db.insert_records(aid, records)
            db.insert_laps(aid, laps)
            idx += 1
            next_run = day + float(rng.uniform(1.0, 2.3))
        day += 1

    settings.set("hr_max", str(DEFAULT_HR_MAX))
    settings.set("units", DEFAULT_UNITS)
    return True


def clear_seed() -> None:
    """删除所有 seed 数据（保留用户导入）。"""
    db.execute("DELETE FROM activities WHERE source='seed'")
