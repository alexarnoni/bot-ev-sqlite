#!/bin/bash
# Script para carregar variáveis de ambiente do .env e ativar venv

# Ativa a venv se existir
if [ -d "venv" ]; then
    echo "🐍 Ativando venv..."
    source venv/bin/activate
    echo "✅ Venv ativada!"
else
    echo "⚠️ Venv não encontrada, usando Python do sistema"
fi

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
