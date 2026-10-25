from datetime import date
from io import BytesIO
import base64
import os
import logging
from pathlib import Path
import requests
import numpy as np
from PIL import Image, ImageFilter
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("terrawatch")

app = FastAPI(title="TerraWatch AI — Satellite Change Intelligence")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.exception_handler(HTTPException)
async def api_http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})

@app.exception_handler(Exception)
async def api_unexpected_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled request error: %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Unexpected server error. Check the VS Code terminal for details."})


NASA_WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
LAYER = "MODIS_Terra_CorrectedReflectance_TrueColor"

class CompareRequest(BaseModel):
    before_date: date
    after_date: date
    west: float = Field(default=76.55, ge=-180, le=180)
    south: float = Field(default=12.90, ge=-90, le=90)
    east: float = Field(default=77.00, ge=-180, le=180)
    north: float = Field(default=13.25, ge=-90, le=90)
    width: int = Field(default=640, ge=128, le=1024)
    height: int = Field(default=480, ge=128, le=1024)

def get_nasa_image(day, req):
    params = {
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap",
        "LAYERS": LAYER, "STYLES": "", "FORMAT": "image/png",
        "SRS": "EPSG:4326",
        "BBOX": f"{req.west},{req.south},{req.east},{req.north}",
        "WIDTH": req.width, "HEIGHT": req.height, "TIME": day.isoformat(),
        "TRANSPARENT": "FALSE"
    }
    try:
        r = requests.get(NASA_WMS, params=params, timeout=(8, 30))
        r.raise_for_status()
        # Some WMS failures return an XML exception document with HTTP 200.
        im = Image.open(BytesIO(r.content)).convert("RGB")
        return im
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not retrieve NASA GIBS imagery for {day}. Try another date or a smaller area. Details: {e}"
        )

