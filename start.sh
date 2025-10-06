#!/bin/bash

# Inicia um único feed usando tmux
# Uso:
#   ./start.sh [feed_name]
# Exemplo:
#   ./start.sh default
#   ./start.sh feed_test

set -euo pipefail

# Carrega variáveis do .env (se existir)
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Carrega variáveis adicionais do script opcional
if [ -f load_env.sh ]; then
  # shellcheck disable=SC1091
  source load_env.sh || true
fi

FEED_ID_ARG=${1:-}

if [ -n "${FEED_ID_ARG}" ]; then
  FEED_ID="$FEED_ID_ARG"
else
  FEED_ID="${FEED_ID:-default}"
fi

echo "🚀 Iniciando feed: $FEED_ID"

# Garante diretórios
mkdir -p "data/$FEED_ID" "logs/$FEED_ID"

# Para sessões existentes
tmux kill-session -t "listener_$FEED_ID" 2>/dev/null || true
tmux kill-session -t "main_$FEED_ID" 2>/dev/null || true

# Exporta FEED_ID para os processos
export FEED_ID

echo "📱 Iniciando listener em tmux: listener_$FEED_ID"
tmux new-session -d -s "listener_$FEED_ID" "source load_env.sh 2>/dev/null || true; export FEED_ID=$FEED_ID; python3 bot_listener.py"

echo "⏰ Iniciando scheduler em tmux: main_$FEED_ID"
tmux new-session -d -s "main_$FEED_ID" "source load_env.sh 2>/dev/null || true; export FEED_ID=$FEED_ID; python3 -c 'import asyncio; from main_scheduler import main; asyncio.run(main())'"

echo
echo "✅ Feed $FEED_ID iniciado. Comandos úteis:"
echo "  tmux attach -t listener_$FEED_ID   # ver logs do listener"
echo "  tmux attach -t main_$FEED_ID       # ver logs do scheduler"
echo "  tmux kill-session -t listener_$FEED_ID; tmux kill-session -t main_$FEED_ID  # parar"


