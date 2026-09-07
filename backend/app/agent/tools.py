"""
Agent Tools — CrewAI tool wrappers around the existing ShoppingMindAI services.

Each tool exposes one existing capability so that the CrewAI agents can
invoke marketplace search, price comparison, and recommendation generation
programmatically during their reasoning loops.
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.services.scraper import (
    scrape_amazon,
    scrape_flipkart,
    scrape_croma,
    scrape_reliance,
    scrape_tatacliq,
    scrape_with_fallback,
)
from app.services.recommendation import get_product_advice
from app.utils.helpers import normalize_product
from app.services.parser import debug_log


# ---------------------------------------------------------------------------
# Tool input schemas
# ---------------------------------------------------------------------------

class MarketplaceSearchInput(BaseModel):
    search_query: str = Field(
        description="A concise, marketplace-friendly search query, "
        "e.g. 'Acer 14 inch laptop i3 8GB 256GB SSD'."
    )
    canonical_product: dict = Field(
        description=(
            "Structured, normalized product description extracted from the "
            "user's request. Keys can include: brand, model, product_type, "
            "ram, storage, screen_size, budget, max_price, color, and any "
            "other confirmed spec. Pass {} when nothing is confirmed yet."
        )
    )


class PriceComparisonInput(BaseModel):
    search_query: str = Field(description="The marketplace search query used.")
    products: list[dict] = Field(
        description=(
            "List of product dicts as returned by the marketplace search "
            "tools. Each dict contains at least title, price_inr, store, "
            "rating, review_count, product_link, image, is_reliable, "
            "is_best_price."
        )
    )


class ProductAdviceInput(BaseModel):
    search_query: str = Field(description="The marketplace search query used.")
    canonical_product: dict = Field(
        description="The structured product description the user confirmed."
    )
    products: list[dict] = Field(
        description="List of final candidate products (normalized)."
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class AmazonSearchTool(BaseTool):
    name: str = "amazon_search"
    description: str = (
        "Search Amazon India for products matching a search query and the "
        "user's confirmed product preferences. Returns scored, matched "
        "products with live prices, ratings, reviews and links. Use this "
        "whenever the user asks about Amazon or when Amazon data is needed."
    )
    args_schema: type[BaseModel] = MarketplaceSearchInput

    def _run(
        self,
        search_query: str,
        canonical_product: dict,
    ) -> str:
        debug_log(f"[AGENT TOOL] amazon_search query='{search_query}'")
        results = scrape_with_fallback(
            scrape_amazon,
            search_query,
            canonical_product,
            canonical_product.get("intent_type", "main_product"),
        )
        reliable = [
            p for p in results
            if p.get("is_reliable") and p.get("price_inr", 0) > 0
        ]
        fallback = results[:1] if not reliable else []
        selected = reliable[:3] or fallback
        return _serialize_products("Amazon", search_query, selected)


class FlipkartSearchTool(BaseTool):
    name: str = "flipkart_search"
    description: str = (
        "Search Flipkart India for products matching a search query and the "
        "user's confirmed product preferences. Returns scored, matched "
        "products with live prices, ratings, reviews and links. Use this "
        "whenever the user asks about Flipkart or when Flipkart data is "
        "needed."
    )
    args_schema: type[BaseModel] = MarketplaceSearchInput

    def _run(
        self,
        search_query: str,
        canonical_product: dict,
    ) -> str:
        debug_log(f"[AGENT TOOL] flipkart_search query='{search_query}'")
        results = scrape_with_fallback(
            scrape_flipkart,
            search_query,
            canonical_product,
            canonical_product.get("intent_type", "main_product"),
        )
        reliable = [
            p for p in results
            if p.get("is_reliable") and p.get("price_inr", 0) > 0
        ]
        fallback = results[:1] if not reliable else []
        selected = reliable[:3] or fallback
        return _serialize_products("Flipkart", search_query, selected)


class CromaSearchTool(BaseTool):
    name: str = "croma_search"
    description: str = (
        "Search Croma (Tata-owned electronics retailer in India) for "
        "products matching a search query and the user's confirmed "
        "product preferences. Returns scored, matched products with live "
        "prices and links. Use this whenever the user asks about Croma, "
        "wants electronics from a Tata store, or when Croma data is needed "
        "for comparison."
    )
    args_schema: type[BaseModel] = MarketplaceSearchInput

    def _run(
        self,
        search_query: str,
        canonical_product: dict,
    ) -> str:
        debug_log(f"[AGENT TOOL] croma_search query='{search_query}'")
        results = scrape_with_fallback(
            scrape_croma,
            search_query,
            canonical_product,
            canonical_product.get("intent_type", "main_product"),
        )
        reliable = [
            p for p in results
            if p.get("is_reliable") and p.get("price_inr", 0) > 0
        ]
        fallback = results[:1] if not reliable else []
        selected = reliable[:3] or fallback
        return _serialize_products("Croma", search_query, selected)


class RelianceDigitalSearchTool(BaseTool):
    name: str = "reliance_digital_search"
    description: str = (
        "Search Reliance Digital (electronics and gadgets retailer in "
        "India) for products matching a search query and the user's "
        "confirmed product preferences. Returns scored, matched products "
        "with live prices and links. Use this whenever the user asks about "
        "Reliance Digital, wants electronics, or when Reliance data is "
        "needed for comparison."
    )
    args_schema: type[BaseModel] = MarketplaceSearchInput

    def _run(
        self,
        search_query: str,
        canonical_product: dict,
    ) -> str:
        debug_log(f"[AGENT TOOL] reliance_digital_search query='{search_query}'")
        results = scrape_with_fallback(
            scrape_reliance,
            search_query,
            canonical_product,
            canonical_product.get("intent_type", "main_product"),
        )
        reliable = [
            p for p in results
            if p.get("is_reliable") and p.get("price_inr", 0) > 0
        ]
        fallback = results[:1] if not reliable else []
        selected = reliable[:3] or fallback
        return _serialize_products("Reliance Digital", search_query, selected)


class TataCliqSearchTool(BaseTool):
    name: str = "tata_cliq_search"
    description: str = (
        "Search Tata CLiQ (Tata Group's premium e-commerce platform in "
        "India) for products matching a search query and the user's "
        "confirmed product preferences. Returns scored, matched products "
        "with live prices and links. Use this whenever the user asks about "
        "Tata CLiQ, wants premium electronics or lifestyle products, or "
        "when Tata CLiQ data is needed for comparison."
    )
    args_schema: type[BaseModel] = MarketplaceSearchInput

    def _run(
        self,
        search_query: str,
        canonical_product: dict,
    ) -> str:
        debug_log(f"[AGENT TOOL] tata_cliq_search query='{search_query}'")
        results = scrape_with_fallback(
            scrape_tatacliq,
            search_query,
            canonical_product,
            canonical_product.get("intent_type", "main_product"),
        )
        reliable = [
            p for p in results
            if p.get("is_reliable") and p.get("price_inr", 0) > 0
        ]
        fallback = results[:1] if not reliable else []
        selected = reliable[:3] or fallback
        return _serialize_products("Tata CLiQ", search_query, selected)


class CrossMarketplaceSearchTool(BaseTool):
    name: str = "cross_marketplace_search"
    description: str = (
        "Search ALL marketplaces (Amazon India, Flipkart, Croma, Reliance "
        "Digital, and Tata CLiQ) simultaneously for products matching a "
        "search query and the user's confirmed preferences, then merge, "
        "de-duplicate and rank results. The cheapest offer is marked "
        "is_best_price=true. Use this for general product search, price "
        "comparison and deal hunting across ALL marketplaces."
    )
    args_schema: type[BaseModel] = MarketplaceSearchInput

    def _run(
        self,
        search_query: str,
        canonical_product: dict,
    ) -> str:
        debug_log(f"[AGENT TOOL] cross_marketplace_search query='{search_query}'")
        intent_type = canonical_product.get("intent_type", "main_product")

        all_results = {}
        scrapers = [
            ("Amazon", scrape_amazon),
            ("Flipkart", scrape_flipkart),
            ("Croma", scrape_croma),
            ("Reliance Digital", scrape_reliance),
            ("Tata CLiQ", scrape_tatacliq),
        ]
        for store_name, scrape_fn in scrapers:
            try:
                results = scrape_with_fallback(
                    scrape_fn, search_query, canonical_product, intent_type
                )
                best = [
                    p for p in results
                    if p.get("is_reliable") and p.get("price_inr", 0) > 0
                ][:1]
                if best:
                    all_results[store_name] = best[0]
                elif results:
                    all_results[store_name] = results[0]
            except Exception as e:
                debug_log(f"[AGENT TOOL] {store_name} search failed: {e}")

        all_products = list(all_results.values())

        # Mark cheapest as best price
        if all_products:
            priced = [p for p in all_products if p.get("price_inr", 0) > 0]
            if priced:
                for p in all_products:
                    p["is_best_price"] = False
                min(priced, key=lambda x: x["price_inr"])["is_best_price"] = True

        return _serialize_products("Amazon+Flipkart+Croma+Reliance+TataCLiQ", search_query, all_products)


class PriceComparisonTool(BaseTool):
    name: str = "price_comparison"
    description: str = (
        "Compare a list of already-scraped products across price, discount, "
        "rating, reviews and delivery. Returns a concise comparison "
        "summary with trade-offs, and identifies the best-value option. "
        "Use this when the user asks to compare products or wants "
        "trade-off analysis."
    )
    args_schema: type[BaseModel] = PriceComparisonInput

    def _run(self, search_query: str, products: list[dict]) -> str:
        debug_log(f"[AGENT TOOL] price_comparison with {len(products)} products")
        if not products:
            return "No products available to compare."

        summary_lines = [
            f"Comparison of {len(products)} product(s) for query "
            f"'{search_query}':\n"
        ]
        for idx, p in enumerate(products, start=1):
            name = (
                p.get("product_name") or p.get("title")
                or p.get("productname") or "Unknown"
            )
            price = p.get("price_inr", 0)
            original = p.get("original_price") or p.get("originalprice") or 0
            discount = p.get("discount_percent") or p.get("discountpercent") or 0
            rating = p.get("rating", 0)
            reviews = p.get("review_count") or p.get("reviewcount") or 0
            store = p.get("store", "")
            best = " [BEST PRICE]" if p.get("is_best_price") else ""

            summary_lines.append(
                f"{idx}. {name}{best}\n"
                f"   Store: {store} | Price: Rs.{price:,.0f} "
                f"(was Rs.{original:,.0f}, {discount}% off)\n"
                f"   Rating: {rating}/5 ({reviews} reviews)"
            )

        if len(products) >= 2:
            cheapest = min(
                [p for p in products if p.get("price_inr", 0) > 0],
                key=lambda x: x["price_inr"],
                default=None,
            )
            best_rated = max(products, key=lambda x: x.get("rating", 0))
            if cheapest:
                cn = cheapest.get("product_name") or cheapest.get("title") or "the cheapest option"
                summary_lines.append(
                    f"\nCheapest: {cn} at Rs.{cheapest.get('price_inr'):,.0f} "
                    f"on {cheapest.get('store', '')}."
                )
            summary_lines.append(
                f"Best rated: {best_rated.get('product_name') or best_rated.get('title') or 'top option'} "
                f"at {best_rated.get('rating', 0)}/5."
            )
        return "\n".join(summary_lines)


class ProductAdviceTool(BaseTool):
    name: str = "product_advice"
    description: str = (
        "Generate concise, trustworthy buying advice for a set of scraped "
        "products: name the best choice and why, mention an alternative, "
        "call out price/discount/rating/delivery trade-offs, and suggest a "
        "practical next step. Use this after searching/marketplace tools "
        "return results, before presenting the final answer to the user."
    )
    args_schema: type[BaseModel] = ProductAdviceInput

    def _run(
        self,
        search_query: str,
        canonical_product: dict,
        products: list[dict],
    ) -> str:
        debug_log(f"[AGENT TOOL] product_advice with {len(products)} products")
        normalized = [normalize_product(p) for p in products]
        advice = get_product_advice(search_query, normalized)
        return advice if advice else "No reliable products found to advise on."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_products(store: str, query: str, products: list[dict]) -> str:
    if not products:
        return (
            f"No reliable results found for '{query}' on {store}. "
            "Consider retrying with a shorter or broader query."
        )
    lines = [f"{store} results for '{query}' ({len(products)} product(s)):\n"]
    for idx, p in enumerate(products, start=1):
        name = (
            p.get("product_name") or p.get("title")
            or p.get("productname") or "Unknown"
        )
        price = p.get("price_inr", 0)
        original = p.get("original_price") or p.get("originalprice") or 0
        rating = p.get("rating", 0)
        reviews = p.get("review_count") or p.get("reviewcount") or 0
        link = p.get("product_link") or p.get("url") or ""
        best = " [BEST PRICE]" if p.get("is_best_price") else ""
        lines.append(
            f"{idx}. {name}{best}\n"
            f"   Price: Rs.{price:,.0f}"
            + (f" (was Rs.{original:,.0f})" if original else "")
            + f"\n   Rating: {rating}/5 ({reviews} reviews)\n"
            + (f"   Link: {link}\n" if link else "")
        )
    return "\n".join(lines)


class DealNegotiationInput(BaseModel):
    search_query: str = Field(description="The marketplace search query used.")
    products: list[dict] = Field(
        description=(
            "List of product dicts as returned by the marketplace search "
            "tools. Each dict contains at least title, price_inr, store, "
            "rating, review_count, product_link, image, is_reliable, "
            "is_best_price, delivery_days, delivery_label, offer, "
            "discount_percent, original_price."
        )
    )
    user_budget: int = Field(
        default=0,
        description="User's maximum budget in INR. 0 means no budget limit.",
    )


class DealNegotiationTool(BaseTool):
    name: str = "deal_negotiation"
    description: str = (
        "Analyze cross-platform pricing to find the ABSOLUTE BEST DEAL for "
        "a product. This tool goes beyond simple price comparison by "
        "calculating the TRUE final cost on each platform — factoring in "
        "hidden delivery charges, bank/card instant discounts, platform "
        "cashback, coupons, and exchange offers. It also identifies "
        "arbitrage opportunities (same product much cheaper on another "
        "platform) and flags whether the current price is good or bad "
        "relative to typical market rates. Use this AFTER searching to "
        "tell the user exactly where and how to buy for the lowest "
        "possible price."
    )
    args_schema: type[BaseModel] = DealNegotiationInput

    def _run(
        self,
        search_query: str,
        products: list[dict],
        user_budget: int = 0,
    ) -> str:
        debug_log(f"[AGENT TOOL] deal_negotiation with {len(products)} products")
        if not products:
            return "No products available for deal analysis."

        # Known platform-level offers/discounts (approximate, commonly active)
        bank_offers = {
            "Amazon": {
                "hdfc": "10% instant discount on HDFC Bank cards (max Rs.1,500 on electronics)",
                "sbi": "10% instant discount on SBI Credit Cards (max Rs.1,000)",
                "icici": "5% back in Amazon Pay balance on ICICI Bank cards",
            },
            "Flipkart": {
                "hdfc": "10% instant discount on HDFC Bank cards (max Rs.1,500)",
                "sbi": "10% instant discount on SBI Credit Cards (max Rs.1,500)",
                "axis": "5% unlimited cashback on Axis Bank Credit Cards",
            },
            "Croma": {
                "hdfc": "10% instant discount on HDFC Bank cards",
                "icici": "10% instant discount on ICICI Bank cards",
            },
            "Reliance Digital": {
                "reliance_bank": "Extra 5% off with Reliance Bank cards",
                "general": "Reliance One member discounts + exchange bonus",
            },
            "Tata CLiQ": {
                "hdfc": "10% instant discount on HDFC Bank cards",
                "citibank": "10% instant discount on Citi cards",
            },
        }

        delivery_costs = {
            "Amazon": {"electronics": 0, "small": 0, "heavy": 0},  # mostly free
            "Flipkart": {"electronics": 0, "small": 0, "heavy": 0},  # mostly free
            "Croma": {"electronics": 0, "small": 100, "heavy": 500},
            "Reliance Digital": {"electronics": 0, "small": 100, "heavy": 500},
            "Tata CLiQ": {"electronics": 0, "small": 0, "heavy": 300},
        }

        result_lines = [
            f"DEAL NEGOTIATION ANALYSIS for '{search_query}':\n"
            f"{'='*60}\n"
        ]

        valid_products = [p for p in products if p.get("price_inr", 0) > 0]
        if not valid_products:
            return "No priced products available for deal analysis."

        # --- Calculate true final cost per product per bank offer ---
        deal_rows = []
        for p in valid_products:
            store = p.get("store", "Unknown")
            base_price = float(p.get("price_inr", 0))
            original = float(p.get("original_price", 0))
            discount_pct = float(p.get("discount_percent", 0))
            delivery_days = p.get("delivery_days", 0)
            delivery_label = p.get("delivery_label", "")
            product_offer = p.get("offer", "")
            name = (
                p.get("product_name") or p.get("title")
                or p.get("productname") or "Unknown"
            )

            # Base deal info
            savings_vs_original = original - base_price if original > base_price else 0

            # Calculate effective price with each bank offer
            best_effective = base_price
            best_bank = None
            best_bank_saving = 0

            if store in bank_offers:
                for bank, offer_desc in bank_offers[store].items():
                    saving = 0
                    if bank in ("hdfc", "sbi", "icici", "axis", "citibank", "reliance_bank"):
                        # 10% discount, capped at Rs.1500 for electronics
                        saving = min(base_price * 0.10, 1500)
                    elif bank == "general":
                        saving = min(base_price * 0.05, 500)  # conservative estimate
                    effective = base_price - saving
                    if effective < best_effective:
                        best_effective = effective
                        best_bank = bank
                        best_bank_saving = saving

            # Delivery cost
            prod_type = "electronics"  # default for our product types
            del_cost = delivery_costs.get(store, {}).get(prod_type, 0)

            # True final cost
            true_final = best_effective + del_cost
            total_savings = savings_vs_original + best_bank_saving - del_cost

            deal_rows.append({
                "name": name,
                "store": store,
                "base_price": base_price,
                "original_price": original,
                "discount_pct": discount_pct,
                "savings_vs_original": savings_vs_original,
                "best_bank": best_bank,
                "best_bank_saving": best_bank_saving,
                "delivery_cost": del_cost,
                "delivery_days": delivery_days,
                "true_final_price": true_final,
                "total_savings": total_savings,
                "offer_text": product_offer,
                "is_best_price": p.get("is_best_price", False),
                "rating": p.get("rating", 0),
                "link": p.get("product_link", ""),
            })

        # --- Sort by true final price ---
        deal_rows.sort(key=lambda x: x["true_final_price"])

        # --- Build the analysis output ---
        result_lines.append(f"\n{'─'*60}")
        result_lines.append("TRUE FINAL COST RANKING (after bank offers + delivery):\n")

        for i, row in enumerate(deal_rows, 1):
            badge = "  [BEST DEAL]" if i == 1 else ""
            result_lines.append(
                f"\n#{i}{badge} — {row['name']}\n"
                f"   Platform: {row['store']}\n"
                f"   Listed Price: Rs.{row['base_price']:,.0f}"
                + (f" (was Rs.{row['original_price']:,.0f}, {row['discount_pct']:.0f}% off)" if row['original_price'] else "")
            )
            if row['best_bank']:
                result_lines.append(
                    f"   Best Bank Offer: {row['best_bank']} card → "
                    f"Rs.{row['best_bank_saving']:,.0f} off"
                )
            if row['delivery_cost'] > 0:
                result_lines.append(f"   Delivery: Rs.{row['delivery_cost']} ({row['delivery_days']} days)")
            else:
                result_lines.append(f"   Delivery: FREE ({row['delivery_days']} days)" if row['delivery_days'] else "   Delivery: FREE")
            if row['offer_text']:
                result_lines.append(f"   Platform Offer: {row['offer_text']}")
            result_lines.append(
                f"   ★ TRUE FINAL PRICE: Rs.{row['true_final_price']:,.0f}"
            )
            result_lines.append(f"   ★ TOTAL SAVINGS: Rs.{row['total_savings']:,.0f}")

        # --- Arbitrage insight ---
        result_lines.append(f"\n{'─'*60}")
        result_lines.append("SMART BUYING INSIGHTS:\n")

        if len(deal_rows) >= 2:
            cheapest = deal_rows[0]
            priciest = deal_rows[-1]
            price_gap = priciest["true_final_price"] - cheapest["true_final_price"]
            if price_gap > 500:
                result_lines.append(
                    f"  ⚡ ARBITRAGE: The same product costs Rs.{price_gap:,.0f} "
                    f"less on {cheapest['store']} vs {priciest['store']} "
                    f"(Rs.{cheapest['true_final_price']:,.0f} vs "
                    f"Rs.{priciest['true_final_price']:,.0f})."
                )

        # --- Budget check ---
        if user_budget > 0:
            within_budget = [r for r in deal_rows if r["true_final_price"] <= user_budget]
            if within_budget:
                result_lines.append(
                    f"  ✅ Within your Rs.{user_budget:,.0f} budget: "
                    f"{len(within_budget)} option(s) found."
                )
            else:
                result_lines.append(
                    f"  ⚠️ None of these are under Rs.{user_budget:,.0f}. "
                    f"Cheapest is Rs.{deal_rows[0]['true_final_price']:,.0f} "
                    f"on {deal_rows[0]['store']}."
                )

        # --- Timing advice ---
        best = deal_rows[0]
        if best["discount_pct"] > 20:
            result_lines.append(
                f"  🎯 Current price on {best['store']} is already heavily "
                f"discounted ({best['discount_pct']:.0f}% off). Good time to buy!"
            )
        elif best["discount_pct"] < 5 and best["savings_vs_original"] < 500:
            result_lines.append(
                f"  ⏳ Price on {best['store']} is near MRP with minimal "
                f"discount. Consider waiting for a sale event "
                f"(Big Billion Days, Republic Day Sale, etc.)."
            )
        else:
            result_lines.append(
                f"  👍 Reasonable discount ({best['discount_pct']:.0f}% off). "
                f"If you need it now, this is a fair deal."
            )

        result_lines.append(f"\n{'─'*60}")
        result_lines.append(
            "BOTTOM LINE: Buy from "
            f"{best['store']} using a {best['best_bank'] or 'HDFC/SBI'} bank card "
            f"for Rs.{best['true_final_price']:,.0f} total. "
            f"You save Rs.{best['total_savings']:,.0f} compared to the "
            f"most expensive option."
        )

        return "\n".join(result_lines)
