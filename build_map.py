# -*- coding: utf-8 -*-
"""
build_map.py
------------
สร้างแผนที่ interactive (Thailand.html) จาก Thailand.geojson
พื้นหลัง Google Map (Leaflet + Google tiles) ฝัง GeoJSON ลงในไฟล์โดยตรง
เพื่อให้เปิดจาก file:// ได้ทันทีโดยไม่ต้องรันเว็บเซิร์ฟเวอร์
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.join(HERE, "GEE4NRE 20240131-0202", "Example")
GEOJSON = os.path.join(EXAMPLE, "Thailand.geojson")
OUT = os.path.join(EXAMPLE, "Thailand.html")

with io.open(GEOJSON, "r", encoding="utf-8") as f:
    geojson_text = f.read()

TEMPLATE = r"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Thailand — Interactive Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
<style>
  html, body { height: 100%; margin: 0; }
  #map { position: absolute; inset: 0; }
  .panel {
    position: absolute; top: 12px; left: 12px; z-index: 1000;
    background: rgba(255,255,255,0.94); border-radius: 10px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.25);
    padding: 12px 14px; font-family: 'Segoe UI','Sarabun',Tahoma,sans-serif;
    max-width: 260px;
  }
  .panel h1 { margin: 0 0 4px; font-size: 1.1rem; color: #1f4e79; }
  .panel p { margin: 2px 0; font-size: .82rem; color: #444; }
  .leaflet-popup-content { font-family: 'Segoe UI','Sarabun',Tahoma,sans-serif; font-size: .85rem; }
  .leaflet-popup-content table { border-collapse: collapse; }
  .leaflet-popup-content td { padding: 2px 6px; border-bottom: 1px solid #eee; }
  .leaflet-popup-content td.k { color: #1f4e79; font-weight: 600; }
</style>
</head>
<body>
<div id="map"></div>
<div class="panel">
  <h1>ประเทศไทย (Thailand)</h1>
  <p>ที่มา: Thailand.geojson (EPSG:4326)</p>
  <p>คลิกที่พื้นที่เพื่อดูข้อมูล • เลือกชั้นแผนที่มุมขวาบน</p>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
  // ---- ข้อมูล GeoJSON ที่ฝังไว้ ----
  const geojsonData = __GEOJSON__;

  // ---- แผนที่ ----
  const map = L.map('map', { zoomControl: true });

  // ---- พื้นหลัง Google tiles (XYZ) ----
  const gAttr = '&copy; Google';
  const sub = ['0','1','2','3'];
  const googleRoad = L.tileLayer('https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
      { subdomains: sub, maxZoom: 21, attribution: gAttr });
  const googleSat = L.tileLayer('https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
      { subdomains: sub, maxZoom: 21, attribution: gAttr });
  const googleHybrid = L.tileLayer('https://mt{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
      { subdomains: sub, maxZoom: 21, attribution: gAttr });
  const googleTerrain = L.tileLayer('https://mt{s}.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
      { subdomains: sub, maxZoom: 21, attribution: gAttr });

  googleHybrid.addTo(map);

  L.control.layers({
    'Google Hybrid': googleHybrid,
    'Google Satellite': googleSat,
    'Google Road': googleRoad,
    'Google Terrain': googleTerrain
  }, null, { position: 'topright', collapsed: false }).addTo(map);

  L.control.scale({ imperial: false }).addTo(map);

  // ---- ชั้นข้อมูล GeoJSON ----
  function popupContent(props) {
    if (!props || Object.keys(props).length === 0) return 'ไม่มีข้อมูลคุณสมบัติ';
    let rows = '';
    for (const k in props) {
      rows += '<tr><td class="k">' + k + '</td><td>' + props[k] + '</td></tr>';
    }
    return '<table>' + rows + '</table>';
  }

  const layer = L.geoJSON(geojsonData, {
    style: {
      color: '#ff3b30', weight: 2, opacity: 0.9,
      fillColor: '#ff3b30', fillOpacity: 0.12
    },
    onEachFeature: function (feature, lyr) {
      lyr.bindPopup(popupContent(feature.properties));
      lyr.on('mouseover', function () { this.setStyle({ weight: 3, fillOpacity: 0.22 }); });
      lyr.on('mouseout',  function () { this.setStyle({ weight: 2, fillOpacity: 0.12 }); });
    }
  }).addTo(map);

  // ---- ซูมให้พอดีขอบเขต ----
  try {
    map.fitBounds(layer.getBounds(), { padding: [20, 20] });
  } catch (e) {
    map.setView([13.5, 100.5], 6);
  }
</script>
</body>
</html>
"""

html = TEMPLATE.replace("__GEOJSON__", geojson_text)
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

print("WROTE:", OUT)
print("size (MB): %.2f" % (os.path.getsize(OUT) / 1e6))
