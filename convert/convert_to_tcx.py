#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Apple Health Export -> Runalyze TCX 转换器
=========================================
把 Apple Health 导出包里的运动数据合并成 Runalyze 可导入的 TCX 文件。

三股未同步的数据流按时间戳合并到 1Hz 轨迹上:
  1) workout-routes/*.gpx     -> GPS 经纬度 / 海拔 / 1Hz 速度 (骨架)
  2) 导出.xml  <Workout>      -> 类型 / 时长 / 总距离 / 卡路里 / 暂停恢复事件
  3) 导出.xml  <Record>       -> 心率 / 跑步速度 / 步幅 / 功率 / 垂直振幅 / 触地时间

用法:
  python convert_to_tcx.py --sport Running --only-date 2023-08-09 --limit 1 --verbose
  python convert_to_tcx.py            # 全量: 跑步+骑行
"""
import argparse
import bisect
import csv
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

import xml.etree.ElementTree as ET
from lxml import etree

# --------------------------------------------------------------------------- #
# 常量与映射
# --------------------------------------------------------------------------- #
DEFAULT_EXPORT = "导出.xml"
DEFAULT_ROUTES = "workout-routes"
DEFAULT_OUT = "tcx_output"

# HealthKit Record type -> 内部通道名
HK = {
    "HKQuantityTypeIdentifierHeartRate": "hr",
    "HKQuantityTypeIdentifierRunningSpeed": "rspeed",
    "HKQuantityTypeIdentifierRunningStrideLength": "stride",
    "HKQuantityTypeIdentifierRunningPower": "power",
    "HKQuantityTypeIdentifierRunningVerticalOscillation": "vo",
    "HKQuantityTypeIdentifierRunningGroundContactTime": "gct",
    "HKQuantityTypeIdentifierStepCount": "step",
    "HKQuantityTypeIdentifierDistanceWalkingRunning": "dist_wr",
    "HKQuantityTypeIdentifierDistanceCycling": "dist_cyc",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "energy",
}

# workoutActivityType -> (内部sport, TCX Sport)
SPORT_MAP = {
    "HKWorkoutActivityTypeRunning": ("Running", "Running"),
    "HKWorkoutActivityTypeCycling": ("Cycling", "Biking"),
}

# 容差(秒)
TOL_HR = 12          # 心率最近匹配
TOL_HR_CARRY = 60    # 心率向前沿用最大间隔(填补短间隔, 长间隔保持缺省以免误导)
TOL_POWER = 15       # 功率最近匹配
TOL_BUCKET = 60      # 分桶型指标缺失时找最近桶的容差
CADENCE_MIN_SPEED = 0.7  # m/s, 低于此速视为非跑步(停止/起步), 步频置空

# TCX 命名空间
NS_TCX = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
NS_EXT = "http://www.garmin.com/xmlschemas/ActivityExtension/v2"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NSMAP = {None: NS_TCX, "xsi": NS_XSI, "ax": NS_EXT}


# --------------------------------------------------------------------------- #
# 时间工具
# --------------------------------------------------------------------------- #
def parse_ts(s):
    """解析 '+0800' 或 '...Z' 时间串 -> UTC epoch(秒)。失败返回 None。"""
    if not s:
        return None
    s = s.strip()
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # 兜底: 去掉时区冒号
        try:
            dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def epoch_to_tcx(t):
    """epoch(秒) -> 'YYYY-MM-DDTHH:MM:SSZ'"""
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def local(tag):
    """去掉命名空间: '{ns}trkpt' -> 'trkpt'"""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


# --------------------------------------------------------------------------- #
# Pass 1: 收集所有 Workout(仅 Running/Cycling)
# --------------------------------------------------------------------------- #
def collect_workouts(export_path):
    workouts = []
    ctx = etree.iterparse(export_path, events=("end",), tag=("Workout",), recover=True)
    for _, elem in ctx:
        wtype = elem.get("workoutActivityType", "")
        mapped = SPORT_MAP.get(wtype)
        if not mapped:
            elem.clear()
            continue
        sport, _ = mapped
        start = parse_ts(elem.get("startDate"))
        end = parse_ts(elem.get("endDate"))
        duration = float(elem.get("duration") or 0.0)  # 单位 min
        if start is None or end is None:
            elem.clear()
            continue

        w = {
            "sport": sport,
            "start": start,
            "end": end,
            "duration_s": duration * 60.0,
            "total_dist_m": None,
            "total_kcal": None,
            "avg_hr": None,
            "max_hr": None,
            "route_file": None,
            "events": [],          # [(type, epoch)]
            "channels": defaultdict(list),
        }

        # 子节点: MetadataEntry / WorkoutEvent / WorkoutStatistics / WorkoutRoute
        for child in elem:
            ln = local(child.tag)
            if ln == "WorkoutRoute":
                for sub in child:
                    if local(sub.tag) == "FileReference":
                        p = sub.get("path", "")
                        w["route_file"] = p.lstrip("/")
            elif ln == "WorkoutEvent":
                etype = child.get("type", "")
                edate = parse_ts(child.get("date"))
                if etype and edate is not None:
                    w["events"].append((etype, edate))
            elif ln == "WorkoutStatistics":
                stype = child.get("type", "")
                avg = child.get("average")
                mx = child.get("maximum")
                ssum = child.get("sum")
                unit = child.get("unit", "")
                if stype == "HKQuantityTypeIdentifierDistanceWalkingRunning" and ssum:
                    w["total_dist_m"] = float(ssum) * 1000.0 if "km" in unit else float(ssum)
                elif stype == "HKQuantityTypeIdentifierDistanceCycling" and ssum:
                    w["total_dist_m"] = float(ssum) * 1000.0 if "km" in unit else float(ssum)
                elif stype == "HKQuantityTypeIdentifierHeartRate":
                    if avg:
                        w["avg_hr"] = float(avg)
                    if mx:
                        w["max_hr"] = float(mx)
                elif stype == "HKQuantityTypeIdentifierActiveEnergyBurned" and ssum:
                    # unit kcal
                    try:
                        w["total_kcal"] = float(ssum)
                    except ValueError:
                        pass
            elif ln == "MetadataEntry":
                key = child.get("key", "")
                val = child.get("value", "")
                if key == "HKElevationAscended":
                    m = re.search(r"([\d.]+)", val)
                    if m:
                        w["elev_gain_m"] = float(m.group(1))
        workouts.append(w)
        elem.clear()
    workouts.sort(key=lambda x: x["start"])
    return workouts


# --------------------------------------------------------------------------- #
# 把一条 Record 归入所属 Workout
# --------------------------------------------------------------------------- #
def assign_record(workouts, starts, rtype, rstart, rend, value):
    chan = HK.get(rtype)
    if chan is None or rstart is None:
        return
    rend = rend if rend is not None else rstart
    # 二分: 找 start <= rstart 的最后一个 workout
    i = bisect.bisect_right(starts, rstart) - 1
    # 检查候选(重叠: rec 与 workout 区间相交)
    for j in (i, i + 1):
        if 0 <= j < len(workouts):
            w = workouts[j]
            if rstart <= w["end"] and rend >= w["start"]:
                if chan in ("hr", "power"):
                    w["channels"][chan].append((rstart, value))         # 瞬时: 点列表
                else:
                    w["channels"][chan].append((rstart, rend, value))   # 分桶: 区间列表
                return


def collect_records(export_path, workouts):
    """Pass 2: 流式解析 Record, 仅保留落入 workout 窗口的。"""
    starts = [w["start"] for w in workouts]
    ctx = etree.iterparse(export_path, events=("end",), tag=("Record",), recover=True)
    n = 0
    for _, elem in ctx:
        rtype = elem.get("type", "")
        if rtype not in HK:
            elem.clear()
            continue
        rstart = parse_ts(elem.get("startDate"))
        rend = parse_ts(elem.get("endDate"))
        val = elem.get("value")
        try:
            val = float(val)
        except (TypeError, ValueError):
            elem.clear()
            continue
        assign_record(workouts, starts, rtype, rstart, rend, val)
        n += 1
        elem.clear()
    # 排序各通道
    for w in workouts:
        for ch, lst in w["channels"].items():
            if ch in ("hr", "power"):
                lst.sort(key=lambda x: x[0])
            else:
                lst.sort(key=lambda x: x[0])
    return n


# --------------------------------------------------------------------------- #
# GPX 读取
# --------------------------------------------------------------------------- #
def read_gpx(path):
    """返回 [{t, lat, lon, ele, speed}], 按 t 升序。失败返回 []。"""
    pts = []
    try:
        for _, elem in ET.iterparse(path, events=("end",)):
            if local(elem.tag) != "trkpt":
                # 注意: 不能 clear 掉 ele/time/speed 等子节点——它们的 'end' 先于
                # 父 trkpt 触发,提前 clear 会让 trkpt.iter() 读到空文本。
                continue
            try:
                lat = float(elem.get("lat"))
                lon = float(elem.get("lon"))
            except (TypeError, ValueError):
                continue
            ele = speed = t = None
            for c in elem.iter():
                ln = local(c.tag)
                if ln == "ele" and c.text:
                    try:
                        ele = float(c.text)
                    except ValueError:
                        pass
                elif ln == "time" and c.text:
                    t = parse_ts(c.text)
                elif ln == "speed" and c.text:
                    try:
                        speed = float(c.text)
                    except ValueError:
                        pass
            elem.clear()  # 读完子节点后再清,释放内存
            if t is not None:
                pts.append({"t": t, "lat": lat, "lon": lon, "ele": ele, "speed": speed})
    except (ET.ParseError, FileNotFoundError, OSError):
        return []
    pts.sort(key=lambda p: p["t"])
    return pts


# --------------------------------------------------------------------------- #
# 合并辅助: 在通道上取值
# --------------------------------------------------------------------------- #
def nearest_point(points, t, tol):
    """points=[(epoch,val)] -> tol 内最近的 val, 否则 None。"""
    if not points:
        return None
    ts = [p[0] for p in points]
    i = bisect.bisect_left(ts, t)
    best = None
    bestd = tol + 1
    for j in (i - 1, i):
        if 0 <= j < len(points):
            d = abs(points[j][0] - t)
            if d <= tol and d < bestd:
                bestd, best = d, points[j][1]
    return best


def covering_bucket(buckets, t, tol):
    """buckets=[(start,end,val)] -> 覆盖 t 的桶 val, 否则 tol 内最近。"""
    if not buckets:
        return None
    starts = [b[0] for b in buckets]
    i = bisect.bisect_right(starts, t) - 1
    # 覆盖匹配
    for j in (i, i + 1, i - 1):
        if 0 <= j < len(buckets):
            s, e, v = buckets[j]
            if s <= t <= e:
                return v
    # 容差内最近
    best = None
    bestd = tol + 1
    for j in (i, i + 1, i - 1):
        if 0 <= j < len(buckets):
            s, e, v = buckets[j]
            d = min(abs(s - t), abs(e - t))
            if d <= tol and d < bestd:
                bestd, best = d, v
    return best


# --------------------------------------------------------------------------- #
# 构建轨迹点(合并)
# --------------------------------------------------------------------------- #
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def build_trackpoints(w):
    """合并 GPX + 各通道 -> 带 lap 分段的轨迹点列表。
    返回: laps = [ [tp,...], ... ], 每个 tp 为合并后的点 dict。"""
    ch = w["channels"]
    is_run = w["sport"] == "Running"

    gpx = []
    if w["route_file"] and os.path.exists(w["route_file"]):
        gpx = read_gpx(w["route_file"])

    # 无 GPS: 退化为心率时间线(室内跑步机等)
    if not gpx:
        hrs = sorted(ch["hr"], key=lambda x: x[0])
        pts = []
        for t, bpm in hrs:
            if w["start"] <= t <= w["end"]:
                pts.append({"t": t, "lat": None, "lon": None, "ele": None,
                            "speed": None, "hr": int(bpm) if bpm else None,
                            "cadence": None, "power": None,
                            "stride": None, "vo": None, "gct": None, "dist": 0.0})
        return [pts] if pts else []

    # 有 GPS: 以 1Hz 轨迹为骨架
    hr_pts = ch["hr"]
    rspeed = ch["rspeed"]
    stride = ch["stride"]
    power_pts = ch["power"]
    vo = ch["vo"]
    gct = ch["gct"]

    last_hr, last_hr_t = None, None
    merged = []
    cum = 0.0
    prev = None
    for p in gpx:
        t = p["t"]
        # 心率: 最近 -> 向前沿用
        bpm = nearest_point(hr_pts, t, TOL_HR)
        if bpm is None and last_hr is not None and (t - last_hr_t) <= TOL_HR_CARRY:
            bpm = last_hr
        if bpm is not None:
            last_hr, last_hr_t = bpm, t

        pw = nearest_point(power_pts, t, TOL_POWER)

        spd_kmh = covering_bucket(rspeed, t, TOL_BUCKET)   # 跑步速度 km/h
        strd = covering_bucket(stride, t, TOL_BUCKET)       # 步幅 m

        # 步频(跑步): 由速度桶+步幅桶推导(平滑,≈Apple报告值);
        # 但仅在真正运动时(GPS速度达标)才有值, 停止/起步瞬间为 None
        cadence = None
        moving = p["speed"] is None or p["speed"] >= CADENCE_MIN_SPEED
        if is_run and moving and spd_kmh and strd and strd > 0.05:
            cadence = (spd_kmh * 1000.0 / 60.0) / strd

        # TCX 速度 m/s: 优先 GPX 1Hz
        spd_ms = p["speed"]
        if (spd_ms is None or spd_ms <= 0.0) and spd_kmh:
            spd_ms = spd_kmh / 3.6

        # 累计距离
        if prev is not None:
            cum += haversine(prev["lat"], prev["lon"], p["lat"], p["lon"])

        merged.append({
            "t": t, "lat": p["lat"], "lon": p["lon"], "ele": p["ele"],
            "speed": spd_ms, "hr": int(round(bpm)) if bpm else None,
            "cadence": int(round(cadence)) if cadence else None,
            "power": int(round(pw)) if pw else None,
            "stride": strd, "vo": covering_bucket(vo, t, TOL_BUCKET),
            "gct": covering_bucket(gct, t, TOL_BUCKET),
            "dist": cum,
        })
        prev = p

    # Lap 分段: 按 Pause/Resume 切出"活动区间", 跳过暂停期
    return split_laps(w, merged)


def split_laps(w, merged):
    """根据 pause/resume 事件把 merged 切成活动区间(每段一个 lap)。"""
    events = [(t, et) for et, t in w["events"]]
    pauses = sorted(t for t, et in events if et == "HKWorkoutEventTypePause")
    resumes = sorted(t for t, et in events if et == "HKWorkoutEventTypeResume")

    if not pauses:
        return [merged] if merged else []

    # 活动区间: [start, pause1], [resume1, pause2], ...
    intervals = []
    cursor = w["start"]
    for p in pauses:
        if p > cursor:
            intervals.append((cursor, p))
        # 找对应 resume
        nxt = next((r for r in resumes if r >= p), None)
        if nxt is None:
            cursor = None
            break
        cursor = nxt
    if cursor is not None:
        intervals.append((cursor, w["end"]))
    if not intervals:
        return [merged] if merged else []

    laps = []
    for a, b in intervals:
        seg = [tp for tp in merged if a <= tp["t"] <= b]
        if seg:
            laps.append(seg)
    return laps or ([merged] if merged else [])


# --------------------------------------------------------------------------- #
# TCX 写出
# --------------------------------------------------------------------------- #
def _sub(parent, tag, text=None, ns=NS_TCX):
    e = etree.SubElement(parent, "{%s}%s" % (ns, tag))
    if text is not None:
        e.text = str(text)
    return e


def write_tcx(path, w, laps):
    root = etree.Element("{%s}TrainingCenterDatabase" % NS_TCX, nsmap=NSMAP)
    root.set("{%s}schemaLocation" % NS_XSI,
             "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 "
             "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2/trainingcenterdatabasev2.xsd")
    activities = _sub(root, "Activities")
    _, tcx_sport = SPORT_MAP["HKWorkoutActivityType" + w["sport"]]
    activity = _sub(activities, "Activity")
    activity.set("Sport", tcx_sport)
    _sub(activity, "Id", epoch_to_tcx(w["start"]))

    total_dist = 0.0
    total_dur = 0.0
    all_hr = []
    for seg in laps:
        first, last = seg[0], seg[-1]
        lap_dur = last["t"] - first["t"]
        # 段距离: 段内累计差
        lap_dist = last["dist"] - first["dist"]
        if lap_dist < 0:
            lap_dist = 0.0
        seg_hr = [p["hr"] for p in seg if p["hr"]]
        all_hr.extend(seg_hr)

        lap = _sub(activity, "Lap")
        lap.set("StartTime", epoch_to_tcx(first["t"]))
        _sub(lap, "TotalTimeSeconds", "%.1f" % max(lap_dur, 0.0))
        _sub(lap, "DistanceMeters", "%.2f" % lap_dist)
        if w["total_kcal"]:
            _sub(lap, "Calories", "%.0f" % (w["total_kcal"] / max(len(laps), 1)))
        if seg_hr:
            avg = _sub(lap, "AverageHeartRateBpm")
            _sub(avg, "Value", "%.0f" % (sum(seg_hr) / len(seg_hr)))
            mx = _sub(lap, "MaximumHeartRateBpm")
            _sub(mx, "Value", "%d" % max(seg_hr))
        # 段摘要扩展(步频/速度)
        cads = [p["cadence"] for p in seg if p["cadence"]]
        spds = [p["speed"] for p in seg if p["speed"] is not None]
        ext = _sub(lap, "Extensions")
        tpx = _sub(ext, "TPX", ns=NS_EXT)
        if spds:
            _sub(tpx, "AvgSpeed", "%.3f" % (sum(spds) / len(spds)), ns=NS_EXT)
        if cads:
            _sub(tpx, "AvgRunCadence", "%.0f" % (sum(cads) / len(cads)), ns=NS_EXT)

        track = _sub(lap, "Track")
        for tp in seg:
            trk = _sub(track, "Trackpoint")
            _sub(trk, "Time", epoch_to_tcx(tp["t"]))
            if tp["lat"] is not None and tp["lon"] is not None:
                pos = _sub(trk, "Position")
                _sub(pos, "LatitudeDegrees", "%.7f" % tp["lat"])
                _sub(pos, "LongitudeDegrees", "%.7f" % tp["lon"])
            if tp["ele"] is not None:
                _sub(trk, "AltitudeMeters", "%.2f" % tp["ele"])
            if tp["dist"] is not None:
                _sub(trk, "DistanceMeters", "%.2f" % tp["dist"])
            if tp["hr"]:
                hrb = _sub(trk, "HeartRateBpm")
                _sub(hrb, "Value", "%d" % tp["hr"])
            if tp["cadence"]:
                _sub(trk, "Cadence", "%d" % tp["cadence"])
            # 扩展: 速度/功率/步频 + 自定义保留项
            if any(tp.get(k) is not None for k in
                   ("speed", "power", "cadence", "stride", "vo", "gct")):
                ex = _sub(trk, "Extensions")
                tpx2 = _sub(ex, "TPX", ns=NS_EXT)
                if tp["speed"] is not None:
                    _sub(tpx2, "Speed", "%.3f" % tp["speed"], ns=NS_EXT)
                if tp["power"]:
                    _sub(tpx2, "Watts", "%d" % tp["power"], ns=NS_EXT)
                if tp["cadence"]:
                    _sub(tpx2, "RunCadence", "%d" % tp["cadence"], ns=NS_EXT)
                # 自定义命名空间保留高级跑步指标
                for name, key, fmt in (("StrideLength", "stride", "%.3f"),
                                       ("VerticalOscillation", "vo", "%.2f"),
                                       ("GroundContactTime", "gct", "%.0f")):
                    if tp[key] is not None:
                        _sub(tpx2, name, fmt % tp[key], ns=NS_EXT)

        total_dist += lap_dist
        total_dur += lap_dur

    tree = etree.ElementTree(root)
    tree.write(path, xml_declaration=True, encoding="utf-8", pretty_print=False)
    return total_dist, total_dur, all_hr


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Apple Health Export -> Runalyze TCX")
    ap.add_argument("--export", default=DEFAULT_EXPORT)
    ap.add_argument("--routes", default=DEFAULT_ROUTES)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--sport", choices=["Running", "Cycling", "both"], default="both")
    ap.add_argument("--only-date", default=None, help="仅处理该日期 YYYY-MM-DD")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="只解析统计,不写文件")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print(">> Pass 1: 收集 Workout ...", flush=True)
    workouts = collect_workouts(args.export)
    print("   Workout 总数: %d (Running+Cycling)" % len(workouts), flush=True)

    print(">> Pass 2: 流式解析 Record 并分桶 ...", flush=True)
    nrec = collect_records(args.export, workouts)
    print("   已分桶 Record: %d" % nrec, flush=True)

    # 过滤
    sel = workouts
    if args.sport != "both":
        sel = [w for w in sel if w["sport"] == args.sport]
    if args.only_date:
        sel = [w for w in sel if datetime.fromtimestamp(w["start"], tz=timezone.utc)
               .strftime("%Y-%m-%d") == args.only_date
               or datetime.fromtimestamp(w["start"]).strftime("%Y-%m-%d") == args.only_date]
    if args.limit:
        sel = sel[:args.limit]

    print(">> 待转换: %d 个运动" % len(sel), flush=True)

    report = []
    seen_names = set()
    ok = fail = 0
    for idx, w in enumerate(sel, 1):
        try:
            laps = build_trackpoints(w)
            n_pts = sum(len(s) for s in laps)
            n_hr = sum(1 for s in laps for p in s if p["hr"])
            n_cad = sum(1 for s in laps for p in s if p["cadence"])
            status = "ok"
            fname = None
            if not laps or n_pts == 0:
                status = "skip_nodata"
                fail += 1
            elif args.dry_run:
                ok += 1
            else:
                dt = datetime.fromtimestamp(w["start"])
                base = "%s_%s" % (dt.strftime("%Y-%m-%d_%H%M"), w["sport"].lower())
                if base not in seen_names:
                    fname = base + ".tcx"
                    seen_names.add(base)
                else:
                    c = 2
                    while True:
                        cand = "%s_%d.tcx" % (base, c)
                        if cand not in seen_names:
                            fname = cand
                            seen_names.add(cand)
                            break
                        c += 1
                fpath = os.path.join(args.out, fname)
                write_tcx(fpath, w, laps)  # 重跑覆盖同名(幂等)
                ok += 1
                # 内置校验: 解析回读
                etree.fromstring(open(fpath, "rb").read())

            if args.verbose or idx <= 3 or idx % 50 == 0 or status != "ok":
                dist_km = (w["total_dist_m"] or 0) / 1000.0
                print("  [%4d/%d] %s %-8s %.2fkm %4.0fmin  pts=%d hr=%d cad=%d  %s"
                      % (idx, len(sel),
                         datetime.fromtimestamp(w["start"]).strftime("%Y-%m-%d %H:%M"),
                         w["sport"], dist_km, w["duration_s"] / 60.0,
                         n_pts, n_hr, n_cad, status), flush=True)

            report.append({
                "date": datetime.fromtimestamp(w["start"]).strftime("%Y-%m-%d %H:%M"),
                "sport": w["sport"],
                "distance_km": "%.3f" % ((w["total_dist_m"] or 0) / 1000.0),
                "duration_min": "%.1f" % (w["duration_s"] / 60.0),
                "trackpoints": n_pts,
                "hr_points": n_hr,
                "cadence_points": n_cad,
                "output": fname or "",
                "status": status,
            })
        except Exception as e:
            fail += 1
            print("  [ERROR] %s %s: %s" % (w["sport"], w["start"], e), flush=True)
            report.append({"date": "", "sport": w["sport"], "distance_km": "",
                           "duration_min": "", "trackpoints": 0, "hr_points": 0,
                           "cadence_points": 0, "output": "", "status": "error:%s" % e})

    # 报告
    if not args.dry_run:
        rp = os.path.join(args.out, "_conversion_report.csv")
        with open(rp, "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=["date", "sport", "distance_km",
                                               "duration_min", "trackpoints",
                                               "hr_points", "cadence_points",
                                               "output", "status"])
            wr.writeheader()
            wr.writerows(report)
        print(">> 报告: %s" % rp, flush=True)

    print(">> 完成: ok=%d fail=%d (共 %d)" % (ok, fail, len(sel)), flush=True)


if __name__ == "__main__":
    main()
