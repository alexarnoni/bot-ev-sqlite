#!/bin/bash

echo "📊 Bot EV+ - Monitor do Dashboard"
echo "================================="
echo

# Verifica se o dashboard está rodando
if tmux has-session -t "dashboard_web" 2>/dev/null; then
    echo "✅ Dashboard está rodando!"
    echo
    echo "📊 Acesse: http://localhost:5001"
    echo "🌐 Ou: http://$(hostname -I | awk '{print $1}'):5001"
    echo "🌍 Externo: http://144.22.239.128:5001"
    echo
    echo "🔧 Comandos úteis:"
    echo "   tmux attach -t dashboard_web    # Conectar à sessão"
    echo "   tmux kill-session -t dashboard_web  # Parar dashboard"
    echo "   ./stop_dashboard.sh             # Parar dashboard"
    echo
    echo "📝 Para ver logs do dashboard:"
    echo "   tmux attach -t dashboard_web"
    echo "   (Ctrl+B depois D para sair sem parar)"
else
    echo "❌ Dashboard não está rodando"
    echo
    echo "🚀 Para iniciar:"
    echo "   ./start_dashboard_tmux.sh"
    echo
    echo "📋 Para ver todas as sessões:"
    echo "   tmux list-sessions"
fi

echo
echo "🔄 Sessões tmux ativas:"
tmux list-sessions 2>/dev/null || echo "Nenhuma sessão ativa"
