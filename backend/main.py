import sys          # Used to check what operating system the code is running on
import asyncio      # Lets us run multiple tasks at the same time (like scraping Amazon + Flipkart together)
import json         # Used to convert Python dictionaries to JSON strings and back

# Windows has a bug with async + threads — this fixes it if we're on Windows
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, BackgroundTasks                       # FastAPI is the web framework — it handles incoming HTTP requests
from fastapi.middleware.cors import CORSMiddleware   # CORS lets the frontend (Next.js) talk to this backend without being blocked
from pydantic import BaseModel                       # BaseModel lets us define what shape the incoming request data should have
from typing import List, Optional                    # Type hints — List = a list, Optional = might be None

# Our own modules
from parser import get_intent          # Sends the user's message to Gemini and gets back what they want to buy
from scraper import scrape_amazon, scrape_flipkart, scrape_with_fallback  # Functions that scrape product listings
from chatbot import ChatBot            # Manages conversation history per session (stores messages)

app = FastAPI()        # Create the FastAPI app — this is the main API object
chatbot = ChatBot()    # Create a single chatbot instance that all sessions share

# Allow the frontend to make requests to this backend
# allow_origins=["*"] means ANY website can call this API (fine for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # Accept requests from any origin
    allow_methods=["*"],    # Allow any HTTP method (GET, POST, etc.)
    allow_headers=["*"],    # Allow any request headers
)


# ─── Request Body Models ────────────────────────────────────────────────────
# These define what JSON shape the API expects when someone calls each endpoint

class SearchRequest(BaseModel):
    query: str                          # The user's typed message (e.g. "I want to buy iPhone 15")
    session_id: str = "user1"           # Identifies which user/session this message belongs to (default: "user1")
    history: Optional[List[dict]] = None  # Optional: past messages (not currently used directly here)


class ClearRequest(BaseModel):
    session_id: str   # Which session to clear/reset


class ScrapeRequest(BaseModel):
    search_query: str        # The cleaned search term to look up (e.g. "Apple iPhone 15 128GB")
    canonical_product: dict  # The full structured product info parsed by Gemini


# ─── Helper: Normalize Product ──────────────────────────────────────────────
def normalize_product(p: dict) -> dict:
    # Takes a raw product dictionary and ensures every field exists with a safe default
    # This prevents crashes if a scraper returns a product missing some fields
    return {
        "product_name": p.get("product_name", ""),          # Full product title
        "productname": p.get("product_name", ""),            # Duplicate with camelCase key (for frontend compatibility)
        "price_inr": p.get("price_inr", 0),                  # Current selling price in rupees
        "priceinr": p.get("price_inr", 0),                   # Same price, alternate key name
        "original_price": p.get("original_price", 0),        # Price before discount (MRP)
        "originalprice": p.get("original_price", 0),         # Same, alternate key
        "discount_percent": p.get("discount_percent", 0),    # How much % is discounted
        "discountpercent": p.get("discount_percent", 0),     # Same, alternate key
        "store": p.get("store", ""),                          # "Amazon" or "Flipkart"
        "delivery_label": p.get("delivery_label", ""),        # e.g. "Free delivery", "Delivery by tomorrow"
        "deliverylabel": p.get("delivery_label", ""),         # Same, alternate key
        "rating": p.get("rating", 0),                         # Star rating out of 5
        "review_count": p.get("review_count", 0),             # Number of customer reviews
        "reviewcount": p.get("review_count", 0),              # Same, alternate key
        "image": p.get("image", ""),                          # Product image URL
        "product_link": p.get("product_link", ""),            # Link to the product page
        "productlink": p.get("product_link", ""),             # Same, alternate key
        "is_reliable": p.get("is_reliable", False),           # True if scraper thinks this is a genuine match
        "isreliable": p.get("is_reliable", False),            # Same, alternate key
        "is_best_price": p.get("is_best_price", False),       # True if this is the cheapest among all results
        "isbestprice": p.get("is_best_price", False),         # Same, alternate key
        "match_score": p.get("match_score", 0),               # How closely this product matches the user's query
        "offer": p.get("offer", ""),                          # Any bank/coupon offers mentioned
        "stock_status": p.get("stock_status", ""),            # e.g. "In Stock", "Out of Stock"
    }


