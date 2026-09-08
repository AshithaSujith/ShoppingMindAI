"""Product data normalization service for ShoppingMindAI."""

import re
from typing import Any


def convert_to_float(price_val: Any) -> float:
    """Safely convert any raw price representation into a clean float."""
    if not price_val:
        return 0.0
    if isinstance(price_val, (int, float)):
        return float(price_val)
    # Remove currency symbols, commas, and extra whitespace
    clean_price = "".join(c for c in str(price_val) if c.isdigit() or c == ".")
    try:
        val = float(clean_price)
        return val if val >= 10.0 else 0.0
    except ValueError:
        return 0.0


def parse_delivery(delivery_val: Any) -> int:
    """Extract delivery duration in days from text or numbers."""
    if not delivery_val:
        return 2  # Default to 2 days
    if isinstance(delivery_val, int):
        return delivery_val
    delivery_str = str(delivery_val).lower()
    if "today" in delivery_str:
        return 0
    if "tomorrow" in delivery_str:
        return 1
    numbers = re.findall(r"\d+", delivery_str)
    if numbers:
        return int(numbers[-1])
    return 2


def normalize_product_data(raw_data: dict[str, Any], source: str = "Marketplace") -> dict[str, Any]:
    """Normalize raw marketplace product dictionary to standard frontend/agent schema."""
    if not isinstance(raw_data, dict):
        return {}

    title = (
        raw_data.get("product_name")
        or raw_data.get("title")
        or raw_data.get("name")
        or raw_data.get("productname")
        or "Unknown Product"
    ).strip()

    rating_raw = raw_data.get("rating", 0.0)
    try:
        rating = float(rating_raw)
    except (ValueError, TypeError):
        nums = re.findall(r"\d+(?:\.\d+)?", str(rating_raw))
        rating = float(nums[0]) if nums else 0.0

    price = convert_to_float(
        raw_data.get("price_inr")
        or raw_data.get("price")
        or raw_data.get("priceinr")
    )

    original_price = convert_to_float(
        raw_data.get("original_price")
        or raw_data.get("mrp")
        or raw_data.get("originalprice")
    )

    discount_percent = raw_data.get("discount_percent") or raw_data.get("discountpercent") or 0
    if not discount_percent and original_price > price > 0:
        discount_percent = round((1 - price / original_price) * 100)

    store = raw_data.get("store") or source

    delivery_days = parse_delivery(
        raw_data.get("delivery_days") or raw_data.get("delivery")
    )
    delivery_label = (
        raw_data.get("delivery_label")
        or raw_data.get("deliverylabel")
        or (f"{delivery_days} day delivery" if delivery_days > 0 else "Free delivery")
    )

    # Product is reliable if it has a valid title, valid store, and price > 0.
    # Note: Unrated products (rating == 0.0) on Croma/Reliance are treated as reliable.
    is_reliable = bool(price > 0 and len(title) > 5 and (rating == 0.0 or rating >= 2.5))

    return {
        "product_name": title,
        "productname": title,
        "price_inr": price,
        "priceinr": price,
        "original_price": original_price,
        "originalprice": original_price,
        "discount_percent": int(discount_percent),
        "discountpercent": int(discount_percent),
        "store": store,
        "delivery_days": delivery_days,
        "delivery_label": delivery_label,
        "deliverylabel": delivery_label,
        "rating": rating,
        "review_count": int(raw_data.get("review_count") or raw_data.get("reviewcount") or 0),
        "reviewcount": int(raw_data.get("review_count") or raw_data.get("reviewcount") or 0),
        "image": raw_data.get("image") or raw_data.get("img") or "",
        "product_link": raw_data.get("product_link") or raw_data.get("url") or raw_data.get("link") or "",
        "productlink": raw_data.get("product_link") or raw_data.get("url") or raw_data.get("link") or "",
        "is_reliable": is_reliable,
        "isreliable": is_reliable,
        "is_best_price": bool(raw_data.get("is_best_price", False)),
        "isbestprice": bool(raw_data.get("is_best_price", False)),
        "match_score": int(raw_data.get("match_score", 0)),
        "offer": raw_data.get("offer", ""),
        "stock_status": raw_data.get("stock_status", "In Stock"),
    }


if __name__ == "__main__":
    raw_amazon_item = {
        "title": "iPhone 17 Pro",
        "price": "₹ 1,20,000",
        "delivery": "2 days",
        "rating": "4.5",
    }
    print(normalize_product_data(raw_amazon_item, "Amazon"))