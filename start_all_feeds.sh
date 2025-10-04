#!/bin/bash

echo "========================================"
echo "    BOT EV+ SQLITE - TODOS OS FEEDS"
echo "========================================"
echo

# Lista de feeds
FEEDS=("feed1" "feed2" "feed3" "feed4" "feed5")

# Cria diretórios se necessário
for feed in "${FEEDS[@]}"; do
    mkdir -p "data/$feed"
    mkdir -p "logs/$feed"
done

echo "Iniciando feeds: ${FEEDS[*]}"
echo

# Função para iniciar um feed
start_feed() {
    local feed=$1
    echo "Iniciando feed: $feed"
    
    # Cria processo em background
    nohup bash -c "export FEED_ID=$feed && python3 bot_listener.py" > "logs/$feed/bot.log" 2>&1 &
    
    # Salva PID
    echo $! > "data/$feed/bot.pid"
    
    echo "Feed $feed iniciado (PID: $!)"
    sleep 2
}

# Inicia todos os feeds
for feed in "${FEEDS[@]}"; do
    start_feed "$feed"
done

echo
echo "Todos os feeds iniciados!"
echo
echo "Para parar todos os feeds: ./stop_all_feeds.sh"
echo "Para monitorar: ./monitor_feeds.sh"
echo
echo "PIDs salvos em: data/*/bot.pid"
echo "Logs em: logs/*/bot.log"