# ─── Helper: Is Query Too Vague? ────────────────────────────────────────────
def should_ask_filters(query: str) -> bool:
    # Returns True if the user's query is too short/vague to search meaningfully
    # Example: "I want to buy" → only filler words → ask for more details

    words = query.lower().split()   # Split the query into individual words, all lowercase

    # Words that don't carry any product meaning
    useless_words = {
        "i", "want", "to", "buy", "need", "show", "me",
        "find", "a", "an", "the", "some", "please", "hey"
    }

    # Keep only words that actually mean something (not in the useless list)
    meaningful = [w for w in words if w not in useless_words]

    # If there are fewer than 2 meaningful words, the query is too vague
    return len(meaningful) < 2


# ─── Route: Health Check ────────────────────────────────────────────────────
@app.get("/")
async def root():
    # Simple endpoint to confirm the API is running
    # Visit http://localhost:8000/ in a browser to test
    return {"message": "ShopMind AI API Running"}


# ─── Route: Clear Session ───────────────────────────────────────────────────
@app.post("/session/clear")
async def clear_session(payload: ClearRequest):
    print("NEW CHAT:", payload.session_id)

    return {
        "status": "success",
        "message": "New session started"
    }

# ─── Route: Get Session History ─────────────────────────────────────────────
@app.get("/session/history/{session_id}")
async def get_history(session_id: str):
    # Returns the full conversation history for a given session
    # Useful when the frontend needs to reload a past session
    history = chatbot.get_history(session_id)
    return {"status": "success", "session_id": session_id, "messages": history}


