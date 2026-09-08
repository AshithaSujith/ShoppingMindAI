"""ZenRows Fetch integration used as a fallback for blocked/dynamic pages.

Tiered strategy (confirmed via manual testing against all 5 marketplaces,
Sept 2026):
  - Tier 1 (js_render only): works for Flipkart, Croma, Reliance Digital.
    Amazon and Tata CLiQ reject this with 400 REQS002 ("requires premium
    proxies"), so tier 1 fails fast for them (~2s) and we escalate.
  - Tier 2 (+ premium_proxy, proxy_country, wait): required for Amazon and
    Tata CLiQ. For Flipkart and Reliance Digital, adding premium_proxy
    causes the request to hang and time out instead of failing cleanly --
    so we only use it as a fallback, never as the first attempt.

"mode" is NOT a valid ZenRows API param -- sending it causes every request
to fail immediately with 400 REQS004 ("Invalid params provided"). Do not
reintroduce it.
"""

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


def _attempt(params: dict, *, timeout: int, retries: int, label: str) -> tuple[Optional[str], Optional[Exception]]:
    """Try one param tier, with its own short retry loop. Returns (html, last_error)."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(ZENROWS_ENDPOINT, params=params, timeout=timeout)
            if response.status_code == 200 and response.text.strip():
                return response.text, None
            snippet = response.text[:200].replace("\n", " ")
            last_error = RuntimeError(f"HTTP {response.status_code}: {snippet}")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < retries - 1:
            time.sleep(2**attempt)
    if last_error:
        print(f"[ZenRows] {label} failed after {retries} attempt(s): {last_error}", flush=True)
    return None, last_error


def fetch_html(url: str, *, timeout: int = 20) -> Optional[str]:
    """Fetch rendered HTML through ZenRows, returning None on unavailable service.

    Tries a cheap tier (js_render only) first, and only escalates to the
    slower/costlier premium_proxy tier if the cheap tier fails. This avoids
    paying the premium_proxy latency penalty for sites that don't need it,
    while still supporting sites (Amazon, Tata CLiQ) that require it.

    The API key is never included in logs or exceptions.
    """
    if not zenrows_enabled():
        return None

    api_key = os.environ["ZENROWS_API_KEY"].strip()
    base_params = {
        "apikey": api_key,
        "url": url,
        "js_render": "true",
    }

    # Tier 1: cheap and fast. Sufficient for Flipkart, Croma, Reliance Digital.
    html, _ = _attempt(base_params, timeout=timeout, retries=2, label="Tier 1 (js_render)")
    if html:
        return html

    # Tier 2: adds premium_proxy. Required for Amazon and Tata CLiQ.
    # Only reached after tier 1 has already failed, so we don't pay this
    # tier's latency/timeout cost for sites that don't need it.
    premium_params = {
        **base_params,
        "premium_proxy": "true",
        "proxy_country": os.getenv("ZENROWS_PROXY_COUNTRY", "in"),
        "wait": os.getenv("ZENROWS_WAIT_SECONDS", "3"),
    }
    html, _ = _attempt(premium_params, timeout=timeout, retries=2, label="Tier 2 (premium_proxy)")
    return html