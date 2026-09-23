"""Single entry point for all OpenAI calls (see CLAUDE.md: "one entry point app/ai/service.py")."""

import time

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    NotFoundError,
    OpenAIError,
    RateLimitError,
)

from app.ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.ai.schemas import AnalysisResult
from app.errors import AppError


def _map_openai_error(exc: Exception, *, model: str) -> AppError:
    if isinstance(exc, AuthenticationError):
        return AppError("invalid_api_key", "That OpenAI API key was rejected", 400)
    if isinstance(exc, NotFoundError):
        return AppError("invalid_model", f"Model '{model}' is not accessible with this key", 400)
    if isinstance(exc, RateLimitError):
        return AppError("rate_limited", "OpenAI rate limit reached, try again shortly", 429)
    if isinstance(exc, APITimeoutError):
        return AppError("timeout", "Timed out reaching OpenAI", 504)
    if isinstance(exc, APIConnectionError):
        return AppError("provider_error", "Couldn't reach OpenAI", 502)
    return AppError("provider_error", "OpenAI request failed", 502)


async def test_api_key(api_key: str, model: str) -> None:
    """Raises AppError with a user-facing message on any failure; returns nothing on success."""
    client = AsyncOpenAI(api_key=api_key)
    try:
        await client.models.retrieve(model)
    except OpenAIError as exc:
        raise _map_openai_error(exc, model=model) from exc


class AnalysisOutcome:
    def __init__(self, result: AnalysisResult, tokens: int | None, latency_ms: int) -> None:
        self.result = result
        self.tokens = tokens
        self.latency_ms = latency_ms
        self.model = ""
        self.prompt_version = PROMPT_VERSION


async def analyze_job_description(
    *, api_key: str, model: str, job_description: str, profiles: list[dict]
) -> AnalysisOutcome:
    """profiles: [{"id": str, "name": str, "tech_stacks": list[str]}, ...] — the client's
    active profiles, given as compact context so the model can recommend one by id.

    Retries once on invalid JSON or an unknown recommended_profile_id (see docs/SPEC.md).
    """
    valid_ids = {p["id"] for p in profiles}
    client = AsyncOpenAI(api_key=api_key)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(job_description, profiles)},
    ]

    attempts = 0
    while True:
        attempts += 1
        started = time.monotonic()
        try:
            completion = await client.chat.completions.parse(
                model=model, messages=messages, response_format=AnalysisResult
            )
        except OpenAIError as exc:
            raise _map_openai_error(exc, model=model) from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        parsed = completion.choices[0].message.parsed
        is_valid = parsed is not None and (
            parsed.recommended_profile_id is None or parsed.recommended_profile_id in valid_ids
        )
        if is_valid:
            assert parsed is not None
            tokens = completion.usage.total_tokens if completion.usage else None
            outcome = AnalysisOutcome(parsed, tokens, latency_ms)
            outcome.model = model
            return outcome

        if attempts >= 2:
            raise AppError(
                "invalid_ai_response",
                "The AI returned an invalid response after a retry. Please try again.",
                502,
            )
