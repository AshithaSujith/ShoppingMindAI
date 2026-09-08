"""CrewAI orchestration for the ShoppingMindAI shopping agent.

The workflow has one intent router, five independent marketplace agents, a
comparison analyst, a deal negotiator, and a final shopping advisor.

v2 changes (fixes three root causes, not just wording):
  1. Filter cards were being silently dropped because no prompt ever taught
     the model the exact JSON shape `_merge_filter_cards` expects. Both
     prompts now embed the literal schema + a worked example, and
     `_merge_filter_cards` gained a safety-net fallback that synthesizes a
     card from `filters` if the model forgets to wrap it.
  2. The crew had `allow_delegation=False` everywhere and `memory=False` —
     i.e. it was a fixed pipeline, not an agent system. Analyst-tier agents
     can now delegate/ask follow-up questions of specialists, and the crew
     retains memory across the run.
  3. Greetings were a single hardcoded string with zero variation or
     awareness of returning users. Replaced with light variation + a shared
     persona guide baked into every agent's backstory so tone is consistent
     and not robotic.

v3 changes (latency):
  4. The 5 marketplace tasks only depend on intent_task, not on each other,
     but ran strictly sequentially — 5 back-to-back LLM+tool round trips.
     They're now marked `async_execution=True` so CrewAI runs them
     concurrently.
  5. `allow_delegation` and crew `memory` (added in v2 for agentic quality)
     each cost an extra LLM round trip when triggered. They're now opt-in
     via env vars, off by default, so the fast path stays fast and you can
     switch them on for a specific run when correctness matters more than
     speed.
  6. Leaf agents (marketplace search — one tool call, done) get a small
     dedicated max_iter instead of inheriting the 15-iteration budget meant
     for agents that actually need to reason over multiple steps.

v4 changes (real-time scrape, then agents enrich):
  7. Marketplace search used to go through an LLM agent that *decided* to
     call its tool. That decision is deterministic ("call this tool with
     this query"), so it doesn't need an LLM at all — it was paying for an
     LLM round trip on top of every scrape. The 5 marketplaces are now
     scraped directly and concurrently in plain Python
     (`_scrape_all_marketplaces`, one thread per store, bounded by
     MARKETPLACE_TIMEOUT_SECONDS so a single stuck store can't hold up the
     rest). Comparison / negotiation / advisor agents only run afterward,
     on the raw scraped products — matching "scrape first, agents work on
     what came back".
  8. `run_crew_for_turn` now has three distinct branches instead of one
     generic "run whatever tasks apply" path: chat (instant), conversation
     (filters only, no scrape), and parsed_query/results (concurrent scrape
     -> enrichment crew). This makes each branch's latency predictable
     instead of depending on which tasks a shared crew happens to run.

NOTE: `_invoke_marketplace_tool` below assumes the standard CrewAI
`BaseTool.run(query=...)` calling convention. If your tools in
app/agent/tools.py expect a different kwarg name or signature, update that
one function — everything else (concurrency, timeouts, normalization) is
independent of it.
"""

import asyncio
import json
import os
import random
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
# Off by default: each adds latency (an extra LLM round trip per delegation
# call, and a vector read/write per task for memory). Flip to "true" for a
# specific run when you want the extra reasoning quality more than speed.
AGENT_ALLOW_DELEGATION = os.getenv("AGENT_ALLOW_DELEGATION", "false").lower() == "true"
AGENT_MEMORY = os.getenv("AGENT_MEMORY", "false").lower() == "true"
# Per-store scrape timeout so one blocked/slow marketplace can't stall the
# other four — a store that times out is just reported as blocked.
MARKETPLACE_TIMEOUT_SECONDS = min(
    float(os.getenv("MARKETPLACE_TIMEOUT_SECONDS", "25")),
    25.0,
)

# ---------------------------------------------------------------------------
# Shared persona + schema fragments (kept in one place so every agent and
# task speaks with the same voice and agrees on the same JSON contracts).
# ---------------------------------------------------------------------------

