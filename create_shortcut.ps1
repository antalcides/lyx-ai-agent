<#
.SYNOPSIS
    Creates the LyX AI Agent Desktop shortcut only.
    Run this after install_windows.ps1 if the shortcut was not created automatically.
#>

$ScriptDir   = "C:\Users\Rafael Olivo\lyx-ai-agent"
$BatchFile   = "$ScriptDir\LyxAI.bat"
$IconPath    = "$ScriptDir\assets\logo-lyx-ai.ico"
$Desktop     = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = "$Desktop\LyX AI Agent.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath       = $BatchFile
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.Description      = "LyX AI Agent — LaTeX document assistant"
$Shortcut.WindowStyle      = 7

if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
    Write-Host "Icon set: $IconPath"
}

$Shortcut.Save()
Write-Host "Shortcut created: $ShortcutPath"
