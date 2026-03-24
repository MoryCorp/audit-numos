import os
from collections import defaultdict
from urllib.parse import urlparse

from playwright.async_api import async_playwright


async def capture_homepage(url: str, output_path: str) -> dict:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    requests_log = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        async def handle_response(response):
            try:
                headers = response.headers
                size = int(headers.get("content-length", 0))
                if size == 0:
                    try:
                        body = await response.body()
                        size = len(body)
                    except Exception:
                        pass
                requests_log.append({
                    "url": response.url,
                    "status": response.status,
                    "size": size,
                    "type": response.request.resource_type,
                })
            except Exception:
                pass

        page.on("response", handle_response)

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception:
            await page.goto(url, wait_until="load", timeout=30000)

        await page.screenshot(path=output_path, full_page=False)
        await browser.close()

    by_type = aggregate_by_type(requests_log)
    base_domain = urlparse(url).netloc
    third_party = [r for r in requests_log if not is_same_domain(r["url"], base_domain)]
    unoptimized_images = find_unoptimized_images(requests_log)

    total_size = sum(r["size"] for r in requests_log)

    return {
        "screenshot_path": output_path,
        "total_requests": len(requests_log),
        "total_size_bytes": total_size,
        "by_type": by_type,
        "third_party_count": len(third_party),
        "third_party_size_bytes": sum(r["size"] for r in third_party),
        "unoptimized_images": unoptimized_images,
    }


def aggregate_by_type(requests_log: list[dict]) -> dict:
    by_type = defaultdict(lambda: {"count": 0, "size_bytes": 0})
    type_mapping = {
        "image": "images",
        "script": "js",
        "stylesheet": "css",
        "font": "fonts",
        "document": "html",
    }
    for r in requests_log:
        category = type_mapping.get(r["type"], "other")
        by_type[category]["count"] += 1
        by_type[category]["size_bytes"] += r["size"]
    return dict(by_type)


def is_same_domain(request_url: str, base_domain: str) -> bool:
    try:
        return urlparse(request_url).netloc.endswith(base_domain)
    except Exception:
        return False


def find_unoptimized_images(requests_log: list[dict]) -> dict:
    large_images = []
    for r in requests_log:
        if r["type"] != "image":
            continue
        if r["size"] < 200_000:
            continue
        url_lower = r["url"].lower()
        if any(url_lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".bmp")):
            large_images.append({
                "url": r["url"],
                "size_bytes": r["size"],
            })
    return {
        "count": len(large_images),
        "total_size_bytes": sum(img["size_bytes"] for img in large_images),
        "images": large_images[:20],
    }
