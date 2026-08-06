param(
  [Parameter(Mandatory=$true)][string]$PatchFile
)
$ErrorActionPreference = "Stop"
$codex = "C:\Program Files\WindowsApps\OpenAI.Codex_26.715.9079.0_x64__2p2nqsd0c76g0\app\resources\codex.exe"
$patch = Get-Content -Raw -Encoding UTF8 $PatchFile
$patch = $patch.TrimEnd().Replace('"','""')
& $codex --codex-run-as-apply-patch $patch
if ($LASTEXITCODE -ne 0) { Write-Host "PATCH FAILED"; exit 1 }
Write-Host "PATCH OK"
