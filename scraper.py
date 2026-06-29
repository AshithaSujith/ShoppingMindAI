import re
import random
import time
from collections import Counter
from playwright.sync_api import sync_playwright


# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(text):
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# =========================================================
# SANITIZE SEARCH QUERY
# =========================================================

def sanitize_search_query(query: str) -> str:
    query = re.sub(r'/[A-Za-z0-9]{1,6}', '', query)
    query = re.sub(r'[^\w\s.]', ' ', query)
    query = re.sub(r'(?<!\d)\.(?!\d)', ' ', query)
    query = re.sub(r'\s+', ' ', query).strip()
    return query


# =========================================================
# EXTRACT NUMBERS
# =========================================================

def extract_numbers(text: str) -> set:
    return set(re.findall(r'\d+', text.lower()))


# =========================================================
# EXTRACT ALPHANUMERIC CODES
# =========================================================

def extract_alphanum_codes(text: str) -> set:
    """
    Extract SKU/model codes containing BOTH letters AND digits.
    e.g. 'RT40H28U3FHL', 'K14x', 'GLS18I5KWFGR'
    Pure numbers and pure words are excluded.
    """
    return set(re.findall(
        r'\b(?=[a-z0-9]*[a-z])(?=[a-z0-9]*[0-9])[a-z0-9]+\b',
        text.lower()
    ))


# =========================================================
# IRRELEVANT PRODUCT FILTER
# =========================================================

IRRELEVANT_WORDS = [
    "case", "cover", "screen protector", "screen guard",
    "tempered glass", "charger", "charging cable", "adapter",
    "skin", "back cover", "bumper", "holder", "mount",
    "camera protector", "lens protector", "pouch",
    "flash drive", "thumb drive", "usb drive", "memory stick",
    "pen drive", "otg", "pendrive", "wall mount", "stand",
    "bracket", "shoe lace", "insole", "shoe cleaner",
    "compatible with", "replacement", "spare part",
]

def is_irrelevant_product(title: str, canonical_product: dict) -> bool:
    if canonical_product.get("intent_type", "main_product") != "main_product":
        return False
    t = normalize_text(title)
    return any(word in t for word in IRRELEVANT_WORDS)


# =========================================================
# HELPERS
# =========================================================

GENDER_GROUPS = {
    "men":    ["men", "mens", "male", "man"],
    "women":  ["women", "womens", "female", "woman", "ladies"],
    "boys":   ["boys", "boy", "kids", "child", "children"],
    "girls":  ["girls", "girl", "kids", "child", "children"],
    "unisex": ["unisex"],
}

OPPOSITE_GENDER = {
    "men":   ["women", "womens", "female", "woman", "ladies"],
    "women": ["men", "mens", "male", "man"],
    "boys":  ["girls", "women", "womens"],
    "girls": ["boys", "men", "mens"],
}

COMMON_COLORS = [
    "black", "white", "grey", "gray", "blue", "red", "green", "pink",
    "yellow", "orange", "purple", "brown", "navy", "silver", "gold",
    "beige", "cream", "teal", "multicolor", "multi", "volt", "cyan",
    "olive", "maroon", "carbon", "titanium", "midnight", "starlight",
    "natural", "desert", "coral", "lavender", "sage", "graphite",
]

MIN_VALID_PRICE = 10.0

KNOWN_BRANDS = [
    "samsung", "xiaomi", "realme", "vivo", "oneplus", "nokia",
    "motorola", "apple", "redmi", "poco", "iqoo",
    "sony", "lg", "huawei", "honor", "infinix", "tecno", "oppo",
    "whirlpool", "haier", "bosch", "siemens", "panasonic", "hitachi",
    "godrej", "voltas", "daikin", "bluestar", "carrier", "lloyd",
    "nike", "adidas", "puma", "reebok", "asics", "skechers", "bata", "woodland",
    "titan", "fastrack", "casio", "fossil", "timex", "seiko", "citizen",
    "nirapara", "everest", "mdh", "catch", "badshah", "shan", "eastern", "kitchentreaures",
    "kitchen treasures", "sakthi", "aachi", "tata", "idhayam",
    "mothers", "priya", "grand", "aashirvaad", "maggi", "knorr",
    "amul", "nestle", "britannia", "haldirams", "parle", "dabur", "patanjali",
    "springburst", "kalprishi", "otkir", "bmhmagic", "marwar", "fsipl",
]


# =========================================================
# MODEL TYPE DETECTION
# =========================================================

def is_product_code(model: str) -> bool:
    tokens = model.strip().split()
    if len(tokens) != 1:
        return False
    tok = tokens[0]
    return (len(tok) >= 4
            and bool(re.search(r'[a-zA-Z]', tok))
            and bool(re.search(r'\d', tok)))


# =========================================================
# PRICE BOUNDS BY CATEGORY
# =========================================================

