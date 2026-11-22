"""Abstract base classes and normalized error types for LLM providers."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


class LLMError(Exception):
    """Base class for all normalized LLM errors."""
    def __init__(self, message: str, provider: str = "", retry_after: Optional[float] = None):
        super().__init__(message)
        self.provider = provider
        self.retry_after = retry_after  # seconds to wait before retrying


class RateLimitError(LLMError):
    """HTTP 429 / provider rate-limited."""
    pass


class QuotaExhaustedError(LLMError):
    """Daily / monthly quota exhausted."""
    pass


class TimeoutError(LLMError):
    """Request timed out."""
    pass


class ServerError(LLMError):
    """HTTP 5xx or provider internal error."""
    pass


class AuthError(LLMError):
    """API key invalid / unauthorized."""
    pass


class BadRequestError(LLMError):
    """Malformed request (4xx that is not auth/rate-limit)."""
    pass


@dataclass
class LLMResult:
    """Normalized response from any provider."""
    text: str
    provider: str
    model: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    extra: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base for all LLM provider implementations."""

    name: str = "abstract"

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the required API key env var is present."""
        ...

    @abstractmethod
    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024,
                 temperature: float = 0.3, timeout: float = 6.0) -> LLMResult:
        """
        Generate a completion synchronously.

        Raises:
            RateLimitError, QuotaExhaustedError, TimeoutError, ServerError,
            AuthError, BadRequestError, or LLMError for unknown errors.
        """
        ...

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name!r}, configured={self.is_configured()})"
