"""从 records 派生汇总字段（海拔升降、均速/均心率等），覆盖 Activity 的空值。"""
from __future__ import annotations

import numpy as np

from .base import Activity


def _smooth(x: np.ndarray, w: int) -> np.ndarray:
    if len(x) < w:
        return x
    kernel = np.ones(w) / w
    return np.convolve(x, kernel, mode="same")


def finalize(act: Activity) -> Activity:
    recs = [r for r in act.records if r.elapsed_s is not None]
    if not recs:
        return act
    recs.sort(key=lambda r: r.elapsed_s)
    act.records = recs

    elapsed = np.array([r.elapsed_s for r in recs], dtype=float)
    act.duration_s = float(elapsed[-1])
    if act.timer_s is None:
        act.timer_s = act.duration_s

    dists = [r.distance_m for r in recs if r.distance_m is not None]
    if dists:
        act.distance_m = float(dists[-1])

    speeds = np.array([r.speed_mps for r in recs if r.speed_mps is not None], dtype=float)
    if speeds.size:
        act.avg_speed_mps = float(np.mean(speeds))
        act.max_speed_mps = float(np.max(speeds))

    hrs = np.array([r.hr for r in recs if r.hr is not None], dtype=float)
    if hrs.size:
        act.avg_hr = float(np.mean(hrs))
        act.max_hr = float(np.max(hrs))

    cads = np.array([r.cadence for r in recs if r.cadence is not None], dtype=float)
    if cads.size:
        act.avg_cadence = float(np.mean(cads))

    strides = np.array([r.stride_length_m for r in recs if r.stride_length_m is not None], dtype=float)
    if strides.size:
        act.avg_stride_length = float(np.mean(strides))
    vos = np.array([r.vertical_oscillation_cm for r in recs if r.vertical_oscillation_cm is not None], dtype=float)
    if vos.size:
        act.avg_vertical_oscillation = float(np.mean(vos))
    stances = np.array([r.stance_time_ms for r in recs if r.stance_time_ms is not None], dtype=float)
    if stances.size:
        act.avg_stance_time = float(np.mean(stances))

    alts = np.array([r.altitude_m for r in recs if r.altitude_m is not None], dtype=float)
    if alts.size >= 2:
        sm = _smooth(alts, 15)
        d = np.diff(sm, prepend=sm[0])
        act.ele_gain_m = float(np.sum(d[d > 0]))
        act.ele_loss_m = float(-np.sum(d[d < 0]))
        if act.distance_m:
            act.avg_grade = act.ele_gain_m / act.distance_m * 100

    return act
