"""OpenRouter provider — access hundreds of models via a unified API."""
from typing import Callable
from .base import AIProvider


FALLBACK_MODELS = [
    "nex-agi/nex-n2.5-pro:free",
    "inclusionai/ling-3.0-flash-vl:free",
    "anthropic/claude-sonnet-5",
    "openai/gpt-5.6-luna",
    "google/gemini-3.5-flash",
    "deepseek/deepseek-v4.1-flash",
]


class OpenRouterProvider(AIProvider):
    name = "openrouter"
    display_name = "OpenRouter"
    requires_api_key = True
    default_base_url = "https://openrouter.ai/api/v1"

    def list_models(self) -> list[str]:
        try:
            import httpx
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/lyx-ai-agent",
                "X-Title": "LyX AI Agent",
            }
            resp = httpx.get(
                f"{self.base_url}/models", headers=headers, timeout=10.0
            )
            resp.raise_for_status()
            data = resp.json()
            ids = [m["id"] for m in data.get("data", [])]
            # Drop batch variants and alias duplicates that only clutter the list
            ids = [i for i in ids if not i.endswith(":batch") and not i.startswith("~")]
            return sorted(ids) or FALLBACK_MODELS
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
            from openai import OpenAI
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers={
                    "HTTP-Referer": "https://github.com/lyx-ai-agent",
                    "X-Title": "LyX AI Agent",
                },
            )
            full_text = ""
            with client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                stream=True,
            ) as stream:
                for chunk in stream:
                    if self._stop_requested:
                        break
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        full_text += delta
                        on_token(delta)
            on_done(full_text)
        except Exception as exc:
            on_error(str(exc))
