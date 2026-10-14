#!/usr/bin/env bash
# DataMind 开发模式停止脚本（macOS / Linux / Windows Git Bash）
#
# 用法:
#   ./scripts/stop_dev.sh             停止前后端
#   ./scripts/stop_dev.sh --backend   只停后端
#   ./scripts/stop_dev.sh --frontend  只停前端
#   ./scripts/stop_dev.sh --status    只查看运行状态
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/scripts/.run"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"

FRONTEND_PORT="${FRONTEND_PORT:-5174}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
TARGET="all"
MODE="stop"
GRACE=15

if [ -t 1 ]; then
  C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
  C_RED=""; C_GREEN=""; C_DIM=""; C_OFF=""
fi

info() { printf '%s\n' "$*"; }
step() { printf '%s\n' "${C_DIM}==>${C_OFF} $*"; }
ok()   { printf '%s\n' "${C_GREEN}✓${C_OFF} $*"; }
die()  { printf '%s\n' "${C_RED}✗${C_OFF} $*" >&2; exit 1; }

usage() { awk 'NR>1 && !/^#/ {exit} NR>1 {sub(/^# ?/, ""); print}' "${BASH_SOURCE[0]}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --backend)  TARGET="backend"; shift ;;
    --frontend) TARGET="frontend"; shift ;;
    --status)   MODE="status"; shift ;;
    -h|--help)  usage; exit 0 ;;
    *) die "未知参数: $1（-h 查看用法）" ;;
  esac
done

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

# 递归结束进程及其子进程（npm -> vite 这类包装进程会被一并清理）
kill_tree() {
  local pid="$1" sig="$2" child
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_tree "$child" "$sig"
  done
  kill "-$sig" "$pid" 2>/dev/null || true
}

wait_gone() {
  local pid="$1" waited=0
  while [ "$waited" -lt "$GRACE" ]; do
    pid_alive "$pid" || return 0
    sleep 1
    waited=$((waited + 1))
  done
  return 1
}

status_service() {
  local name="$1" pidfile="$2" port="$3" url="$4"
  local pid; pid="$(read_pid "$pidfile")"
  if pid_alive "$pid"; then
    ok "$name 运行中  pid $pid  $url"
  elif port_in_use "$port"; then
    ok "$name 运行中  pid $(port_pids "$port" | tr '\n' ' ')  ${url}（非本脚本启动）"
  else
    info "· $name 未运行"
  fi
}

stop_service() {
  local name="$1" pidfile="$2" port="$3"
  local pid; pid="$(read_pid "$pidfile")"
  local stopped=0

  if pid_alive "$pid"; then
    step "停止 $name (pid $pid)"
    kill_tree "$pid" TERM
    if ! wait_gone "$pid"; then
      step "$name 未在 ${GRACE}s 内退出，强制结束"
      kill_tree "$pid" KILL
      wait_gone "$pid" || true
    fi
    stopped=1
  fi

  local leftover; leftover="$(port_pids "$port" || true)"
  if [ -n "$leftover" ]; then
    step "清理端口 $port 上的残留进程: $(printf '%s' "$leftover" | tr '\n' ' ')"
    local p
    for p in $leftover; do kill_tree "$p" TERM; done
    sleep 1
    for p in $(port_pids "$port" || true); do kill_tree "$p" KILL; done
    stopped=1
  fi

  rm -f "$pidfile"
  if [ "$stopped" = "1" ]; then
    ok "$name 已停止"
  else
    info "· $name 未在运行"
  fi
}

if [ "$MODE" = "status" ]; then
  info "DataMind 服务状态"
  [ "$TARGET" = "frontend" ] || status_service "后端" "$BACKEND_PID_FILE" "$BACKEND_PORT" "http://127.0.0.1:$BACKEND_PORT"
  [ "$TARGET" = "backend" ] || status_service "前端" "$FRONTEND_PID_FILE" "$FRONTEND_PORT" "http://127.0.0.1:$FRONTEND_PORT"
  exit 0
fi

[ "$TARGET" = "frontend" ] || stop_service "后端" "$BACKEND_PID_FILE" "$BACKEND_PORT"
[ "$TARGET" = "backend" ] || stop_service "前端" "$FRONTEND_PID_FILE" "$FRONTEND_PORT"
