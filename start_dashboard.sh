#!/bin/bash

echo "🌐 Bot EV+ - Iniciando Dashboard Web"
echo "===================================="
echo

# Carrega variáveis do arquivo .env se existir
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Ativa a venv se existir
if [ -d "venv" ]; then
    echo "🐍 Ativando venv..."
    source venv/bin/activate
    echo "✅ Venv ativada!"
else
    echo "⚠️ Venv não encontrada, usando Python do sistema"
fi

# Instala dependências do dashboard se necessário
echo "📦 Verificando dependências do dashboard..."
pip install -r requirements_dashboard.txt --quiet

echo "🚀 Iniciando dashboard web..."
echo "📊 Acesse: http://localhost:5000"
echo "🌐 Ou: http://$(hostname -I | awk '{print $1}'):5000"
echo

# Inicia o dashboard
python3 web_dashboard.py
