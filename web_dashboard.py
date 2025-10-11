#!/usr/bin/env python3
"""
Dashboard Web para Monitoramento do Bot EV+
Permite monitorar o bot pelo navegador sem precisar acessar a VM
"""

import os
import sys
import json
import sqlite3
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import psutil

# Configuração
app = Flask(__name__)
CORS(app)

# Configurações
FEED_ID = os.getenv("FEED_ID", "default")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8080"))
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")

def get_database_path():
    """Retorna o caminho do banco de dados"""
    return os.path.join(os.getcwd(), "data", FEED_ID, "bot.db")

def get_logs_path():
    """Retorna o caminho dos logs"""
    return os.path.join(os.getcwd(), "logs")

class BotMonitor:
    """Classe para monitorar o bot"""
    
    def __init__(self):
        self.db_path = get_database_path()
        self.logs_path = get_logs_path()
    
    def get_database_connection(self):
        """Conecta ao banco de dados"""
        try:
            return sqlite3.connect(self.db_path)
        except Exception as e:
            print(f"Erro ao conectar ao banco: {e}")
            return None
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do sistema"""
        try:
            # CPU e Memória
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Processos Python
            python_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'cmdline']):
                try:
                    if 'python' in proc.info['name'].lower():
                        cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                        if 'bot_listener.py' in cmdline or 'main_scheduler.py' in cmdline:
                            python_processes.append({
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'cpu_percent': proc.info['cpu_percent'],
                                'memory_percent': proc.info['memory_percent'],
                                'cmdline': cmdline
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_gb': round(memory.used / (1024**3), 2),
                'memory_total_gb': round(memory.total / (1024**3), 2),
                'disk_percent': disk.percent,
                'disk_used_gb': round(disk.used / (1024**3), 2),
                'disk_total_gb': round(disk.total / (1024**3), 2),
                'python_processes': python_processes
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_users_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas dos usuários"""
        conn = self.get_database_connection()
        if not conn:
            return {'error': 'Não foi possível conectar ao banco'}
        
        try:
            cursor = conn.cursor()
            
            # Total de usuários
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Usuários ativos
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
            active_users = cursor.fetchone()[0]
            
            # Usuários configurados
            cursor.execute("""
                SELECT COUNT(*) FROM users u
                JOIN user_filters uf ON u.chat_id = uf.chat_id
                WHERE u.is_active = 1
            """)
            configured_users = cursor.fetchone()[0]
            
            # Últimos usuários registrados
            cursor.execute("""
                SELECT chat_id, nome, created_at, is_active
                FROM users
                ORDER BY created_at DESC
                LIMIT 10
            """)
            recent_users = cursor.fetchall()
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'configured_users': configured_users,
                'recent_users': [
                    {
                        'chat_id': user[0],
                        'nome': user[1],
                        'created_at': user[2],
                        'is_active': bool(user[3])
                    }
                    for user in recent_users
                ]
            }
        except Exception as e:
            return {'error': str(e)}
        finally:
            conn.close()
    
    def get_alerts_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas dos alertas"""
        conn = self.get_database_connection()
        if not conn:
            return {'error': 'Não foi possível conectar ao banco'}
        
        try:
            cursor = conn.cursor()
            
            # Alertas hoje
            cursor.execute("""
                SELECT COUNT(*) FROM alert_history
                WHERE DATE(data_envio) = DATE('now')
            """)
            alerts_today = cursor.fetchone()[0]
            
            # Alertas esta semana
            cursor.execute("""
                SELECT COUNT(*) FROM alert_history
                WHERE data_envio >= datetime('now', '-7 days')
            """)
            alerts_week = cursor.fetchone()[0]
            
            # Alertas por esporte (hoje)
            cursor.execute("""
                SELECT esporte, COUNT(*) as count
                FROM alert_history
                WHERE DATE(data_envio) = DATE('now')
                GROUP BY esporte
                ORDER BY count DESC
                LIMIT 10
            """)
            alerts_by_sport = cursor.fetchall()
            
            # Últimos alertas
            cursor.execute("""
                SELECT chat_id, esporte, home, away, odd, ev, data_envio
                FROM alert_history
                ORDER BY data_envio DESC
                LIMIT 20
            """)
            recent_alerts = cursor.fetchall()
            
            return {
                'alerts_today': alerts_today,
                'alerts_week': alerts_week,
                'alerts_by_sport': [
                    {'esporte': sport[0], 'count': sport[1]}
                    for sport in alerts_by_sport
                ],
                'recent_alerts': [
                    {
                        'chat_id': alert[0],
                        'esporte': alert[1],
                        'home': alert[2],
                        'away': alert[3],
                        'odd': alert[4],
                        'ev': alert[5],
                        'data_envio': alert[6]
                    }
                    for alert in recent_alerts
                ]
            }
        except Exception as e:
            return {'error': str(e)}
        finally:
            conn.close()
    
    def get_feeds_status(self) -> Dict[str, Any]:
        """Retorna status dos feeds"""
        feeds = ["default", "feed1", "feed2", "feed3", "feed4", "feed_test"]
        feeds_status = {}
        
        for feed in feeds:
            try:
                # Verifica se há processos tmux rodando
                import subprocess
                result = subprocess.run(
                    ['tmux', 'list-sessions', '-F', '#{session_name}'],
                    capture_output=True, text=True, timeout=5
                )
                
                listener_running = f"listener_{feed}" in result.stdout
                scheduler_running = f"main_{feed}" in result.stdout
                
                # Verifica se há banco de dados
                feed_db_path = os.path.join(os.getcwd(), "data", feed, "bot.db")
                db_exists = os.path.exists(feed_db_path)
                
                # Conta usuários no feed
                user_count = 0
                if db_exists:
                    try:
                        conn = sqlite3.connect(feed_db_path)
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
                        user_count = cursor.fetchone()[0]
                        conn.close()
                    except:
                        pass
                
                feeds_status[feed] = {
                    'listener_running': listener_running,
                    'scheduler_running': scheduler_running,
                    'db_exists': db_exists,
                    'user_count': user_count,
                    'status': 'active' if (listener_running and scheduler_running) else 'inactive'
                }
                
            except Exception as e:
                feeds_status[feed] = {
                    'listener_running': False,
                    'scheduler_running': False,
                    'db_exists': False,
                    'user_count': 0,
                    'status': 'error',
                    'error': str(e)
                }
        
        return feeds_status
    
    def get_recent_logs(self, lines: int = 50) -> List[str]:
        """Retorna logs recentes"""
        try:
            log_file = os.path.join(self.logs_path, f"listener_{FEED_ID}.log")
            if not os.path.exists(log_file):
                return ["Log file not found"]
            
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return all_lines[-lines:] if len(all_lines) > lines else all_lines
        except Exception as e:
            return [f"Error reading logs: {str(e)}"]
    
    def get_global_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas globais de todos os feeds"""
        feeds = ["default", "feed1", "feed2", "feed3", "feed4", "feed_test"]
        
        # Coleta dados de todos os feeds
        all_users = set()
        all_alerts = 0
        feed_stats = {}
        
        for feed in feeds:
            feed_db_path = os.path.join(os.getcwd(), "data", feed, "bot.db")
            if os.path.exists(feed_db_path):
                try:
                    conn = sqlite3.connect(feed_db_path)
                    cursor = conn.cursor()
                    
                    # Usuários ativos
                    cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
                    active_users = cursor.fetchone()[0]
                    
                    # Usuários únicos (chat_ids)
                    cursor.execute("SELECT chat_id FROM users WHERE is_active = 1")
                    for row in cursor.fetchall():
                        all_users.add(row[0])
                    
                    # Alertas hoje
                    today = datetime.now().strftime('%Y-%m-%d')
                    cursor.execute("SELECT COUNT(*) FROM alert_history WHERE DATE(data_envio) = ?", (today,))
                    alerts_today = cursor.fetchone()[0]
                    all_alerts += alerts_today
                    
                    # Status dos processos
                    import subprocess
                    result = subprocess.run(
                        ['tmux', 'list-sessions', '-F', '#{session_name}'],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    listener_running = f"listener_{feed}" in result.stdout
                    scheduler_running = f"main_{feed}" in result.stdout
                    
                    feed_stats[feed] = {
                        'active_users': active_users,
                        'alerts_today': alerts_today,
                        'listener_running': listener_running,
                        'scheduler_running': scheduler_running,
                        'status': 'active' if (listener_running and scheduler_running) else 'inactive'
                    }
                    
                    conn.close()
                except Exception as e:
                    feed_stats[feed] = {
                        'active_users': 0,
                        'alerts_today': 0,
                        'listener_running': False,
                        'scheduler_running': False,
                        'status': 'error',
                        'error': str(e)
                    }
            else:
                feed_stats[feed] = {
                    'active_users': 0,
                    'alerts_today': 0,
                    'listener_running': False,
                    'scheduler_running': False,
                    'status': 'no_db'
                }
        
        return {
            'total_feeds': len(feeds),
            'active_feeds': sum(1 for f in feed_stats.values() if f['status'] == 'active'),
            'unique_users': len(all_users),
            'total_alerts_today': all_alerts,
            'feed_stats': feed_stats
        }
    
    def get_analytics_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas analíticas"""
        feeds = ["default", "feed1", "feed2", "feed3", "feed4", "feed_test"]
        
        # Coleta dados de todos os feeds
        all_leagues = {}
        all_bookmakers = {}
        all_hours = {}
        
        for feed in feeds:
            feed_db_path = os.path.join(os.getcwd(), "data", feed, "bot.db")
            if os.path.exists(feed_db_path):
                try:
                    conn = sqlite3.connect(feed_db_path)
                    cursor = conn.cursor()
                    
                    # Top esportes (substitui ligas)
                    cursor.execute("""
                        SELECT esporte, COUNT(*) as count 
                        FROM alert_history 
                        WHERE DATE(data_envio) >= DATE('now', '-7 days')
                        GROUP BY esporte 
                        ORDER BY count DESC 
                        LIMIT 10
                    """)
                    for esporte, count in cursor.fetchall():
                        all_leagues[esporte or 'Desconhecido'] = all_leagues.get(esporte or 'Desconhecido', 0) + count
                    
                    # Top bookmakers
                    cursor.execute("""
                        SELECT bookmaker, COUNT(*) as count 
                        FROM alert_history 
                        WHERE DATE(data_envio) >= DATE('now', '-7 days')
                        GROUP BY bookmaker 
                        ORDER BY count DESC 
                        LIMIT 10
                    """)
                    for bookmaker, count in cursor.fetchall():
                        all_bookmakers[bookmaker or 'Desconhecido'] = all_bookmakers.get(bookmaker or 'Desconhecido', 0) + count
                    
                    # Análise de horários
                    cursor.execute("""
                        SELECT strftime('%H', data_envio) as hour, COUNT(*) as count 
                        FROM alert_history 
                        WHERE DATE(data_envio) >= DATE('now', '-7 days')
                        GROUP BY hour 
                        ORDER BY hour
                    """)
                    for hour, count in cursor.fetchall():
                        all_hours[hour] = all_hours.get(hour, 0) + count
                    
                    conn.close()
                except Exception as e:
                    print(f"Erro ao analisar feed {feed}: {e}")
        
        return {
            'top_esportes': sorted(all_leagues.items(), key=lambda x: x[1], reverse=True)[:10],
            'top_bookmakers': sorted(all_bookmakers.items(), key=lambda x: x[1], reverse=True)[:10],
            'hourly_distribution': dict(sorted(all_hours.items()))
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Retorna configurações atuais do .env"""
        config = {}
        env_file = os.path.join(os.getcwd(), '.env')
        
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            config[key] = value
            except Exception as e:
                print(f"Erro ao ler .env: {e}")
        
        # Configurações padrão se não existirem
        default_config = {
            'ODDS_API_KEY': '',
            'TELEGRAM_BOT_TOKEN': '',
            'FEED_ID': 'default',
            'DASHBOARD_PORT': '8080',
            'DASHBOARD_HOST': '0.0.0.0',
            'SCAN_INTERVAL': '120',
            'MAX_ALERTS_PER_DAY': '50',
            'DEFAULT_EV_MIN': '0.05',
            'DEFAULT_EV_MAX': '1.0'
        }
        
        # Merge com padrões
        for key, default_value in default_config.items():
            if key not in config:
                config[key] = default_value
        
        return config
    
    def save_config(self, new_config: Dict[str, str]) -> Dict[str, Any]:
        """Salva configurações no .env"""
        try:
            env_file = os.path.join(os.getcwd(), '.env')
            
            # Faz backup do .env atual
            if os.path.exists(env_file):
                backup_file = f"{env_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                import shutil
                shutil.copy2(env_file, backup_file)
            
            # Escreve novo .env
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write("# Configurações do Bot EV+\n")
                f.write("# Gerado automaticamente pelo dashboard\n\n")
                
                for key, value in new_config.items():
                    if value:  # Só salva valores não vazios
                        f.write(f"{key}={value}\n")
            
            return {'success': True, 'message': 'Configurações salvas com sucesso!'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

# Instância global do monitor
monitor = BotMonitor()

@app.route('/')
def dashboard():
    """Página principal do dashboard"""
    return render_template('dashboard.html')

@app.route('/api/stats/system')
def api_system_stats():
    """API para estatísticas do sistema"""
    return jsonify(monitor.get_system_stats())

@app.route('/api/stats/users')
def api_users_stats():
    """API para estatísticas dos usuários"""
    return jsonify(monitor.get_users_stats())

@app.route('/api/stats/alerts')
def api_alerts_stats():
    """API para estatísticas dos alertas"""
    return jsonify(monitor.get_alerts_stats())

@app.route('/api/stats/feeds')
def api_feeds_stats():
    """API para status dos feeds"""
    return jsonify(monitor.get_feeds_status())

@app.route('/api/logs')
def api_logs():
    """API para logs recentes"""
    lines = request.args.get('lines', 50, type=int)
    return jsonify({'logs': monitor.get_recent_logs(lines)})

@app.route('/api/stats/global')
def api_global_stats():
    """API para estatísticas globais de todos os feeds"""
    return jsonify(monitor.get_global_stats())

@app.route('/api/stats/analytics')
def api_analytics_stats():
    """API para estatísticas analíticas"""
    return jsonify(monitor.get_analytics_stats())

@app.route('/api/actions/start_feed', methods=['POST'])
def api_start_feed():
    """API para iniciar um feed"""
    try:
        data = request.get_json()
        feed_id = data.get('feed_id')
        
        if not feed_id:
            return jsonify({'error': 'Feed ID é obrigatório'}), 400
        
        import subprocess
        import platform
        
        # Detecta o sistema operacional e usa o script correto
        if platform.system() == 'Windows':
            # Windows - usa PowerShell
            result = subprocess.run(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-File', 'start_feed.ps1', feed_id],
                capture_output=True, text=True, timeout=30
            )
        else:
            # Linux/Unix - usa shell script
            result = subprocess.run(
                [f'./start_feed.sh', feed_id],
                capture_output=True, text=True, timeout=30
            )
        
        if result.returncode == 0:
            return jsonify({'message': f'Feed {feed_id} iniciado com sucesso'})
        else:
            return jsonify({'error': f'Erro ao iniciar feed: {result.stderr}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/actions/stop_feed', methods=['POST'])
def api_stop_feed():
    """API para parar um feed"""
    try:
        data = request.get_json()
        feed_id = data.get('feed_id')
        
        if not feed_id:
            return jsonify({'error': 'Feed ID é obrigatório'}), 400
        
        import subprocess
        import platform
        
        # Detecta o sistema operacional e usa o script correto
        if platform.system() == 'Windows':
            # Windows - usa PowerShell
            result = subprocess.run(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-File', 'stop_feed.ps1', feed_id],
                capture_output=True, text=True, timeout=30
            )
        else:
            # Linux/Unix - usa shell script
            result = subprocess.run(
                [f'./stop_feed.sh', feed_id],
                capture_output=True, text=True, timeout=30
            )
        
        if result.returncode == 0:
            return jsonify({'message': f'Feed {feed_id} parado com sucesso'})
        else:
            return jsonify({'error': f'Erro ao parar feed: {result.stderr}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/actions/restart_feed', methods=['POST'])
def api_restart_feed():
    """API para reiniciar um feed"""
    try:
        data = request.get_json()
        feed = data.get('feed', 'default')
        
        # Para o feed
        import subprocess
        subprocess.run(['tmux', 'kill-session', '-t', f'listener_{feed}'], 
                      capture_output=True, timeout=10)
        subprocess.run(['tmux', 'kill-session', '-t', f'main_{feed}'], 
                      capture_output=True, timeout=10)
        
        # Inicia o feed
        import platform
        if platform.system() == 'Windows':
            subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', 'start_all_feeds.sh'], 
                          capture_output=True, timeout=30)
        else:
            subprocess.run(['./start_all_feeds.sh'], 
                          capture_output=True, timeout=30)
        
        return jsonify({'success': True, 'message': f'Feed {feed} reiniciado'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/actions/restart_all', methods=['POST'])
def api_restart_all():
    """API para reiniciar todos os feeds"""
    try:
        import subprocess
        import platform
        
        if platform.system() == 'Windows':
            result = subprocess.run(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-File', 'stop_all_feeds.sh'],
                capture_output=True, text=True, timeout=60
            )
            
            import time
            time.sleep(3)
            
            result2 = subprocess.run(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-File', 'start_all_feeds.sh'],
                capture_output=True, text=True, timeout=60
            )
        else:
            result = subprocess.run(
                ['./stop_all_feeds.sh'],
                capture_output=True, text=True, timeout=60
            )
            
            import time
            time.sleep(3)
            
            result2 = subprocess.run(
                ['./start_all_feeds.sh'],
                capture_output=True, text=True, timeout=60
            )
        
        if result2.returncode == 0:
            return jsonify({'message': 'Todos os feeds reiniciados com sucesso'})
        else:
            return jsonify({'error': f'Erro ao reiniciar feeds: {result2.stderr}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/actions/clear_cache', methods=['POST'])
def api_clear_cache():
    """API para limpar cache de alertas"""
    try:
        import subprocess
        result = subprocess.run(
            ['find', 'cache', '-name', '*.cache', '-delete'],
            capture_output=True, text=True, timeout=30
        )
        
        return jsonify({'message': 'Cache limpo com sucesso'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/actions/backup_db', methods=['POST'])
def api_backup_db():
    """API para fazer backup do banco de dados"""
    try:
        data = request.get_json()
        feed_id = data.get('feed_id', 'default')
        
        import shutil
        from datetime import datetime
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        source_db = os.path.join(os.getcwd(), "data", feed_id, "bot.db")
        backup_path = os.path.join(os.getcwd(), "backups", f"bot_{feed_id}_{timestamp}.db")
        
        # Cria diretório de backup se não existir
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        shutil.copy2(source_db, backup_path)
        
        return jsonify({'message': f'Backup criado: {backup_path}'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/get')
def api_get_config():
    """API para obter configurações atuais"""
    return jsonify(monitor.get_config())

@app.route('/api/config/save', methods=['POST'])
def api_save_config():
    """API para salvar configurações"""
    try:
        data = request.get_json()
        result = monitor.save_config(data)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print(f"🚀 Iniciando Dashboard Web...")
    print(f"📊 Acesse: http://localhost:{DASHBOARD_PORT}")
    print(f"🌐 Ou: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    print(f"🌍 Externo: http://144.22.239.128:{DASHBOARD_PORT}")
    print(f"📁 Feed: {FEED_ID}")
    
    app.run(
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
        debug=False,
        threaded=True
    )
