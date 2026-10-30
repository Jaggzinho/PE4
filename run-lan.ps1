# Start the PE3 QC web application so other computers on the local network
# can use it from their browser. The FastAPI process remains the single owner
# of the DuckDB file; remote clients connect over HTTP and permissions
# (including who may import) are enforced by the application's RBAC.
param(
  [string]$DbPath = "",
  [ValidateRange(1, 65535)][int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launchArgs = @("-m", "backend.app.launcher", "--host", "0.0.0.0", "--port", "$Port", "--no-browser")
if ($DbPath) {
  $launchArgs += @("--db", $DbPath)
}

& netsh advfirewall firewall show rule name="PE3 QC Web ($Port)" > $null 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "Adding inbound firewall rule 'PE3 QC Web ($Port)' for TCP port $Port (may require elevation)..."
  netsh advfirewall firewall add rule name="PE3 QC Web ($Port)" dir=in action=allow protocol=TCP localport=$Port | Out-Null
  if ($LASTEXITCODE -se 0) {
    Write-Host "Firewall rule added."
  } else {
    Write-Warning "Could not add the firewall rule. Run this once as Administrator: netsh advfirewall firewall add rule name=`"PE3 QC Web ($Port)`" dir=in action=allow protocol=TCP localport=$Port"
  }
}

Push-Location $repoRoot
try {
  & python @launchArgs
  exit $LASTEXITCODE
}
finally {
  Pop-Location
}
