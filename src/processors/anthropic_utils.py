"""
Utilities for resilient Anthropic model selection.
"""

import os
import json
import re
from typing import Iterable, List, Tuple


DEFAULT_MODEL_CANDIDATES = [
    "claude-sonnet-4-0",
    "claude-sonnet-4-20250514",
]


def get_model_candidates(*env_vars: str) -> List[str]:
    """Build an ordered list of model candidates from env vars + defaults."""
    candidates = []

    for env_var in [*env_vars, "ANTHROPIC_MODEL"]:
        value = os.environ.get(env_var, "").strip()
        if value:
            candidates.append(value)

    candidates.extend(DEFAULT_MODEL_CANDIDATES)

    ordered_unique = []
    seen = set()
    for model in candidates:
        if model and model not in seen:
            ordered_unique.append(model)
            seen.add(model)

    return ordered_unique


def _is_missing_model_error(exc: Exception) -> bool:
    """Return True when Anthropic rejected the requested model name."""
    message = str(exc).lower()
    return "model:" in message and (
        "not_found_error" in message or "invalid_request_error" in message
    )


def create_message_with_fallback(client, model_candidates: Iterable[str], **kwargs) -> Tuple[object, str]:
    """Try candidate models until one succeeds."""
    last_error = None

    for model in model_candidates:
        try:
            response = client.messages.create(model=model, **kwargs)
            return response, model
        except Exception as exc:
            last_error = exc
            if not _is_missing_model_error(exc):
                raise
            print(f"Model unavailable: {model}")

    if last_error:
        raise last_error

    raise RuntimeError("No Anthropic model candidates configured")


def parse_json_response(text: str) -> dict:
    """Extract the first valid JSON object from a model response."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    decoder = json.JSONDecoder()

    for start in range(len(cleaned)):
        if cleaned[start] != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(cleaned[start:])
            return obj
        except json.JSONDecodeError:
            continue

    raise json.JSONDecodeError("No valid JSON object found", cleaned, 0)
