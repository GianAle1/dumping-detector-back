import os


class Config:
    """Application configuration loaded from environment variables."""

    DEBUG = os.environ.get("DEBUG", "false").lower() in {"1", "true", "t", "yes"}
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    CELERY_BROKER_URL = os.environ.get(
        "CELERY_BROKER_URL", "redis://localhost:6379/0"
    )
    CELERY_RESULT_BACKEND = os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
    )
    _origins = os.environ.get("ALLOWED_ORIGINS", "*")
    if _origins == "*":
        ALLOWED_ORIGINS = "*"
    else:
        ALLOWED_ORIGINS = [origin.strip() for origin in _origins.split(",") if origin.strip()]
