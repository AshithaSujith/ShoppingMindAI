from .base_provider import BaseProvider


class DeepSeekProvider(BaseProvider):

    def generate(
        self,
        system_prompt: str,
        user_input: str,
        temperature: float,
        max_tokens: int,
    ):
        raise NotImplementedError(
            "DeepSeek provider is not implemented yet."
        )