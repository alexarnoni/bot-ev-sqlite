#!/bin/bash

echo "🔍 DEBUG - Verificando Status dos Feeds"
echo "======================================"
echo

# Lista de feeds
FEEDS=("default" "feed1" "feed2" "feed3" "feed4" "feed_test")

echo "📊 Sessões tmux ativas:"
tmux list-sessions
echo

echo "📊 Processos Python:"
ps aux | grep python | grep -v grep
echo

echo "📊 Status detalhado por feed:"
for feed in "${FEEDS[@]}"; do
    echo "🔸 Feed: $feed"
    
    # Verifica listener
    if tmux has-session -t "listener_$feed" 2>/dev/null; then
        echo "  📱 Listener: ✅ ATIVO"
        # Verifica se o processo está realmente rodando
        listener_pid=$(tmux list-panes -t "listener_$feed" -F "#{pane_pid}" 2>/dev/null | head -1)
        if [ -n "$listener_pid" ]; then
            if ps -p "$listener_pid" > /dev/null 2>&1; then
                echo "    PID: $listener_pid (rodando)"
            else
                echo "    PID: $listener_pid (parado)"
            fi
        fi
    else
        echo "  📱 Listener: ❌ INATIVO"
    fi
    
    # Verifica scheduler
    if tmux has-session -t "main_$feed" 2>/dev/null; then
        echo "  ⏰ Scheduler: ✅ ATIVO"
        # Verifica se o processo está realmente rodando
        scheduler_pid=$(tmux list-panes -t "main_$feed" -F "#{pane_pid}" 2>/dev/null | head -1)
        if [ -n "$scheduler_pid" ]; then
            if ps -p "$scheduler_pid" > /dev/null 2>&1; then
                echo "    PID: $scheduler_pid (rodando)"
            else
                echo "    PID: $scheduler_pid (parado)"
            fi
        fi
    else
        echo "  ⏰ Scheduler: ❌ INATIVO"
    fi
    
    # Verifica banco
    if [ -f "data/$feed/bot.db" ]; then
        echo "  🗄️ Banco: ✅ EXISTE"
    else
        echo "  🗄️ Banco: ❌ NÃO EXISTE"
    fi
    
    echo
done

echo "🔧 Testando início manual de um scheduler:"
echo "Tentando iniciar scheduler para default..."
tmux new-session -d -s "test_scheduler" "export FEED_ID=default && python3 main_scheduler.py"
sleep 3

if tmux has-session -t "test_scheduler" 2>/dev/null; then
    echo "✅ Teste de scheduler funcionou!"
    tmux kill-session -t "test_scheduler" 2>/dev/null
else
    echo "❌ Teste de scheduler falhou!"
fi

echo
echo "📋 Para ver logs de erro:"
echo "tmux attach -t listener_default"
echo "tmux attach -t main_default"
