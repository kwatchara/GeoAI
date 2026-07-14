# -*- coding: utf-8 -*-
"""
build_landsat9.py
-----------------
สร้างแผนที่ interactive (Landsat9.html) แสดงภาพ Landsat 9 median ปลอดเมฆ ปี 2026
เฉพาะขอบเขตประเทศไทย สีผสมธรรมชาติ (True/Natural Color) ทับบน Google Map

ขั้นตอน:
  1) เชื่อมต่อ Google Earth Engine ด้วย project id = "kwatchara"
  2) อ่านขอบเขตไทยจาก Thailand.geojson (ในเครื่อง) -> ลดจุด (decimate) เพื่อใช้ clip บน GEE
  3) สร้าง composite Landsat 9 (LANDSAT/LC09/C02/T1_L2) filterDate 2026, cloud mask, median, clip
  4) สีผสมธรรมชาติ SR_B4/SR_B3/SR_B2 -> getMapId ได้ tile URL
  5) เขียน Landsat9.html แบบ standalone (Leaflet + Google tiles + Landsat overlay + เส้นขอบไทย)

หมายเหตุสำคัญ:
  * tile URL จาก getMapId มี token ฝังอยู่และ "หมดอายุใน ~ไม่กี่วัน"
    เมื่อภาพหาย ให้รันสคริปต์นี้ใหม่เพื่อรีเฟรช URL
  * ต้องมีอินเทอร์เน็ตตอนเปิด HTML (ดึง tile จาก Google + earthengine.googleapis.com)
"""
import io
import os
import json

import ee

# ---------------- Config ----------------
PROJECT = "kwatchara"
START_DATE = "2026-01-01"
END_DATE = "2026-07-15"           # ปี 2026 ถึงวันปัจจุบัน (14 ก.ค. 2026)

HERE = os.path.dirname(os.path.abspath(__file__))
GEOJSON = os.path.join(HERE, "GEE4NRE 20240131-0202", "Example", "Thailand.geojson")
OUT = os.path.join(HERE, "Landsat9.html")   # เก็บผลลัพธ์ไว้ที่โฟลเดอร์ GeoAI

DECIMALS = 3        # ปัดพิกัดเหลือ ~110 ม. เพื่อลดขนาด payload ที่ส่งเข้า GEE
MIN_RING_PTS = 4    # ring ต้องมีอย่างน้อย 4 จุด (ปิดวง)

# วิชวลสีผสมธรรมชาติ (หลังคูณ scale factor ของ Landsat C2 L2)
VIS = {"bands": ["SR_B4", "SR_B3", "SR_B2"], "min": 0.0, "max": 0.3, "gamma": 1.1}


# ---------------- Earth Engine ----------------
def init_ee():
    try:
        ee.Initialize(project=PROJECT)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=PROJECT)
    print("EE initialized. project =", PROJECT)


# ---------------- ขอบเขตไทย ----------------
def decimate_ring(ring):
    """ปัดพิกัดและตัดจุดซ้ำติดกัน; คืน None ถ้าจุดไม่พอ"""
    out = []
    last = None
    for pt in ring:
        p = (round(pt[0], DECIMALS), round(pt[1], DECIMALS))
        if p != last:
            out.append([p[0], p[1]])
            last = p
    if len(out) < MIN_RING_PTS:
        return None
    if out[0] != out[-1]:          # ปิดวงให้เรียบร้อย
        out.append(out[0])
    return out


def load_thailand_geometry():
    """อ่าน MultiPolygon จาก geojson -> ลดจุด -> ee.Geometry.MultiPolygon"""
    with io.open(GEOJSON, "r", encoding="utf-8") as f:
        gj = json.load(f)

    geom = gj["features"][0]["geometry"]
    assert geom["type"] == "MultiPolygon", "รองรับเฉพาะ MultiPolygon"

    polys_out = []
    n_in = n_out = 0
    for poly in geom["coordinates"]:
        rings_out = []
        for ring in poly:
            n_in += len(ring)
            dec = decimate_ring(ring)
            if dec:
                rings_out.append(dec)
                n_out += len(dec)
        if rings_out:
            polys_out.append(rings_out)

    print("boundary vertices: %d -> %d (decimated)" % (n_in, n_out))
    return ee.Geometry.MultiPolygon(polys_out, geodesic=False)


