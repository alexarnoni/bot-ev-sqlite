#!/bin/bash
# Script para carregar variáveis de ambiente do .env

# Carrega o arquivo .env se existir
if [ -f .env ]; then
    echo "📄 Carregando variáveis do .env..."
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ Variáveis carregadas!"
    echo "🔑 ODDS_API_KEY: ${ODDS_API_KEY:0:20}..."
else
    echo "❌ Arquivo .env não encontrado!"
    exit 1
fi