def get_price_bounds(canonical_product: dict):
    pt   = normalize_text(canonical_product.get("product_type", ""))
    size = normalize_text(canonical_product.get("size", ""))

    if "tv" in pt or "television" in pt:
        size_nums = re.findall(r'\d+', size)
        screen = int(size_nums[0]) if size_nums else 0
        if screen >= 55:   return (25000, 500000)
        elif screen >= 43: return (12000, 300000)
        elif screen >= 32: return (5000,  200000)
        else:              return (3000,  200000)

    if "air conditioner" in pt or pt.endswith(" ac") or pt == "ac":
        return (15000, 200000)

    if "washing machine" in pt:
        return (5000, 150000)

    if "refrigerator" in pt or "fridge" in pt:
        return (5000, 200000)

    if "laptop" in pt or "notebook" in pt:
        return (10000, 300000)

    if "smartphone" in pt or "phone" in pt or "mobile" in pt:
        return (3000, 200000)

    if "headphones" in pt or "headphone" in pt: return (100, 50000)
    if "earphones"  in pt or "earphone"  in pt: return (100, 30000)
    if "earbuds"    in pt or "earbud"    in pt: return (100, 30000)
    if "speaker"    in pt:                       return (200, 100000)

    if "shoes" in pt or "sneakers" in pt or "footwear" in pt:
        return (200, 30000)

    if "iron"    in pt:                       return (200,  10000)
    if "mixer"   in pt or "grinder" in pt:    return (500,  20000)
    if "pressure cooker" in pt or "cooker" in pt: return (300, 10000)
    if "trimmer" in pt:                       return (200,  10000)
    if "hair dryer" in pt:                    return (200,  10000)
    if "microwave" in pt:                     return (3000, 60000)
    if "water purifier" in pt:                return (3000, 80000)

    if "butter"   in pt: return (30,  1000)
    if "masala"   in pt: return (20,  2000)
    if "spice"    in pt: return (20,  2000)
    if "oil"      in pt: return (50,  5000)
    if "flour"    in pt: return (30,  2000)
    if "coffee"   in pt: return (50,  5000)
    if "tea"      in pt: return (30,  3000)

    if "watch" in pt: return (5000, 500000)

    return (MIN_VALID_PRICE, 500000)


def validate_price(price: float, canonical_product: dict) -> bool:
    if price <= 0:
        return False
    min_p, max_p = get_price_bounds(canonical_product)
    if price < min_p or price > max_p:
        print(f"    [PRICE REJECT] Rs.{price} outside bounds Rs.{min_p}-Rs.{max_p}")
        return False
    return True


# =========================================================
# HARD FILTER
# =========================================================

