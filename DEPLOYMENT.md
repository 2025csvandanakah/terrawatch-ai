# TerraWatch AI — deployment-ready package

This folder is prepared for local use and deployment to Render.

## A. Deploy to Render (recommended)
1. Extract the ZIP.
2. Sign in to GitHub and create a new repository named `terrawatch-ai`. You can make it private or public; if private, authorize Render to access it.
3. In the new repository, use **Add file → Upload files** and upload the *contents* of this extracted folder, so `main.py`, `requirements.txt`, `render.yaml`, and `static/` are at the repository root. Do not upload `.venv`.
4. Commit the files.
5. Open https://dashboard.render.com and choose **New + → Web Service**.
6. Connect GitHub, select `terrawatch-ai`, and deploy.
7. Render can read `render.yaml`; if entering settings manually, use:
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `python -m uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Health check path: `/api/health`
   - Plan: Free (if offered in your account)
8. Wait for the deployment to finish. Open the `onrender.com` URL shown in your Render dashboard.
9. Test the homepage, `/api/health`, one satellite comparison, and the PDF report.

## B. Local Windows run
Double-click `setup_and_run.bat`, or in PowerShell from this folder:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```
If `.venv` does not exist, create it with `py -m venv .venv` first. Use http://127.0.0.1:8000. Do not open `static/index.html` directly.

## Important
- Render's free web services go idle after inactivity and can take around a minute to start again on the next request. This may make the first judge demo request slower.
- This app calls NASA GIBS at runtime; the deployed app requires outbound internet and available imagery for the chosen dates.
- The map uses external Leaflet assets and OpenStreetMap tiles, so those also need internet access.
- Cloud masking and land-change categories are RGB-based heuristics, not validated scientific classifiers. Explain this honestly in the demo.
- Free Render filesystems are ephemeral. The PDF report is generated for download each time; don't use local files for persistent app data.
