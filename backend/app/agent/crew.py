"""CrewAI orchestration for the ShoppingMindAI shopping agent.

The workflow has one intent router, five independent marketplace agents, a
comparison analyst, a deal negotiator, and a final shopping advisor.
"""

import json
import os
import re
from typing import Any

from crewai import Agent, Crew, Process, Task

from app.agent.tools import (
    AmazonSearchTool,
    CromaSearchTool,
    DealNegotiationTool,
    FlipkartSearchTool,
    PriceComparisonTool,
    RelianceDigitalSearchTool,
    TataCliqSearchTool,
)

AGENT_MODEL = os.getenv("AGENT_MODEL", "google/gemini-3.1-flash-lite")
# Verbose mode is enabled by default for local development so agent/tool
# activity is visible in the terminal. Set AGENT_VERBOSE=false in production.
AGENT_VERBOSE = os.getenv("AGENT_VERBOSE", "true").lower() == "true"
TRACE_ENABLED = os.getenv("AGENT_TRACE", "true").lower() == "true"
AGENT_MAX_ITER = int(os.getenv("AGENT_MAX_ITER", "15"))


def _trace(label: str, value: Any = "") -> None:
    """Print readable, secret-safe execution traces for local debugging."""
    if not TRACE_ENABLED:
        return
    text = str(value)
    text = re.sub(r"(?i)(api[_-]?key|authorization|bearer|token|password|secret)\s*[:=]\s*[^,\s}]+", r"\1=[REDACTED]", text)
    if len(text) > 12000:
        text = text[:12000] + "\n...[trace truncated]"
    print(f"\n[ShoppingMindAI] {label}\n{text}", flush=True)


def _task_prompt(task: Task, inputs: dict[str, Any]) -> str:
    try:
        return task.description.format(**inputs)
    except (KeyError, IndexError):
        return task.description


def _agent(role: str, goal: str, backstory: str, tools: list[Any] | None = None) -> Agent:
    return Agent(
        role=role,
        goal=goal,
        backstory=backstory,
        tools=tools or [],
        verbose=AGENT_VERBOSE,
        allow_delegation=False,
        llm=AGENT_MODEL,
    )


