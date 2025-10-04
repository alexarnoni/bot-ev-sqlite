#!/bin/bash

# Bot EV+ - Monitor de Feeds
# Script para monitorar todos os feeds ativos

echo "🔍 Bot EV+ - Monitor de Feeds"
echo "================================"

# Carrega variáveis do arquivo .env se existir
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Lista de feeds para monitorar
FEEDS_TO_MONITOR=("default" "feed1" "feed2" "feed3" "feed4" "feed_test")

echo "📊 Status dos Feeds:"
echo ""

for feed in "${FEEDS_TO_MONITOR[@]}"; do
    echo "🔸 Feed: $feed"
    
    # Verifica se o listener está rodando
    if tmux has-session -t "listener_$feed" 2>/dev/null; then
        echo "  📱 Listener: ✅ ATIVO"
    else
        echo "  📱 Listener: ❌ INATIVO"
    fi
    
    # Verifica se o scheduler está rodando
    if tmux has-session -t "main_$feed" 2>/dev/null; then
        echo "  ⏰ Scheduler: ✅ ATIVO"
    else
        echo "  ⏰ Scheduler: ❌ INATIVO"
    fi
    
    # Verifica se o banco existe
    if [ -f "data/$feed/bot.db" ]; then
        echo "  🗄️ Banco: ✅ EXISTE"
        
        # Conta usuários no banco
        user_count=$(sqlite3 "data/$feed/bot.db" "SELECT COUNT(*) FROM users WHERE is_active = 1;" 2>/dev/null || echo "0")
        echo "  👥 Usuários: $user_count"
        
        # Conta alertas hoje
        alerts_today=$(sqlite3 "data/$feed/bot.db" "SELECT COUNT(*) FROM alert_history WHERE DATE(data_envio) = DATE('now');" 2>/dev/null || echo "0")
        echo "  📈 Alertas hoje: $alerts_today"
    else
        echo "  🗄️ Banco: ❌ NÃO EXISTE"
    fi
    
    echo ""
done

echo "================================"
echo "🔧 Comandos úteis:"
echo ""
echo "📱 Monitorar listener de um feed:"
echo "   tmux attach -t listener_[feed_name]"
echo ""
echo "⏰ Monitorar scheduler de um feed:"
echo "   tmux attach -t main_[feed_name]"
echo ""
echo "🛑 Parar um feed:"
echo "   tmux kill-session -t listener_[feed_name]"
echo "   tmux kill-session -t main_[feed_name]"
echo ""
echo "🚀 Iniciar um feed:"
echo "   ./start.sh [feed_name]"
echo ""
echo "📊 Ver todas as sessões:"
echo "   tmux list-sessions"
echo ""
echo "🔄 Atualizar monitor:"
echo "   ./monitor_feeds.sh"
