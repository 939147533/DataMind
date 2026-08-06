<#
启动开发模式（前后端分离）：
  后端 FastAPI (uvicorn)  http://127.0.0.1:8000
  前端 Vite               http://127.0.0.1:<Port>（默认 5174，规避 5173 被占用）
用法:
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_dev.ps1 [-Port 5174]
#>
param([int]$Port = 5174)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Test-Port([int]$port) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $c.Connect("127.0.0.1", $port); $c.Close(); return $true } catch { return $false }
}

$Py = "$Root\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "[1/4] 创建后端虚拟环境并安装依赖..."
    python -m venv "$Root\backend\.venv"
    & $Py -m pip install --upgrade pip
    & $Py -m pip install -r "$Root\backend\requirements.txt"
} else {
    Write-Host "[1/4] 后端虚拟环境已就绪"
}

if (-not (Test-Path "$Root\frontend\node_modules")) {
    Write-Host "[2/4] 安装前端依赖 (npm ci)..."
    Push-Location "$Root\frontend"
    npm.cmd ci
    Pop-Location
} else {
    Write-Host "[2/4] 前端依赖已就绪"
}

if (Test-Port 8000) {
    Write-Host "[3/4] 端口 8000 已被占用，跳过后端启动（可能已在运行）"
} else {
    Write-Host "[3/4] 启动后端 uvicorn  http://127.0.0.1:8000"
    $BackendLog = "$Root\backend\uvicorn.dev.log"
    Start-Process -FilePath $Py -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory "$Root\backend" -WindowStyle Hidden -RedirectStandardOutput $BackendLog -RedirectStandardError "$BackendLog.err"
}

Write-Host "[4/4] 启动前端 Vite  http://127.0.0.1:$Port （Ctrl+C 停止前端；后端在后台运行）"
Push-Location "$Root\frontend"
npm.cmd run dev -- --port $Port --strictPort
Pop-Location
