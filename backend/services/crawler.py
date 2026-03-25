import asyncio
import json
import logging
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

from database import bulk_insert_crawl_results, update_audit
from services.sitemap import discover_sitemap

logger = logging.getLogger(__name__)


class SEOCrawler:
    def __init__(self, audit_id: str, base_url: str, config: dict):
        self.audit_id = audit_id
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.config = config

        self.seen_urls: set[str] = set()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.results: list[dict] = []
        self.crawled = 0
        self.errors = 0
        self._stopped = False

    async def run(self):
        try:
            # Discover sitemap
            sitemap_data = await discover_sitemap(self.base_url)
            await update_audit(self.audit_id, sitemap_data=sitemap_data)

            # Seed URLs
            self._enqueue(self.base_url, depth=0, source="seed")
            for url in sitemap_data.get("urls", []):
                self._enqueue(url, depth=0, source="sitemap")

            logger.info(f"Crawl {self.audit_id}: {self.queue.qsize()} URLs en queue (sitemap: {len(sitemap_data.get('urls', []))})")

            # Run workers
            connector = aiohttp.TCPConnector(limit=self.config["max_concurrent_requests"])
            timeout = aiohttp.ClientTimeout(total=self.config["request_timeout"])
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                workers = [
                    asyncio.create_task(self._worker(session))
                    for _ in range(self.config["max_concurrent_requests"])
                ]
                await self.queue.join()
                for w in workers:
                    w.cancel()

            # Flush remaining results
            if self.results:
                await self._flush()

            await self._update_progress()
            logger.info(f"Crawl {self.audit_id} termine: {self.crawled} pages, {self.errors} erreurs")

        except Exception as e:
            logger.error(f"Crawl {self.audit_id} echoue: {e}")
            raise

    def stop(self):
        self._stopped = True

    async def _worker(self, session: aiohttp.ClientSession):
        while True:
            url, depth, source = await self.queue.get()
            try:
                if not self._stopped and self.crawled < self.config["max_urls"]:
                    await self._process_url(session, url, depth, source)
                    if len(self.results) >= self.config["commit_batch_size"]:
                        await self._flush()
                        await self._update_progress()
                    await asyncio.sleep(self.config["delay_between_requests"])
            except Exception as e:
                logger.debug(f"Worker error on {url}: {e}")
                self.errors += 1
            finally:
                self.queue.task_done()

    async def _process_url(self, session: aiohttp.ClientSession, url: str, depth: int, source: str):
        result = {
            "url": url,
            "final_url": url,
            "status_code": 0,
            "redirect_chain": [],
            "depth": depth,
            "source": source,
            "content_type": "",
            "error": None,
            "title": None,
            "title_length": 0,
            "description": None,
            "description_length": 0,
            "h1s": [],
            "h1_count": 0,
            "canonical": None,
            "is_noindex": False,
            "images_total": 0,
            "images_without_alt": 0,
            "internal_links_count": 0,
        }

        try:
            async with session.get(
                url,
                allow_redirects=True,
                max_redirects=5,
                headers={"User-Agent": self.config["user_agent"]},
            ) as resp:
                result["status_code"] = resp.status
                result["final_url"] = str(resp.url)
                result["content_type"] = resp.headers.get("content-type", "")

                if resp.history:
                    result["redirect_chain"] = [
                        {"url": str(r.url), "status": r.status}
                        for r in resp.history
                    ]

                if resp.status == 200 and "text/html" in result["content_type"]:
                    try:
                        body = await resp.text(errors="replace")
                        seo = self._parse_html(body, url)
                        result.update(seo)

                        if depth < self.config["max_depth"]:
                            for link in seo.get("_internal_links", []):
                                self._enqueue(link, depth + 1, "internal_link")
                    except Exception as e:
                        logger.debug(f"Parse error {url}: {e}")

        except asyncio.TimeoutError:
            result["error"] = "timeout"
            self.errors += 1
        except aiohttp.ClientError as e:
            result["error"] = str(e)[:200]
            self.errors += 1
        except Exception as e:
            result["error"] = str(e)[:200]
            self.errors += 1

        result.pop("_internal_links", None)
        self.results.append(result)
        self.crawled += 1

    def _parse_html(self, html: str, url: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")

        # Title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None

        # H1
        h1_tags = soup.find_all("h1")
        h1s = [h.get_text(strip=True) for h in h1_tags]

        # Canonical
        canonical_tag = soup.find("link", attrs={"rel": "canonical"})
        canonical = canonical_tag["href"] if canonical_tag and canonical_tag.get("href") else None

        # Noindex
        meta_robots = soup.find("meta", attrs={"name": "robots"})
        robots_content = meta_robots["content"].lower() if meta_robots and meta_robots.get("content") else ""
        is_noindex = "noindex" in robots_content

        # Images
        images = soup.find_all("img")
        images_without_alt = [img for img in images if not img.get("alt")]

        # Internal links
        internal_links = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            absolute = urljoin(url, href)
            parsed = urlparse(absolute)
            if parsed.netloc == self.domain and parsed.scheme in ("http", "https"):
                clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/') or '/'}"
                if parsed.query:
                    clean += f"?{parsed.query}"
                internal_links.add(clean)

        return {
            "title": title,
            "title_length": len(title) if title else 0,
            "description": description,
            "description_length": len(description) if description else 0,
            "h1s": h1s,
            "h1_count": len(h1s),
            "canonical": canonical,
            "is_noindex": is_noindex,
            "images_total": len(images),
            "images_without_alt": len(images_without_alt),
            "internal_links_count": len(internal_links),
            "_internal_links": list(internal_links),
        }

    def _enqueue(self, url: str, depth: int, source: str):
        normalized = self._normalize_url(url)
        if not normalized or normalized in self.seen_urls:
            return
        if urlparse(normalized).netloc != self.domain:
            return
        self.seen_urls.add(normalized)
        self.queue.put_nowait((normalized, depth, source))

    @staticmethod
    def _normalize_url(url: str) -> str | None:
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return None
            path = parsed.path.rstrip("/") or "/"
            normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
            if parsed.query:
                normalized += f"?{parsed.query}"
            return normalized
        except Exception:
            return None

    async def _flush(self):
        if not self.results:
            return
        await bulk_insert_crawl_results(self.audit_id, self.results)
        self.results = []

    async def _update_progress(self):
        await update_audit(self.audit_id, crawl_progress={
            "crawled": self.crawled,
            "queued": self.queue.qsize(),
            "errors": self.errors,
        })
