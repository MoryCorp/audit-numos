import logging
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

SITEMAP_PATHS = [
    "/sitemap_index.xml",
    "/sitemap.xml",
    "/wp-sitemap.xml",
]


async def discover_sitemap(base_url: str) -> dict:
    base = base_url.rstrip("/")
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        # 1. Check robots.txt
        try:
            resp = await client.get(f"{base}/robots.txt")
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    stripped = line.strip()
                    if stripped.lower().startswith("sitemap:"):
                        sitemap_url = stripped.split(":", 1)[1].strip()
                        result = await _parse_sitemap(client, sitemap_url)
                        if result["urls"]:
                            return {**result, "source": "robots.txt"}
        except Exception as e:
            logger.debug(f"robots.txt failed for {base}: {e}")

        # 2. Try standard paths
        for path in SITEMAP_PATHS:
            url = f"{base}{path}"
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and "xml" in resp.headers.get("content-type", ""):
                    result = await _parse_sitemap(client, url)
                    if result["urls"]:
                        return {**result, "source": "standard_path"}
            except Exception:
                continue

    return {"sitemap_url": None, "urls": [], "is_index": False, "source": "not_found"}


async def _parse_sitemap(client: httpx.AsyncClient, sitemap_url: str) -> dict:
    try:
        resp = await client.get(sitemap_url, timeout=30)
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)
    except Exception as e:
        logger.warning(f"Failed to parse sitemap {sitemap_url}: {e}")
        return {"sitemap_url": sitemap_url, "urls": [], "is_index": False}

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    # Check if sitemap index
    sub_sitemaps = root.findall(".//sm:sitemap/sm:loc", ns)
    if sub_sitemaps:
        all_urls = []
        for sub in sub_sitemaps[:50]:  # limit sub-sitemaps
            sub_result = await _parse_sitemap(client, sub.text.strip())
            all_urls.extend(sub_result["urls"])
        return {"sitemap_url": sitemap_url, "urls": all_urls, "is_index": True}

    # Simple sitemap
    urls = []
    for loc in root.findall(".//sm:url/sm:loc", ns):
        if loc.text:
            urls.append(loc.text.strip())

    return {"sitemap_url": sitemap_url, "urls": urls, "is_index": False}
