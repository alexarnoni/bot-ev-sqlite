"""
Script de migração de dados JSON/Pickle/CSV para SQLite
"""
import json
import pickle
import os
import csv
import sys
from typing import Dict, List, Any
from datetime import datetime

from database import Database
from config import get_filters_path, get_cache_dir, get_historico_dir, get_pendentes_dir

def migrate_all(feed_id: str = "default"):
    """Migra todos os dados para SQLite"""
    print(f"🚀 Iniciando migração para feed: {feed_id}")
    
    db = Database(feed_id)
    
    print("📦 Migrando filtros...")
    migrate_filters(db)
    
    print("📦 Migrando cache...")
    migrate_cache(db)
    
    print("📦 Migrando histórico...")
    migrate_history(db)
    
    print("📦 Migrando pendentes...")
    migrate_pending(db)
    
    print("📦 Atualizando catálogo de ligas...")
    update_league_catalog(db)
    
    print("✅ Migração concluída!")
    
    # Mostra estatísticas
    show_migration_stats(db)

def migrate_filters(db: Database):
    """Migra filtros de JSON para SQLite"""
    try:
        filters_path = get_filters_path()
        if not os.path.exists(filters_path):
            print("  ⚠️ Arquivo de filtros não encontrado")
            return
        
        with open(filters_path, 'r', encoding='utf-8') as f:
            filtros = json.load(f)
        
        migrated_count = 0
        for chat_id_str, filtro in filtros.items():
            try:
                chat_id = int(chat_id_str)
                
                # User
                db.create_or_update_user(
                    chat_id,
                    filtro.get('nome'),
                    filtro.get('username')
                )
                
                # Bookmakers
                bookmakers = filtro.get('bookmakers')
                if not bookmakers:
                    # Tenta campo singular (compatibilidade)
                    bk = filtro.get('bookmaker')
                    if bk:
                        bookmakers = [bk]
                
                if bookmakers:
                    db.set_user_bookmakers(chat_id, bookmakers)
                
                # Filters
                db.set_user_filter(
                    chat_id,
                    ev_faixa_min=filtro.get('ev_faixa_min'),
                    ev_faixa_max=filtro.get('ev_faixa_max'),
                    data_inicio=filtro.get('data_inicio'),
                    data_fim=filtro.get('data_fim'),
                    filtro_dias=filtro.get('filtro_dias'),
                    horario_inicio=filtro.get('horario_inicio'),
                    horario_fim=filtro.get('horario_fim')
                )
                
                # Ligas
                ligas = filtro.get('ligas')
                db.set_user_leagues(chat_id, ligas)
                
                # Esportes
                esportes = filtro.get('esportes')
                db.set_user_sports(chat_id, esportes)
                
                migrated_count += 1
                print(f"  ✅ User {chat_id} migrado")
                
            except Exception as e:
                print(f"  ❌ Erro migrando user {chat_id_str}: {e}")
        
        print(f"  📊 {migrated_count} usuários migrados")
    
    except Exception as e:
        print(f"❌ Erro migrando filtros: {e}")

def migrate_cache(db: Database):
    """Migra cache de Pickle para SQLite"""
    cache_dir = get_cache_dir()
    if not os.path.exists(cache_dir):
        print("  ⚠️ Diretório de cache não encontrado")
        return
    
    migrated_count = 0
    total_hashes = 0
    
    for filename in os.listdir(cache_dir):
        if not filename.endswith('.pkl'):
            continue
        
        try:
            # Extrai chat_id do nome do arquivo
            chat_id_str = filename.replace('alert_cache_', '').replace('.pkl', '')
            chat_id = int(chat_id_str)
            
            filepath = os.path.join(cache_dir, filename)
            with open(filepath, 'rb') as f:
                cache = pickle.load(f)
            
            # Converte dict para set se necessário
            if isinstance(cache, dict):
                cache = set(cache.keys())
            elif isinstance(cache, list):
                cache = set(cache)
            
            # Migra hashes para SQLite
            for alert_hash in cache:
                db.add_to_cache(chat_id, alert_hash)
                total_hashes += 1
            
            migrated_count += 1
            print(f"  ✅ Cache {chat_id} migrado ({len(cache)} hashes)")
            
        except Exception as e:
            print(f"  ❌ Erro migrando cache {filename}: {e}")
    
    print(f"  📊 {migrated_count} caches migrados, {total_hashes} hashes totais")

