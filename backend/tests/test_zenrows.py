"""Standalone ZenRows diagnostic script.

Run this directly to see exactly what ZenRows returns, without going
through Playwright, the agent pipeline, or any marketplace scraping logic.

Usage:
    python test_zenrows.py
    python test_zenrows.py "https://www.flipkart.com/search?q=samsung+phone"

Make sure your .env is loaded (either export the vars manually, or run
this with something like `python -m dotenv run -- python test_zenrows.py`,
or just paste your ZENROWS_API_KEY below temporarily for a quick check).
"""

from __future__ import annotations

import os
import sys
import time

import requests

# --- Load .env if python-dotenv is available; harmless if not installed ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("[info] python-dotenv not installed — relying on already-exported env vars.\n")

ZENROWS_ENDPOINT = "https://api.zenrows.com/v1/"

DEFAULT_TEST_URL = "https://www.amazon.in/s?k=samsung+phone+under+30000"


def zenrows_enabled() -> bool:
    return bool(os.getenv("ZENROWS_API_KEY", "").strip()) and os.getenv(
        "ZENROWS_ENABLED", "true"
    ).strip().lower() not in {"0", "false", "no", "off"}


def build_params(url: str, *, include_mode: bool) -> dict:
    params = {
        "apikey": os.environ["ZENROWS_API_KEY"].strip(),
        "url": url,
        "js_render": "true",
        "premium_proxy": "true",
        "proxy_country": os.getenv("ZENROWS_PROXY_COUNTRY", "in"),
        "wait": os.getenv("ZENROWS_WAIT_SECONDS", "3"),
    }
    if include_mode:
        params["mode"] = os.getenv("ZENROWS_MODE", "auto")
    return params


def redacted(params: dict) -> dict:
    safe = dict(params)
    if "apikey" in safe:
        key = safe["apikey"]
        safe["apikey"] = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
    return safe


def try_request(label: str, url: str, *, include_mode: bool, timeout: int = 25) -> None:
    print(f"\n{'=' * 70}")
    print(f"ATTEMPT: {label}")
    print(f"{'=' * 70}")

    params = build_params(url, include_mode=include_mode)
    print(f"Params sent: {redacted(params)}")

    start = time.time()
    try:
        response = requests.get(ZENROWS_ENDPOINT, params=params, timeout=timeout)
    except requests.RequestException as exc:
        elapsed = time.time() - start
        print(f"[NETWORK ERROR] after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
        return

    elapsed = time.time() - start
    print(f"Status code : {response.status_code}")
    print(f"Elapsed     : {elapsed:.1f}s")
    print(f"Response headers (selected):")
    for h in ("content-type", "content-length", "x-request-id", "zr-final-url", "zr-final-status"):
        if h in response.headers:
            print(f"  {h}: {response.headers[h]}")

    body_preview = response.text[:500].replace("\n", " ")
    print(f"Body preview (first 500 chars):\n  {body_preview}")

    if response.status_code == 200 and response.text.strip():
        print(f"\n>>> SUCCESS. Got {len(response.text)} chars of HTML back.")
    else:
        print(f"\n>>> FAILED. Status {response.status_code} — see body preview above for the real reason.")


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEST_URL

    print("ZenRows diagnostic test")
    print(f"Target URL: {url}")

    api_key = os.getenv("ZENROWS_API_KEY", "").strip()
    print(f"ZENROWS_API_KEY present: {bool(api_key)} (len={len(api_key)})")
    print(f"ZENROWS_ENABLED       : {os.getenv('ZENROWS_ENABLED', '<unset, defaults true>')}")
    print(f"ZENROWS_MODE          : {os.getenv('ZENROWS_MODE', '<unset, defaults auto>')}")
    print(f"ZENROWS_PROXY_COUNTRY : {os.getenv('ZENROWS_PROXY_COUNTRY', '<unset, defaults in>')}")
    print(f"ZENROWS_WAIT_SECONDS  : {os.getenv('ZENROWS_WAIT_SECONDS', '<unset, defaults 3>')}")

    if not zenrows_enabled():
        print("\n[ABORT] ZenRows is not enabled per zenrows_enabled() — check "
              "ZENROWS_API_KEY / ZENROWS_ENABLED in your environment.")
        return

    # Attempt 1: exactly what your current fetch_html() sends, including "mode".
    try_request("Current fetch_html() params (with 'mode')", url, include_mode=True)

    # Attempt 2: same request but with 'mode' removed, to test the hypothesis
    # that ZenRows rejects/ignores an unrecognized 'mode' param.
    try_request("Without 'mode' param", url, include_mode=False)

    # Attempt 3: minimal params only — just apikey + url + js_render, to
    # isolate whether ANY of the extra params (premium_proxy, proxy_country,
    # wait) are causing a rejection.
    print(f"\n{'=' * 70}")
    print("ATTEMPT: Minimal params only (apikey + url + js_render)")
    print(f"{'=' * 70}")
    minimal_params = {
        "apikey": os.environ["ZENROWS_API_KEY"].strip(),
        "url": url,
        "js_render": "true",
    }
    print(f"Params sent: {redacted(minimal_params)}")
    try:
        response = requests.get(ZENROWS_ENDPOINT, params=minimal_params, timeout=25)
        print(f"Status code: {response.status_code}")
        print(f"Body preview: {response.text[:500]}")
        if response.status_code == 200:
            print("\n>>> SUCCESS with minimal params.")
    except requests.RequestException as exc:
        print(f"[NETWORK ERROR] {type(exc).__name__}: {exc}")

    print(f"\n{'=' * 70}")
    print("Done. Compare the 3 attempts above:")
    print("  - If ALL fail with the same status/body -> likely an account issue")
    print("    (bad key, expired trial, quota exhausted, plan doesn't support")
    print("    js_render/premium_proxy).")
    print("  - If attempt 1 fails but 2/3 succeed -> the 'mode' param is the bug,")
    print("    just remove it from zenrows.py.")
    print("  - If all 3 fail differently -> read the body previews, ZenRows")
    print("    error bodies are usually a JSON with a clear 'message' field.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()