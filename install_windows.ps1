<#
.SYNOPSIS
    LyX AI Agent — Windows 11 Installer
.DESCRIPTION
    - Verifies Python 3.10+
    - Creates a virtual environment (.venv)
    - Installs all dependencies from requirements.txt
    - Creates a Desktop shortcut (.lnk) with the custom icon
.NOTES
    Run as a regular user (no admin required).
    Usage: Right-click > "Run with PowerShell"
           Or:  powershell -ExecutionPolicy Bypass -File install_windows.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Paths ──────────────────────────────────────────────────────────────────
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir    = Join-Path $ScriptDir ".venv"
$MainScript = Join-Path $ScriptDir "main.py"
$BatchFile  = Join-Path $ScriptDir "LyxAI.bat"
$IconPath   = Join-Path $ScriptDir "assets\logo-lyx-ai.ico"
$Desktop    = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "LyX AI Agent.lnk"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║        LyX AI Agent — Windows Installer      ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Verify Python ──────────────────────────────────────────────────
Write-Host "▶  Checking Python..." -ForegroundColor Yellow

$PythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 10) {
                $PythonCmd = $cmd
                Write-Host "   ✓ Found: $ver" -ForegroundColor Green
                break
            }
        }
    } catch { }
}

if (-not $PythonCmd) {
    Write-Host "   ✗ Python 3.10+ not found." -ForegroundColor Red
    Write-Host "   Please install Python from https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "   Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Step 2: Create virtual environment ─────────────────────────────────────
Write-Host "▶  Creating virtual environment (.venv)..." -ForegroundColor Yellow

if (Test-Path $VenvDir) {
    Write-Host "   ℹ  .venv already exists — skipping creation." -ForegroundColor DarkGray
} else {
    & $PythonCmd -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   ✗ Failed to create virtual environment." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "   ✓ Virtual environment created." -ForegroundColor Green
}

# ── Step 3: Upgrade pip ─────────────────────────────────────────────────────
Write-Host "▶  Upgrading pip..." -ForegroundColor Yellow
$PipExe = Join-Path $VenvDir "Scripts\pip.exe"
& $PipExe install --upgrade pip --quiet
Write-Host "   ✓ pip upgraded." -ForegroundColor Green

# ── Step 4: Install dependencies ───────────────────────────────────────────
Write-Host "▶  Installing dependencies (this may take a minute)..." -ForegroundColor Yellow
$ReqFile = Join-Path $ScriptDir "requirements.txt"
& $PipExe install -r $ReqFile
if ($LASTEXITCODE -ne 0) {
    Write-Host "   ✗ Failed to install some dependencies." -ForegroundColor Red
    Write-Host "   Check your internet connection and try again." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "   ✓ Dependencies installed." -ForegroundColor Green

# ── Step 5: Create Desktop shortcut ────────────────────────────────────────
Write-Host "▶  Creating Desktop shortcut..." -ForegroundColor Yellow

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath       = $BatchFile
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.Description      = "LyX AI Agent — LaTeX document assistant"
$Shortcut.WindowStyle      = 7   # Minimized (hides CMD flash)

if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}

$Shortcut.Save()
Write-Host "   ✓ Shortcut created: $ShortcutPath" -ForegroundColor Green

# ── Done ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║     ✓  Installation complete!                ║" -ForegroundColor Green
Write-Host "║                                              ║" -ForegroundColor Green
Write-Host "║  → Double-click 'LyX AI Agent' on Desktop   ║" -ForegroundColor Green
Write-Host "║  → Or run:  .\LyxAI.bat                     ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# Ask to launch now
$launch = Read-Host "Launch LyX AI Agent now? (Y/N)"
if ($launch -match "^[Yy]") {
    Start-Process $BatchFile
}
