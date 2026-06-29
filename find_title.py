"""
Run: python find_title.py
Searches the full card HTML for the actual product title text.
"""

import time
from playwright.sync_api import sync_playwright

QUERY = "Apple iPhone 17 Pro 256GB"

# These are strings we KNOW should appear in a real iPhone 17 Pro title
TITLE_HINTS = ["iphone 17", "iphone17", "pro max", "titanium", "256gb", "512gb", "128gb"]

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        viewport={"width": 1280, "height": 800},
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
    page = context.new_page()

    url = "https://www.amazon.in/s?k=" + QUERY.replace(" ", "+")
    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    time.sleep(3)

    items = page.query_selector_all('[data-component-type="s-search-result"]')
    print(f"Cards found: {len(items)}\n")

    for idx, item in enumerate(items[:5]):
        print(f"\n{'='*60}")
        print(f"CARD #{idx+1}")
        print(f"{'='*60}")

        full_html = item.inner_html().lower()

        # Check if this card even contains iPhone title text
        has_title = any(hint in full_html for hint in TITLE_HINTS)
        print(f"Contains iPhone title text: {has_title}")

        if not has_title:
            print("  → Skipping (no title hints found, likely a sponsored/unrelated card)")
            continue

        # ── Try every possible text-bearing element ──────────────
        TEXT_SELECTORS = [
            # aria-label on image (Amazon often puts full title here)
            "img.s-image",

            # data-cy based spans
            "[data-cy='title-recipe'] span",
            "[data-cy='title-recipe'] a",

            # Common span classes for titles
            "span.a-size-medium.a-color-base.a-text-normal",
            "span.a-size-base.a-color-base.a-text-normal",
            "span.a-size-large.a-color-base.a-text-normal",
            "span.a-size-medium-plus.a-color-base.a-text-normal",
            "span.a-size-base-plus.a-color-base.a-text-normal",

            # All spans with a-text-normal
            "span.a-text-normal",

            # puis card title
            ".puis-card-container span.a-text-normal",
            ".s-card-container span.a-text-normal",

            # Product title div
            "div.s-title-instructions-style span",
            "div[data-cy='title-recipe']",

            # Link with full title
            "a.a-link-normal.s-underline-text",
            "a.a-link-normal.s-line-clamp-2",
            "a.a-link-normal.s-line-clamp-3",
            "a.a-link-normal.s-line-clamp-4",
        ]

        print("\n  Elements containing iPhone-related text:")
        found_any = False

        for sel in TEXT_SELECTORS:
            try:
                els = item.query_selector_all(sel)
                for el in els:
                    # Check inner_text
                    text = el.inner_text().strip() if sel != "img.s-image" else ""
                    aria = el.get_attribute("aria-label") or ""
                    alt  = el.get_attribute("alt") or ""
                    title_attr = el.get_attribute("title") or ""

                    candidates = [text, aria, alt, title_attr]
                    for val in candidates:
                        if val and any(hint in val.lower() for hint in TITLE_HINTS):
                            attr_name = (
                                "text" if val == text else
                                "aria-label" if val == aria else
                                "alt" if val == alt else "title"
                            )
                            print(f"\n    ✓ SELECTOR : {sel}")
                            print(f"      ATTRIBUTE: {attr_name}")
                            print(f"      VALUE    : {val[:120]}")
                            found_any = True
            except Exception as e:
                pass

        if not found_any:
            print("  ✗ None of the selectors found the title!")
            print("\n  Dumping ALL text nodes in card:")
            # Get all elements and print their text
            all_els = item.query_selector_all("span, a, div, p")
            for el in all_els:
                try:
                    t = el.inner_text().strip()
                    if t and len(t) > 15 and any(hint in t.lower() for hint in TITLE_HINTS):
                        tag = el.evaluate("el => el.tagName")
                        cls = el.get_attribute("class") or ""
                        print(f"    TAG={tag} CLASS='{cls[:60]}' TEXT='{t[:100]}'")
                except:
                    pass

    browser.close()
    print("\n\nDone.")