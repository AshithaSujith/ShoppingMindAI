import traceback
import os
import json
import re
import ast

from dotenv import load_dotenv
from app.services.providers.provider_factory import get_provider

load_dotenv()

provider = get_provider()

with open("prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


# =========================================================
# GREETING DETECTOR
# =========================================================

GREETING_PATTERNS = re.compile(
    r"^\s*(hi|hello|hey|hii|helo|sup|yo|howdy|greetings|"
    r"good\s*(morning|afternoon|evening|night|day)|"
    r"what'?s\s*up|how\s*(are\s*you|r\s*u)|"
    r"namaste|namaskar|vanakkam|salaam)\s*[!.,?]*\s*$",
    re.IGNORECASE,
)


def is_greeting(text: str) -> bool:
    return bool(GREETING_PATTERNS.match(text.strip()))


# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(value):
    if not value:
        return ""
    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)
    return value


# =========================================================
# FILTER VALUE CLEANUP
# =========================================================

# Placeholder values meaning "user didn't specify a preference"
NO_PREFERENCE_VALUES = {"any", "no preference", "none", ""}


def is_no_preference(value) -> bool:
    return str(value).strip().lower() in NO_PREFERENCE_VALUES


def clean_filters(filters: dict) -> dict:
    if not isinstance(filters, dict):
        return {}

    cleaned = {}
    for key, value in filters.items():
        if isinstance(value, list):
            # Keep "No Preference" as a valid chip, only drop blank entries
            kept = [v for v in value if str(v).strip() != ""]
            if kept:
                cleaned[key] = kept
        elif value is None:
            continue
        elif not is_no_preference(value):
            cleaned[key] = value

    return cleaned


# =========================================================
# BUILD SEARCH QUERY (fallback only — used when provider gives no search_query)
# =========================================================

def build_search_query(canonical_product: dict) -> str:
    parts = []

    brand = normalize_text(canonical_product.get("brand", ""))
    product_type = normalize_text(canonical_product.get("product_type", ""))
    model = normalize_text(canonical_product.get("model", ""))
    variant = normalize_text(canonical_product.get("variant", ""))
    gender = normalize_text(canonical_product.get("gender", ""))

    storage = normalize_text(
        canonical_product.get("storage")
        or canonical_product.get("storage_capacity")
        or ""
    )
    size = normalize_text(canonical_product.get("size", ""))
    shoe_size = normalize_text(canonical_product.get("shoe_size", ""))
    pack_size = normalize_text(canonical_product.get("pack_size", ""))
    flavor = normalize_text(canonical_product.get("flavor", ""))
    weight = normalize_text(canonical_product.get("weight", ""))
    quantity = normalize_text(canonical_product.get("quantity", ""))

    model_lower = model.lower()
    brand_lower = brand.lower()
    product_type_lower = product_type.lower()

    # Skip brand if it's already part of model/product_type (avoids "Apple Apple iPhone")
    if brand and brand_lower not in model_lower and brand_lower not in product_type_lower:
        parts.append(brand)

    if model and len(model) > 3:
        parts.append(model)
    elif product_type:
        parts.append(product_type)

    if variant and variant.lower() not in model_lower:
        parts.append(variant)

    if gender and gender.lower() not in ["unisex", "other"]:
        parts.append(gender)

    # Only one size/capacity field, first match wins by priority
    if storage:
        parts.append(storage)
    elif shoe_size:
        parts.append(shoe_size)
    elif weight:
        parts.append(weight)
    elif pack_size:
        parts.append(pack_size)
    elif size:
        parts.append(size)
    elif flavor:
        parts.append(flavor)
    elif quantity:
        parts.append(quantity)

    seen = set()
    final_parts = []
    for part in parts:
        if part.lower() not in seen:
            seen.add(part.lower())
            final_parts.append(part)

    query = normalize_text(" ".join(final_parts))
    print(f"Built search query (fallback): '{query}'")
    return query


# =========================================================
# SANITIZE QUERY
# =========================================================

def collapse_size_range(query: str) -> str:
    # "200L - 300L" → "250L" (midpoint), cleaner for Amazon/Flipkart search
    def _mid(m):
        try:
            lo, unit, hi = int(m.group(1)), m.group(2), int(m.group(3))
            return f"{(lo + hi) // 2}{unit}"
        except Exception:
            return m.group(0)

    return re.sub(r"(\d+)\s*([A-Za-z]+)\s*[-–]\s*(\d+)\s*[A-Za-z]*", _mid, query)


def sanitize_query(query: str) -> str:
    query = collapse_size_range(query)
    query = re.sub(r"/[A-Za-z0-9]{1,6}", "", query)          # strip suffixes like "/Pro"
    query = re.sub(r"[^\w\s.]", " ", query)
    query = re.sub(r"(?<!\d)\.(?!\d)", " ", query)            # keep only decimal-point dots
    query = re.sub(r"\s+", " ", query).strip()
    return query


# =========================================================
# AI CHAT - for greetings and general conversation
# =========================================================

CHAT_SYSTEM_PROMPT = """You are a friendly AI shopping assistant for an Indian e-commerce price comparison tool.
You help users compare prices on Amazon.in and Flipkart and find the best deals.
Respond naturally like a real helpful person. Never use scripted phrases. Vary your language every time.
Keep responses to 1-2 sentences max. Do not return JSON. Just reply naturally.
Always end by inviting the user to tell you what they want to shop for."""


