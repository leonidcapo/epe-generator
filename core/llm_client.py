from __future__ import annotations

import threading

import requests as _requests


class FakeLLMClient:
    """Deterministic stub. No network. Set fail=True to simulate an API error."""

    def __init__(self, responses: list[str] | None = None, default: str = "{}", fail: bool = False):
        self._responses = list(responses or [])
        self._default = default
        self._fail = fail
        self._idx = 0
        self._lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def call(self, system: str, user: str) -> str:
        with self._lock:
            self.calls.append((system, user))
            if self._fail:
                raise RuntimeError("LLM simulated failure")
            if not self._responses:
                return self._default
            resp = self._responses[self._idx % len(self._responses)]
            self._idx += 1
            return resp


class DeepSeekClient:
    """Cliente para la API de DeepSeek (Chat Completions, compatible con OpenAI)."""

    def __init__(self, api_key: str, model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com", max_tokens: int = 2048,
                 temperature: float = 0.4):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._max_tokens = max_tokens
        self._temperature = temperature

    def call(self, system: str, user: str) -> str:
        resp = _requests.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}",
                     "Content-Type": "application/json"},
            json={
                "model": self._model,
                "max_tokens": self._max_tokens,
                "temperature": self._temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def make_client(env: dict):
    provider = env.get("LLM_PROVIDER", "deepseek").lower()
    if provider == "deepseek":
        api_key = env.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("Falta DEEPSEEK_API_KEY en el entorno (.env)")
        return DeepSeekClient(api_key=api_key)
    raise ValueError(f"LLM_PROVIDER no soportado: {provider} (usa deepseek)")
