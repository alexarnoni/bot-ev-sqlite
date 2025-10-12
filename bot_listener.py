import os
import logging
import html
from pathlib import Path
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters

from api_client import OddsAPI
from bookmaker_config import usuario_configurado
from config import (
    get_listener_log_path,
    get_telegram_token,
)
from database import get_db
# from filtros import validar_filtros  # REMOVIDO - agora usa SQLite diretamente
from math import ceil
from rate_limiter import api_rate_limiter
from scanner import scan_apostas_usuario
from scanner import scan_apostas
from status import get_odds_api_status
from utils import carregar_catalogo_ligas, TRADUCAO_ESPORTE_EN

BOOKMAKERS_POR_PAGINA = 30

# Configurar logging (arquivo + terminal)
LISTENER_LOG_PATH = get_listener_log_path()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LISTENER_LOG_PATH, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logging.info("🔊 bot_listener.py iniciado.")

# Carregar variáveis de ambiente
load_dotenv()
TELEGRAM_TOKEN = get_telegram_token()
# Usar ADMIN_USERS do config.py que já está configurado
from config import ADMIN_USERS
ADMIN_CHAT_ID = str(ADMIN_USERS[0]) if ADMIN_USERS else None

db = get_db()


def _fetch_alert_history(chat_id: str) -> list[dict[str, object]]:
    try:
        history = db.get_user_history(int(chat_id))
    except Exception as exc:
        logging.error("Erro ao carregar histórico do chat %s: %s", chat_id, exc)
        return []

    alertas: list[dict[str, object]] = []
    for row in history:
        # Campos do schema novo: data_envio, home, away, ev, bookmaker, odd, stake
        data_envio = row.get("data_envio")
        try:
            if isinstance(data_envio, str):
                datetime.fromisoformat(data_envio)
        except ValueError:
            data_envio = None

        alertas.append(
            {
                "data_envio": data_envio,
                "home": row.get("home"),
                "away": row.get("away"),
                "ev": row.get("ev"),
                "bookmaker": row.get("bookmaker"),
                "league": row.get("league"),
                "odds": row.get("odd"),
                "stake": row.get("stake"),
            }
        )

    return alertas


def _count_user_alerts(chat_id: str) -> int:
    try:
        return db.count_user_alerts(int(chat_id))
    except Exception as exc:
        logging.error("Erro ao contar alertas do chat %s: %s", chat_id, exc)
        return 0


def _count_alerts_on_date(target_date: datetime.date) -> int:
    try:
        return db.count_alerts_on_date(target_date)
    except Exception as exc:
        logging.error("Erro ao contar alertas do dia %s: %s", target_date, exc)
        return 0


def _count_api_cache_entries() -> int:
    try:
        return db.count_api_cache_entries()
    except Exception as exc:
        logging.error("Erro ao consultar quantidade de cache: %s", exc)
        return 0

def is_admin(chat_id):
    """Verifica se o usuário é admin"""
    return str(chat_id) == ADMIN_CHAT_ID

# ----- Migração de banco legado (bot.sqlite3) para schema normalizado -----
def migrar_banco_legado_se_preciso():
    """Se existir bot.sqlite3 (legado) e o banco normalizado estiver vazio, migra os filtros."""
    try:
        legacy_path = Path("bot.sqlite3")
        # Se não existe banco legado, nada a fazer
        if not legacy_path.exists():
            return 0
        # Se já existem usuários no banco novo, não migrar
        if db.get_all_users():
            return 0
        import sqlite3 as _sqlite3
        import json as _json
        migrated = 0
        with _sqlite3.connect(str(legacy_path)) as lconn:
            lconn.row_factory = _sqlite3.Row
            rows = lconn.execute(
                "SELECT chat_id, filter_data, nome, username FROM users"
            ).fetchall()
            temp: dict[str, dict] = {}
            for row in rows:
                chat_id = str(row["chat_id"]) if row["chat_id"] is not None else None
                if not chat_id:
                    continue
                filtros = {}
                if row.get("filter_data"):
                    try:
                        filtros = _json.loads(row["filter_data"]) or {}
                    except Exception:
                        filtros = {}
                if row.get("nome"):
                    filtros["nome"] = row["nome"]
                if row.get("username"):
                    filtros["username"] = row["username"]
                temp[chat_id] = filtros
            # Persiste via API normalizada
            for chat_id, filtros in temp.items():
                cid = int(chat_id)
                db.create_or_update_user(cid, filtros.get("nome"), filtros.get("username"))
                bks = filtros.get("bookmakers") or ([filtros.get("bookmaker")] if filtros.get("bookmaker") else [])
                db.set_user_bookmakers(cid, bks)
                db.set_user_leagues(cid, filtros.get("ligas"))
                db.set_user_sports(cid, filtros.get("esportes"))
                db.set_user_filter(
                    cid,
                    ev_faixa_min=filtros.get("ev_faixa_min"),
                    ev_faixa_max=filtros.get("ev_faixa_max"),
                    filtro_dias=filtros.get("filtro_dias"),
                    data_inicio=filtros.get("data_inicio"),
                    data_fim=filtros.get("data_fim"),
                    horario_inicio=filtros.get("horario_inicio"),
                    horario_fim=filtros.get("horario_fim"),
                )
                migrated += 1
        logging.info(f"✅ Migração de banco legado concluída: {migrated} usuários migrados")
        return migrated
    except Exception as exc:
        logging.error(f"❌ Erro na migração do banco legado: {exc}")
        return 0

# ----- Carregar filtros diretamente do banco normalizado -----
def carregar_filtros_startup():
    """Carrega filtros a partir do schema normalizado"""
    logging.info("🔍 Carregamento de filtros do banco normalizado...")
    try:
        filtros: dict[str, dict] = {}
        # Reconstroi por usuário usando helper completo
        users = db.get_all_users()
        for u in users:
            chat_id = str(u["chat_id"]) if "chat_id" in u else None
            if chat_id is None:
                continue
            
            # Só carregar se não estiver bloqueado
            if not db.is_user_blocked(int(chat_id)):
                completo = db.get_user_complete(int(chat_id))
                if completo:
                    filtros[chat_id] = completo
            else:
                logging.info(f"🚫 Usuário {chat_id} está bloqueado, não carregando filtros")
                
        logging.info(f"✅ {len(filtros)} filtros carregados do banco normalizado")
        return filtros
    except Exception as exc:
        logging.error(f"❌ Erro no carregamento: {exc}")
        return {}

# Primeiro, tentar migrar banco legado, se aplicável
migrar_banco_legado_se_preciso()

# Em seguida, carregar filtros do banco normalizado
filtros_por_chat = carregar_filtros_startup()


def salvar_filtros():
    """Persiste filtros no schema normalizado via Database"""
    try:
        for chat_id, filtros in filtros_por_chat.items():
            if not filtros:
                continue
            cid = int(chat_id)
            # Garante usuário
            db.create_or_update_user(
                cid,
                nome=filtros.get("nome"),
                username=filtros.get("username"),
            )
            # Bookmakers
            bks = filtros.get("bookmakers")
            if not bks and filtros.get("bookmaker"):
                bks = [filtros.get("bookmaker")]
            db.set_user_bookmakers(cid, bks or [])
            # Ligas e esportes
            db.set_user_leagues(cid, filtros.get("ligas"))
            db.set_user_sports(cid, filtros.get("esportes"))
            # Filtros numéricos e datas/horários
            db.set_user_filter(
                cid,
                ev_faixa_min=filtros.get("ev_faixa_min"),
                ev_faixa_max=filtros.get("ev_faixa_max"),
                filtro_dias=filtros.get("filtro_dias"),
                data_inicio=filtros.get("data_inicio"),
                data_fim=filtros.get("data_fim"),
                horario_inicio=filtros.get("horario_inicio"),
                horario_fim=filtros.get("horario_fim"),
            )
        logging.info(f"💾 {len(filtros_por_chat)} filtros salvos no banco normalizado")
    except Exception as exc:
        logging.error(f"❌ Erro ao salvar filtros: {exc}")
        import traceback
        logging.error(f"Stack: {traceback.format_exc()}")

# 🔄 MIGRAÇÃO AUTOMÁTICA DE USUÁRIOS LEGADOS
def migrar_usuarios_legados():
    """Migra usuários da versão anterior para o novo formato"""
    global filtros_por_chat
    
    usuarios_migrados = 0
    
    for chat_id, filtros in filtros_por_chat.items():
        if filtros and not usuario_configurado(int(chat_id)):
            logging.info(f"🔄 Migrando usuário legado: {chat_id}")
            
            # Adicionar bookmaker padrão se não existir
            if not filtros.get("bookmakers") and not filtros.get("bookmaker"):
                filtros["bookmakers"] = ["Bet365"]
                logging.info(f"   ✅ {chat_id}: Bookmaker -> Bet365")
            
            # Adicionar EV mínimo padrão se não existir  
            if filtros.get("ev_faixa_min") is None:
                filtros["ev_faixa_min"] = 0.05  # 5% padrão
                logging.info(f"   ✅ {chat_id}: EV mínimo -> 5%")
            
            usuarios_migrados += 1
    
    if usuarios_migrados > 0:
        salvar_filtros()
        logging.info(f"✅ Migração concluída: {usuarios_migrados} usuários migrados")
    
    return usuarios_migrados

def converter_filtro_estatico_para_dinamico():
    """Converte filtros estáticos expirados para dinâmico de 7 dias"""
    # Função temporariamente desabilitada para evitar erros de sintaxe
    return 0

# Executar migrações na inicialização
logging.info("🚀 Verificando necessidade de migração...")
usuarios_migrados = migrar_usuarios_legados()
filtros_convertidos = converter_filtro_estatico_para_dinamico()

if usuarios_migrados > 0:
    logging.info(f"📋 {usuarios_migrados} usuários migrados da versão anterior")
if filtros_convertidos > 0:
    logging.info(f"🔄 {filtros_convertidos} filtros estáticos convertidos para dinâmico")
if usuarios_migrados == 0 and filtros_convertidos == 0:
    logging.info("ℹ️ Nenhuma migração necessária")

def atualizar_info_usuario(chat_id, user):
    """Garante que o registro do usuário tenha nome e username atualizados + configurações mínimas"""
    filtros_usuario = filtros_por_chat.setdefault(chat_id, {})
    atualizado = False

    # Configurações obrigatórias com valores padrão
    if "ligas" not in filtros_usuario:
        filtros_usuario["ligas"] = None
        atualizado = True
    if "esportes" not in filtros_usuario:
        filtros_usuario["esportes"] = None
        atualizado = True
    
    # 🔧 PREVENÇÃO: Garantir configurações mínimas obrigatórias
    if not filtros_usuario.get("bookmakers") and not filtros_usuario.get("bookmaker"):
        filtros_usuario["bookmakers"] = ["Bet365"]
        atualizado = True
    
    if filtros_usuario.get("ev_faixa_min") is None:
        filtros_usuario["ev_faixa_min"] = 0.05  # 5% padrão
        atualizado = True

    # Atualizar info do usuário
    if user:
        primeiro_nome = getattr(user, "first_name", None)
        username = getattr(user, "username", None)

        if primeiro_nome and filtros_usuario.get("nome") != primeiro_nome:
            filtros_usuario["nome"] = primeiro_nome
            atualizado = True
        if username and filtros_usuario.get("username") != username:
            filtros_usuario["username"] = username
            atualizado = True

    if atualizado:
        logging.info(f"🔄 Usuário {chat_id} atualizado: {filtros_usuario}")

    return filtros_usuario, atualizado

def gerar_botoes_ligas(ligas, selecionadas):
    botoes = []
    for liga in ligas:
        marcada = "✅" if liga in selecionadas else "☑️"
        botoes.append([InlineKeyboardButton(f"{marcada} {liga}", callback_data=f"liga_toggle|{liga}")])
    # Botão para salvar filtro
    botoes.append([InlineKeyboardButton("💾 Salvar filtro", callback_data="liga_salvar")])
    return InlineKeyboardMarkup(botoes)

# ===== SISTEMA DE /START INTELIGENTE =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    filtros_usuario, info_atualizada = atualizar_info_usuario(chat_id, update.effective_user)
    if info_atualizada:
        salvar_filtros()
    
    # ===== USUÁRIO JÁ CONFIGURADO =====
    if usuario_configurado(int(chat_id)):
        return await start_usuario_configurado(update, context, filtros_usuario)
    
    # ===== USUÁRIO NOVO - SETUP OBRIGATÓRIO =====
    return await start_usuario_novo(update, context)