def migrate_history(db: Database):
    """Migra histórico de CSV para SQLite"""
    hist_dir = get_historico_dir()
    if not os.path.exists(hist_dir):
        print("  ⚠️ Diretório de histórico não encontrado")
        return
    
    migrated_count = 0
    total_alerts = 0
    
    for filename in os.listdir(hist_dir):
        if not filename.endswith('.csv'):
            continue
        
        try:
            # Extrai chat_id do nome do arquivo
            chat_id_str = filename.replace('.csv', '')
            chat_id = int(chat_id_str)
            
            filepath = os.path.join(hist_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                
                for row in reader:
                    try:
                        db.add_alert_history(
                            chat_id=chat_id,
                            data_envio=row.get('data_envio', ''),
                            esporte=row.get('esporte', ''),
                            home=row.get('home', ''),
                            away=row.get('away', ''),
                            mercado=row.get('mercado', ''),
                            odd=float(row.get('odd', 0)) if row.get('odd') else 0,
                            stake=float(row.get('stake', 0)) if row.get('stake') else 0,
                            ev=float(row.get('ev', 0)) if row.get('ev') else 0,
                            data_jogo=row.get('data_jogo', ''),
                            url_bet=row.get('url_bet', ''),
                            bookmaker=row.get('bookmaker', '')
                        )
                        count += 1
                        total_alerts += 1
                        
                    except Exception as e:
                        print(f"    ⚠️ Erro na linha {count + 1}: {e}")
                        continue
            
            migrated_count += 1
            print(f"  ✅ Histórico {chat_id} migrado ({count} alertas)")
            
        except Exception as e:
            print(f"  ❌ Erro migrando histórico {filename}: {e}")
    
    print(f"  📊 {migrated_count} históricos migrados, {total_alerts} alertas totais")

def migrate_pending(db: Database):
    """Migra alertas pendentes de JSON para SQLite"""
    pend_dir = get_pendentes_dir()
    if not os.path.exists(pend_dir):
        print("  ⚠️ Diretório de pendentes não encontrado")
        return
    
    migrated_count = 0
    total_pending = 0
    
    for filename in os.listdir(pend_dir):
        if not filename.endswith('.json'):
            continue
        
        try:
            # Extrai chat_id do nome do arquivo
            chat_id_str = filename.replace('.json', '')
            chat_id = int(chat_id_str)
            
            filepath = os.path.join(pend_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                pendentes = json.load(f)
            
            # Migra alertas pendentes
            for evento in pendentes:
                db.add_pending_alert(chat_id, evento)
                total_pending += 1
            
            migrated_count += 1
            print(f"  ✅ Pendentes {chat_id} migrados ({len(pendentes)} alertas)")
            
        except Exception as e:
            print(f"  ❌ Erro migrando pendentes {filename}: {e}")
    
    print(f"  📊 {migrated_count} arquivos de pendentes migrados, {total_pending} alertas totais")

def update_league_catalog(db: Database):
    """Atualiza catálogo de ligas"""
    from utils import LIGAS_POR_REGIAO
    
    try:
        db.update_league_catalog(LIGAS_POR_REGIAO)
        print("  ✅ Catálogo de ligas atualizado")
    except Exception as e:
        print(f"  ❌ Erro atualizando catálogo: {e}")

def show_migration_stats(db: Database):
    """Mostra estatísticas da migração"""
    try:
        print("\n📊 ESTATÍSTICAS DA MIGRAÇÃO:")
        
        # Usuários
        users = db.get_all_users()
        print(f"  👥 Usuários: {len(users)}")
        
        # Bookmakers
        total_bookmakers = 0
        for user in users:
            user_bookmakers = db.get_user_bookmakers(user['chat_id'])
            total_bookmakers += len(user_bookmakers)
        print(f"  📚 Total de bookmakers configurados: {total_bookmakers}")
        
        # Histórico
        system_stats = db.get_system_stats()
        print(f"  📈 Total de alertas no histórico: {system_stats.get('total_alertas', 0)}")
        
        # Cache
        with db.get_connection() as conn:
            cache_count = conn.execute("SELECT COUNT(*) as count FROM alert_cache").fetchone()
            print(f"  💾 Total de hashes no cache: {cache_count['count']}")
        
        # Pendentes
        with db.get_connection() as conn:
            pending_count = conn.execute("SELECT COUNT(*) as count FROM pending_alerts").fetchone()
            print(f"  ⏳ Total de alertas pendentes: {pending_count['count']}")
        
        print("\n✅ Migração concluída com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao mostrar estatísticas: {e}")

def backup_old_files(feed_id: str = "default"):
    """Faz backup dos arquivos antigos"""
    import shutil
    from datetime import datetime
    
    backup_dir = f"backup_{feed_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"📦 Fazendo backup para: {backup_dir}")
    
    # Backup filtros
    filters_path = get_filters_path()
    if os.path.exists(filters_path):
        shutil.copy2(filters_path, os.path.join(backup_dir, "filtros_por_chat.json"))
        print("  ✅ Filtros copiados")
    
    # Backup cache
    cache_dir = get_cache_dir()
    if os.path.exists(cache_dir):
        shutil.copytree(cache_dir, os.path.join(backup_dir, "cache"))
        print("  ✅ Cache copiado")
    
    # Backup histórico
    hist_dir = get_historico_dir()
    if os.path.exists(hist_dir):
        shutil.copytree(hist_dir, os.path.join(backup_dir, "historico_apostas"))
        print("  ✅ Histórico copiado")
    
    # Backup pendentes
    pend_dir = get_pendentes_dir()
    if os.path.exists(pend_dir):
        shutil.copytree(pend_dir, os.path.join(backup_dir, "pendentes"))
        print("  ✅ Pendentes copiados")
    
    print(f"✅ Backup concluído em: {backup_dir}")

if __name__ == "__main__":
    # Parse argumentos
    feed_id = sys.argv[1] if len(sys.argv) > 1 else "default"
    do_backup = "--backup" in sys.argv
    
    print(f"🤖 Bot EV+ - Migração para SQLite")
    print(f"📋 Feed: {feed_id}")
    print(f"💾 Backup: {'Sim' if do_backup else 'Não'}")
    
    if do_backup:
        backup_old_files(feed_id)
    
    # Confirma migração
    resposta = input("\n❓ Continuar com a migração? (s/N): ").lower()
    if resposta not in ['s', 'sim', 'y', 'yes']:
        print("❌ Migração cancelada")
        sys.exit(0)
    
    # Executa migração
    migrate_all(feed_id)
