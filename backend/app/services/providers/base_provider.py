from abc import ABC, abstractmethod


class BaseProvider(ABC):
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_input: str,
        temperature: float,
        max_tokens: int,
    ):
        """
        Generate a response from the AI provider.
        """
        pass