# normalizer.py

def normalize_product_data(raw_data, source):
    # Rating-ine string-il ninnu float-ilekk convert cheyyuka
    rating_str = raw_data.get("rating", "0")
    # Rating '4.5' ennu string-il aanu, athine float aakkuka
    try:
        rating = float(str(rating_str)) 
    except ValueError:
        rating = 0.0

    normalized = {
        "product_name": raw_data.get("title") or "Unknown Product",
        "price_inr": convert_to_float(raw_data.get("price")),
        "store": source,
        "delivery_days": parse_delivery(raw_data.get("delivery")),
        "rating": rating,
        "is_reliable": rating > 4.0 
    }
    return normalized
def convert_to_float(price_str):
    if not price_str: return 0.0
    # Removes currency symbols and commas: "₹ 1,20,000" -> 120000.0
    clean_price = ''.join(c for c in str(price_str) if c.isdigit() or c == '.')
    return float(clean_price)

def parse_delivery(delivery_str):
    # Logic to extract numbers: "Delivered in 2 days" -> 2
    if not delivery_str: return 7 # Default to 7 days
    words = str(delivery_str).split()
    for word in words:
        if word.isdigit(): return int(word)
    return 7

# Example Test
raw_amazon_item = {"title": "iPhone 17 Pro", "price": "₹ 1,20,000", "delivery": "2 days", "rating": "4.5"}
print(normalize_product_data(raw_amazon_item, "Amazon"))