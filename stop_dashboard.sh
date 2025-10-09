#!/bin/bash

echo "🛑 Bot EV+ - Parando Dashboard Web"
echo "=================================="
echo

# Para a sessão tmux do dashboard
echo "🛑 Parando dashboard..."
tmux kill-session -t "dashboard_web" 2>/dev/null || true

# Aguarda um pouco
sleep 2

# Verifica se parou
if ! tmux has-session -t "dashboard_web" 2>/dev/null; then
    echo "✅ Dashboard parado com sucesso!"
else
    echo "⚠️ Dashboard ainda está rodando"
fi

echo
echo "🔧 Para verificar sessões ativas:"
echo "   tmux list-sessions"
