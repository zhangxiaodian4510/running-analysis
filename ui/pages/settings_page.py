"""设置页：单位、最大心率（用于心率区间）。"""
from __future__ import annotations

from nicegui import ui

from config import DEFAULT_HR_MAX, DEFAULT_UNITS
from core import settings
from ui.components import page_header


def render(nav):
    page_header("设置", "单位与个人参数（影响距离显示与心率区间）")

    with ui.card().classes("panel").style("max-width:520px"):
        units_sel = ui.select(
            options={
                "metric": "公制（km / min·km⁻¹）",
                "imperial": "英制（mi / min·mi⁻¹）",
            },
            value=settings.units(),
            label="单位",
        ).classes("w-full")

        hr_input = ui.number(
            value=settings.hr_max(),
            label="最大心率（bpm）",
            min=120, max=230,
        ).classes("w-full")

        def save():
            settings.set("units", units_sel.value or DEFAULT_UNITS)
            settings.set("hr_max", int(hr_input.value or DEFAULT_HR_MAX))
            ui.notify("已保存", type="positive")

        ui.button("保存", on_click=save).props("unelevated")

    ui.label("提示：配速在图表中以「分钟/公里」表示（如 5.4 = 5:24）；KPI 与表格显示为 5:24。").classes("muted")
