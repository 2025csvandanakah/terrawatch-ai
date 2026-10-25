# TerraWatch AI — Final ready-to-run project

## First run on Windows
1. Extract this ZIP into a normal folder.
2. Double-click `setup_and_run.bat`.
3. Wait while it creates `.venv` and installs required packages.
4. Open **http://127.0.0.1:8000** in your browser when Uvicorn starts.
5. Keep the terminal window open while using the website.

No PowerShell script activation is required. The launcher intentionally does not use `--reload`, to prevent repeated reloads when files in `.venv\Lib\site-packages` change.

## If the virtual environment already exists
Open PowerShell in the extracted project folder and run:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```
Do not open `static/index.html` directly; use the local website address above.

## Includes
- HTML/CSS/JavaScript satellite comparison dashboard.
- FastAPI backend requesting dated images from NASA GIBS.
- Approximate cloud/haze masking, pixel-change overlay and heatmap.
- Rule-based candidate land-change categories.
- Leaflet/OSM geographic map with highlighted approximate grid cells.
- PDF report generation.
- Frontend safe JSON parsing with useful API error messages.
- Windows setup and run scripts.

## Limitations
This is a hackathon screening prototype. The cloud mask and category labels are RGB heuristics, not validated scientific detectors or trained AI. Clouds, haze, shadows, seasonal changes, bright land, sensor differences and image misalignment can cause false positives. The map cells are approximate review areas, not precise damage boundaries. MODIS imagery is relatively coarse for small infrastructure. Verify important results with appropriate higher-resolution data and independent review. NASA GIBS imagery availability varies by date/layer; the map tiles and Leaflet library require internet access.
