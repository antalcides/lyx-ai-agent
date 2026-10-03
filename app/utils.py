"""
Utility helpers for LyX AI Agent.
- Prompt builders for each mode (create / edit / correct / translate)
- Document extraction from AI responses (strips markdown fences)
- Safe file I/O: atomic writes + timestamped backups
- OS detection
"""
import os
import re
import shutil
import platform
from datetime import datetime
from pathlib import Path
from typing import Literal

Mode = Literal["create", "edit", "correct", "translate"]

# -----------------------------------------------------------------------
# Prompt builders
# -----------------------------------------------------------------------

_SYSTEM_BASE = """\
You are LyX AI, an expert LaTeX and LyX assistant. You help users with:
1. Creating well-structured LaTeX/LyX documents from natural language descriptions.
2. Editing an EXISTING document, applying exactly the changes requested.
3. Correcting LaTeX errors, syntax issues, and compilation problems.
4. Translating documents between languages while preserving all LaTeX markup.

Rules:
- Always output valid LaTeX code when producing documents, edits or corrections.
- Wrap the COMPLETE resulting document in a single ```latex ... ``` code block.
- Be concise, precise, and professional.
- When correcting, explain briefly what was wrong before giving the fix.
- When translating, preserve ALL LaTeX commands, environments, and structure.
- Never truncate the document and never replace real content with placeholders
  such as "..." or "<!-- rest of document -->". Output every line.
"""

_CREATE_EXTRA = """\
Mode: DOCUMENT CREATION
- Produce a complete, compilable LaTeX document unless the user asks for a snippet.
- Use an appropriate document class (article, report, book, beamer, etc.).
- Include a preamble with the necessary packages.
- If a template or reference document is supplied, follow its structure,
  document class, packages and visual style closely.
- Add comments to explain non-obvious sections.
"""

_EDIT_EXTRA = """\
Mode: DOCUMENT EDITING
- The user supplies an EXISTING document plus a list of requested changes.
- Apply ONLY the requested changes. Preserve everything else exactly as it was:
  preamble, packages, custom commands, labels, citations, bibliography,
  indentation and line structure.
- Do not rewrite, "improve" or reorder content that was not mentioned.
- If a requested change is ambiguous, make the most conservative choice.
- If the document is LyX markup, keep it as LyX markup; do not convert formats.
- Output the COMPLETE updated document, ready to be saved over the original.
- Do not add commentary before or after the code block.
"""

_CORRECT_EXTRA = """\
Mode: ERROR CORRECTION
- Identify and fix all LaTeX errors in the provided code.
- List each error found with a brief explanation.
- Output the complete corrected code in a single ```latex block.
- If the input is LyX markup, treat it accordingly.
"""

_TRANSLATE_EXTRA = """
Mode: TRANSLATION
- Translate only the text content, NOT the LaTeX commands or environments.
- Preserve all LaTeX markup, labels, citations, and structure exactly.
- Target language: {target_language}
- Output the complete translated document in a single ```latex block.
"""


def build_system_prompt(mode: Mode, target_language: str = "English") -> str:
    """Construct the system prompt for a given mode."""
    extra = {
        "create": _CREATE_EXTRA,
        "edit": _EDIT_EXTRA,
        "correct": _CORRECT_EXTRA,
        "translate": _TRANSLATE_EXTRA.format(target_language=target_language),
    }.get(mode, "")
    return _SYSTEM_BASE + "\n" + extra


def build_user_message(
    mode: Mode,
    text: str,
    instruction: str = "",
    document_path: str | Path | None = None,
) -> str:
    """
    Assemble the user turn.

    For ``edit`` mode the text box holds the document and ``instruction`` holds
    the change request, so both are combined with explicit delimiters.
    Every other mode simply sends the text box contents.
    """
    text = text or ""
    instruction = (instruction or "").strip()

    if mode == "edit" and text.strip():
        name = Path(document_path).name if document_path else "document"
        header = f"Current document ({name}):"
        changes = instruction or (
            "Apply the improvements described in the document comments, "
            "fix any LaTeX problems and keep everything else unchanged."
        )
        return (
            f"{header}\n\n```latex\n{text.strip()}\n```\n\n"
            f"Requested changes:\n{changes}"
        )

    if instruction and not text.strip():
        return instruction
    if instruction:
        return f"{instruction}\n\n{text}"
    return text


# -----------------------------------------------------------------------
# Document extraction
# -----------------------------------------------------------------------