def hard_filter(title: str, canonical_product: dict, store: str = "Amazon") -> bool:
    t = normalize_text(title)
    tokens = set(t.split())

    # -- 1. BRAND --
    brand = normalize_text(canonical_product.get("brand", ""))
    product_type_norm = normalize_text(canonical_product.get("product_type", ""))
    model_norm_check = normalize_text(canonical_product.get("model", ""))

    if brand:
        brand_tokens = set(brand.split())

        if not brand_tokens.issubset(tokens):
            print(f"    [HARD FILTER] Brand mismatch: '{title[:60]}'")
            return False

        own_words = brand_tokens | set(product_type_norm.split()) | set(model_norm_check.split())

        competing = [
            b for b in KNOWN_BRANDS
            if b in tokens
            and b not in own_words
            and not any(bt in b for bt in brand_tokens)
            and not any(b in bt for bt in brand_tokens)
            and not any(b in w for w in own_words)
        ]
        if competing:
            print(f"    [HARD FILTER] Competing brand {competing}: '{title[:60]}'")
            return False

    # -- 2. MODEL --
    raw_model = canonical_product.get("model", "")
    raw_model = re.sub(r'/\w+$', '', raw_model).strip()
    model_norm = normalize_text(raw_model)

    if model_norm:
        if is_product_code(model_norm):
            model_codes = extract_alphanum_codes(model_norm)
            title_codes = extract_alphanum_codes(t)

            if model_codes and not model_codes.issubset(title_codes):
                canon_variant = normalize_text(canonical_product.get("variant", ""))
                canon_years = re.findall(r'20\d{2}', canon_variant)
                if canon_years:
                    title_years = re.findall(r'20\d{2}', t)
                    if title_years and not any(y in title_years for y in canon_years):
                        print(f"    [HARD FILTER] Year mismatch (need {canon_years}): '{title[:60]}'")
                        return False

                canon_text = normalize_text(
                    canonical_product.get("variant", "") + " " +
                    canonical_product.get("size", "")
                )
                canon_stars = re.findall(r'(\d)\s*star', canon_text)
                if canon_stars:
                    title_stars = re.findall(r'(\d)\s*star', t)
                    if title_stars and not any(s in title_stars for s in canon_stars):
                        print(f"    [HARD FILTER] Star rating mismatch (need {canon_stars}): '{title[:60]}'")
                        return False

                other_codes = re.findall(r'\b[a-z]{2,4}\d{2,}[a-z0-9]*\b', t)
                if other_codes and not any(list(model_codes)[0][:4] in oc for oc in other_codes):
                    print(f"    [HARD FILTER] Different product code in title: '{title[:60]}'")
                    return False

                print(f"    [SOFT] Code absent, variant matched: '{title[:60]}'")
        else:
            model_codes = extract_alphanum_codes(model_norm)
            if model_codes:
                title_codes = extract_alphanum_codes(t)
                print("MODEL:", model_norm)
                print("TITLE:", title)
                print("MODEL_CODES:", model_codes)
                print("TITLE_CODES:", title_codes)
                if not model_codes.issubset(title_codes):
                    print(f"    [HARD FILTER] Model code mismatch (need {model_codes}): '{title[:60]}'")
                    return False
            else:
                model_numbers = extract_numbers(model_norm)
                if model_numbers:
                    title_numbers = extract_numbers(title)
                    if title_numbers and not model_numbers.issubset(title_numbers):
                        print(f"    [HARD FILTER] Model numbers mismatch (need {model_numbers}): '{title[:60]}'")
                        return False

            model_tokens = model_norm.split()
            skip_words = {"edition", "series", "gen", "generation", "new"}
            essential = [tok for tok in model_tokens if tok not in skip_words]
            if len(essential) >= 2:
                matched = sum(1 for tok in essential if tok in tokens)
                threshold = 0.5 if len(essential) == 2 else 0.6
                if matched / len(essential) < threshold:
                    print(f"    [HARD FILTER] Model token mismatch: '{title[:60]}'")
                    return False
                if len(essential) == 2 and matched == 1:
                    if essential[0] not in tokens:
                        print(f"    [HARD FILTER] Primary model token missing: '{title[:60]}'")
                        return False

            tier_suffixes = {"max", "plus", "ultra", "lite", "mini"}
            model_tiers = {s for s in tier_suffixes if s in set(model_tokens)}
            title_tiers  = {s for s in tier_suffixes if s in tokens}

            if model_tiers != title_tiers:
                print(f"    [HARD FILTER] Tier mismatch (model={model_tiers}, title={title_tiers}): '{title[:60]}'")
                return False

    # -- 3. VARIANT SKU --
    variant = normalize_text(canonical_product.get("variant", ""))
    if variant:
        variant_codes = extract_alphanum_codes(variant)
        if variant_codes:
            title_codes = extract_alphanum_codes(t)
            if not variant_codes.issubset(title_codes):
                print(f"    [HARD FILTER] Variant code mismatch (need {variant_codes}): '{title[:60]}'")
                return False

    # -- 4. PRODUCT NAME (no-SKU products) --
    has_model = bool(canonical_product.get("model", "").strip())
    has_variant_code = bool(extract_alphanum_codes(variant)) if variant else False

    if not has_model and not has_variant_code:
        product_type = normalize_text(canonical_product.get("product_type", ""))
        brand_tokens_set = set(normalize_text(brand).split()) if brand else set()
        pt_tokens = set(product_type.split())
        name_tokens = pt_tokens - brand_tokens_set
        STOP_WORDS = {
            "masala", "powder", "mix", "sauce", "paste", "oil", "spice", "spices",
            "food", "product", "item", "pack", "box", "bottle", "pouch",
            "kg", "g", "ml", "l", "100", "200", "500", "1000",
            "with", "and", "for", "the", "of", "in", "a",
        }
        distinctive = name_tokens - STOP_WORDS
        if distinctive:
            missing = [tok for tok in distinctive if tok not in tokens]
            if missing:
                print(f"    [HARD FILTER] Product name mismatch (missing {missing}): '{title[:60]}'")
                return False

    # -- 5. STORAGE --
    storage_raw = (canonical_product.get("storage") or
                   canonical_product.get("storage_capacity") or "")
    if storage_raw:
        storage_numbers = extract_numbers(storage_raw)
        if storage_numbers:
            if any(kw in title.lower() for kw in ["gb", "tb", "mb"]):
                title_numbers = extract_numbers(title)
                if not storage_numbers.issubset(title_numbers):
                    print(f"    [HARD FILTER] Storage mismatch (need {storage_numbers}): '{title[:60]}'")
                    return False

    # -- 5b. CAPACITY - unit-aware for kg, ton, and litres --
    size_raw = canonical_product.get("size", "")
    if size_raw:
        range_match = re.search(r'(\d+)\s*[lL]\s*[-]\s*(\d+)\s*[lL]', size_raw)
        if range_match:
            lo_l = int(range_match.group(1))
            hi_l = int(range_match.group(2))
            title_litres = [int(m.group(1)) for m in re.finditer(r'(\d+)\s*[lL](?:|\s)', title)]
            if title_litres:
                if not any(lo_l <= v <= hi_l for v in title_litres):
                    print(f"    [HARD FILTER] Capacity range {lo_l}L-{hi_l}L mismatch "
                          f"(title has {title_litres}): '{title[:60]}'")
                    return False

        elif re.search(r'\d+\s*[lL](?:|itre|iter)', size_raw, re.IGNORECASE):
            canon_litres_m = re.findall(r'(\d+)\s*[lL](?:|itre|iter)', size_raw, re.IGNORECASE)
            if canon_litres_m:
                canon_val = int(canon_litres_m[0])
                title_litres = [int(m.group(1)) for m in re.finditer(
                    r'(\d+)\s*[lL](?:|itre|iter)', title, re.IGNORECASE
                )]
                if title_litres:
                    if canon_val not in title_litres:
                        print(f"    [HARD FILTER] Litre capacity mismatch "
                              f"(need {canon_val}L, title has {title_litres}L): '{title[:60]}'")
                        return False

        elif any(kw in size_raw.lower() for kw in ["kg", "ton", "tons"]):
            size_numbers = extract_numbers(size_raw)
            if size_numbers and any(kw in title.lower() for kw in ["kg", "ton", "tons"]):
                title_numbers = extract_numbers(title)
                if not size_numbers.issubset(title_numbers):
                    print(f"    [HARD FILTER] Capacity mismatch (need {size_numbers}): '{title[:60]}'")
                    return False

    # -- 6. WEIGHT / VOLUME / PACK SIZE exact unit-aware match --
    def extract_weight_pairs(text: str) -> set:
        return set(
            (int(m.group(1)), m.group(2).lower().strip())
            for m in re.finditer(
                r'\b(\d+)\s*(g|kg|gm|gms|ml|l|litre|liter|oz|lb)\b',
                text.lower()
            )
        )

    weight_raw = (
        canonical_product.get("weight") or
        canonical_product.get("pack_size") or
        canonical_product.get("volume") or
        ""
    )

    if weight_raw:
        canon_pairs = extract_weight_pairs(weight_raw)
        if canon_pairs:
            title_pairs = extract_weight_pairs(title)
            if title_pairs:
                if not canon_pairs.intersection(title_pairs):
                    print(f"    [HARD FILTER] Weight mismatch "
                          f"(need {canon_pairs}, title has {title_pairs}): '{title[:60]}'")
                    return False

    # -- 7. GENDER --
    user_gender = normalize_text(canonical_product.get("gender", ""))
    if user_gender and user_gender in OPPOSITE_GENDER:
        if any(w in tokens for w in OPPOSITE_GENDER[user_gender]):
            print(f"    [HARD FILTER] Gender mismatch: '{title[:60]}'")
            return False

    # -- 8. COLOR (Amazon only) --
    user_color = normalize_text(canonical_product.get("color", ""))
    if user_color and store == "Amazon":
        user_color_tokens = set(user_color.split())
        title_colors = [c for c in COMMON_COLORS if c in tokens]
        if title_colors:
            match = any(uc in title_colors for uc in user_color_tokens)
            if not match and not (len(user_color_tokens) >= 2 and len(title_colors) == 1):
                print(f"    [HARD FILTER] Color mismatch (has {title_colors}, want {user_color}): '{title[:60]}'")
                return False

    return True


