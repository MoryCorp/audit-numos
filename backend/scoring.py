def calculate_numos_score(
    pagespeed_mobile: dict | None,
    pagespeed_desktop: dict | None,
    crux_data: dict | None,
    ttfb: dict | None,
    crawl_stats: dict | None = None,
) -> dict:
    scores = {}

    # Performance mobile : score Lighthouse /100
    if pagespeed_mobile:
        categories = pagespeed_mobile.get("lighthouseResult", {}).get("categories", {})
        perf = categories.get("performance", {})
        raw = perf.get("score")
        scores["performance"] = (raw * 100) if raw is not None else 50
    else:
        scores["performance"] = 50

    # CrUX : moyenne des verdicts
    crux_metrics = None
    if crux_data:
        crux_metrics = crux_data.get("metrics") if isinstance(crux_data, dict) else None

    if crux_metrics:
        verdict_map = {"FAST": 100, "AVERAGE": 50, "SLOW": 0}
        crux_verdicts = []
        for metric in crux_metrics.values():
            if isinstance(metric, dict):
                cat = metric.get("category", "")
                crux_verdicts.append(verdict_map.get(cat, 50))
        scores["crux"] = sum(crux_verdicts) / len(crux_verdicts) if crux_verdicts else None
    else:
        scores["crux"] = None

    # TTFB : echelle lineaire inversee
    if ttfb and "ttfb_seconds" in ttfb:
        ttfb_s = ttfb["ttfb_seconds"]
        if ttfb_s <= 0.2:
            scores["ttfb"] = 100
        elif ttfb_s >= 3.0:
            scores["ttfb"] = 0
        else:
            scores["ttfb"] = max(0, 100 - ((ttfb_s - 0.2) / 2.8) * 100)
    else:
        scores["ttfb"] = 50

    # SEO crawl (Phase 2)
    if crawl_stats and crawl_stats.get("total_crawled", 0) > 0:
        total_pages = crawl_stats["total_crawled"]
        issues = (
            crawl_stats.get("pages_404", 0) * 3
            + crawl_stats.get("pages_500", 0) * 5
            + crawl_stats.get("missing_titles", 0) * 2
            + crawl_stats.get("duplicate_titles_count", 0) * 1
            + crawl_stats.get("missing_descriptions", 0) * 1
            + crawl_stats.get("missing_h1", 0) * 2
            + crawl_stats.get("multiple_h1", 0) * 0.5
            + crawl_stats.get("broken_internal_links", 0) * 2
        )
        issue_ratio = min(issues / (total_pages * 2), 1.0)
        scores["seo"] = max(0, (1 - issue_ratio) * 100)
    else:
        scores["seo"] = None

    # Ponderation selon les donnees disponibles
    has_crux = scores["crux"] is not None
    has_seo = scores["seo"] is not None

    if has_seo and has_crux:
        weights = {"performance": 0.35, "crux": 0.20, "ttfb": 0.10, "seo": 0.35}
    elif has_seo and not has_crux:
        weights = {"performance": 0.50, "ttfb": 0.15, "seo": 0.35}
    elif not has_seo and has_crux:
        weights = {"performance": 0.55, "crux": 0.30, "ttfb": 0.15}
    else:
        weights = {"performance": 0.80, "ttfb": 0.20}

    global_score = sum(
        scores[k] * weights[k]
        for k in weights
        if scores.get(k) is not None
    )

    return {
        "global": round(global_score),
        "pillars": {
            "performance": round(scores["performance"]),
            "crux": round(scores["crux"]) if scores["crux"] is not None else None,
            "ttfb": round(scores["ttfb"]),
            "seo": round(scores["seo"]) if scores["seo"] is not None else None,
        },
        "weights_used": weights,
    }
