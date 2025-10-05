#!/bin/bash

echo "🔍 Verificando status dos listeners..."
echo "=================================="

# Verificar sessões tmux
echo "📊 Sessões tmux ativas:"
tmux list-sessions 2>/dev/null || echo "Nenhuma sessão tmux encontrada"

echo ""
echo "📋 Verificando logs dos listeners:"

for feed in default feed1 feed2 feed3 feed4 feed_test; do
    echo ""
    echo "🔸 Feed: $feed"
    
    # Verificar se o log existe
    if [ -f "logs/listener_${feed}.log" ]; then
        echo "📄 Últimas 5 linhas do log:"
        tail -5 "logs/listener_${feed}.log" 2>/dev/null || echo "Erro ao ler log"
    else
        echo "❌ Log não encontrado: logs/listener_${feed}.log"
    fi
    
    # Verificar se há processo Python rodando
    echo "🐍 Processos Python para $feed:"
    ps aux | grep "bot_listener.py.*$feed" | grep -v grep || echo "Nenhum processo encontrado"
done

echo ""
echo "🔧 Para reiniciar todos os listeners:"
echo "./start_all_feeds.sh"
