import os

from .gemini_provider import GeminiProvider
from .deepseek_provider import DeepSeekProvider


def get_provider():

    provider = os.getenv("AI_PROVIDER", "gemini").lower()

    if provider == "gemini":
        return GeminiProvider()

    elif provider == "deepseek":
        return DeepSeekProvider()

    raise ValueError(f"Unsupported AI Provider: {provider}")