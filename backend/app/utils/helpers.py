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
