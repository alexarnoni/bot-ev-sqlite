#!/bin/bash

echo "🌍 Bot EV+ - Iniciando Sistema Global"
echo "====================================="
echo

# Carrega variáveis do arquivo .env se existir
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Lista de feeds para iniciar (produção - sem feed_test)
FEEDS_TO_START=("default" "feed1" "feed2" "feed3" "feed4")

echo "📋 Iniciando sistema global:"
echo "   🌍 Scanner Global Único (1 processo)"
echo "   📱 Feeds: ${FEEDS_TO_START[*]}"
echo

# Para qualquer processo que já esteja rodando
echo "🛑 Parando processos existentes..."
tmux kill-session -t "global_scanner" 2>/dev/null || true
for feed in "${FEEDS_TO_START[@]}"; do
    tmux kill-session -t "listener_$feed" 2>/dev/null || true
    tmux kill-session -t "main_$feed" 2>/dev/null || true
done

echo "⏳ Aguardando 5 segundos..."
sleep 5

# 1. Inicia o SCANNER GLOBAL ÚNICO primeiro
echo "🌍 Iniciando Scanner Global Único..."
tmux new-session -d -s "global_scanner" "source load_env.sh && python3 global_scanner.py"
echo "  ✅ Scanner Global iniciado"

echo "⏳ Aguardando 10 segundos para scanner global inicializar..."
sleep 10

# 2. Inicia os feeds (listeners + schedulers)
for i in "${!FEEDS_TO_START[@]}"; do
    feed="${FEEDS_TO_START[$i]}"
    
    if [ $i -gt 0 ]; then
        echo "⏳ Aguardando 5 segundos antes de iniciar $feed..."
        sleep 5
    fi
    
    echo "🚀 Iniciando feed: $feed"
    
    # Cria diretórios se necessário
    mkdir -p "data/$feed"
    mkdir -p "logs/$feed"
    
    # Inicia o listener com variáveis de ambiente
    export FEED_ID=$feed
    tmux new-session -d -s "listener_$feed" "source load_env.sh && export FEED_ID=$feed && python3 bot_listener.py"
    
    # Inicia o scheduler com variáveis de ambiente (agora só processa usuários)
    tmux new-session -d -s "main_$feed" "source load_env.sh && export FEED_ID=$feed && python3 main_scheduler.py"
    
    echo "  📱 Listener iniciado"
    echo "  ⏰ Scheduler iniciado"
    echo "  ✅ Feed $feed iniciado"
    echo
done

echo "🎉 Sistema Global iniciado com sucesso!"
echo
echo "📊 Estrutura do Sistema:"
echo "   🌍 Scanner Global: 1 processo fazendo scan a cada 2min"
echo "   📱 Feed Listeners: ${#FEEDS_TO_START[@]} processos Telegram"
echo "   ⏰ Feed Schedulers: ${#FEEDS_TO_START[@]} processos processando usuários"
echo
echo "📊 Para monitorar:"
echo "   ./monitor_feeds.sh"
echo
echo "📱 Para ver logs:"
echo "   tmux attach -t global_scanner    # Scanner Global"
for feed in "${FEEDS_TO_START[@]}"; do
    echo "   tmux attach -t listener_$feed     # Feed $feed Listener"
done
echo
echo "🛑 Para parar todos:"
echo "   ./stop_all_feeds.sh"
