import sys
import asyncio
import json

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from parser import get_intent
from scraper import scrape_amazon, scrape_flipkart, scrape_with_fallback
from chatbot import ChatBot

app = FastAPI()
chatbot = ChatBot()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str
    session_id: str = "user1"
    history: Optional[List[dict]] = None


class ClearRequest(BaseModel):
    session_id: str

class ScrapeRequest(BaseModel):
    search_query: str
    canonical_product: dict

def normalize_product(p: dict) -> dict:
    return {
        "product_name": p.get("product_name", ""),
        "productname": p.get("product_name", ""),
        "price_inr": p.get("price_inr", 0),
        "priceinr": p.get("price_inr", 0),
        "original_price": p.get("original_price", 0),
        "originalprice": p.get("original_price", 0),
        "discount_percent": p.get("discount_percent", 0),
        "discountpercent": p.get("discount_percent", 0),
        "store": p.get("store", ""),
        "delivery_label": p.get("delivery_label", ""),
        "deliverylabel": p.get("delivery_label", ""),
        "rating": p.get("rating", 0),
        "review_count": p.get("review_count", 0),
        "reviewcount": p.get("review_count", 0),
        "image": p.get("image", ""),
        "product_link": p.get("product_link", ""),
        "productlink": p.get("product_link", ""),
        "is_reliable": p.get("is_reliable", False),
        "isreliable": p.get("is_reliable", False),
        "is_best_price": p.get("is_best_price", False),
        "isbestprice": p.get("is_best_price", False),
        "match_score": p.get("match_score", 0),
        "offer": p.get("offer", ""),
        "stock_status": p.get("stock_status", ""),
    }


def should_ask_filters(query: str) -> bool:
    words = query.lower().split()
    useless_words = {
        "i", "want", "to", "buy", "need", "show", "me",
        "find", "a", "an", "the", "some", "please", "hey"
    }
    meaningful = [w for w in words if w not in useless_words]
    return len(meaningful) < 2


@app.get("/")
async def root():
    return {"message": "ShopMind AI API Running"}


@app.post("/session/clear")
async def clear_session(payload: ClearRequest):
    chatbot.clear(payload.session_id)
    print(f"[Session cleared] {payload.session_id}")
    return {"status": "success", "message": "Session cleared"}


@app.get("/session/history/{session_id}")
async def get_history(session_id: str):
    history = chatbot.get_history(session_id)
    return {"status": "success", "session_id": session_id, "messages": history}


@app.post("/search")
async def search(payload: SearchRequest):
    try:
        query = payload.query.strip()
        session_id = payload.session_id

        print(f"\n{'=' * 50}")
        print(f"USER [{session_id}]: {query}")

        if not query:
            return {"status": "error", "message": "Empty query received."}

        history = chatbot.get_history(session_id)
        context_lines = [f"{m['role'].upper()}: {m['content']}" for m in history]

        full_context = f"""Previous Conversation:
{chr(10).join(context_lines)}

Latest User Input:
{query}""".strip()

        chatbot.add_message(session_id, "user", query)

        result = get_intent(full_context)
        search_mode = result.get("search_mode", "exact_search")

        print(f"INTENT RESULT: {result.get('status')} | MODE: {search_mode}")

        if result.get("status") == "ready":
            data = result.get("data", {})
            canonical_product = data.get("canonical_product", {})
            search_query = data.get("search_query", "")
            intent_type = canonical_product.get("intent_type", "main_product")

            # If query is too vague, ask for more details first
            if should_ask_filters(query):
                message = "Please give a few more details so I can find the right product."
                chatbot.add_message(session_id, "assistant", message)
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

            # ── Check if extracted details were already shown this session ──
            already_shown = any(
                m["role"] == "assistant" and m["content"].startswith("CONFIRMED_STATE:")
                for m in history
            )

            if not already_shown:
                # Step 1: Save state and return parsed_query
                # Frontend will show extracted details, then auto-trigger scraping
                state_snapshot = {
                    "confirmed_canonical_product": canonical_product,
                    "search_query": search_query,
                    "filters_offered_this_turn": list(data.get("filters", {}).keys()),
                }
                chatbot.add_message(
                    session_id,
                    "assistant",
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

            # Step 2: Search summary already shown.
            # Wait for the frontend to call /scrape.

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
            chatbot.add_message(session_id, "assistant", question)
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
            chatbot.add_message(session_id, "assistant", message)
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
            chatbot.add_message(session_id, "assistant", message)
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
            chatbot.add_message(session_id, "assistant", message)
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

@app.post("/scrape")
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