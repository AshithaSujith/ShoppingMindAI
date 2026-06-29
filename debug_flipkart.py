"""
Run: python debug_flipkart2.py
Finds price, rating, title from Flipkart's new card structure.
"""

import time
from playwright.sync_api import sync_playwright

QUERY = "Apple iPhone 17 Pro 256GB"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="en-IN", timezone_id="Asia/Kolkata", viewport={"width": 1280, "height": 800},
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
    page = context.new_page()

    url = "https://www.flipkart.com/search?q=" + QUERY.replace(" ", "+")
    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    time.sleep(3)

    # Scroll to load lazy content
    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    time.sleep(1)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.5)

    items = page.query_selector_all("div[data-id]")
    print(f"Cards found: {len(items)}\n")

    for idx, item in enumerate(items[:3]):
        print(f"\n{'='*60}")
        print(f"CARD #{idx+1}")
        print(f"{'='*60}")

        # Print ALL text nodes with their class names
        print("\n  ALL elements with text:")
        all_els = item.query_selector_all("*")
        for el in all_els:
            try:
                text = el.inner_text().strip()
                cls = el.get_attribute("class") or ""
                tag = el.evaluate("e => e.tagName").lower()
                # Only show leaf nodes with useful text
                if text and len(text) < 200 and "\n" not in text and len(text) > 1:
                    print(f"    <{tag} class='{cls[:50]}'> → '{text[:80]}'")
            except:
                pass

        print(f"\n  Full HTML (first 1500 chars):")
        html = item.inner_html()
        print(html[:1500])
        print()

    browser.close()
    print("Done.")