import re                  # For pattern matching (extracting prices, numbers, codes from text)
import random              # For adding random delays so we don't look like a bot
import time                # For adding wait/sleep pauses between page actions
from collections import Counter          # For counting frequency of values (used in price scanning)
from playwright.sync_api import sync_playwright  # Playwright controls a real browser to scrape pages


# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(text):
    # Converts text to a clean, lowercase, letters/numbers-only format
    # Used before comparing titles so "iPhone 15" and "iphone  15!" both become "iphone 15"
    if not text:
        return ""
    text = text.lower()                          # Make everything lowercase
    text = re.sub(r"[^a-z0-9\s]", " ", text)   # Remove anything that isn't a letter, number, or space
    text = re.sub(r"\s+", " ", text)            # Collapse multiple spaces into one
    return text.strip()                          # Remove leading/trailing whitespace


# =========================================================
# SANITIZE SEARCH QUERY
# =========================================================

def sanitize_search_query(query: str) -> str:
    # Cleans up a search query string before sending it to Amazon/Flipkart
    query = re.sub(r'/[A-Za-z0-9]{1,6}', '', query)     # Remove short slash-suffixes like "/Pro" or "/128"
    query = re.sub(r'[^\w\s.]', ' ', query)              # Remove special characters (keep letters, numbers, spaces, dots)
    query = re.sub(r'(?<!\d)\.(?!\d)', ' ', query)       # Remove dots that aren't decimal points
    query = re.sub(r'\s+', ' ', query).strip()           # Collapse spaces and trim
    return query


# =========================================================
# EXTRACT NUMBERS
# =========================================================

def extract_numbers(text: str) -> set:
    # Pulls out all number sequences from text as a set
    # e.g. "iPhone 15 128GB" → {"15", "128"}
    return set(re.findall(r'\d+', text.lower()))


# =========================================================
# EXTRACT ALPHANUMERIC CODES
# =========================================================

def extract_alphanum_codes(text: str) -> set:
    # Extracts SKU/model codes that contain BOTH letters AND digits
    # e.g. "RT40H28U3FHL", "K14x", "GLS18I5KWFGR"
    # Pure numbers ("128") and pure words ("iPhone") are excluded — only mixed codes
    return set(re.findall(
        r'\b(?=[a-z0-9]*[a-z])(?=[a-z0-9]*[0-9])[a-z0-9]+\b',
        text.lower()
    ))


# =========================================================
# IRRELEVANT PRODUCT FILTER
# =========================================================

# Words that indicate a product is an accessory or add-on, not the main product
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
    # Returns True if this product is an accessory we should ignore
    # Only applies when the user wants the MAIN product (not a spare part or accessory)
    if canonical_product.get("intent_type", "main_product") != "main_product":
        return False   # User explicitly wants an accessory — don't filter it out
    t = normalize_text(title)
    return any(word in t for word in IRRELEVANT_WORDS)


# =========================================================
# HELPERS
# =========================================================

# Maps gender labels to the words we expect to see in product titles
GENDER_GROUPS = {
    "men":    ["men", "mens", "male", "man"],
    "women":  ["women", "womens", "female", "woman", "ladies"],
    "boys":   ["boys", "boy", "kids", "child", "children"],
    "girls":  ["girls", "girl", "kids", "child", "children"],
    "unisex": ["unisex"],
}

# Maps each gender to the words that would mean the WRONG gender
# Used to reject products aimed at the opposite gender
OPPOSITE_GENDER = {
    "men":   ["women", "womens", "female", "woman", "ladies"],
    "women": ["men", "mens", "male", "man"],
    "boys":  ["girls", "women", "womens"],
    "girls": ["boys", "men", "mens"],
}

# List of color names we look for in product titles
COMMON_COLORS = [
    "black", "white", "grey", "gray", "blue", "red", "green", "pink",
    "yellow", "orange", "purple", "brown", "navy", "silver", "gold",
    "beige", "cream", "teal", "multicolor", "multi", "volt", "cyan",
    "olive", "maroon", "carbon", "titanium", "midnight", "starlight",
    "natural", "desert", "coral", "lavender", "sage", "graphite",
]

MIN_VALID_PRICE = 10.0   # Any price below ₹10 is considered invalid/scraped wrongly

# Known brand names — used to detect if a competing brand is in the product title
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
    # Returns True if the model is a single alphanumeric code (like "RT40H28U3FHL")
    # rather than a human-readable name (like "iPhone 15 Pro")
    tokens = model.strip().split()
    if len(tokens) != 1:
        return False   # Must be exactly one token (no spaces)
    tok = tokens[0]
    return (len(tok) >= 4                          # At least 4 characters long
            and bool(re.search(r'[a-zA-Z]', tok)) # Contains at least one letter
            and bool(re.search(r'\d', tok)))       # Contains at least one digit


# =========================================================
# PRICE BOUNDS BY CATEGORY
# =========================================================

