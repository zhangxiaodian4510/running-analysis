"""主题：dataviz 校验过的调色板 + 深色仪表盘样式。"""
from __future__ import annotations

from nicegui import ui

# dataviz 校验调色板（暗色档；默认深色主题）
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
SEQ = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#1c5cab", "#184f95", "#104281"]
BLUE = "#3987e5"
ORANGE = "#d95926"
GREEN = "#199e70"
RED = "#e66767"

INK = "#ffffff"
INK2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
SURFACE = "#161615"
SURFACE2 = "#101010"
CARD = "#222220"
BORDER = "rgba(255,255,255,0.10)"

CSS = f"""
:root {{
  --ink:{INK}; --ink2:{INK2}; --muted:{MUTED};
  --surface:{SURFACE}; --card:{CARD}; --border:{BORDER}; --blue:{BLUE};
}}
body {{ background: radial-gradient(1200px 700px at 80% -10%, #1d2230 0%, {SURFACE} 55%) fixed; }}
.q-page, .nicegui-content {{ background: transparent; }}

/* 卡片 */
.q-card, .panel {{
  background: linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0)) , {CARD};
  border: 1px solid {BORDER};
  border-radius: 14px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.35);
}}
.q-card {{ padding: 4px; }}

/* 标题 */
.page-title {{ font-size: 1.5rem; font-weight: 700; color:{INK}; letter-spacing:.2px; }}
.page-sub {{ color:{MUTED}; font-size:.9rem; margin-top:2px; }}
.section-title {{ font-size:1rem; font-weight:600; color:{INK2}; letter-spacing:.3px; }}

/* 数字与文本 */
.num {{ font-variant-numeric: tabular-nums; }}
.muted {{ color:{MUTED}; }}

/* KPI / stat tile */
.stat-tile {{
  background: {CARD}; border:1px solid {BORDER}; border-radius:14px; padding:14px 16px;
  display:flex; flex-direction:column; gap:2px; min-width:140px;
  box-shadow: 0 8px 22px rgba(0,0,0,0.30);
}}
.stat-value {{ font-size:1.7rem; font-weight:800; color:{INK}; font-variant-numeric: tabular-nums; line-height:1.1; }}
.stat-label {{ font-size:.78rem; color:{MUTED}; text-transform:uppercase; letter-spacing:.08em; }}
.stat-sub {{ font-size:.78rem; color:{INK2}; }}

.kpi-row {{ display:flex; gap:14px; flex-wrap:wrap; }}
.dyn-cols {{ display:flex; gap:8px; }}
.dyn-cols > .stat-tile {{ flex:1 1 140px; min-width:0; }}

/* 地图容器 */
.map-wrap {{ border:1px solid {BORDER}; border-radius:14px; overflow:hidden; box-shadow:0 8px 22px rgba(0,0,0,.30); }}
.map-empty {{ color:{MUTED}; padding:24px; }}

/* 行/列间距 */
.row-gap {{ gap:14px; }}

/* 表格 */
.q-table__bottom {{ color:{MUTED}; }}
.nicegui-table thead th {{ color:{INK2}; font-weight:600; }}
.nicegui-table tbody td {{ color:{INK}; }}
.nicegui-table tbody tr:hover {{ background: rgba(57,135,229,0.10); cursor:pointer; }}

/* 按钮/选择 */
.q-btn, .q-field {{ border-radius:10px; }}

/* 滚动条 */
::-webkit-scrollbar {{ width:10px; height:10px; }}
::-webkit-scrollbar-thumb {{ background:#3a3a38; border-radius:8px; }}
::-webkit-scrollbar-track {{ background:transparent; }}
"""


def apply() -> None:
    """在页面内调用：注入样式与品牌色。"""
    ui.add_head_html(f"<style>{CSS}</style>")
    ui.colors(primary=BLUE, secondary=ORANGE, accent=GREEN, positive=GREEN, negative=RED)
