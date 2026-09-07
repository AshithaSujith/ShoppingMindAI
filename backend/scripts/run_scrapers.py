"""
OttixHow – New Platform Scrapers
Platforms: Croma, Myntra, Nykaa, BigBasket, JioMart, Meesho, Reliance Digital
Follows the same pattern as scrape_amazon / scrape_flipkart in scraper.py
Import and call these exactly like the existing scrapers.
"""

import re
import random
import time

from playwright.sync_api import sync_playwright

# ── Import shared utilities from your existing scraper.py ──────────────────
from scraper import (
    sanitize_search_query,
    calculate_match_score,
    get_minimum_score,
    validate_price,
    parse_price,
    calc_discount,
    finalize_products,
    make_empty_result,
    launch_browser,
    remove_duplicates,
)


# =========================================================
# PRICE / TITLE SELECTORS  (platform-specific)
# =========================================================

# ── Croma ─────────────────────────────────────────────────
CROMA_ITEM_SELECTORS   = ["li.product-item", "div.product-item", "div[class*='product-item']"]
CROMA_TITLE_SELECTORS  = ["h3.product-title a", "h3.product-title", "a.product-title", "h3 a"]
CROMA_PRICE_SELECTORS  = ["span.amount", "span[class*='price']", "div[class*='price'] span"]
CROMA_ORIG_SELECTORS   = ["span.strike-through span.amount", "span[class*='old'] span.amount"]

# ── Myntra ────────────────────────────────────────────────
MYNTRA_ITEM_SELECTORS  = ["li.product-base", "li[class*='product-base']", "div[class*='product-base']"]
MYNTRA_TITLE_SELECTORS = ["h3.product-brand", "h4.product-product", "p.product-product",
                           "a[class*='product-base']"]
MYNTRA_PRICE_SELECTORS = ["span.product-discountedPrice", "div[class*='price'] span",
                           "span[class*='discounted']"]
MYNTRA_ORIG_SELECTORS  = ["span.product-strike", "span[class*='strike']"]

# ── Nykaa ─────────────────────────────────────────────────
NYKAA_ITEM_SELECTORS   = ["div[class*='productWrapper']", "div[class*='product-card']",
                           "div[class*='ProductCard']", "div[data-testid*='product']"]
NYKAA_TITLE_SELECTORS  = ["p[class*='productName']", "div[class*='productName']",
                           "span[class*='productName']", "a[class*='productName']"]
NYKAA_PRICE_SELECTORS  = ["span[class*='postDiscountPrice']", "span[class*='price']",
                           "div[class*='price'] span"]
NYKAA_ORIG_SELECTORS   = ["span[class*='preDiscountPrice']", "span[class*='originalPrice']",
                           "span[class*='mrp']"]

# ── BigBasket ─────────────────────────────────────────────
BB_ITEM_SELECTORS      = ["li[class*='SKUDeck']", "div[class*='SKUDeck']",
                           "div[qa='product-card']", "div[class*='product-card']"]
BB_TITLE_SELECTORS     = ["span[class*='truncate-prod-name']", "span[class*='Heading']",
                           "h3[class*='heading']", "div[class*='prod-name']"]
BB_PRICE_SELECTORS     = ["span[class*='discounted-price']", "span[class*='Price']",
                           "div[class*='price'] span"]
BB_ORIG_SELECTORS      = ["span[class*='mrp']", "span[class*='MRP']", "span[class*='strike']"]

# ── JioMart ───────────────────────────────────────────────
JM_ITEM_SELECTORS      = ["div.plp-card-details-vertical", "div[class*='plp-card']",
                           "li[class*='product']", "div[class*='ProductCard']"]
JM_TITLE_SELECTORS     = ["div.plp-card-details-name", "span[class*='product-name']",
                           "p[class*='product-name']", "div[class*='name']"]
JM_PRICE_SELECTORS     = ["div.plp-card-details-price span", "span[class*='final-price']",
                           "span[class*='price']"]
JM_ORIG_SELECTORS      = ["span[class*='mrp']", "span[class*='strike']", "del"]

# ── Meesho ────────────────────────────────────────────────
MEESHO_ITEM_SELECTORS  = ["div[class*='ProductCard']", "div[class*='product-card']",
                           "div[class*='Card']"]
MEESHO_TITLE_SELECTORS = ["p[class*='ProductTitle']", "span[class*='ProductTitle']",
                           "p[class*='title']"]
MEESHO_PRICE_SELECTORS = ["h5[class*='Price']", "span[class*='Price']", "div[class*='price'] h5"]
MEESHO_ORIG_SELECTORS  = ["p[class*='originalPrice']", "span[class*='strike']",
                           "span[class*='original']"]