def get_price_bounds(canonical_product: dict):
    # Returns (min_price, max_price) for the product's category
    # Helps reject obviously wrong prices (e.g. a ₹50 smartphone is clearly wrong)
    pt   = normalize_text(canonical_product.get("product_type", ""))
    size = normalize_text(canonical_product.get("size", ""))

    # TVs — price range depends on screen size
    if "tv" in pt or "television" in pt:
        size_nums = re.findall(r'\d+', size)
        screen = int(size_nums[0]) if size_nums else 0
        if screen >= 55:   return (25000, 500000)   # 55"+ TVs
        elif screen >= 43: return (12000, 300000)   # 43"-54" TVs
        elif screen >= 32: return (5000,  200000)   # 32"-42" TVs
        else:              return (3000,  200000)   # Smaller TVs

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

    if "iron"    in pt:                           return (200,  10000)
    if "mixer"   in pt or "grinder" in pt:        return (500,  20000)
    if "pressure cooker" in pt or "cooker" in pt: return (300, 10000)
    if "trimmer" in pt:                           return (200,  10000)
    if "hair dryer" in pt:                        return (200,  10000)
    if "microwave" in pt:                         return (3000, 60000)
    if "water purifier" in pt:                    return (3000, 80000)

    # Groceries / food items
    if "butter"   in pt: return (30,  1000)
    if "masala"   in pt: return (20,  2000)
    if "spice"    in pt: return (20,  2000)
    if "oil"      in pt: return (50,  5000)
    if "flour"    in pt: return (30,  2000)
    if "coffee"   in pt: return (50,  5000)
    if "tea"      in pt: return (30,  3000)

    if "watch" in pt: return (5000, 500000)

    return (MIN_VALID_PRICE, 500000)   # Default fallback — accept almost any price


def validate_price(price: float, canonical_product: dict) -> bool:
    # Returns True if the price falls within the expected range for this product type
    if price <= 0:
        return False   # Zero or negative price is always invalid
    min_p, max_p = get_price_bounds(canonical_product)
    if price < min_p or price > max_p:
        print(f"    [PRICE REJECT] Rs.{price} outside bounds Rs.{min_p}-Rs.{max_p}")
        return False
    return True


# =========================================================
# HARD FILTER
# =========================================================

