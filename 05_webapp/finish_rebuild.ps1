param([int]$WardProcessId)

$ErrorActionPreference = 'Stop'
$taskRepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRepoRoot
$taskPython = (Get-Command python).Source
$taskLog = Join-Path $PSScriptRoot 'rebuild_validation.log'
$env:HF_HUB_OFFLINE = '1'

"Waiting for Ward process $WardProcessId" | Out-File -LiteralPath $taskLog -Encoding utf8
if ($WardProcessId -gt 0) {
    Wait-Process -Id $WardProcessId -ErrorAction SilentlyContinue
}

foreach ($taskScript in @('prepare_indices.py', 'verify_indices.py', 'verify_app.py')) {
    "Running $taskScript" | Out-File -LiteralPath $taskLog -Encoding utf8 -Append
    & $taskPython (Join-Path $PSScriptRoot $taskScript) *>> $taskLog
    if ($LASTEXITCODE -ne 0) {
        "Failed: $taskScript (exit $LASTEXITCODE)" | Out-File -LiteralPath $taskLog -Encoding utf8 -Append
        exit $LASTEXITCODE
    }
}
'All threshold indices prepared and validated.' | Out-File -LiteralPath $taskLog -Encoding utf8 -Append