async def start_usuario_configurado(update, context, filtros_usuario):
    """Menu para usuário que já tem configuração completa"""
    
    # Coleta informações da configuração atual
    bookmakers = filtros_usuario.get("bookmakers", [])
    if not bookmakers:
        bookmakers = [filtros_usuario.get("bookmaker", "Bet365")]
    
    ev_min = filtros_usuario.get("ev_faixa_min", 0.05)
    ev_max = filtros_usuario.get("ev_faixa_max")
    ligas = filtros_usuario.get("ligas")
    
    # Filtros de data
    filtro_dias = filtros_usuario.get("filtro_dias")
    data_inicio = filtros_usuario.get("data_inicio")
    data_fim = filtros_usuario.get("data_fim")
    
    # Filtros de horário
    horario_inicio = filtros_usuario.get("horario_inicio")
    horario_fim = filtros_usuario.get("horario_fim")
    
    # Determina status dos filtros
    if filtro_dias:
        status_data = f"{filtro_dias} dias (renova automaticamente) 🔄"
    elif data_inicio and data_fim:
        # Verifica se é estático e se expirou
        try:
            from datetime import timezone
            data_fim_obj = datetime.strptime(data_fim, "%Y-%m-%d").date()
            hoje = datetime.now(timezone.utc).date()
            if data_fim_obj < hoje:
                status_data = "Período expirado ⚠️"
            else:
                status_data = f"Até {data_fim_obj.strftime('%d/%m')} ⚠️"
        except:
            status_data = "Período específico ⚠️"
    else:
        status_data = "Todas as datas"
    
    if horario_inicio and horario_fim:
        status_horario = f"{horario_inicio}-{horario_fim}"
    else:
        status_horario = "24h"
    
    # Menu contextual
        keyboard = [
        [InlineKeyboardButton("⚙️ Alterar Configurações", callback_data="reconfigurar")],
        [InlineKeyboardButton("📊 Ver Filtros Detalhados", callback_data="ver_filtros_completos")],
        [InlineKeyboardButton("🔍 Scan Manual Agora", callback_data="scan_manual_inline")],
        [InlineKeyboardButton("📈 Histórico de Alertas", callback_data="ver_historico")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
    # EV texto - Mínimo ou faixa
    if ev_max and ev_max < 99:
        ev_texto = f"{ev_min*100:.1f}%-{ev_max*100:.1f}%"
    else:
        ev_texto = f"{ev_min*100:.1f}%+"
    
    bookmakers_texto = f"{', '.join(bookmakers[:2])}{'...' if len(bookmakers) > 2 else ''}"
    
    msg = (
        f"👋 <b>Olá, {filtros_usuario.get('nome', 'usuário')}!</b>\n\n"
        "✅ <b>Bot Configurado e Ativo</b>\n\n"
        "🎯 <b>Configuração Atual:</b>\n"
        f"🏠 <b>Casas:</b> {bookmakers_texto}\n"
        f"📈 <b>EV:</b> {ev_texto}\n"
        f"🌍 <b>Ligas:</b> {'Personalizadas' if ligas else 'Todas'}\n"
        f"📅 <b>Datas:</b> {status_data}\n"
        f"🕐 <b>Horários:</b> {status_horario}\n\n"
        "📡 <i>Monitoramento automático ativo!</i>\n"
        "🔔 <i>Alertas enviados a cada 2 minutos</i>"
    )
    
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="HTML")

async def start_usuario_configurado_callback(query, context, filtros_usuario):
    """Menu para usuário configurado via callback"""
    
    bookmakers = filtros_usuario.get("bookmakers", [])
    if not bookmakers:
        bookmakers = [filtros_usuario.get("bookmaker", "Bet365")]
    
    ev_min = filtros_usuario.get("ev_faixa_min", 0.05)
    ev_max = filtros_usuario.get("ev_faixa_max")
    ligas = filtros_usuario.get("ligas")
    
    filtro_dias = filtros_usuario.get("filtro_dias")
    data_inicio = filtros_usuario.get("data_inicio")
    data_fim = filtros_usuario.get("data_fim")
    
    horario_inicio = filtros_usuario.get("horario_inicio")
    horario_fim = filtros_usuario.get("horario_fim")
    
    if filtro_dias:
        status_data = f"{filtro_dias} dias (renova automaticamente) 🔄"
    elif data_inicio and data_fim:
        try:
            from datetime import timezone
            data_fim_obj = datetime.strptime(data_fim, "%Y-%m-%d").date()
            hoje = datetime.now(timezone.utc).date()
            if data_fim_obj < hoje:
                status_data = "Período expirado ⚠️"
            else:
                status_data = f"Até {data_fim_obj.strftime('%d/%m')} ⚠️"
        except:
            status_data = "Período específico ⚠️"
    else:
        status_data = "Todas as datas"
    
    if horario_inicio and horario_fim:
        status_horario = f"{horario_inicio}-{horario_fim}"
    else:
        status_horario = "24h"
    
    keyboard = [
        [InlineKeyboardButton("⚙️ Alterar Configurações", callback_data="reconfigurar")],
        [InlineKeyboardButton("📊 Ver Filtros Detalhados", callback_data="ver_filtros_completos")],
        [InlineKeyboardButton("🔍 Scan Manual Agora", callback_data="scan_manual_inline")],
        [InlineKeyboardButton("📈 Histórico de Alertas", callback_data="ver_historico")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if ev_max and ev_max < 99:
        ev_texto = f"{ev_min*100:.1f}%-{ev_max*100:.1f}%"
    else:
        ev_texto = f"{ev_min*100:.1f}%+"
    
    bookmakers_texto = f"{', '.join(bookmakers[:2])}{'...' if len(bookmakers) > 2 else ''}"
    
    msg = (
        f"👋 <b>Olá, {filtros_usuario.get('nome', 'usuário')}!</b>\n\n"
        "✅ <b>Bot Configurado e Ativo</b>\n\n"
        "🎯 <b>Configuração Atual:</b>\n"
        f"🏠 <b>Casas:</b> {bookmakers_texto}\n"
        f"📈 <b>EV:</b> {ev_texto}\n"
        f"🌍 <b>Ligas:</b> {'Personalizadas' if ligas else 'Todas'}\n"
        f"📅 <b>Datas:</b> {status_data}\n"
        f"🕐 <b>Horários:</b> {status_horario}\n\n"
        "📡 <i>Monitoramento automático ativo!</i>\n"
        "🔔 <i>Alertas enviados a cada 2 minutos</i>"
    )
    
    await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode="HTML")

async def start_usuario_novo_callback(query, context):
    """Setup para usuário novo via callback"""
    
    keyboard = [
        [InlineKeyboardButton("🚀 Começar Configuração", callback_data="setup_passo1")],
        [InlineKeyboardButton("📘 Como Funciona?", callback_data="explicar_bot")],
        [InlineKeyboardButton("🎯 Ver Exemplo de Alerta", callback_data="exemplo_alerta")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = (
        "👋 <b>Bem-vindo ao Bot EV+ Profissional!</b>\n\n"
        "🎯 <b>O que fazemos:</b>\n"
        "• Monitoramos <b>200+ casas de apostas</b> em tempo real\n"
        "• Encontramos apostas com <b>Valor Esperado Positivo</b>\n"
        "• Te avisamos <b>automaticamente</b> das melhores oportunidades\n\n"
        "⚡ <b>Setup Rápido (3 minutos):</b>\n"
        "1️⃣ 🏠 Escolher suas casas de aposta favoritas\n"
        "2️⃣ 📈 Definir seu EV mínimo (recomendado: 5%)\n"
        "3️⃣ 🌍 Selecionar ligas de interesse\n"
        "4️⃣ 📅 Escolher período de alertas\n"
        "5️⃣ 🕐 Configurar horários preferidos\n\n"
        "🔔 <b>Resultado:</b> Alertas automáticos das melhores apostas!\n\n"
        "💡 <i>Usado por apostadores profissionais no mundo todo</i>"
    )
    
    await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode="HTML")

async def start_usuario_novo(update, context):
    """Setup obrigatório para usuário novo"""
            
    keyboard = [
        [InlineKeyboardButton("🚀 Começar Configuração", callback_data="setup_passo1")],
        [InlineKeyboardButton("📘 Como Funciona?", callback_data="explicar_bot")],
        [InlineKeyboardButton("🎯 Ver Exemplo de Alerta", callback_data="exemplo_alerta")],
            ]
    reply_markup = InlineKeyboardMarkup(keyboard)
            
    msg = (
        "👋 <b>Bem-vindo ao Bot EV+ Profissional!</b>\n\n"
        "🎯 <b>O que fazemos:</b>\n"
        "• Monitoramos <b>200+ casas de apostas</b> em tempo real\n"
        "• Encontramos apostas com <b>Valor Esperado Positivo</b>\n"
        "• Te avisamos <b>automaticamente</b> das melhores oportunidades\n\n"
        "⚡ <b>Setup Rápido (3 minutos):</b>\n"
        "1️⃣ 🏠 Escolher suas casas de aposta favoritas\n"
        "2️⃣ 📈 Definir seu EV mínimo (recomendado: 5%)\n"
        "3️⃣ 🌍 Selecionar ligas de interesse\n"
        "4️⃣ 📅 Escolher período de alertas\n"
        "5️⃣ 🕐 Configurar horários preferidos\n\n"
        "🔔 <b>Resultado:</b> Alertas automáticos das melhores apostas!\n\n"
        "💡 <i>Usado por apostadores profissionais no mundo todo</i>"
    )
    
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="HTML")

# ===== CALLBACKS PARA O SISTEMA DE SETUP =====

async def setup_passo1_callback(update, context):
    """Passo 1: Escolher casas de aposta"""
    query = update.callback_query
    await query.answer()
    
    msg = (
        "🏠 <b>Passo 1/4: Casas de Aposta</b>\n\n"
        "Selecione suas casas de aposta favoritas:\n\n"
        "💡 <b>Dica:</b> Escolha 2-3 casas principais onde você costuma apostar\n"
        "🎯 <b>Recomendadas:</b> Bet365, Pinnacle, Betfair\n\n"
        "⬇️ <i>Clique no botão abaixo para escolher</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎰 Escolher Casas de Aposta", callback_data="setup_bookmakers")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="start_inicial")],
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def setup_bookmakers_callback(update, context):
    """Redireciona para seleção de bookmakers no modo setup"""
    query = update.callback_query
    await query.answer()
    
    # Marca que estamos em modo setup
    context.user_data["setup_mode"] = True
    context.user_data["setup_step"] = "bookmakers"
    
    # Usa a função existente mas adapta para setup
    await escolher_bookmaker(update, context)

async def setup_passo2_callback(update, context):
    """Passo 2: Configurar EV - FAIXA MANUAL"""
    query = update.callback_query
    await query.answer()
    
    # SÓ entrada manual - exatamente como sua foto!
    context.user_data["setup_esperando_ev"] = True
    
    msg = (
        "📈 <b>Passo 2/4: EV Mínimo</b>\n\n"
        "📝 <b>Envie sua configuração de EV:</b>\n\n"
        "• <b>Apenas mínimo:</b> <code>0.01</code> (1% ou mais)\n"
        "• <b>Faixa completa:</b> <code>0.01 0.15</code> (1% até 15%)\n"
        "• <b>Sem limite superior:</b> basta mandar um valor (ex: <code>0.03</code>)\n\n"
        "👉 <b>Use valores decimais, onde 0.05 = 5%</b>"
    )
            
    keyboard = [
        [InlineKeyboardButton("🔙 Voltar", callback_data="setup_passo1")],
    ]
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def setup_passo3_callback(update, context):
    """Passo 3: Escolher regiões/ligas"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🇧🇷 Brasil", callback_data="setup_regiao|brasil")],
        [InlineKeyboardButton("🇪🇺 Europa", callback_data="setup_regiao|europa")],
        [InlineKeyboardButton("🌎 América do Sul", callback_data="setup_regiao|americasul")],
        [InlineKeyboardButton("🌍 Todas as Ligas", callback_data="setup_regiao|todas")],
        [InlineKeyboardButton("⚙️ Personalizar Ligas", callback_data="setup_ligas_custom")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="setup_passo2")],
    ]
    
    msg = (
        "🌍 <b>Passo 3/5: Regiões de Interesse</b>\n\n"
        "Escolha as regiões que você quer monitorar:\n\n"
        "🇧🇷 <b>Brasil:</b> Brasileirão, Copa do Brasil, etc.\n"
        "🇪🇺 <b>Europa:</b> Premier League, La Liga, etc.\n"
        "🌎 <b>América do Sul:</b> Libertadores, etc.\n"
        "🌍 <b>Todas:</b> Monitoramento global\n\n"
        "💡 <b>Dica:</b> Comece com sua região principal"
    )
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def setup_regiao_callback(update, context):
    """Processa seleção de região no setup"""
    query = update.callback_query
    await query.answer()
    
    regiao = query.data.split("|")[1]
    chat_id = str(query.message.chat_id)
    
    # Aplica filtro de região usando lógica existente
    catalogo = carregar_catalogo_ligas()
    filtros_usuario = filtros_por_chat.setdefault(chat_id, {})
    
    if regiao == "brasil":
        filtros_usuario["ligas"] = catalogo.get("Brasil", {}).get("Football", [])
    elif regiao == "europa":
        filtros_usuario["ligas"] = catalogo.get("Europa", {}).get("Football", [])
    elif regiao == "americasul":
        filtros_usuario["ligas"] = catalogo.get("América do Sul", {}).get("Football", [])
    elif regiao == "todas":
        filtros_usuario["ligas"] = None
    
    salvar_filtros()
    
    # Vai para passo 4 (filtro de dias)
    await setup_passo4_callback(update, context)

async def setup_passo4_callback(update, context):
    """Passo 4: Escolher período de alertas"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📅 1 Dia", callback_data="setup_dias|1")],
        [InlineKeyboardButton("📅 2 Dias", callback_data="setup_dias|2")],
        [InlineKeyboardButton("📅 3 Dias", callback_data="setup_dias|3")],
        [InlineKeyboardButton("📅 7 Dias", callback_data="setup_dias|7")],
        [InlineKeyboardButton("♾️ Ilimitado", callback_data="setup_dias|0")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="setup_passo3")],
    ]
    
    msg = (
        "📅 <b>Passo 4/5: Período de Alertas</b>\n\n"
        "Por quantos dias você quer receber alertas?\n\n"
        "📅 <b>1 Dia:</b> Dentro de 24 horas\n"
        "📅 <b>2 Dias:</b> Dentro de 48 horas\n"
        "📅 <b>3 Dias:</b> Dentro de 72 horas\n"
        "📅 <b>7 Dias:</b> Dentro de 168 horas\n"
        "♾️ <b>Ilimitado:</b> Sempre ativo\n\n"
        "💡 <b>Dica:</b> O filtro se renova automaticamente a cada dia"
    )
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def setup_dias_callback(update, context):
    """Processa seleção de filtro de dias no setup"""
    query = update.callback_query
    await query.answer()
    
    dias = int(query.data.split("|")[1])
    chat_id = str(query.message.chat_id)
    
    # Salva filtro de dias
    filtros_por_chat.setdefault(chat_id, {})
    filtros_por_chat[chat_id]["filtro_dias"] = dias if dias > 0 else None
    salvar_filtros()
    
    # Vai para passo 5 (horários)
    await setup_passo5_callback(update, context)

