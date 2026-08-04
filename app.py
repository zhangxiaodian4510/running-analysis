"""Runalyze 式跑步数据分析应用入口。

启动：python app.py  →  http://127.0.0.1:8080
首次启动库为空时自动生成示例数据。
"""
from __future__ import annotations

import os

from nicegui import app, ui

from config import APP_NAME, APP_SUBTITLE
from core import db, seed
from ui import theme
from ui.pages import activities, activity_detail, statistics as stats_page, import_page, settings_page
from ui.map_view import ensure_leaflet

# 客户端导航状态
NAV_ITEMS = [
    ("activities", "活动", "event"),
    ("statistics", "统计", "insights"),
    ("import", "导入", "upload"),
    ("settings", "设置", "settings"),
]


class Nav:
    def __init__(self):
        self.page = "activities"
        self.activity_id = None
        self.refresh = None

    def go(self, page: str, activity_id=None):
        self.page = page
        self.activity_id = activity_id
        if self.refresh:
            self.refresh()


nav = Nav()


@ui.refreshable
def content_area():
    if nav.page == "detail" and nav.activity_id is not None:
        activity_detail.render(nav, nav.activity_id)
    elif nav.page == "statistics":
        stats_page.render(nav)
    elif nav.page == "import":
        import_page.render(nav)
    elif nav.page == "settings":
        settings_page.render(nav)
    else:
        activities.render(nav)


nav.refresh = content_area.refresh

LAYOUT_CSS = """
.app-main { max-width: 1240px; margin: 0 auto; padding: 18px 22px 60px; width: 100%; }
.app-header { background: rgba(22,22,21,.82); backdrop-filter: blur(10px);
              border-bottom: 1px solid rgba(255,255,255,.08); }
.app-title { font-weight: 800; font-size: 1.12rem; letter-spacing: .3px; color: #fff; }
.app-drawer { background: rgba(20,20,19,.62); border-right: 1px solid rgba(255,255,255,.06); }
.brand { font-weight: 800; font-size: 1.25rem; color: #fff; padding: 4px 4px 14px; }
.nav-btn { justify-content: flex-start !important; text-transform: none !important;
           font-weight: 600; letter-spacing: .2px; }
.nav-btn.active { color: #3987e5; }
"""


@ui.page("/")
def main():
    theme.apply()
    ui.add_head_html(f"<style>{LAYOUT_CSS}</style>")
    ui.dark_mode(True)
    ensure_leaflet()  # 页面级加载本地 Leaflet，供详情页轨迹使用

    drawer = ui.left_drawer(bordered=True, value=True).classes("app-drawer")
    with drawer:
        with ui.column().style("gap:4px;padding:14px 10px"):
            ui.html(f'<div class="brand">🏃 {APP_NAME}</div>')
            for key, label, icon in NAV_ITEMS:
                ui.button(label, icon=icon, on_click=lambda k=key: nav.go(k)
                          ).props("flat align=left").classes("nav-btn w-full")

    with ui.header().classes("app-header"):
        ui.button(icon="menu", on_click=drawer.toggle).props("flat round dense color=white")
        ui.label(APP_NAME).classes("app-title")
        ui.space()
        ui.label(APP_SUBTITLE).classes("muted")

    with ui.column().classes("app-main"):
        content_area()


def _init() -> None:
    db.init_db()
    if db.activity_count() == 0:
        try:
            seed.run()
            print("[init] 已自动生成示例数据")
        except Exception as e:  # noqa: BLE001
            print(f"[init] 示例数据生成失败：{e}")


_init()

# 本地静态资源（Leaflet 等，避免依赖外部 CDN）
app.add_static_files("/static", "static")

ui.run(
    host=os.getenv("APP_HOST", "127.0.0.1"),
    port=int(os.getenv("APP_PORT", "8080")),
    title=APP_NAME,
    dark=True,
    reload=False,
    show=os.getenv("APP_SHOW", "1") == "1",
)
