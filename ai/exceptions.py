"""Custom exceptions for AI service."""


class AIServiceError(Exception):
    """Base exception for all AI service errors."""


class AIProviderNotConfigured(AIServiceError):
    """Raised when no provider is configured or API key is missing."""


class AIProviderUnavailable(AIServiceError):
    """Raised when the provider API is unreachable or returns an error."""


class AIResponseParseError(AIServiceError):
    """Raised when the AI response cannot be parsed into expected structure."""
