#!/usr/bin/env bash
# DataMind 开发模式启动脚本（macOS / Linux / Windows Git Bash）
#   后端 FastAPI (uvicorn)  http://127.0.0.1:8000
#   前端 Vite               http://127.0.0.1:5174
#
# 用法:
#   ./scripts/start_dev.sh                 启动前后端（后台运行，脚本立即返回）
#   ./scripts/start_dev.sh --port 5175     指定前端端口
#   ./scripts/start_dev.sh --backend-only  只启动后端
#   ./scripts/start_dev.sh --frontend-only 只启动前端
#   ./scripts/start_dev.sh --reload        后端开启热重载
#   ./scripts/start_dev.sh --no-install    不自动创建 venv / 安装依赖
#
# 停止: ./scripts/stop_dev.sh       状态: ./scripts/stop_dev.sh --status
# 日志: scripts/.run/backend.log   scripts/.run/frontend.log
# 环境变量: FRONTEND_PORT / BACKEND_PORT / VENV_DIR / BACKEND_PY

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/scripts/.run"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV_DIR="${VENV_DIR:-$BACKEND_DIR/.venv}"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"

FRONTEND_PORT="${FRONTEND_PORT:-5174}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_PY="${BACKEND_PY:-}"
TARGET="all"
WITH_INSTALL=1
RELOAD=""
BACKEND_TIMEOUT="${BACKEND_TIMEOUT:-180}"
FRONTEND_TIMEOUT="${FRONTEND_TIMEOUT:-90}"

if [ -t 2 ]; then
  C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
  C_RED=""; C_GREEN=""; C_YELLOW=""; C_DIM=""; C_OFF=""
fi

step() { printf '%s\n' "${C_DIM}==>${C_OFF} $*" >&2; }
ok()   { printf '%s\n' "${C_GREEN}✓${C_OFF} $*" >&2; }
warn() { printf '%s\n' "${C_YELLOW}!${C_OFF} $*" >&2; }
die()  { printf '%s\n' "${C_RED}✗${C_OFF} $*" >&2; exit 1; }

usage() { awk 'NR>1 && !/^#/ {exit} NR>1 {sub(/^# ?/, ""); print}' "${BASH_SOURCE[0]}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --port|-p)       FRONTEND_PORT="${2:?--port 需要端口号}"; shift 2 ;;
    --backend-port)  BACKEND_PORT="${2:?--backend-port 需要端口号}"; shift 2 ;;
    --backend-only)  TARGET="backend"; shift ;;
    --frontend-only) TARGET="frontend"; shift ;;
    --reload)        RELOAD="--reload"; shift ;;
    --no-install)    WITH_INSTALL=0; shift ;;
    -h|--help)       usage; exit 0 ;;
    *) die "未知参数: $1（-h 查看用法）" ;;
  esac
done

case "$FRONTEND_PORT$BACKEND_PORT" in
  *[!0-9]*) die "端口必须是数字" ;;
esac

mkdir -p "$RUN_DIR"

pid_alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }

read_pid() { [ -f "$1" ] && tr -d '[:space:]' < "$1" || true; }

port_pids() {
  command -v lsof >/dev/null 2>&1 || return 0
  lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | sort -u
}

port_in_use() {
  if command -v lsof >/dev/null 2>&1; then
    [ -n "$(port_pids "$1")" ]
    return
  fi
  if (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; then return 0; fi
  return 1
}

http_ready() {
  if command -v curl >/dev/null 2>&1; then
    curl -sf -m 2 -o /dev/null "$1"
    return
  fi
  port_in_use "$2"
}

wait_ready() {  # wait_ready <超时秒> <端口> <探测命令...>
  local timeout="$1" port="$2"; shift 2
  local waited=0
  while [ "$waited" -lt "$timeout" ]; do
    if "$@" >/dev/null 2>&1; then return 0; fi
    sleep 1
    waited=$((waited + 1))
  done
  return 1
}

pick_python() {
  local candidate
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

# 在 backend/.venv、backend/.venv-* 中挑选"本机真正能执行"的解释器（Windows venv 无法在 mac/Linux 上运行）
find_venv_python() {
  local dir candidate
  for dir in "$VENV_DIR" "$BACKEND_DIR"/.venv-*; do
    [ -d "$dir" ] || continue
    for candidate in "$dir/bin/python" "$dir/Scripts/python.exe"; do
      if [ -x "$candidate" ] && "$candidate" -c 'import sys' >/dev/null 2>&1; then
        printf '%s' "$candidate"
        return 0
      fi
    done
  done
  return 1
}

# 判断解释器是否属于虚拟环境 / conda 环境（避免把依赖装进系统 Python）
is_env_python() {
  local root
  root="$(cd "$(dirname "$1")/.." 2>/dev/null && pwd)" || return 1
  [ -f "$root/pyvenv.cfg" ] || [ -d "$root/conda-meta" ]
}

host_venv_dir() {
  case "$(uname -s 2>/dev/null || printf unknown)" in
    Darwin) printf '%s' "$BACKEND_DIR/.venv-mac" ;;
    Linux)  printf '%s' "$BACKEND_DIR/.venv-linux" ;;
    *)      printf '%s' "$BACKEND_DIR/.venv-local" ;;
  esac
}

