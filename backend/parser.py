import os       # Used to read environment variables (like the Gemini API key)
import json     # Used to parse Gemini's JSON response into a Python dictionary
import re       # Used for pattern matching with regular expressions (e.g. detecting greetings)
import ast
from google import genai               # Google's Gemini AI client library
from google.genai import types         # Gemini config types (used to set temperature, max tokens, etc.)
from dotenv import load_dotenv         # Reads the .env file so we can use secrets like API keys

load_dotenv()   # Load the .env file — after this, os.getenv("GEMINI_API_KEY") will work

# Create a Gemini client using our API key from the .env file
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Load the shopping prompt from prompt.txt — this is the big instruction we send to Gemini
# It tells Gemini how to parse product queries and what JSON format to respond in
with open("prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


# =========================================================
# GREETING DETECTOR
# =========================================================

# A regex pattern that matches common greeting phrases
# Examples: "hi", "hello", "good morning", "what's up", "namaste", etc.
GREETING_PATTERNS = re.compile(
    r"^\s*(hi|hello|hey|hii|helo|sup|yo|howdy|greetings|"
    r"good\s*(morning|afternoon|evening|night|day)|"
    r"what'?s\s*up|how\s*(are\s*you|r\s*u)|"
    r"namaste|namaskar|vanakkam|salaam)\s*[!.,?]*\s*$",
    re.IGNORECASE,   # Case-insensitive — "Hello" and "HELLO" both match
)


def is_greeting(text: str) -> bool:
    # Returns True if the user's message is just a greeting (nothing else)
    # We strip whitespace before checking to avoid false negatives like "  hi  "
    return bool(GREETING_PATTERNS.match(text.strip()))


# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(value):
    # Cleans up a text value — removes extra spaces, strips whitespace
    # Also handles non-string inputs safely by converting them to string first
    if not value:
        return ""                            # Return empty string if value is None / empty / 0
    value = str(value).strip()              # Convert to string and remove leading/trailing spaces
    value = re.sub(r"\s+", " ", value)     # Replace multiple spaces with a single space
    return value


# =========================================================
# FILTER VALUE CLEANUP
# =========================================================

# These are placeholder values Gemini might return when the user didn't specify a preference
# We treat these as "user didn't pick anything" and strip them from real filter results
NO_PREFERENCE_VALUES = {"any", "no preference", "none", ""}


def is_no_preference(value) -> bool:
    # Returns True if the value means "user didn't specify" — e.g. "any", "none", ""
    return str(value).strip().lower() in NO_PREFERENCE_VALUES


def clean_filters(filters: dict) -> dict:
    # Takes Gemini's raw filter output and removes junk/empty values
    # Returns only filters that have real, meaningful values

    if not isinstance(filters, dict):
        return {}   # If it's not a dict at all, return empty (safety check)

    cleaned = {}
    for key, value in filters.items():
        if isinstance(value, list):
            # For list-type filters (e.g. ["128GB", "256GB", "No Preference"])
            # Keep "No Preference" as-is (it's a valid UI chip the user can click)
            # Only drop completely blank/empty entries
            kept = [v for v in value if str(v).strip() != ""]
            if kept:
                cleaned[key] = kept   # Only add if there's at least one non-blank option
        elif value is None:
            continue   # Skip None values entirely
        elif not is_no_preference(value):
            # For single-value filters, only keep it if it's not a "no preference" placeholder
            cleaned[key] = value

    return cleaned


# =========================================================
# BUILD SEARCH QUERY (fallback only)
# Used ONLY when Gemini does not provide a search_query.
# =========================================================

def build_search_query(canonical_product: dict) -> str:
    # Manually constructs a search string from the parsed product fields
    # This is the backup — Gemini normally provides search_query directly
    parts = []   # Will hold each word/phrase that makes up the search query

    # Extract individual fields from the canonical product, defaulting to "" if missing
    brand = normalize_text(canonical_product.get("brand", ""))
    product_type = normalize_text(canonical_product.get("product_type", ""))
    model = normalize_text(canonical_product.get("model", ""))
    variant = normalize_text(canonical_product.get("variant", ""))
    gender = normalize_text(canonical_product.get("gender", ""))

    # Handle storage — it might be stored under two different key names
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

    # Lowercase versions for comparison (to avoid duplicate words in the query)
    model_lower = model.lower()
    brand_lower = brand.lower()
    product_type_lower = product_type.lower()

    # Add brand ONLY if it's not already part of the model or product type name
    # (prevents duplicates like "Apple Apple iPhone")
    if brand and brand_lower not in model_lower and brand_lower not in product_type_lower:
        parts.append(brand)

    # Add model if it's long enough to be meaningful (more than 3 chars)
    # Otherwise fall back to product type (e.g. "smartphone", "shoes")
    if model and len(model) > 3:
        parts.append(model)
    elif product_type:
        parts.append(product_type)

    # Add variant only if it's not already mentioned in the model name
    # (prevents "iPhone 15 Pro Pro Max" type duplications)
    if variant and variant.lower() not in model_lower:
        parts.append(variant)

    # Add gender only if it's not generic (skip "unisex" or "other")
    if gender and gender.lower() not in ["unisex", "other"]:
        parts.append(gender)

    # Add one size/capacity detail — use the first one that exists, in priority order
    if storage:
        parts.append(storage)          # e.g. "128GB"
    elif shoe_size:
        parts.append(shoe_size)        # e.g. "UK 9"
    elif weight:
        parts.append(weight)           # e.g. "1kg"
    elif pack_size:
        parts.append(pack_size)        # e.g. "Pack of 6"
    elif size:
        parts.append(size)             # e.g. "XL"
    elif flavor:
        parts.append(flavor)           # e.g. "Chocolate"
    elif quantity:
        parts.append(quantity)         # e.g. "500ml"

    # Remove duplicate words (case-insensitive) while preserving order
    seen = set()
    final_parts = []
    for part in parts:
        if part.lower() not in seen:
            seen.add(part.lower())
            final_parts.append(part)

    # Join all parts into a single search string and clean up spacing
    query = normalize_text(" ".join(final_parts))
    print(f"Built search query (fallback): '{query}'")
    return query


# =========================================================
# SANITIZE QUERY
# =========================================================

def collapse_size_range(query: str) -> str:
    # Converts size ranges like "200L - 300L" into a single midpoint value "250L"
    # This makes the search query cleaner for Amazon/Flipkart

    def _mid(m):
        # Called for each regex match — calculates the midpoint of the range
        try:
            lo, unit, hi = int(m.group(1)), m.group(2), int(m.group(3))
            return f"{(lo + hi) // 2}{unit}"   # e.g. (200 + 300) // 2 = 250 → "250L"
        except Exception:
            return m.group(0)   # If calculation fails, return the original text unchanged

    # Match patterns like "200L - 300L" or "200L–300L" and replace with midpoint
    return re.sub(r"(\d+)\s*([A-Za-z]+)\s*[-–]\s*(\d+)\s*[A-Za-z]*", _mid, query)


def sanitize_query(query: str) -> str:
    # Cleans the search query string so it works well on Amazon/Flipkart

    query = collapse_size_range(query)                        # Step 1: Collapse any size ranges into midpoints
    query = re.sub(r"/[A-Za-z0-9]{1,6}", "", query)          # Step 2: Remove short slash-suffixes like "/Pro" or "/256"
    query = re.sub(r"[^\w\s.]", " ", query)                  # Step 3: Remove special characters (keep letters, numbers, spaces, dots)
    query = re.sub(r"(?<!\d)\.(?!\d)", " ", query)           # Step 4: Remove dots that aren't decimal points (e.g. "Apple." → "Apple ")
    query = re.sub(r"\s+", " ", query).strip()               # Step 5: Collapse multiple spaces and trim
    return query


# =========================================================
# GEMINI CHAT - for greetings and general conversation
# =========================================================

# A separate, simpler system prompt just for casual chat (not product parsing)
# Keeps responses short, warm, and ends with an invitation to shop
CHAT_SYSTEM_PROMPT = """You are a friendly AI shopping assistant for an Indian e-commerce price comparison tool.
You help users compare prices on Amazon.in and Flipkart and find the best deals.
Respond naturally like a real helpful person. Never use scripted phrases. Vary your language every time.
Keep responses to 1-2 sentences max. Do not return JSON. Just reply naturally.
Always end by inviting the user to tell you what they want to shop for."""


def get_chat_reply(user_text: str) -> str:
    # Sends a casual/greeting message to Gemini and gets back a friendly reply
    # This is separate from the main shopping parser so greetings feel natural
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",     # Lightweight model — fast and cheap for simple replies
            config=types.GenerateContentConfig(
                system_instruction=CHAT_SYSTEM_PROMPT,   # Use the chat-only prompt
                temperature=0.9,                         # Higher temperature = more varied/creative replies
                max_output_tokens=100,                   # Keep the reply short
            ),
            contents=user_text,   # The user's greeting message
        )
        return response.text.strip()   # Return the cleaned reply text

    except Exception as e:
        # If the first attempt fails, try again with a simplified prompt (no system instruction)
        print(f"CHAT REPLY ERROR: {e}")
        try:
            r = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                config=types.GenerateContentConfig(
                    temperature=0.9,
                    max_output_tokens=80,
                ),
                # Give Gemini just enough context to respond warmly
                contents=f"The user said: '{user_text}'. Reply warmly in one sentence and ask what they want to shop for.",
            )
            return r.text.strip()
        except Exception:
            return ""   # If both attempts fail, return empty string (caller handles it)