# =========================================================
# PACK / COMBO DETECTION
# =========================================================

PACK_PATTERN = re.compile(r'pack\s*of\s*(\d+)|\(\s*(\d+)\s*pack\s*\)|x\s*(\d+)\b', re.IGNORECASE)

COMBO_INDICATORS = ["&", "+", "combo", "bundle", "set of", "kit"]


def detect_pack_count(title: str) -> int:
    m = PACK_PATTERN.search(title)
    if m:
        for g in m.groups():
            if g:
                return int(g)
    return 1


def is_combo_listing(title: str, canonical_product: dict) -> bool:
    """
    Detects if a title represents a combo/bundle of multiple DIFFERENT products,
    not just one product with a pack count.
    """
    t = title.lower()
    brand = normalize_text(canonical_product.get("brand", ""))

    title_without_brand = title
    raw_brand = canonical_product.get("brand", "")
    if raw_brand:
        title_without_brand = re.sub(re.escape(raw_brand), "", title, flags=re.IGNORECASE)

    if re.search(r'\s[&+]\s', title_without_brand):
        return True

    if any(w in t for w in ["combo", "bundle", "set of", "kit", "value pack"]):
        return True

    if brand and t.count(brand.lower()) >= 2:
        return True

    return False


# =========================================================
# MATCH SCORE
# =========================================================

def calculate_match_score(title: str, canonical_product: dict, store: str = "Amazon") -> int:
    if is_irrelevant_product(title, canonical_product):
        return 0
    if not hard_filter(title, canonical_product, store=store):
        return 0

    score = 0
    t = normalize_text(title)
    tokens = set(t.split())

    product_type = normalize_text(canonical_product.get("product_type", ""))
    if product_type:
        pt_tokens = product_type.split()
        matched = sum(1 for tok in pt_tokens if tok in tokens)
        score += int((matched / len(pt_tokens)) * 60)

    brand = normalize_text(canonical_product.get("brand", ""))
    if brand:
        brand_tokens = brand.split()
        matched = sum(1 for tok in brand_tokens if tok in tokens)
        if matched == len(brand_tokens): score += 50
        elif matched > 0: score += 15
        else: score -= 40

    raw_model = re.sub(r'/\w+$', '', canonical_product.get("model", "")).strip()
    model = normalize_text(raw_model)
    if model:
        model_tokens = model.split()
        matched = sum(1 for tok in model_tokens if tok in tokens)
        ratio = matched / len(model_tokens)
        score += int(ratio * 70)
        if ratio >= 0.8: score += 30

    variant = normalize_text(canonical_product.get("variant", ""))
    if variant:
        matched = sum(1 for tok in variant.split() if tok in tokens)
        score += matched * 10

    user_gender = normalize_text(canonical_product.get("gender", ""))
    if user_gender and user_gender in GENDER_GROUPS:
        if any(w in tokens for w in GENDER_GROUPS[user_gender]):
            score += 20

    for field in ["storage", "storage_capacity", "size", "pack_size", "flavor",
                  "weight", "quantity", "version", "color", "ram", "shoe_size",
                  "resolution", "panel_type", "connectivity", "volume"]:
        value = normalize_text(canonical_product.get(field, ""))
        if not value:
            continue
        matched = sum(1 for tok in value.split() if tok in tokens)
        score += matched * 5

    # ─── Multi-pack / combo penalty ───────────────────────────────
    pack_count = detect_pack_count(title)
    canon_pack = canonical_product.get("pack_count") or canonical_product.get("quantity")

    if pack_count > 1:
        if canon_pack and str(pack_count) == str(canon_pack):
            pass
        else:
            score -= 100

    if canonical_product.get("intent_type") != "bundle":
        if is_combo_listing(title, canonical_product):
            score -= 100
    # ─────────────────────────────────────────────────────────────

    return score