def hard_filter(title: str, canonical_product: dict, store: str = "Amazon") -> bool:
    # The main gatekeeper — returns False to REJECT a product, True to KEEP it
    # Checks brand, model, variant, storage, size, gender, color one by one
    # If ANY critical check fails, the product is rejected immediately

    t = normalize_text(title)      # Normalized title for easy comparison
    tokens = set(t.split())        # Individual words in the title as a set

    # ── CHECK 1: BRAND ────────────────────────────────────────────────────
    brand = normalize_text(canonical_product.get("brand", ""))
    product_type_norm = normalize_text(canonical_product.get("product_type", ""))
    model_norm_check = normalize_text(canonical_product.get("model", ""))

    if brand:
        brand_tokens = set(brand.split())

        # Every word of the brand must appear in the title
        # e.g. if brand is "oneplus", "oneplus" must be in the title
        if not brand_tokens.issubset(tokens):
            print(f"    [HARD FILTER] Brand mismatch: '{title[:60]}'")
            return False

        # Collect all words that belong to our product (brand + type + model)
        own_words = brand_tokens | set(product_type_norm.split()) | set(model_norm_check.split())

        # Check if a DIFFERENT known brand appears in the title
        # e.g. user wants Samsung, but title has "Compatible with Apple"
        competing = [
            b for b in KNOWN_BRANDS
            if b in tokens                                      # This brand is in the title
            and b not in own_words                             # It's not our own brand
            and not any(bt in b for bt in brand_tokens)        # It's not a substring of our brand
            and not any(b in bt for bt in brand_tokens)        # Our brand isn't a substring of it
            and not any(b in w for w in own_words)             # It's not part of our product name
        ]
        if competing:
            print(f"    [HARD FILTER] Competing brand {competing}: '{title[:60]}'")
            return False

    # ── CHECK 2: MODEL ───────────────────────────────────────────────────
    raw_model = canonical_product.get("model", "")
    raw_model = re.sub(r'/\w+$', '', raw_model).strip()   # Remove trailing slash variants like "/128GB"
    model_norm = normalize_text(raw_model)

    if model_norm:
        if is_product_code(model_norm):
            # Model is a code like "RT40H28U3FHL" — look for it character-by-character
            model_codes = extract_alphanum_codes(model_norm)
            title_codes = extract_alphanum_codes(t)

            if model_codes and not model_codes.issubset(title_codes):
                # The exact code isn't in the title — try to rescue it via year or star rating
                canon_variant = normalize_text(canonical_product.get("variant", ""))
                canon_years = re.findall(r'20\d{2}', canon_variant)

                if canon_years:
                    # If a year was specified (e.g. "2023 model"), check the title has the same year
                    title_years = re.findall(r'20\d{2}', t)
                    if title_years and not any(y in title_years for y in canon_years):
                        print(f"    [HARD FILTER] Year mismatch (need {canon_years}): '{title[:60]}'")
                        return False

                # If a star rating was specified (e.g. "3 star AC"), check the title matches
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

                # Check if a DIFFERENT product code appears in the title (wrong model entirely)
                other_codes = re.findall(r'\b[a-z]{2,4}\d{2,}[a-z0-9]*\b', t)
                if other_codes and not any(list(model_codes)[0][:4] in oc for oc in other_codes):
                    print(f"    [HARD FILTER] Different product code in title: '{title[:60]}'")
                    return False

                print(f"    [SOFT] Code absent, variant matched: '{title[:60]}'")

        else:
            # Model is a readable name like "iPhone 15 Pro" — check word by word
            model_codes = extract_alphanum_codes(model_norm)
            if model_codes:
                # If the model name contains a code (like "15" in "iPhone 15"), check it's in the title
                title_codes = extract_alphanum_codes(t)
                print("MODEL:", model_norm)
                print("TITLE:", title)
                print("MODEL_CODES:", model_codes)
                print("TITLE_CODES:", title_codes)
                if not model_codes.issubset(title_codes):
                    print(f"    [HARD FILTER] Model code mismatch (need {model_codes}): '{title[:60]}'")
                    return False
            else:
                # No codes — just compare numbers (e.g. "Galaxy A54" needs "54" in title)
                model_numbers = extract_numbers(model_norm)
                if model_numbers:
                    title_numbers = extract_numbers(title)
                    if title_numbers and not model_numbers.issubset(title_numbers):
                        print(f"    [HARD FILTER] Model numbers mismatch (need {model_numbers}): '{title[:60]}'")
                        return False

            # Check that most of the model's words appear in the title
            model_tokens = model_norm.split()
            skip_words = {"edition", "series", "gen", "generation", "new"}   # Words we can ignore
            essential = [tok for tok in model_tokens if tok not in skip_words]

            if len(essential) >= 2:
                matched = sum(1 for tok in essential if tok in tokens)
                # Need at least 50% match for 2-word models, 60% for longer
                threshold = 0.5 if len(essential) == 2 else 0.6
                if matched / len(essential) < threshold:
                    print(f"    [HARD FILTER] Model token mismatch: '{title[:60]}'")
                    return False
                # For 2-word models, the FIRST word must always match (it's usually the key identifier)
                if len(essential) == 2 and matched == 1:
                    if essential[0] not in tokens:
                        print(f"    [HARD FILTER] Primary model token missing: '{title[:60]}'")
                        return False

            # Check that tier suffixes match exactly
            # e.g. user wants "Pro Max" — reject "Pro" or "Max" alone
            tier_suffixes = {"max", "plus", "ultra", "lite", "mini"}
            model_tiers = {s for s in tier_suffixes if s in set(model_tokens)}    # Tiers in what we want
            title_tiers  = {s for s in tier_suffixes if s in tokens}              # Tiers in the title

            if model_tiers != title_tiers:
                print(f"    [HARD FILTER] Tier mismatch (model={model_tiers}, title={title_tiers}): '{title[:60]}'")
                return False

    # ── CHECK 3: VARIANT SKU ─────────────────────────────────────────────
    variant = normalize_text(canonical_product.get("variant", ""))
    if variant:
        variant_codes = extract_alphanum_codes(variant)
        if variant_codes:
            # If the variant has a code (e.g. specific color code), it must appear in the title
            title_codes = extract_alphanum_codes(t)
            if not variant_codes.issubset(title_codes):
                print(f"    [HARD FILTER] Variant code mismatch (need {variant_codes}): '{title[:60]}'")
                return False

    # ── CHECK 4: PRODUCT NAME (for no-SKU products like groceries) ───────
    has_model = bool(canonical_product.get("model", "").strip())
    has_variant_code = bool(extract_alphanum_codes(variant)) if variant else False

    if not has_model and not has_variant_code:
        # For products with no model or SKU (e.g. "Amul Butter"), match on product type words
        product_type = normalize_text(canonical_product.get("product_type", ""))
        brand_tokens_set = set(normalize_text(brand).split()) if brand else set()
        pt_tokens = set(product_type.split())
        name_tokens = pt_tokens - brand_tokens_set   # Remove brand words from the type

        # Generic words that don't help distinguish products
        STOP_WORDS = {
            "masala", "powder", "mix", "sauce", "paste", "oil", "spice", "spices",
            "food", "product", "item", "pack", "box", "bottle", "pouch",
            "kg", "g", "ml", "l", "100", "200", "500", "1000",
            "with", "and", "for", "the", "of", "in", "a",
        }
        distinctive = name_tokens - STOP_WORDS   # Only keep words that are truly distinctive

        if distinctive:
            # All distinctive words must appear in the title
            missing = [tok for tok in distinctive if tok not in tokens]
            if missing:
                print(f"    [HARD FILTER] Product name mismatch (missing {missing}): '{title[:60]}'")
                return False

    # ── CHECK 5: STORAGE ─────────────────────────────────────────────────
    storage_raw = (canonical_product.get("storage") or
                   canonical_product.get("storage_capacity") or "")
    if storage_raw:
        storage_numbers = extract_numbers(storage_raw)
        if storage_numbers:
            # Only check storage if the title actually mentions a storage unit (GB/TB/MB)
            if any(kw in title.lower() for kw in ["gb", "tb", "mb"]):
                title_numbers = extract_numbers(title)
                if not storage_numbers.issubset(title_numbers):
                    print(f"    [HARD FILTER] Storage mismatch (need {storage_numbers}): '{title[:60]}'")
                    return False

    # ── CHECK 5b: CAPACITY (litres, kg, tons) ────────────────────────────
    size_raw = canonical_product.get("size", "")
    if size_raw:
        # Handle capacity given as a RANGE (e.g. "200L - 300L" for a water tank)
        range_match = re.search(r'(\d+)\s*[lL]\s*[-]\s*(\d+)\s*[lL]', size_raw)
        if range_match:
            lo_l = int(range_match.group(1))
            hi_l = int(range_match.group(2))
            title_litres = [int(m.group(1)) for m in re.finditer(r'(\d+)\s*[lL](?:|\s)', title)]
            if title_litres:
                # Title's litre value must fall within the requested range
                if not any(lo_l <= v <= hi_l for v in title_litres):
                    print(f"    [HARD FILTER] Capacity range {lo_l}L-{hi_l}L mismatch "
                          f"(title has {title_litres}): '{title[:60]}'")
                    return False

        # Handle exact litre capacity (e.g. "5 litre pressure cooker")
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

        # Handle kg / ton capacity (e.g. "1.5 ton AC", "7 kg washing machine")
        elif any(kw in size_raw.lower() for kw in ["kg", "ton", "tons"]):
            size_numbers = extract_numbers(size_raw)
            if size_numbers and any(kw in title.lower() for kw in ["kg", "ton", "tons"]):
                title_numbers = extract_numbers(title)
                if not size_numbers.issubset(title_numbers):
                    print(f"    [HARD FILTER] Capacity mismatch (need {size_numbers}): '{title[:60]}'")
                    return False

    # ── CHECK 6: WEIGHT / VOLUME / PACK SIZE ─────────────────────────────
    def extract_weight_pairs(text: str) -> set:
        # Extracts (amount, unit) pairs like (100, "g"), (1, "kg"), (500, "ml")
        return set(
            (int(m.group(1)), m.group(2).lower().strip())
            for m in re.finditer(
                r'\b(\d+)\s*(g|kg|gm|gms|ml|l|litre|liter|oz|lb)\b',
                text.lower()
            )
        )

    # Check weight/pack size/volume — whichever one the user specified
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
                # At least one (amount, unit) pair must match between what we want and the title
                if not canon_pairs.intersection(title_pairs):
                    print(f"    [HARD FILTER] Weight mismatch "
                          f"(need {canon_pairs}, title has {title_pairs}): '{title[:60]}'")
                    return False

    # ── CHECK 7: GENDER ──────────────────────────────────────────────────
    user_gender = normalize_text(canonical_product.get("gender", ""))
    if user_gender and user_gender in OPPOSITE_GENDER:
        # Reject if the title contains words for the OPPOSITE gender
        # e.g. user wants men's shoes, title says "women's running shoes"
        if any(w in tokens for w in OPPOSITE_GENDER[user_gender]):
            print(f"    [HARD FILTER] Gender mismatch: '{title[:60]}'")
            return False

    # ── CHECK 8: COLOR (Amazon only) ─────────────────────────────────────
    user_color = normalize_text(canonical_product.get("color", ""))
    if user_color and store == "Amazon":
        user_color_tokens = set(user_color.split())
        title_colors = [c for c in COMMON_COLORS if c in tokens]   # Colors mentioned in title
        if title_colors:
            # Check if any of the user's requested colors appear in the title
            match = any(uc in title_colors for uc in user_color_tokens)
            # Exception: if user requested 2+ colors (e.g. "midnight blue"), don't be too strict
            if not match and not (len(user_color_tokens) >= 2 and len(title_colors) == 1):
                print(f"    [HARD FILTER] Color mismatch (has {title_colors}, want {user_color}): '{title[:60]}'")
                return False

    return True   # All checks passed — product is a valid match