PERSONA_GUIDE = (
    "Voice: warm, concise, and genuinely helpful — like a knowledgeable friend "
    "in an electronics store, not a form-filling bot. Vary your phrasing turn "
    "to turn; never repeat the exact same sentence twice in one session. "
    "Acknowledge what the user already told you instead of re-asking. Support "
    "plain English and Manglish equally well. Never sound like a template."
)

FILTER_CARD_SCHEMA = (
    "A filter card is exactly this shape — do not invent a different one:\n"
    '{"type":"filters","title":"<short question>","description":"<one line>",'
    '"groups":[{"name":"<filter name, e.g. Brand>","options":["opt1","opt2","opt3"]},'
    '{"name":"<filter name, e.g. Budget>","options":["Under ₹15,000","₹15,000-₹30,000","Above ₹30,000"]}],'
    '"show_search":true,"search_placeholder":"Search here..."}\n'
    "Example — user says 'I want a phone':\n"
    '{"type":"filters","title":"Let\'s find your phone","description":"Pick what matters most, or search directly.",'
    '"groups":[{"name":"Brand","options":["Apple","Samsung","OnePlus","Xiaomi","Any brand"]},'
    '{"name":"Budget","options":["Under ₹15,000","₹15,000-₹30,000","₹30,000-₹60,000","Above ₹60,000"]},'
    '{"name":"Priority","options":["Camera","Battery life","Performance","Value for money"]}],'
    '"show_search":true,"search_placeholder":"Or search for a specific model..."}'
)


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


def _agent(
    role: str,
    goal: str,
    backstory: str,
    tools: list[Any] | None = None,
    allow_delegation: bool = False,
    max_iter: int | None = None,
) -> Agent:
    return Agent(
        role=role,
        goal=goal,
        backstory=f"{backstory} {PERSONA_GUIDE}",
        tools=tools or [],
        verbose=AGENT_VERBOSE,
        # Delegation is real capability but real latency: only honor the
        # per-agent request if the env toggle allows it for this run.
        allow_delegation=allow_delegation and AGENT_ALLOW_DELEGATION,
        respect_context_window=True,
        max_iter=max_iter or AGENT_MAX_ITER,
        llm=AGENT_MODEL,
    )