# =========================================================
# DYNAMIC MINIMUM SCORE
# =========================================================

def get_minimum_score(canonical_product: dict) -> int:
    filled = sum(
        1 for f in ["brand", "product_type", "variant", "model", "storage",
                    "size", "flavor", "gender", "color", "shoe_size", "ram", "resolution"]
        if canonical_product.get(f)
    )
    intent = canonical_product.get("intent_type", "main_product")
    is_grocery = intent in ("consumable", "food") or any(
        kw in normalize_text(canonical_product.get("product_type", ""))
        for kw in ["masala", "spice", "powder", "sauce", "paste", "butter",
                   "oil", "flour", "sugar", "salt", "rice", "dal", "tea", "coffee"]
    )

    if filled >= 5: return 55
    elif filled >= 4: return 50
    elif filled >= 3: return 45 if not is_grocery else 40
    elif filled >= 2: return 40 if not is_grocery else 35
    else: return 25


# =========================================================
# DUPLICATE FILTER
# =========================================================

def remove_duplicates(products):
    unique = []
    seen = set()
    for p in products:
        key = normalize_text(p["product_name"])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


# =========================================================
# PARSE PRICE
# =========================================================

def parse_price(raw: str) -> float:
    try:
        cleaned = raw.replace("\u20b9", "").replace(",", "").strip()
        match = re.search(r'\d+(\.\d+)?', cleaned)
        val = float(match.group()) if match else 0.0
        return val if val >= MIN_VALID_PRICE else 0.0
    except Exception:
        return 0.0


# =========================================================
# AMAZON TITLE EXTRACTION
# =========================================================

def extract_title_amazon(item, debug: bool = False) -> str:
    BAD_VALUES = {"sponsored", "amazon"}
    SELECTORS = [
        ("h2 a span",                                            None),
        ("h2 span.a-text-normal",                                None),
        ("h2 span",                                              None),
        ("h2 a",                                                 "aria-label"),
        ("[data-cy='title-recipe'] span.a-text-normal",         None),
        ("[data-cy='title-recipe'] span",                        None),
        ("[data-cy='title-recipe'] a span",                     None),
        ("img.s-image",                                          "alt"),
        ("div.s-title-instructions-style span",                 None),
        (".a-size-medium.a-color-base.a-text-normal",           None),
        (".a-size-base-plus",                                    None),
        ("a.a-link-normal.s-line-clamp-2 span",                 None),
        ("a.a-link-normal.s-line-clamp-3 span",                 None),
        ("a.a-link-normal.s-line-clamp-2",                      None),
        ("a.a-link-normal.s-line-clamp-3",                      None),
    ]
    best_title = ""
    for selector, attr in SELECTORS:
        try:
            el = item.query_selector(selector)
            if not el:
                continue
            text = (el.get_attribute(attr) or "") if attr else (el.inner_text() or "")
            text = re.sub(r"^sponsored\s*", "", text.strip(), flags=re.IGNORECASE)
            if text.lower() in BAD_VALUES or len(text) < 5:
                continue
            if len(text) > len(best_title):
                best_title = text
            if debug:
                print(f"  [title] {selector} -> {text[:60]}")
        except Exception:
            continue
    return best_title


# =========================================================
# PRICE SELECTORS
# =========================================================

AMAZON_PRICE_SELECTORS = [
    ".a-price-whole",
    ".a-price .a-offscreen",
    ".a-color-price",
    ".a-price-range",
]

AMAZON_ORIG_PRICE_SELECTORS = [
    ".a-price.a-text-price .a-offscreen",
    "span.a-text-price .a-offscreen",
    ".a-text-strike",
]

FLIPKART_PRICE_SELECTORS = [
    "div.oFEPlD", "div.Nx9bqj", "div._30jeq3",
    "div.CxhGGd", "div._1vC4OE", "div.hl05eU div.Nx9bqj",
]

FLIPKART_ORIG_PRICE_SELECTORS = [
    "div.yRaY8j", "div.__6Jmc", "div.sIstCe", "div.struck", "div._3I9_wc",
]

FLIPKART_TITLE_SELECTORS = [
    "div.RG5Slk", "div.KzDlHZ", "div.wjcEIp",
    "a.WKTcLC", "a.IRpwTa", "a.s1Q9rs",
    "div._4rR01T", "div._2WkVRV",
]


# =========================================================
# PRICE HELPERS
# =========================================================

def scrape_price_amazon(item):
    for sel in AMAZON_PRICE_SELECTORS:
        el = item.query_selector(sel)
        if el:
            print(f"FOUND SELECTOR: {sel}")
            try:
                raw_text = el.inner_text()
                print(f"RAW PRICE TEXT: {raw_text}")
                p = parse_price(raw_text)
                print(f"PARSED PRICE: {p}")
                if p > 0:
                    print(f"    [price] '{sel}' -> {p}")
                    return p
            except Exception as e:
                print(f"PRICE PARSE ERROR: {e}")

    candidates = []
    for el in item.query_selector_all(
        "span.a-price-whole, span.a-price-fraction, span.a-color-price, "
        "span.a-color-base, span[class*='price']"
    ):
        try:
            raw = el.inner_text().strip()
            p = parse_price(raw)
            if 0 < p < 500000:
                candidates.append(p)
        except Exception:
            continue

    if not candidates:
        for el in item.query_selector_all("span, div"):
            try:
                raw = el.inner_text().strip()
                if raw.startswith("\u20b9") and len(raw) < 15:
                    p = parse_price(raw)
                    if 0 < p < 500000:
                        candidates.append(p)
            except Exception:
                continue

    if candidates:
        freq = Counter(candidates)
        max_freq = max(freq.values())
        price = min(v for v, c in freq.items() if c == max_freq)
        print(f"    [price] scan -> {price}")
        return price

    print("NO AMAZON PRICE FOUND")
    return 0.0


