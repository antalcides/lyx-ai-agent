"""
LyX integration tools for LyX AI Agent.

Provides cross-platform (Windows / Linux) functions to:
  - Locate the LyX and tex2lyx executables
  - Convert  .tex  ->  .lyx   (via tex2lyx)
  - Convert  .lyx  ->  .tex   (via lyx --export latex)
  - Compile  .lyx  ->  PDF    (via lyx --export pdf)
  - Open    a .lyx file in the LyX GUI

On Windows, tex2lyx (LyX 2.5, Qt6) keeps its event loop alive after the
conversion is done, so the process never exits.  The ``_run_and_poll``
helper launches the tool, waits for the output file to appear and
stabilise, then terminates the process — working around the hang.
"""
from __future__ import annotations

import os
import re
import time
import shutil
import subprocess
import platform
from pathlib import Path
from typing import Callable, Optional

# -----------------------------------------------------------------------
# Platform-specific subprocess flags
# -----------------------------------------------------------------------

# On Windows, console apps may pop up a CMD window.  This flag suppresses it.
_WIN_FLAGS = 0
if platform.system() == "Windows":
    try:
        _WIN_FLAGS = subprocess.CREATE_NO_WINDOW  # py 3.7+
    except AttributeError:
        _WIN_FLAGS = 0x08000000  # CREATE_NO_WINDOW constant


def _is_windows() -> bool:
    return platform.system() == "Windows"


# -----------------------------------------------------------------------
# Version detection
# -----------------------------------------------------------------------

_LYX_VERSION_RE = re.compile(r"(\d+)\.(\d+)")


