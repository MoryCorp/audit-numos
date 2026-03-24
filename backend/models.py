from pydantic import BaseModel, HttpUrl


class AuditCreate(BaseModel):
    url: HttpUrl


class AuditListItem(BaseModel):
    id: str
    url: str
    domain: str
    status: str
    created_at: str
    numos_score: dict | None = None


class AuditProgress(BaseModel):
    id: str
    status: str
    crawl_status: str | None = None
    crawl_progress: dict | None = None


class AuditResponse(BaseModel):
    id: str
    url: str
    domain: str
    status: str
    created_at: str
    updated_at: str | None = None
    pagespeed_mobile: dict | None = None
    pagespeed_desktop: dict | None = None
    crux_url: dict | None = None
    crux_origin: dict | None = None
    ttfb_data: dict | None = None
    screenshot_path: str | None = None
    page_weight_data: dict | None = None
    crawl_status: str | None = None
    crawl_progress: dict | None = None
    sitemap_data: dict | None = None
    crawl_summary: dict | None = None
    numos_score: dict | None = None
