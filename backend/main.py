import asyncio
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import CRAWLER_DEFAULTS, settings
from database import create_audit, delete_audit, get_audit, init_db, list_audits, update_audit
from models import AuditCreate, BulkAuditCreate
from scoring import calculate_numos_score
from services.analyzer import compute_crawl_summary
from services.crawler import SEOCrawler
from services.pagespeed import extract_crux, extract_lighthouse_metrics, run_pagespeed
from services.screenshot import capture_homepage
from services.ttfb import measure_ttfb
from services.webhook import post_audit_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

crawl_semaphore = asyncio.Semaphore(settings.max_concurrent_crawls)
audit_semaphore = asyncio.Semaphore(settings.max_concurrent_audits)
active_crawlers: dict[str, SEOCrawler] = {}
# Les BackgroundTasks de Starlette s'executent en serie : un lot de 100 URL
# partirait un audit apres l'autre. On passe par des taches concurrentes que le
# semaphore regule, et on garde une reference pour qu'elles survivent au GC.
running_audits: set[asyncio.Task] = set()
# Meme precaution : l'event loop ne garde que des references faibles vers les
# taches, une notification sans reference peut disparaitre en cours d'envoi.
pending_webhooks: set[asyncio.Task] = set()

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

bearer_scheme = HTTPBearer()


async def require_admin(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not settings.admin_token or credentials.credentials != settings.admin_token:
        raise HTTPException(status_code=401, detail="Token invalide")


def notify_event(
    notify: bool,
    event: str,
    audit_id: str,
    url: str,
    status: str,
    score: dict | None,
    tech_summary: dict | None = None,
):
    """Publie un evenement d'audit vers le webhook configure.

    notify=False permet d'auditer une liste sans declencher l'envoi d'email :
    la qualification et la prise de contact deviennent deux etapes distinctes.
    """
    if not notify or not settings.audit_webhook_url:
        return
    task = asyncio.create_task(post_audit_event(
        settings.audit_webhook_url,
        {
            "event": event,
            "audit_id": audit_id,
            "url": url,
            "domain": urlparse(url).netloc,
            "status": status,
            "report_url": f"{settings.public_base_url.rstrip('/')}/rapport/{audit_id}",
            "numos_score": score,
            "tech_summary": tech_summary,
        },
    ))
    pending_webhooks.add(task)
    task.add_done_callback(pending_webhooks.discard)


async def run_audit_background(
    audit_id: str,
    url: str,
    notify: bool = True,
    crawl: bool = True,
    crawl_limit: int | None = None,
):
    tech_fingerprint = None
    score = None
    try:
        # La phase 1 ouvre un Chromium et deux appels PageSpeed par audit :
        # le plafond evite qu'un lot de 100 URL sature le conteneur.
        async with audit_semaphore:
            await update_audit(audit_id, status="running")

            screenshot_path = os.path.join(settings.screenshots_dir, f"{audit_id}.png")

            # Phase 1 : jobs rapides en parallele
            psi_mobile, psi_desktop, ttfb_data, screenshot_data = await asyncio.gather(
                safe_run(run_pagespeed, url, "mobile"),
                safe_run(run_pagespeed, url, "desktop"),
                safe_run(measure_ttfb, url),
                safe_run(capture_homepage, url, screenshot_path),
            )

            if screenshot_data:
                tech_fingerprint = screenshot_data.pop("tech_fingerprint", None)

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
                tech_fingerprint=tech_fingerprint,
                numos_score=score,
            )

        tech_summary = tech_fingerprint.get("summary") if tech_fingerprint else None
        logger.info(f"Audit {audit_id} phase 1 OK (score partiel {score['global']}/100)")
        notify_event(notify, "phase_1_complete", audit_id, url, "partial", score, tech_summary)

        if not crawl:
            await update_audit(audit_id, status="done", crawl_status="skipped")
            logger.info(f"Audit {audit_id} termine sans crawl (score {score['global']}/100)")
            notify_event(notify, "audit_complete", audit_id, url, "done", score, tech_summary)
            return

        # Phase 2 : crawl SEO
        crawl_config = dict(CRAWLER_DEFAULTS)
        if crawl_limit:
            crawl_config["max_urls"] = crawl_limit

        try:
            async with crawl_semaphore:
                await update_audit(audit_id, crawl_status="running", crawl_config=crawl_config)
                crawler = SEOCrawler(audit_id, url, crawl_config)
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
            notify_event(notify, "audit_complete", audit_id, url, "done", final_score, tech_summary)

        except Exception as e:
            logger.error(f"Crawl {audit_id} echoue: {e}")
            await update_audit(audit_id, status="done", crawl_status="failed")
            notify_event(notify, "audit_complete", audit_id, url, "done", score, tech_summary)

    except Exception as e:
        logger.error(f"Audit {audit_id} echoue: {e}")
        await update_audit(audit_id, status="failed")
        notify_event(notify, "audit_failed", audit_id, url, "failed", score)


def spawn_audit(audit_id: str, url: str, notify: bool, crawl: bool, crawl_limit: int | None):
    task = asyncio.create_task(run_audit_background(audit_id, url, notify, crawl, crawl_limit))
    running_audits.add(task)
    task.add_done_callback(running_audits.discard)
    return task


async def safe_run(func, *args):
    try:
        return await func(*args)
    except Exception as e:
        logger.error(f"{func.__name__} echoue: {e}")
        return None


@app.post("/api/audits", status_code=201, dependencies=[Depends(require_admin)])
async def create_audit_endpoint(body: AuditCreate):
    url = str(body.url).rstrip("/")
    domain = urlparse(url).netloc
    audit = await create_audit(url, domain)
    spawn_audit(audit["id"], url, body.notify, body.crawl, body.crawl_limit)
    return audit


@app.post("/api/audits/bulk", status_code=201, dependencies=[Depends(require_admin)])
async def create_audits_bulk(body: BulkAuditCreate):
    """Qualifie une liste d'URL en une passe, sans engager l'envoi d'email.

    crawl_limit=settings.light_crawl_limit donne un score incluant le pilier SEO
    pour un cout tres inferieur au crawl complet, ce qui suffit a trier une liste.
    """
    crawl_limit = body.crawl_limit or settings.light_crawl_limit

    created = []
    skipped = []
    seen: set[str] = set()

    for raw_url in body.urls:
        url = str(raw_url).rstrip("/")
        key = url.lower()
        if key in seen:
            skipped.append({"url": url, "reason": "doublon dans le lot"})
            continue
        seen.add(key)

        domain = urlparse(url).netloc
        if not domain:
            skipped.append({"url": url, "reason": "URL invalide"})
            continue

        audit = await create_audit(url, domain)
        spawn_audit(audit["id"], url, body.notify, body.crawl, crawl_limit)
        created.append(audit)

    logger.info(f"Bulk : {len(created)} audit(s) lance(s), {len(skipped)} ignore(s)")
    return {"created": created, "skipped": skipped}


@app.get("/api/audits", dependencies=[Depends(require_admin)])
async def list_audits_endpoint():
    return await list_audits()


@app.get("/api/audits/{audit_id}", dependencies=[Depends(require_admin)])
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


@app.post("/api/audits/{audit_id}/crawl/stop", dependencies=[Depends(require_admin)])
async def stop_crawl(audit_id: str):
    crawler = active_crawlers.get(audit_id)
    if crawler:
        crawler.stop()
        return {"ok": True, "message": "Arret demande"}
    raise HTTPException(status_code=404, detail="Aucun crawl actif pour cet audit")


@app.delete("/api/audits/{audit_id}", dependencies=[Depends(require_admin)])
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