async def setup_passo5_callback(update, context):
    """Passo 5: Configurações de horário (opcional)"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🌆 Apenas Noite (19h-23h)", callback_data="setup_horario|19:00|23:00")],
        [InlineKeyboardButton("☀️ Apenas Tarde (14h-18h)", callback_data="setup_horario|14:00|18:00")],
        [InlineKeyboardButton("🕐 Personalizar Horário", callback_data="setup_horario_custom")],
        [InlineKeyboardButton("⏭️ Pular (24h)", callback_data="setup_finalizar")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="setup_passo4")],
    ]
    
    msg = (
        "🕐 <b>Passo 5/5: Horários (Opcional)</b>\n\n"
        "Quer receber alertas apenas em horários específicos?\n\n"
        "🌆 <b>Noite:</b> Ideal para futebol brasileiro\n"
        "☀️ <b>Tarde:</b> Ideal para futebol europeu\n"
        "🕐 <b>Personalizar:</b> Defina seu horário\n"
        "⏭️ <b>Pular:</b> Receber alertas 24h\n\n"
        "💡 <b>Dica:</b> Você pode alterar depois"
    )
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def setup_horario_callback(update, context):
    """Processa seleção de horário no setup"""
    query = update.callback_query
    await query.answer()
    
    _, inicio, fim = query.data.split("|")
    chat_id = str(query.message.chat_id)
    
    # Salva horário
    filtros_por_chat.setdefault(chat_id, {})["horario_inicio"] = inicio
    filtros_por_chat[chat_id]["horario_fim"] = fim
    salvar_filtros()
    
    # Finaliza setup
    await setup_finalizar_callback(update, context)

async def setup_finalizar_callback(update, context):
    """Finaliza o setup e mostra resumo"""
    query = update.callback_query
    await query.answer()
    
    chat_id = str(query.message.chat_id)
    filtros = filtros_por_chat.get(chat_id, {})
    
    # Gera resumo da configuração
    bookmakers = filtros.get("bookmakers", ["Bet365"])
    ev_min = filtros.get("ev_faixa_min", 0.05)
    ev_max = filtros.get("ev_faixa_max")
    ligas = filtros.get("ligas")
    filtro_dias = filtros.get("filtro_dias")
    horario_inicio = filtros.get("horario_inicio")
    horario_fim = filtros.get("horario_fim")
    
    # EV texto
    if ev_max and ev_max < 99:
        ev_texto = f"{ev_min*100:.1f}%-{ev_max*100:.1f}%"
    else:
        ev_texto = f"{ev_min*100:.1f}%+"
    
    # Filtro de dias texto
    if filtro_dias:
        if filtro_dias == 1:
            dias_texto = "1 dia"
        elif filtro_dias == 2:
            dias_texto = "2 dias"
        elif filtro_dias == 3:
            dias_texto = "3 dias"
        elif filtro_dias == 7:
            dias_texto = "7 dias"
        else:
            dias_texto = f"{filtro_dias} dias"
    else:
        dias_texto = "Ilimitado"
            
    keyboard = [
        [InlineKeyboardButton("🎯 Fazer Primeiro Scan", callback_data="scan_manual_inline")],
        [InlineKeyboardButton("⚙️ Ajustar Configurações", callback_data="reconfigurar")],
        [InlineKeyboardButton("📊 Ver Filtros Completos", callback_data="ver_filtros_completos")],
    ]
    
    msg = (
        "🎉 <b>Configuração Concluída!</b>\n\n"
        "✅ <b>Bot ativo e monitorando:</b>\n"
        f"🏠 <b>Casas:</b> {', '.join(bookmakers[:2])}\n"
        f"📈 <b>EV:</b> {ev_texto}\n"
        f"🌍 <b>Ligas:</b> {'Personalizadas' if ligas else 'Todas'}\n"
        f"📅 <b>Período:</b> {dias_texto}\n"
        f"🕐 <b>Horário:</b> {f'{horario_inicio}-{horario_fim}' if horario_inicio else '24h'}\n\n"
        "🔔 <b>A partir de agora você receberá alertas automáticos!</b>\n\n"
        "📡 <i>Monitoramento ativo a cada 2 minutos</i>\n"
        "💡 <i>Use /start para gerenciar suas configurações</i>"
    )
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def explicar_bot_callback(update, context):
    """Explica como o bot funciona"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🚀 Configurar Agora", callback_data="setup_passo1")],
        [InlineKeyboardButton("🎯 Ver Exemplo", callback_data="exemplo_alerta")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="start_inicial")],
    ]
    
    msg = (
        "📘 <b>Como Funciona o Bot EV+</b>\n\n"
        "🔍 <b>1. Monitoramento:</b>\n"
        "• Analisamos odds de 200+ casas\n"
        "• Comparamos com odds de referência\n"
        "• Identificamos discrepâncias\n\n"
        "🧮 <b>2. Cálculo do EV:</b>\n"
        "• EV = (Odd × Probabilidade Real) - 1\n"
        "• EV > 0 = Aposta com valor\n"
        "• Quanto maior o EV, melhor\n\n"
        "🔔 <b>3. Alertas:</b>\n"
        "• Te avisamos instantaneamente\n"
        "• Apenas apostas acima do seu EV mínimo\n"
        "• Sugestão de stake calculada\n\n"
        "💰 <b>Resultado:</b> Lucro consistente a longo prazo!"
    )
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def exemplo_alerta_callback(update, context):
    """Mostra exemplo de um alerta"""
    query = update.callback_query
    await query.answer()
            
    keyboard = [
        [InlineKeyboardButton("🚀 Quero Receber Alertas Assim!", callback_data="setup_passo1")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="start_inicial")],
    ]
    
    msg = (
        "🎯 <b>Exemplo de Alerta EV+</b>\n\n"
        "⚽ <b>Flamengo vs Palmeiras</b>\n"
        "🏆 Brasileirão - Serie A\n"
        "📌 <b>Mercado:</b> <i>Moneyline (Flamengo)</i>\n"
        "📢 <b>Odd Bet365:</b> <i>2.45</i>\n"
        "📉 <b>Odd mínima recomendada:</b> <i>2.20</i>\n"
        "📈 <b>Valor Esperado (EV):</b> <i>8.7%</i>\n"
        "🎯 <b>Stake:</b> <i>1.5u</i>\n"
        "🗓️ <b>Data do Jogo:</b> <i>25/09/2025 20:00</i>\n"
        "⏳ <b>Faltam:</b> <i>2h 15min</i>\n"
        "🔗 Abrir na Bet365\n\n"
        "💡 <b>Análise:</b> Odd com 8.7% de valor esperado positivo!\n"
        "📊 <b>Stake sugerido:</b> 1.5 unidades do seu bankroll"
    )
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def ver_filtros_completos_callback(update, context):
    """Versão inline do comando /filtros"""
    query = update.callback_query
    await query.answer()
    
    chat_id = str(query.message.chat_id)
    await ver_filtros_inline_detalhado(update, context, chat_id)

async def scan_manual_inline_callback(update, context):
    """Scan manual via botão"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("🔎 <b>Iniciando scan manual...</b>\n\n⏳ Analisando mercado...", parse_mode="HTML")
    
    chat_id = str(query.message.chat_id)
    # Scan individual para o usuário específico
    resultado = await scan_apostas_usuario(chat_id)
            
    keyboard = [
        [InlineKeyboardButton("🔄 Novo Scan", callback_data="scan_manual_inline")],
        [InlineKeyboardButton("🏠 Menu Principal", callback_data="start_inicial")],
    ]
    
    await query.edit_message_text(
        f"✅ <b>Scan Concluído!</b>\n\n{resultado}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def start_inicial_callback(update, context):
    """Volta para o /start inicial"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    chat_id = str(query.message.chat_id)
    
    filtros_usuario, info_atualizada = atualizar_info_usuario(chat_id, query.from_user)
    if info_atualizada:
        salvar_filtros()
    
    if usuario_configurado(int(chat_id)):
        await start_usuario_configurado_callback(query, context, filtros_usuario)
    else:
        await start_usuario_novo_callback(query, context)

async def ver_historico_callback(update, context):
    """Mostra histórico de alertas do usuário"""
    query = update.callback_query
    await query.answer()
    
    chat_id = str(query.message.chat_id)
    
    alertas = _fetch_alert_history(chat_id)

    if alertas:
        total_alertas = len(alertas)
        evs = [float(row["ev"]) for row in alertas if row.get("ev") is not None]
        ev_medio = sum(evs) / len(evs) if evs else 0
        ultimos = alertas[-5:]

        msg = f"📈 <b>Seu Histórico de Alertas</b>\n\n"
        msg += f"📊 <b>Estatísticas:</b>\n"
        msg += f"• Total de alertas: {total_alertas}\n"
        msg += f"• EV médio: {ev_medio:.2%}\n\n"
        msg += "🕐 <b>Últimos 5 alertas:</b>\n"

        for i, alerta in enumerate(reversed(ultimos), 1):
            data_envio = alerta.get("data_envio")
            data = data_envio[:10] if isinstance(data_envio, str) else ""
            home = alerta.get("home", "") or ""
            away = alerta.get("away", "") or ""
            ev = float(alerta.get("ev", 0) or 0)

            msg += f"{i}. {home} vs {away}\n"
            msg += f"   📅 {data} | 📈 {ev:.1%}\n"
    else:
        msg = (
            "📈 <b>Histórico de Alertas</b>\n\n"
            "📭 Você ainda não recebeu alertas.\n\n"
            "💡 <b>Dica:</b> Faça um scan manual para testar sua configuração!"
        )
    
    keyboard = [
        [InlineKeyboardButton("🔍 Fazer Scan Manual", callback_data="scan_manual_inline")],
        [InlineKeyboardButton("🏠 Menu Principal", callback_data="start_inicial")],
    ]
    
    await query.edit_message_text(
        msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )

async def ver_filtros_inline_detalhado(update, context, chat_id):
    """Versão detalhada dos filtros em formato inline"""
    filtros = filtros_por_chat.get(chat_id, {})
    
    # Coleta todas as informações
    ligas = filtros.get("ligas")
    esportes = filtros.get("esportes")
    bookmakers = filtros.get("bookmakers", [filtros.get("bookmaker", "Bet365")])
    if isinstance(bookmakers, str):
        bookmakers = [bookmakers]
    
    ev_min = filtros.get("ev_faixa_min")
    ev_max = filtros.get("ev_faixa_max")
    
    filtro_dias = filtros.get("filtro_dias")
    data_inicio = filtros.get("data_inicio")
    data_fim = filtros.get("data_fim")
    
    horario_inicio = filtros.get("horario_inicio")
    horario_fim = filtros.get("horario_fim")
    
    # Constrói mensagem detalhada
    msg = "📊 <b>Configuração Completa</b>\n\n"
    
    # Casas de aposta
    msg += f"🏠 <b>Casas de Aposta:</b>\n"
    for i, bk in enumerate(bookmakers[:5], 1):  # Mostra até 5
        msg += f"   {i}. {bk}\n"
    if len(bookmakers) > 5:
        msg += f"   ... e mais {len(bookmakers)-5}\n"
    
    # EV - com faixa
    if ev_min is not None:
        if ev_max and ev_max < 99:
            msg += f"\n📈 <b>EV:</b> {ev_min*100:.1f}% até {ev_max*100:.1f}%\n"
        else:
            msg += f"\n📈 <b>EV:</b> {ev_min*100:.1f}% ou mais\n"
    else:
        msg += f"\n📈 <b>EV:</b> Padrão (≥ 5%)\n"
    
    # Ligas
    if ligas:
        msg += f"\n🌍 <b>Ligas:</b> {len(ligas)} selecionadas\n"
        # Mostra algumas ligas como exemplo
        for liga in ligas[:3]:
            msg += f"   • {liga}\n"
        if len(ligas) > 3:
            msg += f"   ... e mais {len(ligas)-3}\n"
    else:
        msg += f"\n🌍 <b>Ligas:</b> Todas disponíveis\n"
    
    # Esportes
    if esportes:
        msg += f"\n⚽ <b>Esportes:</b> {', '.join(esportes)}\n"
    else:
        msg += f"\n⚽ <b>Esportes:</b> Todos\n"
    
    # Data
    if filtro_dias:
        msg += f"\n📅 <b>Datas:</b> {filtro_dias} dias (renova automaticamente) 🔄\n"
    elif data_inicio and data_fim:
        msg += f"\n📅 <b>Datas:</b> {data_inicio} até {data_fim} (estático ⚠️)\n"
    else:
        msg += f"\n📅 <b>Datas:</b> Todas\n"
    
    # Horário
    if horario_inicio and horario_fim:
        msg += f"\n🕐 <b>Horário:</b> {horario_inicio} às {horario_fim}\n"
    else:
        msg += f"\n🕐 <b>Horário:</b> 24 horas\n"
    
    keyboard = [
        [InlineKeyboardButton("⚙️ Alterar Configurações", callback_data="reconfigurar")],
        [InlineKeyboardButton("🏠 Menu Principal", callback_data="start_inicial")],
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    else:
                await update.message.reply_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )

async def setup_ligas_custom_callback(update, context):
    """Ligas personalizadas no setup"""
    query = update.callback_query
    await query.answer()
            
    keyboard = [
        [InlineKeyboardButton("⚽ Usar /ligas para personalizar", callback_data="explicar_ligas_custom")],
        [InlineKeyboardButton("⏭️ Pular por agora", callback_data="setup_passo5")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="setup_passo3")],
    ]
    
    msg = (
        "⚙️ <b>Ligas Personalizadas</b>\n\n"
        "Para selecionar ligas específicas, use:\n"
        "<code>/ligas brasil futebol</code>\n\n"
        "Isso permite escolher exatamente quais campeonatos monitorar.\n\n"
        "💡 <b>Dica:</b> Configure isso depois do setup inicial"
    )
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def setup_horario_custom_callback(update, context):
    """Horário personalizado no setup"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["setup_esperando_horario"] = True
    
    await query.edit_message_text(
        "🕐 <b>Horário Personalizado</b>\n\n"
        "Digite o horário no formato:\n"
        "<code>HH:MM HH:MM</code>\n\n"
        "📝 <b>Exemplos:</b>\n"
        "• <code>15:00 22:00</code> → Das 15h às 22h\n"
        "• <code>20:30 23:30</code> → Das 20h30 às 23h30\n\n"
        "💡 Use formato 24h",
        parse_mode="HTML"
    )

async def explicar_ligas_custom_callback(update, context):
    """Explica como usar ligas customizadas"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("⏭️ Continuar Setup", callback_data="setup_passo5")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="setup_passo3")],
    ]
    
    msg = (
        "⚙️ <b>Como Personalizar Ligas</b>\n\n"
        "Após finalizar o setup, use estes comandos:\n\n"
        "🇧🇷 <code>/ligas brasil futebol</code>\n"
        "🇪🇺 <code>/ligas europa futebol</code>\n"
        "🏀 <code>/ligas europa basquete</code>\n\n"
        "Isso abre uma interface para selecionar exatamente quais campeonatos você quer monitorar.\n\n"
        "💡 <b>Dica:</b> Primeiro termine o setup, depois personalize!"
    )
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def processar_setup_ev_manual(update, context):
    """Processa EV manual durante setup - FAIXA MANUAL"""
    try:
        entrada = update.message.text.strip()
        partes = entrada.split()
        
        chat_id = str(update.effective_chat.id)
        
        if len(partes) == 1:
            # Apenas mínimo: 0.05
            ev_min = float(partes[0])
            if ev_min < 0.01 or ev_min > 10.0:
                raise ValueError("Fora do range")
            
            filtros_por_chat.setdefault(chat_id, {})["ev_faixa_min"] = ev_min
            filtros_por_chat[chat_id]["ev_faixa_max"] = 9999.0  # Sem limite superior
            msg = f"✅ <b>EV configurado: {ev_min*100:.1f}% ou mais</b>"
            
        elif len(partes) == 2:
            # Faixa completa: 0.01 0.15
            ev_min, ev_max = float(partes[0]), float(partes[1])
            
            if ev_min < 0.01 or ev_min > 10.0:
                raise ValueError("Min fora do range")
            if ev_max < ev_min or ev_max > 10.0:
                raise ValueError("Max inválido")
            
            filtros_por_chat.setdefault(chat_id, {})["ev_faixa_min"] = ev_min
            filtros_por_chat[chat_id]["ev_faixa_max"] = ev_max
            msg = f"✅ <b>EV configurado: {ev_min*100:.1f}% até {ev_max*100:.1f}%</b>"
            
        else:
            raise ValueError("Formato inválido")
        
        salvar_filtros()
        context.user_data["setup_esperando_ev"] = False
        
        await update.message.reply_text(f"{msg}\n\nContinuando setup...", parse_mode="HTML")
        
        # MUDANÇA AQUI - chama a função nova
        await enviar_setup_passo3_message(update, context)
        return True
        
    except Exception:
            await update.message.reply_text(
            "❌ <b>Formato inválido!</b>\n\n"
            "📋 <b>Formatos aceitos:</b>\n"
            "• <code>0.05</code> → 5% ou mais\n"
            "• <code>0.03 0.12</code> → 3% até 12%\n\n"
            "👉 Use valores entre 0.01 e 10.0",
            parse_mode="HTML"
        )
    return True

