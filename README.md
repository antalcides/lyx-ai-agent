# LyX AI Agent 🤖

AI-powered assistant for **LyX** and **LaTeX** document editing.
Supports **7 AI providers** — cloud and local — with a dark-themed GUI.

---

## Features

| Feature                 | Description                                                                   |
| ----------------------- | ----------------------------------------------------------------------------- |
| 📝 **Create**           | Generate complete LaTeX documents from natural language                       |
| ✏️ **Edit**             | Open an existing file and apply changes to it, keeping everything else intact |
| 📑 **Template**         | Start a new document from an existing one — the original is never touched     |
| 🔧 **Correct**          | Fix syntax errors, compilation issues and LaTeX bugs                          |
| 🌐 **Translate**        | Translate documents preserving all LaTeX markup                               |
| 💾 **Safe save**        | Timestamped `.bak` backup + atomic write before overwriting anything          |
| 🔄 **Streaming**        | See the AI response appear token by token                                     |
| 🧪 **Test**             | One-click connectivity check per provider                                     |
| 🎨 **Syntax highlight** | Basic LaTeX syntax highlighting in the output area                            |

---

## Working with documents

The bar under the mode buttons is where all file handling happens.

### Modify a file in place

1. Click **📂 Open** and pick a `.tex` / `.lyx` file.
   The document loads into the big box and the mode switches to **✏️ Edit Document**.
2. Type what you want changed in the **Instruction** field, e.g.
   *“add a Results section and translate the abstract to English”*.
3. Click **▶ Send to AI**.
4. Review the result. You can edit the response box directly before saving.
5. Click **💾 Save**.

Before overwriting, the app asks for confirmation, creates a backup named
`informe.20260916-164230.tex.bak` next to the file, and only then writes the new
content atomically. If the file was modified by another program in the meantime,
you get a second warning.

### Use a file as a template

1. Click **📑 Use as template** and pick the source document.
2. Choose where the **new** document should be saved (a name like
   `informe-nuevo.tex` is suggested).
3. The template loads into the box, and the new path becomes the save target.
4. Describe what to build, then **▶ Send to AI** and **💾 Save**.

The template file itself is never written to — only the new file is.

### What gets written to disk

Only the code block is saved. If the AI replies with an explanation followed by
a ```latex block, the prose is discarded and just the document is written. This
is what makes “edit in place” safe: no markdown fences or commentary ever end up
inside your `.tex` file.

---

## Supported AI Providers

| Provider          | Type     | Notes                                             |
| ----------------- | -------- | ------------------------------------------------- |
| **OpenAI**        | ☁️ Cloud | Requires a valid `sk-…` key                       |
| **Anthropic**     | ☁️ Cloud | Requires credit on the account                    |
| **Google Gemini** | ☁️ Cloud | Model list is fetched live                        |
| **OpenRouter**    | ☁️ Cloud | 400+ models; `:free` models need no credit        |
| **OmniRoute**     | 💻 Local | Gateway on `http://localhost:20128/v1` by default |
| **Ollama**        | 💻 Local | `http://localhost:11434`                          |
| **LM Studio**     | 💻 Local | `http://localhost:1234/v1`                        |

---

## Installation

### Windows 11

