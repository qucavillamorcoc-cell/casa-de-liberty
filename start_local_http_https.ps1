param(
    [string]$BindHost = "127.0.0.1",
    [int]$HttpPort = 8001,
    [int]$HttpsPort = 8000
)

$python = $null
if (Test-Path ".\.venv\Scripts\python.exe") {
    $python = (Resolve-Path ".\.venv\Scripts\python.exe").Path
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $python = (Resolve-Path ".\venv\Scripts\python.exe").Path
} else {
    $python = "python"
}

$repo = (Get-Location).Path

Write-Host "Starting HTTP Django server at http://$BindHost`:$HttpPort in a new PowerShell window..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$repo'; & '$python' manage.py runserver $BindHost`:$HttpPort"
)

Write-Host "Starting HTTPS Django server at https://$BindHost`:$HttpsPort in this window..."
Write-Host "Self-signed certificate warning in browser is expected."
& $python serve_https.py --host $BindHost --port $HttpsPort
