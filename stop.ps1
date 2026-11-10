$ErrorActionPreference = 'Stop'
$taskPidFile = Join-Path $PSScriptRoot 'server.pid'
if (-not (Test-Path -LiteralPath $taskPidFile)) { Write-Host 'No saved BIO-GEN server process.'; exit 0 }
$taskServerId = [int](Get-Content -LiteralPath $taskPidFile)
$taskServer = Get-CimInstance Win32_Process -Filter "ProcessId=$taskServerId"
if ($null -eq $taskServer) { Write-Host 'BIO-GEN is already stopped.'; exit 0 }
if ($taskServer.CommandLine -notlike '*uvicorn biogen.app:app*') { throw 'Saved process is not the BIO-GEN server; no process was stopped.' }
$taskChildren = Get-CimInstance Win32_Process -Filter "ParentProcessId=$taskServerId"
foreach ($taskChild in $taskChildren) {
    if ($taskChild.CommandLine -like '*uvicorn biogen.app:app*') { Stop-Process -Id $taskChild.ProcessId -ErrorAction SilentlyContinue }
}
Stop-Process -Id $taskServerId -ErrorAction SilentlyContinue
Write-Host 'BIO-GEN stopped. All saved cases remain on disk.'