# ── Reliance Digital ──────────────────────────────────────
RD_ITEM_SELECTORS      = ["div.sp__product", "li.product-item", "div[class*='product-item']",
                           "div[class*='ProductCard']"]
RD_TITLE_SELECTORS     = ["p.sp__name", "h3.product-title", "div[class*='product-name']",
                           "a[class*='product-name']"]
RD_PRICE_SELECTORS     = ["span.amount", "div[class*='price'] span.amount",
                           "span[class*='price']"]
RD_ORIG_SELECTORS      = ["span.original-price", "span.strike", "span[class*='original']"]


# =========================================================
# GENERIC HELPERS
# =========================================================

def _scrape_price_generic(item, selectors):
    """Try CSS selectors first, then fall back to ₹ text scan."""
    for sel in selectors:
        el = item.query_selector(sel)
        if el:
            p = parse_price(el.inner_text())
            if p > 0:
                return p
    # ₹ scan fallback
    for el in item.query_selector_all("span, div, p, h5"):
        try:
            raw = el.inner_text().strip()
            if raw.startswith("₹") and len(raw) < 15:
                p = parse_price(raw)
                if 0 < p < 500000:
                    return p
        except Exception:
            continue
    return 0.0


def _scrape_orig_price_generic(item, selectors, price):
    for sel in selectors:
        for el in item.query_selector_all(sel):
            try:
                op = parse_price(el.inner_text())
                if op > price and op < price * 5 and op < 500000:
                    return op
            except Exception:
                continue
    return 0.0


def _scrape_title_generic(item, selectors):
    """Try CSS selectors, then img[alt], then a[title]."""
    for sel in selectors:
        el = item.query_selector(sel)
        if el:
            text = (el.get_attribute("title") or el.inner_text() or "").strip()
            if len(text) >= 10:
                return text
    for img in item.query_selector_all("img[alt]"):
        alt = (img.get_attribute("alt") or "").strip()
        if len(alt) >= 10:
            return alt
    for a in item.query_selector_all("a[title]"):
        t = (a.get_attribute("title") or "").strip()
        if len(t) >= 10:
            return t
    return ""


def _scrape_rating_generic(item):
    for el in item.query_selector_all("span, div"):
        try:
            txt = el.inner_text().strip()
            if re.match(r'^[1-5](\.[0-9])?$', txt):
                return float(txt)
        except Exception:
            continue
    return 0.0


def _scrape_review_count_generic(item):
    try:
        m = re.search(r'([\d,]+)\s*(ratings?|reviews?)', item.inner_text(), re.I)
        if m:
            return int(m.group(1).replace(",", ""))
    except Exception:
        pass
    return 0


def _scrape_image_generic(item):
    for img in item.query_selector_all("img[src]"):
        src = img.get_attribute("src") or ""
        if src.startswith("http") and not src.endswith(".svg"):
            return src
    return ""


def _scrape_link_generic(item, base_url, href_contains="/"):
    for a in item.query_selector_all(f"a[href*='{href_contains}']"):
        href = a.get_attribute("href") or ""
        if href:
            return href if href.startswith("http") else base_url.rstrip("/") + href
    return ""


def _wait_for_any(page, selectors, timeout=15000):
    for sel in selectors:
        try:
            page.wait_for_selector(sel, timeout=timeout)
            return True
        except Exception:
            continue
    return False


def _is_blocked(page):
    title = page.title().lower()
    return any(w in title for w in ["robot", "captcha", "blocked", "sorry", "access denied"])


# =========================================================
# GENERIC SCRAPER CORE
# (all 7 platforms share this — only config differs)
# =========================================================

