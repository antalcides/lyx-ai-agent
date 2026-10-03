"""
Tests for the LyX integration tools (lyx_tools module).

These tests cover:
  - Version parsing and comparison
  - Path detection logic (mocked where needed)
  - Command construction
  - The _run_and_poll helper (with a dummy process)

Run with:
    python -m pytest tests/ -v
or:
    python tests/test_lyx_tools.py
"""
import sys
import time
import shutil
import tempfile
import platform
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.lyx_tools import (
    parse_lyx_version,
    is_lyx_25_or_later,
    find_lyx_bin,
    find_latex_binary,
    _get_lyx_sysdir,
    _run_and_poll,
    tex_to_lyx,
    lyx_to_tex,
    compile_lyx,
    open_in_lyx,
)


# ── Version parsing ──────────────────────────────────────────────────────────

def test_parse_version_basic():
    assert parse_lyx_version("tex2lyx 2.5.1 (2026-04-12)") == (2, 5)


def test_parse_version_no_match():
    assert parse_lyx_version("no version here") is None


def test_parse_version_empty():
    assert parse_lyx_version("") is None


def test_parse_version_none():
    assert parse_lyx_version(None) is None


def test_is_2_5_true():
    assert is_lyx_25_or_later("tex2lyx 2.5.1 (2026-04-12)")


def test_is_2_5_false_for_2_3():
    assert not is_lyx_25_or_later("LyX 2.3.x")


def test_is_2_5_false_for_unknown():
    assert not is_lyx_25_or_later("")


def test_is_2_5_true_for_2_6():
    assert is_lyx_25_or_later("LyX 2.6.0")


# ── _get_lyx_sysdir ───────────────────────────────────────────────────────────

def test_get_sysdir_windows():
    if platform.system() != "Windows":
        return
    # A fake bin dir
    with tempfile.TemporaryDirectory() as d:
        bin_dir = Path(d) / "LyX 2.5" / "bin"
        res_dir = Path(d) / "LyX 2.5" / "Resources"
        bin_dir.mkdir(parents=True)
        res_dir.mkdir()
        result = _get_lyx_sysdir(bin_dir)
        assert result == res_dir


def test_get_sysdir_missing_resources():
    if platform.system() != "Windows":
        return
    with tempfile.TemporaryDirectory() as d:
        bin_dir = Path(d) / "bin"
        bin_dir.mkdir()
        result = _get_lyx_sysdir(bin_dir)
        assert result is None  # Resources dir doesn't exist


# ── find_lyx_bin with custom path ─────────────────────────────────────────────

def test_find_lyx_bin_custom_path_not_found():
    """When custom_path is invalid, and no LyX in PATH or known locations,
    find_lyx_bin returns None."""
    with patch("app.lyx_tools.shutil.which", return_value=None):
        with patch("app.lyx_tools._WIN_CANDIDATES", []):
            with patch("app.lyx_tools._LINUX_BIN_DIRS", []):
                result = find_lyx_bin("/nonexistent/path/that/does/not/exist")
    assert result is None


def test_find_latex_binary_custom_not_found():
    with patch("app.lyx_tools.shutil.which", return_value=None):
        with patch("app.lyx_tools._LATEX_WIN_CANDIDATES", []):
            result = find_latex_binary("pdflatex", "/nonexistent/path")
    assert result is None


# ── tex_to_lyx error cases ────────────────────────────────────────────────────

def test_tex_to_lyx_missing_source():
    ok, msg = tex_to_lyx("/nonexistent/file.tex")
    assert not ok
    assert "not found" in msg.lower()


def test_tex_to_lyx_no_lyx_installed():
    with tempfile.TemporaryDirectory() as d:
        tex = Path(d) / "test.tex"
        tex.write_text(r"\documentclass{article}\begin{document}Hi\end{document}",
                       encoding="utf-8")
        with patch("app.lyx_tools.shutil.which", return_value=None):
            with patch("app.lyx_tools._WIN_CANDIDATES", []):
                with patch("app.lyx_tools._LINUX_BIN_DIRS", []):
                    ok, msg = tex_to_lyx(tex, custom_path="/nonexistent")
        assert not ok
        assert "tex2lyx" in msg.lower() or "not found" in msg.lower()


