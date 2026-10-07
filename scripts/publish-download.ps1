# Copy the latest NSIS installer into the public downloads folder for the web site.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root "frontend\dist-electron\NEXA Setup 0.1.0.exe"
$destDir = Join-Path $root "frontend\public\downloads"
$dest = Join-Path $destDir "NEXA-Setup.exe"
if (-not (Test-Path $src)) {
  Write-Error "Installer not found: $src - run electron dist first."
}
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
Copy-Item -Force $src $dest
Write-Output "Published download: $dest"
