"""OmniRoute provider — configurable endpoint (OpenAI-compatible).

OmniRoute normally runs as a local gateway; point the base URL at your own
instance with the 🌐 URL button.
"""
from typing import Callable
from .base import AIProvider


FALLBACK_MODELS = ["auto/best-coding", "auto/best-chat", "auto/fast"]


class OmniRouteProvider(AIProvider):
    name = "omniroute"
    display_name = "OmniRoute"
    requires_api_key = True
    default_base_url = "http://localhost:20128/v1"

    def list_models(self) -> list[str]:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            models = client.models.list()
            ids = [m.id for m in models.data]
            if not ids:
                return FALLBACK_MODELS
            # Router aliases ("auto/…") first, then everything else alphabetically
            auto = sorted(i for i in ids if i.startswith("auto/"))
            rest = sorted(i for i in ids if not i.startswith("auto/"))
            return auto + rest
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
