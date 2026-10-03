"""Provider registry — maps provider names to classes."""
from .base import AIProvider, preferred_model
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider
from .lmstudio_provider import LMStudioProvider
from .openrouter_provider import OpenRouterProvider
from .omniroute_provider import OmniRouteProvider

# Ordered list used to populate the provider dropdown
ALL_PROVIDERS = [
    OpenAIProvider,
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    LMStudioProvider,
    OpenRouterProvider,
    OmniRouteProvider,
]

PROVIDER_MAP: dict[str, type] = {p.name: p for p in ALL_PROVIDERS}
PROVIDER_DISPLAY_NAMES: dict[str, str] = {p.name: p.display_name for p in ALL_PROVIDERS}

__all__ = [
    "ALL_PROVIDERS",
    "PROVIDER_MAP",
    "PROVIDER_DISPLAY_NAMES",
    "AIProvider",
    "preferred_model",
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "OllamaProvider",
    "LMStudioProvider",
    "OpenRouterProvider",
    "OmniRouteProvider",
]
