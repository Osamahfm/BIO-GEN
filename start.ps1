$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run setup.ps1 first to create the BIO-GEN environment.' }
$taskUrl = 'http://127.0.0.1:8765'
try {
    $taskExisting = Invoke-RestMethod ($taskUrl + '/api/status') -TimeoutSec 2
    if ($taskExisting.application -eq 'BIO-GEN') {
        Start-Process $taskUrl
        Write-Host 'Opened the running BIO-GEN application.'
        exit 0
    }
} catch { }
$env:MPLCONFIGDIR = Join-Path $PSScriptRoot 'data\matplotlib-cache'
$taskServer = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','biogen.app:app','--host','127.0.0.1','--port','8765') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'server.stdout.log') -RedirectStandardError (Join-Path $PSScriptRoot 'server.stderr.log') -PassThru
$taskServer.Id | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'server.pid')
for ($taskAttempt = 0; $taskAttempt -lt 30; $taskAttempt++) {
    try {
        $taskReady = Invoke-RestMethod ($taskUrl + '/api/status') -TimeoutSec 2
        if ($taskReady.application -eq 'BIO-GEN') {
            Start-Process $taskUrl
            Write-Host 'BIO-GEN is running. Use Stop BIO-GEN.cmd when finished.'
            exit 0
        }
    } catch { }
    Start-Sleep -Milliseconds 500
}
throw 'BIO-GEN did not start. See server.stderr.log in this folder.'
