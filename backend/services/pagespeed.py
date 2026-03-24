import httpx

from config import settings


async def run_pagespeed(url: str, strategy: str = "mobile") -> dict:
    params = {
        "url": url,
        "key": settings.google_api_key,
        "strategy": strategy,
        "category": ["performance", "seo"],
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


def extract_crux(psi_response: dict) -> dict:
    result = {"url": None, "origin": None}

    loading = psi_response.get("loadingExperience", {})
    if loading.get("metrics"):
        result["url"] = {
            "overall_category": loading.get("overall_category"),
            "metrics": loading.get("metrics", {}),
        }

    origin = psi_response.get("originLoadingExperience", {})
    if origin.get("metrics"):
        result["origin"] = {
            "overall_category": origin.get("overall_category"),
            "metrics": origin.get("metrics", {}),
        }

    return result


def extract_lighthouse_metrics(psi_response: dict) -> dict:
    lighthouse = psi_response.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    audits = lighthouse.get("audits", {})

    perf = categories.get("performance", {})
    seo = categories.get("seo", {})

    def get_audit_value(key: str):
        audit = audits.get(key, {})
        return {
            "score": audit.get("score"),
            "value": audit.get("numericValue"),
            "display": audit.get("displayValue"),
        }

    return {
        "performance_score": perf.get("score"),
        "seo_score": seo.get("score"),
        "lcp": get_audit_value("largest-contentful-paint"),
        "cls": get_audit_value("cumulative-layout-shift"),
        "tbt": get_audit_value("total-blocking-time"),
        "speed_index": get_audit_value("speed-index"),
        "tti": get_audit_value("interactive"),
        "ttfb": get_audit_value("server-response-time"),
    }
