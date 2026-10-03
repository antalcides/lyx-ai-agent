"""
Tests for the document handling features.

Run with:
    .venv/Scripts/python.exe -m pytest tests/ -v
or, without pytest:
    .venv/Scripts/python.exe tests/test_document_ops.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import sanitize_api_key                                    # noqa: E402
from app.utils import (                                                    # noqa: E402
    backup_file,
    build_system_prompt,
    build_user_message,
    extract_document,
    file_signature,
    save_file,
    suggest_copy_name,
)


# ── extract_document ─────────────────────────────────────────────────────────
def test_extract_strips_fences_and_prose():
    response = (
        "Here is the corrected document.\n\n"
        "```latex\n"
        "\\documentclass{article}\n"
        "\\begin{document}\nHello\n\\end{document}\n"
        "```\n\n"
        "I fixed the environment."
    )
    out = extract_document(response)
    assert out.startswith("\\documentclass")
    assert out.rstrip().endswith("\\end{document}")
    assert "```" not in out
    assert "I fixed" not in out


def test_extract_picks_longest_block():
    response = "```latex\nshort\n```\ntext\n```latex\nthis is the longer block\n```"
    assert extract_document(response).strip() == "this is the longer block"


def test_extract_handles_truncated_stream():
    assert extract_document("```latex\n\\begin{document}").strip() == "\\begin{document}"


def test_extract_without_fences_returns_raw():
    assert extract_document("\\documentclass{article}") == "\\documentclass{article}\n"


def test_extract_empty():
    assert extract_document("") == ""


# ── build_user_message ───────────────────────────────────────────────────────
def test_edit_message_contains_document_and_instruction():
    msg = build_user_message("edit", "\\documentclass{article}", "change the title", "informe.tex")
    assert "informe.tex" in msg
    assert "change the title" in msg
    assert "```latex" in msg
    assert "\\documentclass{article}" in msg


def test_edit_message_defaults_instruction():
    msg = build_user_message("edit", "\\documentclass{article}", "", "informe.tex")
    assert "Requested changes:" in msg


def test_non_edit_mode_sends_text_only():
    assert build_user_message("create", "make a report", "") == "make a report"


def test_instruction_only():
    assert build_user_message("create", "", "make a report") == "make a report"


# ── build_system_prompt ──────────────────────────────────────────────────────
def test_edit_mode_prompt_mentions_preserving():
    prompt = build_system_prompt("edit")
    assert "EDITING" in prompt
    assert "preserve" in prompt.lower()


def test_translate_prompt_includes_language():
    assert "Spanish" in build_system_prompt("translate", "Spanish")


# ── sanitize_api_key ─────────────────────────────────────────────────────────
def test_sanitize_removes_common_prefixes():
    cases = [
        ("api-key: sk-or-v1-abc", "sk-or-v1-abc"),
        ("api_key=sk-abc", "sk-abc"),
        ("Bearer sk-123", "sk-123"),
        ("Authorization: Bearer sk-y", "sk-y"),
        ("  'sk-x'  ", "sk-x"),
        ("sk-z", "sk-z"),
        ("token sk-t", "sk-t"),
    ]
    for raw, expected in cases:
        assert sanitize_api_key(raw) == expected, raw


def test_sanitize_keeps_hyphenated_names():
    # A real key must never be mangled
    assert sanitize_api_key("sk-proj-abc-123") == "sk-proj-abc-123"
    assert sanitize_api_key("token-abc") == "token-abc"


def test_sanitize_handles_none():
    assert sanitize_api_key(None) == ""


# ── file safety ──────────────────────────────────────────────────────────────
def test_atomic_save_and_backup():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "informe.tex"
        ok, err = save_file(f, "v1")
        assert ok, err
        assert f.read_text(encoding="utf-8") == "v1"

        sig_before = file_signature(f)
        ok, bak = backup_file(f)
        assert ok, bak
        assert Path(bak).exists()
        assert Path(bak).read_text(encoding="utf-8") == "v1"

        ok, err = save_file(f, "v2")
        assert ok, err
        assert f.read_text(encoding="utf-8") == "v2"
        assert Path(bak).read_text(encoding="utf-8") == "v1"   # original kept
        assert file_signature(f) != sig_before

        # No leftover temp files
        assert not list(Path(d).glob("*.tmp-lyxai"))


def test_backup_of_missing_file_is_noop():
    with tempfile.TemporaryDirectory() as d:
        ok, info = backup_file(Path(d) / "nope.tex")
        assert ok and info == ""


def test_backups_are_pruned():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "doc.tex"
        save_file(f, "x")
        for i in range(6):
            backup_file(f, keep=2)
        assert len(list(Path(d).glob("doc.*.tex.bak"))) <= 2


def test_suggest_copy_name_avoids_collisions():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "informe.tex"
        f.write_text("x", encoding="utf-8")
        first = Path(suggest_copy_name(f))
        assert first.name == "informe-nuevo.tex"
        first.write_text("y", encoding="utf-8")
        second = Path(suggest_copy_name(f))
        assert second.name == "informe-nuevo-2.tex"
        assert not second.exists()


def test_file_signature_missing_file():
    assert file_signature("definitely/not/here.tex") is None


# ── manual runner (no pytest required) ───────────────────────────────────────
if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed.")
    sys.exit(1 if failed else 0)
