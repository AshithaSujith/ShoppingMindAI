import asyncio
import json

from fastapi import APIRouter, BackgroundTasks

from app.schemas.requests import (
    SearchRequest,
    ScrapeRequest,
)

from app.services.parser import get_intent
from app.services.scraper import (
    scrape_amazon,
    scrape_flipkart,
    scrape_with_fallback,
)

from app.services.chatbot import ChatBot

from app.utils.helpers import (
    normalize_product,
    should_ask_filters,
)

router = APIRouter()

chatbot = ChatBot()

@router.post("/search")
async def search(
    payload: SearchRequest,
    background_tasks: BackgroundTasks,
    ):
    try:
        query = payload.query.strip()
        session_id = payload.session_id

        print(f"\n{'=' * 50}")
        print(f"USER [{session_id}]: {query}")

        if not query:
            return {"status": "error", "message": "Empty query received."}

        history = chatbot.get_history(session_id)

        is_first_message = len(history) == 0

        # FIX: build full_context ONCE, inside the if/else, instead of building it
        # twice (a leftover assignment was overwritten by a second block that
        # referenced context_lines even when it was never created — caused a
        # NameError crash on every first message)
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

        # chatbot.add_message(session_id, "user", query)

        result = get_intent(full_context)

        search_mode = result.get("search_mode", "exact_search")

        print(f"INTENT RESULT: {result.get('status')} | MODE: {search_mode}")

        if result.get("status") == "ready":
            data = result.get("data", {})
            canonical_product = data.get("canonical_product", {})
            search_query = data.get("search_query", "")
            intent_type = canonical_product.get("intent_type", "main_product")

            if should_ask_filters(query):
                message = "Please give a few more details so I can find the right product."
                background_tasks.add_task(
                    chatbot.save_conversation,
                    session_id,
                    query,
                    message,
                )

                print("\n========== FILTERS ==========")
                print(result.get("filters", {}))
                print("=============================\n")

                return {
                    "status": "success",
                    "data": {
                        "type": "filters",
                        "message": message,
                        "filters": data.get("filters", {}),
                        "category": canonical_product.get("category", "general"),
                    },
                }

            print(f"SEARCH QUERY: {search_query}")

            if not search_query:
                return {"status": "error", "message": "Failed to generate search query."}

            # Detect if the "extracted details" card was already shown this session
            # (marked by a CONFIRMED_STATE: prefix in history)
            already_shown = any(
                m["role"] == "assistant" and m["content"].startswith("CONFIRMED_STATE:")
                for m in history
            )

            if not already_shown:
                state_snapshot = {
                    "confirmed_canonical_product": canonical_product,
                    "search_query": search_query,
                    "filters_offered_this_turn": list(data.get("filters", {}).keys()),
                }

                background_tasks.add_task(
                    chatbot.save_conversation,
                    session_id,
                    query,
                    "CONFIRMED_STATE:" + json.dumps(state_snapshot),
                )

                return {
                    "status": "success",
                    "data": {
                        "type": "parsed_query",
                        "search_query": search_query,
                        "canonical_product": canonical_product,
                        "filters": data.get("filters", {}),
                        "intent_type": intent_type,
                    },
                }

            return {
                "status": "success",
                "data": {
                    "type": "ready_to_scrape",
                    "message": "Ready to search products.",
                    "search_query": search_query,
                    "canonical_product": canonical_product,
                    "intent_type": intent_type,
                },
            }

        elif result.get("status") == "clarification":
            question = result.get("question", "Could you give me more details?")
            background_tasks.add_task(
                chatbot.save_conversation,
                session_id,
                query,
                question,
            )

            return {
                "status": "success",
                "data": {
                    "type": "clarify",
                    "message": question,
                    "options": result.get("options", []),
                    "missing_attributes": result.get("missing_attributes", []),
                    "filters": result.get("filters", {}),
                },
            }

        elif result.get("status") == "refine":
            message = result.get("message", "Please select your preferences.")
            background_tasks.add_task(
                chatbot.save_conversation,
                session_id,
                query,
                message,
            )

            return {
                "status": "success",
                "data": {
                    "type": "filters",
                    "message": message,
                    "filters": result.get("filters", {}),
                    "category": result.get("category", "general"),
                },
            }

        elif result.get("status") == "chat":
            message = result.get("message", "How can I help you shop today?")
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

        elif result.get("status") == "reject":
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

        return {
            "status": "error",
            "message": result.get("message", "Something went wrong. Please try again."),
        }
    except Exception as e:
        print(f"MAIN API ERROR: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/scrape")
async def scrape(payload: ScrapeRequest):
    try:
        search_query = payload.search_query
        canonical_product = payload.canonical_product

        intent_type = canonical_product.get(
            "intent_type",
            "main_product"
        )

        print(f"\n{'=' * 60}")
        print(f"SCRAPING: {search_query}")

        amazon_task = asyncio.to_thread(
            scrape_with_fallback,
            scrape_amazon,
            search_query,
            canonical_product,
            intent_type,
        )

        flipkart_task = asyncio.to_thread(
            scrape_with_fallback,
            scrape_flipkart,
            search_query,
            canonical_product,
            intent_type,
        )

        amazon_results, flipkart_results = await asyncio.gather(
            amazon_task,
            flipkart_task,
        )

        amazon_best = [
            p
            for p in amazon_results
            if p.get("is_reliable")
            and p.get("price_inr", 0) > 0
        ]

        flipkart_best = [
            p
            for p in flipkart_results
            if p.get("is_reliable")
            and p.get("price_inr", 0) > 0
        ]

        all_products = []

        all_products.extend(amazon_best[:1])
        all_products.extend(flipkart_best[:1])

        if all_products:
            priced = [
                p
                for p in all_products
                if p["price_inr"] > 0
            ]

            if priced:
                for p in all_products:
                    p["is_best_price"] = False

                min(
                    priced,
                    key=lambda x: x["price_inr"]
                )["is_best_price"] = True

        # Fallback: avoid returning empty results if scrapers found something but scored it low
        if not all_products:
            all_products = amazon_results[:1] or flipkart_results[:1]

        return {
            "status": "success",
            "data": {
                "type": "products",
                "products": all_products,
                "canonical_product": canonical_product,
                "search_query": search_query,
            },
        }

    except Exception as e:
        print(f"SCRAPE ERROR: {e}")
        return {
            "status": "error",
            "message": str(e),
        }