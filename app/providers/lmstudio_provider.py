"""LM Studio provider — OpenAI-compatible local server."""
from typing import Callable
from .base import AIProvider


FALLBACK_MODELS = ["local-model", "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF"]


class LMStudioProvider(AIProvider):
    name = "lmstudio"
    display_name = "LM Studio (Local)"
    requires_api_key = False
    default_base_url = "http://localhost:1234/v1"

    def list_models(self) -> list[str]:
        try:
            from openai import OpenAI
            client = OpenAI(api_key="lm-studio", base_url=self.base_url)
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
            from openai import OpenAI
            client = OpenAI(api_key="lm-studio", base_url=self.base_url)
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
