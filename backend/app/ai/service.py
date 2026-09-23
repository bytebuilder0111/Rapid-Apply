"""Single entry point for all OpenAI calls (see CLAUDE.md: "one entry point app/ai/service.py").

Analysis (JD -> recommended profile) is added in Phase 6; for now this only backs the
Integrations page's "Test key" button.
"""

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)

from app.errors import AppError


async def test_api_key(api_key: str, model: str) -> None:
    """Raises AppError with a user-facing message on any failure; returns nothing on success."""
    client = AsyncOpenAI(api_key=api_key)
    try:
        await client.models.retrieve(model)
    except AuthenticationError as exc:
        raise AppError("invalid_api_key", "That OpenAI API key was rejected", 400) from exc
    except NotFoundError as exc:
        message = f"Model '{model}' is not accessible with this key"
        raise AppError("invalid_model", message, 400) from exc
    except RateLimitError as exc:
        raise AppError("rate_limited", "OpenAI rate limit reached, try again shortly", 429) from exc
    except APITimeoutError as exc:
        raise AppError("timeout", "Timed out reaching OpenAI", 504) from exc
    except APIConnectionError as exc:
        raise AppError("provider_error", "Couldn't reach OpenAI", 502) from exc
