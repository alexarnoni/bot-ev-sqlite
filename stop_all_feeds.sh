#!/bin/bash

echo "🛑 Bot EV+ - Parando Todos os Feeds"
echo "===================================="
echo

# Lista de feeds para parar
FEEDS_TO_STOP=("default" "feed1" "feed2" "feed3" "feed4" "feed_test")

echo "📋 Parando feeds: ${FEEDS_TO_STOP[*]}"
echo

for feed in "${FEEDS_TO_STOP[@]}"; do
    echo "🛑 Parando feed: $feed"
    
    # Para o listener
    if tmux has-session -t "listener_$feed" 2>/dev/null; then
        tmux kill-session -t "listener_$feed"
        echo "  📱 Listener parado"
    else
        echo "  📱 Listener já estava parado"
    fi
    
    # Para o scheduler
    if tmux has-session -t "main_$feed" 2>/dev/null; then
        tmux kill-session -t "main_$feed"
        echo "  ⏰ Scheduler parado"
    else
        echo "  ⏰ Scheduler já estava parado"
    fi
    
    # Remove arquivo PID se existir
    if [ -f "data/$feed/bot.pid" ]; then
        rm -f "data/$feed/bot.pid"
        echo "  🗑️ PID removido"
    fi
    
    echo "  ✅ Feed $feed parado"
    echo
done

echo "🎉 Todos os feeds foram parados!"
echo
echo "📊 Para verificar:"
echo "   tmux list-sessions"
echo
echo "🔍 Para monitorar:"
echo "   ./monitor_feeds.sh"
echo
echo "🚀 Para reiniciar:"
echo "   ./setup_multifeed.sh"
