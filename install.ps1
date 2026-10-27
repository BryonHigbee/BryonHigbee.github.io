# DiskAGI (`dagi`) — Frontier at home · OMP Harness Installer (Windows PowerShell)
# Usage (PowerShell):
#   irm https://bryonhigbee.github.io/install.ps1 | iex
$ErrorActionPreference = "Stop"

$InstallDir = Join-Path $HOME ".local\bin"
$ShareDir = Join-Path $HOME ".local\share\diskagi"
$ConfigDir = Join-Path $HOME ".config\diskagi"

New-Item -ItemType Directory -Force -Path $InstallDir, $ShareDir, $ConfigDir | Out-Null

$ScriptPath = Join-Path $ShareDir "dagi.py"
Invoke-WebRequest -Uri "https://bryonhigbee.github.io/dagi.py" -OutFile $ScriptPath -UseBasicParsing

$CmdWrapper = @"
@echo off
python "%USERPROFILE%\.local\share\diskagi\dagi.py" %*
"@
Set-Content -Path (Join-Path $InstallDir "dagi.cmd") -Value $CmdWrapper -Encoding ASCII
Set-Content -Path (Join-Path $InstallDir "diskagi.cmd") -Value $CmdWrapper -Encoding ASCII

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
    $env:Path = "$env:Path;$InstallDir"
}

Write-Host "✓ Installed DiskAGI OMP Harness (`dagi`) to $InstallDir\dagi.cmd" -ForegroundColor Cyan
Write-Host "  Run: dagi            (interactive OMP TUI with 20-Slot Shared Brain)" -ForegroundColor Cyan
Write-Host "       dagi --help     (all OMP flags & subcommands)"
Write-Host "       dagi doctor     (verify Brain, OMP roles, models & endpoints)"
