import json
import os
import uuid
from datetime import datetime, timezone

import aiosqlite

from config import settings

DB_PATH = settings.database_url.replace("sqlite+aiosqlite:///", "/")


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS audits (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                domain TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),

                pagespeed_mobile TEXT,
                pagespeed_desktop TEXT,
                crux_url TEXT,
                crux_origin TEXT,
                ttfb_data TEXT,
                screenshot_path TEXT,
                page_weight_data TEXT,

                crawl_status TEXT DEFAULT 'pending',
                crawl_started_at TEXT,
                crawl_finished_at TEXT,
                crawl_config TEXT,
                crawl_progress TEXT,
                sitemap_data TEXT,
                crawl_summary TEXT,

                numos_score TEXT
            );

            CREATE TABLE IF NOT EXISTS crawl_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_id TEXT NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
                url TEXT NOT NULL,
                final_url TEXT,
                status_code INTEGER,
                redirect_chain TEXT,
                depth INTEGER,
                source TEXT,
                content_type TEXT,
                error TEXT,

                title TEXT,
                title_length INTEGER,
                description TEXT,
                description_length INTEGER,
                h1s TEXT,
                h1_count INTEGER,
                canonical TEXT,
                is_noindex INTEGER DEFAULT 0,
                images_total INTEGER,
                images_without_alt INTEGER,
                internal_links_count INTEGER,

                crawled_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_crawl_results_audit
                ON crawl_results(audit_id);
            CREATE INDEX IF NOT EXISTS idx_crawl_results_status
                ON crawl_results(audit_id, status_code);
        """)


def _parse_json_field(value):
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _serialize(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def _row_to_dict(row, columns):
    d = dict(zip(columns, row))
    json_fields = [
        "pagespeed_mobile", "pagespeed_desktop", "crux_url", "crux_origin",
        "ttfb_data", "page_weight_data", "crawl_config", "crawl_progress",
        "sitemap_data", "crawl_summary", "numos_score",
    ]
    for field in json_fields:
        if field in d:
            d[field] = _parse_json_field(d[field])
    return d


async def create_audit(url: str, domain: str) -> dict:
    audit_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO audits (id, url, domain, status, created_at, updated_at) VALUES (?, ?, ?, 'pending', ?, ?)",
            (audit_id, url, domain, now, now),
        )
        await db.commit()
    return {"id": audit_id, "url": url, "domain": domain, "status": "pending", "created_at": now}


async def get_audit(audit_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = None
        cursor = await db.execute("SELECT * FROM audits WHERE id = ?", (audit_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cursor.description]
        return _row_to_dict(row, columns)


async def list_audits() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, url, domain, status, created_at, numos_score FROM audits ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        result = []
        for row in rows:
            d = dict(zip(columns, row))
            d["numos_score"] = _parse_json_field(d.get("numos_score"))
            result.append(d)
        return result


async def update_audit(audit_id: str, **kwargs):
    if not kwargs:
        return
    now = datetime.now(timezone.utc).isoformat()
    kwargs["updated_at"] = now
    serialized = {k: _serialize(v) for k, v in kwargs.items()}
    set_clause = ", ".join(f"{k} = ?" for k in serialized)
    values = list(serialized.values()) + [audit_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE audits SET {set_clause} WHERE id = ?", values)
        await db.commit()


async def delete_audit(audit_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM audits WHERE id = ?", (audit_id,))
        await db.commit()
        return cursor.rowcount > 0
