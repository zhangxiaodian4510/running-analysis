"""ECharts option 生成器（纯 dict，无 JS 函数 → 可安全 JSON 序列化）。

设计遵循 dataviz 规范：单一 y 轴（绝不双轴）、≥2 系列带 legend、crosshair+tooltip、
细标记、文字用 ink token 而非系列色。配速在图表中以「分钟/公里」(5.4 表示 5:24) 表示。
"""
from __future__ import annotations

import math

import numpy as np

from . import theme as T


def _ink_text():
    return {"color": T.INK2, "fontFamily": "system-ui, -apple-system, 'Segoe UI', sans-serif"}


def _axis_line():
    return {"lineStyle": {"color": T.GRID}, "axisLabel": {"color": T.MUTED},
            "splitLine": {"show": True, "lineStyle": {"color": T.GRID, "type": "dashed"}}}


def _pairs(x, y, max_n=1400):
    out = []
    for a, b in zip(x, y):
        try:
            fa, fb = float(a), float(b)
        except (TypeError, ValueError):
            continue
        if math.isfinite(fa) and math.isfinite(fb):
            out.append([fa, fb])
    if len(out) > max_n:
        step = int(np.ceil(len(out) / max_n))
        out = out[::step]
    return out


# --------------------------------------------------------------------------- #
# 周/月：距离柱状
# --------------------------------------------------------------------------- #
def weekly_distance_option(df, units: str = "metric") -> dict:
    if df is None or df.empty:
        return _empty("暂无数据")
    name = "里程 (km)" if units == "metric" else "里程 (mi)"
    vals = (df["distance_km"]).tolist() if units == "metric" else (df["distance_km"] * 0.621371).tolist()
    return {
        "backgroundColor": "transparent",
        "textStyle": _ink_text(),
        "grid": {"left": 40, "right": 16, "top": 20, "bottom": 28, "containLabel": True},
        "tooltip": {"trigger": "axis", "backgroundColor": T.SURFACE2, "borderColor": T.GRID,
                    "textStyle": {"color": T.INK}},
        "xAxis": {"type": "category", "data": df["label"].tolist(), **_axis_line()},
        "yAxis": {"type": "value", "name": name, "nameTextStyle": {"color": T.MUTED}, **_axis_line()},
        "series": [{
            "type": "bar", "name": name, "data": [round(v, 1) for v in vals],
            "barMaxWidth": 26,
            "itemStyle": {"color": T.BLUE, "borderRadius": [4, 4, 0, 0]},
            "emphasis": {"itemStyle": {"color": T.SERIES[4]}},
        }],
    }


# --------------------------------------------------------------------------- #
# 周：配速趋势 + 4 周滚动（2 系列）
# --------------------------------------------------------------------------- #
def pace_trend_option(df) -> dict:
    if df is None or df.empty or "pace_s_per_km" not in df.columns:
        return _empty("暂无数据")
    d = df.dropna(subset=["pace_s_per_km"])
    if d.empty:
        return _empty("暂无数据")
    avg_hr = d["avg_hr"].round(0).tolist()
    pace_min = (d["pace_s_per_km"] / 60.0).round(2).tolist()
    roll = (d.get("pace_rolling", d["pace_s_per_km"]) / 60.0).round(2).tolist()
    return {
        "backgroundColor": "transparent",
        "textStyle": _ink_text(),
        "legend": {
            "data": [
                "周配速",
                "4周均线",
                "平均心率"
            ],
            "textStyle": {
                "color": T.INK2
            },
            "top": 0
        },
        "grid": {"left": 40, "right": 16, "top": 36, "bottom": 28, "containLabel": True},
        "tooltip": {"trigger": "axis", "backgroundColor": T.SURFACE2, "borderColor": T.GRID,
                    "textStyle": {"color": T.INK}, ":formatter": _TREND_AXIS_TIP},
        "xAxis": {"type": "category", "boundaryGap": False, "data": d["label"].tolist(), **_axis_line()},

        "yAxis": [
            {
                "type": "value",
                "name": "配速 (min/km)",
                "nameTextStyle": {"color": T.MUTED},
                "scale": True,
                "inverse": True,
                **_axis_line()
            },
            {
                "type": "value",
                "name": "心率 (bpm)",
                "nameTextStyle": {"color": T.MUTED},
                "scale": True,
                "position": "right",
                **_axis_line()
            }
        ],

        "series": [
            {
                "name": "周配速",
                "type": "line",
                "smooth": True,
                "symbol": "circle",
                "symbolSize": 6,
                "yAxisIndex": 0,
                "data": pace_min,
                "lineStyle": {
                    "width": 2,
                    "color": T.BLUE
                },
                "itemStyle": {
                    "color": T.BLUE
                },
            },
            {
                "name": "4周均线",
                "type": "line",
                "smooth": True,
                "symbol": "none",
                "yAxisIndex": 0,
                "data": roll,
                "lineStyle": {
                    "width": 3,
                    "color": T.ORANGE,
                    "type": "dashed"
                },
                "itemStyle": {
                    "color": T.ORANGE
                },
            },
            {
                "name": "平均心率",
                "type": "line",
                "smooth": True,
                "symbol": "circle",
                "symbolSize": 6,
                "yAxisIndex": 1,
                "data": avg_hr,
                "lineStyle": {
                    "width": 2,
                    "color": T.GREEN
                },
                "itemStyle": {
                    "color": T.GREEN
                },
            }
        ]
    }


