#!/usr/bin/env bash
set -e

TAILSCALE_AUTH_KEY="tskey-auth-kXHWBzsmm411CNTRL-RdGH3VpLPV3uvpCn7qNcV3AWXGYDei8G"
SHUTDOWN_DELAY="5h57m"
PORT=8080

log() { echo "[$(date '+%H:%M:%S')] $*"; }

cleanup() {
    log "Shutting down services..."
    kill $OLLAMA_PID 2>/dev/null || true
    kill $CHAT_PID 2>/dev/null || true
    sudo tailscale logout 2>/dev/null || true
    sudo shutdown -h now
}
trap cleanup EXIT INT TERM

log "=== Qwen2.5-Coder Chat Setup ==="

# --- Tailscale ---
if ! command -v tailscale &>/dev/null; then
    log "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
fi
log "Connecting to Tailscale..."
sudo tailscale up --auth-key "$TAILSCALE_AUTH_KEY" --hostname qwen-coder
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || true)
log "Tailscale IP: $TAILSCALE_IP"

# --- Ollama ---
if ! command -v ollama &>/dev/null; then
    log "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi
log "Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!
sleep 3

log "Pulling Qwen2.5-Coder:7b (this may take a while)..."
ollama pull qwen2.5-coder:7b

# --- Python deps ---
log "Installing Python dependencies..."
pip install -r requirements.txt --quiet 2>/dev/null || pip3 install -r requirements.txt --quiet

# --- Start chat UI ---
log "Starting chat UI on port $PORT..."
python3 chat_ui.py --port "$PORT" &
CHAT_PID=$!
sleep 2

log ""
log "============================================"
log "  Chat UI ready!"
log "  Local:      http://localhost:$PORT"
log "  Tailscale:  http://$TAILSCALE_IP:$PORT"
log "  Shutdown in: $SHUTDOWN_DELAY"
log "============================================"
log ""

sleep "$SHUTDOWN_DELAY" &
SHUTDOWN_PID=$!
wait $SHUTDOWN_PID

log "Auto-shutdown triggered after $SHUTDOWN_DELAY"
