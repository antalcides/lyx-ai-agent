"""OpenAI provider — supports gpt-4o, gpt-4-turbo, gpt-3.5-turbo, etc."""
from typing import Callable
from .base import AIProvider


FALLBACK_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
]


class OpenAIProvider(AIProvider):
    name = "openai"
    display_name = "OpenAI"
    requires_api_key = True
    default_base_url = "https://api.openai.com/v1"

    def list_models(self) -> list[str]:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            models = client.models.list()
            chat_models = sorted(
                [m.id for m in models.data if "gpt" in m.id.lower()],
                reverse=True,
            )
            return chat_models if chat_models else FALLBACK_MODELS
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
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
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
