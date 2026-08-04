from __future__ import annotations

import json
from nicegui import ui

LEAFLET_CSS = "/static/leaflet/leaflet.css"
LEAFLET_JS = "/static/leaflet/leaflet.js"


def ensure_leaflet() -> None:
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

    container = ui.element("div").classes("map-wrap").style(f"width:100%;height:{height}px")
    div_id = str(container.id)

    mid = pts[len(pts) // 2]
    
    # 修改点：将 Tile Layer 替换为 Esri 卫星图，并增强轨迹线高亮显示
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
          
          // --- 核心修改：使用 Esri 卫星瓦片地图 ---
          L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri',
            maxZoom: 18
          }).addTo(map);

          // 调整轨迹线样式（使用荧光黄/亮色，防止被卫星图复杂地貌吞没）
          var line=L.polyline(pts,{color:'#FFE600',weight:5,opacity:0.95,lineJoin:'round',lineCap:'round'}).addTo(map);
          
          // 起始点标圈
          L.circleMarker(pts[0],{radius:6,color:'#ffffff',fillColor:'#00FF66',fillOpacity:1,weight:2}).addTo(map);
          L.circleMarker(pts[pts.length-1],{radius:6,color:'#ffffff',fillColor:'#FF3333',fillOpacity:1,weight:2}).addTo(map);
          
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