# ---------------- Landsat 9 composite ----------------
def mask_l9_sr(img):
    """cloud mask จาก QA_PIXEL (C2 L2) + คูณ scale factor แบนด์แสง"""
    qa = img.select("QA_PIXEL")
    mask = (qa.bitwiseAnd(1 << 1).eq(0)      # dilated cloud
            .And(qa.bitwiseAnd(1 << 2).eq(0))  # cirrus
            .And(qa.bitwiseAnd(1 << 3).eq(0))  # cloud
            .And(qa.bitwiseAnd(1 << 4).eq(0)))  # cloud shadow
    optical = img.select("SR_B.").multiply(0.0000275).add(-0.2)
    return img.addBands(optical, None, True).updateMask(mask)


def build_composite(geom):
    col = (ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
           .filterDate(START_DATE, END_DATE)
           .filterBounds(geom)
           .map(mask_l9_sr))
    n = col.size().getInfo()
    print("Landsat 9 scenes in range: %d" % n)
    if n == 0:
        raise SystemExit("ไม่พบภาพ Landsat 9 ในช่วงเวลาที่กำหนด")
    return col.median().clip(geom)


# ---------------- HTML ----------------
TEMPLATE = r"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Landsat 9 — ปลอดเมฆ 2026 (ประเทศไทย)</title>
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
    max-width: 300px;
  }
  .panel h1 { margin: 0 0 4px; font-size: 1.05rem; color: #1f4e79; }
  .panel p { margin: 2px 0; font-size: .8rem; color: #444; line-height: 1.35; }
  .panel .tag { display:inline-block; background:#1f4e79; color:#fff;
    border-radius: 5px; padding: 1px 7px; font-size:.72rem; margin-top:4px; }
</style>
</head>
<body>
<div id="map"></div>
<div class="panel">
  <h1>Landsat 9 — สีผสมธรรมชาติ</h1>
  <p>Median ปลอดเมฆ ช่วง __START__ ถึง __END__</p>
  <p>ขอบเขตเฉพาะประเทศไทย • แบนด์ SR_B4/3/2</p>
  <p><span class="tag">GEE · LANDSAT/LC09/C02/T1_L2</span></p>
  <p style="color:#a33">* หากภาพไม่แสดง อาจเป็นเพราะ tile URL หมดอายุ — รัน build_landsat9.py ใหม่</p>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
  const geojsonData = __GEOJSON__;
  const eeTileUrl = "__EE_TILE_URL__";

  const map = L.map('map', { zoomControl: true });

  // ---- Google basemap (XYZ) ----
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

  googleRoad.addTo(map);

  // ---- Landsat 9 overlay จาก GEE ----
  const landsat = L.tileLayer(eeTileUrl,
      { maxZoom: 20, opacity: 1.0, attribution: 'Landsat 9 · USGS/NASA via Google Earth Engine' });
  landsat.addTo(map);

  // ---- เส้นขอบประเทศไทย ----
  const outline = L.geoJSON(geojsonData, {
    style: { color: '#ffd400', weight: 1.5, opacity: 0.9, fill: false }
  }).addTo(map);

  L.control.layers(
    {
      'Google Road': googleRoad,
      'Google Satellite': googleSat,
      'Google Hybrid': googleHybrid,
      'Google Terrain': googleTerrain
    },
    {
      'Landsat 9 (2026, ปลอดเมฆ)': landsat,
      'เส้นขอบไทย': outline
    },
    { position: 'topright', collapsed: false }
  ).addTo(map);

  L.control.scale({ imperial: false }).addTo(map);

  try {
    map.fitBounds(outline.getBounds(), { padding: [20, 20] });
  } catch (e) {
    map.setView([13.5, 100.5], 6);
  }
</script>
</body>
</html>
"""


def write_html(tile_url):
    with io.open(GEOJSON, "r", encoding="utf-8") as f:
        geojson_text = f.read()
    html = (TEMPLATE
            .replace("__GEOJSON__", geojson_text)
            .replace("__EE_TILE_URL__", tile_url)
            .replace("__START__", START_DATE)
            .replace("__END__", END_DATE))
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("WROTE:", OUT)
    print("size (MB): %.2f" % (os.path.getsize(OUT) / 1e6))


def main():
    init_ee()
    geom = load_thailand_geometry()
    composite = build_composite(geom)
    mapid = composite.getMapId(VIS)
    tile_url = mapid["tile_fetcher"].url_format
    print("EE tile URL:", tile_url)
    write_html(tile_url)


if __name__ == "__main__":
    main()
