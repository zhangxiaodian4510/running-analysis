#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Apple Health Export -> Runalyze FIT 转换器
==========================================
与 convert_to_tcx.py 同源、同效果, 输出 Garmin FIT 二进制格式。
复用 TCX 转换器的合并逻辑(GPS/海拔/速度/心率/步频/功率/步幅/振幅/触地),
用官方 garmin-fit-sdk 写出完整 Activity 文件。

用法:
  python convert_to_fit.py --sport Running --only-date 2023-08-09 --limit 1 --verbose
  python convert_to_fit.py            # 全量: 跑步+骑行
"""
import argparse
import csv
import os
from datetime import datetime, timezone

from garmin_fit_sdk import Encoder

import convert_to_tcx as C   # 复用: collect_workouts / collect_records / build_trackpoints

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
DEFAULT_EXPORT = "导出.xml"
DEFAULT_OUT = "fit_output"

# sport 内部名 -> (FIT sport枚举, sub_sport)
FIT_SPORT = {"Running": (1, 0), "Cycling": (2, 0)}   # 1=running 2=cycling, sub_sport 0=generic

MESG_FILE_ID, MESG_FILE_CREATOR, MESG_SPORT = 0, 49, 12
MESG_LAP, MESG_RECORD, MESG_SESSION, MESG_ACTIVITY = 19, 20, 18, 34

SEMIC = (2 ** 31) / 180.0   # 经纬度(度) -> semicircles


def semicircles(deg):
    return int(round(deg * SEMIC))


def dt_of(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def _avg(xs, rnd=None):
    if not xs:
        return None
    v = sum(xs) / len(xs)
    return round(v, rnd) if rnd is not None else v


def _maxv(xs):
    return max(xs) if xs else None


# --------------------------------------------------------------------------- #
# FIT 写出
# --------------------------------------------------------------------------- #
def write_fit(path, w, laps):
    """laps = [[tp,...],...] (来自 C.build_trackpoints)。写出 FIT 字节到 path。"""
    all_recs = [tp for seg in laps for tp in seg]
    if not all_recs:
        return 0

    # 在活动点上重算累计距离: build_trackpoints 的 dist 是按"全 GPX(含暂停期)"累加的,
    # 暂停时 GPS 漂移会虚增。这里逐段累加、跨段不加间隙(暂停期距离不增加),
    # 使 record.distance / lap / session 总距离三者一致, 并与 workout 实际距离吻合。
    cum = 0.0
    for seg in laps:
        prev = None
        for tp in seg:
            if prev is not None and tp["lat"] is not None and prev["lat"] is not None:
                cum += C.haversine(prev["lat"], prev["lon"], tp["lat"], tp["lon"])
            tp["dist"] = cum
            prev = tp
    wall_elapsed = all_recs[-1]["t"] - all_recs[0]["t"]

    sport, sub = FIT_SPORT[w["sport"]]
    is_run = w["sport"] == "Running"
    enc = Encoder()

    start_dt = dt_of(all_recs[0]["t"])
    end_dt = dt_of(all_recs[-1]["t"])

    # 1) file_id
    enc.write_mesg({"mesg_num": MESG_FILE_ID, "type": 4, "manufacturer": 1,
                    "time_created": end_dt, "product_name": "Apple Health Export"})
    # 2) file_creator
    enc.write_mesg({"mesg_num": MESG_FILE_CREATOR, "software_version": 2.1})
    # 3) sport
    enc.write_mesg({"mesg_num": MESG_SPORT, "sport": sport, "sub_sport": sub})

    # 4) records (全部, 时间顺序)
    for tp in all_recs:
        rec = {
            "mesg_num": MESG_RECORD,
            "timestamp": dt_of(tp["t"]),
            "position_lat": semicircles(tp["lat"]) if tp["lat"] is not None else None,
            "position_long": semicircles(tp["lon"]) if tp["lon"] is not None else None,
            "altitude": tp["ele"],
            "distance": tp["dist"],
            "speed": tp["speed"],
            "heart_rate": tp["hr"],
            "cadence": tp["cadence"],
            "power": tp["power"],
        }
        if is_run:
            rec["step_length"] = round(tp["stride"] * 1000) if tp["stride"] else None      # m -> mm
            rec["vertical_oscillation"] = round(tp["vo"] * 10) if tp["vo"] else None       # cm -> mm
            rec["stance_time"] = tp["gct"]                                                # ms
        enc.write_mesg(rec)

    # 5) laps (每段一个)
    total_elapsed = 0.0
    total_ascent = 0
    for i, seg in enumerate(laps):
        first, last = seg[0], seg[-1]
        elapsed = last["t"] - first["t"]
        dist = (last["dist"] or 0.0) - (first["dist"] or 0.0)
        if dist < 0:
            dist = 0.0
        speeds = [r["speed"] for r in seg if r["speed"] is not None]
        hrs = [r["hr"] for r in seg if r["hr"]]
        cads = [r["cadence"] for r in seg if r["cadence"]]
        pws = [r["power"] for r in seg if r["power"]]
        asc = 0.0
        prev_e = None
        for r in seg:
            if r["ele"] is not None:
                if prev_e is not None and r["ele"] > prev_e:
                    asc += r["ele"] - prev_e
                prev_e = r["ele"]
        total_ascent += int(asc)
        cal = None
        if w["total_kcal"]:
            cal = int(w["total_kcal"] * elapsed / max(last["t"] - laps[0][0]["t"], 1))
        enc.write_mesg({
            "mesg_num": MESG_LAP, "message_index": i,
            "timestamp": dt_of(last["t"]), "start_time": dt_of(first["t"]),
            "total_elapsed_time": elapsed, "total_timer_time": elapsed,
            "total_distance": dist, "total_calories": cal,
            "avg_speed": round(_avg(speeds), 3) if speeds else None,
            "max_speed": round(_maxv(speeds), 3) if speeds else None,
            "avg_heart_rate": round(_avg(hrs)) if hrs else None,
            "max_heart_rate": _maxv(hrs),
            "avg_cadence": round(_avg(cads)) if cads else None,
            "max_cadence": _maxv(cads),
            "avg_power": round(_avg(pws)) if pws else None,
            "max_power": _maxv(pws),
            "total_ascent": int(asc),
            "sport": sport, "sub_sport": sub,
        })
        total_elapsed += elapsed

    # 6) session (整次汇总)
    g_speeds = [r["speed"] for r in all_recs if r["speed"] is not None]
    g_hrs = [r["hr"] for r in all_recs if r["hr"]]
    g_cads = [r["cadence"] for r in all_recs if r["cadence"]]
    g_pws = [r["power"] for r in all_recs if r["power"]]
    sess = {
        "mesg_num": MESG_SESSION, "timestamp": end_dt, "start_time": start_dt,
        "sport": sport, "sub_sport": sub,
        "total_elapsed_time": wall_elapsed, "total_timer_time": total_elapsed,
        "total_distance": (all_recs[-1]["dist"] or 0.0),
        "total_calories": int(w["total_kcal"]) if w["total_kcal"] else None,
        "total_ascent": total_ascent,
        "avg_speed": round(_avg(g_speeds), 3) if g_speeds else None,
        "max_speed": round(_maxv(g_speeds), 3) if g_speeds else None,
        "avg_heart_rate": round(_avg(g_hrs)) if g_hrs else None,
        "max_heart_rate": _maxv(g_hrs),
        "avg_cadence": round(_avg(g_cads)) if g_cads else None,
        "max_cadence": _maxv(g_cads),
        "avg_power": round(_avg(g_pws)) if g_pws else None,
        "max_power": _maxv(g_pws),
        "num_laps": len(laps),
    }
    if is_run:
        g_strd = [r["stride"] for r in all_recs if r["stride"]]
        g_vo = [r["vo"] for r in all_recs if r["vo"]]
        g_gct = [r["gct"] for r in all_recs if r["gct"]]
        if g_strd:
            sess["avg_step_length"] = round(_avg(g_strd) * 1000)        # m -> mm
        if g_vo:
            sess["avg_vertical_oscillation"] = round(_avg(g_vo) * 10)   # cm -> mm
        if g_gct:
            sess["avg_stance_time"] = round(_avg(g_gct))               # ms
    enc.write_mesg(sess)

    # 7) activity
    enc.write_mesg({"mesg_num": MESG_ACTIVITY, "timestamp": end_dt,
                    "total_timer_time": total_elapsed, "num_sessions": 1})

    data = enc.close()
    with open(path, "wb") as f:
        f.write(data)
    return len(all_recs)


# --------------------------------------------------------------------------- #
# 主流程 (与 convert_to_tcx 一致的过滤/报告)
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Apple Health Export -> Runalyze FIT")
    ap.add_argument("--export", default=DEFAULT_EXPORT)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--sport", choices=["Running", "Cycling", "both"], default="both")
    ap.add_argument("--only-date", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print(">> Pass 1: 收集 Workout ...", flush=True)
    workouts = C.collect_workouts(args.export)
    print("   Workout 总数: %d (Running+Cycling)" % len(workouts), flush=True)

    print(">> Pass 2: 流式解析 Record 并分桶 ...", flush=True)
    C.collect_records(args.export, workouts)

    sel = workouts
    if args.sport != "both":
        sel = [w for w in sel if w["sport"] == args.sport]
    if args.only_date:
        sel = [w for w in sel if datetime.fromtimestamp(w["start"]).strftime("%Y-%m-%d")
               == args.only_date]
    if args.limit:
        sel = sel[:args.limit]
    print(">> 待转换: %d 个运动" % len(sel), flush=True)

    report = []
    seen = set()
    ok = fail = 0
    for idx, w in enumerate(sel, 1):
        try:
            laps = C.build_trackpoints(w)
            n_pts = sum(len(s) for s in laps)
            n_hr = sum(1 for s in laps for p in s if p["hr"])
            n_cad = sum(1 for s in laps for p in s if p["cadence"])
            if not laps or n_pts == 0:
                status, fname = "skip_nodata", ""
                fail += 1
            else:
                dt = datetime.fromtimestamp(w["start"])
                base = "%s_%s" % (dt.strftime("%Y-%m-%d_%H%M"), w["sport"].lower())
                if base not in seen:
                    fname, seen = base + ".fit", seen | {base}
                else:
                    c = 2
                    while "%s_%d.fit" % (base, c) in seen:
                        c += 1
                    fname = "%s_%d.fit" % (base, c)
                    seen.add(fname)
                write_fit(os.path.join(args.out, fname), w, laps)
                ok += 1
                status = "ok"
            if args.verbose or idx <= 3 or idx % 50 == 0 or status != "ok":
                print("  [%4d/%d] %s %-8s %.2fkm %4.0fmin  pts=%d hr=%d cad=%d  %s" % (
                    idx, len(sel),
                    datetime.fromtimestamp(w["start"]).strftime("%Y-%m-%d %H:%M"),
                    w["sport"], (w["total_dist_m"] or 0) / 1000.0,
                    w["duration_s"] / 60.0, n_pts, n_hr, n_cad, status), flush=True)
            report.append({"date": datetime.fromtimestamp(w["start"]).strftime("%Y-%m-%d %H:%M"),
                           "sport": w["sport"],
                           "distance_km": "%.3f" % ((w["total_dist_m"] or 0) / 1000.0),
                           "duration_min": "%.1f" % (w["duration_s"] / 60.0),
                           "trackpoints": n_pts, "hr_points": n_hr, "cadence_points": n_cad,
                           "output": fname, "status": status})
        except Exception as e:
            fail += 1
            print("  [ERROR] %s: %s" % (w["sport"], e), flush=True)
            report.append({"date": "", "sport": w["sport"], "distance_km": "",
                           "duration_min": "", "trackpoints": 0, "hr_points": 0,
                           "cadence_points": 0, "output": "", "status": "error:%s" % e})

    rp = os.path.join(args.out, "_conversion_report.csv")
    with open(rp, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=["date", "sport", "distance_km", "duration_min",
                                           "trackpoints", "hr_points", "cadence_points",
                                           "output", "status"])
        wr.writeheader()
        wr.writerows(report)
    print(">> 报告: %s" % rp, flush=True)
    print(">> 完成: ok=%d fail=%d (共 %d)" % (ok, fail, len(sel)), flush=True)


if __name__ == "__main__":
    main()