def png_data(im):
    b = BytesIO()
    im.save(b, format="PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode("ascii")

def classify_pixels(before, after, valid):
    """
    Transparent heuristic classification, not a trained model.
    Uses RGB color/brightness cues and change direction. Results should be
    presented as candidate categories requiring review, never as proof.
    """
    b = np.asarray(before).astype(np.float32) / 255.0
    a = np.asarray(after).astype(np.float32) / 255.0
    # Green dominance is only a rough vegetation proxy in true-colour imagery.
    b_green = b[:, :, 1] - (b[:, :, 0] + b[:, :, 2]) / 2
    a_green = a[:, :, 1] - (a[:, :, 0] + a[:, :, 2]) / 2
    green_drop = b_green - a_green
    brightness_b = b.mean(axis=2)
    brightness_a = a.mean(axis=2)
    brightness_change = brightness_a - brightness_b
    r, g, bl = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    soil_like = (r > g * 0.92) & (g > bl * 0.75) & (r > 0.28) & (g > 0.20)
    dark_change = brightness_change < -0.12
    light_change = brightness_change > 0.12

    counts = {
        "Vegetation loss candidate": int(((green_drop > 0.10) & valid).sum()),
        "New bright/bare surface candidate": int((soil_like & (np.abs(brightness_change) > 0.08) & valid).sum()),
        "Darkening/water-or-shadow candidate": int((dark_change & valid).sum()),
        "Brightening/construction-or-cloud candidate": int((light_change & valid).sum()),
    }
    total = sum(counts.values())
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    categories = []
    for name, count in ranked:
        if count > 0:
            categories.append({
                "name": name,
                "pixels": count,
                "share_of_valid_pixels": round(count / max(int(valid.sum()), 1) * 100, 2)
            })
    return categories[:4]

@app.get("/")
def home():
    return FileResponse(ROOT / "index.html")

@app.get("/api/health")
def health():
    return {"status": "ok", "imagery_source": "NASA GIBS WMS", "layer": LAYER}

@app.post("/api/compare")
def compare(req: CompareRequest):
    if req.before_date >= req.after_date:
        raise HTTPException(status_code=400, detail="Before date must be earlier than after date.")
    if req.east <= req.west or req.north <= req.south:
        raise HTTPException(status_code=400, detail="Invalid bounding box: east must exceed west and north must exceed south.")

    before = get_nasa_image(req.before_date, req)
    after = get_nasa_image(req.after_date, req)

    b = np.asarray(before).astype(np.int16)
    a = np.asarray(after).astype(np.int16)
    diff = np.abs(a - b).mean(axis=2).astype(np.float32)

    # Heuristic cloud/bright-haze mask. True-colour RGB cannot reliably identify all clouds.
    after_rgb = np.asarray(after).astype(np.float32)
    maxc = after_rgb.max(axis=2)
    minc = after_rgb.min(axis=2)
    saturation = (maxc - minc) / np.maximum(maxc, 1.0)
    brightness = after_rgb.mean(axis=2)
    before_rgb = np.asarray(before).astype(np.float32)
    bmax, bmin = before_rgb.max(axis=2), before_rgb.min(axis=2)
    b_saturation = (bmax - bmin) / np.maximum(bmax, 1.0)
    b_brightness = before_rgb.mean(axis=2)

    # Candidate cloud/haze pixels: bright, relatively low saturation in either date.
    cloud_after = (brightness > 178) & (saturation < 0.24)
    cloud_before = (b_brightness > 178) & (b_saturation < 0.24)
    cloud_mask = cloud_after | cloud_before
    # Expand mask a little to avoid cloud-edge pixels contaminating the score.
    cloud_img = Image.fromarray((cloud_mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    cloud_mask = np.asarray(cloud_img) > 0

    valid = ~cloud_mask
    # Adaptive threshold computed from non-cloud pixels only.
    valid_diffs = diff[valid]
    if valid_diffs.size < 50:
        valid = np.ones_like(cloud_mask, dtype=bool)
        valid_diffs = diff[valid]
        cloud_warning = "Too few pixels passed the cloud heuristic; score uses all pixels and is especially uncertain."
    else:
        cloud_warning = "Cloud/haze masking is heuristic and may miss thin clouds or mask bright land."

    threshold = max(18.0, float(np.percentile(valid_diffs, 82)))
    changed = (diff >= threshold) & valid
    valid_count = max(int(valid.sum()), 1)
    changed_pixels = int(changed.sum())
    pct = round(100 * changed_pixels / valid_count, 2)
    cloud_pct = round(100 * int(cloud_mask.sum()) / cloud_mask.size, 2)

    overlay = after.convert("RGBA")
    red = Image.new("RGBA", after.size, (255, 48, 64, 0))
    red.putalpha(Image.fromarray((changed.astype(np.uint8) * 135), mode="L"))
    overlay = Image.alpha_composite(overlay, red).convert("RGB")

    # Cloud mask view (yellow pixels indicate excluded cloud/haze candidates).
    cloud_overlay = after.convert("RGBA")
    yellow = Image.new("RGBA", after.size, (255, 210, 60, 0))
    yellow.putalpha(Image.fromarray((cloud_mask.astype(np.uint8) * 115), mode="L"))
    cloud_overlay = Image.alpha_composite(cloud_overlay, yellow).convert("RGB")

    norm = np.clip(diff * 3.0, 0, 255).astype(np.uint8)
    heat_arr = np.zeros((norm.shape[0], norm.shape[1], 3), dtype=np.uint8)
    heat_arr[:, :, 0] = norm
    heat_arr[:, :, 1] = np.clip(255 - np.abs(norm.astype(np.int16)-128)*2, 0, 255).astype(np.uint8)
    heat_arr[:, :, 2] = 255 - norm
    heat = Image.fromarray(heat_arr)

    # Coarse geographic grid of changed-pixel density, useful for map display.
    # Rows are mapped north-to-south; columns west-to-east.
    rows, cols = 8, 8
    h, w = changed.shape
    cells = []
    for ri in range(rows):
        for ci in range(cols):
            y0, y1 = int(ri*h/rows), int((ri+1)*h/rows)
            x0, x1 = int(ci*w/cols), int((ci+1)*w/cols)
            cell_valid = valid[y0:y1, x0:x1]
            if cell_valid.size == 0:
                continue
            density = 100 * float(changed[y0:y1, x0:x1].sum()) / max(int(cell_valid.sum()), 1)
            if density >= 8:
                west = req.west + (req.east-req.west) * ci/cols
                east = req.west + (req.east-req.west) * (ci+1)/cols
                north = req.north - (req.north-req.south) * ri/rows
                south = req.north - (req.north-req.south) * (ri+1)/rows
                cells.append({
                    "south": south, "west": west, "north": north, "east": east,
                    "change_density_percent": round(density, 1)
                })

    categories = classify_pixels(before, after, valid)
    return {
        "before_date": req.before_date.isoformat(),
        "after_date": req.after_date.isoformat(),
        "bbox": {"west": req.west, "south": req.south, "east": req.east, "north": req.north},
        "before_image": png_data(before),
        "after_image": png_data(after),
        "overlay_image": png_data(overlay),
        "heatmap_image": png_data(heat),
        "cloud_image": png_data(cloud_overlay),
        "changed_pixel_percent": pct,
        "changed_pixels": changed_pixels,
        "total_pixels": valid_count,
        "cloud_candidate_percent": cloud_pct,
        "screening_level": "High" if pct >= 30 else ("Medium" if pct >= 12 else "Low"),
        "method": "Cloud-aware heuristic + adaptive RGB difference",
        "categories": categories,
        "map_cells": cells,
        "caveat": (
            "These are screening estimates, not confirmed damage or human intent. "
            "Cloud/haze masking uses a simple brightness/saturation heuristic. "
            "Category labels are rule-based RGB candidates, not a trained or validated AI classifier. "
            "Clouds, shadows, seasons, image alignment and sensor conditions can cause false positives."
        ),
        "cloud_note": cloud_warning
    }

@app.post("/api/report")
def report(req: CompareRequest):
    data = compare(req)
    path = str(ROOT / "terrawatch_change_report.pdf")
    c = canvas.Canvas(path, pagesize=letter)
    _, h = letter
    y = h - 52
    c.setFont("Helvetica-Bold", 18)
    c.drawString(48, y, "TerraWatch AI — Satellite Change Report")
    y -= 32
    c.setFont("Helvetica", 10)
    lines = [
        f"Before date: {data['before_date']}",
        f"After date: {data['after_date']}",
        f"Bounding box (west, south, east, north): {req.west}, {req.south}, {req.east}, {req.north}",
        f"Changed valid pixels: {data['changed_pixel_percent']}%",
        f"Cloud/haze candidates excluded: {data['cloud_candidate_percent']}%",
        f"Screening priority (heuristic): {data['screening_level']}",
        f"Method: {data['method']}",
        "",
        "Candidate categories (rule-based, not validated):",
    ]
    for cat in data["categories"]:
        lines.append(f"- {cat['name']}: {cat['share_of_valid_pixels']}% of valid pixels")
    lines += [
        "",
        "Interpretation and limitations:",
        "This report highlights visual differences between NASA GIBS image renderings.",
        "Cloud masking and category labels are heuristic and can be wrong.",
        "The result does not prove the type, cause, severity, or legality of a change.",
        "Verify important findings with expert review and suitable higher-resolution data.",
        "",
        "Imagery source: NASA Global Imagery Browse Services (GIBS).",
        "Prototype status: screening demo, not an operational damage assessment."
    ]
    for line in lines:
        if y < 55:
            c.showPage()
            y = h - 50
            c.setFont("Helvetica", 10)
        c.drawString(48, y, line[:115])
        y -= 16
    c.save()
    return FileResponse(path, media_type="application/pdf", filename="terrawatch_change_report.pdf")