def _scrape_platform(
    store_name,
    search_url_fn,       # fn(query) -> url
    item_selectors,
    title_selectors,
    price_selectors,
    orig_price_selectors,
    link_base_url,
    link_href_fragment,
    query,
    canonical_product,
    intent_type="main_product",
    extra_item_filter=None,   # optional fn(item) -> bool
    delivery_days=3,
    delivery_label="3–5 days",
):
    query = sanitize_search_query(query)
    min_score = get_minimum_score(canonical_product)

    print(f"\n{'='*60}\nScraping {store_name} for: {query}")
    print(f"Min score: {min_score}\n{'='*60}\n")

    products = []

    with sync_playwright() as p:
        browser, context = launch_browser(p)
        page = context.new_page()

        url = search_url_fn(query)
        print(f"URL: {url}\n")

        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"  [GOTO ERROR] {e}")
            browser.close()
            return make_empty_result(store_name, query)

        _wait_for_any(page, item_selectors, timeout=15000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(random.uniform(1.2, 2.2))
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)

        if _is_blocked(page):
            print(f"  [{store_name}] Blocked / CAPTCHA detected")
            browser.close()
            return make_empty_result(store_name, query,
                                     f"{store_name} is temporarily blocking. Try again.")

        # Collect items using the first selector that returns results
        items = []
        for sel in item_selectors:
            items = page.query_selector_all(sel)
            if items:
                print(f"  Using item selector: {sel}  ({len(items)} items)")
                break

        print(f"Raw items found: {len(items)}\n")

        for item in items[:25]:
            try:
                if extra_item_filter and not extra_item_filter(item):
                    continue

                title = _scrape_title_generic(item, title_selectors)
                if not title or len(title) < 10:
                    print("  SKIP: no title")
                    continue

                score = calculate_match_score(title, canonical_product, store=store_name)
                print(f"  {'✓' if score >= min_score else '✗'} score={score:3d} | {title[:70]}")
                if score < min_score:
                    continue

                price = _scrape_price_generic(item, price_selectors)
                if price == 0 or not validate_price(price, canonical_product):
                    print(f"  SKIP: invalid price {price} for '{title[:50]}'")
                    continue

                orig    = _scrape_orig_price_generic(item, orig_price_selectors, price)
                discount, orig = calc_discount(price, orig)
                rating  = _scrape_rating_generic(item)
                reviews = _scrape_review_count_generic(item)
                image   = _scrape_image_generic(item)
                link    = _scrape_link_generic(item, link_base_url, link_href_fragment)

                products.append({
                    "product_name":     title,
                    "price_inr":        price,
                    "original_price":   orig,
                    "discount_percent": discount,
                    "store":            store_name,
                    "delivery_days":    delivery_days,
                    "delivery_label":   delivery_label,
                    "rating":           rating,
                    "review_count":     reviews,
                    "offer":            "",
                    "stock_status":     "In Stock",
                    "is_reliable":      True,
                    "image":            image,
                    "product_link":     link,
                    "match_score":      score,
                    "is_best_price":    False,
                })
                print(f"  -> KEPT: {title[:60]} | Rs.{price}")

            except Exception as e:
                print(f"  ITEM ERROR: {e}")

        context.close()
        browser.close()

    print(f"\nFinal {store_name} count: {len(products)}")
    return finalize_products(products, store_name, query)


# =========================================================
# CROMA
# =========================================================

def scrape_croma(query, canonical_product, intent_type="main_product"):
    return _scrape_platform(
        store_name          = "Croma",
        search_url_fn       = lambda q: f"https://www.croma.com/searchB?text={q.replace(' ', '+')}",
        item_selectors      = CROMA_ITEM_SELECTORS,
        title_selectors     = CROMA_TITLE_SELECTORS,
        price_selectors     = CROMA_PRICE_SELECTORS,
        orig_price_selectors= CROMA_ORIG_SELECTORS,
        link_base_url       = "https://www.croma.com",
        link_href_fragment  = "/p/",
        query               = query,
        canonical_product   = canonical_product,
        intent_type         = intent_type,
        delivery_days       = 3,
        delivery_label      = "3–5 days",
    )


# =========================================================
# MYNTRA
# =========================================================

def scrape_myntra(query, canonical_product, intent_type="main_product"):
    return _scrape_platform(
        store_name          = "Myntra",
        search_url_fn       = lambda q: f"https://www.myntra.com/{q.replace(' ', '-')}",
        item_selectors      = MYNTRA_ITEM_SELECTORS,
        title_selectors     = MYNTRA_TITLE_SELECTORS,
        price_selectors     = MYNTRA_PRICE_SELECTORS,
        orig_price_selectors= MYNTRA_ORIG_SELECTORS,
        link_base_url       = "https://www.myntra.com",
        link_href_fragment  = "/buy",
        query               = query,
        canonical_product   = canonical_product,
        intent_type         = intent_type,
        delivery_days       = 4,
        delivery_label      = "4–7 days",
    )


# =========================================================
# NYKAA
# =========================================================

def scrape_nykaa(query, canonical_product, intent_type="main_product"):
    return _scrape_platform(
        store_name          = "Nykaa",
        search_url_fn       = lambda q: f"https://www.nykaa.com/search/result/?q={q.replace(' ', '%20')}",
        item_selectors      = NYKAA_ITEM_SELECTORS,
        title_selectors     = NYKAA_TITLE_SELECTORS,
        price_selectors     = NYKAA_PRICE_SELECTORS,
        orig_price_selectors= NYKAA_ORIG_SELECTORS,
        link_base_url       = "https://www.nykaa.com",
        link_href_fragment  = "/p/",
        query               = query,
        canonical_product   = canonical_product,
        intent_type         = intent_type,
        delivery_days       = 4,
        delivery_label      = "4–6 days",
    )


