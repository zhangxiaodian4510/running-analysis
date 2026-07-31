"""统计：周/月距离与配速趋势 + 日历热图 + 长期趋势。"""
from __future__ import annotations

import pandas as pd
from nicegui import ui

from analytics import statistics as S
from core import settings
from ui import charts
from ui import theme as T
from ui.components import page_header, section_title


def render(nav):
    df = S.activities_df()
    page_header("统计与趋势", "周/月汇总、配速进步、训练日历")

    if df.empty:
        with ui.card().classes("panel"):
            ui.label("还没有数据。先在「导入」页添加活动或生成示例数据。")
        return

    state = {"mode": "week", "calendar_range": "3m","period_range": "3m" ,"calendar_theme": "blue"}  # 周月模式 + 日历时间范围 + 日历颜色主题

    @ui.refreshable
    def period_charts():
        # --- 1. 根据 period_range 过滤数据 ---
        range_code = state["period_range"]
        today = pd.Timestamp.now().normalize()
        if range_code == "1m":
            start = today - pd.offsets.DateOffset(months=1)
        elif range_code == "3m":
            start = today - pd.offsets.DateOffset(months=3)
        elif range_code == "6m":
            start = today - pd.offsets.DateOffset(months=6)
        elif range_code == "1y":
            start = today - pd.offsets.DateOffset(years=1)
        else:
            start = None  # 全部数据
        filtered_df = df.copy() if start is None else df[df["dt"] >= start]
        if state["mode"] == "week":
            dist_df = S.weekly(filtered_df)
            pace_df = S.pace_trend(filtered_df)  # 含 4 周滚动均线
        else:
            dist_df = S.monthly(filtered_df)
            pace_df = S.monthly(filtered_df)
        with ui.row().classes("w-full").style("align-items:stretch;gap:14px"):
            with ui.column().style("flex:1;gap:6px"):
                section_title("里程")
                ui.echart(charts.weekly_distance_option(dist_df, settings.units())).style("height:300px")
            with ui.column().style("flex:1;gap:6px"):
                section_title("配速趋势（数值越小越快）")
                ui.echart(charts.pace_trend_option(pace_df)).style("height:300px")

    @ui.refreshable
    def calendar_chart():
        # 根据选择的时间范围过滤数据
        range_code = state["calendar_range"]
        today = pd.Timestamp.now().normalize()
        if range_code == "1m":
            start = today - pd.offsets.DateOffset(months=1)
        elif range_code == "3m":
            start = today - pd.offsets.DateOffset(months=3)
        elif range_code == "6m":
            start = today - pd.offsets.DateOffset(months=6)
        elif range_code == "1y":
            start = today - pd.offsets.DateOffset(years=1)
        else:
            start = None  # 全部数据

        filtered = df.copy() if start is None else df[df["dt"] >= start]
        daily = S.calendar_daily(filtered)
        theme = state["calendar_theme"]
        ui.echart(charts.calendar_option(daily, theme)).style("height:240px")

    def on_mode(e):
        state["mode"] = e.value if hasattr(e, "value") else e
        period_charts.refresh()

    def on_period_range(e):
        state["period_range"] = e.value
        period_charts.refresh()

    def on_calendar_range(e):
        state["calendar_range"] = e.value
        calendar_chart.refresh()

    def on_calendar_theme(e):
        state["calendar_theme"] = e.value
        calendar_chart.refresh()

    ui.toggle({"week": "周", "month": "月"}, value=state["mode"], on_change=on_mode)
    # 时间范围选择器
    ui.select({
        "1m": "近一个月",
        "3m": "近三个月",
        "6m": "近半年",
        "1y": "近一年",
        "all": "全部"
    }, value=state["period_range"], on_change=on_period_range).props('dense outlined')
    period_charts()

    section_title("训练日历")
    with ui.row().style("gap:10px;align-items:center"):
        # 时间范围选择器
        ui.select({
            "1m": "近一个月",
            "3m": "近三个月",
            "6m": "近半年",
            "1y": "近一年",
            "all": "全部"
        }, value=state["calendar_range"], on_change=on_calendar_range).props('dense outlined')
        # 颜色主题选择器
        ui.select({
            "blue": "蓝色系",
            "green": "绿色系",
            "orange": "橙色系",
            "red": "红色系"
        }, value=state["calendar_theme"], on_change=on_calendar_theme).props('dense outlined')
    calendar_chart()

    section_title("长期趋势")
    wk = S.weekly(df)
    with ui.row().classes("w-full").style("align-items:stretch;gap:14px"):
        with ui.column().style("flex:1;gap:6px"):
            # 周均配速：按周聚合配速 (pace_s_per_km)
            pace_agg = _weekly_metric(df, "pace_s_per_km")
            ui.echart(charts.metric_trend_option(pace_agg, "value", "周均配速", T.BLUE, "min/km")).style("height:260px")
        with ui.column().style("flex:1;gap:6px"):
            # 周均心率：按周聚合活动均心率
            hr_agg = _weekly_metric(df, "avg_hr")
            ui.echart(charts.metric_trend_option(hr_agg, "value", "周均心率", T.RED, "bpm")).style("height:260px")


def _weekly_metric(df, col):
    import pandas as pd
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.dropna(subset=["dt", col]).copy()
    d[col] = d[col].astype(float)
    g = d.set_index("dt").resample("W-MON").agg(value=(col, "mean"), count=(col, "count"))
    g = g[g["count"] > 0].copy()
    g["label"] = g.index.strftime("%m-%d")
    return g.reset_index()