def parse_lyx_version(version_str: str) -> tuple[int, int] | None:
    """Extract (major, minor) from a LyX version string."""
    m = _LYX_VERSION_RE.search(version_str or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def is_lyx_25_or_later(version_str: str) -> bool:
    """True when the LyX version is 2.5 or higher."""
    v = parse_lyx_version(version_str)
    return v is not None and v >= (2, 5)


# -----------------------------------------------------------------------
# Locate the LyX installation
# -----------------------------------------------------------------------

# Windows: common install locations (sorted newest-first)
_WIN_CANDIDATES = [
    r"C:\Program Files\LyX 2.5\bin",
    r"C:\Program Files (x86)\LyX 2.5\bin",
    r"C:\Program Files\LyX 2.4\bin",
    r"C:\Program Files (x86)\LyX 2.4\bin",
    r"C:\Program Files\LyX 2.3\bin",
    r"C:\Program Files (x86)\LyX 2.3\bin",
    r"C:\Program Files\LyX\bin",
    r"C:\Program Files (x86)\LyX\bin",
]

# Linux: known paths where tex2lyx / lyx may live
_LINUX_BIN_DIRS = [
    "/usr/bin",
    "/usr/local/bin",
    "/opt/lyx/bin",
    "/opt/LyX/bin",
    "/snap/bin",
]


def _probe_lyx_dir(directory: str | Path) -> Optional[Path]:
    """Return the directory if both lyx and tex2lyx exist in it, else None."""
    d = Path(directory)
    if not d.is_dir():
        return None
    if _is_windows():
        lyx = d / "LyX.exe"
        tex2lyx = d / "tex2lyx.exe"
    else:
        lyx = d / "lyx"
        tex2lyx = d / "tex2lyx"
    if lyx.is_file() and tex2lyx.is_file():
        return d
    return None


def find_lyx_bin(custom_path: str = "") -> Optional[Path]:
    """
    Locate the directory containing the LyX binaries.

    Search order:
      1. An explicit *custom_path* (the user's override).
      2. The system PATH (``shutil.which``).
      3. Known hard-coded install locations.

    Returns the directory Path, or None when LyX is not found.
    """
    # 1. Explicit override
    if custom_path:
        p = Path(custom_path)
        if p.is_file():
            probed = _probe_lyx_dir(p.parent)
            if probed:
                return probed
        elif p.is_dir():
            probed = _probe_lyx_dir(p)
            if probed:
                return probed

    # 2. PATH lookup
    lyx_name = "lyx.exe" if _is_windows() else "lyx"
    which = shutil.which(lyx_name) or shutil.which("lyx")
    if which:
        probed = _probe_lyx_dir(Path(which).parent)
        if probed:
            return probed

    # 3. Known locations
    candidates = _WIN_CANDIDATES if _is_windows() else _LINUX_BIN_DIRS
    for c in candidates:
        probed = _probe_lyx_dir(c)
        if probed:
            return probed
    return None


def get_lyx_executable(custom_path: str = "") -> Optional[Path]:
    """Full path to the LyX executable, or None."""
    d = find_lyx_bin(custom_path)
    if not d:
        return None
    name = "LyX.exe" if _is_windows() else "lyx"
    exe = d / name
    return exe if exe.is_file() else None


def get_tex2lyx_executable(custom_path: str = "") -> Optional[Path]:
    """Full path to tex2lyx, or None."""
    d = find_lyx_bin(custom_path)
    if not d:
        return None
    name = "tex2lyx.exe" if _is_windows() else "tex2lyx"
    exe = d / name
    return exe if exe.is_file() else None


def _get_lyx_sysdir(bin_dir: Path) -> Optional[Path]:
    """Return the LyX Resources directory derived from the bin directory."""
    if _is_windows():
        res = bin_dir.parent / "Resources"
        return res if res.is_dir() else None
    return None


# -----------------------------------------------------------------------
# Core runner: launch a process, poll for output, terminate
# -----------------------------------------------------------------------

def _run_and_poll(
    cmd: list[str],
    output_file: Path,
    timeout: int = 60,
    stabilise_checks: int = 2,
    stabilise_interval: float = 0.5,
) -> tuple[bool, str]:
    """
    Launch *cmd*, wait for *output_file* to appear and stop growing, then
    terminate the process.

    This works around tex2lyx (Qt6) on Windows, which keeps its event loop
    alive after the conversion is done and never exits on its own.

    Returns (success, error_message).
    """
    # Remove a stale output file so we can detect when it appears fresh.
    if output_file.exists():
        try:
            output_file.unlink()
        except OSError:
            pass

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=_WIN_FLAGS if _is_windows() else 0,
        )
    except Exception as exc:
        return False, f"Failed to launch: {exc}"

    deadline = time.monotonic() + timeout
    last_size = -1
    stable_count = 0

    while time.monotonic() < deadline:
        # Check if the process exited on its own (Linux, or some Windows builds)
        if proc.poll() is not None:
            # Process finished — give it a moment to flush, then break
            time.sleep(0.2)
            break

        # Check the output file
        if output_file.is_file():
            try:
                current_size = output_file.stat().st_size
            except OSError:
                current_size = 0
            if current_size > 0 and current_size == last_size:
                stable_count += 1
                if stable_count >= stabilise_checks:
                    # File has stopped growing — conversion is done
                    break
            else:
                stable_count = 0
                last_size = current_size

        time.sleep(stabilise_interval)

    # Terminate the process if it's still running
    if proc.poll() is None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    return True, ""


# -----------------------------------------------------------------------
# Version
# -----------------------------------------------------------------------

