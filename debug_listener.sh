#!/bin/bash

echo "🔍 DIAGNÓSTICO DETALHADO DOS LISTENERS"
echo "====================================="

# Verificar se o bot_listener.py tem erros de sintaxe
echo "📝 Verificando sintaxe do bot_listener.py..."
python3 -m py_compile bot_listener.py
if [ $? -eq 0 ]; then
    echo "✅ Sintaxe OK"
else
    echo "❌ ERRO DE SINTAXE no bot_listener.py"
    echo "Executando para ver o erro:"
    python3 bot_listener.py
fi

echo ""
echo "📦 Verificando dependências..."
python3 -c "
try:
    import telegram
    print('✅ telegram OK')
except ImportError as e:
    print(f'❌ telegram: {e}')

try:
    import asyncio
    print('✅ asyncio OK')
except ImportError as e:
    print(f'❌ asyncio: {e}')

try:
    from config import get_telegram_token
    print('✅ config OK')
except ImportError as e:
    print(f'❌ config: {e}')

try:
    from bot_ev import enviar_alerta
    print('✅ bot_ev OK')
except ImportError as e:
    print(f'❌ bot_ev: {e}')
"

echo ""
echo "🧪 Testando execução manual do listener..."
echo "Tentando executar: export FEED_ID=default && python3 bot_listener.py"
echo "Pressione Ctrl+C para parar após 10 segundos"

timeout 10s bash -c "export FEED_ID=default && python3 bot_listener.py" || echo "Timeout ou erro na execução"

echo ""
echo "📊 Verificando sessões tmux ativas:"
tmux list-sessions

echo ""
echo "🔧 Para tentar iniciar manualmente:"
echo "tmux new-session -d -s listener_default 'export FEED_ID=default && python3 bot_listener.py'"
echo "tmux attach -t listener_default"