# =========================================================
# BIGBASKET
# =========================================================

def scrape_bigbasket(query, canonical_product, intent_type="main_product"):
    return _scrape_platform(
        store_name          = "BigBasket",
        search_url_fn       = lambda q: f"https://www.bigbasket.com/ps/?q={q.replace(' ', '+')}",
        item_selectors      = BB_ITEM_SELECTORS,
        title_selectors     = BB_TITLE_SELECTORS,
        price_selectors     = BB_PRICE_SELECTORS,
        orig_price_selectors= BB_ORIG_SELECTORS,
        link_base_url       = "https://www.bigbasket.com",
        link_href_fragment  = "/pd/",
        query               = query,
        canonical_product   = canonical_product,
        intent_type         = intent_type,
        delivery_days       = 1,
        delivery_label      = "Same / Next day",
    )


# =========================================================
# JIOMART
# =========================================================

def scrape_jiomart(query, canonical_product, intent_type="main_product"):
    return _scrape_platform(
        store_name          = "JioMart",
        search_url_fn       = lambda q: f"https://www.jiomart.com/search#{q.replace(' ', '%20')}",
        item_selectors      = JM_ITEM_SELECTORS,
        title_selectors     = JM_TITLE_SELECTORS,
        price_selectors     = JM_PRICE_SELECTORS,
        orig_price_selectors= JM_ORIG_SELECTORS,
        link_base_url       = "https://www.jiomart.com",
        link_href_fragment  = "/p/",
        query               = query,
        canonical_product   = canonical_product,
        intent_type         = intent_type,
        delivery_days       = 2,
        delivery_label      = "1–3 days",
    )


# =========================================================
# MEESHO
# =========================================================

def scrape_meesho(query, canonical_product, intent_type="main_product"):
    return _scrape_platform(
        store_name          = "Meesho",
        search_url_fn       = lambda q: f"https://www.meesho.com/search?q={q.replace(' ', '%20')}",
        item_selectors      = MEESHO_ITEM_SELECTORS,
        title_selectors     = MEESHO_TITLE_SELECTORS,
        price_selectors     = MEESHO_PRICE_SELECTORS,
        orig_price_selectors= MEESHO_ORIG_SELECTORS,
        link_base_url       = "https://www.meesho.com",
        link_href_fragment  = "/p/",
        query               = query,
        canonical_product   = canonical_product,
        intent_type         = intent_type,
        delivery_days       = 5,
        delivery_label      = "5–7 days",
    )


# =========================================================
# RELIANCE DIGITAL
# =========================================================

def scrape_reliance(query, canonical_product, intent_type="main_product"):
    return _scrape_platform(
        store_name          = "Reliance Digital",
        search_url_fn       = lambda q: f"https://www.reliancedigital.in/search?q={q.replace(' ', '+')}:relevance",
        item_selectors      = RD_ITEM_SELECTORS,
        title_selectors     = RD_TITLE_SELECTORS,
        price_selectors     = RD_PRICE_SELECTORS,
        orig_price_selectors= RD_ORIG_SELECTORS,
        link_base_url       = "https://www.reliancedigital.in",
        link_href_fragment  = "/p/",
        query               = query,
        canonical_product   = canonical_product,
        intent_type         = intent_type,
        delivery_days       = 3,
        delivery_label      = "3–5 days",
    )


# =========================================================
# CONVENIENCE: scrape ALL new platforms at once
# =========================================================

ALL_NEW_SCRAPERS = {
    "Croma":            scrape_croma,
    "Myntra":           scrape_myntra,
    "Nykaa":            scrape_nykaa,
    "BigBasket":        scrape_bigbasket,
    "JioMart":          scrape_jiomart,
    "Meesho":           scrape_meesho,
    "Reliance Digital": scrape_reliance,
}


def scrape_all_new_platforms(query, canonical_product, intent_type="main_product"):
    """
    Run all 7 new scrapers and return a flat list of results.
    Usage:
        results = scrape_all_new_platforms(query, canonical_product)
    """
    all_results = []
    for name, fn in ALL_NEW_SCRAPERS.items():
        try:
            res = fn(query, canonical_product, intent_type)
            all_results.extend(res)
        except Exception as e:
            print(f"  [{name}] scraper error: {e}")
    return all_results