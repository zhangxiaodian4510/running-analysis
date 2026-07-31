"""统计聚合：活动表、周月汇总、趋势、日历、1km 分圈。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core import db


# --------------------------------------------------------------------------- #
# 读取
# --------------------------------------------------------------------------- #
def activities_df() -> pd.DataFrame:
    df = db.query_df("SELECT * FROM activities ORDER BY start_time DESC")
    if df.empty:
        return df
    df["dt"] = pd.to_datetime(df["start_time"], errors="coerce")
    df["date"] = df["dt"].dt.date
    df["pace_s_per_km"] = df.apply(
        lambda r: (r["duration_s"] / (r["distance_m"] / 1000.0))
        if r["distance_m"]
        else np.nan,
        axis=1,
    )
    df["speed_kmh"] = (df["avg_speed_mps"] * 3.6).where(df["avg_speed_mps"].notna())
    return df


def records_df(activity_id: int) -> pd.DataFrame:
    return db.query_df(
        "SELECT * FROM records WHERE activity_id=? ORDER BY elapsed_s", (activity_id,)
    )


# --------------------------------------------------------------------------- #
# 汇总数字（KPI）
# --------------------------------------------------------------------------- #
def totals(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"distance_m": 0, "duration_s": 0, "count": 0, "avg_pace": None,
                "ele_gain_m": 0, "calories": 0}
    dist = float(df["distance_m"].sum())
    dur = float(df["duration_s"].sum())
    avg_pace = (dur / (dist / 1000.0)) if dist else None
    return {
        "distance_m": dist,
        "duration_s": dur,
        "count": int(len(df)),
        "avg_pace": avg_pace,
        "ele_gain_m": float(df["ele_gain_m"].fillna(0).sum()),
        "calories": float(df["calories"].fillna(0).sum()),
    }


def this_week_km(df: pd.DataFrame) -> float:
    if df is None or df.empty:
        return 0.0
    today = pd.Timestamp.now().normalize()
    start = today - pd.offsets.Day(today.weekday())  # 周一
    mask = (df["dt"] >= start) & (df["dt"] < start + pd.offsets.Week(1))
    return float(df.loc[mask, "distance_m"].fillna(0).sum() / 1000.0)


# --------------------------------------------------------------------------- #
# 周月聚合
# --------------------------------------------------------------------------- #
def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    s = df.dropna(subset=["dt"]).set_index("dt")
    g = s.resample(rule).agg(
        distance_m=("distance_m", "sum"),
        duration_s=("duration_s", "sum"),
        count=("id", "count"),
        ele_gain_m=("ele_gain_m", "sum"),
    )
    if "avg_hr" in s.columns:
        hr_time_sum = (
            s["avg_hr"] * s["duration_s"]
        ).resample(rule).sum()

        g["avg_hr"] = (
            hr_time_sum / g["duration_s"]
        )
    g = g[g["count"] > 0].copy()
    g["distance_km"] = g["distance_m"] / 1000.0
    g["duration_h"] = g["duration_s"] / 3600.0
    g["pace_s_per_km"] = g["duration_s"] / (g["distance_m"] / 1000.0)  # 配速：秒/公里（修复前是秒/米，数值大1000倍）
    g["speed_kmh"] = (g["distance_m"] / g["duration_s"] * 3.6).where(g["duration_s"] > 0)
    g["label"] = g.index.strftime("%m-%d" if rule.startswith("W") else "%Y-%m")
    return g.reset_index()


def weekly(df: pd.DataFrame) -> pd.DataFrame:
    return _resample(df, "W-MON")


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    return _resample(df, "MS")


def pace_trend(df: pd.DataFrame, window: int = 4) -> pd.DataFrame:
    """周维度配速趋势 + 滚动均值。用速度(km/h)的滚动均值更稳；这里返回配速与滚动配速。"""
    w = weekly(df)
    if w.empty:
        return w
    w = w.copy()
    w["pace_rolling"] = w["pace_s_per_km"].rolling(window=window, min_periods=1).mean()
    return w


# --------------------------------------------------------------------------- #
# 日历热图数据
# --------------------------------------------------------------------------- #
def calendar_daily(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "distance_km"])
    d = df.dropna(subset=["date"]).copy()
    d["distance_km"] = d["distance_m"].fillna(0) / 1000.0
    g = d.groupby("date").agg(distance_km=("distance_km", "sum")).reset_index()
    g["date"] = pd.to_datetime(g["date"]).dt.strftime("%Y-%m-%d")
    return g[["date", "distance_km"]]


# --------------------------------------------------------------------------- #
# records 派生（详情页用）
# --------------------------------------------------------------------------- #
def ensure_distance(df: pd.DataFrame) -> pd.DataFrame:
    """records 缺 distance_m 时，由经纬度累积（haversine）补全。"""
    if df is None or df.empty:
        return df
    if "distance_m" in df.columns and df["distance_m"].notna().any():
        return df
    lat = df["lat"].astype(float).to_numpy()
    lon = df["lon"].astype(float).to_numpy()
    R = 6371000.0
    dlat = np.radians(np.diff(lat))
    dlon = np.radians(np.diff(lon))
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat[:-1])) * np.cos(np.radians(lat[1:])) * np.sin(dlon / 2) ** 2
    seg = 2 * R * np.arcsin(np.sqrt(a))
    dist = np.concatenate([[0.0], np.cumsum(seg)])
    df = df.copy()
    df["distance_m"] = dist
    return df


def splits_km(df: pd.DataFrame) -> list[dict]:
    """records → 每 1km 分圈 {km, distance_m, duration_s, pace, avg_hr}。"""
    if df is None or df.empty:
        return []
    d = ensure_distance(df)
    d = d.dropna(subset=["distance_m"]).sort_values("elapsed_s")
    if d.empty:
        return []
    d = d.copy()
    d["km"] = (d["distance_m"] // 1000).astype(int)
    out = []
    for km, g in d.groupby("km"):
        if km < 0:
            continue
        dist = float(g["distance_m"].max() - g["distance_m"].min())
        dur = float(g["elapsed_s"].max() - g["elapsed_s"].min())
        pace = (dur / (dist / 1000.0)) if dist > 0 else None
        hr = g["hr"].mean() if "hr" in g else np.nan
        out.append(
            {
                "km": int(km) + 1,
                "distance_m": dist,
                "duration_s": dur,
                "pace": pace,
                "avg_hr": float(hr) if hr == hr else None,
            }
        )
    return out
