# DiskAGI Standalone MCP + Vision/Video + Local->Cloud Failover Auto-Setup (Windows PowerShell)
$ErrorActionPreference = "Stop"
$ShareDir = Join-Path $env:LOCALAPPDATA "DiskAGI-MCP"
New-Item -ItemType Directory -Force -Path $ShareDir | Out-Null
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($ScriptDir -and (Test-Path (Join-Path $ScriptDir "diskagi_mcp_standalone.py"))) {
    Copy-Item (Join-Path $ScriptDir "diskagi_mcp_standalone.py") (Join-Path $ShareDir "diskagi_mcp_standalone.py") -Force
    Copy-Item (Join-Path $ScriptDir "setup_harnesses.py") (Join-Path $ShareDir "setup_harnesses.py") -Force
} else {
    Invoke-WebRequest -Uri "https://bryonhigbee.github.io/releases/diskagi_mcp_standalone.py" -OutFile (Join-Path $ShareDir "diskagi_mcp_standalone.py") -UseBasicParsing
    Invoke-WebRequest -Uri "https://bryonhigbee.github.io/releases/setup_harnesses.py" -OutFile (Join-Path $ShareDir "setup_harnesses.py") -UseBasicParsing
}
python (Join-Path $ShareDir "setup_harnesses.py")