def get_lyx_version(custom_path: str = "") -> str:
    """
    Return the LyX version string.

    On Windows the GUI binary (LyX.exe) does not write to stdout, so we
    use ``tex2lyx -version`` which shares the same version number and
    runs as a console application.  tex2lyx -version exits cleanly,
    unlike the conversion mode.
    """
    tex2lyx = get_tex2lyx_executable(custom_path)
    if tex2lyx:
        try:
            result = subprocess.run(
                [str(tex2lyx), "-version"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                creationflags=_WIN_FLAGS if _is_windows() else 0,
            )
            out = (result.stdout + result.stderr).strip()
            if out:
                return out
        except Exception:
            pass

    exe = get_lyx_executable(custom_path)
    if not exe:
        return ""
    try:
        result = subprocess.run(
            [str(exe), "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            creationflags=_WIN_FLAGS if _is_windows() else 0,
        )
        return (result.stdout + result.stderr).strip()
    except Exception as exc:
        return f"Error: {exc}"


# -----------------------------------------------------------------------
# .tex  ->  .lyx   (tex2lyx)
# -----------------------------------------------------------------------

def tex_to_lyx(
    tex_path: str | Path,
    lyx_path: str | Path | None = None,
    custom_path: str = "",
    force: bool = True,
) -> tuple[bool, str]:
    """
    Convert a .tex file to .lyx using tex2lyx.

    Parameters
    ----------
    tex_path
        Source .tex file (must exist).
    lyx_path
        Destination .lyx file. When omitted, the same stem with .lyx
        extension is used next to the source.
    custom_path
        Optional override for the LyX bin directory.
    force
        Pass ``-f`` so tex2lyx overwrites an existing .lyx.

    Returns (success, message).
    """
    tex = Path(tex_path)
    if not tex.is_file():
        return False, f"Source file not found: {tex}"

    if lyx_path is None:
        lyx_path = tex.with_suffix(".lyx")
    lyx = Path(lyx_path)

    bin_dir = find_lyx_bin(custom_path)
    if not bin_dir:
        return False, (
            "tex2lyx was not found. Install LyX 2.5 or later and configure "
            "its path under Settings > LyX."
        )

    exe = bin_dir / ("tex2lyx.exe" if _is_windows() else "tex2lyx")
    if not exe.is_file():
        return False, f"tex2lyx not found in: {bin_dir}"

    cmd = [str(exe)]
    if force:
        cmd.append("-f")
    sysdir = _get_lyx_sysdir(bin_dir)
    if sysdir:
        cmd += ["-sysdir", str(sysdir)]
    cmd += [str(tex), str(lyx)]

    ok, err = _run_and_poll(cmd, lyx, timeout=60)
    if not ok:
        return False, err

    if not lyx.is_file() or lyx.stat().st_size == 0:
        return False, "tex2lyx completed but the .lyx file was not created."

    return True, f"Converted: {tex.name} -> {lyx.name}"


# -----------------------------------------------------------------------
# .lyx  ->  .tex   (lyx --export latex)
# -----------------------------------------------------------------------

def lyx_to_tex(
    lyx_path: str | Path,
    tex_path: str | Path | None = None,
    custom_path: str = "",
) -> tuple[bool, str]:
    """
    Export a .lyx file to .tex using ``lyx --export latex``.

    When *tex_path* is omitted, the output goes next to the source with the
    .tex extension. LyX writes the output next to the .lyx file, so when the
    destination differs from the default location, we work on a temp copy.
    """
    lyx = Path(lyx_path)
    if not lyx.is_file():
        return False, f"Source file not found: {lyx}"

    if tex_path is None:
        tex_path = lyx.with_suffix(".tex")
    tex = Path(tex_path)

    bin_dir = find_lyx_bin(custom_path)
    if not bin_dir:
        return False, (
            "LyX was not found. Install LyX 2.5 or later and configure "
            "its path under Settings > LyX."
        )
    exe = bin_dir / ("LyX.exe" if _is_windows() else "lyx")
    if not exe.is_file():
        return False, f"LyX not found in: {bin_dir}"

    use_temp = tex.resolve() != lyx.with_suffix(".tex").resolve()
    tmp_dir: Optional[Path] = None
    if use_temp:
        import tempfile
        tmp_dir = Path(tempfile.mkdtemp(prefix="lyx_export_"))
        work_file = tmp_dir / lyx.name
        shutil.copy2(lyx, work_file)
    else:
        work_file = lyx

    default_out = work_file.with_suffix(".tex")

    cmd = [str(exe)]
    sysdir = _get_lyx_sysdir(bin_dir)
    if sysdir:
        cmd += ["-sysdir", str(sysdir)]
    cmd += ["--export", "latex", str(work_file)]

    ok, err = _run_and_poll(cmd, default_out, timeout=120, stabilise_checks=3)
    if not ok:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return False, err

    if not default_out.is_file():
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return False, "LyX export failed: no output file was produced."

    # Copy to the user-chosen destination if needed
    if use_temp and tmp_dir:
        shutil.copy2(default_out, tex)
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if not tex.is_file():
        return False, "LyX export failed: output file was not written."

    return True, f"Exported: {lyx.name} -> {tex.name}"


# -----------------------------------------------------------------------
# Locate the LaTeX compiler (pdflatex / xelatex / lualatex)
# -----------------------------------------------------------------------

_LATEX_WIN_CANDIDATES = [
    r"C:\texlive\2026\bin\windows",
    r"C:\texlive\2025\bin\windows",
    r"C:\texlive\2024\bin\windows",
    r"C:\texlive\2023\bin\windows",
    r"C:\texlive\2022\bin\windows",
    r"C:\texlive\2026\bin\win32",
    r"C:\texlive\2025\bin\win32",
    r"C:\Program Files\MiKTeX\miktex\bin\x64",
    r"C:\Program Files\MiKTeX 2.9\miktex\bin\x64",
    r"C:\Program Files (x86)\MiKTeX\miktex\bin",
]


def find_latex_binary(
    name: str = "pdflatex",
    custom_latex_path: str = "",
) -> Optional[Path]:
    """
    Locate the pdflatex (or xelatex / lualatex) executable.

    Search order:
      1. *custom_latex_path* (the user's override — a directory or file path).
      2. The system PATH.
      3. Known hard-coded TeXLive / MiKTeX locations.
    """
    exe_name = name + (".exe" if _is_windows() else "")

    # 1. Explicit override
    if custom_latex_path:
        p = Path(custom_latex_path)
        if p.is_file():
            return p
        candidate = p / exe_name
        if candidate.is_file():
            return candidate

    # 2. PATH lookup
    which = shutil.which(name) or shutil.which(exe_name)
    if which:
        return Path(which)

    # 3. Known locations
    if _is_windows():
        for d in _LATEX_WIN_CANDIDATES:
            candidate = Path(d) / exe_name
            if candidate.is_file():
                return candidate
    else:
        for d in ["/usr/bin", "/usr/local/bin", "/opt/texlive/bin/x86_64-linux"]:
            candidate = Path(d) / name
            if candidate.is_file():
                return candidate

    return None


# -----------------------------------------------------------------------
# Compile .lyx  ->  PDF  (lyx --export pdf, with pdflatex fallback)
# -----------------------------------------------------------------------

def _compile_tex_with_pdflatex(
    tex_path: Path,
    pdf_path: Path,
    latex_exe: Path,
    passes: int = 2,
) -> tuple[bool, str]:
    """
    Compile a .tex file to PDF directly with pdflatex.

    Runs *passes* iterations to resolve cross-references, then moves the
    PDF to *pdf_path*.
    """
    work_dir = tex_path.parent
    base = tex_path.stem

    cmd = [
        str(latex_exe),
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={work_dir}",
        str(tex_path),
    ]

    for i in range(passes):
        try:
            result = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
                creationflags=_WIN_FLAGS if _is_windows() else 0,
                cwd=str(work_dir),
            )
        except subprocess.TimeoutExpired:
            return False, f"pdflatex timed out on pass {i+1}."
        except Exception as exc:
            return False, f"Failed to run pdflatex: {exc}"

        if result.returncode != 0:
            # Extract the first error line
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            for line in stdout.splitlines():
                if line.startswith("!"):
                    return False, f"LaTeX error: {line}"
            detail = stderr or stdout or f"exit code {result.returncode}"
            return False, f"pdflatex failed: {detail[:200]}"

    produced = work_dir / f"{base}.pdf"
    if not produced.is_file():
        return False, "pdflatex completed but no PDF was produced."

    # Move to the requested destination if different
    if produced.resolve() != pdf_path.resolve():
        shutil.copy2(produced, pdf_path)

    # Clean up aux files
    for ext in (".aux", ".log", ".toc", ".out", ".bbl", ".blg", ".fls",
                ".fdb_latexmk", ".synctex.gz"):
        aux = work_dir / f"{base}{ext}"
        try:
            aux.unlink()
        except OSError:
            pass

    return True, ""


def compile_lyx(
    lyx_path: str | Path,
    output_format: str = "pdf",
    custom_path: str = "",
    custom_latex_path: str = "",
) -> tuple[bool, str, Optional[Path]]:
    """
    Compile a .lyx file to PDF (or another format).

    Strategy:
      1. Try ``lyx --export pdf`` (works when LyX is properly configured).
      2. If that fails, fall back to: export .lyx -> .tex, then compile
         the .tex with pdflatex directly.

    Returns (success, message, output_path).
    """
    lyx = Path(lyx_path)
    if not lyx.is_file():
        return False, f"Source file not found: {lyx}", None

    bin_dir = find_lyx_bin(custom_path)
    if not bin_dir:
        return False, (
            "LyX was not found. Install LyX 2.5 or later and configure "
            "its path under Settings > LyX."
        ), None
    exe = bin_dir / ("LyX.exe" if _is_windows() else "lyx")
    if not exe.is_file():
        return False, f"LyX not found in: {bin_dir}", None

    fmt = output_format.lower()
    out_file = lyx.with_suffix(".pdf" if fmt.startswith("pdf") else f".{fmt}")

    # --- Attempt 1: lyx --export pdf ---
    cmd = [str(exe)]
    sysdir = _get_lyx_sysdir(bin_dir)
    if sysdir:
        cmd += ["-sysdir", str(sysdir)]
    cmd += ["--export", fmt, str(lyx)]

    ok, err = _run_and_poll(
        cmd, out_file, timeout=120,
        stabilise_checks=4, stabilise_interval=1.0,
    )

    if ok and out_file.is_file() and out_file.stat().st_size > 0:
        return True, f"Compiled: {lyx.name} -> {out_file.name}", out_file

    # --- Attempt 2: lyx -> tex -> pdflatex ---
    latex_exe = find_latex_binary("pdflatex", custom_latex_path)
    if not latex_exe:
        return False, (
            "Compilation failed: LyX could not export PDF directly, and "
            "pdflatex was not found. Install a LaTeX distribution (TeXLive "
            "or MiKTeX) or set the LaTeX path under Settings > LyX."
        ), None

    # Export .lyx to .tex
    tex_file = lyx.with_suffix(".tex")
    ok_exp, msg_exp = lyx_to_tex(lyx, tex_file, custom_path)
    if not ok_exp:
        return False, f"Cannot export .lyx to .tex for compilation: {msg_exp}", None

    # Compile .tex to PDF
    ok_pdf, err_pdf = _compile_tex_with_pdflatex(tex_file, out_file, latex_exe)
    if not ok_pdf:
        return False, err_pdf, None

    return True, f"Compiled: {lyx.name} -> {out_file.name} (via pdflatex)", out_file


# -----------------------------------------------------------------------
# Open in LyX GUI
# -----------------------------------------------------------------------

def open_in_lyx(
    lyx_path: str | Path,
    custom_path: str = "",
) -> tuple[bool, str]:
    """
    Launch the LyX GUI with *lyx_path* already loaded.
    """
    lyx = Path(lyx_path)
    if not lyx.is_file():
        return False, f"File not found: {lyx}"

    bin_dir = find_lyx_bin(custom_path)
    if not bin_dir:
        return False, (
            "LyX was not found. Install LyX 2.5 or later and configure "
            "its path under Settings > LyX."
        )
    exe = bin_dir / ("LyX.exe" if _is_windows() else "lyx")
    if not exe.is_file():
        return False, f"LyX not found in: {bin_dir}"

    cmd = [str(exe)]
    sysdir = _get_lyx_sysdir(bin_dir)
    if sysdir:
        cmd += ["-sysdir", str(sysdir)]
    cmd.append(str(lyx))

    try:
        if _is_windows():
            subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS,
            )
        else:
            subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except Exception as exc:
        return False, f"Failed to launch LyX: {exc}"

    return True, f"Opened in LyX: {lyx.name}"
