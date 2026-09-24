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

from app.ai.prompts import (
    PROMPT_VERSION,
    RESUME_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_resume_prompt,
    build_user_prompt,
)
from app.ai.schemas import AnalysisResponse, AnalysisResult, ResumeSummary
from app.errors import AppError

MAX_KEY_SKILLS = 8


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


async def summarize_resume(*, api_key: str, model: str, resume_text: str) -> ResumeSummary:
    """One small call per uploaded resume; the result is all that's stored."""
    client = AsyncOpenAI(api_key=api_key)
    messages = [
        {"role": "system", "content": RESUME_SYSTEM_PROMPT},
        {"role": "user", "content": build_resume_prompt(resume_text)},
    ]
    for _ in range(2):
        try:
            completion = await client.chat.completions.parse(
                model=model, messages=messages, response_format=ResumeSummary
            )
        except OpenAIError as exc:
            raise _map_openai_error(exc, model=model) from exc
        parsed = completion.choices[0].message.parsed
        if parsed is not None and parsed.summary.strip():
            skills = [s.strip() for s in parsed.key_skills if s.strip()][:MAX_KEY_SKILLS]
            return ResumeSummary(summary=parsed.summary.strip(), key_skills=skills)
    raise AppError(
        "invalid_ai_response",
        "The AI couldn't summarize this resume. Please try again.",
        502,
    )


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
    """profiles: [{"id", "name", "summary", "skills"}, ...] — the client's active resumes that
    have an uploaded summary. The model summarizes the JD and picks the best-fitting resume
    (or none) in a single call.

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
                model=model, messages=messages, response_format=AnalysisResponse
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
            outcome = AnalysisOutcome(
                AnalysisResult.model_validate(parsed.model_dump()), tokens, latency_ms
            )
            outcome.model = model
            return outcome

        if attempts >= 2:
            raise AppError(
                "invalid_ai_response",
                "The AI returned an invalid response after a retry. Please try again.",
                502,
            )
