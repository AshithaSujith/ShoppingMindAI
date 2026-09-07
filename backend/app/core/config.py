import os
from functools import lru_cache
from typing import Any


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_cors_origins(raw: str | None) -> list[str]:
    if not raw:
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> dict[str, Any]:
    settings = {
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "agent_mode": _env_bool("AGENT_MODE", True),
        "auto_create_tables": _env_bool("AUTO_CREATE_TABLES", True),
        "cors_origins": _parse_cors_origins(os.getenv("CORS_ORIGINS")),
    }
    return settings