async def enviar_setup_passo3_message(update, context):
    """Passo 3 do setup enviado como mensagem normal"""
    keyboard = [
        [InlineKeyboardButton("🇧🇷 Brasil", callback_data="setup_regiao|brasil")],
        [InlineKeyboardButton("🇪🇺 Europa", callback_data="setup_regiao|europa")],
        [InlineKeyboardButton("🌎 América do Sul", callback_data="setup_regiao|americasul")],
        [InlineKeyboardButton("🌍 Todas as Ligas", callback_data="setup_regiao|todas")],
        [InlineKeyboardButton("⚙️ Personalizar Ligas", callback_data="setup_ligas_custom")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="setup_passo2")],
    ]
    
    msg = (
        "🌍 <b>Passo 3/4: Regiões de Interesse</b>\n\n"
        "Escolha as regiões que você quer monitorar:\n\n"
        "🇧🇷 <b>Brasil:</b> Brasileirão, Copa do Brasil, etc.\n"
        "🇪🇺 <b>Europa:</b> Premier League, La Liga, etc.\n"
        "🌎 <b>América do Sul:</b> Libertadores, etc.\n"
        "🌍 <b>Todas:</b> Monitoramento global\n\n"
        "💡 <b>Dica:</b> Comece com sua região principal"
    )
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def enviar_setup_finalizacao_message(update, context):
    """Finalização do setup enviada como mensagem normal"""
    chat_id = str(update.effective_chat.id)
    filtros = filtros_por_chat.get(chat_id, {})
    
    bookmakers = filtros.get("bookmakers", ["Bet365"])
    ev_min = filtros.get("ev_faixa_min", 0.05)
    ev_max = filtros.get("ev_faixa_max")
    ligas = filtros.get("ligas")
    horario_inicio = filtros.get("horario_inicio")
    horario_fim = filtros.get("horario_fim")
    
    if ev_max and ev_max < 99:
        ev_texto = f"{ev_min*100:.1f}%-{ev_max*100:.1f}%"
    else:
        ev_texto = f"{ev_min*100:.1f}%+"
    
    keyboard = [
        [InlineKeyboardButton("🎯 Fazer Primeiro Scan", callback_data="scan_manual_inline")],
        [InlineKeyboardButton("⚙️ Ajustar Configurações", callback_data="reconfigurar")],
        [InlineKeyboardButton("📊 Ver Filtros Completos", callback_data="ver_filtros_completos")],
    ]
    
    msg = (
        "🎉 <b>Configuração Concluída!</b>\n\n"
        "✅ <b>Bot ativo e monitorando:</b>\n"
        f"🏠 <b>Casas:</b> {', '.join(bookmakers[:2])}\n"
        f"📈 <b>EV:</b> {ev_texto}\n"
        f"🌍 <b>Ligas:</b> {'Personalizadas' if ligas else 'Todas'}\n"
        f"🕐 <b>Horário:</b> {f'{horario_inicio}-{horario_fim}' if horario_inicio else '24h'}\n\n"
        "📢 <b>A partir de agora você receberá alertas automáticos!</b>\n\n"
        "📡 <i>Monitoramento ativo a cada 2 minutos</i>\n"
        "💡 <i>Use /start para gerenciar suas configurações</i>"
    )
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def processar_setup_horario_manual(update, context):
    """Processa horário manual durante setup"""
    try:
        entrada = update.message.text.strip()
        partes = entrada.split()
        
        if len(partes) != 2:
            raise ValueError("Formato inválido")
        
        inicio, fim = partes
        datetime.strptime(inicio, "%H:%M")
        datetime.strptime(fim, "%H:%M")
        
        chat_id = str(update.effective_chat.id)
        filtros_por_chat.setdefault(chat_id, {})["horario_inicio"] = inicio
        filtros_por_chat[chat_id]["horario_fim"] = fim
        salvar_filtros()
        
        context.user_data["setup_esperando_horario"] = False
        
        await update.message.reply_text(
            f"✅ <b>Horário configurado: {inicio} às {fim}</b>\n\n"
            "Finalizando setup...",
            parse_mode="HTML"
        )
        
        # Vai para finalização
        await enviar_setup_finalizacao_message(update, context)
        return True
        
    except:
        await update.message.reply_text(
            "❌ <b>Formato inválido!</b>\n\n"
            "Use: <code>HH:MM HH:MM</code>\n"
            "Exemplo: <code>19:00 23:00</code>",
            parse_mode="HTML"
        )
        return True

# Handlers para esportes checkbox
async def esporte_toggle_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    esporte = query.data.split("|")[1]
    selecao = context.user_data.get("esportes_selecao", {})
    
    if esporte in selecao["selecionados"]:
        selecao["selecionados"].remove(esporte)
    else:
        selecao["selecionados"].add(esporte)
    
    keyboard = []
    for esp in selecao["disponiveis"]:
        marcado = "✅" if esp in selecao["selecionados"] else "☑️"
        keyboard.append([InlineKeyboardButton(f"{marcado} {esp}", callback_data=f"esporte_toggle|{esp}")])
    
    keyboard.append([InlineKeyboardButton("💾 Salvar Seleção", callback_data="esporte_salvar")])
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="escolher_esportes")])
    
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

async def esporte_salvar_handler(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    
    selecao = context.user_data.get("esportes_selecao", {})
    esportes_final = list(selecao["selecionados"]) if selecao["selecionados"] else None
    
    filtros_por_chat.setdefault(chat_id, {})["esportes"] = esportes_final
    salvar_filtros()
    
    if esportes_final:
        msg = f"✅ Esportes configurados: {', '.join(esportes_final)}"
    else:
        msg = "✅ Todos os esportes habilitados"
    
    await query.edit_message_text(msg)

# Handlers para regiões checkbox  
async def regiao_toggle_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    regiao = query.data.split("|")[1]
    selecao = context.user_data.get("regioes_selecao", {})
    
    if regiao in selecao["selecionadas"]:
        selecao["selecionadas"].remove(regiao)
    else:
        selecao["selecionadas"].add(regiao)
    
    keyboard = []
    for reg in selecao["disponiveis"]:
        marcado = "✅" if reg in selecao["selecionadas"] else "☑️"
        keyboard.append([InlineKeyboardButton(f"{marcado} {reg}", callback_data=f"regiao_toggle|{reg}")])
    
    keyboard.append([InlineKeyboardButton("💾 Aplicar Seleção", callback_data="regiao_salvar")])
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="escolher_ligas_visual")])
    
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

async def regiao_salvar_handler(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    
    selecao = context.user_data.get("regioes_selecao", {})
    catalogo = carregar_catalogo_ligas()
    
    ligas_final = []
    for regiao in selecao["selecionadas"]:
        ligas_final.extend(catalogo.get(regiao, {}).get("Football", []))
    
    filtros_por_chat.setdefault(chat_id, {})["ligas"] = ligas_final if ligas_final else None
    salvar_filtros()
    
    if ligas_final:
        msg = f"✅ Regiões configuradas: {', '.join(selecao['selecionadas'])}\n{len(ligas_final)} ligas ativadas"
    else:
        msg = "✅ Todas as ligas habilitadas"
    
    await query.edit_message_text(msg)

# Comando /admin
async def admin_handler(update, context):
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id):
        await update.message.reply_text("❌ Acesso negado. Apenas administradores podem usar este comando.")
        return
    
    # Estatísticas do sistema
    stats_api = api_rate_limiter.get_stats()
    status_api = db.get_api_status()
    usuarios_ativos = len(filtros_por_chat.keys())
    
    # Contagem de alertas hoje
    total_alertas_hoje = _count_alerts_on_date(date.today())
    
    status_icone = "✅" if status_api.get("odds_api_ok") else "❌"
    status_msg = status_api.get("odds_api_message", "Desconhecido")
    status_detalhes = status_api.get("odds_api_details")
    atualizado_em = status_api.get("updated_at")
    if atualizado_em:
        try:
            from datetime import timezone, timedelta
            dt = datetime.fromisoformat(atualizado_em)
            # Se não tem timezone, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            # Converte para horário de Brasília (UTC-3)
            brasilia_tz = timezone(timedelta(hours=-3))
            dt_brasilia = dt.astimezone(brasilia_tz)
            atualizado_em_fmt = dt_brasilia.strftime("%d/%m/%Y %H:%M:%S")
        except ValueError:
            atualizado_em_fmt = atualizado_em
    else:
        atualizado_em_fmt = datetime.now().strftime("%H:%M:%S")

    msg = f"""
🔧 <b>Painel de Administração</b>

📊 <b>Status da API:</b>
• Usage: {stats_api['usage_percent']:.1f}% ({stats_api['requests_used']}/{stats_api['requests_max']})
• Requests restantes: {stats_api['requests_remaining']}
• Status: {status_msg} {status_icone}
"""

    if status_detalhes:
        msg += f"• Detalhes: {status_detalhes}\n"

    msg += f"""

👥 <b>Usuários:</b>
• Usuários ativos: {usuarios_ativos}
• Alertas enviados hoje: {total_alertas_hoje}

⚙️ <b>Sistema:</b>
• Última atualização: {atualizado_em_fmt}

<b>Comandos disponíveis:</b>
/admin_users - Ver lista de usuários
/admin_stats - Estatísticas detalhadas
/admin_broadcast - Enviar mensagem para todos
/admin_block_user - Bloquear usuário do bot
/admin_unblock_user - Desbloquear usuário bloqueado
"""
    
    await update.message.reply_text(msg, parse_mode="HTML")

# Comando para listar usuários
async def admin_users_handler(update, context):
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id):
        await update.message.reply_text("❌ Acesso negado.")
        return
    
    # Buscar todos os usuários do banco (incluindo bloqueados)
    all_users = db.get_all_users()
    
    if not all_users:
        await update.message.reply_text("🔭 Nenhum usuário cadastrado.")
        return
        
    msg = "👥 <b>Usuários do Sistema:</b>\n\n"
    
    for i, user in enumerate(all_users, 1):
        user_chat_id = str(user["chat_id"])
        is_blocked = user.get("is_blocked", False)
        
        # Status icon
        status_icon = "🚫" if is_blocked else "✅"
        
        # Contar alertas do usuário
        total_alertas = _count_user_alerts(user_chat_id)

        # Buscar filtros do usuário
        filtros = filtros_por_chat.get(user_chat_id, {})
        
        # Bookmakers do usuário
        bookmakers = filtros.get("bookmakers", [filtros.get("bookmaker", "Bet365")])
        if isinstance(bookmakers, str):
            bookmakers = [bookmakers]

        nome = user.get("nome") or filtros.get("nome")
        username = user.get("username") or filtros.get("username")
        nome_formatado = html.escape(nome) if nome else None
        username_limpo = username.lstrip("@") if username else None
        username_formatado = html.escape(username_limpo) if username_limpo else None

        if nome_formatado and username_formatado:
            identificacao = f"{nome_formatado} (@{username_formatado})"
        elif nome_formatado:
            identificacao = nome_formatado
        elif username_formatado:
            identificacao = f"@{username_formatado}"
        else:
            identificacao = "Usuário sem nome"

        msg += f"<b>{i}.</b> {status_icon} {identificacao} — Chat ID: <code>{user_chat_id}</code>\n"
        msg += f"   • Bookmakers: {', '.join(bookmakers)}\n"
        msg += f"   • Total alertas: {total_alertas}\n"
        ligas_usuario = filtros.get("ligas")
        if not ligas_usuario:
            ligas_desc = "Todas"
        else:
            ligas_desc = f"{len(ligas_usuario)} definidas"
        msg += f"   • Ligas: {ligas_desc}\n\n"
    
    await update.message.reply_text(msg, parse_mode="HTML")

