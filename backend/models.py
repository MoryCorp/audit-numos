from pydantic import BaseModel, Field, HttpUrl


class AuditCreate(BaseModel):
    url: HttpUrl
    # notify=True par defaut pour ne rien changer aux appels existants.
    notify: bool = True
    crawl: bool = True
    crawl_limit: int | None = Field(default=None, ge=1, le=5000)


class BulkAuditCreate(BaseModel):
    urls: list[HttpUrl] = Field(..., min_length=1, max_length=200)
    # Le bulk sert a qualifier une liste : on audite d'abord, on decide
    # d'envoyer ensuite. Pas de webhook sauf demande explicite.
    notify: bool = False
    crawl: bool = True
    crawl_limit: int | None = Field(default=None, ge=1, le=5000)


class BulkAuditResult(BaseModel):
    created: list[dict]
    skipped: list[dict]


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
    tech_fingerprint: dict | None = None
