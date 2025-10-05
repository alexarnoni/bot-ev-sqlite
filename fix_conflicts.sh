#!/bin/bash

echo "🔧 CORRIGINDO CONFLITOS DE TOKENS"
echo "================================="
echo

# Para TODOS os processos Python relacionados ao bot
echo "🛑 Parando todos os processos Python..."
pkill -f "python.*bot_listener.py" 2>/dev/null || true
pkill -f "python.*main_scheduler.py" 2>/dev/null || true
pkill -f "python.*-c.*main_scheduler" 2>/dev/null || true

# Para todas as sessões tmux
echo "🛑 Parando todas as sessões tmux..."
tmux kill-server 2>/dev/null || true

echo "⏳ Aguardando 10 segundos para limpar tudo..."
sleep 10

# Verifica se ainda há processos rodando
echo "🔍 Verificando processos restantes..."
remaining=$(ps aux | grep -E "(bot_listener|main_scheduler)" | grep -v grep | wc -l)
if [ "$remaining" -gt 0 ]; then
    echo "⚠️ Ainda há $remaining processos rodando, forçando parada..."
    pkill -9 -f "python.*bot_listener.py" 2>/dev/null || true
    pkill -9 -f "python.*main_scheduler.py" 2>/dev/null || true
    sleep 5
fi

echo "✅ Todos os processos parados"
echo

# Inicia apenas UM feed por vez com delay
echo "🚀 Iniciando feeds com sequenciamento correto..."

FEEDS=("default" "feed1" "feed2" "feed3" "feed4" "feed_test")

for i in "${!FEEDS[@]}"; do
    feed="${FEEDS[$i]}"
    
    echo "📱 Iniciando feed: $feed"
    
    # Cria diretórios
    mkdir -p "data/$feed"
    mkdir -p "logs/$feed"
    
    # Inicia listener
    export FEED_ID=$feed
    tmux new-session -d -s "listener_$feed" "export FEED_ID=$feed && python3 bot_listener.py"
    
    # Aguarda listener estabilizar
    echo "  ⏳ Aguardando listener estabilizar..."
    sleep 15
    
    # Inicia scheduler
    tmux new-session -d -s "main_$feed" "export FEED_ID=$feed && python3 -c 'import asyncio; from main_scheduler import main; asyncio.run(main())'"
    
    # Aguarda scheduler estabilizar
    echo "  ⏳ Aguardando scheduler estabilizar..."
    sleep 10
    
    echo "  ✅ Feed $feed iniciado"
    echo
    
    # Aguarda antes do próximo feed
    if [ $i -lt $((${#FEEDS[@]} - 1)) ]; then
        echo "⏳ Aguardando 30 segundos antes do próximo feed..."
        sleep 30
    fi
done

echo "🎉 TODOS OS FEEDS INICIADOS COM SUCESSO!"
echo "========================================"
echo

# Verifica status
echo "📊 Verificando status final..."
./monitor_feeds.sh

echo
echo "🔍 Para ver logs:"
echo "tmux attach -t listener_default"
echo "tmux attach -t main_default"
echo
echo "🛑 Para parar tudo:"
echo "./stop_all_feeds.sh"