def scrape_orig_price_amazon(item, price):
    for sel in AMAZON_ORIG_PRICE_SELECTORS:
        for el in item.query_selector_all(sel):
            op = parse_price(el.inner_text())
            if op > price and op < price * 5 and op < 500000:
                return op
    return 0.0


def scrape_price_flipkart(item):
    for sel in FLIPKART_PRICE_SELECTORS:
        el = item.query_selector(sel)
        if el:
            p = parse_price(el.inner_text())
            if p > 0:
                print(f"    [price] class '{sel}' -> {p}")
                return p
    candidates = []
    for el in item.query_selector_all("div, span"):
        try:
            raw = el.inner_text().strip()
            if raw.startswith("\u20b9") and len(raw) < 15:
                p = parse_price(raw)
                if 0 < p < 500000:
                    candidates.append(p)
        except Exception:
            continue
    if candidates:
        freq = Counter(candidates)
        max_freq = max(freq.values())
        price = min(v for v, c in freq.items() if c == max_freq)
        print(f"    [price] scan -> {price} (candidates: {sorted(set(candidates))[:5]})")
        return price
    return 0.0


def scrape_orig_price_flipkart(item, price):
    for sel in FLIPKART_ORIG_PRICE_SELECTORS:
        el = item.query_selector(sel)
        if el:
            op = parse_price(el.inner_text())
            if op > price and op < price * 5 and op < 500000:
                return op
    return 0.0


def calc_discount(price, original_price):
    if original_price > 0 and price > 0 and original_price > price:
        d = round((1 - price / original_price) * 100)
        if 1 <= d <= 90:
            return d, original_price
    return 0, 0


# =========================================================
# SHARED BROWSER LAUNCHER
# =========================================================

def launch_browser(p):
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox", "--disable-setuid-sandbox",
            "--disable-infobars", "--disable-dev-shm-usage",
            "--disable-extensions", "--window-size=1280,800",
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
        extra_http_headers={
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
    )
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    return browser, context


def make_empty_result(store, query, message=None):
    base_url = (
        f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
        if store == "Amazon"
        else f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
    )
    return [{
        "product_name": message or f"No products found for '{query}'",
        "price_inr": 0, "original_price": 0, "discount_percent": 0,
        "store": store, "delivery_days": 0, "delivery_label": "",
        "rating": 0, "review_count": 0, "offer": "",
        "stock_status": "Unknown", "is_reliable": False,
        "image": "", "product_link": base_url,
        "match_score": 0, "is_best_price": False,
    }]


def finalize_products(products, store, query):
    products = remove_duplicates(products)
    products.sort(key=lambda x: (x["match_score"], x["rating"]), reverse=True)
    if products:
        priced = [p for p in products if p["price_inr"] > 0]
        if priced:
            min(priced, key=lambda x: x["price_inr"])["is_best_price"] = True
    return products[:1] if products else make_empty_result(store, query)


def scrape_with_fallback(scrape_fn, query, canonical_product, intent_type):
    results = scrape_fn(query, canonical_product, intent_type)
    real = [p for p in results if p.get("is_reliable") and p.get("price_inr", 0) > 0]
    if real:
        return results

    brand   = canonical_product.get("brand", "")
    model   = canonical_product.get("model", "")
    pt      = canonical_product.get("product_type", "")
    size    = canonical_product.get("size", "") or canonical_product.get("weight", "")

    if model and brand:
        short_query = f"{brand} {model}".strip()
    elif brand and pt:
        short_query = f"{brand} {pt} {size}".strip()
    else:
        short_query = query

    short_query = sanitize_search_query(short_query)

    if short_query != query and len(short_query) >= 5:
        print(f"  [FALLBACK P2] Retrying with shorter query: '{short_query}'")
        results2 = scrape_fn(short_query, canonical_product, intent_type)
        real2 = [p for p in results2 if p.get("is_reliable") and p.get("price_inr", 0) > 0]
        if real2:
            return results2

    print(f"  [FALLBACK P3] Retrying without brand filter...")
    relaxed = dict(canonical_product)
    relaxed.pop("brand", None)
    results3 = scrape_fn(query, relaxed, intent_type)
    real3 = [p for p in results3 if p.get("is_reliable") and p.get("price_inr", 0) > 0]
    if real3:
        for p in real3:
            p["offer"] = p.get("offer", "") or "Similar product shown"
        return results3

    if not [p for p in results3 if p.get("is_reliable") and p.get("price_inr", 0) > 0]:
        model = canonical_product.get("model", "")
        pt = canonical_product.get("product_type", "")
        if model and pt:
            generic_query = f"{model} {pt}"
            generic_query = sanitize_search_query(generic_query)
            print(f"  [FALLBACK P4] Generic model+type query: '{generic_query}'")
            generic_canon = {
                k: v for k, v in canonical_product.items()
                if k in ("brand", "model", "product_type", "storage", "storage_capacity")
            }
            results4 = scrape_fn(generic_query, generic_canon, intent_type)
            real4 = [p for p in results4 if p.get("is_reliable") and p.get("price_inr", 0) > 0]
            if real4:
                return results4

    return results


