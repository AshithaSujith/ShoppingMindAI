# run_pipeline.py
from scraper import scrape_amazon

# Simulating the final "search_query" from your AI Brain (Phase 1)
search_query = "iPhone 17 Pro 512GB India"

# Step 1: Scrape
# Step 2: Normalize
result = scrape_amazon(search_query)

print("--- FINAL STANDARDIZED PRODUCT DATA ---")
print(result)