"""
Configuration manager for LyX AI Agent.
Stores settings in config.json next to main.py.
"""
import json
import os
import re
from pathlib import Path
from typing import Any


CONFIG_FILE = Path(__file__).parent.parent / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "last_provider": "openai",
    "last_model": "",
    "last_mode": "create",
    "last_target_language": "English",
    "api_keys": {},          # {provider_name: api_key}
    "base_urls": {},         # {provider_name: base_url}
    "window_geometry": "1200x820",
    "font_size": 11,
    "theme": "dark",
    # Document handling
    "last_open_dir": "",     # last folder used in Open/Save dialogs
    "auto_backup": True,     # write a .bak copy before overwriting
    "confirm_overwrite": True,
}

# Prefixes users often paste along with the key itself, e.g.
# "api-key: sk-or-v1-…", "Authorization: Bearer sk-…" or "Bearer sk-…".
# Stripped on read and on save. The trailing (?::|=|\s) makes the separator
# optional, so a bare "Bearer sk-…" is handled too.
_KEY_PREFIX_RE = re.compile(
    r"^\s*(?:api[-_]?key|authorization|bearer|token)\s*(?::|=|\s)\s*",
    re.IGNORECASE,
)


def sanitize_api_key(key: str | None) -> str:
    """
    Normalise a pasted API key.

    Removes surrounding whitespace, quotes and an accidental
    ``api-key:`` / ``Bearer`` prefix — a very common copy-paste mistake that
    makes every request fail with 401.
    """
    if not key:
        return ""
    value = key.strip().strip('"').strip("'").strip()
    # May need more than one pass: "Authorization: Bearer sk-…"
    for _ in range(3):
        new = _KEY_PREFIX_RE.sub("", value).strip()
        if new == value:
            break
        value = new
    return value.replace("\n", "").replace("\r", "").strip()


class Config:
    """Simple JSON-backed configuration."""

    def __init__(self):
        self._data: dict[str, Any] = {}
        self.load()

    # ------------------------------------------------------------------
    def load(self) -> None:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self._data = {**DEFAULT_CONFIG, **loaded}
            except Exception:
                self._data = dict(DEFAULT_CONFIG)
        else:
            self._data = dict(DEFAULT_CONFIG)

    def save(self) -> None:
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            print(f"[Config] Could not save config: {exc}")

    # ------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    # ------------------------------------------------------------------
    # Shortcut helpers
    def get_api_key(self, provider: str) -> str:
        return sanitize_api_key(self._data.get("api_keys", {}).get(provider, ""))

    def set_api_key(self, provider: str, key: str) -> None:
        if "api_keys" not in self._data:
            self._data["api_keys"] = {}
        self._data["api_keys"][provider] = sanitize_api_key(key)
        self.save()

    def sanitize_all_api_keys(self) -> list[str]:
        """
        Clean every stored key in place. Returns the list of providers whose
        stored value was changed.
        """
        fixed: list[str] = []
        keys = self._data.get("api_keys", {})
        for provider, raw in list(keys.items()):
            clean = sanitize_api_key(raw)
            if clean != raw:
                keys[provider] = clean
                fixed.append(provider)
        if fixed:
            self.save()
        return fixed

    def get_base_url(self, provider: str, default: str = "") -> str:
        return self._data.get("base_urls", {}).get(provider, default) or default

    def set_base_url(self, provider: str, url: str) -> None:
        if "base_urls" not in self._data:
            self._data["base_urls"] = {}
        self._data["base_urls"][provider] = (url or "").strip().rstrip("/")
        self.save()

    @property
    def last_open_dir(self) -> str:
        return self._data.get("last_open_dir", "")

    @last_open_dir.setter
    def last_open_dir(self, value: str) -> None:
        self._data["last_open_dir"] = value
        self.save()

    @property
    def auto_backup(self) -> bool:
        return bool(self._data.get("auto_backup", True))

    @auto_backup.setter
    def auto_backup(self, value: bool) -> None:
        self._data["auto_backup"] = bool(value)
        self.save()

    @property
    def confirm_overwrite(self) -> bool:
        return bool(self._data.get("confirm_overwrite", True))

    @confirm_overwrite.setter
    def confirm_overwrite(self, value: bool) -> None:
        self._data["confirm_overwrite"] = bool(value)
        self.save()

    @property
    def last_provider(self) -> str:
        return self._data.get("last_provider", "openai")

    @last_provider.setter
    def last_provider(self, value: str) -> None:
        self._data["last_provider"] = value
        self.save()

    @property
    def last_model(self) -> str:
        return self._data.get("last_model", "")

    @last_model.setter
    def last_model(self, value: str) -> None:
        self._data["last_model"] = value
        self.save()

    @property
    def last_mode(self) -> str:
        return self._data.get("last_mode", "create")

    @last_mode.setter
    def last_mode(self, value: str) -> None:
        self._data["last_mode"] = value
        self.save()

    @property
    def last_target_language(self) -> str:
        return self._data.get("last_target_language", "English")

    @last_target_language.setter
    def last_target_language(self, value: str) -> None:
        self._data["last_target_language"] = value
        self.save()


# Singleton
_config_instance: Config | None = None


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
