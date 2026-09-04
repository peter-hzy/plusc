param(
    [Parameter(Mandatory=$true)][string]$Workspace
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    py -3.11 -m venv (Join-Path $RepoRoot ".venv")
}
& $Python -m pip install -e "$RepoRoot[excel]"
& (Join-Path $RepoRoot ".venv\Scripts\inbound-leads.exe") doctor
& (Join-Path $RepoRoot ".venv\Scripts\inbound-leads.exe") init --workspace $Workspace

