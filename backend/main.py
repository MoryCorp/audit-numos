import asyncio
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import create_audit, delete_audit, get_audit, init_db, list_audits, update_audit
from models import AuditCreate, AuditListItem, AuditProgress, AuditResponse
from scoring import calculate_numos_score
from services.pagespeed import extract_crux, extract_lighthouse_metrics, run_pagespeed
from services.screenshot import capture_homepage
from services.ttfb import measure_ttfb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

crawl_semaphore = asyncio.Semaphore(settings.max_concurrent_crawls)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs(settings.screenshots_dir, exist_ok=True)
    yield


app = FastAPI(title="Numos Audit Tool", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/screenshots", StaticFiles(directory=settings.screenshots_dir), name="screenshots")


async def run_audit_background(audit_id: str, url: str):
    try:
        await update_audit(audit_id, status="running")

        screenshot_path = os.path.join(settings.screenshots_dir, f"{audit_id}.png")

        psi_mobile, psi_desktop, ttfb_data, screenshot_data = await asyncio.gather(
            safe_run(run_pagespeed, url, "mobile"),
            safe_run(run_pagespeed, url, "desktop"),
            safe_run(measure_ttfb, url),
            safe_run(capture_homepage, url, screenshot_path),
            return_exceptions=False,
        )

        crux_url = None
        crux_origin = None
        if psi_mobile:
            crux = extract_crux(psi_mobile)
            crux_url = crux.get("url")
            crux_origin = crux.get("origin")

        score = calculate_numos_score(
            pagespeed_mobile=psi_mobile,
            pagespeed_desktop=psi_desktop,
            crux_data=crux_url,
            ttfb=ttfb_data,
        )

        relative_screenshot = f"{audit_id}.png" if screenshot_data else None

        await update_audit(
            audit_id,
            status="done",
            pagespeed_mobile=psi_mobile,
            pagespeed_desktop=psi_desktop,
            crux_url=crux_url,
            crux_origin=crux_origin,
            ttfb_data=ttfb_data,
            screenshot_path=relative_screenshot,
            page_weight_data=screenshot_data,
            numos_score=score,
        )
        logger.info(f"Audit {audit_id} termine avec score {score['global']}/100")

    except Exception as e:
        logger.error(f"Audit {audit_id} echoue: {e}")
        await update_audit(audit_id, status="failed")


async def safe_run(func, *args):
    try:
        return await func(*args)
    except Exception as e:
        logger.error(f"{func.__name__} echoue: {e}")
        return None


@app.post("/api/audits", status_code=201)
async def create_audit_endpoint(body: AuditCreate, background_tasks: BackgroundTasks):
    url = str(body.url).rstrip("/")
    domain = urlparse(url).netloc
    audit = await create_audit(url, domain)
    background_tasks.add_task(run_audit_background, audit["id"], url)
    return audit


@app.get("/api/audits")
async def list_audits_endpoint():
    return await list_audits()


@app.get("/api/audits/{audit_id}")
async def get_audit_endpoint(audit_id: str):
    audit = await get_audit(audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit non trouve")
    return audit


@app.get("/api/audits/{audit_id}/progress")
async def get_audit_progress(audit_id: str):
    audit = await get_audit(audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit non trouve")
    return {
        "id": audit["id"],
        "status": audit["status"],
        "crawl_status": audit.get("crawl_status"),
        "crawl_progress": audit.get("crawl_progress"),
    }


@app.get("/api/audits/{audit_id}/report")
async def get_audit_report(audit_id: str):
    audit = await get_audit(audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit non trouve")

    lighthouse_mobile = None
    lighthouse_desktop = None
    if audit.get("pagespeed_mobile"):
        lighthouse_mobile = extract_lighthouse_metrics(audit["pagespeed_mobile"])
    if audit.get("pagespeed_desktop"):
        lighthouse_desktop = extract_lighthouse_metrics(audit["pagespeed_desktop"])

    screenshot_url = None
    if audit.get("screenshot_path"):
        screenshot_url = f"/screenshots/{audit['screenshot_path']}"

    page_weight = audit.get("page_weight_data")
    if page_weight and "screenshot_path" in page_weight:
        del page_weight["screenshot_path"]

    return {
        "id": audit["id"],
        "url": audit["url"],
        "domain": audit["domain"],
        "status": audit["status"],
        "created_at": audit["created_at"],
        "screenshot_url": screenshot_url,
        "numos_score": audit.get("numos_score"),
        "lighthouse_mobile": lighthouse_mobile,
        "lighthouse_desktop": lighthouse_desktop,
        "crux_url": audit.get("crux_url"),
        "crux_origin": audit.get("crux_origin"),
        "ttfb_data": audit.get("ttfb_data"),
        "page_weight": page_weight,
        "crawl_summary": audit.get("crawl_summary"),
    }


@app.delete("/api/audits/{audit_id}")
async def delete_audit_endpoint(audit_id: str):
    audit = await get_audit(audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit non trouve")
    if audit.get("screenshot_path"):
        path = os.path.join(settings.screenshots_dir, audit["screenshot_path"])
        if os.path.exists(path):
            os.remove(path)
    await delete_audit(audit_id)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
