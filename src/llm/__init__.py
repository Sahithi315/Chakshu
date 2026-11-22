"""LLM provider abstraction with automatic failover routing."""
from .base import LLMProvider, LLMResult, LLMError, RateLimitError, QuotaExhaustedError
from .base import TimeoutError as LLMTimeoutError, ServerError, AuthError, BadRequestError
from .router import LLMRouter, get_router

__all__ = [
    "LLMProvider", "LLMResult", "LLMError", "RateLimitError", "QuotaExhaustedError",
    "LLMTimeoutError", "ServerError", "AuthError", "BadRequestError",
    "LLMRouter", "get_router",
]
