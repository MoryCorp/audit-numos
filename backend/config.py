from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///data/numos-audit.db"
    screenshots_dir: str = "/data/screenshots"
    host: str = "0.0.0.0"
    port: int = 8000
    max_concurrent_crawls: int = 5
    default_crawl_limit: int = 5000
    cors_origins: str = "https://audit.numos.fr"
    admin_token: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

TTFB_BENCHMARKS = {
    "excellent": 0.2,
    "bon": 0.5,
    "moyen": 1.0,
    "mauvais": 2.0,
}

PAGE_WEIGHT_BENCHMARKS = {
    "total_mb": 2.0,
    "requests": 50,
}

CRAWLER_DEFAULTS = {
    "max_urls": 500,
    "max_concurrent_requests": 10,
    "request_timeout": 10,
    "delay_between_requests": 0.1,
    "max_depth": 5,
    "commit_batch_size": 50,
    "user_agent": "NumosAuditBot/1.0 (+https://numos.fr)",
}
