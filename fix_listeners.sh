#!/bin/bash

echo "🔧 CORRIGINDO LISTENERS INATIVOS"
echo "================================"

# 1. Parar TUDO primeiro
echo "🛑 Parando todos os processos..."
./stop_all_feeds.sh

# 2. Aguardar um pouco
echo "⏳ Aguardando 10 segundos..."
sleep 10

# 3. Verificar se parou tudo
echo "🔍 Verificando se tudo parou..."
tmux list-sessions 2>/dev/null || echo "✅ Todas as sessões paradas"

# 4. Matar processos Python restantes
echo "🔪 Matando processos Python restantes..."
pkill -f "bot_listener.py" 2>/dev/null || echo "Nenhum processo bot_listener.py encontrado"
pkill -f "main_scheduler.py" 2>/dev/null || echo "Nenhum processo main_scheduler.py encontrado"

# 5. Aguardar mais um pouco
echo "⏳ Aguardando 5 segundos..."
sleep 5

# 6. Iniciar apenas os listeners primeiro
echo "🚀 Iniciando apenas os listeners..."
for feed in default feed1 feed2 feed3 feed4 feed_test; do
    echo "📱 Iniciando listener: $feed"
    tmux new-session -d -s "listener_$feed" "source load_env.sh && export FEED_ID=$feed && python3 bot_listener.py"
    sleep 3
done

# 7. Aguardar listeners estabilizarem
echo "⏳ Aguardando listeners estabilizarem (15 segundos)..."
sleep 15

# 8. Iniciar schedulers
echo "⏰ Iniciando schedulers..."
for feed in default feed1 feed2 feed3 feed4 feed_test; do
    echo "⏰ Iniciando scheduler: $feed"
    tmux new-session -d -s "main_$feed" "source load_env.sh && export FEED_ID=$feed && python3 -c 'import asyncio; from main_scheduler import main; asyncio.run(main())'"
    sleep 2
done

echo ""
echo "✅ CORREÇÃO CONCLUÍDA!"
echo "======================"
echo "📊 Para verificar: ./monitor_feeds.sh"
echo "📱 Para ver logs: tail -f logs/listener_default.log"
