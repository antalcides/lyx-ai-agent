"""
LyX AI Agent — Main GUI
Dark-themed Tkinter interface with streaming AI responses.
"""
import sys
import os
import threading
import queue
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as tkfont

from .config import get_config
from .providers import ALL_PROVIDERS, PROVIDER_MAP, PROVIDER_DISPLAY_NAMES, preferred_model
from .utils import (
    build_system_prompt,
    build_user_message,
    extract_document,
    load_file,
    save_file,
    backup_file,
    file_signature,
    suggest_copy_name,
    estimate_tokens,
    get_logo_path,
    is_windows,
)

# ── Color palette ─────────────────────────────────────────────────────────────
BG_DEEP     = "#0d1117"
BG_SURFACE  = "#161b22"
BG_CARD     = "#1c2128"
BG_INPUT    = "#0f1419"
BORDER      = "#30363d"
BORDER_LIGHT= "#3d444d"

ACCENT_CYAN  = "#00d4ff"
ACCENT_BLUE  = "#1f6feb"
ACCENT_PURPLE= "#7c3aed"
ACCENT_GREEN = "#3fb950"
ACCENT_RED   = "#f85149"
ACCENT_AMBER = "#d29922"

TEXT_PRIMARY = "#e6edf3"
TEXT_DIM     = "#8b949e"
TEXT_MUTED   = "#484f58"

MODE_COLORS = {
    "create":    "#3fb950",
    "edit":      "#a371f7",
    "correct":   "#d29922",
    "translate": "#00d4ff",
}
MODE_LABELS = {
    "create":    "📝  Create Document",
    "edit":      "✏️  Edit Document",
    "correct":   "🔧  Correct Errors",
    "translate": "🌐  Translate",
}

# Prompt shown in the one-line instruction field, per mode
INSTRUCTION_HINTS = {
    "create":    "Optional: describe what to build (the box below is extra context)",
    "edit":      "What should I change in this document?  e.g. «change the title and add a section on results»",
    "correct":   "Optional: extra notes about the errors",
    "translate": "",
}

LANGUAGES = [
    "English", "Spanish", "French", "German", "Portuguese",
    "Italian", "Dutch", "Russian", "Chinese (Simplified)",
    "Chinese (Traditional)", "Japanese", "Korean", "Arabic",
    "Polish", "Swedish", "Turkish",
]

# ── LaTeX syntax highlight tags ───────────────────────────────────────────────
LATEX_TAGS = {
    "cmd":     {"foreground": "#79c0ff"},   # \commands
    "env":     {"foreground": "#7ee787"},   # {environments}
    "math":    {"foreground": "#ffa657"},   # $math$ / \[...\]
    "comment": {"foreground": "#8b949e", "font_style": "italic"},
    "bracket": {"foreground": "#e6edf3"},
}

import re

LATEX_PATTERNS = [
    ("math",    re.compile(r"\$[^$\n]*\$|\\\[.*?\\\]", re.DOTALL)),
    ("cmd",     re.compile(r"\\[a-zA-Z@]+")),
    ("comment", re.compile(r"%.*?$", re.MULTILINE)),
    ("env",     re.compile(r"\{[^{}\n]*\}")),
]


