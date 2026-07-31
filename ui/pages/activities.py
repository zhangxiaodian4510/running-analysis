"""活动列表 + 顶部 KPI。"""
from __future__ import annotations

from analytics import statistics as S
from analytics import units as U
from core import settings
from ui import theme as T
from ui.components import page_header, section_title, stat_tile
from nicegui import ui


def render(nav):
    units = settings.units()
    df = S.activities_df()

    page_header("活动", f"共 {len(df)} 次记录")

    if df.empty:
        with ui.card().classes("panel"):
            ui.label("还没有任何活动。去「导入」页上传 .fit/.tcx/.gpx，或生成示例数据。")
            ui.button("去导入", on_click=lambda: nav.go("import"))
        return

    totals = S.totals(df)
    with ui.row().classes("kpi-row"):
        stat_tile("总里程", U.fmt_distance(totals["distance_m"], units), "累计", T.BLUE)
        stat_tile("总时长", U.fmt_duration(totals["duration_s"]), "运动时间", T.GREEN)
        stat_tile("活动数", str(totals["count"]), "次", T.ORANGE)
        stat_tile("平均配速", U.fmt_pace(totals["avg_pace"]), "min/km", T.SERIES[3])
        stat_tile("本周里程", f"{S.this_week_km(df):.1f} km", "本周", T.SERIES[2])

    section_title("活动记录")
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "id": int(r["id"]),
            "date": str(r["date"]),
            "sport": _sport(r["sport"]),
            "distance": U.fmt_distance(r["distance_m"], units),
            "duration": U.fmt_duration(r["duration_s"]),
            "pace": U.fmt_pace(r["pace_s_per_km"]),
            "avg_hr": U.fmt_int(r["avg_hr"]),
            "ele": U.fmt_int(r["ele_gain_m"], " m"),
        })

    columns = [
        {"name": "date", "label": "日期", "field": "date", "align": "left", "sortable": True},
        {"name": "sport", "label": "项目", "field": "sport", "align": "center"},
        {"name": "distance", "label": "距离", "field": "distance", "align": "right", "sortable": True},
        {"name": "duration", "label": "时长", "field": "duration", "align": "right"},
        {"name": "pace", "label": "配速", "field": "pace", "align": "right"},
        {"name": "avg_hr", "label": "均心率", "field": "avg_hr", "align": "right"},
        {"name": "ele", "label": "爬升", "field": "ele", "align": "right"},
    ]
    table = ui.table(columns=columns, rows=rows, row_key="id").classes("nicegui-table w-full")
    table.props("flat dense :rows-per-page-options=[15,25,50,0] wrap-cells")

    def on_click(e):
        args = e.args
        row = args[1] if isinstance(args, (list, tuple)) and len(args) > 1 else args
        if isinstance(row, dict):
            nav.go("detail", row.get("id"))

    table.on("row-click", on_click)


def _sport(s):
    return {"running": "跑步", "cycling": "骑行", "walking": "步行"}.get(str(s), str(s or "跑步"))
