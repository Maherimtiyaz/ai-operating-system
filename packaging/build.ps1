# Builds the standalone Windows app into dist\AIOP\.
#
#   .\packaging\build.ps1
#
# The whisper weights are not bundled; the app downloads them on first run.
# Only the engine DLLs and the config template ship next to the executable.

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$VenvPyInstaller = Join-Path $Root ".venv\Scripts\pyinstaller.exe"

Push-Location $Root
try {
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        throw "Virtualenv not found at $VenvPython; create it first (python -m venv .venv)."
    }

    Write-Host "==> Installing build tooling (pyinstaller, requests)"
    & $VenvPython -m pip install --quiet --upgrade pyinstaller requests
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

    Write-Host "==> Building dist\AIOP"
    & $VenvPyInstaller --noconfirm --clean (Join-Path $PSScriptRoot "aiop.spec")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

    $Dist = Join-Path $Root "dist\AIOP"
    $DistModels = Join-Path $Dist "models"
    $DistConfig = Join-Path $Dist "config"

    New-Item -ItemType Directory -Force -Path $DistModels | Out-Null
    New-Item -ItemType Directory -Force -Path $DistConfig | Out-Null

    Write-Host "==> Copying whisper backend DLLs next to the executable"
    Copy-Item -Force (Join-Path $Root "models\*.dll") $DistModels

    Write-Host "==> Copying the config template"
    Copy-Item -Force (Join-Path $Root "config\config.yaml") $DistConfig

    Write-Host ""
    Write-Host "Build complete: $Dist"
    Write-Host "Smoke check: run  '$Dist\AIOP.exe --check'"
}
finally {
    Pop-Location
}