# Comando para estatísticas detalhadas
async def admin_stats_handler(update, context):
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id):
        await update.message.reply_text("❌ Acesso negado.")
        return
    
    # Análise dos arquivos de histórico
    total_alertas = 0
    usuarios_com_alertas = 0
    bookmakers_usados = {}
    
    for user_chat_id in filtros_por_chat.keys():
        alertas_usuario = _fetch_alert_history(user_chat_id)
        if not alertas_usuario:
            continue

        usuarios_com_alertas += 1
        total_alertas += len(alertas_usuario)

        # Contar bookmakers
        for alerta in alertas_usuario:
            bk = alerta.get("bookmaker", "Desconhecido") or "Desconhecido"
            bookmakers_usados[bk] = bookmakers_usados.get(bk, 0) + 1
    
    # Top 3 bookmakers
    top_bookmakers = sorted(bookmakers_usados.items(), key=lambda x: x[1], reverse=True)[:3]
    
    msg = f"""
📈 <b>Estatísticas Detalhadas</b>

📊 <b>Alertas:</b>
• Total de alertas enviados: {total_alertas}
• Usuários com histórico: {usuarios_com_alertas}
• Média por usuário ativo: {total_alertas/usuarios_com_alertas if usuarios_com_alertas > 0 else 0:.1f}

🏢 <b>Bookmakers mais usados:</b>
"""
    
    for i, (bk, count) in enumerate(top_bookmakers, 1):
        msg += f"{i}. {bk}: {count} alertas\n"
    
    # Análise de arquivos do sistema
    cache_entries = _count_api_cache_entries()
    msg += "\n💾 <b>Sistema:</b>\n"
    msg += f"• Registros em cache: {cache_entries}\n"
    
    await update.message.reply_text(msg, parse_mode="HTML")

# Comando para broadcast
async def admin_broadcast_handler(update, context):
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id):
        await update.message.reply_text("❌ Acesso negado.")
        return
    
    if not context.args:
            await update.message.reply_text(
            "📢 <b>Uso:</b> <code>/admin_broadcast sua mensagem aqui</code>\n\n"
            "Esta mensagem será enviada para todos os usuários ativos.",
            parse_mode="HTML"
        )
            return
    
    mensagem = " ".join(context.args)
    enviados = 0
    falhas = 0
    
    await update.message.reply_text("📤 Enviando mensagem para todos os usuários...")
    
    for user_chat_id in filtros_por_chat.keys():
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            params = {
                "chat_id": user_chat_id,
                "text": f"📢 <b>Mensagem do Administrador:</b>\n\n{mensagem}",
                "parse_mode": "HTML"
            }
            
            import requests
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                enviados += 1
            else:
                falhas += 1
                
        except Exception:
            falhas += 1
    
    await update.message.reply_text(
        f"✅ Broadcast concluído!\n"
        f"• Enviados: {enviados}\n"
        f"• Falhas: {falhas}"
    )

# Comando para bloquear usuário
async def admin_block_user_handler(update, context):
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id):
        await update.message.reply_text("❌ Acesso negado.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Uso: /admin_block_user CHAT_ID\n"
            "Use /admin_users para ver os IDs dos usuários."
        )
        return
    
    try:
        target_chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Chat ID inválido. Use apenas números.")
        return
    
    # Verificar se usuário existe
    user = db.get_user(target_chat_id)
    if not user:
        await update.message.reply_text(f"❌ Usuário {target_chat_id} não encontrado.")
        return
    
    # Verificar se já está bloqueado
    if db.is_user_blocked(target_chat_id):
        await update.message.reply_text(f"⚠️ Usuário já está bloqueado.")
        return
    
    # Bloquear usuário
    db.block_user(target_chat_id)
    
    # Remover do cache de filtros
    if str(target_chat_id) in filtros_por_chat:
        del filtros_por_chat[str(target_chat_id)]
    
    nome = user.get('nome') or user.get('username') or 'Sem nome'
    await update.message.reply_text(
        f"✅ Usuário bloqueado com sucesso!\n\n"
        f"👤 Nome: {nome}\n"
        f"🆔 Chat ID: {target_chat_id}\n\n"
        f"O usuário não receberá mais alertas até ser desbloqueado."
    )

# Comando para desbloquear usuário
async def admin_unblock_user_handler(update, context):
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id):
        await update.message.reply_text("❌ Acesso negado.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Uso: /admin_unblock_user CHAT_ID\n"
            "Use /admin_users para ver os usuários bloqueados."
        )
        return
    
    try:
        target_chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Chat ID inválido. Use apenas números.")
        return
    
    # Verificar se usuário existe
    user = db.get_user(target_chat_id)
    if not user:
        await update.message.reply_text(f"❌ Usuário {target_chat_id} não encontrado.")
        return
    
    # Verificar se está bloqueado
    if not db.is_user_blocked(target_chat_id):
        await update.message.reply_text(f"⚠️ Usuário não está bloqueado.")
        return
    
    # Desbloquear usuário
    db.unblock_user(target_chat_id)
    
    # Recarregar filtros do usuário
    user_complete = db.get_user_complete(target_chat_id)
    if user_complete and db.usuario_configurado(target_chat_id):
        filtros_por_chat[str(target_chat_id)] = user_complete
    
    nome = user.get('nome') or user.get('username') or 'Sem nome'
    await update.message.reply_text(
        f"✅ Usuário desbloqueado com sucesso!\n\n"
        f"👤 Nome: {nome}\n"
        f"🆔 Chat ID: {target_chat_id}\n\n"
        f"O usuário voltará a receber alertas normalmente."
    )

async def ligas_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    args = context.args

    if not args:
        await update.message.reply_text(
            "Use: /ligas [região] [esporte (opcional)]\nExemplo: /ligas brasil\nOu: /ligas europa basquete"
        )
        return

    regiao = args[0].capitalize()
    esporte_pt = args[1].lower() if len(args) > 1 else "futebol"
    esporte_en = TRADUCAO_ESPORTE_EN.get(esporte_pt, "Football")
    catalogo = carregar_catalogo_ligas()
    ligas = catalogo.get(regiao, {}).get(esporte_en, [])

    if not ligas:
        await update.message.reply_text(f"Nenhuma liga encontrada para {regiao} - {esporte_pt.title()}.")
        return

    # Armazena seleção temporária em context.user_data
    context.user_data["ligas_selecao"] = {
        "regiao": regiao,
        "esporte": esporte_en,
        "todas_ligas": ligas,
        "selecionadas": set(ligas)  # default: todas marcadas
    }

    await update.message.reply_text(
        f"Selecione as ligas de {regiao} - {esporte_pt.title()} que deseja ativar:",
        reply_markup=gerar_botoes_ligas(ligas, set(ligas))
    )

async def ligas_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat.id)
    data = query.data

    filtros_usuario, _ = atualizar_info_usuario(chat_id, update.effective_user)

    selecao = context.user_data.get("ligas_selecao")
    if not selecao:
        await query.edit_message_text("Sessão de seleção expirada. Use /ligas novamente.")
        return

    if data.startswith("liga_toggle|"):
        liga = data.split("|", 1)[1]
        if liga in selecao["selecionadas"]:
            selecao["selecionadas"].remove(liga)  # Remove se já estava selecionada
        else:
            selecao["selecionadas"].add(liga)     # Adiciona se não estava selecionada
        
        # Atualiza botões
        await query.edit_message_reply_markup(
            reply_markup=gerar_botoes_ligas(selecao["todas_ligas"], selecao["selecionadas"])
        )
        
    elif data == "liga_salvar":
        filtros_usuario["ligas"] = sorted(selecao["selecionadas"])
        filtros_usuario["esportes"] = None
        salvar_filtros()
        await query.edit_message_text(
            f"✅ Filtro atualizado! {len(selecao['selecionadas'])} ligas salvas."
        )
        # Limpa a seleção do usuário apenas após salvar
        context.user_data.pop("ligas_selecao", None)

async def escolher_bookmaker(update, context):
    chat_id = str(update.effective_chat.id)
    filtros_por_chat.setdefault(chat_id, {})
    selecionados = filtros_por_chat[chat_id].get("bookmaker", "Bet365")

    api = OddsAPI()
    lista_bk = await api.get_bookmakers()
    context.user_data["bookmakers_lista"] = lista_bk
    context.user_data["bookmaker_selecionados"] = set([selecionados])
    context.user_data["bookmaker_pagina"] = 0  # Começa na página 0

    await enviar_pagina_bookmakers(update, context)

def gerar_botoes_bookmakers(lista, selecionados, pagina=0):
    total_paginas = ceil(len(lista) / BOOKMAKERS_POR_PAGINA)
    inicio = pagina * BOOKMAKERS_POR_PAGINA
    fim = inicio + BOOKMAKERS_POR_PAGINA
    slice_bk = lista[inicio:fim]

    botoes = []
    for i in range(0, len(slice_bk), 2):
        linha = []
        for j in range(2):
            if i + j < len(slice_bk):
                bk = slice_bk[i + j]
                marcado = "✅" if bk in selecionados else "☑️"
                linha.append(InlineKeyboardButton(f"{marcado} {bk}", callback_data=f"bookmaker|{bk}"))
        botoes.append(linha)

    nav = []
    if pagina > 0:
        nav.append(InlineKeyboardButton("⬅️ Anterior", callback_data="bookmaker_prev"))
    if fim < len(lista):
        nav.append(InlineKeyboardButton("Próxima ➡️", callback_data="bookmaker_next"))
    if nav:
        botoes.append(nav)

    botoes.append([InlineKeyboardButton("💾 Salvar", callback_data="bookmaker_salvar")])
    return InlineKeyboardMarkup(botoes)

async def enviar_pagina_bookmakers(update, context):
    lista = context.user_data["bookmakers_lista"]
    selecionados = context.user_data.get("bookmaker_selecionados", set(["Bet365"]))
    pagina = context.user_data.get("bookmaker_pagina", 0)

    reply_markup = gerar_botoes_bookmakers(lista, selecionados, pagina)

    if update.callback_query:
        await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)
    else:
        await update.message.reply_text(
            "🎰 Escolha sua casa de aposta preferida:",
            reply_markup=reply_markup
        )

async def callback_bookmaker(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    data = query.data

    if "bookmakers_lista" not in context.user_data:
        await query.edit_message_text("Sessão expirada. Use /bookmakers novamente.")
        return

    if data == "bookmaker_prev":
        context.user_data["bookmaker_pagina"] = max(0, context.user_data["bookmaker_pagina"] - 1)
        await enviar_pagina_bookmakers(update, context)

    elif data == "bookmaker_next":
        total = len(context.user_data["bookmakers_lista"])
        max_pagina = ceil(total / BOOKMAKERS_POR_PAGINA) - 1
        context.user_data["bookmaker_pagina"] = min(max_pagina, context.user_data["bookmaker_pagina"] + 1)
        await enviar_pagina_bookmakers(update, context)

    elif data.startswith("bookmaker|"):
        escolhido = data.split("|")[1]
        selecionados = context.user_data.get("bookmaker_selecionados", set())
        if escolhido in selecionados:
            selecionados.remove(escolhido)
        else:
            selecionados.add(escolhido)
        context.user_data["bookmaker_selecionados"] = selecionados
        await enviar_pagina_bookmakers(update, context)

    elif data == "bookmaker_salvar":
        selecionados = list(context.user_data.get("bookmaker_selecionados", ["Bet365"]))
        filtros_por_chat.setdefault(chat_id, {})["bookmakers"] = selecionados
        salvar_filtros()
        
        # Verificar se está em modo setup
        if context.user_data.get("setup_mode"):
            context.user_data.pop("setup_mode", None)
            await query.edit_message_text(
                f"✅ <b>Casas selecionadas:</b> {', '.join(selecionados)}\n\n"
                "Continuando setup...",
                parse_mode="HTML"
            )
            # Vai para próximo passo do setup
            await setup_passo2_callback(update, context)
        else:
            # Modo normal - usuário já configurado, volta para o menu
            await query.edit_message_text(
                f"✅ <b>Casas de aposta atualizadas:</b> {', '.join(selecionados)}\n\n"
                "Voltando ao menu principal...",
                parse_mode="HTML"
            )
            # Volta para o menu principal do usuário configurado
            filtros_usuario = filtros_por_chat.get(chat_id, {})
            await start_usuario_configurado_callback(query, context, filtros_usuario)

# ===== FILTROS DE DATA =====
async def filtros_data_handler(update, context):
    """Menu para configurar filtros de data"""
    keyboard = [
        [InlineKeyboardButton("📅 1 Dia", callback_data="data_dinamica|1")],
        [InlineKeyboardButton("📅 2 Dias", callback_data="data_dinamica|2")],
        [InlineKeyboardButton("📅 3 Dias", callback_data="data_dinamica|3")],
        [InlineKeyboardButton("📅 7 Dias", callback_data="data_dinamica|7")],
        [InlineKeyboardButton("♾️ Ilimitado", callback_data="data_dinamica|0")],
        [InlineKeyboardButton("🗓️ Período específico", callback_data="data_estatica")],
        [InlineKeyboardButton("🧹 Remover filtro de data", callback_data="data_remover")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="reconfigurar")],
    ]
    
    msg = (
        "📅 <b>Filtro de Data dos Jogos</b>\n\n"
        "🔄 <b>Dinâmico (recomendado):</b>\n"
        "Sempre os próximos X dias a partir de hoje (renova automaticamente)\n\n"
        "📅 <b>1 Dia:</b> Dentro de 24 horas\n"
        "📅 <b>2 Dias:</b> Dentro de 48 horas\n"
        "📅 <b>3 Dias:</b> Dentro de 72 horas\n"
        "📅 <b>7 Dias:</b> Dentro de 168 horas\n"
        "♾️ <b>Ilimitado:</b> Sempre ativo\n\n"
        "⚠️ <b>Estático:</b>\n"
        "Período fixo que expira\n\n"
        "Escolha sua preferência:"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )

async def callback_data_dinamica(update, context):
    """Configura filtro dinâmico"""
    query = update.callback_query
    await query.answer()
    
    dias = int(query.data.split("|")[1])
    chat_id = str(query.message.chat_id)
    
    # Remove filtros estáticos e adiciona dinâmico
    filtros_por_chat.setdefault(chat_id, {})
    filtros_por_chat[chat_id].pop("data_inicio", None)
    filtros_por_chat[chat_id].pop("data_fim", None)
    filtros_por_chat[chat_id]["filtro_dias"] = dias
    
    salvar_filtros()
    
    # Se usuário já configurado, volta para o menu
    if usuario_configurado(int(chat_id)):
        from datetime import timezone
        hoje = datetime.now(timezone.utc).date()
        data_fim = hoje + timedelta(days=dias)
        msg = f"✅ Filtro de data configurado: {dias} dias\n🔄 Hoje até {data_fim.strftime('%d/%m/%Y')}\n\nVoltando ao menu principal..."
        await query.edit_message_text(msg, parse_mode="HTML")
        filtros_usuario = filtros_por_chat.get(chat_id, {})
        await start_usuario_configurado_callback(query, context, filtros_usuario)
        return
    
    from datetime import timezone
    hoje = datetime.now(timezone.utc).date()
    data_fim = hoje + timedelta(days=dias)
    await query.edit_message_text(
        f"✅ <b>Filtro dinâmico configurado!</b>\n\n"
        f"📅 {dias} dias (renova automaticamente)\n"
        f"🔄 Hoje até {data_fim.strftime('%d/%m/%Y')}\n\n"
        f"💡 <i>Se atualiza automaticamente todos os dias!</i>",
        parse_mode="HTML"
    )