# --------------------------------------------------------------------------- #
# 长期：均心率 / 步频趋势（可选小图）
# --------------------------------------------------------------------------- #
def metric_trend_option(df, col: str, title: str, color: str, unit: str) -> dict:
    if df is None or df.empty or col not in df.columns:
        return _empty("暂无数据")
    d = df.dropna(subset=[col])
    if d.empty:
        return _empty("暂无数据")
    return {
        "backgroundColor": "transparent",
        "textStyle": _ink_text(),
        "grid": {"left": 70, "right": 20, "top": 40, "bottom": 32, "containLabel": True},  # top: 24→40, bottom: 28→32，加空间避免标题被遮挡
        "tooltip": {"trigger": "axis", "backgroundColor": T.SURFACE2, "borderColor": T.GRID,
                    "textStyle": {"color": T.INK}, ":formatter": _PACE_AXIS_TIP if col == "pace_s_per_km" else None},
        "xAxis": {"type": "category", "boundaryGap": False, "data": d["label"].tolist(), **_axis_line()},
        "yAxis": {"type": "value", "name": f"{title} ({unit})", "nameTextStyle": {"color": T.MUTED},
                  "scale": True, **_axis_line(),
                  # 配速轴：将小数分钟(如 5.5)格式化为 "5:30"
                  "axisLabel": {"color": T.MUTED, ":formatter": _PACE_FMT if col == "pace_s_per_km" else None},
        },
        "series": [{
            "type": "line", "smooth": True, "symbol": "none",
            "data": [round(float(v) / 60.0, 2) if "pace_s_per_km" in col and not pd.isna(v) else round(float(v), 1) for v in d[col].tolist()],
            "lineStyle": {"width": 2, "color": color},
            "areaStyle": {"color": color, "opacity": 0.12},
            "itemStyle": {"color": color},
        }],
    }


# --------------------------------------------------------------------------- #
# 详情：每项一张独立图，x 轴为时间（分钟），y 轴为对应数据
# --------------------------------------------------------------------------- #
def _pace_values(d):
    spd = d.get("speed_mps", pd_nans(d))
    return np.where(spd > 0, 1000.0 / (spd * 60.0), np.nan)


# 分钟(小数) → "m:ss"。走 NiceGUI 动态属性 :formatter（前端 convertDynamicProperties 转成 JS；
# 若转换失败则回退默认数值刻度，图仍能渲染）。
_MS_FMT = ("(v) => { v = Number(v) || 0; var m = Math.floor(v); var s = Math.round((v - m) * 60); if (s >= 60) { m += 1; s = s - 60; } return m + ':' + String(s).padStart(2, '0'); }")

# 专门用于配速轴的 formatter：数据已经是分钟（如 5.5），直接转 "m:ss"
_PACE_FMT = ("(v) => { v = Number(v) || 0; var m = Math.floor(v); var s = Math.round((v - m) * 60); if (s >= 60) { m += 1; s = s - 60; } return m + ':' + String(s).padStart(2, '0'); }")

