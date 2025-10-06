#!/bin/bash

echo "🚀 Bot EV+ - Iniciando Todos os Feeds"
echo "====================================="
echo

# Carrega variáveis do arquivo .env se existir
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Lista de feeds para iniciar (produção - sem feed_test)
FEEDS_TO_START=("default" "feed1" "feed2" "feed3" "feed4")

echo "📋 Iniciando feeds: ${FEEDS_TO_START[*]}"
echo

# Para qualquer feed que já esteja rodando
echo "🛑 Parando feeds existentes..."
for feed in "${FEEDS_TO_START[@]}"; do
    tmux kill-session -t "listener_$feed" 2>/dev/null || true
    tmux kill-session -t "main_$feed" 2>/dev/null || true
done

echo "⏳ Aguardando 5 segundos..."
sleep 5

# Inicia os feeds
for i in "${!FEEDS_TO_START[@]}"; do
    feed="${FEEDS_TO_START[$i]}"
    
    if [ $i -gt 0 ]; then
        echo "⏳ Aguardando 10 segundos antes de iniciar $feed..."
        sleep 10
    fi
    
    echo "🚀 Iniciando feed: $feed"
    
    # Cria diretórios se necessário
    mkdir -p "data/$feed"
    mkdir -p "logs/$feed"
    
    # Inicia o listener com variáveis de ambiente
    export FEED_ID=$feed
    tmux new-session -d -s "listener_$feed" "source load_env.sh && export FEED_ID=$feed && python3 bot_listener.py"
    
    # Inicia o scheduler com variáveis de ambiente
    tmux new-session -d -s "main_$feed" "source load_env.sh && export FEED_ID=$feed && python3 -c 'import asyncio; from main_scheduler import main; asyncio.run(main())'"
    
    echo "  📱 Listener iniciado"
    echo "  ⏰ Scheduler iniciado"
    echo "  ✅ Feed $feed iniciado"
    echo
done

echo "🎉 Todos os feeds foram iniciados!"
echo
echo "📊 Para monitorar:"
echo "   ./monitor_feeds.sh"
echo
echo "📱 Para ver logs:"
for feed in "${FEEDS_TO_START[@]}"; do
    echo "   tmux attach -t listener_$feed"
done
echo
echo "🛑 Para parar todos:"
echo "   ./stop_all_feeds.sh"