# =========================================================
# PACK / COMBO DETECTION
# =========================================================

# Pattern to detect "Pack of 3", "(3 Pack)", "x3" in product titles
PACK_PATTERN = re.compile(r'pack\s*of\s*(\d+)|\(\s*(\d+)\s*pack\s*\)|x\s*(\d+)\b', re.IGNORECASE)

COMBO_INDICATORS = ["&", "+", "combo", "bundle", "set of", "kit"]   # Words that suggest a combo listing


def detect_pack_count(title: str) -> int:
    # Returns how many units are in a pack, e.g. "Pack of 3" → 3
    # Returns 1 if no pack info is found (i.e. it's a single item)
    m = PACK_PATTERN.search(title)
    if m:
        for g in m.groups():
            if g:
                return int(g)
    return 1


def is_combo_listing(title: str, canonical_product: dict) -> bool:
    # Returns True if this is a combo/bundle of DIFFERENT products
    # (not just multiple units of the same product)
    t = title.lower()
    brand = normalize_text(canonical_product.get("brand", ""))

    # Remove the brand name from the title so brand repetition doesn't cause false detection
    title_without_brand = title
    raw_brand = canonical_product.get("brand", "")
    if raw_brand:
        title_without_brand = re.sub(re.escape(raw_brand), "", title, flags=re.IGNORECASE)

    # " & " or " + " between product names usually signals a combo (e.g. "Shampoo & Conditioner")
    if re.search(r'\s[&+]\s', title_without_brand):
        return True

    # Words like "combo", "bundle", "kit" explicitly indicate multiple products
    if any(w in t for w in ["combo", "bundle", "set of", "kit", "value pack"]):
        return True

    # If the brand name appears twice in the title, it's likely bundling 2 different products
    if brand and t.count(brand.lower()) >= 2:
        return True

    return False


# =========================================================
# MATCH SCORE
# =========================================================

def calculate_match_score(title: str, canonical_product: dict, store: str = "Amazon") -> int:
    # Calculates how well a product title matches what the user is looking for
    # Returns a score (higher = better match); 0 means rejected

    # Immediate rejection if irrelevant accessory or fails the hard filter
    if is_irrelevant_product(title, canonical_product):
        return 0
    if not hard_filter(title, canonical_product, store=store):
        return 0

    score = 0
    t = normalize_text(title)
    tokens = set(t.split())

    # +60 points if product type matches (e.g. "smartphone", "shoes")
    product_type = normalize_text(canonical_product.get("product_type", ""))
    if product_type:
        pt_tokens = product_type.split()
        matched = sum(1 for tok in pt_tokens if tok in tokens)
        score += int((matched / len(pt_tokens)) * 60)

    # +50 points if brand fully matches, +15 if partial, -40 if brand not found
    brand = normalize_text(canonical_product.get("brand", ""))
    if brand:
        brand_tokens = brand.split()
        matched = sum(1 for tok in brand_tokens if tok in tokens)
        if matched == len(brand_tokens): score += 50
        elif matched > 0: score += 15
        else: score -= 40

    # +70 points (max) based on how many model words match; bonus +30 if 80%+ match
    raw_model = re.sub(r'/\w+$', '', canonical_product.get("model", "")).strip()
    model = normalize_text(raw_model)
    if model:
        model_tokens = model.split()
        matched = sum(1 for tok in model_tokens if tok in tokens)
        ratio = matched / len(model_tokens)
        score += int(ratio * 70)
        if ratio >= 0.8: score += 30

    # +10 per matching variant word
    variant = normalize_text(canonical_product.get("variant", ""))
    if variant:
        matched = sum(1 for tok in variant.split() if tok in tokens)
        score += matched * 10

    # +20 if gender matches (e.g. "men" found in title when user wants men's shoes)
    user_gender = normalize_text(canonical_product.get("gender", ""))
    if user_gender and user_gender in GENDER_GROUPS:
        if any(w in tokens for w in GENDER_GROUPS[user_gender]):
            score += 20

    # +5 per matching word for other fields like storage, color, size, RAM, etc.
    for field in ["storage", "storage_capacity", "size", "pack_size", "flavor",
                  "weight", "quantity", "version", "color", "ram", "shoe_size",
                  "resolution", "panel_type", "connectivity", "volume"]:
        value = normalize_text(canonical_product.get(field, ""))
        if not value:
            continue
        matched = sum(1 for tok in value.split() if tok in tokens)
        score += matched * 5

    # ── Multi-pack / combo penalty ────────────────────────────────────────
    pack_count = detect_pack_count(title)   # How many units in this listing?
    canon_pack = canonical_product.get("pack_count") or canonical_product.get("quantity")

    if pack_count > 1:
        if canon_pack and str(pack_count) == str(canon_pack):
            pass   # User asked for exactly this pack size — no penalty
        else:
            score -= 100   # User wants 1 unit but this is a multi-pack — big penalty

    # -100 if it's a combo listing (unless user specifically wants a bundle)
    if canonical_product.get("intent_type") != "bundle":
        if is_combo_listing(title, canonical_product):
            score -= 100

    return score


