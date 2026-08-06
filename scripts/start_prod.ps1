<#
启动生产模式（单端口 8000 托管前端产物）：
  1. 构建前端 (npm run build -> frontend/dist)
  2. 启动后端 uvicorn，由 FastAPI 挂载静态资源
用法:
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_prod.ps1
访问: http://127.0.0.1:8000
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Test-Port([int]$port) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $c.Connect("127.0.0.1", $port); $c.Close(); return $true } catch { return $false }
}

Write-Host "[1/2] 构建前端..."
Push-Location "$Root\frontend"
npm.cmd run build
Pop-Location

if (Test-Port 8000) {
    Write-Host "[2/2] 端口 8000 已被占用，请先停止占用进程后重试"
    exit 1
}

$Py = "$Root\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "未找到后端虚拟环境，请先运行 scripts\start_dev.ps1 初始化环境"
    exit 1
}

Write-Host "[2/2] 启动生产服务  http://127.0.0.1:8000 （Ctrl+C 停止）"
Push-Location "$Root\backend"
& $Py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Pop-Location
