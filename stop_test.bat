@echo off
title Parar Bot de Teste

echo ========================================
echo    PARANDO BOT DE TESTE
echo ========================================
echo.

REM Para processos Python relacionados ao bot
echo Parando processos Python...
taskkill /f /im python.exe 2>nul

REM Verifica se ainda há processos
tasklist /fi "imagename eq python.exe" 2>nul | find /i "python.exe" >nul
if %errorlevel%==0 (
    echo Aviso: Ainda ha processos Python rodando
    echo Deseja forcar parada? (s/n)
    set /p choice=
    if /i "%choice%"=="s" (
        taskkill /f /im python.exe
        echo Todos os processos Python parados
    )
) else (
    echo Nenhum processo Python encontrado
)

echo.
echo Bot de teste parado!
echo.
pause