# =========================================================
# DYNAMIC MINIMUM SCORE
# =========================================================

def get_minimum_score(canonical_product: dict) -> int:
    # Calculates the minimum acceptable match score for this query
    # More detailed queries require a higher score to pass (stricter matching)
    # Simpler queries (like groceries) get a lower threshold

    # Count how many fields the user actually specified
    filled = sum(
        1 for f in ["brand", "product_type", "variant", "model", "storage",
                    "size", "flavor", "gender", "color", "shoe_size", "ram", "resolution"]
        if canonical_product.get(f)
    )

    intent = canonical_product.get("intent_type", "main_product")

    # Check if this is a food/grocery item (they get lower thresholds — titles vary a lot)
    is_grocery = intent in ("consumable", "food") or any(
        kw in normalize_text(canonical_product.get("product_type", ""))
        for kw in ["masala", "spice", "powder", "sauce", "paste", "butter",
                   "oil", "flour", "sugar", "salt", "rice", "dal", "tea", "coffee"]
    )

    # More filled fields = stricter threshold needed
    if filled >= 5: return 55
    elif filled >= 4: return 50
    elif filled >= 3: return 45 if not is_grocery else 40
    elif filled >= 2: return 40 if not is_grocery else 35
    else: return 25


# =========================================================
# DUPLICATE FILTER
# =========================================================

def remove_duplicates(products):
    # Removes products with identical normalized titles
    # Keeps the first occurrence (which is already sorted by score)
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
    # Converts a raw price string like "₹1,29,999" to a float like 129999.0
    try:
        cleaned = raw.replace("\u20b9", "").replace(",", "").strip()  # Remove ₹ symbol and commas
        match = re.search(r'\d+(\.\d+)?', cleaned)                    # Find the number
        val = float(match.group()) if match else 0.0
        return val if val >= MIN_VALID_PRICE else 0.0                 # Return 0 if suspiciously low
    except Exception:
        return 0.0


# =========================================================
# AMAZON TITLE EXTRACTION
# =========================================================

