#!/bin/bash
# Script para iniciar o feed americano no Linux/Mac
# Define o feed_id e inicia o bot

echo "🇺🇸 Iniciando American Sports Feed..."

# Define variáveis de ambiente
export FEED_ID="feed_american"

# Verifica se o token está configurado
if [ -z "$BOT_TOKEN_FEED_AMERICAN" ]; then
    echo "❌ BOT_TOKEN_FEED_AMERICAN não configurado!"
    echo "Configure a variável de ambiente BOT_TOKEN_FEED_AMERICAN"
    echo "Exemplo: export BOT_TOKEN_FEED_AMERICAN='seu_token_aqui'"
    exit 1
fi

# Verifica se a API key está configurada
if [ -z "$ODDS_API_KEY" ]; then
    echo "❌ ODDS_API_KEY não configurada!"
    echo "Configure a variável de ambiente ODDS_API_KEY"
    exit 1
fi

echo "✅ Variáveis de ambiente configuradas"
echo "📊 Feed ID: $FEED_ID"
echo "🤖 Token: ${BOT_TOKEN_FEED_AMERICAN:0:8}..."

# Inicia o bot
echo "🚀 Iniciando bot..."
python3 bot_listener.py
