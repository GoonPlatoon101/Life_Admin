import json
import re
import time
from typing import Any

from openai import (
    OpenAI,
    InternalServerError,
    APIConnectionError,
    RateLimitError,
)

from config import Config

MAX_API_RETRIES = 4
RETRY_BASE_DELAY = 2.0

def create_client(config: Config) -> OpenAI:
    kwargs: dict = {
        "api_key": config.llm_api_key,
        "base_url": config.llm_base_url,
    }
    if "openrouter.ai" in config.llm_base_url:
        kwargs["default_headers"] = {"X-OpenRouter-Title": "LifeAdmin"}
    return OpenAI(**kwargs)

def complete_with_retry(client: OpenAI, *, on_retry=None, **kwargs):
    """
    Call chat.completions.create, retrying transient failures with backoff.

    Retries connection / rate-limit / 5xx errors and the raw json.JSONDecordError that a gateway
    throws when it returns a non-JSON body on overlaod.

    Real 4xx client erros are left to raise immediatrly. `on_retry(exc, attempt, delay)` is an optional hook so callers
    can print progree
    """

    last_exc: Exception | None = None
    for attempt in range (1, MAX_API_RETRIES + 1):
        try: 
            return client.chat.completions.create(**kwargs)
        except(
            APIConnectionError,
            RateLimitError,
            InternalServerError,
            json.JSONDecodeError,
        ) as exc:
            last_exc = exc
            if attempt == MAX_API_RETRIES:
                break 
            delay = RETRY_BASE_DELAY * 2 ** (attempt - 1)
            if on_retry:
                on_retry(exc, attempt, delay)
            time.sleep(delay)
        
    raise RuntimeError(
        f"LLM request failed after {MAX_API_RETRIES} attempts: {last_exc}"
    ) from last_exc


def _extract_json_object(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(cleaned[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("Expected the model to return a JSON object.")
    return parsed


def complete_json_with_retry(client: OpenAI, *, on_retry=None, **kwargs) -> dict[str, Any]:
    response = complete_with_retry(client, on_retry=on_retry, **kwargs)
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("Model returned an empty message.")
    return _extract_json_object(content)
