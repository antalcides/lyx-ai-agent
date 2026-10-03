"""
Base class for all AI providers.
Each provider must implement list_models() and stream_chat().
"""
from abc import ABC, abstractmethod
from typing import Callable, Generator


def preferred_model(cls: type, models: list[str]) -> str:
    """
    Pick a sensible default out of a live model list.

    Providers return long, alphabetically unordered lists (OpenRouter has 400+,
    OmniRoute 600+), so blindly taking the first entry often lands on an
    unusable or paid-only model. Prefer, in order:
      1. the first entry of the provider's own FALLBACK_MODELS that is available
      2. any free model (":free")
      3. the first entry
    """
    if not models:
        return ""
    try:
        module = __import__(cls.__module__, fromlist=["FALLBACK_MODELS"])
        fallback = list(getattr(module, "FALLBACK_MODELS", []) or [])
    except Exception:
        fallback = []
    for candidate in fallback:
        if candidate in models:
            return candidate
    free = [m for m in models if m.endswith(":free")]
    if free:
        return free[0]
    return models[0]


class AIProvider(ABC):
    """Abstract base class that every AI provider must implement."""

    name: str = "base"
    display_name: str = "Base"
    requires_api_key: bool = True
    default_base_url: str = ""

    def __init__(self, api_key: str = "", base_url: str = "", model: str = ""):
        self.api_key = api_key
        self.base_url = base_url or self.default_base_url
        self.model = model
        self._stop_requested = False

    # ------------------------------------------------------------------
    @abstractmethod
    def list_models(self) -> list[str]:
        """Return a list of available model IDs for this provider."""
        ...

    @abstractmethod
    def stream_chat(
        self,
        system_prompt: str,
        user_message: str,
        on_token: Callable[[str], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        """
        Send a message and stream the response token by token.

        Parameters
        ----------
        system_prompt : str
            System/context prompt describing the task.
        user_message : str
            The user's request.
        on_token : Callable[[str], None]
            Called for each new token received.
        on_done : Callable[[str], None]
            Called when the full response is ready, with the complete text.
        on_error : Callable[[str], None]
            Called if an error occurs, with the error message.
        """
        ...

    # ------------------------------------------------------------------
    def stop(self) -> None:
        """Signal the provider to stop the current stream."""
        self._stop_requested = True

    def reset_stop(self) -> None:
        """Clear the stop flag before starting a new request."""
        self._stop_requested = False

    def validate(self) -> tuple[bool, str]:
        """
        Check if the provider is properly configured.
        Returns (ok: bool, message: str).
        """
        if self.requires_api_key and not self.api_key:
            return False, f"API key for {self.display_name} is missing."
        if not self.model:
            return False, "No model selected."
        return True, "OK"
