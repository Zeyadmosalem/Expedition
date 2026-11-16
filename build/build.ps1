# Build the Windows app, check it starts, and zip it for sharing.
#   powershell -ExecutionPolicy Bypass -File build\build.ps1
param([string]$Version = "1.2.0")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"

& $py build\make_icon.py
& $py -m PyInstaller --noconfirm --clean build\expedition.spec --distpath dist --workpath build\work
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# Self-check: run the packaged game through a scripted session.
$log = Join-Path $env:TEMP "expedition-smoke.log"
if (Test-Path $log) { Remove-Item $log }
$proc = Start-Process -FilePath "dist\Expedition\Expedition.exe" -ArgumentList "--smoke", "`"$log`"" -Wait -PassThru
$result = if (Test-Path $log) { Get-Content $log -Raw } else { "no log written" }
if ($proc.ExitCode -ne 0 -or -not $result.StartsWith("ok")) { throw "Smoke test failed (exit $($proc.ExitCode)): $result" }
Write-Host "Smoke test: $result"

Copy-Item build\PLAY.txt dist\Expedition\PLAY.txt
$zip = "dist\Expedition-v$Version-windows.zip"
Compress-Archive -Path dist\Expedition -DestinationPath $zip -Force
$size = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "Built $zip ($size MB)"
