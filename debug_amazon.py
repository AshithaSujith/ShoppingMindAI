"""
Run this script directly:  python debug_amazon.py
It will print the exact HTML structure Amazon is serving you,
so we can identify the correct title selector.
"""

import time
from playwright.sync_api import sync_playwright

QUERY = "Apple iPhone 17 Pro 256GB"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--window-size=1280,800",
        ]
    )

    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        viewport={"width": 1280, "height": 800},
    )

    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )

    page = context.new_page()
    url = "https://www.amazon.in/s?k=" + QUERY.replace(" ", "+")
    print(f"\nOpening: {url}\n")

    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    time.sleep(3)

    print(f"Page title: {page.title()}\n")
    print("=" * 60)

    # ── 1. How many result cards found? ──────────────────────────
    items = page.query_selector_all('[data-component-type="s-search-result"]')
    print(f"Result cards found: {len(items)}\n")

    if not items:
        print("NO CARDS FOUND. Dumping full page HTML (first 3000 chars):\n")
        print(page.content()[:3000])
        browser.close()
        exit()

    # ── 2. Inspect first 3 cards in detail ───────────────────────
    for idx, item in enumerate(items[:3]):
        print(f"\n{'─'*60}")
        print(f"CARD #{idx + 1}")
        print(f"{'─'*60}")

        # (a) Try every selector we care about
        SELECTORS = [
            "h2.a-size-mini a span.a-text-normal",
            "h2.a-size-mini a span",
            "h2.a-size-mini span.a-text-normal",
            "h2.a-size-base-plus a span",
            "h2.a-size-medium a span",
            "h2 a span.a-text-normal",
            "h2 a span",
            "h2 span.a-text-normal",
            "h2 span",
            "[data-cy='title-recipe'] h2 a span",
            "[data-cy='title-recipe'] span",
            "h2 a",          # will read aria-label
        ]

        print("\n  Selector probe results:")
        for sel in SELECTORS:
            el = item.query_selector(sel)
            if el:
                text = el.inner_text().strip() or el.get_attribute("aria-label") or ""
                print(f"    ✓  {sel:<50}  →  '{text[:80]}'")
            else:
                print(f"    ✗  {sel}")

        # (b) Dump the raw h2 HTML so we can see exact class names
        h2 = item.query_selector("h2")
        if h2:
            print(f"\n  Raw <h2> HTML:\n    {h2.inner_html()[:600]}")
        else:
            print("\n  No <h2> found in this card!")

        # (c) Dump full card HTML (truncated) for complete picture
        print(f"\n  Full card HTML (first 1200 chars):")
        card_html = item.inner_html()
        for line in card_html[:1200].split("\n"):
            print(f"    {line}")

    # ── 3. Save full page HTML to file for offline inspection ─────
    with open("amazon_page_dump.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    print("\n\nFull page HTML saved to: amazon_page_dump.html")
    print("Open it in a browser or text editor for complete inspection.\n")

    browser.close()