def build_crew(session_id: str, user_query: str, conversation_history: str = "", conversation_round: int = 0):
    """Build a fresh, isolated crew for one conversation turn."""
    intent_router = _agent(
        "Shopping Intent Router",
        "Understand the latest user request, preserve context, and output strict JSON describing chat, clarification, search, or result-follow-up intent.",
        "You are a friendly Indian shopping assistant. Ask for missing details for vague requests, understand English and Manglish, and never scrape for greetings or underspecified requests.",
    )

    marketplace_specs = [
        ("Amazon India Research Agent", "Amazon", "amazon", AmazonSearchTool()),
        ("Flipkart Research Agent", "Flipkart", "flipkart", FlipkartSearchTool()),
        ("Croma Research Agent", "Croma", "croma", CromaSearchTool()),
        ("Reliance Digital Research Agent", "Reliance Digital", "reliance_digital", RelianceDigitalSearchTool()),
        ("Tata CLiQ Research Agent", "Tata CLiQ", "tata_cliq", TataCliqSearchTool()),
    ]
    marketplace_agents: list[tuple[str, Agent, Any]] = []
    for role, store, key, tool in marketplace_specs:
        marketplace_agents.append(
            (
                key,
                _agent(
                    role,
                    f"Search only {store} using your dedicated tool. Return real matching products with names, prices, ratings, stock, delivery, offers, images, and links. Reject wrong brands, models, variants, accessories, CAPTCHA pages, Cloudflare pages, and unreliable results.",
                    f"You are the specialist researcher for {store}. You must never call another marketplace's tool or invent unavailable data. If {store} blocks automated access, report no reliable result rather than fabricating one.",
                    [tool],
                ),
                tool,
            )
        )

    comparison_agent = _agent(
        "Comparison Analyst",
        "Compare only products returned by the five marketplace agents, filter incorrect or unreliable matches, and identify best price, best rating, delivery, stock, and trade-offs.",
        "You are a rigorous product comparison analyst. Ground every statement in returned data and clearly label unavailable marketplace data.",
        [PriceComparisonTool()],
    )
    deal_agent = _agent(
        "Deal Negotiator",
        "Find the best true final deal after listed price, discounts, bank offers, exchange offers, coupons, delivery charges, and timing advice.",
        "You are a careful Indian deal negotiator. Never invent an offer; distinguish verified data from assumptions and say when a store has no reliable result.",
        [DealNegotiationTool()],
    )
    advisor_agent = _agent(
        "Shopping Advisor",
        "Provide the final structured JSON response required by the frontend, with a warm answer, products, filters, follow-ups, and transparent caveats.",
        "You are the friendly face of ShoppingMindAI. Support English and Manglish users, keep answers concise, and output only valid JSON.",
    )

    intent_task = Task(
        description=(
            "Analyze this turn. Previous conversation:\n{history}\n\n"
            "Clarifying replies already sent: {conversation_round}\n\n"
            "Latest user input:\n{user_query}\n\n"
            "Return state chat for greetings/off-topic, conversation only when no product category can be inferred, "
            "parsed_query for any recognizable product/category request, or results for a follow-up about displayed products. "
            "Also return user_mode as expert or exploratory. Expert means the user supplied a concrete model, brand, "
            "budget, or meaningful constraints; exploratory means the user named a category but needs recommendations. "
            "Understand normal English and Manglish. Never ask one filter at a time. For a recognizable category "
            "such as phone, laptop, headphones, TV, or appliance, set search_now=true and proceed with a best-effort "
            "search using confirmed details and smart_defaults; optional missing filters must never block the search. "
            "For exploratory categories, set recommendation_lenses to performance, camera, battery, value, and overall "
            "where relevant, and return multiple products for those lenses. Use one consolidated filter card only when "
            "no product category can be inferred. Return only JSON."
        ),
        expected_output=(
            '{"state":"chat|conversation|parsed_query|results","user_mode":"expert|exploratory",'
            '"search_now":true,"search_query":"","canonical_product":{},"marketplaces":[],"filters":{},'
            '"missing_filters":[],"smart_defaults":{},"recommendation_lenses":[],"message":"",'
            '"confidence":"low|medium|high"}'
        ),
        agent=intent_router,
    )

    marketplace_tasks: list[Task] = []
    for key, agent, _tool in marketplace_agents:
        store = key.replace("_", " ").title()
        marketplace_tasks.append(
            Task(
                description=(
                    f"You are the independent {store} agent. Read the intent analysis and search plan:\n"
                    "{intent_output}\n\nLatest query: {user_query}\nSearch query: {search_query}\n"
                    "Canonical product: {canonical_product}\nUser mode: {user_mode}\nSmart defaults: {smart_defaults}\n"
                    "Recommendation lenses: {recommendation_lenses}\n\nUse ONLY your dedicated marketplace tool. "
                    "Return JSON with marketplace, products, blocked, and notes. Do not invent data."
                ),
                expected_output='{"marketplace":"...","products":[],"blocked":false,"notes":"..."}',
                agent=agent,
                context=[intent_task],
            )
        )

    comparison_task = Task(
        description=(
            "Compare the five independent marketplace reports for {user_query}. Reports:\n"
            "Amazon: {amazon_output}\nFlipkart: {flipkart_output}\nCroma: {croma_output}\n"
            "Reliance Digital: {reliance_digital_output}\nTata CLiQ: {tata_cliq_output}\n"
            "User mode: {user_mode}. Smart defaults: {smart_defaults}. Recommendation lenses: {recommendation_lenses}. "
            "Reject wrong variants and unreliable or blocked results. Use price_comparison and return JSON."
        ),
        expected_output='{"products":[],"best_price":{},"best_rated":{},"trade_offs":[],"blocked_marketplaces":[],"advice":""}',
        agent=comparison_agent,
        context=marketplace_tasks,
    )
    negotiation_task = Task(
        description=(
            "Use the comparison and marketplace reports to calculate the true best deal. "
            "Include only evidenced discounts, bank offers, exchange offers, delivery details, and timing advice.\n"
            "Comparison: {comparison_output}\nAmazon: {amazon_output}\nFlipkart: {flipkart_output}\n"
            "Croma: {croma_output}\nReliance Digital: {reliance_digital_output}\nTata CLiQ: {tata_cliq_output}"
        ),
        expected_output='{"best_deal":{},"savings":0,"verified_offers":[],"delivery":"","timing_advice":""}',
        agent=deal_agent,
        context=[comparison_task],
    )
    advisor_task = Task(
        description=(
            "Compose the final frontend payload for {user_query}. Intent: {intent_output}\n"
            "Marketplace reports: {amazon_output}\n{flipkart_output}\n{croma_output}\n{reliance_digital_output}\n{tata_cliq_output}\n"
            "Comparison: {comparison_output}\nNegotiation: {negotiation_output}\n\n"
            "User mode: {user_mode}. Smart defaults: {smart_defaults}. Recommendation lenses: {recommendation_lenses}.\n"
            "For chat return type text. For a request with no inferable product category return type conversation "
            "with at most ONE consolidated filter card. For any recognizable product/category request return "
            "parsed_query immediately with search_query and canonical_product; never force sequential filter turns. "
            "For product results return results with real products and two follow-ups. Mention blocked stores honestly. "
            "Return only one valid JSON object."
        ),
        expected_output=(
            '{"type":"text|conversation|parsed_query|results","message":"",'
            '"search_query":"","canonical_product":{},"filters":{},"cards":[],'
            '"products":[],"follow_ups":[],"confidence":"medium"}'
        ),
        agent=advisor_agent,
        context=[intent_task, *marketplace_tasks, comparison_task, negotiation_task],
    )

    all_tasks = [intent_task, *marketplace_tasks, comparison_task, negotiation_task, advisor_task]
    crew = Crew(
        agents=[intent_router, *(agent for _key, agent, _tool in marketplace_agents), comparison_agent, deal_agent, advisor_agent],
        tasks=all_tasks,
        process=Process.sequential,
        verbose=AGENT_VERBOSE,
        max_iter=AGENT_MAX_ITER,
        memory=False,
    )
    inputs = {
        "session_id": session_id,
        "user_query": user_query,
        "history": conversation_history or "No previous messages (first turn).",
        "conversation_round": str(conversation_round),
        "intent_output": "",
        "user_mode": "exploratory",
        "search_now": "True",
        "smart_defaults": "{}",
        "recommendation_lenses": "[]",
        "search_query": user_query,
        "canonical_product": "{}",
        "marketplaces": "amazon, flipkart, croma, reliance_digital, tata_cliq",
        "amazon_output": "",
        "flipkart_output": "",
        "croma_output": "",
        "reliance_digital_output": "",
        "tata_cliq_output": "",
        "comparison_output": "",
        "negotiation_output": "",
    }
    return crew, inputs, intent_task, all_tasks