_FENCED_RE = re.compile(
    r"```[ \t]*(?:latex|tex|lyx|bibtex)?[ \t]*\r?\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_OPEN_FENCE_RE = re.compile(
    r"```[ \t]*(?:latex|tex|lyx|bibtex)?[ \t]*\r?\n",
    re.IGNORECASE,
)


def extract_document(text: str) -> str:
    """
    Pull the document out of an AI response.

    Prefers the longest fenced code block; if the stream was cut off before the
    closing fence, everything after the opening fence is used. When there is no
    fence at all the raw text is returned, so plain-code answers still work.
    """
    if not text:
        return ""

    blocks = _FENCED_RE.findall(text)
    if blocks:
        return max(blocks, key=len).strip() + "\n"

    m = _OPEN_FENCE_RE.search(text)
    if m:
        return text[m.end():].strip() + "\n"

    return text.strip() + "\n"


# -----------------------------------------------------------------------
# File I/O
# -----------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".tex", ".lyx", ".txt", ".md", ".bib", ".cls", ".sty"}

# How many timestamped backups to keep per file
MAX_BACKUPS = 10


def load_file(path: str | Path) -> tuple[bool, str]:
    """
    Load a text file. Returns (success, content_or_error_message).
    """
    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        return True, content
    except Exception as exc:
        return False, f"Could not read file: {exc}"


def save_file(path: str | Path, content: str, *, atomic: bool = True) -> tuple[bool, str]:
    """
    Save content to a file. Returns (success, error_message).

    With ``atomic=True`` the data is written to a temporary sibling and then
    moved into place, so an interrupted write can never leave a half-written
    document behind.
    """
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if atomic:
            tmp = target.with_name(target.name + ".tmp-lyxai")
            tmp.write_text(content, encoding="utf-8")
            os.replace(tmp, target)
        else:
            target.write_text(content, encoding="utf-8")
        return True, ""
    except Exception as exc:
        return False, f"Could not save file: {exc}"


def backup_file(path: str | Path, keep: int = MAX_BACKUPS) -> tuple[bool, str]:
    """
    Copy *path* to ``<name>.<YYYYmmdd-HHMMSS>.<ext>.bak`` next to it.

    Returns (success, backup_path_or_error). Non-existent files are a no-op.
    """
    src = Path(path)
    if not src.exists():
        return True, ""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = src.with_name(f"{src.stem}.{stamp}{src.suffix}.bak")
    try:
        shutil.copy2(src, bak)
    except Exception as exc:
        return False, f"Could not create backup: {exc}"

    # Prune the oldest backups for this file
    try:
        pattern = f"{src.stem}.*{src.suffix}.bak"
        old = sorted(
            src.parent.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for stale in old[keep:]:
            try:
                stale.unlink()
            except OSError:
                pass
    except Exception:
        pass

    return True, str(bak)


def file_signature(path: str | Path) -> tuple[float, int] | None:
    """Return (mtime, size) for a file, or None when it does not exist."""
    try:
        st = Path(path).stat()
        return (st.st_mtime, st.st_size)
    except OSError:
        return None


def suggest_copy_name(path: str | Path, suffix: str = "-nuevo") -> str:
    """
    Propose a non-existing sibling filename, e.g. ``informe-nuevo.tex``.
    Used when a document is opened as a template.
    """
    src = Path(path)
    candidate = src.with_name(f"{src.stem}{suffix}{src.suffix}")
    n = 2
    while candidate.exists():
        candidate = src.with_name(f"{src.stem}{suffix}-{n}{src.suffix}")
        n += 1
    return str(candidate)


def is_latex_path(path: str | Path | None) -> bool:
    return bool(path) and Path(path).suffix.lower() in {".tex", ".lyx"}


# -----------------------------------------------------------------------
# OS / environment helpers
# -----------------------------------------------------------------------

def is_windows() -> bool:
    return platform.system() == "Windows"


def is_linux() -> bool:
    return platform.system() == "Linux"


def get_assets_dir() -> Path:
    """Return the assets/ directory next to main.py."""
    return Path(__file__).parent.parent / "assets"


def get_logo_path(ext: str = ".png") -> Path:
    return get_assets_dir() / f"logo-lyx-ai{ext}"


# -----------------------------------------------------------------------
# Clipboard
# -----------------------------------------------------------------------

def copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard. Returns True on success."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.after(500, root.destroy)
        root.mainloop()
        return True
    except Exception:
        return False


# -----------------------------------------------------------------------
# Token counting (rough estimate)
# -----------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return max(1, len(text) // 4)