# ── lyx_to_tex error cases ────────────────────────────────────────────────────

def test_lyx_to_tex_missing_source():
    ok, msg = lyx_to_tex("/nonexistent/file.lyx")
    assert not ok
    assert "not found" in msg.lower()


def test_lyx_to_tex_no_lyx_installed():
    with tempfile.TemporaryDirectory() as d:
        lyx = Path(d) / "test.lyx"
        lyx.write_text("#LyX\n", encoding="utf-8")
        ok, msg = lyx_to_tex(lyx, custom_path="/nonexistent")
        assert not ok
        assert "lyx" in msg.lower() or "not found" in msg.lower()


# ── compile_lyx error cases ────────────────────────────────────────────────────

def test_compile_lyx_missing_source():
    ok, msg, out = compile_lyx("/nonexistent/file.lyx")
    assert not ok
    assert out is None
    assert "not found" in msg.lower()


# ── open_in_lyx error cases ────────────────────────────────────────────────────

def test_open_in_lyx_missing_file():
    ok, msg = open_in_lyx("/nonexistent/file.lyx")
    assert not ok
    assert "not found" in msg.lower()


# ── _run_and_poll with a dummy process ─────────────────────────────────────────

def test_run_and_poll_file_appears():
    """_run_and_poll should detect when an output file appears and is stable."""
    with tempfile.TemporaryDirectory() as d:
        out_file = Path(d) / "output.txt"

        # Mock Popen so we can simulate a process that stays alive
        mock_proc = MagicMock()
        # Simulate: process stays alive (poll returns None), then we write the file
        call_count = [0]
        def fake_poll():
            call_count[0] += 1
            if call_count[0] > 3:
                # Write the output file
                out_file.write_text("result", encoding="utf-8")
            return None  # never exits on its own
        mock_proc.poll = fake_poll
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock(return_value=0)
        mock_proc.kill = MagicMock()

        with patch("app.lyx_tools.subprocess.Popen", return_value=mock_proc):
            ok, err = _run_and_poll(["dummy"], out_file, timeout=10,
                                    stabilise_checks=2, stabilise_interval=0.1)

        assert ok
        assert out_file.is_file()
        assert out_file.read_text() == "result"
        # Process was terminated since it never exited on its own
        mock_proc.terminate.assert_called()


def test_run_and_poll_process_exits():
    """_run_and_poll should handle a process that exits on its own."""
    with tempfile.TemporaryDirectory() as d:
        out_file = Path(d) / "output.txt"
        out_file.write_text("done", encoding="utf-8")

        mock_proc = MagicMock()
        mock_proc.poll = MagicMock(return_value=0)  # exited immediately
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock(return_value=0)

        with patch("app.lyx_tools.subprocess.Popen", return_value=mock_proc):
            ok, err = _run_and_poll(["dummy"], out_file, timeout=5,
                                    stabilise_checks=2, stabilise_interval=0.1)

        assert ok


def test_run_and_poll_timeout():
    """_run_and_poll should return (True, '') even on timeout — the caller
    checks the file existence."""
    with tempfile.TemporaryDirectory() as d:
        out_file = Path(d) / "output.txt"
        # File never appears

        mock_proc = MagicMock()
        mock_proc.poll = MagicMock(return_value=None)  # never exits
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock(return_value=0)
        mock_proc.kill = MagicMock()

        with patch("app.lyx_tools.subprocess.Popen", return_value=mock_proc):
            ok, err = _run_and_poll(["dummy"], out_file, timeout=2,
                                    stabilise_checks=2, stabilise_interval=0.1)

        # The helper returns True (it ran without error) — the caller is
        # responsible for checking if the file exists.
        assert ok
        mock_proc.terminate.assert_called()


# ── manual runner ──────────────────────────────────────────────────────────────
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