def build_crew(session_id: str, user_query: str, conversation_history: str = "", conversation_round: int = 0):
    """Build a fresh, isolated crew for one conversation turn."""
    intent_router = _agent(
        "Shopping Intent Router",
        "Understand the latest user request, preserve context, and output strict JSON describing chat, clarification, search, or result-follow-up intent.",
        "You are a friendly Indian shopping assistant. Ask for missing details for vague requests, understand English and Manglish, and never scrape for greetings or underspecified requests.",
    )

    # NOTE: marketplace/comparison/negotiation agents used to be built here
    # too, but they're no longer part of this crew — direct scraping
    # (_scrape_all_marketplaces) and enrichment (build_enrichment_crew) own
    # that work now. This crew only ever runs intent_task, and optionally
    # advisor_task for the no-scrape chat/conversation branch.
    advisor_agent = _agent(
        "Shopping Advisor",
        "Provide the final structured JSON response required by the frontend, with a warm answer, products, filters, follow-ups, and transparent caveats.",
        "You are the friendly face of ShoppingMindAI. Support English and Manglish users, keep answers concise, and output only valid JSON. If any upstream report is missing or unclear, ask that specialist for clarification before writing your final answer rather than guessing.",
        allow_delegation=True,
    )

    intent_task = Task(
        description=(
            "## Conversation so far\n{history}\n\n"
            "## Clarifying replies already sent this turn\n{conversation_round}\n\n"
            "## Latest user message\n{user_query}\n\n"
            "Classify this turn. Follow these rules in order and stop at the first match:\n"
            "1. Greeting or off-topic (no product mentioned) -> state=chat\n"
            "2. Follow-up question about products already shown this session -> state=results\n"
            "3. Broad category with no brand/budget/model/spec constraint "
            "(e.g. 'phones', 'oru laptop venam' [Manglish: 'want a laptop']) -> "
            "state=conversation, search_now=false, filters populated, and later "
            "the advisor will wrap them in ONE consolidated filter card\n"
            "4. Specific request with at least one concrete constraint "
            "(brand, model, budget, spec, or explicit 'search now') -> "
            "state=parsed_query, search_now=true, search_query=<cleaned query>\n\n"
            "When useful, include category_terms inside canonical_product as a short list of "
            "category wording commonly used in marketplace titles. Always set "
            "canonical_product[\"product_type\"] explicitly (e.g. \"smartphone\", \"laptop\"), "
            "never only category_terms. Derive these terms from the request and context; do not "
            "use a fixed global synonym list.\n\n"
            "Also classify user_mode:\n"
            "- expert: user gave a concrete brand, model, budget, or spec\n"
            "- exploratory: user named only a category\n\n"
            "When state=conversation, populate `filters` as a plain object mapping "
            "each relevant filter name to its list of sensible options, e.g.:\n"
            '{"Brand":["Apple","Samsung","OnePlus"],"Budget":["Under ₹15,000","₹15,000-₹30,000"]}\n'
            "Pick filter names and options that actually make sense for that "
            "product category — do not reuse phone filters for, say, blenders.\n\n"
            "For exploratory + filters already selected in a previous turn, set "
            "recommendation_lenses to the criteria that matter for that category "
            "(e.g. camera/battery/performance for phones; taste/quantity for food).\n\n"
            "Never split filters into multiple sequential questions — all relevant "
            "choices go in `filters` at once. Understand plain English and Manglish "
            "equally. Reference {history} naturally — do not act like this is a "
            "first message if it is not. Return only JSON, no prose, no markdown fences."
        ),
        expected_output=(
            '{"state":"chat|conversation|parsed_query|results","user_mode":"expert|exploratory",'
            '"search_now":true,"search_query":"","canonical_product":{},"marketplaces":[],"filters":{},'
            '"missing_filters":[],"smart_defaults":{},"recommendation_lenses":[],"message":"",'
            '"confidence":"low|medium|high"}'
        ),
        agent=intent_router,
    )

    advisor_task = Task(
        description=(
            "## Inputs\n"
            "User query: {user_query}\n"
            "Intent analysis: {intent_output}\n"
            "Marketplace reports — Amazon: {amazon_output} | Flipkart: {flipkart_output} | "
            "Croma: {croma_output} | Reliance Digital: {reliance_digital_output} | "
            "Tata CLiQ: {tata_cliq_output}\n"
            "Comparison: {comparison_output}\n"
            "Negotiation: {negotiation_output}\n"
            "User mode: {user_mode} | Smart defaults: {smart_defaults} | "
            "Recommendation lenses: {recommendation_lenses}\n\n"
            "## Output routing — pick exactly one, in this order\n"
            "1. Pure chat/greeting -> type=text, short warm message, no cards\n"
            "2. No inferable product category, or filters were prepared by the "
            "intent analysis -> type=conversation, and wrap the `filters` object "
            "from the intent analysis into exactly ONE card using this schema:\n"
            f"{FILTER_CARD_SCHEMA}\n"
            "3. Any recognizable product/category, even without full filters -> "
            "type=parsed_query with search_query and canonical_product filled in — "
            "never force the user through sequential filter turns\n"
            "4. Products were actually searched -> type=results with real products "
            "only (never invent one) and exactly two relevant follow_ups\n\n"
            "## Rules\n"
            "- If any marketplace was blocked or returned nothing reliable, say so "
            "plainly in message — do not silently drop it or fabricate a substitute.\n"
            "- Every product in products[] must trace back to a marketplace report.\n"
            "- Write message like a helpful person, not a form: reference what the "
            "user actually said, avoid repeating stock phrases from earlier in "
            "{history}.\n"
            "- Output exactly one valid JSON object — no prose before or after, no "
            "markdown fences."
        ),
        expected_output=(
            '{"type":"text|conversation|parsed_query|results","message":"",'
            '"search_query":"","canonical_product":{},"filters":{},"cards":[],'
            '"products":[],"follow_ups":[],"confidence":"medium"}'
        ),
        agent=advisor_agent,
        context=[intent_task],
    )

    all_tasks = [intent_task, advisor_task]
    crew = Crew(
        agents=[intent_router, advisor_agent],
        tasks=all_tasks,
        process=Process.sequential,
        verbose=AGENT_VERBOSE,
        max_iter=AGENT_MAX_ITER,
        # Memory costs a vector read/write per task and is largely redundant
        # here since conversation_history is already passed explicitly each
        # turn — only pay for it when AGENT_MEMORY=true.
        memory=AGENT_MEMORY,
    )
    inputs = {
        "session_id": session_id,
        "user_query": user_query,
        "history": conversation_history or "No previous messages (first turn).",
        "conversation_round": str(conversation_round),
        "intent_output": "",
        "user_mode": "exploratory",
        "search_now": "true",
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


# ---------------------------------------------------------------------------
# Direct concurrent scraping (no LLM in the loop) + a lighter enrichment
# crew that only spins up comparison/negotiation/advisor agents once real
# products already exist.
# ---------------------------------------------------------------------------

_MARKETPLACE_SPECS = [
    ("amazon", "Amazon", AmazonSearchTool),
    ("flipkart", "Flipkart", FlipkartSearchTool),
    ("croma", "Croma", CromaSearchTool),
    ("reliance_digital", "Reliance Digital", RelianceDigitalSearchTool),
    ("tata_cliq", "Tata CLiQ", TataCliqSearchTool),
]


def _invoke_marketplace_tool(tool: Any, search_query: str, canonical_product: dict) -> Any:
    """Call a marketplace tool synchronously.

    Use the schema's canonical field name. Do not catch TypeError here: a
    TypeError raised inside a scraper must not trigger a second call that drops
    canonical_product and silently changes filtering behavior.
    """
    return tool.run(
        search_query=search_query,
        canonical_product=canonical_product or {},
    )


def _normalize_marketplace_result(key: str, store: str, raw: Any) -> dict:
    """Coerce whatever a tool returns into the {marketplace, products,
    blocked, notes} shape the comparison/negotiation/advisor prompts expect.
    """
    if isinstance(raw, dict):
        return {
            "marketplace": raw.get("marketplace", store),
            "products": raw.get("products", []) if isinstance(raw.get("products"), list) else [],
            "blocked": bool(raw.get("blocked", False)),
            "notes": raw.get("notes", ""),
        }
    if isinstance(raw, list):
        return {"marketplace": store, "products": raw, "blocked": False, "notes": ""}
    if isinstance(raw, str):
        parsed = _parse_json(raw, {})
        if parsed:
            return _normalize_marketplace_result(key, store, parsed)
        return {"marketplace": store, "products": [], "blocked": False, "notes": raw[:500]}
    return {"marketplace": store, "products": [], "blocked": True, "notes": "No usable response from tool."}


async def _scrape_one_marketplace(key: str, store: str, tool: Any, search_query: str, canonical_product: dict) -> tuple[str, dict]:
    try:
        raw = await asyncio.wait_for(
            asyncio.to_thread(_invoke_marketplace_tool, tool, search_query, canonical_product),
            timeout=MARKETPLACE_TIMEOUT_SECONDS,
        )
        result = _normalize_marketplace_result(key, store, raw)
    except asyncio.TimeoutError:
        result = {"marketplace": store, "products": [], "blocked": True, "notes": "Timed out."}
    except Exception as exc:  # noqa: BLE001
        result = {"marketplace": store, "products": [], "blocked": True, "notes": f"Error: {exc}"}
    _trace(f"SCRAPE :: {store}", result)
    return key, result


async def _scrape_all_marketplaces(search_query: str, canonical_product: dict) -> dict[str, dict]:
    """Hit all 5 marketplaces concurrently, no LLM involved. This is the
    "scrape in seconds" step — total time is bounded by the slowest store,
    capped by MARKETPLACE_TIMEOUT_SECONDS, not the sum of all 5.
    """
    tasks = [
        _scrape_one_marketplace(key, store, tool_cls(), search_query, canonical_product)
        for key, store, tool_cls in _MARKETPLACE_SPECS
    ]
    results = await asyncio.gather(*tasks)
    return dict(results)


def build_enrichment_crew(inputs: dict[str, Any]):
    """A smaller crew with only the agents that need real reasoning:
    comparison, negotiation, and the final advisor. Runs only after
    `_scrape_all_marketplaces` has already populated inputs["<key>_output"].
    """
    comparison_agent = _agent(
        "Comparison Analyst",
        "Compare only products returned by the five marketplace scrapes, filter incorrect or unreliable matches, and identify best price, best rating, delivery, stock, and trade-offs.",
        "You are a rigorous product comparison analyst. Ground every statement in returned data and clearly label unavailable marketplace data. If a report looks incomplete, contradictory, or suspicious, you may ask for clarification before finalizing your comparison.",
        [PriceComparisonTool()],
        allow_delegation=True,
    )
    deal_agent = _agent(
        "Deal Negotiator",
        "Find the best true final deal after listed price, discounts, bank offers, exchange offers, coupons, delivery charges, and timing advice.",
        "You are a careful Indian deal negotiator. Never invent an offer; distinguish verified data from assumptions and say when a store has no reliable result.",
        [DealNegotiationTool()],
        allow_delegation=True,
    )
    advisor_agent = _agent(
        "Shopping Advisor",
        "Provide the final structured JSON response required by the frontend, with a warm answer, products, filters, follow-ups, and transparent caveats.",
        "You are the friendly face of ShoppingMindAI. Support English and Manglish users, keep answers concise, and output only valid JSON.",
        allow_delegation=True,
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
            "## Inputs\n"
            "User query: {user_query}\n"
            "Intent analysis: {intent_output}\n"
            "Marketplace reports — Amazon: {amazon_output} | Flipkart: {flipkart_output} | "
            "Croma: {croma_output} | Reliance Digital: {reliance_digital_output} | "
            "Tata CLiQ: {tata_cliq_output}\n"
            "Comparison: {comparison_output}\n"
            "Negotiation: {negotiation_output}\n"
            "User mode: {user_mode} | Smart defaults: {smart_defaults} | "
            "Recommendation lenses: {recommendation_lenses}\n\n"
            "The products were already scraped live from all 5 marketplaces — "
            "your job is to synthesize, not to decide whether to search. "
            "Return type=results with real products only (never invent one) and "
            "exactly two relevant follow_ups. If any marketplace was blocked or "
            "returned nothing reliable, say so plainly in message. Write message "
            "like a helpful person, not a form. Output exactly one valid JSON "
            "object — no prose before or after, no markdown fences."
        ),
        expected_output=(
            '{"type":"results","message":"","products":[],"follow_ups":[],"confidence":"medium"}'
        ),
        agent=advisor_agent,
        context=[comparison_task, negotiation_task],
    )

    crew = Crew(
        agents=[comparison_agent, deal_agent, advisor_agent],
        tasks=[comparison_task, negotiation_task, advisor_task],
        process=Process.sequential,
        verbose=AGENT_VERBOSE,
        max_iter=AGENT_MAX_ITER,
        memory=AGENT_MEMORY,
    )
    return crew


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


