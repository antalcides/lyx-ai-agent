"""Ollama provider — local models via Ollama's OpenAI-compatible API."""
from typing import Callable
from .base import AIProvider


FALLBACK_MODELS = [
    "qwen2.5-coder:3b",
    "deepseek-coder:latest",
    "qwen3.5:4b",
    "gemma3:4b",
    "llama3.2:3b",
    "qwen2.5-coder:1.5b",
]


class OllamaProvider(AIProvider):
    name = "ollama"
    display_name = "Ollama (Local)"
    requires_api_key = False
    default_base_url = "http://localhost:11434"

    def list_models(self) -> list[str]:
        try:
            import httpx
            url = self.base_url.rstrip("/") + "/api/tags"
            resp = httpx.get(url, timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])] or FALLBACK_MODELS
        except Exception:
            return FALLBACK_MODELS

    def stream_chat(
        self,
        system_prompt: str,
        user_message: str,
        on_token: Callable[[str], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        self.reset_stop()
        try:
            import httpx
            import json
            url = self.base_url.rstrip("/") + "/api/chat"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "stream": True,
            }
            full_text = ""
            with httpx.stream("POST", url, json=payload, timeout=120.0) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if self._stop_requested:
                        break
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            full_text += token
                            on_token(token)
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
            on_done(full_text)
        except Exception as exc:
            on_error(str(exc))
