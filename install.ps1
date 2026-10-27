# DiskAGI (`dagi`) — Frontier at home · Windows PowerShell One-Line Installer
# Usage (PowerShell):
#   irm https://bryonhigbee.github.io/install.ps1 | iex
$ErrorActionPreference = "Stop"

$InstallDir = Join-Path $HOME ".local\bin"
$ShareDir   = Join-Path $HOME ".local\share\diskagi"
$ConfigDir  = Join-Path $HOME ".config\diskagi"
$RemoteBase = if ($env:DISKAGI_DIST_URL) { $env:DISKAGI_DIST_URL } else { "https://bryonhigbee.github.io" }

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $ShareDir   | Out-Null
New-Item -ItemType Directory -Force -Path $ConfigDir  | Out-Null

$ScriptDest = Join-Path $ShareDir "dagi.py"
Write-Host "[dagi] Downloading DiskAGI CLI from $RemoteBase/dagi.py ..." -ForegroundColor Cyan
Invoke-WebRequest -UseBasicParsing -Uri "$RemoteBase/dagi.py" -OutFile $ScriptDest

# Create Windows batch & PowerShell shims (`dagi.cmd` and `diskagi.cmd`)
$CmdShim = "@echo off`r`npython `"$ScriptDest`" %*`r`n"
Set-Content -Path (Join-Path $InstallDir "dagi.cmd")    -Value $CmdShim -Encoding ASCII
Set-Content -Path (Join-Path $InstallDir "diskagi.cmd") -Value $CmdShim -Encoding ASCII

# Ensure ~/.local/bin is on user PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
    $env:Path = "$env:Path;$InstallDir"
}

Write-Host "✓ Installed DiskAGI CLI (`dagi` and `diskagi`) to $InstallDir" -ForegroundColor Green
Write-Host "  Run: dagi          (interactive Blue Claude-Code TUI)" -ForegroundColor Cyan
Write-Host "       dagi --help   (all subcommands)"
Write-Host "       dagi doctor   (verify Brain, models & endpoints)"