def extract_title_amazon(item, debug: bool = False) -> str:
    # Tries multiple CSS selectors to find the product title in an Amazon search result card
    # Returns the longest valid title found (longer usually = more complete)

    BAD_VALUES = {"sponsored", "amazon"}   # Titles that aren't real product names

    # List of CSS selectors to try, in order of preference
    # Each entry is (selector, attribute) — attribute is None if we want inner text
    SELECTORS = [
        ("h2 a span",                                            None),
        ("h2 span.a-text-normal",                                None),
        ("h2 span",                                              None),
        ("h2 a",                                                 "aria-label"),
        ("[data-cy='title-recipe'] span.a-text-normal",         None),
        ("[data-cy='title-recipe'] span",                        None),
        ("[data-cy='title-recipe'] a span",                     None),
        ("img.s-image",                                          "alt"),       # Fallback: use image alt text
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
            # Get text from attribute (e.g. aria-label) or inner text
            text = (el.get_attribute(attr) or "") if attr else (el.inner_text() or "")
            text = re.sub(r"^sponsored\s*", "", text.strip(), flags=re.IGNORECASE)   # Strip "Sponsored" prefix
            if text.lower() in BAD_VALUES or len(text) < 5:
                continue   # Skip junk values
            if len(text) > len(best_title):
                best_title = text   # Keep the longest valid title found so far
            if debug:
                print(f"  [title] {selector} -> {text[:60]}")
        except Exception:
            continue

    return best_title


# =========================================================
# PRICE SELECTORS
# =========================================================

# CSS selectors to find prices on Amazon product cards
AMAZON_PRICE_SELECTORS = [
    ".a-price-whole",               # Main price (integer part)
    ".a-price .a-offscreen",        # Screen-reader price (usually most complete)
    ".a-color-price",               # Red sale price
    ".a-price-range",               # Price range (for variable products)
]

# CSS selectors to find the original (before discount) price on Amazon
AMAZON_ORIG_PRICE_SELECTORS = [
    ".a-price.a-text-price .a-offscreen",
    "span.a-text-price .a-offscreen",
    ".a-text-strike",               # Strikethrough price
]

# CSS selectors to find prices on Flipkart product cards
FLIPKART_PRICE_SELECTORS = [
    "div.oFEPlD", "div.Nx9bqj", "div._30jeq3",
    "div.CxhGGd", "div._1vC4OE", "div.hl05eU div.Nx9bqj",
]

# CSS selectors to find original (before discount) price on Flipkart
FLIPKART_ORIG_PRICE_SELECTORS = [
    "div.yRaY8j", "div.__6Jmc", "div.sIstCe", "div.struck", "div._3I9_wc",
]

# CSS selectors to find product titles on Flipkart cards
FLIPKART_TITLE_SELECTORS = [
    "div.RG5Slk", "div.KzDlHZ", "div.wjcEIp",
    "a.WKTcLC", "a.IRpwTa", "a.s1Q9rs",
    "div._4rR01T", "div._2WkVRV",
]


# =========================================================
# PRICE HELPERS
# =========================================================

def scrape_price_amazon(item):
    # Tries known CSS selectors first, then falls back to scanning all price-like elements
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
                    return p   # Found a valid price — return immediately
            except Exception as e:
                print(f"PRICE PARSE ERROR: {e}")

    # Fallback: scan all elements that might have a price in them
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

    # Second fallback: any element starting with ₹ that's short enough to be a price
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
        # Use frequency analysis — the most common value is likely the real price
        # If tied, take the minimum (most conservative)
        freq = Counter(candidates)
        max_freq = max(freq.values())
        price = min(v for v, c in freq.items() if c == max_freq)
        print(f"    [price] scan -> {price}")
        return price

    print("NO AMAZON PRICE FOUND")
    return 0.0


def scrape_orig_price_amazon(item, price):
    # Tries to find the original MRP (before discount) on Amazon
    # Returns 0 if the original price is invalid (e.g. lower than current or 5x higher = suspect)
    for sel in AMAZON_ORIG_PRICE_SELECTORS:
        for el in item.query_selector_all(sel):
            op = parse_price(el.inner_text())
            if op > price and op < price * 5 and op < 500000:
                return op   # Valid original price found
    return 0.0


def scrape_price_flipkart(item):
    # Tries known Flipkart price selectors first, then scans all ₹ elements
    for sel in FLIPKART_PRICE_SELECTORS:
        el = item.query_selector(sel)
        if el:
            p = parse_price(el.inner_text())
            if p > 0:
                print(f"    [price] class '{sel}' -> {p}")
                return p

    # Fallback: scan for any short element starting with ₹
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
        # Same frequency analysis as Amazon
        freq = Counter(candidates)
        max_freq = max(freq.values())
        price = min(v for v, c in freq.items() if c == max_freq)
        print(f"    [price] scan -> {price} (candidates: {sorted(set(candidates))[:5]})")
        return price
    return 0.0


def scrape_orig_price_flipkart(item, price):
    # Finds the original (before discount) price on Flipkart
    for sel in FLIPKART_ORIG_PRICE_SELECTORS:
        el = item.query_selector(sel)
        if el:
            op = parse_price(el.inner_text())
            if op > price and op < price * 5 and op < 500000:
                return op
    return 0.0


def calc_discount(price, original_price):
    # Calculates the discount percentage given sale price and original price
    # Returns (discount_percent, original_price) or (0, 0) if invalid
    if original_price > 0 and price > 0 and original_price > price:
        d = round((1 - price / original_price) * 100)
        if 1 <= d <= 90:   # Only accept discounts between 1% and 90% (anything else is suspicious)
            return d, original_price
    return 0, 0


# =========================================================
# SHARED BROWSER LAUNCHER
# =========================================================

def launch_browser(p):
    # Launches a headless Chromium browser that looks like a real user's browser
    # "headless" means no visible window — it runs in the background
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",  # Hide the "controlled by automation" flag
            "--no-sandbox", "--disable-setuid-sandbox",        # Required for running in containers
            "--disable-infobars", "--disable-dev-shm-usage",  # Remove bot-detection hints
            "--disable-extensions", "--window-size=1280,800",
        ]
    )

    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),                                       # Pretend to be a normal Windows Chrome browser
        locale="en-IN",                          # Indian English locale
        timezone_id="Asia/Kolkata",              # Indian timezone
        viewport={"width": 1280, "height": 800}, # Standard screen size
        extra_http_headers={
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
    )

    # Override the webdriver property that websites use to detect bots
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )

    return browser, context


def make_empty_result(store, query, message=None):
    # Creates a placeholder "no results" product when scraping finds nothing
    # Links directly to the search page so the user can check manually
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
    # Cleans up the final product list before returning it:
    # 1. Remove duplicates
    # 2. Sort by match score (highest first), then rating as tiebreaker
    # 3. Mark the cheapest as "best price"
    # 4. Return only the top 1 result (or an empty result if nothing was found)
    products = remove_duplicates(products)
    products.sort(key=lambda x: (x["match_score"], x["rating"]), reverse=True)
    if products:
        priced = [p for p in products if p["price_inr"] > 0]
        if priced:
            min(priced, key=lambda x: x["price_inr"])["is_best_price"] = True
    return products[:1] if products else make_empty_result(store, query)