# =========================================================
# MAIN PARSER
# =========================================================

def get_intent(full_query: str) -> dict:
    # The core function — takes the full conversation context and returns a structured intent result
    # Called by main.py every time the user sends a message

    # ── Step 1: Extract the latest user message from the context string ───
    last_line = full_query.strip().split("\n")[-1]   # Get the last line of the context
    if last_line.startswith("Latest User Input:"):
        # Remove the label prefix to get just the raw user message
        last_line = last_line.replace("Latest User Input:", "").strip()

    # ── Step 2: If it's a greeting, skip the shopping prompt entirely ──────
    if is_greeting(last_line):
        print(f"GREETING DETECTED: '{last_line}'")
        reply = get_chat_reply(last_line)   # Get a friendly chat reply instead
        return {
            "status": "chat",
            "message": reply,
        }

    # ── Step 3: Send the full context to Gemini with the shopping prompt ───
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,   # The big shopping parser prompt from prompt.txt
                temperature=0.2,                    # Low temperature = consistent, predictable JSON output
                max_output_tokens=500,              # Allow enough tokens for a full JSON response
            ),
            contents=f"USER QUERY:\n{full_query}",   # Send the full conversation context
        )

        # Clean up Gemini's response — remove markdown code fences if present
        clean = response.text.strip()
        clean = clean.replace("```json", "").replace("```", "").strip()

        print("RAW GEMINI:", clean)   # Log raw output for debugging

        # Try to parse Gemini's response as JSON
        try:
            data = json.loads(clean)
            response_type = data.get("type", "")   # What kind of response did Gemini return?
        except json.JSONDecodeError:
            # If it's not valid JSON, treat it as a plain text chat reply
            return {
                "status": "chat",
                "message": clean,
            }

        # ── CASE: Gemini says the product is ready to search ──────────────
        if response_type == "ready":
            canonical_product = data.get("canonical_product", {})   # Structured product details

            # Check if Gemini added a follow-up clarification or preference question
            # even though it returned "ready" — this happens when search_query is missing
            inline_clarification = data.get("clarification", "")
            pref_question = data.get("preference_collection", "")
            follow_up = inline_clarification or pref_question

            # If there's a follow-up question AND no search query yet, treat it as clarification
            if follow_up and not data.get("search_query"):
                print(f"PREFERENCE/CLARIFICATION STAGE — holding search: {follow_up}")
                return {
                    "status": "clarification",
                    "search_mode": "assistant_mode",
                    "question": data.get("question", follow_up),
                    "missing_attributes": data.get("missing_required_attributes", []),
                    "filters": clean_filters(data.get("filters", {})),
                }

            # Handle compound model names like "iPhone 15 or iPhone 15 Pro"
            # We only want the first option — "iPhone 15"
            raw_model = canonical_product.get("model", "")
            if " or " in raw_model.lower():
                first_model = raw_model.split(" or ")[0].strip()
                canonical_product["model"] = first_model
                print(f"MODEL COMPOUND DETECTED: '{raw_model}' → using '{first_model}'")

            # Normalize all canonical product fields and remove "no preference" values
            normalized = {
                k: normalize_text(v)
                for k, v in canonical_product.items()
                if v is not None and not is_no_preference(v)   # Skip None and placeholder values
            }

            # Get the search query Gemini suggested (e.g. "Apple iPhone 15 128GB")
            gemini_query = normalize_text(data.get("search_query", ""))

            # If Gemini returned a compound query like "iPhone 15 or iPhone 15 Pro", discard it
            # and fall back to building the query ourselves
            if gemini_query and " or " in gemini_query.lower():
                gemini_query = ""
                print("Gemini search_query had compound OR — falling back to builder")

            # Use Gemini's query if it's clean, otherwise build one from the product fields
            if gemini_query:
                search_query = sanitize_query(gemini_query)
                print(f"Using Gemini search_query: '{search_query}'")
            else:
                search_query = sanitize_query(build_search_query(normalized))

            # If we still couldn't build a search query, return an error
            if not search_query:
                return {"status": "error", "message": "Failed to build search query."}

            # Validate the product category — only accept known categories
            category = normalize_text(data.get("category", "general")).lower()
            valid_categories = {"electronics", "fashion", "beauty", "grocery", "general"}
            if category not in valid_categories:
                category = "general"   # Default to "general" if Gemini returned something unexpected

            print(f"CATEGORY: {category}")

            # Clean and normalize the filter values
            filters = clean_filters(data.get("filters", {}))
            normalized_filters = {}

            for key, value in filters.items():

                # If Gemini returned the value as a string like "{'options': ['Gala', ...]}", parse it
                if isinstance(value, str):
                    try:
                        value = ast.literal_eval(value)
                    except Exception:
                        pass

                # If Gemini returned {"options": ["Gala", "Fuji", ...]}, unwrap the list
                if isinstance(value, dict) and "options" in value:
                    value = [str(v) for v in value["options"] if str(v).strip()]

                # Normalize to a list regardless of shape
                if isinstance(value, list):
                    normalized_filters[key] = value
                elif value is None:
                    normalized_filters[key] = []
                else:
                    normalized_filters[key] = [str(value)]

            # Return the full ready result — main.py will use this to trigger scraping
            return {
                "status": "ready",
                "search_mode": data.get("search_mode", "exact_search"),
                "data": {
                    "canonical_product": normalized,    # Cleaned product details
                    "search_query": search_query,       # The string to search on Amazon/Flipkart
                    "category": category,               # Product category
                    "filters": normalized_filters,      # Filter options for the sidebar
                },
            }

        # ── CASE: Gemini wants to offer filter options to narrow down ──────
        elif response_type == "refine":
            # Validate category same as above
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

            # Clean and normalize filters same as above
            filters = clean_filters(data.get("filters", {}))
            normalized_filters = {}

            for key, value in filters.items():

                # If Gemini returned the value as a string like "{'options': ['Gala', ...]}", parse it
                if isinstance(value, str):
                    try:
                        value = ast.literal_eval(value)
                    except Exception:
                        pass

                # If Gemini returned {"options": ["Gala", "Fuji", ...]}, unwrap the list
                if isinstance(value, dict) and "options" in value:
                    value = [str(v) for v in value["options"] if str(v).strip()]

                # Normalize to a list regardless of shape
                if isinstance(value, list):
                    normalized_filters[key] = value
                elif value is None:
                    normalized_filters[key] = []
                else:
                    normalized_filters[key] = [str(value)]

            # Return refine response — frontend will show filter chips for the user to pick
            return {
                "status": "refine",
                "search_mode": data.get("search_mode", "assistant_mode"),
                "message": data.get("message", ""),     # Message to show above the filters
                "filters": normalized_filters,
            }

        # ── CASE: Gemini needs to ask the user a specific question ─────────
        elif response_type == "clarification":
            return {
                "status": "clarification",
                "search_mode": data.get("search_mode", "assistant_mode"),
                "question": data.get("question", "Could you provide more details?"),   # The question to ask
                "missing_attributes": data.get("missing_required_attributes", []),     # What info is still needed
                "options": data.get("options", []),    # Optional answer buttons to show the user
            }

        # ── CASE: Gemini returned a JSON chat/text response ───────────────
        # This handles cases where Gemini replied in JSON but with a plain message field
        elif "message" in data or "response" in data:
            return {
                "status": "chat",
                "message": data.get("message") or data.get("response", ""),
            }

        # ── FALLBACK: Gemini returned something we don't recognize ─────────
        # Treat it as out-of-scope and politely redirect to shopping
        return {
            "status": "reject",
            "reason": "I can only help with shopping queries. Try asking me to find a product!",
        }

    except Exception as e:
        # Catch any unexpected crash (network error, API failure, etc.)
        print("PARSER ERROR:", e)
        return {"status": "error", "message": str(e)}