def _best_effort_category_response(user_query: str) -> dict | None:
    """Keep category routing model-driven; do not hardcode product options."""
    return None


def _merge_filter_cards(payload: dict) -> dict:
    """Merge model-generated filter cards into one card without inventing options.

    Includes a safety net: if the model produced a `filters` object (per the
    schema taught in the prompt) but forgot to wrap it in a `cards` entry, we
    synthesize the card ourselves rather than silently losing it — this is
    the direct fix for "filters never show up".
    """
    cards = payload.get("cards")
    cards = cards if isinstance(cards, list) else []

    generated_filters = payload.get("filters")
    generated_filters = generated_filters if isinstance(generated_filters, dict) else {}

    filter_cards = [
        card for card in cards
        if isinstance(card, dict) and card.get("type") in {"filters", "filter_group"}
    ]

    if not filter_cards:
        if payload.get("type") == "conversation" and generated_filters:
            synthesized = {
                "type": "filters",
                "title": payload.get("message") or "Let's narrow this down",
                "description": "Pick what matters most, or search directly.",
                "groups": [
                    {"name": name, "options": values if isinstance(values, list) else [values]}
                    for name, values in generated_filters.items()
                ],
                "show_search": True,
                "search_placeholder": "Search here...",
            }
            payload["cards"] = [synthesized, *cards]
        return payload

    merged = dict(filter_cards[0])
    merged["type"] = "filters"
    filter_lookup = {
        str(name).strip().casefold(): values
        for name, values in generated_filters.items()
    }

    groups = []
    seen_names = set()
    for card in filter_cards:
        card_groups = card.get("groups")
        if not isinstance(card_groups, list) or not card_groups:
            card_groups = [
                {"name": name, "options": values}
                for name, values in generated_filters.items()
            ]

        for group in card_groups:
            if not isinstance(group, dict):
                continue
            raw_name = str(group.get("name", "")).strip()
            if not raw_name:
                continue
            name = raw_name.casefold()
            if name in seen_names:
                continue

            normalized_group = dict(group)
            options = normalized_group.get("options")
            if not isinstance(options, list) or not options:
                values = filter_lookup.get(name, [])
                normalized_group["options"] = values if isinstance(values, list) else [values]

            seen_names.add(name)
            groups.append(normalized_group)

    merged["groups"] = groups
    merged["show_search"] = any(card.get("show_search") is not False for card in filter_cards)
    merged.setdefault("search_placeholder", "Search here...")

    remaining_cards = [card for card in cards if card not in filter_cards]
    payload["cards"] = [merged, *remaining_cards]
    return payload


