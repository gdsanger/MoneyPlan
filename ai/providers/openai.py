"""OpenAI provider implementation."""
import base64
from typing import Optional
from openai import OpenAI
from openai.types.chat import ChatCompletion
from ai.providers.base import BaseAIProvider, AIMessage, AIResponse
from ai.exceptions import AIProviderUnavailable


class OpenAIProvider(BaseAIProvider):
    """
    OpenAI provider using the openai Python SDK.
    Supports: gpt-4o, gpt-4o-mini (vision-capable models)

    Image handling: base64 encoded, passed as content array with type "image_url"
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model identifier (default: gpt-4o-mini)
        """
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=api_key)

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
            # Convert AIMessage objects to OpenAI format
            openai_messages = []
            if system_prompt:
                openai_messages.append({"role": "system", "content": system_prompt})

            for msg in messages:
                openai_messages.append({"role": msg.role, "content": msg.content})

            # Make API call
            response: ChatCompletion = self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # Extract response data
            choice = response.choices[0]
            content = choice.message.content or ""
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            return AIResponse(
                content=content,
                model=response.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider="openai",
                finish_reason=choice.finish_reason,
            )
        except Exception as e:
            raise AIProviderUnavailable(f"OpenAI API error: {str(e)}") from e

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

        OpenAI vision: encode image as base64 data URL
        content = [{"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                   {"type": "text", "text": prompt}]

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
            data_url = f"data:{image_mime_type};base64,{b64_image}"

            # Build messages with image content
            openai_messages = []
            if system_prompt:
                openai_messages.append({"role": "system", "content": system_prompt})

            # Image message with text
            openai_messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ]
            })

            # Make API call
            response: ChatCompletion = self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                max_tokens=max_tokens,
            )

            # Extract response data
            choice = response.choices[0]
            content = choice.message.content or ""
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            return AIResponse(
                content=content,
                model=response.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider="openai",
                finish_reason=choice.finish_reason,
            )
        except Exception as e:
            raise AIProviderUnavailable(f"OpenAI API error: {str(e)}") from e

    def test_connection(self) -> bool:
        """
        Test if the provider is reachable and API key is valid.

        Sends a minimal completion to verify the key works.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Send minimal request to test connection
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
            return True
        except Exception:
            return False
