"""Google Gemini provider with streaming support.

Note: this uses the `google-generativeai` SDK, which Google has deprecated in
favour of `google-genai`. It still works, but migrating is a good follow-up.
"""
from typing import Callable
from .base import AIProvider


# Used only when the live model list cannot be fetched.
FALLBACK_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
    "gemini-pro-latest",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
]

# Model families that are not useful for document writing
_EXCLUDE = (
    "embedding", "aqa", "tts", "image", "vision", "lyria",
    "learnlm", "gemma", "nano-banana", "customtools", "omni",
)


class GeminiProvider(AIProvider):
    name = "gemini"
    display_name = "Google Gemini"
    requires_api_key = True
    default_base_url = ""

    def list_models(self) -> list[str]:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            names = [
                m.name.replace("models/", "")
                for m in genai.list_models()
                if "generateContent" in m.supported_generation_methods
            ]
            chat = [n for n in names if not any(x in n.lower() for x in _EXCLUDE)]
            # Stable models first, previews afterwards
            stable = sorted((n for n in chat if "preview" not in n.lower()), reverse=True)
            preview = sorted((n for n in chat if "preview" in n.lower()), reverse=True)
            return (stable + preview) or FALLBACK_MODELS
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
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
            )
            full_text = ""
            for chunk in model.generate_content(user_message, stream=True):
                if self._stop_requested:
                    break
                token = chunk.text or ""
                if token:
                    full_text += token
                    on_token(token)
            on_done(full_text)
        except Exception as exc:
            on_error(str(exc))