async def callback_data_estatica(update, context):
    """Ativa modo de entrada manual de data"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["esperando_data_estatica"] = True
    
    await query.edit_message_text(
        "🗓️ <b>Período Específico</b>\n\n"
        "Envie as datas no formato:\n"
        "<code>DD/MM/AAAA DD/MM/AAAA</code>\n\n"
        "📝 <b>Exemplos:</b>\n"
        "• <code>25/09/2025 30/09/2025</code>\n"
        "• <code>01/10/2025 15/10/2025</code>\n\n"
        "⚠️ <i>Filtro estático expira nas datas definidas</i>",
        parse_mode="HTML"
    )

async def callback_data_remover(update, context):
    """Remove filtros de data"""
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    
    filtros_por_chat.setdefault(chat_id, {})
    filtros_por_chat[chat_id].pop("data_inicio", None)
    filtros_por_chat[chat_id].pop("data_fim", None)
    filtros_por_chat[chat_id].pop("filtro_dias", None)
    
    salvar_filtros()
    
    await query.edit_message_text(
        "🧹 <b>Filtro de data removido!</b>\n\n"
        "Agora você receberá alertas de jogos em qualquer data.",
        parse_mode="HTML"
    )

async def processar_data_estatica(update, context):
    """Processa entrada manual de data estática"""
    if not context.user_data.get("esperando_data_estatica"):
        return False
    
    entrada = update.message.text.strip()
    context.user_data["esperando_data_estatica"] = False
    chat_id = str(update.effective_chat.id)
    
    try:
        # Espera formato "DD/MM/AAAA DD/MM/AAAA"
        partes = entrada.split()
        if len(partes) != 2:
            raise ValueError("Formato inválido")
        
        data_inicio_str, data_fim_str = partes
        
        # Validar e converter datas
        data_inicio = datetime.strptime(data_inicio_str, "%d/%m/%Y").date()
        data_fim = datetime.strptime(data_fim_str, "%d/%m/%Y").date()
        
        if data_inicio > data_fim:
            raise ValueError("Data início deve ser anterior à data fim")
        
        # Converter para formato ISO (YYYY-MM-DD) para salvar
        data_inicio_iso = data_inicio.strftime("%Y-%m-%d")
        data_fim_iso = data_fim.strftime("%Y-%m-%d")
        
        # Salvar
        filtros_por_chat.setdefault(chat_id, {})
        filtros_por_chat[chat_id].pop("filtro_dias", None)  # Remove dinâmico
        filtros_por_chat[chat_id]["data_inicio"] = data_inicio_iso
        filtros_por_chat[chat_id]["data_fim"] = data_fim_iso
        salvar_filtros()
        
        diferenca_dias = (data_fim - data_inicio).days + 1
        
        await update.message.reply_text(
            f"✅ <b>Período específico configurado!</b>\n\n"
            f"📅 <b>De:</b> {data_inicio_str}\n"
            f"📅 <b>Até:</b> {data_fim_str}\n"
            f"📊 <b>Total:</b> {diferenca_dias} dias\n\n"
            f"⚠️ <i>Filtro estático - expira após as datas</i>",
            parse_mode="HTML"
        )
        return True
        
    except Exception:
        await update.message.reply_text(
            "❌ <b>Formato inválido!</b>\n\n"
            "Use o formato: <code>DD/MM/AAAA DD/MM/AAAA</code>\n\n"
            "📝 <b>Exemplo correto:</b>\n"
            "<code>25/09/2025 30/09/2025</code>",
            parse_mode="HTML"
        )
        return True

# ===== FILTROS DE HORÁRIO =====
async def filtros_horario_handler(update, context):
    """Menu para configurar filtros de horário"""
    chat_id = str(update.effective_chat.id if update.callback_query else update.effective_chat.id)
    filtros = filtros_por_chat.get(chat_id, {})
    
    horario_atual = ""
    h_ini = filtros.get("horario_inicio")
    h_fim = filtros.get("horario_fim")
    if h_ini and h_fim:
        horario_atual = f"\n🕐 <b>Atual:</b> {h_ini} às {h_fim}"
    
    keyboard = [
        [InlineKeyboardButton("🌅 Manhã (06:00-12:00)", callback_data="horario_preset|06:00|12:00")],
        [InlineKeyboardButton("☀️ Tarde (12:00-18:00)", callback_data="horario_preset|12:00|18:00")],
        [InlineKeyboardButton("🌆 Noite (18:00-23:59)", callback_data="horario_preset|18:00|23:59")],
        [InlineKeyboardButton("🌙 Madrugada (00:00-06:00)", callback_data="horario_preset|00:00|06:00")],
        [InlineKeyboardButton("🏢 Comercial (08:00-18:00)", callback_data="horario_preset|08:00|18:00")],
        [InlineKeyboardButton("⚽ Futebol BR (19:00-23:00)", callback_data="horario_preset|19:00|23:00")],
        [InlineKeyboardButton("⚙️ Horário personalizado", callback_data="horario_custom")],
        [InlineKeyboardButton("🧹 Remover filtro", callback_data="horario_remover")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="reconfigurar")],
    ]
    
    msg = (
        f"🕐 <b>Filtro de Horário dos Jogos</b>{horario_atual}\n\n"
        "Escolha apenas jogos que começam dentro do horário desejado:\n\n"
        "💡 <i>Horário baseado no fuso do Brasil (UTC-3)</i>"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )

async def callback_horario_preset(update, context):
    """Aplica horário pré-definido"""
    query = update.callback_query
    await query.answer()
    
    _, inicio, fim = query.data.split("|")
    chat_id = str(query.message.chat_id)
    
    filtros_por_chat.setdefault(chat_id, {})
    filtros_por_chat[chat_id]["horario_inicio"] = inicio
    filtros_por_chat[chat_id]["horario_fim"] = fim
    
    salvar_filtros()
    
    # Determinar nome do período
    nome_periodo = {
        ("06:00", "12:00"): "Manhã",
        ("12:00", "18:00"): "Tarde", 
        ("18:00", "23:59"): "Noite",
        ("00:00", "06:00"): "Madrugada",
        ("08:00", "18:00"): "Comercial",
        ("19:00", "23:00"): "Futebol BR"
    }.get((inicio, fim), "Personalizado")
    
    # Se usuário já configurado, volta para o menu
    if usuario_configurado(int(chat_id)):
        msg = f"✅ Filtro de horário configurado!\n🕐 Período: {nome_periodo}\n⏰ Horário: {inicio} às {fim}\n\nVoltando ao menu principal..."
        await query.edit_message_text(msg, parse_mode="HTML")
        filtros_usuario = filtros_por_chat.get(chat_id, {})
        await start_usuario_configurado_callback(query, context, filtros_usuario)
        return
    
    await query.edit_message_text(
        f"✅ <b>Filtro de horário configurado!</b>\n\n"
        f"🕐 <b>Período:</b> {nome_periodo}\n"
        f"⏰ <b>Horário:</b> {inicio} às {fim}\n\n"
        f"🎯 Você receberá alertas apenas de jogos que começam neste horário.",
        parse_mode="HTML"
    )

async def callback_horario_custom(update, context):
    """Ativa modo de entrada manual de horário"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["esperando_horario_custom"] = True

    await query.edit_message_text(
        "⚙️ <b>Horário Personalizado</b>\n\n"
        "Envie o horário no formato:\n"
        "<code>HH:MM HH:MM</code>\n\n"
        "📝 <b>Exemplos:</b>\n"
        "• <code>14:00 22:30</code> → 14h às 22h30\n"
        "• <code>09:15 17:45</code> → 9h15 às 17h45\n"
        "• <code>20:00 02:00</code> → 20h às 2h (cruza meia-noite)\n\n"
        "💡 Use formato 24h (00:00 até 23:59)",
        parse_mode="HTML"
    )

async def callback_horario_remover(update, context):
    """Remove filtros de horário"""
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    
    filtros_por_chat.setdefault(chat_id, {})
    filtros_por_chat[chat_id].pop("horario_inicio", None)
    filtros_por_chat[chat_id].pop("horario_fim", None)
    
    salvar_filtros()
    
    await query.edit_message_text(
        "🧹 <b>Filtro de horário removido!</b>\n\n"
        "Agora você receberá alertas de jogos em qualquer horário.",
        parse_mode="HTML"
    )

async def processar_horario_custom(update, context):
    """Processa entrada manual de horário"""
    if not context.user_data.get("esperando_horario_custom"):
        return False
    
    entrada = update.message.text.strip()
    context.user_data["esperando_horario_custom"] = False
    chat_id = str(update.effective_chat.id)
    
    try:
        # Espera formato "HH:MM HH:MM"
        partes = entrada.split()
        if len(partes) != 2:
            raise ValueError("Formato inválido")
        
        inicio, fim = partes
        
        # Validar formato HH:MM
        datetime.strptime(inicio, "%H:%M")
        datetime.strptime(fim, "%H:%M")
        
        # Salvar
        filtros_por_chat.setdefault(chat_id, {})
        filtros_por_chat[chat_id]["horario_inicio"] = inicio
        filtros_por_chat[chat_id]["horario_fim"] = fim
        salvar_filtros()
        
        # Determinar se cruza meia-noite
        cruza_meia_noite = inicio > fim
        nota_extra = "\n\n🌙 <i>Horário cruza a meia-noite</i>" if cruza_meia_noite else ""
        
        await update.message.reply_text(
            f"✅ <b>Horário personalizado configurado!</b>\n\n"
            f"⏰ <b>Das:</b> {inicio}\n"
            f"⏰ <b>Até:</b> {fim}{nota_extra}",
            parse_mode="HTML"
        )
        return True
        
    except Exception:
                await update.message.reply_text(
            "❌ <b>Formato inválido!</b>\n\n"
            "Use o formato: <code>HH:MM HH:MM</code>\n\n"
            "📝 <b>Exemplo correto:</b>\n"
            "<code>14:30 22:00</code>",
            parse_mode="HTML"
        )
    return True

# ===== MENUS E CONFIGURAÇÕES =====

async def reconfigurar_callback(update, context):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🏠 Mudar Casas de Aposta", callback_data="reconfig_bookmakers")],
        [InlineKeyboardButton("🏆 Escolher Ligas", callback_data="escolher_ligas_visual")],
        [InlineKeyboardButton("📈 Alterar EV Mínimo", callback_data="ev_menu")],
        [InlineKeyboardButton("🌍 Trocar Esportes/Regiões", callback_data="escolher_esportes")],
        [InlineKeyboardButton("📅 Filtros de Data", callback_data="filtros_data")],
        [InlineKeyboardButton("🕐 Filtros de Horário", callback_data="filtros_horario")],
        [InlineKeyboardButton("🗑️ Limpar Filtros", callback_data="menu_limpar")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="start_inicial")],
    ]
    
    await query.edit_message_text(
        "⚙️ <b>Alterar Configurações</b>\n\nO que você quer modificar?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def ev_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu de EV - VERSÃO CORRIGIDA"""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("✏️ Configurar EV", callback_data="ev_custom")],
        [InlineKeyboardButton("🧹 Remover filtro de EV", callback_data="ev_remove")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="reconfigurar")],
    ]

    await query.edit_message_text(
        "📈 <b>Configuração de EV</b>\n\n"
        "Configure o valor esperado mínimo (ou faixa) para receber alertas.\n\n"
        "📝 <b>Opções:</b>\n"
        "• Apenas mínimo: <code>0.05</code>\n"
        "• Faixa completa: <code>0.03 0.12</code>\n\n"
        "💡 <b>Dica:</b> Comece com 5% ou 8%",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def ev_custom_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """EV personalizado - VERSÃO CORRIGIDA (igual sua foto)"""
    query = update.callback_query
    await query.answer()
    context.user_data["esperando_ev_manual"] = True
    await query.edit_message_text(
        "📈 <b>Configuração de EV</b>\n\n"
        "✏️ <b>Envie sua configuração de EV:</b>\n\n"
        "• <b>Apenas mínimo:</b> <code>0.01</code> (1% ou mais)\n"
        "• <b>Faixa completa:</b> <code>0.01 0.15</code> (1% até 15%)\n"
        "• <b>Sem limite superior:</b> basta mandar um valor (ex: <code>0.03</code>)\n\n"
        "👉 <b>Use valores decimais, onde 0.05 = 5%</b>",
        parse_mode="HTML"
    )

async def capturar_input_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NOVO: Verificar se está em setup
    if context.user_data.get("setup_esperando_ev"):
        return await processar_setup_ev_manual(update, context)
    
    if context.user_data.get("setup_esperando_horario"):
        return await processar_setup_horario_manual(update, context)
    
    # Verificar se é horário customizado
    if await processar_horario_custom(update, context):
                return
            
    # Verificar se é data estática
    if await processar_data_estatica(update, context):
        return
    
    chat_id = str(update.effective_chat.id)

    # Caso EV manual - VERSÃO CORRIGIDA (com faixa)
    if context.user_data.get("esperando_ev_manual"):
        try:
            entrada = update.message.text.strip()
            partes = entrada.split()
            
            if len(partes) == 1:
                # Apenas mínimo
                ev_min = float(partes[0])
                if ev_min < 0.01 or ev_min > 10.0:
                    raise ValueError("Fora do range")
                
                filtros_por_chat.setdefault(chat_id, {})["ev_faixa_min"] = ev_min
                filtros_por_chat[chat_id]["ev_faixa_max"] = 9999.0  # Sem limite superior
                msg = f"✅ <b>EV configurado: {ev_min*100:.1f}% ou mais</b>"
                
            elif len(partes) == 2:
                # Faixa completa
                ev_min, ev_max = float(partes[0]), float(partes[1])
                
                if ev_min < 0.01 or ev_min > 10.0:
                    raise ValueError("Min fora do range")
                if ev_max < ev_min or ev_max > 10.0:
                    raise ValueError("Max inválido")
                
                filtros_por_chat.setdefault(chat_id, {})["ev_faixa_min"] = ev_min
                filtros_por_chat[chat_id]["ev_faixa_max"] = ev_max
                msg = f"✅ <b>EV configurado: {ev_min*100:.1f}% até {ev_max*100:.1f}%</b>"
                
            else:
                raise ValueError("Formato inválido")
            
            salvar_filtros()
            context.user_data["esperando_ev_manual"] = False
            await update.message.reply_text(msg, parse_mode="HTML")
            return
            
        except Exception:
            context.user_data["esperando_ev_manual"] = False
            await update.message.reply_text(
                "❌ <b>Formato inválido!</b>\n\n"
                "📝 <b>Formatos aceitos:</b>\n"
                "• <code>0.05</code> → 5% ou mais\n"
                "• <code>0.03 0.12</code> → 3% até 12%\n\n"
                "👉 Use valores entre 0.01 e 10.0",
                parse_mode="HTML"
            )
            return

async def ev_remove_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)

    filtros_por_chat.setdefault(chat_id, {})
    filtros_por_chat[chat_id].pop("ev_faixa_min", None)
    filtros_por_chat[chat_id].pop("ev_faixa_max", None)
    salvar_filtros()

    await query.edit_message_text("🧹 <b>Filtro de EV removido!</b>\n\nVoltará ao padrão (≥ 5%).", parse_mode="HTML")