ensure_backend_env() {
  local py="" target_dir="$VENV_DIR" base_python

  if [ -n "$BACKEND_PY" ]; then
    py="$BACKEND_PY"
  else
    py="$(find_venv_python || true)"
  fi

  if [ -z "$py" ]; then
    [ "$WITH_INSTALL" = "1" ] || die "未找到可用的后端虚拟环境。请先执行:
    python3.12 -m venv backend/.venv && backend/.venv/bin/python -m pip install -r backend/requirements.txt"
    if [ -e "$target_dir" ]; then
      target_dir="$(host_venv_dir)"
      warn "$VENV_DIR 不是本机可运行的虚拟环境（可能由 Windows 创建），改用 $target_dir"
    fi
    base_python="$(pick_python)" || die "未找到 Python 3.10+，请先安装（macOS: brew install python@3.12）"
    step "创建后端虚拟环境 ${target_dir}（${base_python}），首次安装依赖需要几分钟..."
    "$base_python" -m venv "$target_dir"
    py="$(find_venv_python || true)"
    [ -n "$py" ] || die "虚拟环境创建失败: $target_dir"
    "$py" -m pip install --upgrade pip
    "$py" -m pip install -r "$BACKEND_DIR/requirements.txt"
  fi

  if ! "$py" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
    [ "$WITH_INSTALL" = "1" ] || die "虚拟环境缺少依赖，请执行: \"$py\" -m pip install -r backend/requirements.txt"
    is_env_python "$py" || die "拒绝向非虚拟环境的解释器安装依赖: $py
请改用项目虚拟环境，例如: VENV_DIR=backend/.venv-mac ./scripts/start_dev.sh"
    step "安装后端依赖..."
    "$py" -m pip install -r "$BACKEND_DIR/requirements.txt"
  fi

  printf '%s' "$py"
}

ensure_frontend_env() {
  command -v npm >/dev/null 2>&1 || die "未找到 npm，请先安装 Node.js 18+"
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    [ "$WITH_INSTALL" = "1" ] || die "未找到 frontend/node_modules，请先执行: cd frontend && npm ci"
    step "安装前端依赖（首次执行需要几分钟）..."
    ( cd "$FRONTEND_DIR" && { [ -f package-lock.json ] && npm ci || npm install; } )
  fi
}

start_backend() {
  local running py
  running="$(read_pid "$BACKEND_PID_FILE")"
  if pid_alive "$running"; then
    warn "后端已在运行 (pid $running)，跳过启动"
    return 0
  fi
  if port_in_use "$BACKEND_PORT"; then
    warn "端口 $BACKEND_PORT 已被占用，跳过后端启动（可能已由其他方式启动）"
    return 0
  fi

  py="$(ensure_backend_env)"
  step "启动后端 uvicorn  http://127.0.0.1:$BACKEND_PORT  (env: $py)"
  ( cd "$BACKEND_DIR" && exec nohup "$py" -m uvicorn app.main:app \
      --host 127.0.0.1 --port "$BACKEND_PORT" $RELOAD >"$BACKEND_LOG" 2>&1 ) &
  echo $! >"$BACKEND_PID_FILE"

  if wait_ready "$BACKEND_TIMEOUT" "$BACKEND_PORT" http_ready "http://127.0.0.1:$BACKEND_PORT/api/health" "$BACKEND_PORT"; then
    ok "后端就绪 (pid $(read_pid "$BACKEND_PID_FILE"))  http://127.0.0.1:$BACKEND_PORT"
  else
    warn "后端在 $BACKEND_TIMEOUT 秒内未就绪，日志末尾："
    tail -n 20 "$BACKEND_LOG" 2>/dev/null | sed 's/^/    /' >&2 || true
    rm -f "$BACKEND_PID_FILE"
    die "后端启动失败（完整日志: ${BACKEND_LOG}）"
  fi
}

start_frontend() {
  local running
  running="$(read_pid "$FRONTEND_PID_FILE")"
  if pid_alive "$running"; then
    warn "前端已在运行 (pid $running)，跳过启动"
    return 0
  fi
  if port_in_use "$FRONTEND_PORT"; then
    warn "端口 $FRONTEND_PORT 已被占用，跳过前端启动"
    return 0
  fi

  ensure_frontend_env
  step "启动前端 Vite  http://127.0.0.1:$FRONTEND_PORT"
  ( cd "$FRONTEND_DIR" && exec nohup npm run dev -- --port "$FRONTEND_PORT" --strictPort --host 127.0.0.1 \
      >"$FRONTEND_LOG" 2>&1 ) &
  echo $! >"$FRONTEND_PID_FILE"

  if wait_ready "$FRONTEND_TIMEOUT" "$FRONTEND_PORT" http_ready "http://127.0.0.1:$FRONTEND_PORT/" "$FRONTEND_PORT"; then
    ok "前端就绪 (pid $(read_pid "$FRONTEND_PID_FILE"))  http://127.0.0.1:$FRONTEND_PORT"
  else
    warn "前端在 $FRONTEND_TIMEOUT 秒内未就绪，日志末尾："
    tail -n 20 "$FRONTEND_LOG" 2>/dev/null | sed 's/^/    /' >&2 || true
    rm -f "$FRONTEND_PID_FILE"
    die "前端启动失败（完整日志: ${FRONTEND_LOG}）"
  fi
}

[ "$TARGET" = "frontend" ] || start_backend
[ "$TARGET" = "backend" ] || start_frontend

printf '\n' >&2
[ "$TARGET" = "frontend" ] || printf '  后端  http://127.0.0.1:%s\n' "$BACKEND_PORT" >&2
[ "$TARGET" = "backend" ]  || printf '  前端  http://127.0.0.1:%s\n' "$FRONTEND_PORT" >&2
printf '  默认账号 admin / admin123\n' >&2
printf '  日志 scripts/.run/  停止 ./scripts/stop_dev.sh\n' >&2
