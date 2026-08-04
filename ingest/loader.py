"""按扩展名分发到解析器 → 落库（按 filename 去重）。"""
from __future__ import annotations

import os
from typing import Optional

from core import db
from .base import Activity
from . import derive


def _parse(path: str, filename: str, ext: str) -> Activity:
    # 延迟导入：缺失某依赖时只影响对应格式
    if ext == "fit":
        from . import fit_parser
        return fit_parser.parse(path, filename)
    if ext == "tcx":
        from . import tcx_parser
        return tcx_parser.parse(path, filename)
    if ext == "gpx":
        from . import gpx_parser
        return gpx_parser.parse(path, filename)
    raise ValueError(f"不支持的格式 .{ext}")


def import_file(path: str) -> dict:
    """导入单个文件。返回 {status, filename, message}。status: ok|skipped|error"""
    filename = os.path.basename(path)
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    if ext not in ("fit", "tcx", "gpx"):
        return {"status": "error", "filename": filename, "message": f"不支持的格式 .{ext}"}

    if db.filename_exists(filename):
        return {"status": "skipped", "filename": filename, "message": "已导入过"}

    try:
        act = _parse(path, filename, ext)
        derive.finalize(act)
        if not act.records:
            return {"status": "error", "filename": filename, "message": "文件内无轨迹/采样点"}

        aid = db.insert_activity(_activity_row(act))
        db.insert_records(aid, [_record_row(r) for r in act.records])
        db.insert_laps(aid, [_lap_row(l) for l in act.laps])

        km = (act.distance_m or 0) / 1000
        return {
            "status": "ok",
            "filename": filename,
            "message": f"{act.sport} · {km:.2f} km · {len(act.records)} 点",
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "filename": filename, "message": str(e)}


def import_path(p: str) -> list[dict]:
    """导入文件或目录（递归一层）。"""
    results: list[dict] = []
    if os.path.isdir(p):
        for fn in sorted(os.listdir(p)):
            fp = os.path.join(p, fn)
            if os.path.isfile(fp):
                results.append(import_file(fp))
    elif os.path.isfile(p):
        results.append(import_file(p))
    return results


def _activity_row(act: Activity) -> dict:
    return {
        "filename": act.filename,
        "source": act.source,
        "sport": act.sport,
        "start_time": act.start_time,
        "duration_s": act.duration_s,
        "timer_s": act.timer_s,
        "distance_m": act.distance_m,
        "avg_speed_mps": act.avg_speed_mps,
        "max_speed_mps": act.max_speed_mps,
        "avg_hr": act.avg_hr,
        "max_hr": act.max_hr,
        "avg_cadence": act.avg_cadence,
        "avg_stride_length": act.avg_stride_length,
        "avg_vertical_oscillation": act.avg_vertical_oscillation,
        "avg_stance_time": act.avg_stance_time,
        "avg_power": act.avg_power,
        "calories": act.calories,
        "ele_gain_m": act.ele_gain_m,
        "ele_loss_m": act.ele_loss_m,
        "avg_grade": act.avg_grade,
    }


def _record_row(r) -> dict:
    return {
        "elapsed_s": r.elapsed_s,
        "hr": r.hr,
        "cadence": r.cadence,
        "speed_mps": r.speed_mps,
        "distance_m": r.distance_m,
        "altitude_m": r.altitude_m,
        "lat": r.lat,
        "lon": r.lon,
        "power": r.power,
        "stride_length_m": r.stride_length_m,
        "vertical_oscillation_cm": r.vertical_oscillation_cm,
        "stance_time_ms": r.stance_time_ms,
    }


def _lap_row(l) -> dict:
    return {
        "lap_index": l.lap_index,
        "start_time": l.start_time,
        "duration_s": l.duration_s,
        "distance_m": l.distance_m,
        "avg_hr": l.avg_hr,
        "max_hr": l.max_hr,
        "avg_speed_mps": l.avg_speed_mps,
        "calories": l.calories,
    }
