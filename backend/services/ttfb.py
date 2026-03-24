import statistics
import time

import httpx

from config import TTFB_BENCHMARKS


async def measure_ttfb(url: str, samples: int = 3) -> dict:
    results = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        for _ in range(samples):
            start = time.perf_counter()
            try:
                await client.head(url)
            except httpx.RequestError:
                await client.get(url)
            elapsed = time.perf_counter() - start
            results.append(round(elapsed, 3))

    median = statistics.median(results)
    return {
        "ttfb_seconds": round(median, 3),
        "samples": results,
        "verdict": classify_ttfb(median),
    }


def classify_ttfb(seconds: float) -> str:
    if seconds <= TTFB_BENCHMARKS["excellent"]:
        return "excellent"
    if seconds <= TTFB_BENCHMARKS["bon"]:
        return "bon"
    if seconds <= TTFB_BENCHMARKS["moyen"]:
        return "moyen"
    return "mauvais"
