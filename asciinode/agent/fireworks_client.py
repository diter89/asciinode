import json
import os
from typing import Any, Dict, List, Mapping, Optional

import requests


DEFAULT_MODEL = "accounts/sentientfoundation/models/dobby-unhinged-llama-3-3-70b-new"
DEFAULT_URL = "https://api.fireworks.ai/inference/v1/chat/completions"


class FireworksError(RuntimeError):
    pass


def _resolve_api_key(explicit_key: Optional[str]) -> str:
    api_key = explicit_key or os.getenv("FIREWORKS_API_KEY")
    if not api_key:
        raise FireworksError(
            "Fireworks API key is missing. Provide via `api_key` argument or FIREWORKS_API_KEY env var."
        )
    return api_key


def chat_completion(
    messages: List[Mapping[str, Any]],
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.6,
    top_p: float = 1.0,
    top_k: int = 40,
    presence_penalty: float = 0.0,
    frequency_penalty: float = 0.0,
    api_key: Optional[str] = None,
    url: str = DEFAULT_URL,
    timeout: float = 30.0,
) -> Dict[str, Any]:

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "top_k": top_k,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "temperature": temperature,
        "messages": list(messages),
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_resolve_api_key(api_key)}",
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
    if response.status_code >= 400:
        raise FireworksError(
            f"Fireworks API error {response.status_code}: {response.text.strip() or 'no message'}"
        )

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise FireworksError(f"Failed to decode Fireworks response: {exc}") from exc

    return data
