#!/bin/bash

echo "========================================"
echo "    PARANDO TODOS OS FEEDS"
echo "========================================"
echo

FEEDS=("feed1" "feed2" "feed3" "feed4" "feed5")

# Para todos os feeds
for feed in "${FEEDS[@]}"; do
    pid_file="data/$feed/bot.pid"
    
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "Parando feed $feed (PID: $pid)..."
            kill "$pid"
            sleep 1
            
            # Verifica se ainda está rodando
            if ps -p "$pid" > /dev/null 2>&1; then
                echo "Forçando parada do feed $feed..."
                kill -9 "$pid"
            fi
            
            echo "Feed $feed parado"
        else
            echo "Feed $feed já estava parado"
        fi
        rm -f "$pid_file"
    else
        echo "Feed $feed não estava rodando"
    fi
done

echo
echo "Verificando processos Python restantes..."
python_pids=$(pgrep -f "bot_listener.py")
if [ -n "$python_pids" ]; then
    echo "Processos Python ainda rodando: $python_pids"
    echo "Deseja forçar parada de todos os processos Python? (s/n)"
    read -r choice
    if [ "$choice" = "s" ] || [ "$choice" = "S" ]; then
        pkill -f "bot_listener.py"
        echo "Todos os processos Python parados"
    fi
else
    echo "Nenhum processo Python rodando"
fi

echo
echo "Todos os feeds foram parados!"
