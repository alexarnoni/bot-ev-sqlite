#!/bin/bash

echo "🔧 CORRIGINDO CONFLITO DE TOKENS DO TELEGRAM"
echo "============================================="
echo

# Para todos os feeds ativos
echo "🛑 Parando todos os feeds ativos..."
tmux kill-session -t listener_default 2>/dev/null || true
tmux kill-session -t listener_feed_test 2>/dev/null || true
tmux kill-session -t main_default 2>/dev/null || true
tmux kill-session -t main_feed_test 2>/dev/null || true

echo "✅ Feeds parados"
echo

# Aguarda um pouco para garantir que as conexões foram fechadas
echo "⏳ Aguardando 5 segundos para fechar conexões..."
sleep 5

# Cria arquivo .env com tokens corretos
echo "📝 Criando arquivo .env com tokens corretos..."
cat > .env << 'EOF'
# Bot EV+ - Configuração de Ambiente
# Tokens diferentes para cada feed

# ===========================================
# TOKENS DOS BOTS (um por feed)
# ===========================================
BOT_TOKEN_DEFAULT=7819087759:AAEe2FzOA7R-9Q1X2ENZDDFZpWEzba-NYXI
BOT_TOKEN_FEED1=8047370953:AAG0sh1sjVqyW7NnmrGqBVJypmRcPYHb9hM
BOT_TOKEN_FEED2=8435178186:AAGQx2F-i9pNjZ4XXkQvMpazPMwjFiW9HfY
BOT_TOKEN_FEED3=7812298685:AAHpClDOP4hxGgGXw5H29wyqBJRvfvg5JxM
BOT_TOKEN_FEED4=8222396387:AAF8G1gljEDZ8DvrH0HQA9s3ogJgw6Lubr8
BOT_TOKEN_FEED_TEST=8419247298:AAGvkg7BkswyEO1xH0MAdZHyzNHZ7OFX4Es

# ===========================================
# API ODDS
# ===========================================
ODDS_API_KEY=d1ffd194fc054b5c7e9691d6aed713c66ab77bc0c9fbd62f66c0d8b04c6f1bea

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
EOF

echo "✅ Arquivo .env criado com tokens corretos"
echo

# Inicia apenas o feed default com seu token específico
echo "🚀 Iniciando feed DEFAULT com token específico..."
export FEED_ID=default
export BOT_TOKEN_DEFAULT=7819087759:AAEe2FzOA7R-9Q1X2ENZDDFZpWEzba-NYXI
tmux new-session -d -s "listener_default" "export FEED_ID=default && python bot_listener.py"
tmux new-session -d -s "main_default" "export FEED_ID=default && python main_scheduler.py"

echo "✅ Feed DEFAULT iniciado"
echo

# Aguarda um pouco antes de iniciar o segundo feed
echo "⏳ Aguardando 10 segundos antes de iniciar feed_test..."
sleep 10

# Inicia o feed_test com seu token específico
echo "🚀 Iniciando feed FEED_TEST com token específico..."
export FEED_ID=feed_test
export BOT_TOKEN_FEED_TEST=8419247298:AAGvkg7BkswyEO1xH0MAdZHyzNHZ7OFX4Es
tmux new-session -d -s "listener_feed_test" "export FEED_ID=feed_test && python bot_listener.py"
tmux new-session -d -s "main_feed_test" "export FEED_ID=feed_test && python main_scheduler.py"

echo "✅ Feed FEED_TEST iniciado"
echo

echo "🎉 CORREÇÃO CONCLUÍDA!"
echo "======================"
echo
echo "📋 Status dos feeds:"
echo "• DEFAULT: tmux attach -t listener_default"
echo "• FEED_TEST: tmux attach -t listener_feed_test"
echo
echo "🔍 Para verificar se está funcionando:"
echo "tmux list-sessions"
echo
echo "📊 Para ver logs:"
echo "tail -f logs/listener_default.log"
echo "tail -f logs/listener_feed_test.log"
