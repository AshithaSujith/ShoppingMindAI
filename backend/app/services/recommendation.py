import json

from app.services.providers.provider_factory import get_provider


RECOMMENDATION_PROMPT = """You are a careful AI shopping copilot. Use ONLY the supplied scraped products.
Give concise, useful buying advice: name the best choice and why, mention one alternative when available,
call out price/discount/rating/delivery trade-offs, and give one practical next step. Never invent facts.
Return JSON only: {"message": "..."}. Use short paragraphs and bullets in the message."""


def get_product_advice(search_query: str, products: list[dict]) -> str:
    if not products:
        return ""

    try:
        response = get_provider().generate(
            system_prompt=RECOMMENDATION_PROMPT,
            user_input=json.dumps({"search_query": search_query, "products": products}),
            temperature=0.2,
            max_tokens=450,
        )
        data = json.loads(response.replace("```json", "").replace("```", "").strip())
        message = data.get("message", "")
        return message if isinstance(message, str) else ""
    except Exception as error:
        print(f"RECOMMENDATION ERROR: {error}")
        return ""
