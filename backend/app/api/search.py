import asyncio
import json

from fastapi import APIRouter, BackgroundTasks

from app.schemas.requests import (
    SearchRequest,
    ScrapeRequest,
)

from app.services.parser import get_intent, debug_log
from app.services.scraper import (
    scrape_amazon,
    scrape_flipkart,
    scrape_with_fallback,
)

from app.services.chatbot import ChatBot

from app.utils.helpers import (
    normalize_product,
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

        debug_log(f"\n{'=' * 50}")
        debug_log(f"USER [{session_id}]: {query}")

        if not query:
            return {"status": "error", "message": "Empty query received."}

        history = chatbot.get_history(session_id)

        is_first_message = len(history) == 0

        # FIX: build full_context ONCE, inside the if/else, instead of building it
        # twice (a leftover assignment was overwritten by a second block that
        # referenced context_lines even when it was never created — caused a
        # NameError crash on every first message)
        if is_first_message:
            debug_log("FIRST MESSAGE -> Skip DB History")

            full_context = f"""Latest User Input:
{query}""".strip()

        else:
            debug_log("FOLLOW-UP MESSAGE -> Load DB History")

            context_lines = [
                f"{m['role'].upper()}: {m['content']}"
                for m in history
            ]

            # Count how many clarifying (non-CONFIRMED_STATE) assistant replies
            # have already gone out this session, so the model can be told —
            # per prompt.txt Section 7a — to stop asking and move on.
            conversation_round = sum(
                1
                for m in history
                if m["role"] == "assistant"
                and not m["content"].startswith("CONFIRMED_STATE:")
            )

            debug_log(f"CONVERSATION_ROUND: {conversation_round}")

            full_context = f"""Previous Conversation:
{chr(10).join(context_lines)}

CONVERSATION_ROUND: {conversation_round}

Latest User Input:
{query}""".strip()

        # chatbot.add_message(session_id, "user", query)

        result = get_intent(full_context)

        search_mode = result.get("search_mode", "exact_search")

        debug_log(f"INTENT RESULT: {result.get('status')} | MODE: {search_mode}")

        if result.get("status") == "ready":
            data = result.get("data", {})
            canonical_product = data.get("canonical_product", {})
            search_query = data.get("search_query", "")
            intent_type = canonical_product.get("intent_type", "main_product")

            debug_log(f"SEARCH QUERY: {search_query}")

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

                assistant_message = result.get("message", "")
                if assistant_message:
                    background_tasks.add_task(
                        chatbot.save_conversation,
                        session_id,
                        query,
                        assistant_message,
                    )

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
                    "type": "conversation",
                    "assistant_message": message,
                    "confidence": result.get("confidence", "medium"),
                    "filters": result.get("filters", {}),
                    "category": result.get("category", "general"),
                    "next_action": "refine",
                },
            }
        elif result.get("status") == "conversation":
            message = result.get("assistant_message", "")

            background_tasks.add_task(
                chatbot.save_conversation,
                session_id,
                query,
                message,
            )   
            return {
                    "status": "success",
                    "data": {
                        "type": "conversation",
                        "message": message,
                        "cards": result.get("cards", []),
                        "confidence": result.get("confidence", "medium"),
                        "questions": result.get("questions", []),
                        "chips": result.get("chips", []),
                        "recommendations": result.get("recommendations", []),
                        "comparison": result.get("comparison"),
                        "product_line": result.get("product_line"),
                        "next_action": result.get("next_action", "conversation"),
                        "missing_required_attributes": result.get(
                            "missing_required_attributes", []
                        ),
                    },
                }
        elif result.get("status") == "results":
            background_tasks.add_task(
                chatbot.save_conversation,
                session_id,
                query,
                result.get("message", ""),
            )

            return {
                "status": "success",
                "data": {
                    "type": "results",
                    "message": result.get("message", ""),
                    "products": result.get("products", []),
                    "follow_ups": result.get("follow_ups", []),
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
                    "cards": result.get("cards", []),
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
        debug_log(f"MAIN API ERROR: {e}")
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

        debug_log(f"\n{'=' * 60}")
        debug_log(f"SCRAPING: {search_query}")

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
        debug_log(f"SCRAPE ERROR: {e}")
        return {
            "status": "error",
            "message": str(e),
        }