import asyncio
import json
import logging

from fastapi import APIRouter

from app.schemas.requests import SearchRequest, ScrapeRequest

from app.services.parser import debug_log
from app.services.scraper import (
    scrape_amazon,
    scrape_flipkart,
    scrape_croma,
    scrape_reliance,
    scrape_tatacliq,
    scrape_with_fallback,
)

from app.services.chatbot import ChatBot
from app.services.recommendation import get_product_advice
from app.agent.crew import run_crew_for_turn
from app.utils.helpers import normalize_product

router = APIRouter()
logger = logging.getLogger("shoppingmind.search")

chatbot = ChatBot()


def _build_context(session_id: str, query: str, filters: dict | None = None):
    """Load conversation history and build the context string for the crew."""
    history = chatbot.get_history(session_id)
    is_first_message = len(history) == 0

    if is_first_message:
        debug_log("AGENT MODE: FIRST MESSAGE -> Skip DB History")
        filter_context = f"\nSelected Filters:\n{json.dumps(filters, ensure_ascii=False)}" if filters else ""
        full_context = f"Latest User Input:\n{query}{filter_context}"
        conversation_round = 0
    else:
        debug_log("AGENT MODE: FOLLOW-UP MESSAGE -> Load DB History")
        context_lines = [f"{m['role'].upper()}: {m['content']}" for m in history]
        conversation_round = sum(
            1
            for m in history
            if m["role"] == "assistant"
            and not m["content"].startswith("CONFIRMED_STATE:")
        )
        full_context = f"""Previous Conversation:
{chr(10).join(context_lines)}

CONVERSATION_ROUND: {conversation_round}

Latest User Input:
{query}

Selected Filters:
{json.dumps(filters, ensure_ascii=False) if filters else "None"}""".strip()

    return full_context, conversation_round, is_first_message


def _record_assistant_reply(session_id, query, assistant_message, state_snapshot=None):
    """Save the assistant reply (and optional state snapshot) to the DB."""
    if assistant_message:
        chatbot.save_conversation(session_id, query, assistant_message)
    if state_snapshot is not None:
        chatbot.save_conversation(
            session_id, query, "CONFIRMED_STATE:" + json.dumps(state_snapshot)
        )


def _normalize_results_products(products: list) -> list:
    """Map advisor/scraper product shapes to the frontend contract."""
    normalized = []
    for raw in products:
        if not isinstance(raw, dict):
            continue
        price = raw.get("price_inr") or raw.get("price") or raw.get("priceinr") or 0
        link = raw.get("product_link") or raw.get("link") or raw.get("url") or ""
        title = raw.get("title") or raw.get("product_name") or raw.get("productname") or ""
        normalized.append(
            normalize_product(
                {
                    "product_name": title,
                    "price_inr": float(price) if price else 0,
                    "original_price": raw.get("original_price") or raw.get("originalprice") or 0,
                    "discount_percent": raw.get("discount_percent") or raw.get("discountpercent") or 0,
                    "store": raw.get("store", ""),
                    "rating": raw.get("rating", 0),
                    "review_count": raw.get("review_count") or raw.get("reviewcount") or 0,
                    "image": raw.get("image", ""),
                    "product_link": link,
                    "is_reliable": raw.get("is_reliable", raw.get("isreliable", True)),
                    "is_best_price": raw.get("is_best_price", raw.get("isbestprice", False)),
                    "delivery_label": raw.get("delivery_label") or raw.get("deliverylabel") or "",
                }
            )
        )
    return normalized


def _normalize_canonical_product(payload: dict) -> dict:
    """Normalize the crew's canonical_product to match the scraper's key style."""
    raw = payload.get("canonical_product", {}) or {}
    normalized = {
        k: (v[0] if isinstance(v, list) and v else v)
        for k, v in raw.items()
        if v is not None and str(v).strip().lower() not in ("no preference", "", "none")
    }
    # Normalize category labels so plural UI options match product-title tokens.
    product_type = str(normalized.get("product_type", "")).strip().lower()
    category_aliases = {
        "smartphones": "smartphone",
        "mobiles": "mobile phone",
        "laptops": "laptop",
        "headphones": "headphone",
        "earbuds": "earbud",
        "televisions": "television",
        "tvs": "television",
        "refrigerators": "refrigerator",
        "fridges": "refrigerator",
        "washing machines": "washing machine",
    }
    if product_type in category_aliases:
        normalized["product_type"] = category_aliases[product_type]

    # Copy price info into fields the scraper's filters expect
    max_price = normalized.pop("max_price", None) or normalized.pop("Max price", None)
    if max_price:
        normalized["max_price"] = str(max_price)
    return normalized


