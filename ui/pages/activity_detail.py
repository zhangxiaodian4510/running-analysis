"""单次活动详情：数字卡 + 地图 + 联动曲线 + 心率区间 + 分圈 + 分圈表。"""
from __future__ import annotations

import pandas as pd
from nicegui import ui

from analytics import hr_zones
from analytics import statistics as S
from analytics import units as U
from analytics.units import pace_from_duration_distance
from core import db, settings
from ui import charts
from ui import theme as T
from ui.components import page_header, section_title, stat_tile
from ui.map_view import render_route


def render(nav, activity_id):
    units = settings.units()
    act = db.query_one("SELECT * FROM activities WHERE id=?", (activity_id,))
    if not act:
        page_header("未找到活动")
        ui.button("返回", on_click=lambda: nav.go("activities"))
        return

    recs = S.records_df(activity_id)
    laps = db.query_all("SELECT * FROM laps WHERE activity_id=? ORDER BY lap_index", (activity_id,))

    dt = pd.to_datetime(act["start_time"])
    pace = pace_from_duration_distance(act["duration_s"], act["distance_m"])

    page_header(
        f"{dt.strftime('%Y-%m-%d %H:%M')} · {_sport(act['sport'])}",
        f"{U.fmt_distance(act['distance_m'], units)} · {U.fmt_duration(act['duration_s'])}",
    )
    ui.button("← 返回列表", on_click=lambda: nav.go("activities")).props("flat unelevated")

    # 顶部数字卡
    with ui.row().classes("kpi-row"):
        stat_tile("距离", U.fmt_distance(act["distance_m"], units), color=T.BLUE)
        stat_tile("时长", U.fmt_duration(act["duration_s"]), color=T.GREEN)
        stat_tile("平均配速", U.fmt_pace(pace), "min/km", T.ORANGE)
        stat_tile("均心率", U.fmt_int(act["avg_hr"], " bpm"), color=T.RED)
        stat_tile("最大心率", U.fmt_int(act["max_hr"], " bpm"))
        stat_tile("爬升", U.fmt_int(act["ele_gain_m"], " m"), color=T.SERIES[2])
        stat_tile("热量", U.fmt_calories(act["calories"]))

    # 地图
    if not recs.empty and recs["lat"].notna().any():
        section_title("轨迹")
        sub = recs.dropna(subset=["lat", "lon"])
        pts = list(zip(sub["lat"].tolist(), sub["lon"].tolist()))
        render_route(pts, height=420, key=f"act{activity_id}")

    # 各项独立曲线（横轴为时间，自上而下对齐）
    if not recs.empty:
        section_title("数据曲线（横轴为时间）")
        for title, opt in charts.detail_series_options(recs):
            # 1. 给 card 加上 w-full 类，确保卡片本身占据 100% 宽度
            with ui.card().classes("panel w-full").style("padding:8px 12px;margin-bottom:10px"):
                ui.label(title).classes("section-title").style("margin:2px 0 0 2px")
                # 2. 核心修改：增加 width:100%，让 ECharts 图表撑满卡片内部区域
                ui.echart(opt).style("width:100%; height:220px")

    # 跑步动力学：左平均卡（两列）+ 右散点图/曲线图（可切换，仅有数据时显示）
    dyn = charts.dynamics_scatter_options(recs)
    avg_stride = act["avg_stride_length"]
    avg_vo = act["avg_vertical_oscillation"]
    avg_stance = act["avg_stance_time"]

    if dyn or any(v is not None for v in (avg_stride, avg_vo, avg_stance)):
        section_title("跑步动力学")
        cad = act["avg_cadence"]
        ratio = (avg_vo / avg_stride) if (avg_vo and avg_stride) else None  # cm/m 即 %
        flight = (60000.0 / cad - avg_stance) if (cad and avg_stance) else None

        # 右侧图表面板：散点/曲线可切换。@ui.refreshable 让 toggle 只局部刷新这一张卡片，
        # 不重建整个页面。current_type 作为显式参数传入，切换时用新值 refresh。
        @ui.refreshable
        def dynamics_panel(current_type: str = "scatter"):
            current_dyn = charts.dynamics_scatter_options(recs, chart_type=current_type)
            if not current_dyn:
                ui.label("无跑步动力学采样数据").classes("muted")
                return
            with ui.card().classes("panel w-full").style("padding:10px 14px"):
                # 顶部工具栏：Tab 靠左，Toggle 靠右
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.tabs().props("dense") as tabs:
                        for label, _ in current_dyn:
                            ui.tab(label)

                    # 切换按钮：on_value_change 收到的就是新选中的值（'scatter' 或 'line'）
                    ui.toggle(
                        {"scatter": "散点", "line": "曲线"},
                        value=current_type,
                    ).props("dense mandatory toggle-color=primary flat text-color=grey-7").on_value_change(
                        lambda e: dynamics_panel.refresh(
                            e.value if isinstance(e.value, str) else str(e.value))
                    )

                # Tab 内容区
                with ui.tab_panels(tabs, value=current_dyn[0][0]).classes("w-full"):
                    for label, opt in current_dyn:
                        with ui.tab_panel(label):
                            ui.echart(opt).style("width:100%; height:340px")

        # 左右双栏：左平均卡（两列）+ 右可切换图表
        with ui.row().classes("w-full").style("align-items:stretch;gap:14px"):
            # 左：平均数据（两列：步频/步幅 · 振幅/比例 · 着地/腾空）
            with ui.column().style("flex:0 0 300px;gap:8px"):
                with ui.row().classes("w-full dyn-cols"):
                    stat_tile("步频", U.fmt_int(cad, " spm"), color="#c98500")
                    stat_tile("步幅", U.fmt_stride(avg_stride), color=T.SERIES[6])
                with ui.row().classes("w-full dyn-cols"):
                    stat_tile("垂直振幅", U.fmt_vertical_oscillation(avg_vo), color=T.SERIES[5])
                    stat_tile("垂直比例", U.fmt_ratio(ratio), color=T.SERIES[4])
                with ui.row().classes("w-full dyn-cols"):
                    stat_tile("着地时间", U.fmt_ms(avg_stance), color=T.SERIES[1])
                    stat_tile("腾空时间", U.fmt_ms(flight), color=T.SERIES[7])

            # 右：可切换的图表面板（只调用一次）
            with ui.column().style("flex:1;gap:6px;min-width:0"):
                dynamics_panel("scatter")

    # 心率区间 + 分圈
    has_zones = bool(recs["hr"].notna().any()) if not recs.empty else False
    has_splits = bool(recs["distance_m"].notna().any()) if not recs.empty else False
    if has_zones or has_splits:
        with ui.row().classes("w-full").style("align-items:stretch;gap:14px"):
            with ui.column().classes("col").style("flex:1;gap:6px"):
                if has_zones:
                    section_title("心率区间停留")
                    zones = hr_zones.zone_minutes(recs, settings.hr_max())
                    ui.echart(charts.hr_zones_option(zones)).style("height:280px")
            with ui.column().classes("col").style("flex:1;gap:6px"):
                if has_splits:
                    section_title("每公里配速")
                    splits = S.splits_km(recs)
                    ui.echart(charts.splits_option(splits)).style("height:280px")

    # 分圈表
    if laps:
        section_title("分圈")
        rows = [{
            "#": l["lap_index"] + 1,
            "距离": U.fmt_distance(l["distance_m"], units),
            "时长": U.fmt_duration(l["duration_s"]),
            "配速": U.fmt_pace(pace_from_duration_distance(l["duration_s"], l["distance_m"])),
            "均心率": U.fmt_int(l["avg_hr"]),
            "热量": U.fmt_calories(l["calories"]),
        } for l in laps]
        columns = [{"name": k, "label": k, "field": k, "align": "right"} for k in rows[0].keys()]
        columns[0]["align"] = "left"
        ui.table(columns=columns, rows=rows, row_key="#").classes("nicegui-table").props("flat dense")


def _sport(s):
    return {"running": "跑步", "cycling": "骑行", "walking": "步行"}.get(str(s), str(s or "跑步"))
