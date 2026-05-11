"""Public API for AI service."""
import time
from typing import Optional
from ai.models import AIConfig, AIRequestLog
from ai.providers.base import BaseAIProvider, AIMessage, AIResponse
from ai.providers.openai import OpenAIProvider
from ai.providers.anthropic import AnthropicProvider
from ai.exceptions import AIProviderNotConfigured, AIProviderUnavailable


def get_provider() -> BaseAIProvider:
    """
    Factory: reads AIConfig and returns the configured provider instance.

    Returns:
        BaseAIProvider: The configured provider instance

    Raises:
        AIProviderNotConfigured: If no valid config exists or API key is missing
    """
    config = AIConfig.get()

    if not config.enabled:
        raise AIProviderNotConfigured("AI service is disabled in configuration")

    provider = config.provider

    if provider == 'openai':
        api_key = config.openai_api_key.strip()
        if not api_key:
            raise AIProviderNotConfigured("OpenAI API key not configured")
        return OpenAIProvider(api_key=api_key, model=config.openai_model)

    elif provider == 'anthropic':
        api_key = config.anthropic_api_key.strip()
        if not api_key:
            raise AIProviderNotConfigured("Anthropic API key not configured")
        return AnthropicProvider(api_key=api_key, model=config.anthropic_model)

    else:
        raise AIProviderNotConfigured(f"Unknown provider: {provider}")


def complete(
    messages: list[AIMessage],
    system_prompt: str = "",
    feature: str = "general",
    max_tokens: Optional[int] = None,
) -> AIResponse:
    """
    Public completion function. Handles provider selection, logging, and error wrapping.
    Logs every call to AIRequestLog.

    Args:
        messages: List of AIMessage objects
        system_prompt: Optional system prompt
        feature: Feature identifier for logging (e.g., "receipt_recognition")
        max_tokens: Maximum tokens (uses config default if not specified)

    Returns:
        AIResponse with completion details

    Raises:
        AIProviderNotConfigured: If provider is not configured
        AIProviderUnavailable: If provider API call fails
    """
    config = AIConfig.get()

    # Use config max_tokens if not specified
    if max_tokens is None:
        max_tokens = config.max_tokens

    start_time = time.time()
    success = False
    error_message = ""
    response = None

    try:
        provider = get_provider()
        response = provider.complete(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        success = True
        return response

    except Exception as e:
        error_message = str(e)
        raise

    finally:
        # Always log the request
        duration_ms = int((time.time() - start_time) * 1000)

        AIRequestLog.objects.create(
            provider=response.provider if response else config.provider,
            model=response.model if response else "",
            feature=feature,
            input_tokens=response.input_tokens if response else 0,
            output_tokens=response.output_tokens if response else 0,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
        )


def complete_with_image(
    image_data: bytes,
    image_mime_type: str,
    prompt: str,
    system_prompt: str = "",
    feature: str = "general",
    max_tokens: Optional[int] = None,
) -> AIResponse:
    """
    Public image+prompt completion. Same logging and error handling as complete().

    Args:
        image_data: Raw image bytes
        image_mime_type: MIME type (e.g., "image/jpeg")
        prompt: Text prompt to accompany the image
        system_prompt: Optional system prompt
        feature: Feature identifier for logging (e.g., "receipt_recognition")
        max_tokens: Maximum tokens (uses config default if not specified)

    Returns:
        AIResponse with completion details

    Raises:
        AIProviderNotConfigured: If provider is not configured
        AIProviderUnavailable: If provider API call fails
    """
    config = AIConfig.get()

    # Use config max_tokens if not specified
    if max_tokens is None:
        max_tokens = config.max_tokens

    start_time = time.time()
    success = False
    error_message = ""
    response = None

    try:
        provider = get_provider()
        response = provider.complete_with_image(
            image_data=image_data,
            image_mime_type=image_mime_type,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        success = True
        return response

    except Exception as e:
        error_message = str(e)
        raise

    finally:
        # Always log the request
        duration_ms = int((time.time() - start_time) * 1000)

        AIRequestLog.objects.create(
            provider=response.provider if response else config.provider,
            model=response.model if response else "",
            feature=feature,
            input_tokens=response.input_tokens if response else 0,
            output_tokens=response.output_tokens if response else 0,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
        )
