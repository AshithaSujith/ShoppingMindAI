import os

from dotenv import load_dotenv
from openai import OpenAI

from .base_provider import BaseProvider

load_dotenv()


class DeepSeekProvider(BaseProvider):

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
        )

    def generate(
        self,
        system_prompt: str,
        user_input: str,
        temperature: float,
        max_tokens: int,
    ):
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_input,
                },
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        usage = response.usage

        print("\n========== DEEPSEEK CACHE ==========")
        print(f"Prompt Tokens     : {usage.prompt_tokens}")
        print(f"Completion Tokens : {usage.completion_tokens}")
        print(f"Total Tokens      : {usage.total_tokens}")
        print(f"Cache Hit Tokens  : {usage.prompt_cache_hit_tokens}")
        print(f"Cache Miss Tokens : {usage.prompt_cache_miss_tokens}")
        print("====================================\n")

        return response.choices[0].message.content