# ----- Botões de resposta interativa -----
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = str(query.message.chat_id)
    filtros_usuario, _ = atualizar_info_usuario(chat_id, update.effective_user)

    data = query.data.lower()
    catalogo = carregar_catalogo_ligas()

    if data == "brasil":
        ligas_brasil_atuais = catalogo.get("Brasil", {}).get("Football", [])
        filtros_usuario["ligas"] = ligas_brasil_atuais
        filtros_usuario["esportes"] = None
        msg = "✅ Filtro ajustado para: 🇧🇷 Brasil (ligas dinâmicas da API)."
        
        # Se usuário já configurado, volta para o menu
        if usuario_configurado(int(chat_id)):
            salvar_filtros()
            await query.edit_message_text(
                f"{msg}\n\nVoltando ao menu principal...",
                parse_mode="HTML"
            )
            await start_usuario_configurado_callback(query, context, filtros_usuario)
            return

    elif data == "europa":
        ligas_europa_atuais = catalogo.get("Europa", {}).get("Football", [])
        filtros_usuario["ligas"] = ligas_europa_atuais
        filtros_usuario["esportes"] = None
        msg = "✅ Filtro ajustado para: 🇪🇺 Europa (ligas dinâmicas da API)."
        
        # Se usuário já configurado, volta para o menu
        if usuario_configurado(int(chat_id)):
            salvar_filtros()
            await query.edit_message_text(
                f"{msg}\n\nVoltando ao menu principal...",
                parse_mode="HTML"
            )
            await start_usuario_configurado_callback(query, context, filtros_usuario)
            return

    elif data == "americasul":
        ligas_america_sul_atuais = catalogo.get("América do Sul", {}).get("Football", [])
        filtros_usuario["ligas"] = ligas_america_sul_atuais
        filtros_usuario["esportes"] = None
        msg = "✅ Filtro ajustado para: 🌎 América do Sul (ligas dinâmicas da API)."
        
        # Se usuário já configurado, volta para o menu
        if usuario_configurado(int(chat_id)):
            salvar_filtros()
            await query.edit_message_text(
                f"{msg}\n\nVoltando ao menu principal...",
                parse_mode="HTML"
            )
            await start_usuario_configurado_callback(query, context, filtros_usuario)
            return

    elif data == "todos":
        filtros_usuario["ligas"] = None
        filtros_usuario["esportes"] = None
        msg = "✅ Filtro removido! Você receberá alertas de todas as ligas."
        
        # Se usuário já configurado, volta para o menu
        if usuario_configurado(int(chat_id)):
            salvar_filtros()
            await query.edit_message_text(
                f"{msg}\n\nVoltando ao menu principal...",
                parse_mode="HTML"
            )
            await start_usuario_configurado_callback(query, context, filtros_usuario)
            return

    elif data == "setup_passo1":
        await setup_passo1_callback(update, context)
        return
    
    elif data == "setup_bookmakers":
        await setup_bookmakers_callback(update, context)
        return

    elif data == "setup_passo2":
        await setup_passo2_callback(update, context)
        return

    elif data == "setup_passo3":
        await setup_passo3_callback(update, context)
        return

    elif data.startswith("setup_regiao|"):
        await setup_regiao_callback(update, context)
        return

    elif data == "setup_passo4":
        await setup_passo4_callback(update, context)
        return

    elif data == "setup_passo5":
        await setup_passo5_callback(update, context)
        return

    elif data.startswith("setup_dias|"):
        await setup_dias_callback(update, context)
        return

    elif data.startswith("setup_horario|"):
        await setup_horario_callback(update, context)
        return

    elif data == "setup_finalizar":
        await setup_finalizar_callback(update, context)
        return

    elif data == "explicar_bot":
        await explicar_bot_callback(update, context)
        return

    elif data == "exemplo_alerta":
        await exemplo_alerta_callback(update, context)
        return

    elif data == "ver_filtros_completos":
        await ver_filtros_completos_callback(update, context)
        return

    elif data == "scan_manual_inline":
        await scan_manual_inline_callback(update, context)
        return

    elif data == "start_inicial":
        await start_inicial_callback(update, context)
        return

    elif data == "ver_historico":
        await ver_historico_callback(update, context)
        return

    elif data == "explicar_ligas_custom":
        await explicar_ligas_custom_callback(update, context)
        return

    elif data == "setup_ligas_custom":
        await setup_ligas_custom_callback(update, context)
        return

    elif data == "setup_horario_custom":
        await setup_horario_custom_callback(update, context)
        return

    elif data == "reconfigurar":
        await reconfigurar_callback(update, context)
        return

    elif data == "reconfig_bookmakers":
        await escolher_bookmaker(update, context)
        return

    elif data == "ev_menu":
        await ev_menu_handler(update, context)
        return

    elif data == "ev_custom":
        await ev_custom_handler(update, context)
        return

    elif data == "ev_remove":
        await ev_remove_handler(update, context)
        return

    elif data == "filtros_data":
        await filtros_data_handler(update, context)
        return

    elif data.startswith("data_dinamica|"):
        await callback_data_dinamica(update, context)
        return

    elif data == "data_estatica":
        await callback_data_estatica(update, context)
        return

    elif data == "data_remover":
        await callback_data_remover(update, context)
        return

    elif data == "filtros_horario":
        await filtros_horario_handler(update, context)
        return

    elif data.startswith("horario_preset|"):
        await callback_horario_preset(update, context)
        return

    elif data == "horario_custom":
        await callback_horario_custom(update, context)
        return

    elif data == "horario_remover":
        await callback_horario_remover(update, context)
        return

    elif data == "escolher_ligas_visual":
        await escolher_ligas_visual_callback(update, context)
        return

    elif data == "escolher_esportes":
        await escolher_esportes_callback(update, context)
        return

    elif data == "menu_limpar":
        await menu_limpar_callback(update, context)
        return
    elif data == "explicar_esportes_comando":
        await explicar_esportes_comando_callback(update, context)
        return

    elif data == "explicar_ligas_comando":
        await explicar_ligas_comando_callback(update, context)
        return

    else:
        msg = "❓ Opção não reconhecida."

    salvar_filtros()
    await query.edit_message_text(text=msg, parse_mode="HTML")

    # ===== FUNÇÕES AUXILIARES FALTANTES =====

