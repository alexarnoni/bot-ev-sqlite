#!/bin/bash

echo "🌐 Bot EV+ - Iniciando Dashboard Web em Sessão TMUX"
echo "=================================================="
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

# Para sessão existente se houver
echo "🛑 Parando dashboard existente..."
tmux kill-session -t "dashboard_web" 2>/dev/null || true

# Aguarda um pouco
sleep 2

# Inicia o dashboard em sessão tmux
echo "🚀 Iniciando dashboard em sessão tmux..."
tmux new-session -d -s "dashboard_web" "python3 web_dashboard.py"

# Aguarda um pouco para inicializar
sleep 3

# Verifica se está rodando
if tmux has-session -t "dashboard_web" 2>/dev/null; then
    echo "✅ Dashboard iniciado com sucesso!"
    echo
    echo "📊 Acesse: http://localhost:5001"
    echo "🌐 Ou: http://$(hostname -I | awk '{print $1}'):5001"
    echo "🌍 Externo: http://144.22.239.128:5001"
    echo
    echo "🔧 Comandos úteis:"
    echo "   tmux attach -t dashboard_web    # Conectar à sessão"
    echo "   tmux kill-session -t dashboard_web  # Parar dashboard"
    echo "   tmux list-sessions              # Ver sessões ativas"
    echo
    echo "💡 Agora você pode fechar a VM que o dashboard continuará rodando!"
else
    echo "❌ Erro ao iniciar dashboard"
    exit 1
fi
