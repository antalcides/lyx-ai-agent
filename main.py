"""
LyX AI Agent — Entry point.

Usage
-----
    python main.py              Launch the GUI
    python main.py --diagnose   Test every configured provider and exit
    python main.py --version    Show version information
"""
import sys
import os

# Ensure the project root is on the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

__version__ = "1.1.0"

# module -> pip package name
REQUIRED = {
    "PIL":                    "pillow",
    "httpx":                  "httpx",
    "openai":                 "openai",
    "anthropic":              "anthropic",
    "google.generativeai":    "google-generativeai",
}


def check_dependencies() -> list[str]:
    """Return a list of missing required packages."""
    missing = []
    for module, pkg in REQUIRED.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)
    return missing


def diagnose() -> int:
    """Send a tiny request to every provider and report what works."""
    from app.config import get_config
    from app.providers import ALL_PROVIDERS, preferred_model

    cfg = get_config()
    fixed = cfg.sanitize_all_api_keys()
    if fixed:
        print(f"Cleaned up stored API keys for: {', '.join(fixed)}\n")

    print(f"{'provider':<18} {'model':<36} result")
    print("-" * 96)

    failures = 0
    for cls in ALL_PROVIDERS:
        api_key = cfg.get_api_key(cls.name)
        base_url = cfg.get_base_url(cls.name, cls.default_base_url)
        provider = cls(api_key=api_key, base_url=base_url)
        models = provider.list_models()
        model = preferred_model(cls, models)
        provider.model = model

        result = {"text": "", "error": None}
        try:
            provider.stream_chat(
                "You are a connectivity probe. Reply with the single word: OK",
                "ping",
                lambda t: result.__setitem__("text", result["text"] + t),
                lambda f: result.__setitem__("text", f or result["text"]),
                lambda e: result.__setitem__("error", e),
            )
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"

        label = cls.display_name
        if result["error"]:
            failures += 1
            detail = str(result["error"]).split("\n")[0][:46]
            print(f"{label:<18} {model:<36} FAIL  {detail}")
        else:
            reply = result["text"].strip()[:20] or "(empty)"
            print(f"{label:<18} {model:<36} OK    {reply}")

    print("-" * 96)
    print(f"{len(ALL_PROVIDERS) - failures}/{len(ALL_PROVIDERS)} providers answered.")
    return 0 if failures < len(ALL_PROVIDERS) else 1


def main():
    if "--version" in sys.argv:
        print(f"LyX AI Agent {__version__}")
        return

    missing = check_dependencies()
    if missing and "--diagnose" not in sys.argv:
        print("=" * 60)
        print("LyX AI Agent — Missing dependencies detected!")
        print("Please install them with:")
        print(f"  pip install {' '.join(missing)}")
        print("=" * 60)
        print()
        # Try to show a GUI warning
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Missing dependencies",
                f"Please install the following packages:\n\n"
                f"pip install {' '.join(missing)}\n\n"
                f"Then restart LyX AI Agent.",
            )
            root.destroy()
        except Exception:
            pass
        sys.exit(1)

    if "--diagnose" in sys.argv:
        sys.exit(diagnose())

    from app.gui import LyxAIApp
    app = LyxAIApp()
    app.run()


if __name__ == "__main__":
    main()
