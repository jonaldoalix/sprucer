#!/usr/bin/env bash
# Idempotent local lab stack: mock LLM :4000, brain :8787, Next :3737.
# Safe to re-run — only starts what is not already listening.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${ROOT}/.sprucer/logs"
PID_DIR="${ROOT}/.sprucer/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

port_open() {
  local port="$1"
  ss -tlnH "sport = :${port}" 2>/dev/null | grep -q LISTEN
}

start_if_needed() {
  local name="$1"
  local port="$2"
  local pidfile="$PID_DIR/${name}.pid"
  shift 2

  if port_open "$port"; then
    echo "${name}: already listening on :${port}"
    return 0
  fi

  echo "${name}: starting on :${port}"
  nohup "$@" >>"$LOG_DIR/${name}.log" 2>&1 &
  echo $! >"$pidfile"
  # Wait briefly for bind
  for _ in $(seq 1 40); do
    if port_open "$port"; then
      echo "${name}: up (pid $(cat "$pidfile"))"
      return 0
    fi
    sleep 0.25
  done
  echo "${name}: failed to bind :${port} — see ${LOG_DIR}/${name}.log" >&2
  return 1
}

cd "$ROOT"

# Prefer venv if present
if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi

start_if_needed mock_llm 4000 python "$ROOT/scripts/mock_llm.py"
start_if_needed brain 8787 sprucer-brain
start_if_needed web 3737 bash -lc "cd '$ROOT/web' && npm run dev --cache '$ROOT/.npm-cache'"

echo
echo "Sprucer lab stack:"
echo "  local     http://127.0.0.1:3737"
echo "  tailscale http://100.64.0.5:3737"
echo "  brain     http://127.0.0.1:8787  (proxied via /v1 from the web UI)"
echo "  mock llm  http://127.0.0.1:4000/v1"
