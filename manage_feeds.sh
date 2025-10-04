#!/bin/bash

echo "========================================"
echo "    GERENCIADOR DE FEEDS - VM"
echo "========================================"
echo

FEEDS=("feed1" "feed2" "feed3" "feed4" "feed5")

show_menu() {
    echo
    echo "Feeds disponíveis:"
    for i in "${!FEEDS[@]}"; do
        echo "$((i+1)). ${FEEDS[i]}"
    done
    echo "6. Todos os feeds"
    echo "7. Sair"
    echo
}

check_feed_status() {
    local feed=$1
    local pid_file="data/$feed/bot.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "Status: RODANDO (PID: $pid)"
        else
            echo "Status: PARADO"
            rm -f "$pid_file"
        fi
    else
        echo "Status: PARADO"
    fi
}

start_feed() {
    local feed=$1
    echo "Iniciando feed: $feed"
    
    mkdir -p "data/$feed"
    mkdir -p "logs/$feed"
    
    nohup bash -c "export FEED_ID=$feed && python3 bot_listener.py" > "logs/$feed/bot.log" 2>&1 &
    local pid=$!
    
    echo $pid > "data/$feed/bot.pid"
    echo "Feed $feed iniciado (PID: $pid)"
}

stop_feed() {
    local feed=$1
    local pid_file="data/$feed/bot.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid"
            echo "Feed $feed parado (PID: $pid)"
        else
            echo "Feed $feed já estava parado"
        fi
        rm -f "$pid_file"
    else
        echo "Feed $feed não está rodando"
    fi
}

restart_feed() {
    local feed=$1
    echo "Reiniciando feed: $feed"
    stop_feed "$feed"
    sleep 2
    start_feed "$feed"
}

view_logs() {
    local feed=$1
    local log_file="logs/$feed/bot.log"
    
    if [ -f "$log_file" ]; then
        echo "Últimas 20 linhas do log do feed $feed:"
        echo "----------------------------------------"
        tail -20 "$log_file"
        echo "----------------------------------------"
        echo
        echo "Deseja ver o log completo? (s/n)"
        read -r choice
        if [ "$choice" = "s" ] || [ "$choice" = "S" ]; then
            less "$log_file"
        fi
    else
        echo "Log não encontrado para o feed $feed"
    fi
}

while true; do
    show_menu
    read -p "Escolha uma opção: " choice
    
    case $choice in
        1|2|3|4|5)
            feed_index=$((choice-1))
            feed=${FEEDS[feed_index]}
            
            echo
            echo "Feed selecionado: $feed"
            check_feed_status "$feed"
            echo
            echo "O que deseja fazer?"
            echo "1. Iniciar"
            echo "2. Parar"
            echo "3. Reiniciar"
            echo "4. Ver logs"
            echo "5. Voltar ao menu"
            echo
            read -p "Escolha: " action
            
            case $action in
                1) start_feed "$feed" ;;
                2) stop_feed "$feed" ;;
                3) restart_feed "$feed" ;;
                4) view_logs "$feed" ;;
                5) continue ;;
                *) echo "Opção inválida" ;;
            esac
            ;;
        6)
            echo
            echo "Gerenciando todos os feeds..."
            echo "1. Iniciar todos"
            echo "2. Parar todos"
            echo "3. Reiniciar todos"
            echo "4. Status de todos"
            echo
            read -p "Escolha: " all_action
            
            case $all_action in
                1)
                    for feed in "${FEEDS[@]}"; do
                        start_feed "$feed"
                        sleep 1
                    done
                    ;;
                2)
                    for feed in "${FEEDS[@]}"; do
                        stop_feed "$feed"
                    done
                    ;;
                3)
                    for feed in "${FEEDS[@]}"; do
                        restart_feed "$feed"
                        sleep 1
                    done
                    ;;
                4)
                    for feed in "${FEEDS[@]}"; do
                        echo "Feed: $feed"
                        check_feed_status "$feed"
                        echo
                    done
                    ;;
                *) echo "Opção inválida" ;;
            esac
            ;;
        7)
            echo "Saindo..."
            exit 0
            ;;
        *)
            echo "Opção inválida"
            ;;
    esac
    
    echo
    read -p "Pressione Enter para continuar..."
done
