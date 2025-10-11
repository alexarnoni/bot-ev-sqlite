#!/bin/bash

# Script para parar um feed específico no Linux/Unix
# Uso: ./stop_feed.sh <feed_id>

FEED_ID=${1:-"default"}

echo "Stopping feed: $FEED_ID"

# Para processos tmux se existirem
tmux kill-session -t "listener_$FEED_ID" 2>/dev/null || true
tmux kill-session -t "main_$FEED_ID" 2>/dev/null || true

# Para processos Python diretamente se não estiverem em tmux
pkill -f "bot_listener.py.*FEED_ID=$FEED_ID" 2>/dev/null || true
pkill -f "main_scheduler.py.*FEED_ID=$FEED_ID" 2>/dev/null || true

echo "Done. Feed $FEED_ID stopped."