async def escolher_ligas_visual_callback(update, context):
    """Menu visual para escolha de ligas"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🇧🇷 Brasil", callback_data="brasil")],
        [InlineKeyboardButton("🇪🇺 Europa", callback_data="europa")],
        [InlineKeyboardButton("🌎 América do Sul", callback_data="americasul")],
        [InlineKeyboardButton("🌍 Todas as Ligas", callback_data="todos")],
        [InlineKeyboardButton("⚙️ Personalizar via /ligas", callback_data="explicar_ligas_comando")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="reconfigurar")],
    ]
    
    await query.edit_message_text(
        "🏆 <b>Escolher Ligas</b>\n\n"
        "Selecione as regiões que você quer monitorar:\n\n"
        "🇧🇷 <b>Brasil:</b> Brasileirão, Copa do Brasil, etc.\n"
        "🇪🇺 <b>Europa:</b> Premier League, La Liga, etc.\n"
        "🌎 <b>América do Sul:</b> Libertadores, etc.\n"
        "🌍 <b>Todas:</b> Monitoramento global\n\n"
        "⚙️ Para seleção granular, use: <code>/ligas brasil futebol</code>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def escolher_esportes_callback(update, context):
    """Menu para escolher esportes"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("⚽ Só Futebol", callback_data="esporte_futebol")],
        [InlineKeyboardButton("🏀 Só Basquete", callback_data="esporte_basquete")],
        [InlineKeyboardButton("🎾 Só Tênis", callback_data="esporte_tenis")],
        [InlineKeyboardButton("🏈 Todos os Esportes", callback_data="esporte_todos")],
        [InlineKeyboardButton("⚙️ Personalizar via /esportes", callback_data="explicar_esportes_comando")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="reconfigurar")],
    ]
    
    await query.edit_message_text(
        "⚽ <b>Escolher Esportes</b>\n\n"
        "Quais esportes você quer monitorar?\n\n"
        "💡 Para seleção múltipla, use:\n"
        "<code>/esportes futebol basquete tenis</code>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def menu_limpar_callback(update, context):
    """Menu para limpar filtros"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🧹 Limpar TUDO", callback_data="limpar_todos")],
        [InlineKeyboardButton("📅 Só filtros de Data", callback_data="limpar_data")],
        [InlineKeyboardButton("🕐 Só filtros de Horário", callback_data="limpar_horario")],
        [InlineKeyboardButton("📈 Só filtros de EV", callback_data="limpar_ev")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="reconfigurar")],
    ]
    
    await query.edit_message_text(
        "🗑️ <b>Limpar Filtros</b>\n\n"
        "⚠️ <b>Atenção:</b> Esta ação não pode ser desfeita!\n\n"
        "O que você quer limpar?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def explicar_ligas_comando_callback(update, context):
    """Interface de checkbox para regiões"""
    query = update.callback_query
    await query.answer()
    
    regioes_disponiveis = ["Brasil", "Europa", "América do Sul", "Norte/Centro", "Ásia/Oceania", "Internacionais"]
    
    context.user_data["regioes_selecao"] = {
        "disponiveis": regioes_disponiveis,
        "selecionadas": set()
    }
    
    keyboard = []
    for regiao in regioes_disponiveis:
        keyboard.append([InlineKeyboardButton(f"☑️ {regiao}", callback_data=f"regiao_toggle|{regiao}")])
    
    keyboard.append([InlineKeyboardButton("💾 Aplicar Seleção", callback_data="regiao_salvar")])
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="escolher_ligas_visual")])
    
    await query.edit_message_text(
        "🏆 <b>Selecionar Regiões</b>\n\nMarque as regiões que quer monitorar:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def explicar_esportes_comando_callback(update, context):
    """Interface de checkbox para esportes - VERSÃO DINÂMICA"""
    query = update.callback_query
    await query.answer()
    
    # BUSCA ESPORTES DINAMICAMENTE DO CATÁLOGO DA API
    catalogo = carregar_catalogo_ligas()
    esportes_disponiveis = set()
    
    # Extrai todos os esportes únicos de todas as regiões
    for regiao_data in catalogo.values():
        if isinstance(regiao_data, dict):
            esportes_disponiveis.update(regiao_data.keys())
    
    # Converte para lista ordenada, com fallback se catálogo vazio
    if esportes_disponiveis:
        esportes_disponiveis = sorted(list(esportes_disponiveis))
    else:
        # Fallback caso catálogo ainda não exista
        esportes_disponiveis = ["Football", "Basketball", "Tennis", "Baseball", "Hockey", "MMA", "Boxing", "Volleyball"]
    
    chat_id = str(query.message.chat_id)
    filtros = filtros_por_chat.get(chat_id, {})
    esportes_selecionados = set(filtros.get("esportes", []))
    
    context.user_data["esportes_selecao"] = {
        "disponiveis": esportes_disponiveis,
        "selecionados": esportes_selecionados
    }
    
    keyboard = []
    for esporte in esportes_disponiveis:
        marcado = "✅" if esporte in esportes_selecionados else "☑️"
        keyboard.append([InlineKeyboardButton(f"{marcado} {esporte}", callback_data=f"esporte_toggle|{esporte}")])
    
    keyboard.append([InlineKeyboardButton("💾 Salvar Seleção", callback_data="esporte_salvar")])
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="escolher_esportes")])
    
    await query.edit_message_text(
        f"⚽ <b>Selecionar Esportes</b>\n\nMarque os esportes que quer monitorar:\n\n<i>📊 {len(esportes_disponiveis)} esportes encontrados na API</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

# Handlers para esportes individuais
async def esporte_callback_handler(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    data = query.data
    
    esporte_map = {
        "esporte_futebol": ["Football"],
        "esporte_basquete": ["Basketball"],
        "esporte_tenis": ["Tennis"],
        "esporte_todos": None
    }
    
    esportes = esporte_map.get(data)
    filtros_por_chat.setdefault(chat_id, {})["esportes"] = esportes
    salvar_filtros()
    
    if esportes:
        msg = f"✅ Esporte configurado: {esportes[0]}"
    else:
        msg = "✅ Todos os esportes habilitados"
    
    # Se usuário já configurado, volta para o menu
    if usuario_configurado(int(chat_id)):
        await query.edit_message_text(
            f"{msg}\n\nVoltando ao menu principal...",
            parse_mode="HTML"
        )
        filtros_usuario = filtros_por_chat.get(chat_id, {})
        await start_usuario_configurado_callback(query, context, filtros_usuario)
        return
    
    await query.edit_message_text(msg)

# Handlers para limpeza
async def limpar_callback_handler(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    data = query.data
    
    filtros_usuario = filtros_por_chat.setdefault(chat_id, {})
    
    if data == "limpar_todos":
        # Preserva apenas as configurações mínimas obrigatórias
        bookmakers = filtros_usuario.get("bookmakers", ["Bet365"])
        ev_min = filtros_usuario.get("ev_faixa_min", 0.05)
        nome = filtros_usuario.get("nome")
        username = filtros_usuario.get("username")
        
        filtros_por_chat[chat_id] = {
            "bookmakers": bookmakers,
            "ev_faixa_min": ev_min,
            "ligas": None,
            "esportes": None
        }
        
        if nome:
            filtros_por_chat[chat_id]["nome"] = nome
        if username:
            filtros_por_chat[chat_id]["username"] = username
            
        msg = "🧹 <b>Todos os filtros limpos!</b>\n\nConfiguração resetada para o padrão."
        
    elif data == "limpar_data":
        filtros_usuario.pop("data_inicio", None)
        filtros_usuario.pop("data_fim", None)
        filtros_usuario.pop("filtro_dias", None)
        msg = "📅 Filtros de data removidos"
        
    elif data == "limpar_horario":
        filtros_usuario.pop("horario_inicio", None)
        filtros_usuario.pop("horario_fim", None)
        msg = "🕐 Filtros de horário removidos"
        
    elif data == "limpar_ev":
        filtros_usuario.pop("ev_faixa_min", None)
        filtros_usuario.pop("ev_faixa_max", None)
        msg = "📈 Filtros de EV removidos"
    
    salvar_filtros()
    await query.edit_message_text(msg, parse_mode="HTML")

# ----- Filtros por região -----
async def set_brasil(update, context):
    chat_id = str(update.effective_chat.id)
    filtros_por_chat.setdefault(chat_id, {"ligas": [], "esportes": None})

    catalogo = carregar_catalogo_ligas()
    ligas_brasil_atuais = catalogo.get("Brasil", {}).get("Football", [])
    filtros_por_chat[chat_id]["ligas"] = ligas_brasil_atuais

    salvar_filtros()
    await update.message.reply_text("✅ Filtro ajustado para: 🇧🇷 Brasil (ligas dinâmicas da API).")

async def set_americasul(update, context):
    chat_id = str(update.effective_chat.id)
    filtros_por_chat.setdefault(chat_id, {"ligas": [], "esportes": None})

    catalogo = carregar_catalogo_ligas()
    ligas_america_sul_atuais = catalogo.get("América do Sul", {}).get("Football", [])
    filtros_por_chat[chat_id]["ligas"] = ligas_america_sul_atuais

    salvar_filtros()
    await update.message.reply_text("✅ Filtro ajustado para: 🌎 América do Sul (ligas dinâmicas da API).")

async def set_europa(update, context):
    chat_id = str(update.effective_chat.id)
    filtros_por_chat.setdefault(chat_id, {"ligas": [], "esportes": None})

    catalogo = carregar_catalogo_ligas()
    ligas_europa_atuais = catalogo.get("Europa", {}).get("Football", [])
    filtros_por_chat[chat_id]["ligas"] = ligas_europa_atuais

    salvar_filtros()
    await update.message.reply_text("✅ Filtro ajustado para: 🇪🇺 Europa (ligas dinâmicas da API).")

async def set_escandinavo(update, context):
    chat_id = str(update.effective_chat.id)
    filtros_por_chat.setdefault(chat_id, {"ligas": [], "esportes": None})

    catalogo = carregar_catalogo_ligas()
    ligas_escandinavo_atuais = []
    for regiao in ["Suécia", "Noruega", "Finlândia", "Dinamarca", "Islândia"]:
        ligas_escandinavo_atuais += catalogo.get(regiao, {}).get("Football", [])
    filtros_por_chat[chat_id]["ligas"] = ligas_escandinavo_atuais

    salvar_filtros()
    await update.message.reply_text("✅ Filtro ajustado para: ❄️ Escandinávia (ligas dinâmicas da API).")

async def set_norte_centro(update, context):
    chat_id = str(update.effective_chat.id)
    filtros_por_chat.setdefault(chat_id, {"ligas": [], "esportes": None})

    catalogo = carregar_catalogo_ligas()
    ligas_norte_centro_atuais = catalogo.get("Norte/Centro", {}).get("Football", [])
    filtros_por_chat[chat_id]["ligas"] = ligas_norte_centro_atuais

    salvar_filtros()
    await update.message.reply_text("✅ Filtro ajustado para: 🇺🇸 América do Norte/Centro (ligas dinâmicas da API).")

async def set_asia(update, context):
    chat_id = str(update.effective_chat.id)
    filtros_por_chat.setdefault(chat_id, {"ligas": [], "esportes": None})

    catalogo = carregar_catalogo_ligas()
    ligas_asia_atuais = catalogo.get("Ásia/Oceania", {}).get("Football", [])
    filtros_por_chat[chat_id]["ligas"] = ligas_asia_atuais

    salvar_filtros()
    await update.message.reply_text("✅ Filtro ajustado para: 🌏 Ásia/Oceania (ligas dinâmicas da API).")

async def set_feminino(update, context):
    chat_id = str(update.effective_chat.id)
    filtros_por_chat.setdefault(chat_id, {"ligas": [], "esportes": None})

    catalogo = carregar_catalogo_ligas()
    ligas_femininas_atuais = []
    # Futebol feminino em todas as regiões
    for regiao in catalogo:
        ligas_femininas_atuais += [
            liga for liga in catalogo[regiao].get("Football", []) if "Women" in liga
        ]
    filtros_por_chat[chat_id]["ligas"] = ligas_femininas_atuais

    salvar_filtros()
    await update.message.reply_text("✅ Filtro ajustado para: 👩‍🦰 Futebol Feminino (ligas dinâmicas da API).")

async def set_internacionais(update, context):
    chat_id = str(update.effective_chat.id)
    filtros_por_chat.setdefault(chat_id, {"ligas": [], "esportes": None})

    catalogo = carregar_catalogo_ligas()
    ligas_internacionais_atuais = catalogo.get("Internacionais", {}).get("Football", [])
    filtros_por_chat[chat_id]["ligas"] = ligas_internacionais_atuais

    salvar_filtros()
    await update.message.reply_text("✅ Filtro ajustado para: 🏆 Competições Internacionais (ligas dinâmicas da API).")

async def set_todos(update, context):
    chat_id = str(update.effective_chat.id)
    filtros_usuario, _ = atualizar_info_usuario(chat_id, update.effective_user)
    filtros_usuario["ligas"] = None
    filtros_usuario["esportes"] = None
    salvar_filtros()
    await update.message.reply_text("Filtro removido. Você receberá alertas de todas as ligas.")

# ----- Ver filtros -----
async def ver_filtros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    await ver_filtros_inline_detalhado(update, context, chat_id)

# ----- Filtro por esportes -----
ESPORTES_VALIDOS = {
    "futebol": "Football", "tenis": "Tennis", "tênis": "Tennis",
    "basquete": "Basketball", "beisebol": "Baseball", "hockey": "Hockey",
    "mma": "MMA", "boxe": "Boxing", "volei": "Volleyball", "vôlei": "Volleyball"
}

async def set_esportes(update, context):
    chat_id = str(update.effective_chat.id)
    argumentos = context.args
    if not argumentos:
        await update.message.reply_text("❗ Use: /esportes futebol tenis basquete")
        return

    esportes = [ESPORTES_VALIDOS[arg.lower()] for arg in argumentos if arg.lower() in ESPORTES_VALIDOS]
    if not esportes:
        await update.message.reply_text("⚠️ Nenhum esporte reconhecido.")
        return

    filtros_por_chat.setdefault(chat_id, {})["esportes"] = esportes
    salvar_filtros()
    await update.message.reply_text(f"✅ Esportes configurados: {', '.join(esportes)}")

# ----- /ajuda -----
async def ajuda(update, context):
    msg = (
        "👋 <b>Bem-vindo ao Bot EV+</b>\n\n"
        "Você pode filtrar as apostas por região, esporte ou selecionar ligas específicas!\n\n"
        "<b>Filtros rápidos:</b>\n"
        "• /brasil — Receba alertas de todas as ligas do Brasil 🇧🇷\n"
        "• /europa — Todas as ligas europeias 🇪🇺\n"
        "• /americasul — América do Sul 🌎\n"
        "• /internacionais — Copas e amistosos 🌍\n"
        "• /feminino — Só futebol feminino 👩‍🦰\n\n"
        "<b>Personalização avançada:</b>\n"
        "• /esportes futebol basquete — Receba só os esportes desejados\n"
        "• /ligas brasil futebol — Selecione as ligas do Brasil (ex: só Serie A e Copa do Brasil)\n\n"
        "<b>Exemplo prático:</b>\n"
        "1️⃣ Digite: <code>/ligas brasil futebol</code>\n"
        "2️⃣ Marque/desmarque as ligas que deseja nos botões\n"
        "3️⃣ Toque em 💾 Salvar filtro para aplicar\n\n"
        "<b>Outros comandos:</b>\n"
        "• /filtros — Ver filtros ativos\n"
        "• /todos — Remover todos os filtros\n"
        "• /scan — Rodar busca manual\n"
        "• /ajuda — Ver esta mensagem\n\n"
        "ℹ️ <i>Quanto mais específico o filtro, mais personalizado o alerta!</i>"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

# ----- /scan manual -----
async def scan_handler(update, context):
    await update.message.reply_text("🔎 Iniciando scan manual...")
    chat_id = str(update.effective_chat.id)
    
    # Scan individual para o usuário específico
    resultado = await scan_apostas_usuario(chat_id)
    await update.message.reply_text(f"✅ Scan finalizado!\n{resultado}")

async def stats_handler(update, context):
    chat_id = str(update.effective_chat.id)
    
    # Estatísticas da API
    stats_api = api_rate_limiter.get_stats()
    msg = f"📊 **Status do Sistema:**\n"
    msg += f"• API Usage: {stats_api['usage_percent']:.1f}% ({stats_api['requests_used']}/{stats_api['requests_max']})\n"
    msg += f"• Requests restantes: {stats_api['requests_remaining']}\n\n"
    
    alertas_usuario = _fetch_alert_history(chat_id)
    if alertas_usuario:
        total = len(alertas_usuario)
        evs = [float(row["ev"]) for row in alertas_usuario if row.get("ev") is not None]
        ev_medio = sum(evs) / len(evs) if evs else 0
        msg += f"📈 **Suas estatísticas:**\n"
        msg += f"• Total de alertas: {total}\n"
        msg += f"• EV médio: {ev_medio:.2%}\n"
    else:
        msg += "📈 Nenhum histórico encontrado."
    
    await update.message.reply_text(msg)

# ----- Fallback para comandos inválidos -----
async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Comando não reconhecido. Digite /ajuda para ver as opções disponíveis.")

# ----- Inicializar bot -----
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Comandos principais
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", start))
app.add_handler(CommandHandler("ajuda", ajuda))
app.add_handler(CommandHandler("scan", scan_handler))
app.add_handler(CommandHandler("stats", stats_handler))
app.add_handler(CommandHandler("filtros", ver_filtros))
app.add_handler(CommandHandler("bookmakers", escolher_bookmaker))
app.add_handler(CallbackQueryHandler(callback_bookmaker, pattern="^bookmaker"))
app.add_handler(CommandHandler("filtrosdata", filtros_data_handler))
app.add_handler(CommandHandler("filtroshorario", filtros_horario_handler))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), capturar_input_manual))

#Comandos admin
app.add_handler(CommandHandler("admin", admin_handler))
app.add_handler(CommandHandler("admin_users", admin_users_handler))
app.add_handler(CommandHandler("admin_stats", admin_stats_handler))
app.add_handler(CommandHandler("admin_broadcast", admin_broadcast_handler))
app.add_handler(CommandHandler("admin_block_user", admin_block_user_handler))
app.add_handler(CommandHandler("admin_unblock_user", admin_unblock_user_handler))

# Comandos de filtro por região
app.add_handler(CommandHandler("brasil", set_brasil))
app.add_handler(CommandHandler("americasul", set_americasul))
app.add_handler(CommandHandler("europa", set_europa))
app.add_handler(CommandHandler("escandinavo", set_escandinavo))
app.add_handler(CommandHandler("nortecentro", set_norte_centro))
app.add_handler(CommandHandler("asia", set_asia))
app.add_handler(CommandHandler("feminino", set_feminino))
app.add_handler(CommandHandler("internacionais", set_internacionais))
app.add_handler(CommandHandler("todos", set_todos))

# Callbacks para interfaces de checkbox
app.add_handler(CallbackQueryHandler(esporte_toggle_handler, pattern="^esporte_toggle\\|"))
app.add_handler(CallbackQueryHandler(esporte_salvar_handler, pattern="^esporte_salvar$"))
app.add_handler(CallbackQueryHandler(regiao_toggle_handler, pattern="^regiao_toggle\\|"))
app.add_handler(CallbackQueryHandler(regiao_salvar_handler, pattern="^regiao_salvar$"))

# Comando de filtro por esportes
app.add_handler(CommandHandler("esportes", set_esportes))

# Comando de personalização por ligas (com botões)
app.add_handler(CommandHandler("ligas", ligas_handler))
app.add_handler(CallbackQueryHandler(ligas_callback_handler, pattern="^liga_"))

# Callbacks para filtros de data
app.add_handler(CallbackQueryHandler(callback_data_dinamica, pattern="^data_dinamica\\|"))
app.add_handler(CallbackQueryHandler(callback_data_estatica, pattern="^data_estatica$"))
app.add_handler(CallbackQueryHandler(callback_data_remover, pattern="^data_remover$"))

# Callbacks para filtros de horário
app.add_handler(CallbackQueryHandler(callback_horario_preset, pattern="^horario_preset\\|"))
app.add_handler(CallbackQueryHandler(callback_horario_custom, pattern="^horario_custom$"))
app.add_handler(CallbackQueryHandler(callback_horario_remover, pattern="^horario_remover$"))

# Callbacks para esportes
app.add_handler(CallbackQueryHandler(esporte_callback_handler, pattern="^esporte_"))

# Callbacks para limpeza
app.add_handler(CallbackQueryHandler(limpar_callback_handler, pattern="^limpar_"))

# Botões interativos das regiões (start e presets) - DEVE SER O ÚLTIMO
app.add_handler(CallbackQueryHandler(callback_handler))

# Comando inválido (fallback)
app.add_handler(MessageHandler(filters.COMMAND, fallback_handler))

if __name__ == "__main__":
    print("🚀 Bot EV+ iniciado!")
    print(f"📊 {len(filtros_por_chat)} usuários carregados")
    app.run_polling()