"""Abstract base class for AI providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class AIMessage:
    """A message in an AI conversation."""
    role: str      # "user" | "assistant" | "system"
    content: str   # text content OR base64 image content


@dataclass
class AIResponse:
    """Response from an AI provider."""
    content: str           # raw text response from the model
    model: str             # model identifier used
    input_tokens: int
    output_tokens: int
    provider: str          # "openai" | "anthropic"


class BaseAIProvider(ABC):
    """Abstract base for all AI providers."""

    @abstractmethod
    def complete(
        self,
        messages: list[AIMessage],
        system_prompt: str = "",
        max_tokens: int = 1000,
        temperature: float = 0.1,
    ) -> AIResponse:
        """Send messages and return a completion response."""

    @abstractmethod
    def complete_with_image(
        self,
        image_data: bytes,
        image_mime_type: str,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1000,
    ) -> AIResponse:
        """Send an image with a prompt and return a completion response."""

    @abstractmethod
    def test_connection(self) -> bool:
        """Test if the provider is reachable and API key is valid."""