# =========================================================
# AMAZON SCRAPER
# =========================================================

def scrape_amazon(query, canonical_product, intent_type="main_product", debug_titles=False):
    query = sanitize_search_query(query)
    min_score = get_minimum_score(canonical_product)

    print(f"\n{'='*60}\nScraping Amazon for: {query}")
    print(f"Canonical: {canonical_product}")
    print(f"Min score: {min_score}\n{'='*60}\n")

    products = []

    with sync_playwright() as p:
        browser, context = launch_browser(p)
        page = context.new_page()

        url = "https://www.amazon.in/s?k=" + query.replace(" ", "+")
        print(f"URL: {url}\n")
        page.goto(url, timeout=60000, wait_until="domcontentloaded")

        page.evaluate("window.scrollTo(0, 400)")
        time.sleep(1.5)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)

        try:
            page.wait_for_selector('[data-component-type="s-search-result"]', timeout=20000)
        except Exception:
            print("WARNING: Primary selector timed out, trying fallback")
            try:
                page.wait_for_selector('div[data-asin]:not([data-asin=""])', timeout=8000)
            except Exception:
                print("WARNING: Both selectors timed out")

        time.sleep(random.uniform(1.5, 2.5))
        page_title = page.title()
        print(f"Page title: {page_title}")

        if any(w in page_title.lower() for w in ["robot", "captcha", "sorry", "blocked"]):
            browser.close()
            return make_empty_result("Amazon", query, "Amazon is temporarily blocking. Try again.")

        items = page.query_selector_all("div[data-component-type='s-search-result'][data-asin]")
        if not items:
            items = page.query_selector_all("div[data-asin]:not([data-asin=''])")

        if len(items) == 0:
            print("No items -- waiting 3s and retrying...")
            time.sleep(3.0)
            page.evaluate("window.scrollTo(0, 300)")
            time.sleep(1.0)
            items = page.query_selector_all("div[data-component-type='s-search-result'][data-asin]")

        print(f"Raw items found: {len(items)}\n")

        for item in items[:25]:
            try:
                asin = item.get_attribute("data-asin")
                if not asin or asin.strip() == "":
                    continue

                if item.query_selector('span:has-text("Sponsored")'):
                    continue

                title = extract_title_amazon(item, debug=debug_titles)
                if not title or len(title) < 10:
                    print("  SKIP: no title")
                    continue

                score = calculate_match_score(title, canonical_product, store="Amazon")
                print(f"  {'OK' if score >= min_score else 'NO'} score={score:3d} | {title[:70]}")
                if score < min_score:
                    continue

                price = scrape_price_amazon(item)
                print(f"  AMAZON PRICE: {price}")

                valid_price = validate_price(price, canonical_product)
                print(f"  VALID PRICE?: {valid_price}")

                if price == 0 or not valid_price:
                    print(f"  SKIP: invalid price {price} for '{title[:50]}'")
                    continue

                orig = scrape_orig_price_amazon(item, price)
                discount, orig = calc_discount(price, orig)

                rating = 0
                rel = item.query_selector(".a-icon-alt")
                if rel:
                    try: rating = float(rel.inner_text().split()[0])
                    except: pass

                review_count = 0
                rev_el = item.query_selector("span[aria-label*='ratings'], .a-size-base.s-underline-text")
                if rev_el:
                    try:
                        m = re.search(r'\d+', rev_el.inner_text().replace(",", ""))
                        if m: review_count = int(m.group())
                    except: pass

                stock_status = "In Stock"
                sel = item.query_selector(".a-color-price, span:has-text('Only'), span:has-text('left in stock')")
                if sel:
                    st = sel.inner_text().lower()
                    if "only" in st or "left" in st: stock_status = "Limited Stock"
                    elif "out of stock" in st: stock_status = "Out of Stock"

                delivery_days, delivery_label = 2, "2 day delivery"
                del_el = item.query_selector("[data-cy='delivery-recipe'] span, .a-color-base.a-text-bold")
                if del_el:
                    dl = del_el.inner_text().strip()
                    if dl:
                        delivery_label = dl
                        if "tomorrow" in dl.lower(): delivery_days = 1
                        elif "today" in dl.lower(): delivery_days = 0
                        else:
                            nums = re.findall(r'\d+', dl)
                            if nums: delivery_days = int(nums[-1])

                image = ""
                img_el = item.query_selector("img.s-image")
                if img_el: image = img_el.get_attribute("src") or ""

                product_link = ""
                link_el = item.query_selector("a.a-link-normal[href*='/dp/']")
                if link_el:
                    href = link_el.get_attribute("href") or ""
                    product_link = href if href.startswith("http") else "https://www.amazon.in" + href

                products.append({
                    "product_name": title, "price_inr": price,
                    "original_price": orig, "discount_percent": discount,
                    "store": "Amazon", "delivery_days": delivery_days,
                    "delivery_label": delivery_label, "rating": rating,
                    "review_count": review_count, "offer": "",
                    "stock_status": stock_status, "is_reliable": True,
                    "image": image, "product_link": product_link,
                    "match_score": score, "is_best_price": False,
                })
                print(f"  -> KEPT: {title[:60]} | Rs.{price}")

            except Exception as e:
                print(f"  ITEM ERROR: {e}")

        context.close()
        browser.close()

    print(f"\nFinal Amazon count: {len(products)}")
    return finalize_products(products, "Amazon", query)