```powershell
# Option A — PowerShell (recommended)
powershell -ExecutionPolicy Bypass -File install_windows.ps1

# Option B — run manually
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Then double-click **LyX AI Agent** on your Desktop, or run:

```cmd
LyxAI.bat
```

### Linux (Debian 12 / 13)

```bash
chmod +x install_linux.sh
./install_linux.sh
```

Then run `lyx-ai-agent`, or find it in your application menu under
**Office / Science**.

---

## Quick Start

1. **Select a provider** from the dropdown.
2. **Enter the API key** via `🔑 API Key` (not needed for Ollama / LM Studio).
3. Click **🧪 Test** to confirm the provider actually answers.
4. **Choose a mode**: Create · Edit · Correct · Translate.
5. Type your request, or open a document.
6. Click **▶ Send to AI**, review, then **💾 Save**.

---

## Diagnostics

Check every configured provider without opening the GUI:

```bash
.venv/Scripts/python.exe main.py --diagnose
```

It prints one line per provider with the model it tried and the outcome:

```
provider           model                                result
------------------------------------------------------------------------------------------------
OpenAI             gpt-4o                               FAIL  Error code: 401 - Incorrect API key
Google Gemini      gemini-3.5-flash                     OK    OK
Ollama (Local)     qwen2.5-coder:3b                     OK    OK
OpenRouter         nex-agi/nex-n2.5-pro:free            OK    OK
OmniRoute          auto/best-coding                     OK    OKping
```

Run the test suite:

```bash
.venv/Scripts/python.exe tests/test_document_ops.py
```

---

## Troubleshooting

| Symptom                             | Cause                                                              | Fix                                                                                                 |
| ----------------------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| `401 Incorrect API key`             | The key is wrong or malformed                                      | Paste it again with **🔑 API Key**. A stray `api-key:` or `Bearer` prefix is stripped automatically |
| `401 Missing Authentication header` | Key stored with a prefix                                           | Fixed automatically on load — see `sanitize_api_key`                                                |
| `400 credit balance is too low`     | The account has no credit                                          | Top up, or switch to a local provider                                                               |
| `404 model no longer available`     | The model was retired                                              | Click **↻** to refresh the list and pick a current model                                            |
| `502` / `ProxyError` on OmniRoute   | Wrong base URL                                                     | Set it to `http://localhost:20128/v1` with **🌐 URL**                                               |
| `Connection error` on LM Studio     | The local server is not running                                    | Start LM Studio and enable its server                                                               |
| `429 quota exceeded`                | Free-tier quota used up                                            | Wait, or use another provider                                                                       |
| Provider list shows odd models      | The live list could not be fetched, the built-in fallback is shown | The status bar turns amber and suggests **🧪 Test**                                                 |

---

## Configuration

Settings live in `config.json` (next to `main.py`) and can also be edited via
**⚙ Settings**.

### API Keys

| Provider   | Environment variable (alternative) |
| ---------- | ---------------------------------- |
| OpenAI     | `OPENAI_API_KEY`                   |
| Anthropic  | `ANTHROPIC_API_KEY`                |
| Gemini     | `GOOGLE_API_KEY`                   |
| OpenRouter | `OPENROUTER_API_KEY`               |
| OmniRoute  | set in Settings → Base URLs        |

### Local providers

- **Ollama**: start with `ollama serve` — default `http://localhost:11434`
- **LM Studio**: start the local server — default `http://localhost:1234/v1`
- **OmniRoute**: start the gateway — default `http://localhost:20128/v1`

> ⚠️ **`config.json` stores your API keys in plain text.** It is listed in
> `.gitignore` — keep it that way and never commit it.

### Document settings

Under **⚙ Settings → 📄 Documents**:

- **Create a timestamped `.bak` copy before overwriting a file** (default: on)
- **Ask for confirmation before overwriting an existing file** (default: on)

---

## Project Structure

```
lyx-ai-agent/
├── main.py                  # Entry point (+ --diagnose)
├── app/
│   ├── gui.py               # Main Tkinter GUI
│   ├── config.py            # Settings + API key sanitising
│   ├── utils.py             # Prompts, document extraction, safe file I/O
│   └── providers/           # One file per AI provider
│       ├── base.py          # AIProvider ABC + model preference
│       ├── openai_provider.py
│       ├── anthropic_provider.py
│       ├── gemini_provider.py
│       ├── ollama_provider.py
│       ├── lmstudio_provider.py
│       ├── openrouter_provider.py
│       └── omniroute_provider.py
├── tests/
│   └── test_document_ops.py # Tests for extraction, keys and file safety
├── assets/
│   ├── logo-lyx-ai.png
│   └── logo-lyx-ai.ico
├── config.json              # User settings + keys (gitignored)
├── requirements.txt
├── install_windows.ps1      # Windows installer
├── LyxAI.bat                # Windows launcher
└── install_linux.sh         # Linux installer
```

---

## Requirements

- Python **3.10+**
- `tkinter` (included in most Python installations; on Linux: `sudo apt install python3-tk`)
- Internet connection for cloud providers

---

## License

MIT — use freely, modify as needed.
