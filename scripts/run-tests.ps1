<#
.SYNOPSIS
    Runs the backend test suite in two separate pytest invocations.

.DESCRIPTION
    On Windows the default ProactorEventLoop degrades after the ~600 unit tests
    spin up hundreds of short-lived asyncio.run() loops: asyncpg sockets to
    Postgres start getting reset mid-suite (WinError 64 / 10054), so the real-DB
    e2e tests that run later fail even though each one passes on its own. Running
    the e2e files in their own process keeps each group's loop count low enough
    that asyncpg stays healthy. Both groups pass; a single combined invocation
    does not on Windows. (RC-D — see tasks/todo.md.)

    Group 1: everything except the e2e files (unit / mocked).
    Group 2: the real-DB e2e files, in a fresh process.

    Extra args are forwarded to both invocations, e.g.:
        ./scripts/run-tests.ps1 -q
        ./scripts/run-tests.ps1 -k prioritization

.NOTES
    Run from anywhere; paths resolve relative to the repo root.
    Requires Postgres + Redis up (docker compose up -d postgres redis).
#>
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo "backend\venv\Scripts\python.exe"
Set-Location $repo

if (-not (Test-Path $py)) {
    Write-Host "venv python not found at $py" -ForegroundColor Red
    exit 1
}

# Real-DB e2e files that suffer the Windows event-loop accumulation (RC-D).
# Both lists below must together cover every test (Group 1 ignores exactly
# these, Group 2 runs exactly these).
$e2eFiles = @(
    "backend/tests/test_integrations_integration.py",
    "backend/tests/test_integrations_wazuh.py",
    "backend/tests/test_n8n_bridge_integration.py",
    "backend/tests/test_prioritization_engine.py",
    "backend/tests/test_security_taxonomies.py"
)
$ignoreArgs = $e2eFiles | ForEach-Object { "--ignore=$_" }

Write-Host "== Group 1: unit / mocked tests ==" -ForegroundColor Cyan
& $py -m pytest backend/tests @ignoreArgs @args
$unitExit = $LASTEXITCODE

Write-Host ""
Write-Host "== Group 2: real-DB e2e tests (separate process) ==" -ForegroundColor Cyan
& $py -m pytest @e2eFiles @args
$e2eExit = $LASTEXITCODE

Write-Host ""
if ($unitExit -ne 0 -or $e2eExit -ne 0) {
    Write-Host "TESTS FAILED (group1=$unitExit group2=$e2eExit)" -ForegroundColor Red
    exit 1
}
Write-Host "ALL TESTS PASSED" -ForegroundColor Green
exit 0
