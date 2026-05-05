#!/bin/bash

echo "🛑 Bot EV+ - Parando Sistema Global"
echo "==================================="
echo

# Lista de feeds para parar
FEEDS_TO_STOP=("default" "feed1" "feed2" "feed3" "feed4")

echo "🛑 Parando todos os processos..."

# Para o scanner global
echo "🌍 Parando Scanner Global..."
tmux kill-session -t "global_scanner" 2>/dev/null || true

# Para todos os feeds
for feed in "${FEEDS_TO_STOP[@]}"; do
    echo "📱 Parando feed: $feed"
    tmux kill-session -t "listener_$feed" 2>/dev/null || true
    tmux kill-session -t "main_$feed" 2>/dev/null || true
done

echo "⏳ Aguardando 5 segundos..."
sleep 5

echo "✅ Todos os processos foram parados!"
echo
echo "📊 Processos parados:"
echo "   🌍 Scanner Global"
echo "   📱 Feed Listeners: ${#FEEDS_TO_STOP[@]} processos"
echo "   ⏰ Feed Schedulers: ${#FEEDS_TO_STOP[@]} processos"
