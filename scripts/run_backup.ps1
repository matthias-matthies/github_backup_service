<#
.SYNOPSIS
    Run the GitHub Organisation Backup Service on Windows.

.DESCRIPTION
    Activates the virtual environment, loads the configuration and invokes the
    backup CLI.  Timestamps log output and writes to logs\backup.log.

.PARAMETER Config
    Path to the YAML configuration file.  Defaults to .\config.yml.

.PARAMETER LogLevel
    Logging verbosity.  One of: DEBUG, INFO, WARNING, ERROR, CRITICAL.
    Defaults to INFO.

.PARAMETER DryRun
    When set, simulates the backup without writing any data.

.EXAMPLE
    .\scripts\run_backup.ps1
    .\scripts\run_backup.ps1 -Config "C:\backups\config.yml" -LogLevel DEBUG
    .\scripts\run_backup.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [string]$Config    = ".\config.yml",
    [ValidateSet("DEBUG","INFO","WARNING","ERROR","CRITICAL")]
    [string]$LogLevel  = "INFO",
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

# ── Virtual environment ─────────────────────────────────────────────────────
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    Write-Host "--> Activating virtual environment …" -ForegroundColor Cyan
    & $VenvActivate
} else {
    Write-Warning "Virtual environment not found at $VenvActivate. Run scripts\setup.sh or 'pip install -r requirements.txt' first."
}

# ── Runtime directories ─────────────────────────────────────────────────────
foreach ($dir in @("backup\organizations","backup\repositories","backup\metadata","backup\assets","logs")) {
    $full = Join-Path $ProjectRoot $dir
    if (-not (Test-Path $full)) { New-Item -ItemType Directory -Path $full -Force | Out-Null }
}

# ── Build argument list ─────────────────────────────────────────────────────
$args_list = @("--config", $Config, "--log-level", $LogLevel)
if ($DryRun) { $args_list += "--dry-run" }

# ── Execute ─────────────────────────────────────────────────────────────────
$Timestamp = Get-Date -Format "yyyy-MM-ddTHH-mm-ss"
Write-Host "==> Starting backup run [$Timestamp]" -ForegroundColor Green

Push-Location $ProjectRoot
try {
    python -m src.backup @args_list
    $ExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($ExitCode -eq 0) {
    Write-Host "==> Backup completed successfully." -ForegroundColor Green
} else {
    Write-Error "==> Backup failed with exit code $ExitCode. Check logs\backup.log for details."
}
exit $ExitCode
