import os
from typing import Dict, Any


def get_settings() -> Dict[str, Any]:
    """
    Load application settings from environment variables with sensible defaults.
    """
    default_cors = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001"
    )
    return {
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "agent_mode": os.getenv("AGENT_MODE", "false").lower() in ("true", "1", "yes"),
        "auto_create_tables": os.getenv("AUTO_CREATE_TABLES", "true").lower() in ("true", "1", "yes"),
        "cors_origins": [
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", default_cors).split(",")
            if origin.strip()
        ],
        "database_url": os.getenv(
            "DATABASE_URL",
            "postgresql://user:password@localhost:5432/shoppingmindai"
        ),
    }