# 配速轴 tooltip formatter（用于 axis trigger）：接收数组参数，格式化每个数据点的配速值
_TREND_AXIS_TIP = """
(p) => {
    if (!p || p.length === 0) {
        return '';
    }

    var result = [];

    // 日期
    result.push(p[0].axisValue);

    p.forEach(function(x) {

        if (x.seriesName === '周配速' || x.seriesName === '4周均线') {

            var v = Number(x.value) || 0;
            var m = Math.floor(v);
            var s = Math.round((v - m) * 60);

            if (s >= 60) {
                m += 1;
                s -= 60;
            }

            result.push(
                x.marker + x.seriesName + ': ' +
                m + ':' +
                String(s).padStart(2, '0') +
                ' min/km'
            );

        } else if (x.seriesName === '平均心率') {

            result.push(
                x.marker + x.seriesName + ': ' +
                Number(x.value).toFixed(0) +
                ' bpm'
            );

        } else {

            result.push(
                x.marker + x.seriesName + ': ' +
                x.value
            );
        }

    });

    return result.join('<br/>');
}
"""
# 时间轴 tooltip 头：把悬停点 x(分钟) 显示成 m:ss
_MS_TIP = ("(p) => { var v = p[0].value[0]; var m = Math.floor(v); var s = Math.round((v - m) * 60); if (s >= 60) { m += 1; s = 0; } return (m + ':' + String(s).padStart(2, '0')) + '<br/>' + p.map(function(x){ return x.marker + x.seriesName + ': ' + x.value[1]; }).join('<br/>'); }")


def _visible_axis_lines():
    """可见的轴线/刻度：默认 _axis_line() 的 GRID 色(#2c2c2a)在深色卡片(#222220)上几乎看不见。"""
    return {
        "axisLine": {"show": True, "lineStyle": {"color": T.BORDER}},
        "axisTick": {"show": True, "lineStyle": {"color": T.BORDER}},
        "splitLine": {"show": True, "lineStyle": {"color": "rgba(255,255,255,0.05)"}},
    }


def _time_series_option(recs_df, title: str, ylabel: str, color: str, value_fn, area: bool = False) -> dict:
    if recs_df is None or recs_df.empty:
        return _empty("无采样数据")
    t = (recs_df["elapsed_s"].astype(float) / 60.0).to_numpy()
    y = value_fn(recs_df)
    data = _pairs(t, y)
    if not data:
        return _empty("无数据")
    series = {
        "name": title, "type": "line", "data": data, "smooth": True, "showSymbol": False,
        "lineStyle": {"width": 2, "color": color}, "itemStyle": {"color": color},
    }
    if area:
        series["areaStyle"] = {"color": color, "opacity": 0.14}
    return {
        "backgroundColor": "transparent",
        "textStyle": _ink_text(),
        "grid": {"left": 50, "right": 20, "top": 18, "bottom": 30, "containLabel": True},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "line"},
                    "backgroundColor": T.SURFACE2, "borderColor": T.GRID, "textStyle": {"color": T.INK},
                    ":formatter": _MS_TIP},
        "xAxis": {**_visible_axis_lines(), "type": "value", "min": 0, "name": "时间",
                  "nameTextStyle": {"color": T.MUTED},
                  "axisLabel": {"color": T.MUTED, ":formatter": _MS_FMT}},
        "yAxis": {**_visible_axis_lines(), "type": "value", "name": ylabel, "scale": True,
                  "nameTextStyle": {"color": T.MUTED}, "axisLabel": {"color": T.MUTED}},
        "series": [series],
    }


def detail_series_options(recs_df) -> list:
    """返回 [(标题, option), ...]：配速 / 心率 / 海拔 / 步频，各一张独立图。"""
    return [
        ("配速 (min/km)", _time_series_option(
            recs_df, "配速", "配速 (min/km)", T.BLUE, _pace_values)),
        ("心率 (bpm)", _time_series_option(
            recs_df, "心率", "心率 (bpm)", T.RED, lambda d: d.get("hr", pd_nans(d)).to_numpy())),
        ("海拔 (m)", _time_series_option(
            recs_df, "海拔", "海拔 (m)", T.GREEN,
            lambda d: d.get("altitude_m", pd_nans(d)).to_numpy(), area=True)),
        ("步频 (spm)", _time_series_option(
            recs_df, "步频", "步频 (spm)", "#c98500",
            lambda d: d.get("cadence", pd_nans(d)).to_numpy())),
    ]


def pd_nans(d):
    import pandas as pd
    return pd.Series(np.nan, index=d.index)


# --------------------------------------------------------------------------- #
# 心率区间停留（水平条，顺序蓝）
# --------------------------------------------------------------------------- #
def hr_zones_option(zones: list[dict]) -> dict:
    if not zones:
        return _empty("无心率数据")
    names = [z["name"] for z in zones]
    minutes = [int(round(z["minutes"])) for z in zones]
    colors = [T.SEQ[3], T.SEQ[4], T.SEQ[5], T.SEQ[6], T.SEQ[7]]
    return {
        "backgroundColor": "transparent",
        "textStyle": _ink_text(),
        "grid": {"left": 16, "right": 40, "top": 16, "bottom": 16, "containLabel": True},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"},
                    "backgroundColor": T.SURFACE2, "borderColor": T.GRID, "textStyle": {"color": T.INK}},
        "xAxis": {"type": "value", "axisLabel": {"color": T.MUTED, "formatter": "{value} 分"},
                  "splitLine": {"lineStyle": {"color": T.GRID, "type": "dashed"}}},
        "yAxis": {"type": "category", "data": names, "axisLine": {"lineStyle": {"color": T.GRID}},
                  "axisLabel": {"color": T.INK2}},
        "series": [{
            "type": "bar", "data": [{"value": m, "itemStyle": {"color": colors[i % len(colors)]}}
                                    for i, m in enumerate(minutes)],
            "barMaxWidth": 22, "label": {"show": True, "position": "right", "color": T.INK2,
                                         "formatter": "{c} 分"},
        }],
    }