def get_chat_reply(user_text: str) -> str:
    try:
        response = provider.generate(
            system_prompt=CHAT_SYSTEM_PROMPT,
            user_input=user_text,
            temperature=0.9,
            max_tokens=100,
        )
        return response.strip()

    except Exception as e:
        print(f"CHAT REPLY ERROR: {e}")
        return ""


# =========================================================
# MAIN PARSER
# =========================================================

def get_intent(full_query: str) -> dict:
    last_line = full_query.strip().split("\n")[-1]
    if last_line.startswith("Latest User Input:"):
        last_line = last_line.replace("Latest User Input:", "").strip()

    if is_greeting(last_line):
        print(f"GREETING DETECTED: '{last_line}'")
        reply = get_chat_reply(last_line)
        return {
            "status": "chat",
            "message": reply,
        }

    try:
        response = provider.generate(
            system_prompt=SYSTEM_PROMPT,
            user_input=f"USER QUERY:\n{full_query}",
            temperature=0.2,
            max_tokens=500,
        )

        clean = response.strip()
        clean = clean.replace("```json", "").replace("```", "").strip()

        print("RAW PROVIDER RESPONSE:", clean)

        try:
            data = json.loads(clean)
            response_type = data.get("type", "")
        except json.JSONDecodeError:
            return {
                "status": "chat",
                "message": clean,
            }

        if response_type == "ready":
            canonical_product = data.get("canonical_product", {})

            # Provider can return "ready" but still have a pending question — hold the search in that case
            inline_clarification = data.get("clarification", "")
            pref_question = data.get("preference_collection", "")
            follow_up = inline_clarification or pref_question

            if follow_up and not data.get("search_query"):
                print(f"PREFERENCE/CLARIFICATION STAGE — holding search: {follow_up}")
                return {
                    "status": "clarification",
                    "search_mode": "assistant_mode",
                    "question": data.get("question", follow_up),
                    "missing_attributes": data.get("missing_required_attributes", []),
                    "filters": clean_filters(data.get("filters", {})),
                }

            # Compound model names like "iPhone 15 or iPhone 15 Pro" — take the first option only
            raw_model = canonical_product.get("model", "")
            if " or " in raw_model.lower():
                first_model = raw_model.split(" or ")[0].strip()
                canonical_product["model"] = first_model
                print(f"MODEL COMPOUND DETECTED: '{raw_model}' → using '{first_model}'")

            normalized = {
                k: normalize_text(v)
                for k, v in canonical_product.items()
                if v is not None and not is_no_preference(v)
            }

            provider_query = normalize_text(data.get("search_query", ""))

            # Discard compound OR queries and fall back to building our own
            if provider_query and " or " in provider_query.lower():
                provider_query = ""
                print("Provider search_query had compound OR — falling back to builder")

            if provider_query:
                search_query = sanitize_query(provider_query)
                print(f"Using provider search_query: '{search_query}'")
            else:
                search_query = sanitize_query(build_search_query(normalized))

            if not search_query:
                return {"status": "error", "message": "Failed to build search query."}

            category = normalize_text(data.get("category", "general")).lower()
            valid_categories = {"electronics", "fashion", "beauty", "grocery", "general"}
            if category not in valid_categories:
                category = "general"

            print(f"CATEGORY: {category}")

            filters = clean_filters(data.get("filters", {}))
            normalized_filters = {}

            for key, value in filters.items():
                # Provider sometimes returns filter values as a stringified dict/list — recover it
                if isinstance(value, str):
                    try:
                        value = ast.literal_eval(value)
                    except Exception:
                        pass

                if isinstance(value, dict) and "options" in value:
                    value = [str(v) for v in value["options"] if str(v).strip()]

                if isinstance(value, list):
                    normalized_filters[key] = value
                elif value is None:
                    normalized_filters[key] = []
                else:
                    normalized_filters[key] = [str(value)]

            return {
                "status": "ready",
                "search_mode": data.get("search_mode", "exact_search"),
                "data": {
                    "canonical_product": normalized,
                    "search_query": search_query,
                    "category": category,
                    "filters": normalized_filters,
                },
            }

        elif response_type == "refine":
            category = normalize_text(
                data.get("category", "general")
            ).lower()

            valid_categories = {
                "electronics",
                "fashion",
                "beauty",
                "grocery",
                "general",
            }

            if category not in valid_categories:
                category = "general"

            filters = clean_filters(data.get("filters", {}))
            normalized_filters = {}

            for key, value in filters.items():
                if isinstance(value, str):
                    try:
                        value = ast.literal_eval(value)
                    except Exception:
                        pass

                if isinstance(value, dict) and "options" in value:
                    value = [str(v) for v in value["options"] if str(v).strip()]

                if isinstance(value, list):
                    normalized_filters[key] = value
                elif value is None:
                    normalized_filters[key] = []
                else:
                    normalized_filters[key] = [str(value)]

            return {
                "status": "refine",
                "search_mode": data.get("search_mode", "assistant_mode"),
                "message": data.get("message", ""),
                "filters": normalized_filters,
            }

        elif response_type == "clarification":
            return {
                "status": "clarification",
                "search_mode": data.get("search_mode", "assistant_mode"),
                "question": data.get("question", "Could you provide more details?"),
                "missing_attributes": data.get("missing_required_attributes", []),
                "options": data.get("options", []),
            }

        elif "message" in data or "response" in data:
            return {
                "status": "chat",
                "message": data.get("message") or data.get("response", ""),
            }

        return {
            "status": "reject",
            "reason": "I can only help with shopping queries. Try asking me to find a product!",
        }

    except Exception as e:
        print("PARSER ERROR:", e)
        traceback.print_exc()
        return {"status": "error", "message": str(e)}