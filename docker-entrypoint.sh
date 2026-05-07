#!/bin/bash

echo "Bot EV+ v3.0 - Docker Entrypoint"
echo "================================="

# Carrega variáveis do arquivo .env se existir
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Verifica se as variáveis obrigatórias estão definidas
if [ -z "$ODDS_API_KEY" ]; then
    echo "ERRO: ODDS_API_KEY não definida!"
    exit 1
fi

if [ -z "$BOT_TOKEN_DEFAULT" ]; then
    echo "ERRO: BOT_TOKEN_DEFAULT não definida!"
    exit 1
fi

echo "Configuração carregada:"
echo "  FEED_ID: ${FEED_ID:-default}"
echo "  ODDS_API_KEY: ${ODDS_API_KEY:0:8}..."
echo "  BOT_TOKEN_DEFAULT: ${BOT_TOKEN_DEFAULT:0:8}..."

# Cria diretórios se não existirem
mkdir -p data/global data/default data/feed1 data/feed2 data/feed3 data/feed4 logs

# Inicializa banco de dados se necessário
python -c "
import os
os.environ['FEED_ID'] = 'default'
from src.core.database import get_db
db = get_db()
print('Database inicializado')
"

# Verifica o modo de execução
if [ "$1" = "global" ]; then
    echo "Iniciando sistema global completo..."
    ./start_global_system.sh
elif [ "$1" = "scanner" ]; then
    echo "Iniciando apenas scanner global..."
    python global_scanner.py
elif [ "$1" = "feed" ]; then
    FEED_ID=${2:-default}
    echo "Iniciando feed individual: $FEED_ID"
    export FEED_ID=$FEED_ID
    python main_scheduler.py &
    python bot_listener.py
elif [ "$1" = "test" ]; then
    echo "Executando testes..."
    python -c "
import os
os.environ['FEED_ID'] = 'default'
from src.scanner.global_scanner import GlobalScanner
from src.scanner.main_scheduler import BotScheduler
from src.scanner.scan_cache import get_snapshot_cache
print('Todos os módulos importados com sucesso!')
"
else
    echo "Modos disponíveis:"
    echo "  global  - Sistema global completo (recomendado)"
    echo "  scanner - Apenas scanner global"
    echo "  feed    - Feed individual (ex: feed default)"
    echo "  test    - Executar testes"
    echo ""
    echo "Exemplos:"
    echo "  docker run bot-ev global"
    echo "  docker run bot-ev scanner"
    echo "  docker run bot-ev feed default"
    echo "  docker run bot-ev test"
fi