def _is_greeting(text: str) -> bool:
    """Recognize short greetings consistently without routing them to the LLM."""
    words = re.sub(r"[^a-z\s]", " ", text.lower()).split()
    if not words or len(words) > 6:
        return False
    greeting_words = {"hi", "hai", "hello", "hey", "yo", "sup", "namaste", "namaskar"}
    polite_words = {"there", "everyone", "friend", "good", "morning", "afternoon", "evening", "day"}
    return any(word in greeting_words for word in words) and all(
        word in greeting_words or word in polite_words for word in words
    )


async def run_crew_for_turn(session_id: str, user_query: str, conversation_history: str = "", conversation_round: int = 0) -> dict:
    # Greetings should be instant, useful, and scraper-free. Returning a
    # structured conversation card here also avoids depending on an LLM to
    # remember the special greeting-card contract.
    if _is_greeting(user_query.strip()):
        greeting = _greeting_response()
        _trace("SHORTCUT :: Greeting (no LLM/tools)", greeting)
        return greeting

    best_effort = _best_effort_category_response(user_query)
    if best_effort is not None:
        _trace("SHORTCUT :: Direct category search (no clarification)", best_effort)
        return best_effort

    crew, inputs, intent_task, all_tasks = build_crew(session_id, user_query, conversation_history, conversation_round)
    try:
        _trace("REQUEST", {"session_id": session_id, "user_query": user_query, "conversation_round": conversation_round})
        _trace("AGENT PLAN", [agent.role for agent in crew.agents])
        _trace("LLM INPUT :: Shopping Intent Router", _task_prompt(intent_task, inputs))
        crew.tasks = [intent_task]
        intent_result = await crew.kickoff_async(inputs=inputs)
        intent_raw = intent_result.raw.strip()
        _trace("LLM OUTPUT :: Shopping Intent Router", intent_raw)
        intent_payload = _parse_json(intent_raw, {"state": "chat", "message": intent_raw})
        state = intent_payload.get("state", "chat")
        intent_payload = _apply_smart_defaults(intent_payload, user_query)
        intent_raw = json.dumps(intent_payload, ensure_ascii=False)
        inputs["intent_output"] = intent_raw
        inputs["user_mode"] = intent_payload.get("user_mode", "exploratory")
        inputs["search_now"] = str(intent_payload.get("search_now", True))
        inputs["smart_defaults"] = json.dumps(intent_payload.get("smart_defaults", {}), ensure_ascii=False)
        inputs["recommendation_lenses"] = json.dumps(intent_payload.get("recommendation_lenses", []), ensure_ascii=False)
        inputs["search_query"] = intent_payload.get("search_query") or user_query
        inputs["canonical_product"] = json.dumps(intent_payload.get("canonical_product", {}), ensure_ascii=False)
        if state in {"chat", "conversation"}:
            inputs.update({"comparison_output": "", "negotiation_output": ""})
            crew.tasks = [intent_task, all_tasks[-1]]
        else:
            crew.tasks = all_tasks

        _trace("SELECTED STATE", {"state": state, "tasks": [task.agent.role for task in crew.tasks]})
        for task in crew.tasks:
            _trace(f"LLM INPUT :: {task.agent.role}", _task_prompt(task, inputs))
        result = await crew.kickoff_async(inputs=inputs)
        final_raw = result.raw.strip()
        _trace("LLM OUTPUT :: Shopping Advisor", final_raw)
        final_payload = _parse_advisor_output(final_raw)
        _trace("RESPONSE TO FRONTEND", final_payload)
        return final_payload
    except Exception as exc:  # noqa: BLE001
        _trace("ERROR", repr(exc))
        return {"fallback": True, "message": str(exc)}