def scrape_with_fallback(scrape_fn, query, canonical_product, intent_type):
    # Wrapper that tries up to 4 different query strategies before giving up
    # This ensures we return SOMETHING even when the ideal search fails

    # ── Pass 1: Try the original query ──────────────────────────────────
    results = scrape_fn(query, canonical_product, intent_type)
    real = [p for p in results if p.get("is_reliable") and p.get("price_inr", 0) > 0]
    if real:
        return results   # Found reliable results — done

    # ── Pass 2: Try a shorter/simpler query (brand + model only) ────────
    brand   = canonical_product.get("brand", "")
    model   = canonical_product.get("model", "")
    pt      = canonical_product.get("product_type", "")
    size    = canonical_product.get("size", "") or canonical_product.get("weight", "")

    if model and brand:
        short_query = f"{brand} {model}".strip()       # e.g. "Apple iPhone 15"
    elif brand and pt:
        short_query = f"{brand} {pt} {size}".strip()  # e.g. "Samsung TV 55"
    else:
        short_query = query

    short_query = sanitize_search_query(short_query)

    if short_query != query and len(short_query) >= 5:
        print(f"  [FALLBACK P2] Retrying with shorter query: '{short_query}'")
        results2 = scrape_fn(short_query, canonical_product, intent_type)
        real2 = [p for p in results2 if p.get("is_reliable") and p.get("price_inr", 0) > 0]
        if real2:
            return results2

    # ── Pass 3: Remove the brand filter and search more broadly ─────────
    print(f"  [FALLBACK P3] Retrying without brand filter...")
    relaxed = dict(canonical_product)     # Copy canonical product
    relaxed.pop("brand", None)            # Remove brand so hard_filter doesn't reject brand mismatches
    results3 = scrape_fn(query, relaxed, intent_type)
    real3 = [p for p in results3 if p.get("is_reliable") and p.get("price_inr", 0) > 0]
    if real3:
        for p in real3:
            # Add a note so the frontend knows this is a similar product, not exact
            p["offer"] = p.get("offer", "") or "Similar product shown"
        return results3

    # ── Pass 4: Try with just model + product type, minimal filters ──────
    if not [p for p in results3 if p.get("is_reliable") and p.get("price_inr", 0) > 0]:
        model = canonical_product.get("model", "")
        pt = canonical_product.get("product_type", "")
        if model and pt:
            generic_query = f"{model} {pt}"
            generic_query = sanitize_search_query(generic_query)
            print(f"  [FALLBACK P4] Generic model+type query: '{generic_query}'")

            # Only keep the most essential fields for the filter check
            generic_canon = {
                k: v for k, v in canonical_product.items()
                if k in ("brand", "model", "product_type", "storage", "storage_capacity")
            }
            results4 = scrape_fn(generic_query, generic_canon, intent_type)
            real4 = [p for p in results4 if p.get("is_reliable") and p.get("price_inr", 0) > 0]
            if real4:
                return results4

    # All 4 passes failed — return whatever we have (even if empty/unreliable)
    return results


# =========================================================
# AMAZON SCRAPER
# =========================================================

def scrape_amazon(query, canonical_product, intent_type="main_product", debug_titles=False):
    query = sanitize_search_query(query)           # Clean up the query first
    min_score = get_minimum_score(canonical_product)  # Calculate how strict we need to be

    print(f"\n{'='*60}\nScraping Amazon for: {query}")
    print(f"Canonical: {canonical_product}")
    print(f"Min score: {min_score}\n{'='*60}\n")

    products = []   # Will collect all valid matched products

    with sync_playwright() as p:
        browser, context = launch_browser(p)   # Start the browser
        page = context.new_page()              # Open a new tab

        # Build the Amazon search URL and navigate to it
        url = "https://www.amazon.in/s?k=" + query.replace(" ", "+")
        print(f"URL: {url}\n")
        page.goto(url, timeout=60000, wait_until="domcontentloaded")

        # Scroll down and back to trigger lazy-loaded content (like images and prices)
        page.evaluate("window.scrollTo(0, 400)")
        time.sleep(1.5)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)

        # Wait for product cards to appear on the page
        try:
            page.wait_for_selector('[data-component-type="s-search-result"]', timeout=20000)
        except Exception:
            print("WARNING: Primary selector timed out, trying fallback")
            try:
                page.wait_for_selector('div[data-asin]:not([data-asin=""])', timeout=8000)
            except Exception:
                print("WARNING: Both selectors timed out")

        time.sleep(random.uniform(1.5, 2.5))   # Random pause to avoid bot detection

        page_title = page.title()
        print(f"Page title: {page_title}")

        # If Amazon showed a CAPTCHA or block page, abort and return empty result
        if any(w in page_title.lower() for w in ["robot", "captcha", "sorry", "blocked"]):
            browser.close()
            return make_empty_result("Amazon", query, "Amazon is temporarily blocking. Try again.")

        # Find all product cards on the search results page
        items = page.query_selector_all("div[data-component-type='s-search-result'][data-asin]")
        if not items:
            items = page.query_selector_all("div[data-asin]:not([data-asin=''])")  # Fallback selector

        # If still no items, wait a bit longer and try once more
        if len(items) == 0:
            print("No items -- waiting 3s and retrying...")
            time.sleep(3.0)
            page.evaluate("window.scrollTo(0, 300)")
            time.sleep(1.0)
            items = page.query_selector_all("div[data-component-type='s-search-result'][data-asin]")

        print(f"Raw items found: {len(items)}\n")

        # Loop through first 25 results (more than enough to find the best match)
        for item in items[:25]:
            try:
                # Get the product's ASIN (Amazon's unique product ID)
                asin = item.get_attribute("data-asin")
                if not asin or asin.strip() == "":
                    continue   # Skip cards with no ASIN (usually ads or placeholders)

                # Skip sponsored/ad listings
                if item.query_selector('span:has-text("Sponsored")'):
                    continue

                # Extract the product title
                title = extract_title_amazon(item, debug=debug_titles)
                if not title or len(title) < 10:
                    print("  SKIP: no title")
                    continue

                # Calculate how well this title matches what the user wants
                score = calculate_match_score(title, canonical_product, store="Amazon")
                print(f"  {'OK' if score >= min_score else 'NO'} score={score:3d} | {title[:70]}")
                if score < min_score:
                    continue   # Score too low — skip this product

                # Scrape and validate the price
                price = scrape_price_amazon(item)
                print(f"  AMAZON PRICE: {price}")

                valid_price = validate_price(price, canonical_product)
                print(f"  VALID PRICE?: {valid_price}")

                if price == 0 or not valid_price:
                    print(f"  SKIP: invalid price {price} for '{title[:50]}'")
                    continue

                # Get original (before discount) price and calculate discount %
                orig = scrape_orig_price_amazon(item, price)
                discount, orig = calc_discount(price, orig)

                # Extract star rating
                rating = 0
                rel = item.query_selector(".a-icon-alt")
                if rel:
                    try: rating = float(rel.inner_text().split()[0])
                    except: pass

                # Extract number of reviews
                review_count = 0
                rev_el = item.query_selector("span[aria-label*='ratings'], .a-size-base.s-underline-text")
                if rev_el:
                    try:
                        m = re.search(r'\d+', rev_el.inner_text().replace(",", ""))
                        if m: review_count = int(m.group())
                    except: pass

                # Determine stock status
                stock_status = "In Stock"
                sel = item.query_selector(".a-color-price, span:has-text('Only'), span:has-text('left in stock')")
                if sel:
                    st = sel.inner_text().lower()
                    if "only" in st or "left" in st: stock_status = "Limited Stock"
                    elif "out of stock" in st: stock_status = "Out of Stock"

                # Extract delivery information
                delivery_days, delivery_label = 2, "2 day delivery"   # Defaults
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

                # Extract product image URL
                image = ""
                img_el = item.query_selector("img.s-image")
                if img_el: image = img_el.get_attribute("src") or ""

                # Extract product page link (must contain "/dp/" which is Amazon's product URL pattern)
                product_link = ""
                link_el = item.query_selector("a.a-link-normal[href*='/dp/']")
                if link_el:
                    href = link_el.get_attribute("href") or ""
                    product_link = href if href.startswith("http") else "https://www.amazon.in" + href

                # All checks passed — add this product to our results
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
                print(f"  ITEM ERROR: {e}")   # Log the error and continue to next item

        context.close()
        browser.close()

    print(f"\nFinal Amazon count: {len(products)}")
    return finalize_products(products, "Amazon", query)   # Sort, deduplicate, and return top result


