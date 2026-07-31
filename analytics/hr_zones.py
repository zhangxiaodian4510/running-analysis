"""心率区间（按 %HRmax 的 5 区）。"""
from __future__ import annotations

import numpy as np
import pandas as pd

# (名称, 下界%HRmax, 上界%HRmax)
ZONES = [
    ("Z1 恢复", 0.50, 0.60),
    ("Z2 有氧", 0.60, 0.70),
    ("Z3 节奏", 0.70, 0.80),
    ("Z4 阈值", 0.80, 0.90),
    ("Z5 无氧", 0.90, 1.01),
]


def zone_minutes(df: pd.DataFrame, hr_max: float) -> list[dict]:
    """records DataFrame → 每区停留分钟与占比。

    用相邻采样点的时间差为权重、两点心率均值为强度，归入对应区间。
    """
    if df is None or df.empty or not hr_max:
        return []
    d = df.dropna(subset=["hr"]).sort_values("elapsed_s")
    if d.empty:
        return []
    t = d["elapsed_s"].astype(float).to_numpy()
    hr = d["hr"].astype(float).to_numpy()
    dt = np.diff(t, prepend=t[0])           # 首点 dt=0
    mid = (hr + np.concatenate([[hr[0]], hr[:-1]])) / 2.0
    pct = mid / hr_max
    total = float(dt.sum()) or 1.0

    out = []
    for name, lo, hi in ZONES:
        mask = (pct >= lo) & (pct < hi)
        secs = float(dt[mask].sum())
        out.append(
            {
                "name": name,
                "lo": lo,
                "hi": hi,
                "minutes": secs / 60.0,
                "pct": secs / total * 100.0,
            }
        )
    return out