def _apply_smart_defaults(payload: dict, user_query: str) -> dict:
    """Make router output safe and useful even when optional fields are absent."""
    result = dict(payload or {})
    canonical = dict(result.get("canonical_product") or {})
    text = user_query.lower()

    category_patterns = {
        "smartphone": r"\b(?:smartphones?|mobiles?|cell phones?)\b",
        "laptop": r"\blaptops?\b",
        "headphone": r"\b(?:headphones?|earbuds?|earphones?)\b",
        "television": r"\b(?:televisions?|tvs?)\b",
        "camera": r"\bcameras?\b",
        "tablet": r"\btablets?\b",
        "refrigerator": r"\b(?:refrigerators?|fridges?)\b",
        "washing machine": r"\bwashing machines?\b",
    }
    inferred_category = next(
        (name for name, pattern in category_patterns.items() if re.search(pattern, text)),
        None,
    )
    product_type = str(canonical.get("product_type", "")).strip().lower()
    if not product_type and inferred_category:
        canonical["product_type"] = inferred_category
        product_type = inferred_category

    has_constraints = bool(re.search(
        r"\b(?:under|below|upto|up to|less than|gb|tb|ram|camera|gaming|battery|storage|color|colour|brand|model|pro|max|plus|ultra)\b",
        text,
    ))
    user_mode = result.get("user_mode") if result.get("user_mode") in {"expert", "exploratory"} else None
    result["user_mode"] = user_mode or ("expert" if has_constraints else "exploratory")

    defaults = dict(result.get("smart_defaults") or {})
    defaults.setdefault("currency", "INR")
    defaults.setdefault("result_count", 8)
    defaults.setdefault("sort_by", "overall")
    defaults.setdefault("include_variants", True)
    if result["user_mode"] == "exploratory":
        defaults.setdefault("rank_lenses", ["overall", "value", "performance", "camera", "battery"])
    result["smart_defaults"] = defaults

    if inferred_category and result.get("state") in {"conversation", "chat", None}:
        result["state"] = "parsed_query"
        result["search_now"] = True
        result.setdefault("search_query", user_query.strip())
    else:
        result["search_now"] = bool(result.get("search_now", bool(inferred_category)))
    result["canonical_product"] = canonical
    result["missing_filters"] = result.get("missing_filters") or []
    result["recommendation_lenses"] = result.get("recommendation_lenses") or defaults.get("rank_lenses", [])
    return result


