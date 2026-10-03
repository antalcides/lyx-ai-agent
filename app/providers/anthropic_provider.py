"""Anthropic provider — Claude models with streaming support."""
from typing import Callable
from .base import AIProvider


FALLBACK_MODELS = [
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-opus-4-8",
    "claude-sonnet-4-6",
    "claude-opus-4-5-20251101",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5-20250929",
]


class AnthropicProvider(AIProvider):
    name = "anthropic"
    display_name = "Anthropic"
    requires_api_key = True
    default_base_url = ""

    def list_models(self) -> list[str]:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            models = client.models.list()
            return [m.id for m in models.data] or FALLBACK_MODELS
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
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            full_text = ""
            with client.messages.stream(
                model=self.model,
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                for text in stream.text_stream:
                    if self._stop_requested:
                        break
                    full_text += text
                    on_token(text)
            on_done(full_text)
        except Exception as exc:
            on_error(str(exc))