# --------------------------------------------------------------------------- #
# 1km 分圈配速（y 轴反向：越快越高）
# --------------------------------------------------------------------------- #
def splits_option(splits: list[dict]) -> dict:
    if not splits:
        return _empty("无分圈数据")
    labels = [f"{s['km']}K" for s in splits]
    vals = [round(float(s["pace"]) / 60.0, 2) if s.get("pace") else None for s in splits]
    return {
        "backgroundColor": "transparent",
        "textStyle": _ink_text(),
        "grid": {"left": 16, "right": 16, "top": 16, "bottom": 28, "containLabel": True},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"},
                    "backgroundColor": T.SURFACE2, "borderColor": T.GRID, "textStyle": {"color": T.INK}},
        "xAxis": {"type": "category", "data": labels, **_axis_line()},
        "yAxis": {"type": "value", "name": "配速 (min/km)", "inverse": True,
                  "nameTextStyle": {"color": T.MUTED}, "scale": True, **_axis_line()},
        "series": [{
            "type": "bar", "data": vals, "barMaxWidth": 30,
            "itemStyle": {"color": T.BLUE, "borderRadius": [4, 4, 0, 0]},
            "label": {"show": True, "position": "top", "color": T.INK2, "formatter": "{c}"},
        }],
    }


# --------------------------------------------------------------------------- #
# 日历热图（顺序蓝）
# --------------------------------------------------------------------------- #
def calendar_option(daily_df, theme="blue") -> dict:
    if daily_df is None or daily_df.empty:
        return _empty("暂无数据")
    data = [[row["date"], round(float(row["distance_km"]), 2)]
            for _, row in daily_df.iterrows()]
    dates = [r[0] for r in data]
    start = min(dates)
    end = max(dates)
    vmax = max([r[1] for r in data] + [10.0])

    # 颜色主题
    themes = {
        "blue": T.SEQ,
        "green": ["#d7f9d0", "#a6d9cd", "#8cc4b4", "#71afad", "#599a96", "#468a82", "#367a73", "#266c6e", "#165e60"],
        "orange": ["#fff2cc", "#ffd6cc", "#ffbaaf", "#ff9d8f", "#ff7f6f", "#ff6150", "#e54840", "#c93226", "#a71c0a"],
        "red": T.SERIES,  # 用 SERIES 色系
    }
    colors = themes.get(theme, T.SEQ)

    return {
        "backgroundColor": "transparent",
        "textStyle": _ink_text(),
        "tooltip": {"backgroundColor": T.SURFACE2, "borderColor": T.GRID, "textStyle": {"color": T.INK}},
        "visualMap": {
            "min": 0, "max": vmax, "calculable": True, "orient": "horizontal",
            "left": "center", "bottom": 6, "itemHeight": 160,
            "inRange": {"color": colors},
            "textStyle": {"color": T.MUTED},
            "text": ["多", "少"],
        },
        "calendar": {
            "top": 70, "left": 50, "right": 40, "bottom": 70,  # 加宽左右空间让年份显示完整
            "range": [start, end],
            "cellSize": ["auto", 13],
            "itemStyle": {"borderColor": T.SURFACE, "color": T.SURFACE2, "borderWidth": 2},
            "splitLine": {"show": False},
            "yearLabel": {"show": True, "color": T.INK2, "fontSize": 12},  # 加上 show 和 fontSize
            "monthLabel": {"color": T.INK2, "fontSize": 12},
            "dayLabel": {"color": T.MUTED, "fontSize": 10},
        },
        "series": [{"type": "heatmap", "coordinateSystem": "calendar", "data": data}],
    }


def _empty(msg: str = "暂无数据") -> dict:
    return {
        "backgroundColor": "transparent",
        "textStyle": _ink_text(),
        "title": {"text": msg, "left": "center", "top": "center", "textStyle": {"color": T.MUTED}},
    }
