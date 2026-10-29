param(
  [switch]$Install
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$webRoot = Join-Path $repoRoot "web"

Push-Location $webRoot
try {
  if ($Install) {
    npm ci
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  }
  npm run build
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
  Pop-Location
}

$indexPath = Join-Path $repoRoot "dist\index.html"
if (-not (Test-Path -LiteralPath $indexPath -PathType Leaf)) {
  throw "Frontend build did not create $indexPath"
}
Write-Host "Built PE3 web frontend at $indexPath"
