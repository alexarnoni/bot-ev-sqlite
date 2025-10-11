#!/bin/bash

# Script para iniciar um feed específico no Linux/Unix
# Uso: ./start_feed.sh <feed_id>

FEED_ID=${1:-"default"}

echo "Starting feed: $FEED_ID"

# Cria diretórios necessários
mkdir -p "data/$FEED_ID"
mkdir -p "logs/$FEED_ID"

# Inicia listener em sessão tmux
tmux new-session -d -s "listener_$FEED_ID" "FEED_ID=$FEED_ID python bot_listener.py"

# Inicia scheduler em sessão tmux
tmux new-session -d -s "main_$FEED_ID" "FEED_ID=$FEED_ID python main_scheduler.py"

echo "Feed $FEED_ID started in tmux sessions:"
echo "  - listener_$FEED_ID"
echo "  - main_$FEED_ID"
echo ""
echo "To view logs: tmux attach -t listener_$FEED_ID"
echo "To stop: ./stop_feed.sh $FEED_ID"