# ─── Route: Main Search ─────────────────────────────────────────────────────
@app.post("/search")
async def search(
    payload: SearchRequest,
    background_tasks: BackgroundTasks,
    ):
    try:
        query = payload.query.strip()       # Remove any leading/trailing whitespace from the user's message
        session_id = payload.session_id     # Which user is sending this message

        # Print a separator and the user's message in the terminal for debugging
        print(f"\n{'=' * 50}")
        print(f"USER [{session_id}]: {query}")

        # If the user sent an empty message, return an error immediately
        if not query:
            return {"status": "error", "message": "Empty query received."}

        # Load this session's past messages from storage
        history = chatbot.get_history(session_id)

        # Format the history as "USER: ..." / "ASSISTANT: ..." lines
        is_first_message = len(history) == 0

        # ── FIX: build full_context ONCE, inside the if/else, instead of
        # building it twice (a leftover assignment was being overwritten by
        # a second block that referenced `context_lines` even when it was
        # never created — that caused a NameError crash on every first message) ──
        if is_first_message:
            print("FIRST MESSAGE -> Skip DB History")

            full_context = f"""Latest User Input:
{query}""".strip()

        else:
            print("FOLLOW-UP MESSAGE -> Load DB History")

            context_lines = [
                f"{m['role'].upper()}: {m['content']}"
                for m in history
            ]

            full_context = f"""Previous Conversation:
{chr(10).join(context_lines)}

Latest User Input:
{query}""".strip()

        # Save the user's new message to the session history
        # chatbot.add_message(session_id, "user", query)

        # Send the full context to Gemini and get back the parsed intent
        result = get_intent(full_context)

        # What search mode Gemini decided (e.g. "exact_search" or "assistant_mode")
        search_mode = result.get("search_mode", "exact_search")

        print(f"INTENT RESULT: {result.get('status')} | MODE: {search_mode}")

        # ── CASE 1: Gemini understood the product and is ready to search ──
        if result.get("status") == "ready":
            data = result.get("data", {})                                  # All parsed data from Gemini
            canonical_product = data.get("canonical_product", {})          # Structured product details
            search_query = data.get("search_query", "")                    # The search string for Amazon/Flipkart
            intent_type = canonical_product.get("intent_type", "main_product")  # e.g. "main_product", "accessory"

            # If the query is too vague (e.g. just "buy something"), ask the user for more info
            if should_ask_filters(query):
                message = "Please give a few more details so I can find the right product."
                background_tasks.add_task(
                    chatbot.save_conversation,
                    session_id,
                    query,
                    message,
                )

                # Log the available filters for debugging
                print("\n========== FILTERS ==========")
                print(result.get("filters", {}))
                print("=============================\n")

                # Tell the frontend to show filter chips so the user can narrow down
                return {
                    "status": "success",
                    "data": {
                        "type": "filters",               # Frontend should render filter selection UI
                        "message": message,
                        "filters": data.get("filters", {}),
                        "category": canonical_product.get("category", "general"),
                    },
                }

            print(f"SEARCH QUERY: {search_query}")

            # If Gemini didn't produce a search query for some reason, return an error
            if not search_query:
                return {"status": "error", "message": "Failed to generate search query."}

            # ── Check if we already showed the "extracted details" card this session ──
            # We store a CONFIRMED_STATE: marker in history when we first show it
            already_shown = any(
                m["role"] == "assistant" and m["content"].startswith("CONFIRMED_STATE:")
                for m in history
            )

            if not already_shown:
                # FIRST TIME: Save the parsed state into history and return it to the frontend
                # The frontend will display the "CanonicalProductDetails" card,
                # then automatically call /scrape to get actual products
                state_snapshot = {
                    "confirmed_canonical_product": canonical_product,   # What Gemini understood the user wants
                    "search_query": search_query,                       # What to search on Amazon/Flipkart
                    "filters_offered_this_turn": list(data.get("filters", {}).keys()),  # Which filters were available
                }

                # Store the state in history with a special prefix so we can detect it later
                background_tasks.add_task(
                    chatbot.save_conversation,
                    session_id,
                    query,
                    "CONFIRMED_STATE:" + json.dumps(state_snapshot),
                )

                # Return parsed_query so frontend knows to show the details card before scraping
                return {
                    "status": "success",
                    "data": {
                        "type": "parsed_query",           # Frontend will show the extracted product summary card
                        "search_query": search_query,
                        "canonical_product": canonical_product,
                        "filters": data.get("filters", {}),
                        "intent_type": intent_type,
                    },
                }

            # SECOND TIME: The details card was already shown in a previous turn
            # Now just tell the frontend we're ready for it to trigger /scrape
            return {
                "status": "success",
                "data": {
                    "type": "ready_to_scrape",           # Frontend should directly call /scrape now
                    "message": "Ready to search products.",
                    "search_query": search_query,
                    "canonical_product": canonical_product,
                    "intent_type": intent_type,
                },
            }

        # ── CASE 2: Gemini needs more info before it can search ──
        elif result.get("status") == "clarification":
            question = result.get("question", "Could you give me more details?")  # The question Gemini wants to ask
            background_tasks.add_task(
                chatbot.save_conversation,
                session_id,
                query,
                question,
            )

            # Tell the frontend to show the clarification question + optional answer buttons
            return {
                "status": "success",
                "data": {
                    "type": "clarify",                             # Frontend shows a question with optional option chips
                    "message": question,
                    "options": result.get("options", []),          # Suggested answer options (e.g. ["256GB", "512GB"])
                    "missing_attributes": result.get("missing_attributes", []),  # What info is still needed
                    "filters": result.get("filters", {}),          # Any filters Gemini already knows
                },
            }

        # ── CASE 3: Gemini wants to offer filter choices to narrow down ──
        elif result.get("status") == "refine":
            message = result.get("message", "Please select your preferences.")
            background_tasks.add_task(
                chatbot.save_conversation,
                session_id,
                query,
                message,
            )

            # Tell the frontend to show filter chips for the user to pick from
            return {
                "status": "success",
                "data": {
                    "type": "filters",
                    "message": message,
                    "filters": result.get("filters", {}),
                    "category": result.get("category", "general"),
                },
            }

        # ── CASE 4: User said something conversational (not a product search) ──
        elif result.get("status") == "chat":
            message = result.get("message", "How can I help you shop today?")
            background_tasks.add_task(
                chatbot.save_conversation,
                session_id,
                query,
                message,
            )

            # Just return Gemini's text reply — no product cards or filters
            return {
                "status": "success",
                "data": {
                    "type": "text",       # Frontend shows it as a plain chat bubble
                    "message": message,
                },
            }

        # ── CASE 5: User asked something outside ShopBot's scope ──
        elif result.get("status") == "reject":
            # Use Gemini's custom reason, or fall back to a default message
            message = (
                result.get("reason")
                or "I'm a shopping assistant — I can help you find and compare product prices on Amazon and Flipkart. What would you like to buy?"
            )
            background_tasks.add_task(
                chatbot.save_conversation,
                session_id,
                query,
                message,
            )

            return {
                "status": "success",
                "data": {
                    "type": "text",
                    "message": message,
                },
            }

        # ── FALLBACK: Something unexpected happened ──
        return {
            "status": "error",
            "message": result.get("message", "Something went wrong. Please try again."),
        }

    except Exception as e:
        # Catch any unhandled crash and return it as an error (so the app doesn't die)
        print(f"MAIN API ERROR: {e}")
        return {"status": "error", "message": str(e)}


