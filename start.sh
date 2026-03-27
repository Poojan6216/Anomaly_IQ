#!/usr/bin/env bash
# -------------------------------------------------------
# AnomalyIQ startup script
# Launches the FastAPI backend and Vite frontend in parallel.
# Usage: ./start.sh
# -------------------------------------------------------

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Terminal colour helpers ──────────────────────────────
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "${CYAN}[AnomalyIQ]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

# ── 1. Check .env ────────────────────────────────────────
if [ ! -f "$ROOT/.env" ]; then
  warn ".env file not found at $ROOT/.env — copy .env.example or create it first."
  exit 1
fi

# ── 2. Check Python venv ─────────────────────────────────
VENV="$ROOT/backend/.venv"
if [ ! -d "$VENV" ]; then
  log "Creating Python virtual environment..."
  python3 -m venv "$VENV"
  source "$VENV/bin/activate"
  pip install -q --upgrade pip
  pip install -q -r "$ROOT/backend/requirements.txt"
  ok "Python venv ready."
else
  source "$VENV/bin/activate"
fi

# ── 3. Check frontend deps ───────────────────────────────
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  log "Installing frontend npm dependencies..."
  cd "$ROOT/frontend" && npm install --silent
  ok "npm dependencies installed."
fi

# ── 4. Start backend ─────────────────────────────────────
log "Starting FastAPI backend on http://localhost:8000 ..."
cd "$ROOT"
PYTHONPATH="$ROOT" uvicorn backend.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --log-level info &
BACKEND_PID=$!
ok "Backend PID $BACKEND_PID"

# ── 5. Start frontend ────────────────────────────────────
log "Starting Vite frontend on http://localhost:5173 ..."
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!
ok "Frontend PID $FRONTEND_PID"

# ── 6. Wait and handle Ctrl+C ────────────────────────────
log "Both services running. Press Ctrl+C to stop."
trap "log 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait $BACKEND_PID $FRONTEND_PID
