import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .base_provider import BaseProvider

load_dotenv()


class GeminiProvider(BaseProvider):

    def __init__(self):
        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY")
        )

    def generate(
        self,
        system_prompt: str,
        user_input: str,
        temperature: float,
        max_tokens: int,
    ):

        response = self.client.models.generate_content(
            model="gemini-3.1-flash-lite",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
            contents=user_input,
        )

        return response