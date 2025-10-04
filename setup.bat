@echo off
echo ========================================
echo    SETUP BOT EV+ SQLITE
echo ========================================
echo.

REM Verifica se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado!
    echo Instale o Python 3.11+ primeiro.
    pause
    exit /b 1
)

echo Python encontrado!
python --version
echo.

REM Verifica se ambiente virtual já existe
if exist "venv\Scripts\activate.bat" (
    echo Ambiente virtual ja existe!
    echo Usando ambiente existente...
) else (
    echo Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 (
        echo ERRO: Falha ao criar ambiente virtual!
        pause
        exit /b 1
    )
)

REM Ativa ambiente virtual
echo Ativando ambiente virtual...
call venv\Scripts\activate.bat

REM Instala dependencias
echo Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERRO: Falha ao instalar dependencias!
    pause
    exit /b 1
)

REM Cria diretorios necessarios
echo Criando diretorios...
if not exist "data" mkdir "data"
if not exist "data\feed_test" mkdir "data\feed_test"
if not exist "logs" mkdir "logs"

REM Copia .env de exemplo se nao existir
if not exist ".env" (
    echo Criando arquivo .env...
    copy env.example .env
    echo.
    echo IMPORTANTE: Configure o .env com seus tokens!
    echo Edite o arquivo .env e adicione:
    echo - TELEGRAM_TOKEN_FEED_TEST=seu_token_aqui
    echo - ODDS_API_KEY=sua_chave_api_aqui
    echo.
)

echo.
echo ========================================
echo    SETUP CONCLUIDO COM SUCESSO!
echo ========================================
echo.
echo Proximos passos:
echo 1. Configure o arquivo .env com seus tokens
echo 2. Execute run_test.bat para testar
echo 3. Execute start_bot.bat para iniciar o bot
echo.
pause
