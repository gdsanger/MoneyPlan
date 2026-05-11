"""Anthropic provider implementation."""
import base64
from typing import Optional
from anthropic import Anthropic
from ai.providers.base import BaseAIProvider, AIMessage, AIResponse
from ai.exceptions import AIProviderUnavailable


class AnthropicProvider(BaseAIProvider):
    """
    Anthropic provider using the anthropic Python SDK.
    Supports: claude-3-5-haiku-20241022, claude-3-5-sonnet-20241022 (vision-capable)

    Image handling: base64 encoded, passed as content block with type "image"
    """

    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-20241022"):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model identifier (default: claude-3-5-haiku-20241022)
        """
        self.api_key = api_key
        self.model = model
        self.client = Anthropic(api_key=api_key)

    def complete(
        self,
        messages: list[AIMessage],
        system_prompt: str = "",
        max_tokens: int = 1000,
        temperature: float = 0.1,
    ) -> AIResponse:
        """
        Send messages and return a completion response.

        Args:
            messages: List of AIMessage objects
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Temperature for sampling

        Returns:
            AIResponse with completion details

        Raises:
            AIProviderUnavailable: If the API call fails
        """
        try:
            # Convert AIMessage objects to Anthropic format
            anthropic_messages = []
            for msg in messages:
                anthropic_messages.append({"role": msg.role, "content": msg.content})

            # Build kwargs for API call
            kwargs = {
                "model": self.model,
                "messages": anthropic_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            # Add system prompt if provided
            if system_prompt:
                kwargs["system"] = system_prompt

            # Make API call
            response = self.client.messages.create(**kwargs)

            # Extract response data
            content = response.content[0].text if response.content else ""
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            return AIResponse(
                content=content,
                model=response.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider="anthropic",
            )
        except Exception as e:
            raise AIProviderUnavailable(f"Anthropic API error: {str(e)}") from e

    def complete_with_image(
        self,
        image_data: bytes,
        image_mime_type: str,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1000,
    ) -> AIResponse:
        """
        Send an image with a prompt and return a completion response.

        Anthropic vision: {"type": "image", "source": {"type": "base64",
                           "media_type": mime, "data": b64}}

        Args:
            image_data: Raw image bytes
            image_mime_type: MIME type (e.g., "image/jpeg")
            prompt: Text prompt to accompany the image
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate

        Returns:
            AIResponse with completion details

        Raises:
            AIProviderUnavailable: If the API call fails
        """
        try:
            # Encode image as base64
            b64_image = base64.b64encode(image_data).decode('utf-8')

            # Build message with image content
            content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_mime_type,
                        "data": b64_image,
                    }
                },
                {
                    "type": "text",
                    "text": prompt,
                }
            ]

            # Build kwargs for API call
            kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": max_tokens,
            }

            # Add system prompt if provided
            if system_prompt:
                kwargs["system"] = system_prompt

            # Make API call
            response = self.client.messages.create(**kwargs)

            # Extract response data
            content_text = response.content[0].text if response.content else ""
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            return AIResponse(
                content=content_text,
                model=response.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider="anthropic",
            )
        except Exception as e:
            raise AIProviderUnavailable(f"Anthropic API error: {str(e)}") from e

    def test_connection(self) -> bool:
        """
        Test if the provider is reachable and API key is valid.

        Sends a minimal completion to verify the key works.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Send minimal request to test connection
            response = self.client.messages.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
            return True
        except Exception:
            return False