# =========================================================
# FLIPKART SCRAPER
# =========================================================

def scrape_flipkart(query, canonical_product, intent_type="main_product", debug_titles=False):
    # Same structure as scrape_amazon, but adapted for Flipkart's HTML layout
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

        # Wait for Flipkart's product cards (they use "data-id" instead of "data-asin")
        try:
            page.wait_for_selector("div[data-id]", timeout=15000)
        except Exception:
            print("WARNING: Timed out waiting for Flipkart cards")

        # Scroll to trigger lazy loading, then scroll back to top
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(1.0)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(random.uniform(1.0, 2.0))

        page_title = page.title()
        print(f"Page title: {page_title}")

        # Abort if Flipkart is blocking us
        if any(w in page_title.lower() for w in ["robot", "captcha", "blocked", "sorry"]):
            browser.close()
            return make_empty_result("Flipkart", query, "Flipkart is temporarily blocking. Try again.")

        items = page.query_selector_all("div[data-id]")   # All product cards on Flipkart
        print(f"Raw items found: {len(items)}\n")

        for item in items[:25]:
            try:
                title = ""

                # Strategy 1: Look for an <a> tag with a "title" attribute (most reliable on Flipkart)
                for a_el in item.query_selector_all("a[title]"):
                    c = (a_el.get_attribute("title") or "").strip()
                    if len(c) >= 10:
                        title = c
                        break

                # Strategy 2: Try <img> alt text
                if not title:
                    for img_el in item.query_selector_all("img[alt]"):
                        c = (img_el.get_attribute("alt") or "").strip()
                        if len(c) >= 10:
                            title = c
                            break

                # Strategy 3: Try known Flipkart title CSS selectors
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

                # Score and filter the product — same as Amazon
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

                # Extract rating — Flipkart uses different CSS classes than Amazon
                rating = 0
                rat_el = item.query_selector("span.CjyrHS, div.MKiFS6")
                if rat_el:
                    try: rating = float(rat_el.inner_text().strip())
                    except: pass

                # Fallback: scan all short text elements for something that looks like a rating (e.g. "4.3")
                if rating == 0:
                    for el in item.query_selector_all("span, div"):
                        try:
                            txt = el.inner_text().strip()
                            if re.match(r'^[1-5]\.[0-9]$', txt):   # Matches "4.3", "3.7", etc.
                                rating = float(txt)
                                break
                        except: continue

                # Extract review count
                review_count = 0
                rev_el = item.query_selector("span.PvbNMB")
                if rev_el:
                    try:
                        nums = re.findall(r'\d+', rev_el.inner_text().replace(",", ""))
                        if nums: review_count = int(nums[0])
                    except: pass

                # Fallback: search the full card text for "X ratings" or "X reviews"
                if review_count == 0:
                    try:
                        m = re.search(r'([\d,]+)\s*(ratings|reviews)', item.inner_text(), re.I)
                        if m: review_count = int(m.group(1).replace(",", ""))
                    except: pass

                # Extract bank/coupon offer text
                offer = ""
                for oel in item.query_selector_all("div.hx1EGN"):
                    ot = oel.inner_text().strip()
                    if ot:
                        offer = ot
                        break

                # Extract product image (Flipkart images use "rukminim" CDN domain)
                image = ""
                for img_el in item.query_selector_all("img[src]"):
                    src = img_el.get_attribute("src") or ""
                    if "rukminim" in src:     # Flipkart's image CDN identifier
                        image = src
                        break
                if not image:
                    img_el = item.query_selector("img")
                    if img_el: image = img_el.get_attribute("src") or ""

                # Extract product link (Flipkart product URLs contain "/p/")
                product_link = ""
                for a_el in item.query_selector_all("a[href*='/p/']"):
                    href = a_el.get_attribute("href") or ""
                    if href:
                        product_link = href if href.startswith("http") else "https://www.flipkart.com" + href
                        break

                # Add to results
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