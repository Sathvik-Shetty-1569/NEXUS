"""
Thin wrapper around the Groq API that forces structured JSON output and
validates it against a Pydantic model. Retries once on a parse/validation
failure by feeding the error back to the model.
"""

import json
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError
from groq import Groq

from app.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_RATE_LIMIT_CALLS,
    GROQ_RATE_LIMIT_PERIOD_SECONDS,
)
from app.models.rate_limiter import SlidingWindowRateLimiter

_client = Groq(api_key=GROQ_API_KEY)
_rate_limiter = SlidingWindowRateLimiter(
    max_calls=GROQ_RATE_LIMIT_CALLS,
    period_seconds=GROQ_RATE_LIMIT_PERIOD_SECONDS,
)

T = TypeVar("T", bound=BaseModel)


def call_groq_structured(
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    temperature: float = 0.4,
    max_retries: int = 1,
) -> T:
    """
    Calls Groq in JSON mode and parses the result into `schema`.
    Raises ValueError if it still fails after retries.
    """
    schema_hint = (
        f"\n\nRespond ONLY with a valid JSON object matching this schema "
        f"(no markdown fences, no preamble):\n{schema.model_json_schema()}"
    )

    messages = [
        {"role": "system", "content": system_prompt + schema_hint},
        {"role": "user", "content": user_prompt},
    ]

    last_error = None
    for attempt in range(max_retries + 1):
        _rate_limiter.acquire()  # raises GroqRateLimitError if budget exhausted
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content

        try:
            data = json.loads(raw)
            return schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            # feed the error back so the retry can self-correct
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": f"That was invalid JSON or didn't match the schema. "
                    f"Error: {e}. Return corrected JSON only.",
                }
            )

    raise ValueError(f"Groq structured output failed after retries: {last_error}")
