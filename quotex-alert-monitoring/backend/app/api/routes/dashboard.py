"""
Dashboard routes - ALERT-ONLY monitoring system.
Serves the monitoring dashboard SPA (HTML/JS/CSS).
No trade execution UI -- display-only alert dashboard.
"""

import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])

# Possible locations for the dashboard build output
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent  # backend/
_STATIC_DIR = _BACKEND_DIR / "static"
_DASHBOARD_BUILD_DIR = _STATIC_DIR / "dashboard"

# Fallback HTML when the dashboard has not been built yet
_FALLBACK_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quotex Alert Monitoring Dashboard</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh; margin: 0;
            background: #0f172a; color: #e2e8f0;
        }
        .container { text-align: center; padding: 2rem; }
        h1 { color: #38bdf8; margin-bottom: 0.5rem; }
        p { color: #94a3b8; }
        code { background: #1e293b; padding: 0.2rem 0.5rem; border-radius: 4px; }
        .badge {
            display: inline-block; margin-top: 1rem; padding: 0.3rem 0.8rem;
            background: #1e293b; border: 1px solid #334155; border-radius: 999px;
            font-size: 0.75rem; color: #94a3b8;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Quotex Alert Monitoring</h1>
        <p>ALERT-ONLY system &mdash; no trade execution</p>
        <p>Dashboard has not been built yet.</p>
        <p>API is running at <code>/health</code> and <code>/api/signals/</code></p>
        <div class="badge">Monitoring API Active</div>
    </div>
</body>
</html>
"""


def _find_index_html() -> Path | None:
    """Locate the dashboard index.html in known build locations."""
    candidates = [
        _DASHBOARD_BUILD_DIR / "index.html",
        _STATIC_DIR / "index.html",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


@router.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the monitoring dashboard.

    ALERT-ONLY: This dashboard displays signal alerts and analytics.
    No trade execution controls are present.
    """
    index = _find_index_html()
    if index is not None:
        return FileResponse(index, media_type="text/html")

    logger.info("Dashboard build not found, serving fallback page")
    return HTMLResponse(content=_FALLBACK_HTML, status_code=200)


@router.get("/history", response_class=HTMLResponse)
async def serve_dashboard_history():
    """Serve the dashboard for the /history SPA route.

    ALERT-ONLY: SPA client-side routing -- serves the same index.html
    and lets the frontend JS handle the /history route.
    """
    index = _find_index_html()
    if index is not None:
        return FileResponse(index, media_type="text/html")

    logger.info("Dashboard build not found, serving fallback page for /history")
    return HTMLResponse(content=_FALLBACK_HTML, status_code=200)