async def run_crew_for_turn(session_id: str, user_query: str, conversation_history: str = "", conversation_round: int = 0) -> dict:
    # Greetings should be instant, useful, and scraper-free. Returning a
    # structured conversation card here also avoids depending on an LLM to
    # remember the special greeting-card contract.
    if _is_greeting(user_query.strip()):
        greeting = _greeting_response(returning=bool(conversation_history.strip()))
        _trace("SHORTCUT :: Greeting (no LLM/tools)", greeting)
        return greeting

    best_effort = _best_effort_category_response(user_query)
    if best_effort is not None:
        _trace("SHORTCUT :: Direct category search (no clarification)", best_effort)
        return best_effort

    crew, inputs, intent_task, _all_tasks = build_crew(session_id, user_query, conversation_history, conversation_round)

    try:
        _trace("REQUEST", {"session_id": session_id, "user_query": user_query, "conversation_round": conversation_round})
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
        inputs["search_now"] = json.dumps(bool(intent_payload.get("search_now", True)))
        inputs["smart_defaults"] = json.dumps(intent_payload.get("smart_defaults", {}), ensure_ascii=False)
        inputs["recommendation_lenses"] = json.dumps(intent_payload.get("recommendation_lenses", []), ensure_ascii=False)
        inputs["search_query"] = intent_payload.get("search_query") or user_query
        inputs["canonical_product"] = json.dumps(intent_payload.get("canonical_product", {}), ensure_ascii=False)

        # --- Branch 1: chat / conversation -> no scraping, filters or a
        # short reply only. Fast by construction (intent + advisor, 2 LLM
        # calls max).
        if state in {"chat", "conversation"}:
            inputs.update({
                "amazon_output": "", "flipkart_output": "", "croma_output": "",
                "reliance_digital_output": "", "tata_cliq_output": "",
                "comparison_output": "", "negotiation_output": "",
            })
            advisor_task = _all_tasks[-1]
            crew.tasks = [intent_task, advisor_task]
            _trace("SELECTED STATE", {"state": state, "path": "filters-or-chat, no scrape"})
            result = await crew.kickoff_async(inputs=inputs)
            final_payload = _parse_advisor_output(result.raw.strip())
            final_payload = _merge_filter_cards(final_payload)
            _trace("RESPONSE TO FRONTEND", final_payload)
            return final_payload

        # --- Branch 2: parsed_query / results -> the user is either an
        # expert who searched directly, or has already picked filters.
        # Scrape all 5 marketplaces concurrently (no LLM), then only the
        # comparison/negotiation/advisor agents run, on real data.
        search_query = inputs["search_query"]
        canonical_product = _canonical_product_for_scraping(intent_payload)
        _trace("SCRAPE START", {"search_query": search_query, "canonical_product": canonical_product})
        scraped = await _scrape_all_marketplaces(search_query, canonical_product)
        for key, result in scraped.items():
            inputs[f"{key}_output"] = json.dumps(result, ensure_ascii=False)
        _trace("SCRAPE DONE", {key: {"blocked": r["blocked"], "count": len(r["products"])} for key, r in scraped.items()})

        enrichment_crew = build_enrichment_crew(inputs)
        for task in enrichment_crew.tasks:
            _trace(f"LLM INPUT :: {task.agent.role}", _task_prompt(task, inputs))
        result = await enrichment_crew.kickoff_async(inputs=inputs)
        final_raw = result.raw.strip()
        _trace("LLM OUTPUT :: Shopping Advisor", final_raw)
        final_payload = _parse_advisor_output(final_raw)
        final_payload = _merge_filter_cards(final_payload)
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

    default_search_now = result.get("state") not in {"conversation", "chat"}
    result["search_now"] = bool(result.get("search_now", default_search_now))

    result["canonical_product"] = canonical
    result["missing_filters"] = result.get("missing_filters") or []
    result["recommendation_lenses"] = result.get("recommendation_lenses") or defaults.get("rank_lenses", [])
    return result


