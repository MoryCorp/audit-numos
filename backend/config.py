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