# ─── Route: Scrape Products ─────────────────────────────────────────────────
@app.post("/scrape")
async def scrape(payload: ScrapeRequest):
    try:
        search_query = payload.search_query          # The search term to look up (e.g. "Apple iPhone 15 128GB")
        canonical_product = payload.canonical_product  # Full structured product info from Gemini

        # Whether the user wants a main product, accessory, spare part, etc.
        intent_type = canonical_product.get(
            "intent_type",
            "main_product"    # Default to main product if not specified
        )

        print(f"\n{'=' * 60}")
        print(f"SCRAPING: {search_query}")

        # Run Amazon and Flipkart scrapers AT THE SAME TIME (parallel) to save time
        # asyncio.to_thread() runs a blocking (non-async) function in a background thread
        amazon_task = asyncio.to_thread(
            scrape_with_fallback,     # Wrapper that retries scraping if the first attempt fails
            scrape_amazon,            # The actual Amazon scraper function
            search_query,
            canonical_product,
            intent_type,
        )

        flipkart_task = asyncio.to_thread(
            scrape_with_fallback,     # Same fallback wrapper for Flipkart
            scrape_flipkart,          # The actual Flipkart scraper function
            search_query,
            canonical_product,
            intent_type,
        )

        # Wait for BOTH scrapers to finish (they run in parallel)
        amazon_results, flipkart_results = await asyncio.gather(
            amazon_task,
            flipkart_task,
        )

        # Filter Amazon results: only keep products that are reliable matches AND have a price
        amazon_best = [
            p
            for p in amazon_results
            if p.get("is_reliable")         # Scraper flagged this as a genuine match
            and p.get("price_inr", 0) > 0   # Has a valid price (not 0 or missing)
        ]

        # Same filter for Flipkart
        flipkart_best = [
            p
            for p in flipkart_results
            if p.get("is_reliable")
            and p.get("price_inr", 0) > 0
        ]

        all_products = []   # Will hold the final product list to return

        # Take only the TOP 1 result from each store (the best match per store)
        all_products.extend(amazon_best[:1])    # Add best Amazon result
        all_products.extend(flipkart_best[:1])  # Add best Flipkart result

        # ── Mark the cheapest product with is_best_price = True ──
        if all_products:
            # Only consider products that actually have a price
            priced = [
                p
                for p in all_products
                if p["price_inr"] > 0
            ]

            if priced:
                # Reset all products' best price flag to False first
                for p in all_products:
                    p["is_best_price"] = False

                # Find the product with the lowest price and set its flag to True
                min(
                    priced,
                    key=lambda x: x["price_inr"]   # Compare by price
                )["is_best_price"] = True

        # ── Fallback: if no reliable products found, return the first raw result ──
        # This prevents returning empty results when scrapers found something but scored it low
        if not all_products:
            all_products = amazon_results[:1] or flipkart_results[:1]

        # Return the final product list to the frontend
        return {
            "status": "success",
            "data": {
                "type": "products",                    # Frontend should render product cards
                "products": all_products,
                "canonical_product": canonical_product,  # Pass this along so frontend can display parsed details
                "search_query": search_query,
            },
        }

    except Exception as e:
        # Catch any crash and return a clean error instead of crashing the server
        print(f"SCRAPE ERROR: {e}")
        return {
            "status": "error",
            "message": str(e),
        }