_GREETING_OPENERS = [
    "Hey! I can help you find the right product and compare trusted stores. What are you shopping for?",
    "Hi there! Looking for something specific, or want to browse a category?",
    "Hello! Tell me what you're shopping for and I'll compare prices across stores for you.",
]
_RETURNING_OPENERS = [
    "Welcome back! What else can I help you find?",
    "Hey again! Ready to keep looking, or shopping for something new?",
]


def _greeting_response(returning: bool = False) -> dict:
    message = random.choice(_RETURNING_OPENERS if returning else _GREETING_OPENERS)
    return {
        "fallback": False,
        "type": "conversation",
        "message": message,
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

def _canonical_product_for_scraping(intent_payload: dict) -> dict:
    """Merge dynamic intent evidence and budget filters for the scrapers."""
    canonical = dict(intent_payload.get("canonical_product") or {})

    # The intent router sometimes emits "category" instead of "product_type".
    # Every scoring/price-bounds function in scraping_utils.py only reads
    # product_type, so alias it here — cheap, and doesn't depend on the LLM
    # reliably following prompt wording every time.
    if not canonical.get("product_type") and canonical.get("category"):
        canonical["product_type"] = canonical["category"]

    filters = intent_payload.get("filters") or {}
    price_values = filters.get("Price Range") or filters.get("Budget") or []
    if isinstance(price_values, str):
        price_values = [price_values]
    for value in price_values:
        numbers = re.findall(r"\d[\d,]*", str(value))
        if numbers and re.search(r"up to|under|below|less than|maximum", str(value), re.I):
            canonical["max_price"] = max(float(number.replace(",", "")) for number in numbers)
            break
    return canonical