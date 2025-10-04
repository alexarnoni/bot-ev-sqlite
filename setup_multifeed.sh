#!/bin/bash

echo "🔧 CONFIGURANDO MULTIFEED BOT EV+"
echo "=================================="
echo

# Para todos os feeds ativos
echo "🛑 Parando todos os feeds ativos..."
tmux kill-session -t listener_default 2>/dev/null || true
tmux kill-session -t listener_feed_test 2>/dev/null || true
tmux kill-session -t listener_feed1 2>/dev/null || true
tmux kill-session -t listener_feed2 2>/dev/null || true
tmux kill-session -t listener_feed3 2>/dev/null || true
tmux kill-session -t listener_feed4 2>/dev/null || true
tmux kill-session -t main_default 2>/dev/null || true
tmux kill-session -t main_feed_test 2>/dev/null || true
tmux kill-session -t main_feed1 2>/dev/null || true
tmux kill-session -t main_feed2 2>/dev/null || true
tmux kill-session -t main_feed3 2>/dev/null || true
tmux kill-session -t main_feed4 2>/dev/null || true

echo "✅ Feeds parados"
echo

# Aguarda um pouco
echo "⏳ Aguardando 5 segundos..."
sleep 5

# Cria arquivo .env completo
echo "📝 Criando arquivo .env completo..."
cat > .env << 'EOF'
# Bot EV+ - Configuração de Ambiente
# Copie este arquivo para .env e configure suas variáveis

# ===========================================
# TOKENS DOS BOTS (um por feed)
# ===========================================
BOT_TOKEN_DEFAULT=BOT_TOKEN_DEFAULT_REDACTED
BOT_TOKEN_FEED1=BOT_TOKEN_FEED1_REDACTED
BOT_TOKEN_FEED2=BOT_TOKEN_FEED2_REDACTED
BOT_TOKEN_FEED3=BOT_TOKEN_FEED3_REDACTED
BOT_TOKEN_FEED4=BOT_TOKEN_FEED4_REDACTED
BOT_TOKEN_FEED_TEST=BOT_TOKEN_FEED_TEST_REDACTED

# ===========================================
# API ODDS
# ===========================================
ODDS_API_KEY=ODDS_API_KEY_REDACTED

# ===========================================
# CONFIGURAÇÃO DE FEEDS
# ===========================================
FEEDS=default feed1 feed2 feed3 feed4 feed_test
FEED_ID=default

# ===========================================
# USUÁRIOS ADMINISTRADORES
# ===========================================
ADMIN_USERS=350780046

# ===========================================
# CONFIGURAÇÕES DO SISTEMA
# ===========================================
LOG_LEVEL=INFO
DASHBOARD_PORT=8080
RATE_LIMIT_REQUESTS_PER_HOUR=4800
MAX_CONCURRENT_SCANS=3
CACHE_CLEANUP_DAYS=30
REQUEST_LOG_CLEANUP_HOURS=2

# ===========================================
# CONFIGURAÇÕES OPCIONAIS
# ===========================================
# Timezone (padrão: UTC)
# TIMEZONE=America/Sao_Paulo

# Diretório de dados (padrão: ./data)
DATA_DIR=./data

# Diretório de logs (padrão: ./logs)
# LOG_DIR=./logs

# ===========================================
# SISTEMA SQLITE
# ===========================================
# Cada feed terá seu próprio banco:
# data/feed1/bot.db
# data/feed2/bot.db
# data/feed3/bot.db
# data/feed4/bot.db
# data/feed_test/bot.db
EOF

echo "✅ Arquivo .env criado com configuração multifeed completa"
echo

# Pergunta quais feeds iniciar
echo "📋 Feeds disponíveis:"
echo "1. default (Feed principal - @ArnoniBot)"
echo "2. feed_test (teste - @ArnonitesteBot)"
echo "3. feed1 (Feed 1 - @ArnoniFeed1Bot)"
echo "4. feed2 (Feed 2 - @ArnoniFeed2Bot)"
echo "5. feed3 (Feed 3 - @ArnoniFeed3Bot)"
echo "6. feed4 (Feed 4 - @ArnoniFeed4Bot)"
echo "7. Todos (default + feed_test)"
echo "8. Todos os feeds"
echo

read -p "Escolha uma opção (1-8): " choice

case $choice in
    1) feeds=("default") ;;
    2) feeds=("feed_test") ;;
    3) feeds=("feed1") ;;
    4) feeds=("feed2") ;;
    5) feeds=("feed3") ;;
    6) feeds=("feed4") ;;
    7) feeds=("default" "feed_test") ;;
    8) feeds=("default" "feed1" "feed2" "feed3" "feed4" "feed_test") ;;
    *) echo "❌ Opção inválida"; exit 1 ;;
esac

# Inicia os feeds
echo "🚀 Iniciando feeds selecionados..."
for i in "${!feeds[@]}"; do
    feed_id="${feeds[$i]}"
    
    if [ $i -gt 0 ]; then
        echo "⏳ Aguardando 10 segundos antes de iniciar $feed_id..."
        sleep 10
    fi
    
    echo "📱 Iniciando feed: $feed_id"
    export FEED_ID=$feed_id
    tmux new-session -d -s "listener_$feed_id" "export FEED_ID=$feed_id && python3 bot_listener.py"
    tmux new-session -d -s "main_$feed_id" "export FEED_ID=$feed_id && python3 main_scheduler.py"
    echo "✅ Feed $feed_id iniciado"
done

echo
echo "🎉 CONFIGURAÇÃO MULTIFEED CONCLUÍDA!"
echo "====================================="
echo
echo "📋 Feeds ativos:"
for feed_id in "${feeds[@]}"; do
    echo "• $feed_id: tmux attach -t listener_$feed_id"
done
echo
echo "🔍 Para verificar:"
echo "tmux list-sessions"
echo
echo "📊 Para ver logs:"
for feed_id in "${feeds[@]}"; do
    echo "tail -f logs/listener_$feed_id.log"
done
