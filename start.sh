#!/bin/bash

# Bot EV+ - Script de inicialização
# Uso: ./start.sh [feed_id]

# Carrega variáveis do arquivo .env se existir
if [ -f .env ]; then
    echo "📄 Carregando configurações do .env..."
    export $(grep -v '^#' .env | xargs)
fi

FEED_ID=${1:-"default"}
FEEDS=${FEEDS:-"$FEED_ID"}

echo "🤖 Iniciando Bot EV+ (Feed: $FEED_ID)"

# Verifica se as variáveis de ambiente estão configuradas
if [ -z "$BOT_TOKEN_DEFAULT" ] && [ -z "$BOT_TOKEN_FEED1" ] && [ -z "$BOT_TOKEN_FEED2" ]; then
    echo "❌ Erro: Nenhum BOT_TOKEN configurado"
    echo "Configure pelo menos uma das variáveis:"
    echo "  BOT_TOKEN_DEFAULT"
    echo "  BOT_TOKEN_FEED1" 
    echo "  BOT_TOKEN_FEED2"
    exit 1
fi

if [ -z "$ODDS_API_KEY" ]; then
    echo "❌ Erro: ODDS_API_KEY não configurada"
    exit 1
fi

# Cria diretórios necessários
mkdir -p data/$FEED_ID
mkdir -p logs

# Exporta variáveis de ambiente
export FEED_ID=$FEED_ID
export FEEDS=$FEEDS

# Inicia o bot listener
echo "📱 Iniciando bot listener..."
tmux new-session -d -s "listener_$FEED_ID" "python bot_listener.py"

# Inicia o scheduler
echo "⏰ Iniciando scheduler..."
tmux new-session -d -s "main_$FEED_ID" "python main_scheduler.py"

echo "✅ Bot EV+ iniciado com sucesso!"
echo "📋 Feed: $FEED_ID"
echo "🔧 Para ver logs: tmux attach -t listener_$FEED_ID"
echo "⏰ Para ver scheduler: tmux attach -t main_$FEED_ID"
echo "🛑 Para parar: tmux kill-session -t listener_$FEED_ID && tmux kill-session -t main_$FEED_ID"
