"""Leaflet 轨迹图。

绕开 NiceGUI leaflet 高层 API 的不确定性：头部加载 Leaflet，在固定高度 div 内用
ui.run_javascript 直接驱动原生 L 画轨迹。tile 用 CARTO dark 与深色主题一致。
"""
from __future__ import annotations

import json

from nicegui import ui

LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"


def ensure_leaflet() -> None:
    # 每个渲染了地图的页面都注入一次 Leaflet（ui.add_head_html 作用于当前页面）
    ui.add_head_html(f'<link rel="stylesheet" href="{LEAFLET_CSS}"/>')
    ui.add_head_html(f'<script src="{LEAFLET_JS}"></script>')


def render_route(latlons, height: int = 400, key: str = "route"):
    """渲染轨迹。latlons: [(lat, lon), ...]"""
    ensure_leaflet()
    pts = [[float(a), float(b)] for a, b in latlons if a is not None and b is not None]

    div_id = f"map_{key}"
    with ui.element("div").classes("map-wrap").style(f"height:{height}px"):
        if len(pts) < 2:
            ui.label("该活动无 GPS 轨迹").classes("map-empty")
            return
        ui.html(f'<div id="{div_id}" style="width:100%;height:100%"></div>')

    mid = pts[len(pts) // 2]
    template = """
    (function(){
      function init(){
        var el=document.getElementById('__DIV__');
        if(!el||typeof L==='undefined'){ setTimeout(init,80); return; }
        if(window.__maps&&window.__maps['__DIV__']){ try{window.__maps['__DIV__'].remove();}catch(e){} }
        var map=L.map(el,{zoomControl:true,attributionControl:true}).setView([__MIDLAT__,__MIDLON__],14);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
          {attribution:'&copy; OpenStreetMap &copy; CARTO', maxZoom:19, subdomains:'abcd'}).addTo(map);
        var pts=__POINTS__;
        var line=L.polyline(pts,{color:'#3987e5',weight:5,opacity:0.95,lineJoin:'round',lineCap:'round'}).addTo(map);
        L.circleMarker(pts[0],{radius:6,color:'#199e70',fillColor:'#199e70',fillOpacity:1,weight:2}).addTo(map);
        L.circleMarker(pts[pts.length-1],{radius:6,color:'#e66767',fillColor:'#e66767',fillOpacity:1,weight:2}).addTo(map);
        try{ map.fitBounds(line.getBounds(),{padding:[28,28]}); }catch(e){}
        window.__maps=window.__maps||{}; window.__maps['__DIV__']=map;
        setTimeout(function(){ map.invalidateSize(); }, 200);
      }
      setTimeout(init,60);
    })();
    """
    js = (template
          .replace("__DIV__", div_id)
          .replace("__MIDLAT__", repr(mid[0]))
          .replace("__MIDLON__", repr(mid[1]))
          .replace("__POINTS__", json.dumps(pts)))
    ui.run_javascript(js)
