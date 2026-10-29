param(
  [string]$DbPath = "",
  [ValidateRange(1, 65535)][int]$Port = 8000,
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launchArgs = @("-m", "backend.app.launcher", "--port", "$Port")
if ($DbPath) {
  $launchArgs += @("--db", $DbPath)
}
if ($NoBrowser) {
  $launchArgs += "--no-browser"
}

Push-Location $repoRoot
try {
  & python @launchArgs
  exit $LASTEXITCODE
}
finally {
  Pop-Location
}