def _best_effort_category_response(user_query: str) -> dict | None:
    """Search immediately when the user names a recognizable category.

    Optional preferences should improve a search, not block it. This keeps
    broad requests useful while still allowing the agent pipeline to handle
    unusual or ambiguous requests.
    """
    text = user_query.strip()
    lowered = text.lower()
    categories = {
        "phone": r"\b(?:phone|mobile|smartphone)s?\b",
        "laptop": r"\blaptops?\b",
        "headphones": r"\b(?:headphones?|earbuds?|earphones?)\b",
        "smartwatch": r"\bsmart watches?\b|\bsmartwatches?\b",
        "television": r"\b(?:televisions?|tvs?)\b",
        "camera": r"\bcameras?\b",
        "tablet": r"\btablets?\b",
        "air purifier": r"\bair purifiers?\b",
        "refrigerator": r"\b(?:refrigerators?|fridges?)\b",
        "washing machine": r"\bwashing machines?\b",
    }
    category = next((name for name, pattern in categories.items() if re.search(pattern, lowered)), None)
    if category is None or "charger" in lowered or "case" in lowered:
        return None

    price_match = re.search(r"(?:under|below|less than|upto|up to)\s*(?:₹|rs\.?\s*)?([0-9][0-9,]*(?:\.[0-9]+)?)(?:\s*(k|000))?", lowered)
    max_price = None
    if price_match:
        max_price = float(price_match.group(1).replace(",", ""))
        if price_match.group(2) == "k":
            max_price *= 1000

    canonical = {"product_type": category}
    if max_price:
        canonical["max_price"] = int(max_price)
    return {
        "fallback": False,
        "type": "parsed_query",
        "message": f"I’ll search the best {category} options now and compare the available stores.",
        "search_query": text,
        "canonical_product": canonical,
        "filters": {},
        "intent_type": "main_product",
        "loading": {
            "title": f"Finding the best {category} options",
            "description": "I’m comparing available prices, ratings, and delivery details across stores.",
            "tip": "You can refine the results afterward with a brand, budget, or feature.",
        },
    }


def _greeting_response() -> dict:
    return {
        "fallback": False,
        "type": "conversation",
        "message": "Hello! I can help you find the right product and compare trusted stores. What would you like to shop for?",
        "confidence": "high",
        "cards": [
            {
                "type": "options",
                "title": "What are you shopping for?",
                "description": "Choose a product category or search for anything directly.",
                "options": [
                    "Phones",
                    "Laptops",
                    "Headphones",
                    "Smartwatches",
                    "Televisions",
                    "Home appliances",
                ],
                "show_search": True,
                "search_placeholder": "Search for any product...",
                "submit_button": "Find Products",
            }
        ],
    }


def _parse_json(raw: str, fallback: dict) -> dict:
    clean = raw.replace("```json", "").replace("```", "").strip()
    start, end = clean.find("{"), clean.rfind("}")
    if start < 0 or end <= start:
        return fallback
    try:
        value = json.loads(clean[start : end + 1])
        return value if isinstance(value, dict) else fallback
    except json.JSONDecodeError:
        return fallback


def _parse_advisor_output(raw: str) -> dict:
    value = _parse_json(raw, {"fallback": True, "message": raw})
    value["fallback"] = False if "type" in value else True
    return value
