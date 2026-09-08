"""Search and scraping endpoints for ShoppingMindAI."""

import asyncio
import json
import logging
import os
import re

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


def _normalize_canonical_product(payload: dict) -> dict:
    """Normalize model field names and values to the scraper contract."""
    raw = payload.get("canonical_product", {}) or {}
    key_map = {
        "producttype": "product_type", "type": "product_type", "category": "product_type",
        "subcategory": "product_type", "brandname": "brand", "brand": "brand",
        "modelname": "model", "model": "model", "screensize": "size", "screen": "size",
        "size": "size", "ram": "ram", "storage": "storage", "colour": "color",
        "color": "color", "maxprice": "max_price", "price": "max_price",
        "budget": "max_price", "maxbudget": "max_price",
    }
    normalized = {}
    for raw_key, value in raw.items():
        if value is None:
            continue
        value = value[0] if isinstance(value, list) and value else value
        if str(value).strip().casefold() in {"", "none", "no preference", "any", "any brand"}:
            continue
        compact_key = re.sub(r"[^a-z0-9]", "", str(raw_key).casefold())
        key = key_map.get(compact_key, str(raw_key).strip())
        normalized[key] = value

    product_type = str(normalized.get("product_type", "")).strip().lower()
    if product_type:
        cleaned = re.sub(r"[^a-z0-9\s]", " ", product_type)
        normalized["product_type"] = re.sub(r"\s+", " ", cleaned).strip()

    max_price = normalized.get("max_price")
    if max_price is not None:
        numbers = re.findall(r"\d+(?:\.\d+)?", str(max_price).replace(",", ""))
        if numbers:
            normalized["max_price"] = str(max(float(number) for number in numbers))
    return normalized


@router.post("/search")
async def search(payload: SearchRequest):
    """Route the user's message through the CrewAI agent crew."""
    try:
        query = payload.query.strip()
        session_id = payload.session_id

        print(f"[API] POST /search session={session_id} query={query!r}", flush=True)
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
                        "message": assistant_message,
                        "search_query": search_query,
                        "canonical_product": canonical_product,
                        "filters": result.get("filters", {}),
                        "cards": result.get("cards", []),
                        "intent_type": result.get("intent_type", "main_product"),
                        "search_now": bool(result.get("search_now", True)),
                        "loading": loading,
                    },
                }

        if response_type == "results":
            products = result.get("products", [])
            _record_assistant_reply(session_id, query, assistant_message)
            return {
                "status": "success",
                "data": {
                    "type": "results",
                    "message": assistant_message,
                    "products": products,
                    "follow_ups": result.get("follow_ups", []),
                },
            }

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
    """Direct scraper endpoint — used by the frontend 'Search Products' button."""
    try:
        search_query = payload.search_query
        canonical_product = payload.canonical_product

        print(f"[API] POST /scrape query={search_query!r}", flush=True)
        intent_type = canonical_product.get("intent_type", "main_product")

        debug_log(f"\n{'=' * 60}")
        debug_log(f"SCRAPING: {search_query}")

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

        concurrency = max(1, int(os.getenv("MARKETPLACE_CONCURRENCY", "5")))
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_marketplace(name, scraper):
            async with semaphore:
                return await run_marketplace(name, scraper)

        marketplace_pairs = await asyncio.gather(
            *(bounded_marketplace(name, scraper) for name, scraper in marketplaces)
        )
        marketplace_results = dict(marketplace_pairs)
        all_products = []
        for store_name, results in marketplace_results.items():
            reliable = [
                p for p in results
                if p.get("is_reliable", True) and p.get("price_inr", 0) > 0
            ]
            selected = reliable[:3] if reliable else [p for p in results if p.get("price_inr", 0) > 0][:3]
            all_products.extend(selected)
            debug_log(f"MARKETPLACE RESULTS: {store_name}: {len(selected)} reliable products returned")

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