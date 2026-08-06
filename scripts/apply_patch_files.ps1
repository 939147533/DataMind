param(
  [Parameter(Mandatory=$true)][string]$Manifest
)
$ErrorActionPreference = "Stop"
$codex = "C:\Program Files\WindowsApps\OpenAI.Codex_26.715.9079.0_x64__2p2nqsd0c76g0\app\resources\codex.exe"
$items = Get-Content -Raw -Encoding UTF8 $Manifest | ConvertFrom-Json

# Pass 1: 删除已存在的文件
$delHunks = @()
foreach ($f in $items.files) {
  if (Test-Path $f.path) { $delHunks += "*** Delete File: $($f.path)" }
}
if ($delHunks.Count -gt 0) {
  $delPatch = "*** Begin Patch`n" + ($delHunks -join "`n") + "`n*** End Patch"
  $delPatch = $delPatch.TrimEnd().Replace('"','""')
  & $codex --codex-run-as-apply-patch $delPatch
  if ($LASTEXITCODE -ne 0) { Write-Host "DELETE PATCH FAILED"; exit 1 }
}

# Pass 2: 添加文件
$addHunks = @()
foreach ($f in $items.files) {
  $lines = ($f.content -split "`r?`n")
  $body = ($lines | ForEach-Object { "+$_" }) -join "`n"
  $addHunks += "*** Add File: $($f.path)`n$body"
}
$addPatch = "*** Begin Patch`n" + ($addHunks -join "`n") + "`n*** End Patch"
$addPatch = $addPatch.TrimEnd().Replace('"','""')
& $codex --codex-run-as-apply-patch $addPatch
if ($LASTEXITCODE -ne 0) { Write-Host "ADD PATCH FAILED"; exit 1 }
Write-Host "PATCH OK"
