"""LLM router with per-provider circuit breaker and total latency budget."""
from __future__ import annotations
import logging
import os
import random
import time
from typing import Optional

from .base import (
    LLMProvider, LLMResult, LLMError, RateLimitError, QuotaExhaustedError,
    TimeoutError as LLMTimeoutError, ServerError, AuthError, BadRequestError,
)

logger = logging.getLogger(__name__)

# Defaults (overridable via env vars)
_DEFAULT_PER_PROVIDER_TIMEOUT = 6.0
_DEFAULT_TOTAL_BUDGET = 12.0
_DEFAULT_COOLDOWN = 60.0
_DEFAULT_QUOTA_COOLDOWN = 3600.0
_MAX_JITTER_RETRY_WAIT = 1.5


class _CircuitBreaker:
    """Per-provider cooldown tracker."""

    def __init__(self):
        self._cooldown_until: dict[str, float] = {}
        self._unhealthy: set[str] = set()

    def is_available(self, name: str) -> bool:
        if name in self._unhealthy:
            return False
        return time.monotonic() >= self._cooldown_until.get(name, 0.0)

    def cooldown_remaining(self, name: str) -> float:
        if name in self._unhealthy:
            return float("inf")
        remaining = self._cooldown_until.get(name, 0.0) - time.monotonic()
        return max(0.0, remaining)

    def set_cooldown(self, name: str, seconds: float):
        self._cooldown_until[name] = time.monotonic() + seconds
        logger.info("[LLMRouter] %s cooling down for %.0fs", name, seconds)

    def mark_unhealthy(self, name: str):
        self._unhealthy.add(name)
        logger.error("[LLMRouter] %s marked unhealthy (auth/bad-request error)", name)

    def reset(self, name: str):
        self._cooldown_until.pop(name, None)
        self._unhealthy.discard(name)


_circuit_breaker = _CircuitBreaker()


class LLMRouter:
    """
    Try providers in configured order with circuit-breaker per provider.

    Failover on: RateLimitError, QuotaExhaustedError, TimeoutError, ServerError.
    Stop trying a provider on: AuthError, BadRequestError (mark unhealthy + skip).
    """

    def __init__(self, providers: list[LLMProvider]):
        self.providers = providers

    def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.3,
        validator=None,
    ) -> Optional[LLMResult]:
        """Try providers in order. Returns LLMResult or None if all fail.
        If validator is provided and validator(result) is False or raises,
        the provider's output is rejected and the router fails over to the next provider.
        """
        per_timeout = float(os.environ.get("LLM_PER_PROVIDER_TIMEOUT", _DEFAULT_PER_PROVIDER_TIMEOUT))
        total_budget = float(os.environ.get("LLM_TOTAL_BUDGET", _DEFAULT_TOTAL_BUDGET))
        cooldown = float(os.environ.get("LLM_COOLDOWN_SECONDS", _DEFAULT_COOLDOWN))
        quota_cooldown = float(os.environ.get("LLM_QUOTA_COOLDOWN_SECONDS", _DEFAULT_QUOTA_COOLDOWN))

        budget_start = time.monotonic()
        last_error: Optional[Exception] = None

        for provider in self.providers:
            if time.monotonic() - budget_start >= total_budget:
                logger.warning("[LLMRouter] Total latency budget (%.0fs) exhausted", total_budget)
                break

            if not provider.is_configured():
                logger.debug("[LLMRouter] %s not configured, skipping", provider.name)
                continue

            if not _circuit_breaker.is_available(provider.name):
                remain = _circuit_breaker.cooldown_remaining(provider.name)
                logger.debug("[LLMRouter] %s in cooldown (%.0fs left), skipping", provider.name, remain)
                continue

            # Try once; if transient error, do one jittered retry
            for attempt in range(2):
                remaining_budget = total_budget - (time.monotonic() - budget_start)
                effective_timeout = min(per_timeout, remaining_budget)
                if effective_timeout <= 0:
                    break
                try:
                    result = provider.generate(
                        prompt=prompt,
                        system=system,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=effective_timeout,
                    )
                    # If validator is provided, check if output is valid
                    if validator is not None:
                        is_valid = False
                        try:
                            is_valid = bool(validator(result))
                        except Exception as val_err:
                            logger.warning("[LLMRouter] %s output failed validation: %s", provider.name, val_err)
                            is_valid = False
                        if not is_valid:
                            logger.warning("[LLMRouter] %s output rejected by validator, failing over to next provider", provider.name)
                            break  # Move to next provider

                    logger.info(
                        "[LLMRouter] %s served request (%.0fms, attempt %d)",
                        provider.name, result.latency_ms, attempt + 1,
                    )
                    return result
                except (RateLimitError, QuotaExhaustedError) as e:
                    cd = e.retry_after if e.retry_after else (
                        quota_cooldown if isinstance(e, QuotaExhaustedError) else cooldown
                    )
                    _circuit_breaker.set_cooldown(provider.name, cd)
                    last_error = e
                    break  # do NOT retry on rate-limit; move to next provider
                except (AuthError, BadRequestError) as e:
                    _circuit_breaker.mark_unhealthy(provider.name)
                    logger.error("[LLMRouter] %s auth/bad-request: %s", provider.name, e)
                    last_error = e
                    break  # skip this provider entirely
                except (LLMTimeoutError, ServerError, LLMError) as e:
                    last_error = e
                    if attempt == 0:
                        # Jittered retry
                        jitter = random.uniform(0.1, _MAX_JITTER_RETRY_WAIT)
                        logger.warning(
                            "[LLMRouter] %s transient error (%s), retry in %.1fs",
                            provider.name, type(e).__name__, jitter,
                        )
                        time.sleep(jitter)
                    # On second attempt failure, fall through to next provider
                except Exception as e:
                    last_error = e
                    logger.error("[LLMRouter] %s unexpected error: %s", provider.name, e)
                    break

        logger.warning("[LLMRouter] All providers failed. Last error: %s", last_error)
        return None

    def status(self) -> list[dict]:
        """Return per-provider health for /api/health endpoint. No keys exposed."""
        result = []
        for p in self.providers:
            remain = _circuit_breaker.cooldown_remaining(p.name)
            is_unhealthy = p.name in _circuit_breaker._unhealthy
            result.append({
                "provider": p.name,
                "configured": p.is_configured(),
                "available": p.is_configured() and _circuit_breaker.is_available(p.name),
                "cooldown_remaining_seconds": None if remain == float("inf") else round(remain, 1),
                "unhealthy": is_unhealthy,
            })
        return result


# Singleton router built from env vars
_router: Optional[LLMRouter] = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = _build_router()
    return _router


def _build_router() -> LLMRouter:
    from .anthropic_provider import AnthropicProvider
    from .gemini_provider import GeminiProvider
    from .openai_provider import OpenAIProvider

    provider_map = {
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
    }

    order_env = os.environ.get("LLM_PROVIDER_ORDER", "anthropic,gemini,openai")
    order = [name.strip().lower() for name in order_env.split(",") if name.strip()]

    providers: list[LLMProvider] = []
    for name in order:
        cls = provider_map.get(name)
        if cls:
            providers.append(cls())
        else:
            logger.warning("[LLMRouter] Unknown provider '%s' in LLM_PROVIDER_ORDER, skipping", name)

    logger.info("[LLMRouter] Built router with providers: %s", [p.name for p in providers])
    return LLMRouter(providers)
