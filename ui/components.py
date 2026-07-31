"""可复用 UI 组件。"""
from __future__ import annotations

from typing import Optional

from nicegui import ui


def stat_tile(label: str, value: str, sub: Optional[str] = None, color: Optional[str] = None):
    with ui.element("div").classes("stat-tile"):
        if color:
            ui.html(f'<div style="height:4px;width:36px;border-radius:3px;background:{color};margin-bottom:8px"></div>')
        ui.label(value).classes("stat-value num")
        ui.label(label).classes("stat-label")
        if sub:
            ui.label(sub).classes("stat-sub")


def page_header(title: str, subtitle: str = ""):
    with ui.column().classes("w-full").style("gap:2px;margin-bottom:6px"):
        ui.label(title).classes("page-title")
        if subtitle:
            ui.label(subtitle).classes("page-sub")


def section_title(text: str):
    ui.label(text).classes("section-title")


def panel(classes: str = ""):
    return ui.card().classes(f"panel {classes}".strip())
