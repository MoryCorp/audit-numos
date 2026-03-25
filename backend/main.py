import asyncio
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import CRAWLER_DEFAULTS, settings
from database import create_audit, delete_audit, get_audit, init_db, list_audits, update_audit
from models import AuditCreate
from scoring import calculate_numos_score
from services.analyzer import compute_crawl_summary
from services.crawler import SEOCrawler
from services.pagespeed import extract_crux, extract_lighthouse_metrics, run_pagespeed
from services.screenshot import capture_homepage
from services.ttfb import measure_ttfb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

crawl_semaphore = asyncio.Semaphore(settings.max_concurrent_crawls)
active_crawlers: dict[str, SEOCrawler] = {}

os.makedirs(settings.screenshots_dir, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
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

        # Phase 1 : jobs rapides en parallele
        psi_mobile, psi_desktop, ttfb_data, screenshot_data = await asyncio.gather(
            safe_run(run_pagespeed, url, "mobile"),
            safe_run(run_pagespeed, url, "desktop"),
            safe_run(measure_ttfb, url),
            safe_run(capture_homepage, url, screenshot_path),
        )

        crux_url = None
        crux_origin = None
        if psi_mobile:
            crux = extract_crux(psi_mobile)
            crux_url = crux.get("url")
            crux_origin = crux.get("origin")

        # Score partiel (sans SEO)
        score = calculate_numos_score(
            pagespeed_mobile=psi_mobile,
            pagespeed_desktop=psi_desktop,
            crux_data=crux_url,
            ttfb=ttfb_data,
        )

        relative_screenshot = f"{audit_id}.png" if screenshot_data else None

        await update_audit(
            audit_id,
            status="partial",
            pagespeed_mobile=psi_mobile,
            pagespeed_desktop=psi_desktop,
            crux_url=crux_url,
            crux_origin=crux_origin,
            ttfb_data=ttfb_data,
            screenshot_path=relative_screenshot,
            page_weight_data=screenshot_data,
            numos_score=score,
        )
        logger.info(f"Audit {audit_id} phase 1 OK (score partiel {score['global']}/100), lancement crawl SEO")

        # Phase 2 : crawl SEO
        try:
            async with crawl_semaphore:
                await update_audit(audit_id, crawl_status="running")
                crawler = SEOCrawler(audit_id, url, CRAWLER_DEFAULTS)
                active_crawlers[audit_id] = crawler
                try:
                    await crawler.run()
                finally:
                    active_crawlers.pop(audit_id, None)

            # Agreger et recalculer le score
            summary = await compute_crawl_summary(audit_id)
            final_score = calculate_numos_score(
                pagespeed_mobile=psi_mobile,
                pagespeed_desktop=psi_desktop,
                crux_data=crux_url,
                ttfb=ttfb_data,
                crawl_stats=summary,
            )

            await update_audit(
                audit_id,
                status="done",
                crawl_status="done",
                crawl_summary=summary,
                numos_score=final_score,
            )
            logger.info(f"Audit {audit_id} termine (score final {final_score['global']}/100, {summary['total_crawled']} pages)")

        except Exception as e:
            logger.error(f"Crawl {audit_id} echoue: {e}")
            await update_audit(audit_id, status="done", crawl_status="failed")

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
        "crawl_status": audit.get("crawl_status"),
        "crawl_progress": audit.get("crawl_progress"),
        "crawl_summary": audit.get("crawl_summary"),
    }


@app.post("/api/audits/{audit_id}/crawl/stop")
async def stop_crawl(audit_id: str):
    crawler = active_crawlers.get(audit_id)
    if crawler:
        crawler.stop()
        return {"ok": True, "message": "Arret demande"}
    raise HTTPException(status_code=404, detail="Aucun crawl actif pour cet audit")


@app.delete("/api/audits/{audit_id}")
async def delete_audit_endpoint(audit_id: str):
    audit = await get_audit(audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit non trouve")
    crawler = active_crawlers.get(audit_id)
    if crawler:
        crawler.stop()
    if audit.get("screenshot_path"):
        path = os.path.join(settings.screenshots_dir, audit["screenshot_path"])
        if os.path.exists(path):
            os.remove(path)
    await delete_audit(audit_id)
    return {"ok": True}


STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        file_path = os.path.join(STATIC_DIR, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
