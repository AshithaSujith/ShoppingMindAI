import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Read your existing prompt.txt
with open("prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


def create_context_cache():
    print("Creating Gemini Context Cache...")

    cache = client.caches.create(
        model="gemini-3.1-flash-lite",
        config=types.CreateCachedContentConfig(
            display_name="shoppingmind-system-prompt",
            system_instruction=SYSTEM_PROMPT,
            ttl="3600s",  # Cache valid for 1 hour
        ),
    )

    print("✅ Cache created successfully!")
    print(f"Cache Name : {cache.name}")

    return cache.name


if __name__ == "__main__":
    create_context_cache()
