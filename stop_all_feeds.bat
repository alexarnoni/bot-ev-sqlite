@echo off
echo 🛑 PARANDO TODOS OS FEEDS
echo ========================

echo Parando listener_default...
tmux kill-session -t listener_default 2>nul

echo Parando listener_feed_test...
tmux kill-session -t listener_feed_test 2>nul

echo Parando main_default...
tmux kill-session -t main_default 2>nul

echo Parando main_feed_test...
tmux kill-session -t main_feed_test 2>nul

echo.
echo ✅ Todos os feeds foram parados
echo.
echo Para verificar se não há mais sessões ativas:
echo tmux list-sessions