@router.post("/search")
async def search(payload: SearchRequest):
    """Route the user's message through the CrewAI agent crew.

    The crew returns a structured JSON payload matching the same frontend
    contract as the original pipeline: type in
    {text, conversation, parsed_query, results}, plus the scraper triggers
    search_query / canonical_product when type == parsed_query.
    """
    try:
        query = payload.query.strip()
        session_id = payload.session_id

        debug_log(f"\n{'=' * 50}")
        debug_log(f"AGENT USER [{session_id}]: {query}")

        if not query:
            return {"status": "error", "message": "Empty query received."}

        full_context, conversation_round, _ = _build_context(session_id, query, payload.filters)

        result = await run_crew_for_turn(
            session_id=session_id,
            user_query=query,
            conversation_history=full_context,
            conversation_round=conversation_round,
        )

        if result.get("fallback"):
            debug_log(f"AGENT FALLBACK: {result.get('message', '')[:200]}")
            message = (
                result.get("message")
                or "Something went wrong on my end. Please try again."
            )
            _record_assistant_reply(session_id, query, message)
            return {
                "status": "success",
                "data": {"type": "text", "message": message},
            }

        response_type = result.get("type", "text")
        assistant_message = result.get("message", "")

        if response_type == "parsed_query":
            canonical_product = _normalize_canonical_product(result)
            search_query = result.get("search_query", "")
            loading = result.get("loading", {})

            if not search_query:
                debug_log("AGENT: no search_query in parsed_query response -> treating as conversation")
                response_type = "conversation"
            else:
                state_snapshot = {
                    "confirmed_canonical_product": canonical_product,
                    "search_query": search_query,
                    "filters_offered_this_turn": list(result.get("filters", {}).keys()),
                    "loading": loading,
                }
                _record_assistant_reply(
                    session_id, query, assistant_message, state_snapshot
                )
                return {
                    "status": "success",
                    "data": {
                        "type": "parsed_query",
                        "search_query": search_query,
                        "canonical_product": canonical_product,
                        "filters": result.get("filters", {}),
                        "intent_type": result.get("intent_type", "main_product"),
                        "loading": loading,
                    },
                }

        if response_type == "results":
            products = _normalize_results_products(result.get("products", []))
            try:
                _record_assistant_reply(session_id, query, assistant_message)
            except Exception:
                logger.exception("Failed to persist assistant reply for session %s", session_id)
            return {
                "status": "success",
                "data": {
                    "type": "results",
                    "message": assistant_message,
                    "products": products,
                    "follow_ups": result.get("follow_ups", []),
                },
            }

        # conversation | text | chat — all map to a conversational reply
        _record_assistant_reply(session_id, query, assistant_message)
        return {
            "status": "success",
            "data": {
                "type": "conversation" if response_type == "conversation" else "text",
                "message": assistant_message,
                "cards": result.get("cards", []),
                "filters": result.get("filters", {}),
                "confidence": result.get("confidence", "medium"),
                "questions": result.get("questions", []),
                "chips": result.get("chips", []),
                "recommendations": result.get("recommendations", []),
                "comparison": result.get("comparison"),
                "product_line": result.get("product_line"),
                "follow_ups": result.get("follow_ups", []),
            },
        }

    except Exception as exc:
        logger.exception("Agent API request failed")
        debug_log("AGENT API ERROR: request failed; details recorded in server logs")
        return {"status": "error", "message": "The shopping assistant is temporarily unavailable. Please try again."}


@router.post("/scrape")
async def scrape(payload: ScrapeRequest):
    """Direct scraper endpoint — deterministic logic, still used by the
    frontend 'Search Products' button and runnable as a standalone tool."""
    try:
        search_query = payload.search_query
        canonical_product = payload.canonical_product

        intent_type = canonical_product.get("intent_type", "main_product")

        debug_log(f"\n{'=' * 60}")
        debug_log(f"SCRAPING: {search_query}")

        # Playwright-based scrapers are synchronous, so run every dedicated
        # marketplace scraper in its own worker thread. This keeps FastAPI
        # responsive and makes all five marketplace agents active in this path.
        marketplaces = [
            ("Amazon", scrape_amazon),
            ("Flipkart", scrape_flipkart),
            ("Croma", scrape_croma),
            ("Reliance Digital", scrape_reliance),
            ("Tata CLiQ", scrape_tatacliq),
        ]

        async def run_marketplace(store_name, scraper):
            try:
                debug_log(f"MARKETPLACE START: {store_name}")
                results = await asyncio.to_thread(
                    scrape_with_fallback,
                    scraper,
                    search_query,
                    canonical_product,
                    intent_type,
                )
                debug_log(f"MARKETPLACE DONE: {store_name}: {len(results)} candidates")
                return store_name, results
            except Exception as exc:
                logger.exception("%s scrape failed", store_name)
                debug_log(f"MARKETPLACE ERROR: {store_name}: {exc}")
                return store_name, []

        # ScrapeOps Proxy API plans can have a low concurrency limit. Run the
        # five stores sequentially so one request does not cause 429 failures
        # for the remaining marketplaces.
        marketplace_results = {}
        for name, scraper in marketplaces:
            store_name, results = await run_marketplace(name, scraper)
            marketplace_results[store_name] = results
        all_products = []
        for store_name, results in marketplace_results.items():
            reliable = [
                p for p in results
                if p.get("is_reliable") and p.get("price_inr", 0) > 0
            ]
            selected = reliable[:3] or results[:1]
            all_products.extend(selected)
            debug_log(f"MARKETPLACE RESULTS: {store_name}: {len(selected)} returned")

        if all_products:
            priced = [p for p in all_products if p.get("price_inr", 0) > 0]
            for p in all_products:
                p["is_best_price"] = False
            if priced:
                min(priced, key=lambda x: x["price_inr"])["is_best_price"] = True

        advice = await asyncio.to_thread(get_product_advice, search_query, all_products)

        return {
            "status": "success",
            "data": {
                "type": "products",
                "products": all_products,
                "message": advice,
                "canonical_product": canonical_product,
                "search_query": search_query,
            },
        }

    except Exception as exc:
        logger.exception("Scrape request failed")
        debug_log("SCRAPE ERROR: request failed; details recorded in server logs")
        return {
            "status": "error",
            "message": "Product search is temporarily unavailable. Please try again.",
        }
