$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceMod = Join-Path $root 'mod\ares_ai'
$modRoot = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Paradox Interactive\Hearts of Iron IV\mod'
$targetMod = Join-Path $modRoot 'ares_ai'
if (-not (Test-Path -LiteralPath $sourceMod)) { throw "Не найдена папка мода: $sourceMod" }
New-Item -ItemType Directory -Force -Path $modRoot | Out-Null
if (Test-Path -LiteralPath $targetMod) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    Move-Item -LiteralPath $targetMod -Destination (Join-Path $modRoot "ares_ai.backup-$stamp")
    Write-Host "Предыдущая папка мода сохранена как ares_ai.backup-$stamp"
}
Copy-Item -LiteralPath $sourceMod -Destination $targetMod -Recurse
$descriptor = @'
name="ARES AI — Adaptive Response Prototype"
version="0.1"
path="mod/ares_ai"
tags={
  "Gameplay"
  "AI"
}
supported_version="1.19.3"
'@
Set-Content -LiteralPath (Join-Path $modRoot 'ares_ai.mod') -Value $descriptor -Encoding UTF8
Write-Host "Установлено в: $modRoot"