# ══════════════════════════════════════════════════════════════════════════════
class LyxAIApp:
    """Main application window."""

    def __init__(self):
        self.cfg = get_config()
        self.root = tk.Tk()
        self._setup_root()
        self._load_fonts()
        self._build_styles()
        self._build_ui()
        self._token_queue: queue.Queue = queue.Queue()
        self._current_provider = None
        self._response_buffer = ""
        self._total_tokens = 0

        # ── Document state ────────────────────────────────────────────────
        # Path the response will be written back to (None = unsaved document).
        self._doc_path: Path | None = None
        # Original file the document was derived from, when used as a template.
        self._template_path: Path | None = None
        # (mtime, size) of the file on disk when it was loaded, used to detect
        # external modifications before overwriting.
        self._doc_signature = None
        # Text currently held in the input box for the open document.
        self._doc_loaded_text = ""

        # Restore last session
        self._restore_session()
        self._start_queue_pump()
        self._refresh_doc_bar()

    # ── Window setup ──────────────────────────────────────────────────────────
    def _setup_root(self):
        self.root.title("LyX AI Agent")
        self.root.configure(bg=BG_DEEP)
        geom = self.cfg.get("window_geometry", "1280x860")
        self.root.geometry(geom)
        self.root.minsize(900, 640)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # App icon
        try:
            ico = get_logo_path(".ico")
            png = get_logo_path(".png")
            if is_windows() and ico.exists():
                self.root.iconbitmap(str(ico))
            elif png.exists():
                img = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, img)
        except Exception:
            pass

    def _load_fonts(self):
        self.font_ui    = tkfont.Font(family="Segoe UI", size=10)
        self.font_mono  = tkfont.Font(family="Consolas", size=11)
        self.font_title = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        self.font_small = tkfont.Font(family="Segoe UI", size=9)
        self.font_btn   = tkfont.Font(family="Segoe UI", size=10, weight="bold")

    # ── ttk Styles ────────────────────────────────────────────────────────────
    def _build_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")

        # --- Frames ---
        style.configure("Dark.TFrame", background=BG_DEEP)
        style.configure("Card.TFrame", background=BG_CARD, relief="flat")
        style.configure("Surface.TFrame", background=BG_SURFACE)

        # --- Labels ---
        style.configure("Dark.TLabel",
                         background=BG_DEEP, foreground=TEXT_PRIMARY,
                         font=self.font_ui)
        style.configure("Dim.TLabel",
                         background=BG_DEEP, foreground=TEXT_DIM,
                         font=self.font_small)
        style.configure("Card.TLabel",
                         background=BG_CARD, foreground=TEXT_PRIMARY,
                         font=self.font_ui)
        style.configure("Title.TLabel",
                         background=BG_DEEP, foreground=ACCENT_CYAN,
                         font=self.font_title)

        # --- Combobox ---
        style.configure("Dark.TCombobox",
                         fieldbackground=BG_INPUT, background=BG_CARD,
                         foreground=TEXT_PRIMARY, selectbackground=ACCENT_BLUE,
                         bordercolor=BORDER, arrowcolor=ACCENT_CYAN,
                         padding=5)
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly", BG_INPUT)],
                  foreground=[("readonly", TEXT_PRIMARY)])

        # --- Separator ---
        style.configure("Dark.TSeparator", background=BORDER)

        # --- Scrollbar ---
        style.configure("Dark.Vertical.TScrollbar",
                         background=BG_CARD, troughcolor=BG_SURFACE,
                         arrowcolor=TEXT_DIM, bordercolor=BORDER)

        # --- Progressbar ---
        style.configure("Cyan.Horizontal.TProgressbar",
                         troughcolor=BG_SURFACE, background=ACCENT_CYAN,
                         bordercolor=BG_DEEP)

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Main container
        main = tk.Frame(self.root, bg=BG_DEEP)
        main.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(5, weight=1)   # input row expands
        main.rowconfigure(7, weight=2)   # output row expands more

        self._build_header(main, row=0)
        self._build_provider_row(main, row=1)
        self._build_mode_row(main, row=2)
        self._build_doc_bar(main, row=3)
        self._build_instruction_row(main, row=4)
        self._build_input_section(main, row=5)
        self._build_action_row(main, row=6)
        self._build_output_section(main, row=7)
        self._build_status_bar(main, row=8)

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self, parent, row):
        hdr = tk.Frame(parent, bg=BG_SURFACE, height=62)
        hdr.grid(row=row, column=0, sticky="ew", padx=0, pady=0)
        hdr.columnconfigure(1, weight=1)
        hdr.grid_propagate(False)

        # Logo
        try:
            from PIL import Image, ImageTk
            img = Image.open(get_logo_path(".png")).resize((46, 46), Image.LANCZOS)
            self._logo_img = ImageTk.PhotoImage(img)
            tk.Label(hdr, image=self._logo_img, bg=BG_SURFACE).grid(
                row=0, column=0, padx=(14, 8), pady=8, sticky="w")
        except Exception:
            tk.Label(hdr, text="🤖", font=("Segoe UI Emoji", 22),
                     bg=BG_SURFACE, fg=ACCENT_CYAN).grid(
                row=0, column=0, padx=(14, 8), pady=8, sticky="w")

        # Title
        title_frame = tk.Frame(hdr, bg=BG_SURFACE)
        title_frame.grid(row=0, column=1, sticky="w", pady=8)
        tk.Label(title_frame, text="LyX AI Agent",
                 font=self.font_title, bg=BG_SURFACE, fg=ACCENT_CYAN).pack(anchor="w")
        tk.Label(title_frame,
                 text="LaTeX / LyX document assistant  ·  Create · Edit · Correct · Translate",
                 font=self.font_small, bg=BG_SURFACE, fg=TEXT_DIM).pack(anchor="w")

        # Config button
        cfg_btn = self._make_btn(hdr, "⚙  Settings", self._open_settings,
                                 bg=BG_CARD, fg=TEXT_DIM, width=11)
        cfg_btn.grid(row=0, column=2, padx=14, pady=12, sticky="e")

        # Horizontal line
        tk.Frame(parent, bg=ACCENT_CYAN, height=2).grid(
            row=row, column=0, sticky="sew")

    # ── Provider row ──────────────────────────────────────────────────────────
    def _build_provider_row(self, parent, row):
        frame = tk.Frame(parent, bg=BG_SURFACE, pady=0)
        frame.grid(row=row, column=0, sticky="ew", padx=0, pady=0)
        frame.columnconfigure(3, weight=1)

        tk.Label(frame, text="Provider:", bg=BG_SURFACE, fg=TEXT_DIM,
                 font=self.font_small).grid(row=0, column=0, padx=(16, 4), pady=10)

        # Provider dropdown
        provider_names = [p.display_name for p in ALL_PROVIDERS]
        self.provider_var = tk.StringVar()
        self.provider_cb = ttk.Combobox(
            frame, textvariable=self.provider_var,
            values=provider_names, state="readonly",
            style="Dark.TCombobox", width=18)
        self.provider_cb.grid(row=0, column=1, padx=(0, 18), pady=10)
        self.provider_cb.bind("<<ComboboxSelected>>", self._on_provider_change)

        tk.Label(frame, text="Model:", bg=BG_SURFACE, fg=TEXT_DIM,
                 font=self.font_small).grid(row=0, column=2, padx=(0, 4), pady=10)

        # Model dropdown
        self.model_var = tk.StringVar()
        self.model_cb = ttk.Combobox(
            frame, textvariable=self.model_var,
            values=[], state="readonly",
            style="Dark.TCombobox", width=30)
        self.model_cb.grid(row=0, column=3, padx=(0, 18), pady=10, sticky="w")
        self.model_cb.bind("<<ComboboxSelected>>", self._on_model_change)

        # Refresh models button
        self.refresh_btn = self._make_btn(
            frame, "↻", self._refresh_models,
            bg=BG_CARD, fg=ACCENT_CYAN, width=3,
            tooltip="Refresh model list from server")
        self.refresh_btn.grid(row=0, column=4, padx=(0, 8), pady=10)

        # Connection test button
        self.test_btn = self._make_btn(
            frame, "🧪  Test", self._test_connection,
            bg=BG_CARD, fg=ACCENT_GREEN, width=9,
            tooltip="Send a 1-token request to check the provider really answers")
        self.test_btn.grid(row=0, column=5, padx=(0, 8), pady=10)

        # API Key button
        self.key_btn = self._make_btn(
            frame, "🔑  API Key", self._edit_api_key,
            bg=BG_CARD, fg=ACCENT_AMBER, width=10)
        self.key_btn.grid(row=0, column=6, padx=(0, 8), pady=10)

        # Base URL button (for local providers)
        self.url_btn = self._make_btn(
            frame, "🌐  URL", self._edit_base_url,
            bg=BG_CARD, fg=TEXT_DIM, width=8)
        self.url_btn.grid(row=0, column=7, padx=(0, 16), pady=10)

        tk.Frame(parent, bg=BORDER, height=1).grid(
            row=row, column=0, sticky="sew")

    # ── Mode row ──────────────────────────────────────────────────────────────
    def _build_mode_row(self, parent, row):
        frame = tk.Frame(parent, bg=BG_DEEP, pady=0)
        frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(10, 6))

        self.mode_var = tk.StringVar(value="create")
        self._mode_buttons: dict[str, tk.Button] = {}

        for mode, label in MODE_LABELS.items():
            color = MODE_COLORS[mode]
            btn = tk.Button(
                frame, text=label,
                font=self.font_btn,
                bg=BG_CARD, fg=TEXT_DIM,
                activebackground=color, activeforeground=BG_DEEP,
                relief="flat", cursor="hand2",
                padx=20, pady=8,
                bd=0,
                command=lambda m=mode: self._set_mode(m),
            )
            btn.pack(side="left", padx=(0, 8))
            self._mode_buttons[mode] = btn

        # Language selector (only visible in translate mode)
        self._lang_frame = tk.Frame(frame, bg=BG_DEEP)
        self._lang_frame.pack(side="left", padx=(16, 0))
        tk.Label(self._lang_frame, text="→ Target:", bg=BG_DEEP,
                 fg=TEXT_DIM, font=self.font_small).pack(side="left")
        self.lang_var = tk.StringVar(value=self.cfg.last_target_language)
        self.lang_cb = ttk.Combobox(
            self._lang_frame, textvariable=self.lang_var,
            values=LANGUAGES, state="readonly",
            style="Dark.TCombobox", width=16)
        self.lang_cb.pack(side="left", padx=(4, 0))
        self.lang_cb.bind("<<ComboboxSelected>>", self._on_lang_change)
        self._lang_frame.pack_forget()

    # ── Document bar (open / template / save) ─────────────────────────────────
    def _build_doc_bar(self, parent, row):
        frame = tk.Frame(parent, bg=BG_SURFACE)
        frame.grid(row=row, column=0, sticky="ew", padx=0, pady=0)
        frame.columnconfigure(1, weight=1)

        tk.Label(frame, text="📄", bg=BG_SURFACE, fg=ACCENT_CYAN,
                 font=self.font_small).grid(row=0, column=0, padx=(16, 4), pady=7)

        self.doc_label = tk.Label(
            frame, text="No document open", bg=BG_SURFACE, fg=TEXT_MUTED,
            font=self.font_small, anchor="w")
        self.doc_label.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=7)

        self.open_btn = self._make_btn(
            frame, "📂  Open", self._open_document,
            bg=BG_CARD, fg=TEXT_PRIMARY, width=10,
            tooltip="Open a .tex / .lyx file to edit it in place")
        self.open_btn.grid(row=0, column=2, padx=(0, 6), pady=6)

        self.tpl_btn = self._make_btn(
            frame, "📑  Use as template", self._use_as_template,
            bg=BG_CARD, fg=ACCENT_PURPLE, width=19,
            tooltip="Start a new document from an existing one — the original is never touched")
        self.tpl_btn.grid(row=0, column=3, padx=(0, 6), pady=6)

        self.save_btn = self._make_btn(
            frame, "💾  Save", self._save_result,
            bg=BG_CARD, fg=ACCENT_GREEN, width=10,
            tooltip="Write the result back to the open document (a .bak copy is kept)")
        self.save_btn.grid(row=0, column=4, padx=(0, 6), pady=6)

        self.saveas_btn = self._make_btn(
            frame, "💾  Save as…", self._save_result_as,
            bg=BG_CARD, fg=TEXT_DIM, width=13)
        self.saveas_btn.grid(row=0, column=5, padx=(0, 6), pady=6)

        self.revert_btn = self._make_btn(
            frame, "↩  Reload", self._reload_document,
            bg=BG_CARD, fg=TEXT_DIM, width=10,
            tooltip="Discard local edits and reload the file from disk")
        self.revert_btn.grid(row=0, column=6, padx=(0, 6), pady=6)

        self.close_btn = self._make_btn(
            frame, "✕", self._close_document,
            bg=BG_CARD, fg=ACCENT_RED, width=3,
            tooltip="Close the document (nothing is deleted from disk)")
        self.close_btn.grid(row=0, column=7, padx=(0, 16), pady=6)

        tk.Frame(parent, bg=BORDER, height=1).grid(row=row, column=0, sticky="sew")

    # ── Instruction row ───────────────────────────────────────────────────────
    def _build_instruction_row(self, parent, row):
        self._instr_row = tk.Frame(parent, bg=BG_DEEP)
        self._instr_row.grid(row=row, column=0, sticky="ew", padx=16, pady=(10, 0))
        self._instr_row.columnconfigure(1, weight=1)

        tk.Label(self._instr_row, text="Instruction:", bg=BG_DEEP, fg=ACCENT_PURPLE,
                 font=self.font_small).grid(row=0, column=0, sticky="w", padx=(0, 6))

        self.instruction_var = tk.StringVar()
        self.instruction_entry = tk.Entry(
            self._instr_row, textvariable=self.instruction_var,
            bg=BG_INPUT, fg=TEXT_PRIMARY, insertbackground=ACCENT_CYAN,
            relief="flat", font=self.font_ui, bd=1)
        self.instruction_entry.grid(row=0, column=1, sticky="ew", ipady=5)

        self.instr_hint = tk.Label(
            self._instr_row, text="", bg=BG_DEEP, fg=TEXT_MUTED,
            font=self.font_small, anchor="w")
        self.instr_hint.grid(row=1, column=1, sticky="ew", pady=(2, 0))

        self._instr_row_visible = True
        self._apply_instruction_visibility()

    def _apply_instruction_visibility(self):
        """Show the instruction field for create/edit/correct, hide for translate."""
        mode = self.mode_var.get() if hasattr(self, "mode_var") else "create"
        hint = INSTRUCTION_HINTS.get(mode, "")
        if hint:
            if not self._instr_row_visible:
                self._instr_row.grid()
                self._instr_row_visible = True
            self.instr_hint.configure(text=hint)
        else:
            self._instr_row.grid_remove()
            self._instr_row_visible = False

    # ── Input section ─────────────────────────────────────────────────────────
    def _build_input_section(self, parent, row):
        frame = tk.Frame(parent, bg=BG_DEEP)
        frame.grid(row=row, column=0, sticky="nsew", padx=16, pady=(4, 0))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        # Label row
        lbl_frame = tk.Frame(frame, bg=BG_DEEP)
        lbl_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.input_label_var = tk.StringVar(value="Your request / LaTeX code:")
        tk.Label(lbl_frame, textvariable=self.input_label_var,
                 bg=BG_DEEP, fg=TEXT_DIM, font=self.font_small).pack(side="left")
        # Insert the contents of a file without binding it as the open document
        self._make_btn(lbl_frame, "📎  Insert file", self._insert_file,
                       bg=BG_CARD, fg=TEXT_DIM, width=13,
                       tooltip="Paste a file's contents into the box (not tracked as the open document)"
                       ).pack(side="right", padx=(4, 0))
        self._make_btn(lbl_frame, "🗑  Clear", self._clear_input,
                       bg=BG_CARD, fg=ACCENT_RED, width=8).pack(side="right")

        # Text area
        txt_frame = tk.Frame(frame, bg=BORDER, bd=1)
        txt_frame.grid(row=1, column=0, sticky="nsew")
        txt_frame.columnconfigure(0, weight=1)
        txt_frame.rowconfigure(0, weight=1)

        self.input_text = tk.Text(
            txt_frame,
            bg=BG_INPUT, fg=TEXT_PRIMARY,
            insertbackground=ACCENT_CYAN,
            selectbackground=ACCENT_BLUE,
            font=self.font_mono,
            wrap="word",
            relief="flat", bd=0,
            padx=12, pady=10,
            undo=True,
        )
        self.input_text.grid(row=0, column=0, sticky="nsew")

        vsb = tk.Scrollbar(txt_frame, orient="vertical",
                           command=self.input_text.yview,
                           bg=BG_CARD, troughcolor=BG_SURFACE,
                           activebackground=ACCENT_CYAN)
        vsb.grid(row=0, column=1, sticky="ns")
        self.input_text.configure(yscrollcommand=vsb.set)

        # Placeholder text
        self._set_placeholder()

    def _set_placeholder(self):
        placeholder = (
            "Describe the document you want to create, paste LaTeX code to correct,\n"
            "or paste text/LaTeX to translate…"
        )
        self.input_text.insert("1.0", placeholder)
        self.input_text.configure(fg=TEXT_MUTED)
        self.input_text.bind("<FocusIn>", self._clear_placeholder)
        self.input_text.bind("<FocusOut>", self._restore_placeholder)
        self._placeholder_active = True

    def _clear_placeholder(self, event=None):
        if self._placeholder_active:
            self.input_text.delete("1.0", "end")
            self.input_text.configure(fg=TEXT_PRIMARY)
            self._placeholder_active = False

    def _restore_placeholder(self, event=None):
        if not self.input_text.get("1.0", "end").strip():
            self._set_placeholder()

    # ── Action row ────────────────────────────────────────────────────────────
    def _build_action_row(self, parent, row):
        frame = tk.Frame(parent, bg=BG_DEEP)
        frame.grid(row=row, column=0, sticky="ew", padx=16, pady=10)

        # Send button (prominent)
        self.send_btn = tk.Button(
            frame,
            text="▶   Send to AI",
            font=self.font_btn,
            bg=ACCENT_CYAN, fg=BG_DEEP,
            activebackground="#00b8d9", activeforeground=BG_DEEP,
            relief="flat", cursor="hand2",
            padx=28, pady=10,
            bd=0,
            command=self._send,
        )
        self.send_btn.pack(side="left", padx=(0, 8))

        # Stop button
        self.stop_btn = tk.Button(
            frame,
            text="⏹  Stop",
            font=self.font_btn,
            bg=BG_CARD, fg=ACCENT_RED,
            activebackground="#3d1a19", activeforeground=ACCENT_RED,
            relief="flat", cursor="hand2",
            padx=16, pady=10, bd=0,
            state="disabled",
            command=self._stop,
        )
        self.stop_btn.pack(side="left", padx=(0, 8))

        # Copy result button
        self._make_btn(frame, "📋  Copy result", self._copy_result,
                       bg=BG_CARD, fg=TEXT_DIM, width=14).pack(side="left", padx=(0, 8))

        # Save result button
        self._make_btn(frame, "💾  Save .tex", self._save_result,
                       bg=BG_CARD, fg=ACCENT_GREEN, width=12).pack(side="left")

        # Progress bar (right side)
        pb_frame = tk.Frame(frame, bg=BG_DEEP)
        pb_frame.pack(side="right")
        self.progress = ttk.Progressbar(
            pb_frame, mode="indeterminate", length=160,
            style="Cyan.Horizontal.TProgressbar")
        self.progress.pack(pady=2)
        self._progress_running = False

    # ── Output section ────────────────────────────────────────────────────────
    def _build_output_section(self, parent, row):
        frame = tk.Frame(parent, bg=BG_DEEP)
        frame.grid(row=row, column=0, sticky="nsew", padx=16, pady=(0, 6))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        # Label row
        lbl_frame = tk.Frame(frame, bg=BG_DEEP)
        lbl_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        tk.Label(lbl_frame, text="AI Response:",
                 bg=BG_DEEP, fg=TEXT_DIM, font=self.font_small).pack(side="left")
        self._make_btn(lbl_frame, "🗑  Clear", self._clear_output,
                       bg=BG_CARD, fg=ACCENT_RED, width=8).pack(side="right")

        # Text area
        txt_frame = tk.Frame(frame, bg=BORDER, bd=1)
        txt_frame.grid(row=1, column=0, sticky="nsew")
        txt_frame.columnconfigure(0, weight=1)
        txt_frame.rowconfigure(0, weight=1)

        self.output_text = tk.Text(
            txt_frame,
            bg=BG_INPUT, fg=TEXT_PRIMARY,
            insertbackground=ACCENT_CYAN,
            selectbackground=ACCENT_BLUE,
            font=self.font_mono,
            wrap="word",
            relief="flat", bd=0,
            padx=12, pady=10,
            state="disabled",
        )
        self.output_text.grid(row=0, column=0, sticky="nsew")

        vsb = tk.Scrollbar(txt_frame, orient="vertical",
                           command=self.output_text.yview,
                           bg=BG_CARD, troughcolor=BG_SURFACE,
                           activebackground=ACCENT_CYAN)
        vsb.grid(row=0, column=1, sticky="ns")
        self.output_text.configure(yscrollcommand=vsb.set)

        # Configure LaTeX syntax highlight tags
        self._setup_output_tags()

    def _setup_output_tags(self):
        self.output_text.tag_configure("cmd",     foreground="#79c0ff")
        self.output_text.tag_configure("env",     foreground="#7ee787")
        self.output_text.tag_configure("math",    foreground="#ffa657")
        self.output_text.tag_configure("comment", foreground=TEXT_DIM)
        self.output_text.tag_configure("code_block",
                                        background="#0f1419", foreground="#e6edf3")
        self.output_text.tag_configure("error_msg", foreground=ACCENT_RED)
        self.output_text.tag_configure("info_msg",  foreground=ACCENT_CYAN)

    # ── Status bar ────────────────────────────────────────────────────────────
    def _build_status_bar(self, parent, row):
        bar = tk.Frame(parent, bg=BG_SURFACE, height=26)
        bar.grid(row=row, column=0, sticky="ew")
        bar.grid_propagate(False)

        self.status_dot = tk.Label(bar, text="●", fg=ACCENT_GREEN,
                                    bg=BG_SURFACE, font=self.font_small)
        self.status_dot.pack(side="left", padx=(10, 4))
        self.status_label = tk.Label(bar, text="Ready", fg=TEXT_DIM,
                                      bg=BG_SURFACE, font=self.font_small)
        self.status_label.pack(side="left")

        self.token_label = tk.Label(bar, text="Tokens: 0",
                                     fg=TEXT_MUTED, bg=BG_SURFACE, font=self.font_small)
        self.token_label.pack(side="right", padx=10)

        self.provider_status = tk.Label(bar, text="No provider selected",
                                         fg=TEXT_MUTED, bg=BG_SURFACE, font=self.font_small)
        self.provider_status.pack(side="right", padx=(0, 16))

    # ── Helper: create a styled button ────────────────────────────────────────
    def _make_btn(self, parent, text, command, bg=BG_CARD, fg=TEXT_PRIMARY,
                  width=None, tooltip=None, **kwargs):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=fg,
            activebackground=BORDER_LIGHT, activeforeground=TEXT_PRIMARY,
            relief="flat", cursor="hand2",
            font=self.font_small, bd=0,
            padx=8, pady=5,
            **({"width": width} if width else {}),
            **kwargs,
        )
        if tooltip:
            self._add_tooltip(btn, tooltip)
        return btn

    def _add_tooltip(self, widget, text):
        def enter(e):
            tip = tk.Toplevel()
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{e.x_root+10}+{e.y_root+10}")
            tk.Label(tip, text=text, bg="#ffffe0", fg="black",
                     font=self.font_small, padx=4, pady=2).pack()
            widget._tooltip = tip
        def leave(e):
            if hasattr(widget, "_tooltip"):
                widget._tooltip.destroy()
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    # ── Mode management ───────────────────────────────────────────────────────
    def _set_mode(self, mode: str):
        self.mode_var.set(mode)
        color = MODE_COLORS[mode]
        for m, btn in self._mode_buttons.items():
            if m == mode:
                btn.configure(bg=color, fg=BG_DEEP)
            else:
                btn.configure(bg=BG_CARD, fg=TEXT_DIM)
        # Show/hide language selector
        if mode == "translate":
            self._lang_frame.pack(side="left", padx=(16, 0))
        else:
            self._lang_frame.pack_forget()
        self.cfg.last_mode = mode
        self._apply_instruction_visibility()
        self._update_input_label()

    def _update_input_label(self):
        """Reflect what the big text box is expected to hold."""
        mode = self.mode_var.get()
        if self._doc_path and mode in ("edit", "correct"):
            label = f"Document: {self._doc_path.name}"
        elif self._doc_path and mode == "create":
            label = f"Reference / template: {self._doc_path.name}"
        else:
            label = {
                "create":    "Your request / LaTeX code:",
                "edit":      "Document to edit (or paste LaTeX):",
                "correct":   "LaTeX code to correct:",
                "translate": "Text / LaTeX to translate:",
            }.get(mode, "Input:")
        self.input_label_var.set(label)

    # ── Provider management ───────────────────────────────────────────────────
    def _on_provider_change(self, event=None):
        selected_display = self.provider_var.get()
        # Find provider name from display name
        for p in ALL_PROVIDERS:
            if p.display_name == selected_display:
                self.cfg.last_provider = p.name
                break
        self._update_key_url_buttons()
        self._refresh_models()

    def _on_model_change(self, event=None):
        self.cfg.last_model = self.model_var.get()

    def _on_lang_change(self, event=None):
        self.cfg.last_target_language = self.lang_var.get()

    def _get_current_provider_class(self):
        display = self.provider_var.get()
        for p in ALL_PROVIDERS:
            if p.display_name == display:
                return p
        return None

    def _update_key_url_buttons(self):
        p_cls = self._get_current_provider_class()
        if not p_cls:
            return
        if p_cls.requires_api_key:
            self.key_btn.configure(fg=ACCENT_AMBER)
        else:
            self.key_btn.configure(fg=TEXT_MUTED)

    def _refresh_models(self):
        p_cls = self._get_current_provider_class()
        if not p_cls:
            return
        self._set_status("Fetching models…", ACCENT_AMBER)
        api_key = self.cfg.get_api_key(p_cls.name)
        base_url = self.cfg.get_base_url(p_cls.name, p_cls.default_base_url)

        def fetch():
            try:
                provider = p_cls(api_key=api_key, base_url=base_url)
                models = provider.list_models()
                self.root.after(0, lambda: self._update_model_list(models))
            except Exception as exc:
                self.root.after(0, lambda: self._set_status(f"Error: {exc}", ACCENT_RED))

        threading.Thread(target=fetch, daemon=True).start()

    def _update_model_list(self, models: list[str]):
        self.model_cb.configure(values=models)
        last = self.cfg.last_model
        if last in models:
            self.model_var.set(last)
        elif models:
            p_cls = self._get_current_provider_class()
            self.model_var.set(preferred_model(p_cls, models) if p_cls else models[0])
        provider_name = self.cfg.last_provider
        self.provider_status.configure(
            text=f"Provider: {PROVIDER_DISPLAY_NAMES.get(provider_name, provider_name)}")
        if self._is_fallback_list(models):
            self._set_status(
                "Ready — offline model list shown; run 🧪 Test to check the provider",
                ACCENT_AMBER)
        else:
            self._set_status("Ready", ACCENT_GREEN)

    def _is_fallback_list(self, models: list[str]) -> bool:
        """True when the shown list is the hard-coded fallback, i.e. the
        provider could not actually be reached."""
        p_cls = self._get_current_provider_class()
        if not p_cls or not models:
            return False
        try:
            module = __import__(p_cls.__module__, fromlist=["FALLBACK_MODELS"])
            fallback = getattr(module, "FALLBACK_MODELS", None)
        except Exception:
            return False
        return fallback is not None and list(models) == list(fallback)

    # ── Connection test ───────────────────────────────────────────────────────
    def _test_connection(self):
        p_cls = self._get_current_provider_class()
        if not p_cls:
            messagebox.showerror("No provider", "Please select a provider.", parent=self.root)
            return
        model = self.model_var.get()
        if not model:
            messagebox.showerror("No model", "Please select a model.", parent=self.root)
            return

        api_key = self.cfg.get_api_key(p_cls.name)
        base_url = self.cfg.get_base_url(p_cls.name, p_cls.default_base_url)
        provider = p_cls(api_key=api_key, base_url=base_url, model=model)

        self.test_btn.configure(state="disabled")
        self._set_status(f"Testing {p_cls.display_name}…", ACCENT_AMBER)

        def run():
            result = {"text": "", "error": None}

            def on_token(tok):
                result["text"] += tok

            def on_done(full):
                result["text"] = full or result["text"]

            def on_error(err):
                result["error"] = err

            try:
                provider.stream_chat(
                    "You are a connectivity probe. Reply with the single word: OK",
                    "ping", on_token, on_done, on_error)
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"

            self.root.after(0, lambda: self._report_test(result, p_cls))

        threading.Thread(target=run, daemon=True).start()

    def _report_test(self, result: dict, p_cls):
        self.test_btn.configure(state="normal")
        if result["error"]:
            self._set_status(
                f"{p_cls.display_name}: FAILED — {result['error'][:70]}", ACCENT_RED)
            messagebox.showerror(
                f"{p_cls.display_name} — connection failed",
                f"{result['error']}\n\n"
                f"Model: {self.model_var.get()}\n"
                f"Base URL: {self.cfg.get_base_url(p_cls.name, p_cls.default_base_url) or '(default)'}\n\n"
                f"Check the API key (🔑 API Key) and the base URL (🌐 URL).",
                parent=self.root)
        else:
            preview = result["text"].strip()[:60] or "(empty reply)"
            self._set_status(f"{p_cls.display_name}: OK — {preview}", ACCENT_GREEN)
            messagebox.showinfo(
                f"{p_cls.display_name} — connection OK",
                f"Model: {self.model_var.get()}\n\nReply: {preview}",
                parent=self.root)

    # ── API Key / URL dialogs ─────────────────────────────────────────────────
    def _edit_api_key(self):
        p_cls = self._get_current_provider_class()
        if not p_cls:
            return
        current = self.cfg.get_api_key(p_cls.name)
        key = simpledialog.askstring(
            f"{p_cls.display_name} — API Key",
            f"Enter API key for {p_cls.display_name}:",
            initialvalue=current,
            show="*",
            parent=self.root,
        )
        if key is not None:
            self.cfg.set_api_key(p_cls.name, key.strip())
            self._set_status("API key saved.", ACCENT_GREEN)

    def _edit_base_url(self):
        p_cls = self._get_current_provider_class()
        if not p_cls:
            return
        current = self.cfg.get_base_url(p_cls.name, p_cls.default_base_url)
        url = simpledialog.askstring(
            f"{p_cls.display_name} — Base URL",
            f"Enter base URL for {p_cls.display_name}:",
            initialvalue=current,
            parent=self.root,
        )
        if url is not None:
            self.cfg.set_base_url(p_cls.name, url.strip())
            self._set_status("Base URL saved. Refreshing models…", ACCENT_AMBER)
            self._refresh_models()

    # ── Send / Stop ───────────────────────────────────────────────────────────
    def _send(self):
        mode = self.mode_var.get()
        instruction = self.instruction_var.get().strip()

        # Validate input
        user_input = self.input_text.get("1.0", "end").strip()
        if not user_input or self._placeholder_active:
            if instruction and mode in ("edit", "create"):
                user_input = ""
            else:
                messagebox.showwarning(
                    "Empty input",
                    "Please enter a request or paste LaTeX code.",
                    parent=self.root)
                return

        if mode == "edit" and not user_input and not self._doc_path:
            messagebox.showwarning(
                "No document",
                "Open a document first (📂 Open) or paste the LaTeX you want to edit.",
                parent=self.root)
            return

        p_cls = self._get_current_provider_class()
        if not p_cls:
            messagebox.showerror("No provider", "Please select a provider.", parent=self.root)
            return

        model = self.model_var.get()
        if not model:
            messagebox.showerror("No model", "Please select a model.", parent=self.root)
            return

        api_key = self.cfg.get_api_key(p_cls.name)
        base_url = self.cfg.get_base_url(p_cls.name, p_cls.default_base_url)

        provider = p_cls(api_key=api_key, base_url=base_url, model=model)
        ok, msg = provider.validate()
        if not ok:
            messagebox.showerror("Configuration error", msg, parent=self.root)
            return

        target_lang = self.lang_var.get()
        system_prompt = build_system_prompt(mode, target_lang)
        user_message = build_user_message(
            mode, user_input, instruction, self._doc_path)

        # Prepare UI
        self._clear_output()
        self._response_buffer = ""
        self._set_status("Generating…", ACCENT_CYAN)
        self.send_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._start_progress()

        self._current_provider = provider

        def on_token(tok: str):
            self._token_queue.put(("token", tok))

        def on_done(full: str):
            self._token_queue.put(("done", full))

        def on_error(err: str):
            self._token_queue.put(("error", err))

        threading.Thread(
            target=provider.stream_chat,
            args=(system_prompt, user_message, on_token, on_done, on_error),
            daemon=True,
        ).start()

    def _stop(self):
        if self._current_provider:
            self._current_provider.stop()
        self._set_status("Stopped.", ACCENT_AMBER)
        self._finish_generation()

    # ── Queue pump (processes streaming tokens on the main thread) ────────────
    def _start_queue_pump(self):
        self._pump()

    def _pump(self):
        try:
            while True:
                kind, data = self._token_queue.get_nowait()
                if kind == "token":
                    self._append_output(data)
                    self._total_tokens += estimate_tokens(data)
                    self.token_label.configure(
                        text=f"Tokens: ~{self._total_tokens:,}")
                elif kind == "done":
                    self._set_status("Done  ✓", ACCENT_GREEN)
                    self._finish_generation()
                    self._highlight_output()
                elif kind == "error":
                    self._append_output(f"\n\n[ERROR] {data}", tag="error_msg")
                    self._set_status(f"Error: {data[:60]}", ACCENT_RED)
                    self._finish_generation()
        except queue.Empty:
            pass
        finally:
            self.root.after(40, self._pump)

    def _finish_generation(self):
        self.send_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._stop_progress()
        # Unlock the response box so the result can be touched up before saving
        self.output_text.configure(state="normal")

    # ── Output helpers ────────────────────────────────────────────────────────
    def _append_output(self, text: str, tag: str | None = None):
        self.output_text.configure(state="normal")
        if tag:
            self.output_text.insert("end", text, tag)
        else:
            self.output_text.insert("end", text)
        self.output_text.see("end")
        self.output_text.configure(state="disabled")
        self._response_buffer += text

    def _clear_output(self):
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")
        self._response_buffer = ""
        self._total_tokens = 0
        self.token_label.configure(text="Tokens: 0")

    def _highlight_output(self):
        """Apply basic LaTeX syntax highlighting to the output text."""
        content = self.output_text.get("1.0", "end")
        self.output_text.configure(state="normal")
        for tag, pattern in LATEX_PATTERNS:
            for m in pattern.finditer(content):
                start = f"1.0+{m.start()}c"
                end   = f"1.0+{m.end()}c"
                self.output_text.tag_add(tag, start, end)
        self.output_text.configure(state="disabled")

    # ── File operations ───────────────────────────────────────────────────────
    @staticmethod
    def _filetypes(save: bool = False):
        if save:
            return [
                ("LaTeX files", "*.tex"),
                ("LyX files",   "*.lyx"),
                ("BibTeX files", "*.bib"),
                ("Text files",  "*.txt"),
                ("Markdown",    "*.md"),
                ("All files",   "*.*"),
            ]
        return [
            ("LaTeX / LyX", "*.tex *.lyx"),
            ("BibTeX",      "*.bib"),
            ("Text files",  "*.txt *.md"),
            ("All files",   "*.*"),
        ]

    def _initial_dir(self) -> str:
        if self._doc_path:
            return str(self._doc_path.parent)
        if self._template_path:
            return str(self._template_path.parent)
        return self.cfg.last_open_dir or ""

    # ── Opening / binding a document ──────────────────────────────────────────
    def _insert_file(self):
        """Paste a file's contents into the box without binding it."""
        path = filedialog.askopenfilename(
            title="Insert file contents",
            initialdir=self._initial_dir(),
            filetypes=self._filetypes(), parent=self.root)
        if not path:
            return
        ok, content = load_file(path)
        if not ok:
            messagebox.showerror("Load error", content, parent=self.root)
            return
        self._clear_placeholder()
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", content)
        self.cfg.last_open_dir = str(Path(path).parent)
        self._set_status(f"Inserted: {Path(path).name}", ACCENT_GREEN)

    def _open_document(self):
        """Open a file and bind it as the document to be modified."""
        path = filedialog.askopenfilename(
            title="Open document to edit",
            initialdir=self._initial_dir(),
            filetypes=self._filetypes(), parent=self.root)
        if not path:
            return

        # Warn if unsaved work would be lost
        if not self._confirm_discard_edits():
            return

        ok, content = load_file(path)
        if not ok:
            messagebox.showerror("Load error", content, parent=self.root)
            return

        self._doc_path = Path(path)
        self._template_path = None
        self._doc_signature = file_signature(path)
        self._doc_loaded_text = content
        self.cfg.last_open_dir = str(self._doc_path.parent)

        self._clear_placeholder()
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", content)

        # Opening a document means you want to change it
        if self.mode_var.get() not in ("edit", "correct"):
            self._set_mode("edit")

        self._refresh_doc_bar()
        self.instruction_entry.focus_set()
        self._set_status(f"Opened: {self._doc_path.name} — describe the changes below",
                         ACCENT_GREEN)

    def _use_as_template(self):
        """Start a NEW document from an existing one; the original is untouched."""
        src = filedialog.askopenfilename(
            title="Choose the template document",
            initialdir=self._initial_dir(),
            filetypes=self._filetypes(), parent=self.root)
        if not src:
            return
        if not self._confirm_discard_edits():
            return

        ok, content = load_file(src)
        if not ok:
            messagebox.showerror("Load error", content, parent=self.root)
            return

        # Immediately ask where the NEW document should live, so the template
        # can never be overwritten by accident.
        dest = filedialog.asksaveasfilename(
            title="Save the new document as",
            initialdir=str(Path(src).parent),
            initialfile=Path(suggest_copy_name(src)).name,
            defaultextension=Path(src).suffix or ".tex",
            filetypes=self._filetypes(save=True), parent=self.root)
        if not dest:
            return

        self._template_path = Path(src)
        self._doc_path = Path(dest)
        self._doc_signature = None          # brand-new file
        self._doc_loaded_text = content
        self.cfg.last_open_dir = str(Path(src).parent)

        self._clear_placeholder()
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", content)
        self.instruction_var.set("")

        self._set_mode("edit")
        self._refresh_doc_bar()
        self.instruction_entry.focus_set()
        self._set_status(
            f"Template: {Path(src).name} → new file: {Path(dest).name}", ACCENT_PURPLE)

    def _reload_document(self):
        """Discard local edits and read the file from disk again."""
        if not self._doc_path:
            return
        if not self._doc_path.exists():
            messagebox.showerror("Missing file",
                                 f"{self._doc_path} no longer exists.", parent=self.root)
            return
        ok, content = load_file(self._doc_path)
        if not ok:
            messagebox.showerror("Load error", content, parent=self.root)
            return
        self._clear_placeholder()
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", content)
        self._doc_loaded_text = content
        self._doc_signature = file_signature(self._doc_path)
        self._refresh_doc_bar()
        self._set_status(f"Reloaded: {self._doc_path.name}", ACCENT_GREEN)

    def _close_document(self):
        """Forget the open document (does not delete anything on disk)."""
        self._doc_path = None
        self._template_path = None
        self._doc_signature = None
        self._doc_loaded_text = ""
        self.instruction_var.set("")
        self._refresh_doc_bar()
        self._set_status("Document closed.", TEXT_DIM)

    def _confirm_discard_edits(self) -> bool:
        """Ask before replacing the text box contents when it holds real edits."""
        current = self.input_text.get("1.0", "end").strip()
        if not self._doc_path or not current or current == self._doc_loaded_text.strip():
            return True
        return messagebox.askyesno(
            "Discard local edits?",
            f"The box contains changes to «{self._doc_path.name}» that have not "
            f"been sent to the AI yet.\n\nDiscard them and continue?",
            parent=self.root)

    # ── Document bar ──────────────────────────────────────────────────────────
    def _refresh_doc_bar(self):
        """Update the label and enable/disable the file buttons."""
        if self._doc_path:
            name = self._doc_path.name
            if self._template_path:
                text = (f"New document: {name}   ·   from template "
                        f"«{self._template_path.name}»")
                color = ACCENT_PURPLE
            else:
                text = f"Editing: {name}"
                if not self._doc_path.exists():
                    text += "   ·   (new file, not saved yet)"
                color = ACCENT_CYAN
            if len(str(self._doc_path)) > 96:
                text += "   ·   " + str(self._doc_path.parent)
            self.doc_label.configure(text=text, fg=color)
        else:
            self.doc_label.configure(
                text="No document open — Open a file to modify it, or use one as a template",
                fg=TEXT_MUTED)

        state = "normal" if self._doc_path else "disabled"
        for btn in (self.save_btn, self.saveas_btn, self.revert_btn, self.close_btn):
            btn.configure(state=state)

    # ── Saving ────────────────────────────────────────────────────────────────
    def _current_result(self) -> str:
        """The document extracted from the AI response (fences stripped)."""
        return extract_document(self._response_buffer)

    def _save_result(self):
        """Save the response back to the open document (with backup)."""
        if not self._doc_path:
            self._save_result_as()
            return
        content = self._current_result()
        if not content.strip():
            messagebox.showwarning("Nothing to save",
                                   "The response area is empty.", parent=self.root)
            return
        self._write_document(self._doc_path, content)

    def _save_result_as(self):
        """Save the response to a file of your choosing."""
        content = self._current_result()
        if not content.strip():
            messagebox.showwarning("Nothing to save",
                                   "The response area is empty.", parent=self.root)
            return

        suggested = ""
        if self._doc_path:
            suggested = self._doc_path.name
        elif self._template_path:
            suggested = Path(suggest_copy_name(self._template_path)).name

        path = filedialog.asksaveasfilename(
            title="Save result as",
            initialdir=self._initial_dir(),
            initialfile=suggested,
            defaultextension=".tex",
            filetypes=self._filetypes(save=True), parent=self.root)
        if not path:
            return

        target = Path(path)
        if self._write_document(target, content):
            # The new file becomes the open document
            self._doc_path = target
            self._doc_signature = file_signature(target)
            self._doc_loaded_text = self.input_text.get("1.0", "end")
            self._refresh_doc_bar()

    def _write_document(self, target: Path, content: str) -> bool:
        """
        Write *content* to *target*, applying the safety policy:
        confirm → backup → atomic write.
        """
        exists = target.exists()

        # 1. Has the file changed on disk since we loaded it?
        if exists and self._doc_signature and target == self._doc_path:
            current_sig = file_signature(target)
            if current_sig and current_sig != self._doc_signature:
                if not messagebox.askyesno(
                        "File changed on disk",
                        f"«{target.name}» was modified by another program after you "
                        f"opened it.\n\nOverwriting will lose those changes.\n\n"
                        f"Continue anyway?",
                        parent=self.root, icon="warning"):
                    self._set_status("Save cancelled.", ACCENT_AMBER)
                    return False

        # 2. Explicit confirmation before overwriting an existing file
        if exists and self.cfg.confirm_overwrite:
            n_lines = content.count("\n") + 1
            if not messagebox.askyesno(
                    "Overwrite file?",
                    f"This will replace:\n\n{target}\n\n"
                    f"({n_lines} lines)\n\n"
                    + ("A timestamped .bak copy will be created first."
                       if self.cfg.auto_backup
                       else "Backups are disabled in Settings."),
                    parent=self.root, icon="warning"):
                self._set_status("Save cancelled.", ACCENT_AMBER)
                return False

        # 3. Backup
        backup_note = ""
        if exists and self.cfg.auto_backup:
            ok, info = backup_file(target)
            if not ok:
                if not messagebox.askyesno(
                        "Backup failed",
                        f"{info}\n\nSave without a backup?", parent=self.root):
                    return False
            elif info:
                backup_note = f"  ·  backup: {Path(info).name}"

        # 4. Atomic write
        ok, err = save_file(target, content)
        if not ok:
            messagebox.showerror("Save error", err, parent=self.root)
            self._set_status("Save failed.", ACCENT_RED)
            return False

        self._doc_signature = file_signature(target)
        self._set_status(f"Saved: {target.name}{backup_note}", ACCENT_GREEN)
        self._refresh_doc_bar()
        return True

    def _copy_result(self):
        content = self._current_result().strip()
        if not content:
            messagebox.showwarning("Nothing to copy",
                                    "The response area is empty.", parent=self.root)
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self._set_status("Copied to clipboard (code only).", ACCENT_GREEN)

    def _clear_input(self):
        self.input_text.delete("1.0", "end")
        self._restore_placeholder()

    # ── Settings window ───────────────────────────────────────────────────────
    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("LyX AI Agent — Settings")
        win.configure(bg=BG_DEEP)
        win.geometry("640x500")
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Settings", font=self.font_title,
                 bg=BG_DEEP, fg=ACCENT_CYAN).pack(pady=(18, 8))

        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=16, pady=8)

        # ── API Keys tab
        keys_tab = tk.Frame(notebook, bg=BG_CARD, padx=16, pady=12)
        notebook.add(keys_tab, text="  🔑  API Keys  ")
        for p in ALL_PROVIDERS:
            row = tk.Frame(keys_tab, bg=BG_CARD)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=f"{p.display_name}:",
                     bg=BG_CARD, fg=TEXT_DIM, font=self.font_small,
                     width=18, anchor="w").pack(side="left")
            var = tk.StringVar(value=self.cfg.get_api_key(p.name))
            entry = tk.Entry(row, textvariable=var, show="*",
                              bg=BG_INPUT, fg=TEXT_PRIMARY,
                              insertbackground=ACCENT_CYAN,
                              relief="flat", font=self.font_small, width=30)
            entry.pack(side="left", padx=(0, 8))
            def save_key(pname=p.name, v=var):
                self.cfg.set_api_key(pname, v.get().strip())
                v.set(self.cfg.get_api_key(pname))
            entry.bind("<FocusOut>", lambda e, s=save_key: s())

        tk.Label(keys_tab,
                 text=("Accidental prefixes such as “api-key:” or “Bearer” are\n"
                       "removed automatically when the key is saved."),
                 bg=BG_CARD, fg=TEXT_MUTED, font=self.font_small,
                 justify="left", anchor="w").pack(fill="x", pady=(10, 0))

        # ── Base URLs tab
        urls_tab = tk.Frame(notebook, bg=BG_CARD, padx=16, pady=12)
        notebook.add(urls_tab, text="  🌐  Base URLs  ")
        for p in ALL_PROVIDERS:
            if not p.default_base_url:
                continue
            row = tk.Frame(urls_tab, bg=BG_CARD)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=f"{p.display_name}:",
                     bg=BG_CARD, fg=TEXT_DIM, font=self.font_small,
                     width=18, anchor="w").pack(side="left")
            var = tk.StringVar(
                value=self.cfg.get_base_url(p.name, p.default_base_url))
            entry = tk.Entry(row, textvariable=var,
                              bg=BG_INPUT, fg=TEXT_PRIMARY,
                              insertbackground=ACCENT_CYAN,
                              relief="flat", font=self.font_small, width=36)
            entry.pack(side="left")
            def save_url(pname=p.name, v=var):
                self.cfg.set_base_url(pname, v.get().strip())
            entry.bind("<FocusOut>", lambda e, s=save_url: s())

        # ── Appearance tab
        appearance_tab = tk.Frame(notebook, bg=BG_CARD, padx=16, pady=12)
        notebook.add(appearance_tab, text="  🎨  Appearance  ")
        tk.Label(appearance_tab, text="Font size (mono):",
                 bg=BG_CARD, fg=TEXT_DIM, font=self.font_small).grid(
            row=0, column=0, sticky="w", pady=6)
        fs_var = tk.IntVar(value=self.cfg.get("font_size", 11))
        tk.Spinbox(appearance_tab, from_=8, to=20, textvariable=fs_var,
                   bg=BG_INPUT, fg=TEXT_PRIMARY, width=5,
                   command=lambda: self._apply_font_size(fs_var.get())).grid(
            row=0, column=1, sticky="w", padx=8)

        # ── Documents tab
        docs_tab = tk.Frame(notebook, bg=BG_CARD, padx=16, pady=12)
        notebook.add(docs_tab, text="  📄  Documents  ")

        backup_var = tk.BooleanVar(value=self.cfg.auto_backup)
        tk.Checkbutton(
            docs_tab,
            text="Create a timestamped .bak copy before overwriting a file",
            variable=backup_var,
            command=lambda: setattr(self.cfg, "auto_backup", backup_var.get()),
            bg=BG_CARD, fg=TEXT_PRIMARY, selectcolor=BG_INPUT,
            activebackground=BG_CARD, activeforeground=TEXT_PRIMARY,
            font=self.font_small, anchor="w", bd=0,
            highlightthickness=0,
        ).pack(fill="x", pady=6)

        confirm_var = tk.BooleanVar(value=self.cfg.confirm_overwrite)
        tk.Checkbutton(
            docs_tab,
            text="Ask for confirmation before overwriting an existing file",
            variable=confirm_var,
            command=lambda: setattr(self.cfg, "confirm_overwrite", confirm_var.get()),
            bg=BG_CARD, fg=TEXT_PRIMARY, selectcolor=BG_INPUT,
            activebackground=BG_CARD, activeforeground=TEXT_PRIMARY,
            font=self.font_small, anchor="w", bd=0,
            highlightthickness=0,
        ).pack(fill="x", pady=6)

        tk.Label(docs_tab,
                 text=("When you save an AI response, only the code block is written\n"
                       "to the file — the AI's explanations are left out.\n\n"
                       "“Use as template” always writes to a NEW file, so the\n"
                       "original document is never modified."),
                 bg=BG_CARD, fg=TEXT_DIM, font=self.font_small,
                 justify="left", anchor="w").pack(fill="x", pady=(10, 0))

        # Close
        tk.Button(win, text="Close", command=win.destroy,
                  bg=ACCENT_CYAN, fg=BG_DEEP, relief="flat",
                  font=self.font_btn, padx=16, pady=6, cursor="hand2").pack(pady=12)

    def _apply_font_size(self, size: int):
        self.font_mono.configure(size=size)
        self.cfg.set("font_size", size)

    # ── Status helpers ────────────────────────────────────────────────────────
    def _set_status(self, msg: str, color: str = TEXT_DIM):
        self.status_label.configure(text=msg, fg=color)
        self.status_dot.configure(fg=color)

    def _start_progress(self):
        self.progress.start(12)
        self._progress_running = True

    def _stop_progress(self):
        self.progress.stop()
        self._progress_running = False

    # ── Session restore ───────────────────────────────────────────────────────
    def _restore_session(self):
        # Provider
        last_p = self.cfg.last_provider
        for p in ALL_PROVIDERS:
            if p.name == last_p:
                self.provider_var.set(p.display_name)
                break
        else:
            if ALL_PROVIDERS:
                self.provider_var.set(ALL_PROVIDERS[0].display_name)

        # Mode
        self._set_mode(self.cfg.last_mode)

        # Load models in background
        self.root.after(200, self._refresh_models)

    # ── Close ─────────────────────────────────────────────────────────────────
    def _on_close(self):
        # Save window geometry
        self.cfg.set("window_geometry", self.root.wm_geometry())
        self.root.destroy()

    # ── Run ───────────────────────────────────────────────────────────────────
    def run(self):
        self.root.mainloop()