# =========================================================
# FLIPKART SCRAPER
# =========================================================

def scrape_flipkart(query, canonical_product, intent_type="main_product", debug_titles=False):
    query = sanitize_search_query(query)
    min_score = get_minimum_score(canonical_product)

    print(f"\n{'='*60}\nScraping Flipkart for: {query}")
    print(f"Min score: {min_score}\n{'='*60}\n")

    products = []

    with sync_playwright() as p:
        browser, context = launch_browser(p)
        page = context.new_page()

        url = "https://www.flipkart.com/search?q=" + query.replace(" ", "+")
        print(f"URL: {url}\n")
        page.goto(url, timeout=60000, wait_until="domcontentloaded")

        try:
            page.wait_for_selector("div[data-id]", timeout=15000)
        except Exception:
            print("WARNING: Timed out waiting for Flipkart cards")

        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(1.0)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(random.uniform(1.0, 2.0))

        page_title = page.title()
        print(f"Page title: {page_title}")

        if any(w in page_title.lower() for w in ["robot", "captcha", "blocked", "sorry"]):
            browser.close()
            return make_empty_result("Flipkart", query, "Flipkart is temporarily blocking. Try again.")

        items = page.query_selector_all("div[data-id]")
        print(f"Raw items found: {len(items)}\n")

        for item in items[:25]:
            try:
                title = ""

                for a_el in item.query_selector_all("a[title]"):
                    c = (a_el.get_attribute("title") or "").strip()
                    if len(c) >= 10:
                        title = c
                        break

                if not title:
                    for img_el in item.query_selector_all("img[alt]"):
                        c = (img_el.get_attribute("alt") or "").strip()
                        if len(c) >= 10:
                            title = c
                            break

                if not title:
                    for sel in FLIPKART_TITLE_SELECTORS:
                        el = item.query_selector(sel)
                        if el:
                            c = (el.get_attribute("title") or el.inner_text() or "").strip()
                            if len(c) >= 10:
                                title = c
                                break

                if not title:
                    print("  SKIP: no title")
                    continue

                if debug_titles:
                    print(f"  [title-fk] {title[:80]}")

                score = calculate_match_score(title, canonical_product, store="Flipkart")
                print(f"  {'OK' if score >= min_score else 'NO'} score={score:3d} | {title[:70]}")
                if score < min_score:
                    continue

                price = scrape_price_flipkart(item)
                if price == 0 or not validate_price(price, canonical_product):
                    print(f"  SKIP: invalid price {price} for '{title[:50]}'")
                    continue

                orig = scrape_orig_price_flipkart(item, price)
                discount, orig = calc_discount(price, orig)

                rating = 0
                rat_el = item.query_selector("span.CjyrHS, div.MKiFS6")
                if rat_el:
                    try: rating = float(rat_el.inner_text().strip())
                    except: pass
                if rating == 0:
                    for el in item.query_selector_all("span, div"):
                        try:
                            txt = el.inner_text().strip()
                            if re.match(r'^[1-5]\.[0-9]$', txt):
                                rating = float(txt)
                                break
                        except: continue

                review_count = 0
                rev_el = item.query_selector("span.PvbNMB")
                if rev_el:
                    try:
                        nums = re.findall(r'\d+', rev_el.inner_text().replace(",", ""))
                        if nums: review_count = int(nums[0])
                    except: pass
                if review_count == 0:
                    try:
                        m = re.search(r'([\d,]+)\s*(ratings|reviews)', item.inner_text(), re.I)
                        if m: review_count = int(m.group(1).replace(",", ""))
                    except: pass

                offer = ""
                for oel in item.query_selector_all("div.hx1EGN"):
                    ot = oel.inner_text().strip()
                    if ot:
                        offer = ot
                        break

                image = ""
                for img_el in item.query_selector_all("img[src]"):
                    src = img_el.get_attribute("src") or ""
                    if "rukminim" in src:
                        image = src
                        break
                if not image:
                    img_el = item.query_selector("img")
                    if img_el: image = img_el.get_attribute("src") or ""

                product_link = ""
                for a_el in item.query_selector_all("a[href*='/p/']"):
                    href = a_el.get_attribute("href") or ""
                    if href:
                        product_link = href if href.startswith("http") else "https://www.flipkart.com" + href
                        break

                products.append({
                    "product_name": title, "price_inr": price,
                    "original_price": orig, "discount_percent": discount,
                    "store": "Flipkart", "delivery_days": 3,
                    "delivery_label": "2-4 days", "rating": rating,
                    "review_count": review_count, "offer": offer,
                    "stock_status": "In Stock", "is_reliable": True,
                    "image": image, "product_link": product_link,
                    "match_score": score, "is_best_price": False,
                })
                print(f"  -> KEPT: {title[:60]} | Rs.{price}")

            except Exception as e:
                print(f"  ITEM ERROR: {e}")

        context.close()
        browser.close()

    print(f"\nFinal Flipkart count: {len(products)}")
    return finalize_products(products, "Flipkart", query)