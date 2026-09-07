"""ZenRows Fetch integration used as a fallback for blocked/dynamic pages."""

from __future__ import annotations

import os
import time
from typing import Optional

import requests


ZENROWS_ENDPOINT = "https://api.zenrows.com/v1/"


def zenrows_enabled() -> bool:
    return bool(os.getenv("ZENROWS_API_KEY", "").strip()) and os.getenv(
        "ZENROWS_ENABLED", "true"
    ).strip().lower() not in {"0", "false", "no", "off"}


def fetch_html(url: str, *, timeout: int = 20) -> Optional[str]:
    """Fetch rendered HTML through ZenRows, returning None on unavailable service.

    ZenRows' adaptive mode escalates the request when a site needs rendering or
    premium proxies. The API key is never included in logs or exceptions.
    """
    if not zenrows_enabled():
        return None

    params = {
        "apikey": os.environ["ZENROWS_API_KEY"].strip(),
        "url": url,
        "mode": os.getenv("ZENROWS_MODE", "auto"),
        "js_render": "true",
        "premium_proxy": "true",
        "proxy_country": os.getenv("ZENROWS_PROXY_COUNTRY", "in"),
        "wait": os.getenv("ZENROWS_WAIT_SECONDS", "3"),
    }
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(ZENROWS_ENDPOINT, params=params, timeout=timeout)
            if response.status_code == 200 and response.text.strip():
                return response.text
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < 2:
            time.sleep(2**attempt)

    # Do not leak response bodies or credentials into application logs.
    if last_error:
        print(f"[ZenRows] Fetch failed after retries: {type(last_error).__name__}", flush=True)
    return None