import json
import logging

import aiosqlite

from database import DB_PATH

logger = logging.getLogger(__name__)

ISSUE_DEFS = [
    {"key": "pages_500", "severity": "critical", "label": "pages ont une erreur serveur (500)"},
    {"key": "pages_404", "severity": "critical", "label": "pages affichent une erreur (404)"},
    {"key": "broken_internal_links", "severity": "critical", "label": "liens internes pointent vers des pages inexistantes"},
    {"key": "missing_titles", "severity": "warning", "label": "pages n'ont pas de titre pour Google"},
    {"key": "missing_h1", "severity": "warning", "label": "pages n'ont pas de titre principal (H1)"},
    {"key": "duplicate_titles_count", "severity": "warning", "label": "groupes de pages partagent le meme titre"},
    {"key": "long_titles", "severity": "warning", "label": "titres sont trop longs et seront tronques par Google"},
    {"key": "missing_descriptions", "severity": "warning", "label": "pages n'ont pas de description pour Google"},
    {"key": "multiple_h1", "severity": "warning", "label": "pages ont plusieurs titres principaux (H1)"},
    {"key": "redirect_chains", "severity": "warning", "label": "pages passent par 2 redirections ou plus"},
    {"key": "images_without_alt", "severity": "info", "label": "images sont invisibles pour Google (pas de texte alternatif)"},
    {"key": "deep_pages", "severity": "info", "label": "pages sont a plus de 3 clics de profondeur"},
    {"key": "noindex_pages", "severity": "info", "label": "pages demandent a Google de ne pas les referencer"},
    {"key": "long_descriptions", "severity": "info", "label": "descriptions sont trop longues"},
]


async def compute_crawl_summary(audit_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Total crawled
        cur = await db.execute(
            "SELECT COUNT(*) as cnt FROM crawl_results WHERE audit_id = ?", (audit_id,)
        )
        total_crawled = (await cur.fetchone())["cnt"]

        if total_crawled == 0:
            return {"total_crawled": 0, "issues": []}

        # Status code counts
        cur = await db.execute("""
            SELECT status_code, COUNT(*) as cnt
            FROM crawl_results WHERE audit_id = ?
            GROUP BY status_code
        """, (audit_id,))
        status_counts = {row["status_code"]: row["cnt"] for row in await cur.fetchall()}

        pages_ok = status_counts.get(200, 0)
        pages_301 = status_counts.get(301, 0)
        pages_302 = status_counts.get(302, 0)
        pages_404 = status_counts.get(404, 0)
        pages_500 = sum(v for k, v in status_counts.items() if k and 500 <= k < 600)
        total_errors = sum(v for k, v in status_counts.items() if k and (k >= 400 or k == 0))

        # Redirect chains (2+ redirections)
        cur = await db.execute("""
            SELECT COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND redirect_chain IS NOT NULL
            AND json_array_length(redirect_chain) >= 2
        """, (audit_id,))
        redirect_chains = (await cur.fetchone())["cnt"]

        # Missing titles (on 200 HTML pages only)
        cur = await db.execute("""
            SELECT COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND status_code = 200
            AND content_type LIKE '%text/html%'
            AND (title IS NULL OR title = '')
        """, (audit_id,))
        missing_titles = (await cur.fetchone())["cnt"]

        # Long titles
        cur = await db.execute("""
            SELECT COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND status_code = 200 AND title_length > 60
        """, (audit_id,))
        long_titles = (await cur.fetchone())["cnt"]

        # Duplicate titles
        cur = await db.execute("""
            SELECT title, COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND status_code = 200
            AND title IS NOT NULL AND title != ''
            GROUP BY title HAVING cnt > 1
            ORDER BY cnt DESC LIMIT 20
        """, (audit_id,))
        dup_rows = await cur.fetchall()
        duplicate_titles = [{"title": r["title"], "count": r["cnt"]} for r in dup_rows]
        duplicate_titles_count = len(duplicate_titles)

        # Missing descriptions
        cur = await db.execute("""
            SELECT COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND status_code = 200
            AND content_type LIKE '%text/html%'
            AND (description IS NULL OR description = '')
        """, (audit_id,))
        missing_descriptions = (await cur.fetchone())["cnt"]

        # Long descriptions
        cur = await db.execute("""
            SELECT COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND status_code = 200 AND description_length > 160
        """, (audit_id,))
        long_descriptions = (await cur.fetchone())["cnt"]

        # Missing H1
        cur = await db.execute("""
            SELECT COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND status_code = 200
            AND content_type LIKE '%text/html%'
            AND h1_count = 0
        """, (audit_id,))
        missing_h1 = (await cur.fetchone())["cnt"]

        # Multiple H1
        cur = await db.execute("""
            SELECT COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND status_code = 200 AND h1_count > 1
        """, (audit_id,))
        multiple_h1 = (await cur.fetchone())["cnt"]

        # Images without alt
        cur = await db.execute("""
            SELECT SUM(images_without_alt) as cnt FROM crawl_results
            WHERE audit_id = ? AND status_code = 200
        """, (audit_id,))
        images_without_alt = (await cur.fetchone())["cnt"] or 0

        # Deep pages (depth > 3)
        cur = await db.execute("""
            SELECT COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND status_code = 200 AND depth > 3
        """, (audit_id,))
        deep_pages = (await cur.fetchone())["cnt"]

        # Noindex pages
        cur = await db.execute("""
            SELECT COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND is_noindex = 1
        """, (audit_id,))
        noindex_pages = (await cur.fetchone())["cnt"]

        # Broken internal links (links pointing to 404 pages)
        cur = await db.execute("""
            SELECT COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND status_code = 404 AND source = 'internal_link'
        """, (audit_id,))
        broken_internal_links = (await cur.fetchone())["cnt"]

        # Sitemap stats
        cur = await db.execute("""
            SELECT COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND source = 'sitemap'
        """, (audit_id,))
        sitemap_crawled = (await cur.fetchone())["cnt"]

        cur = await db.execute("""
            SELECT COUNT(*) as cnt FROM crawl_results
            WHERE audit_id = ? AND source = 'sitemap' AND status_code != 200
        """, (audit_id,))
        sitemap_errors = (await cur.fetchone())["cnt"]

    # Build stats dict
    stats = {
        "total_crawled": total_crawled,
        "total_errors": total_errors,
        "pages_ok": pages_ok,
        "pages_301": pages_301,
        "pages_302": pages_302,
        "pages_404": pages_404,
        "pages_500": pages_500,
        "redirect_chains": redirect_chains,
        "missing_titles": missing_titles,
        "long_titles": long_titles,
        "duplicate_titles": duplicate_titles,
        "duplicate_titles_count": duplicate_titles_count,
        "missing_descriptions": missing_descriptions,
        "long_descriptions": long_descriptions,
        "missing_h1": missing_h1,
        "multiple_h1": multiple_h1,
        "images_without_alt": images_without_alt,
        "deep_pages": deep_pages,
        "noindex_pages": noindex_pages,
        "broken_internal_links": broken_internal_links,
        "sitemap_urls": sitemap_crawled,
        "sitemap_errors": sitemap_errors,
    }

    # Build issues list (only non-zero, sorted by severity then count)
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    issues = []
    for defn in ISSUE_DEFS:
        count = stats.get(defn["key"], 0)
        if count > 0:
            issues.append({
                "key": defn["key"],
                "count": count,
                "severity": defn["severity"],
                "label": defn["label"],
            })
    issues.sort(key=lambda x: (severity_order[x["severity"]], -x["count"]))
    stats["issues"] = issues

    return stats
