"""Leaflet 轨迹图。

绕开 NiceGUI leaflet 高层 API 的不确定性：头部加载 Leaflet，在固定高度 div 内用
ui.run_javascript 直接驱动原生 L 画轨迹。tile 用 CARTO dark 与深色主题一致。
"""
from __future__ import annotations

import json

from nicegui import ui

# Leaflet 本地打包（static/leaflet/），避免 CDN 在受限网络下加载失败导致地图空白
LEAFLET_CSS = "/static/leaflet/leaflet.css"
LEAFLET_JS = "/static/leaflet/leaflet.js"


def ensure_leaflet() -> None:
    # 每个渲染了地图的页面都注入一次 Leaflet（ui.add_head_html 作用于当前页面）
    ui.add_head_html(f'<link rel="stylesheet" href="{LEAFLET_CSS}"/>')
    ui.add_head_html(f'<script src="{LEAFLET_JS}"></script>')


def render_route(latlons, height: int = 400, key: str = "route"):
    """渲染轨迹。latlons: [(lat, lon), ...]"""
    ensure_leaflet()
    pts = [[float(a), float(b)] for a, b in latlons if a is not None and b is not None]

    if len(pts) < 2:
        with ui.element("div").classes("map-wrap").style(f"height:{height}px"):
            ui.label("该活动无 GPS 轨迹").classes("map-empty")
        return

    # Leaflet 容器：直接用 NiceGUI element（DOM id = element.id），设明确像素高度。
    # 不用 ui.html——它默认会包一层 div，导致内部 height:100% 塌缩为 0，地图不渲染。
    container = ui.element("div").classes("map-wrap").style(f"width:100%;height:{height}px")
    div_id = str(container.id)

    mid = pts[len(pts) // 2]
    template = """
    (function(){
      var DIV=__DIV__;
      console.log('[route] init scheduled', DIV);
      function loadCss(){
        if(document.querySelector('link[data-leaflet-css]')) return;
        var l=document.createElement('link'); l.rel='stylesheet';
        l.href='/static/leaflet/leaflet.css'; l.setAttribute('data-leaflet-css','1');
        document.head.appendChild(l);
      }
      function loadJs(cb){
        if(typeof L!=='undefined'){ cb(); return; }
        var ex=document.querySelector('script[data-leaflet-js]');
        if(ex){ setTimeout(function(){loadJs(cb);},60); return; }
        console.log('[route] loading leaflet.js');
        var s=document.createElement('script'); s.src='/static/leaflet/leaflet.js';
        s.setAttribute('data-leaflet-js','1');
        s.onload=function(){ console.log('[route] leaflet.js loaded, L=',typeof L); cb(); };
        s.onerror=function(){ console.error('[route] leaflet.js FAILED',s.src); };
        document.head.appendChild(s);
      }
      function build(){
        var el=null;
        try{ if(typeof getHtmlElement==='function') el=getHtmlElement(DIV); }catch(e){}
        if(!el) el=document.getElementById('c'+DIV);
        if(!el) el=document.getElementById(String(DIV));
        console.log('[route] build el=', el? ('found ('+el.tagName+')') : 'NULL');
        if(!el){ setTimeout(build,80); return; }
        loadCss();
        loadJs(function(){
          if(typeof L==='undefined'){ console.error('[route] L undefined after load'); return; }
          if(window.__maps&&window.__maps[DIV]){ try{window.__maps[DIV].remove();}catch(e){} }
          var pts=__POINTS__;
          var map=L.map(el,{zoomControl:true,attributionControl:true}).setView([__MIDLAT__,__MIDLON__],14);
          L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            {attribution:'&copy; OpenStreetMap &copy; CARTO', maxZoom:19, subdomains:'abcd'}).addTo(map);
          var line=L.polyline(pts,{color:'#3987e5',weight:5,opacity:0.95,lineJoin:'round',lineCap:'round'}).addTo(map);
          L.circleMarker(pts[0],{radius:6,color:'#199e70',fillColor:'#199e70',fillOpacity:1,weight:2}).addTo(map);
          L.circleMarker(pts[pts.length-1],{radius:6,color:'#e66767',fillColor:'#e66767',fillOpacity:1,weight:2}).addTo(map);
          try{ map.fitBounds(line.getBounds(),{padding:[28,28]}); }catch(e){}
          window.__maps=window.__maps||{}; window.__maps[DIV]=map;
          setTimeout(function(){ map.invalidateSize(); },200);
          console.log('[route] map created', DIV);
        });
      }
      setTimeout(build,60);
    })();
    """
    js = (template
          .replace("__DIV__", div_id)
          .replace("__MIDLAT__", repr(mid[0]))
          .replace("__MIDLON__", repr(mid[1]))
          .replace("__POINTS__", json.dumps(pts)))
    ui.run_javascript(js)
