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
from database import DatabaseError, SQLiteConnectionConfig, SQLiteConnectionPool
from filtros import validar_filtros
from math import ceil
from rate_limiter import api_rate_limiter
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
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

BOT_DB_PATH = Path(os.getenv("BOT_DB_PATH", "bot.sqlite3"))
_DB_POOL = SQLiteConnectionPool(SQLiteConnectionConfig(BOT_DB_PATH))


def _fetch_alert_history(chat_id: str) -> list[dict[str, object]]:
    try:
        with _DB_POOL.connection() as conn:
            rows = conn.execute(
                """
                SELECT ah.event_date, ah.home_team, ah.away_team, ah.ev_value,
                       ah.bookmaker, ah.league, ah.odds, ah.stake, ah.created_at
                  FROM alert_history ah
                  JOIN users u ON u.id = ah.user_id
                 WHERE u.chat_id = ?
                 ORDER BY ah.created_at ASC
                """,
                (chat_id,),
            ).fetchall()
    except DatabaseError as exc:
        logging.error("Erro ao carregar histórico do chat %s: %s", chat_id, exc)
        return []

    alertas: list[dict[str, object]] = []
    for row in rows:
        data_evento = row["event_date"]
        if isinstance(data_evento, str):
            try:
                data_evento = datetime.fromisoformat(data_evento)
            except ValueError:
                data_evento = None
        created_at = row["created_at"]
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = None

        referencia = data_evento or created_at
        data_envio = referencia.isoformat() if isinstance(referencia, datetime) else None

        alertas.append(
            {
                "data_envio": data_envio,
                "home": row["home_team"],
                "away": row["away_team"],
                "ev": row["ev_value"],
                "bookmaker": row["bookmaker"],
                "league": row["league"],
                "odds": row["odds"],
                "stake": row["stake"],
            }
        )

    return alertas


def _count_user_alerts(chat_id: str) -> int:
    try:
        with _DB_POOL.connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total
                  FROM alert_history ah
                  JOIN users u ON u.id = ah.user_id
                 WHERE u.chat_id = ?
                """,
                (chat_id,),
            ).fetchone()
            return int(row["total"]) if row else 0
    except DatabaseError as exc:
        logging.error("Erro ao contar alertas do chat %s: %s", chat_id, exc)
        return 0


def _count_alerts_on_date(target_date: datetime.date) -> int:
    inicio = datetime.combine(target_date, datetime.min.time())
    fim = inicio + timedelta(days=1)
    inicio_str = inicio.isoformat(sep=" ")
    fim_str = fim.isoformat(sep=" ")

    try:
        with _DB_POOL.connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total
                  FROM alert_history
                 WHERE (created_at >= ? AND created_at < ?)
                    OR (datetime(event_date) >= datetime(?) AND datetime(event_date) < datetime(?))
                """,
                (inicio_str, fim_str, inicio_str, fim_str),
            ).fetchone()
            return int(row["total"]) if row else 0
    except DatabaseError as exc:
        logging.error("Erro ao contar alertas do dia %s: %s", target_date, exc)
        return 0


def _count_api_cache_entries() -> int:
    try:
        with _DB_POOL.connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM api_cache").fetchone()
            return int(row["total"]) if row else 0
    except DatabaseError as exc:
        logging.error("Erro ao consultar quantidade de cache: %s", exc)
        return 0

def is_admin(chat_id):
    """Verifica se o usuário é admin"""
    return str(chat_id) == ADMIN_CHAT_ID

# ----- Carregar filtros diretamente do banco de dados -----
def carregar_filtros_startup():
    logging.info("🔍 Carregamento de filtros iniciado...")
    try:
        filtros = validar_filtros()
        logging.info(f"✅ {len(filtros)} filtros carregados")
        return filtros
    except Exception as exc:
        logging.error(f"❌ Erro no carregamento: {exc}")
        return {}

filtros_por_chat = carregar_filtros_startup()


def salvar_filtros():
    """Salva filtros diretamente no banco sem usar validar_filtros"""
    try:
        from filtros import _ensure_user, _persist_filter

        with _DB_POOL.transaction() as conn:
            for chat_id, filtros in filtros_por_chat.items():
                if filtros:  # Só salva se tem dados
                    user_id = _ensure_user(conn, str(chat_id), filtros)
                    _persist_filter(conn, user_id, filtros)

        logging.info(f"💾 {len(filtros_por_chat)} filtros salvos no banco")
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
        if filtros and not usuario_configurado(filtros):
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
    global filtros_por_chat
    
    hoje = datetime.now().date()
    conversoes = 0
    
    for chat_id, filtros in filtros_por_chat.items():
        data_inicio_str = filtros.get("data_inicio")
        data_fim_str = filtros.get("data_fim")
        
        # Se tem filtro estático
        if data_inicio_str and data_fim_str and not filtros.get("filtro_dias"):
            try:
                data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
                
                # Se o filtro estático já expirou
                if data_fim < hoje:
                    logging.info(f"🔄 Convertendo filtro estático expirado para dinâmico: {chat_id}")
                    
                    # Remove filtro estático
                    filtros.pop("data_inicio", None)
                    filtros.pop("data_fim", None)
                    
                    # Adiciona filtro dinâmico de 7 dias
                    filtros["filtro_dias"] = 7
                    
                    conversoes += 1
                    logging.info(f"   ✅ {chat_id}: Estático expirado → Dinâmico 7 dias")
                    
            except Exception as e:
                logging.warning(f"Erro ao converter filtro de {chat_id}: {e}")
    
    if conversoes > 0:
        salvar_filtros()
        logging.info(f"✅ {conversoes} filtros estáticos expirados convertidos para dinâmico")
    
    return conversoes

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
    if usuario_configurado(filtros_usuario):
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
        status_data = f"Próximos {filtro_dias} dias 🔄"
    elif data_inicio and data_fim:
        # Verifica se é estático e se expirou
        try:
            data_fim_obj = datetime.strptime(data_fim, "%Y-%m-%d").date()
            hoje = datetime.now().date()
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
        "🔔 <i>Alertas enviados a cada 3 minutos</i>"
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
        status_data = f"Próximos {filtro_dias} dias 🔄"
    elif data_inicio and data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, "%Y-%m-%d").date()
            hoje = datetime.now().date()
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
        "🔔 <i>Alertas enviados a cada 3 minutos</i>"
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
        "⚡ <b>Setup Rápido (2 minutos):</b>\n"
        "1️⃣ 🏠 Escolher suas casas de aposta favoritas\n"
        "2️⃣ 📈 Definir seu EV mínimo (recomendado: 5%)\n"
        "3️⃣ 🌍 Selecionar ligas de interesse\n"
        "4️⃣ 🕐 Configurar horários preferidos\n\n"
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
        "⚡ <b>Setup Rápido (2 minutos):</b>\n"
        "1️⃣ 🏠 Escolher suas casas de aposta favoritas\n"
        "2️⃣ 📈 Definir seu EV mínimo (recomendado: 5%)\n"
        "3️⃣ 🌍 Selecionar ligas de interesse\n"
        "4️⃣ 🕐 Configurar horários preferidos\n\n"
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

# ===== FUNÇÕES PRINCIPAIS RESTANTES =====

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
    resultado = await scan_apostas(chat_id)
    
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
    
    if usuario_configurado(filtros_usuario):
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
        msg += f"\n📅 <b>Datas:</b> Próximos {filtro_dias} dias (dinâmico)\n"
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

# ===== FUNÇÕES DE CONFIGURAÇÃO =====

async def escolher_bookmaker(update, context):
    chat_id = str(update.effective_chat.id)
    filtros_por_chat.setdefault(chat_id, {})
    selecionados = filtros_por_chat[chat_id].get("bookmaker", "Bet365")

    api = OddsAPI()
    lista_bk = api.listar_bookmakers()
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
            # Modo normal
            await query.edit_message_text(f"✅ Casas de aposta salvas: {', '.join(selecionados)}")

# ===== PROCESSAMENTO DE INPUT MANUAL =====

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
        
        # Vai para próximo passo
        await setup_passo3_callback(update, context)
        return True
        
    except Exception:
        await update.message.reply_text(
            "❌ <b>Formato inválido!</b>\n\n"
            "📝 <b>Formatos aceitos:</b>\n"
            "• <code>0.05</code> → 5% ou mais\n"
            "• <code>0.03 0.12</code> → 3% até 12%\n\n"
            "👉 Use valores entre 0.01 e 10.0",
            parse_mode="HTML"
        )
        return True

async def capturar_input_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NOVO: Verificar se está em setup
    if context.user_data.get("setup_esperando_ev"):
        return await processar_setup_ev_manual(update, context)
    
    # Resposta padrão para mensagens não reconhecidas
    await update.message.reply_text(
        "🤖 Use /start para configurar o bot ou /ajuda para ver os comandos disponíveis."
    )

# ===== CALLBACK HANDLER PRINCIPAL =====

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = str(query.message.chat_id)
    filtros_usuario, _ = atualizar_info_usuario(chat_id, update.effective_user)

    data = query.data.lower()

    if data == "setup_passo1":
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

    else:
        msg = "❓ Opção não reconhecida."

    salvar_filtros()
    await query.edit_message_text(text=msg, parse_mode="HTML")

# ===== COMANDOS ADMINISTRATIVOS =====

async def admin_handler(update, context):
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id):
        await update.message.reply_text("❌ Acesso negado. Apenas administradores podem usar este comando.")
        return
    
    # Estatísticas do sistema
    stats_api = api_rate_limiter.get_stats()
    status_api = get_odds_api_status()
    usuarios_ativos = len(filtros_por_chat.keys())
    
    # Contagem de alertas hoje
    total_alertas_hoje = _count_alerts_on_date(date.today())
    
    status_icone = "✅" if status_api.get("ok") else "❌"
    status_msg = status_api.get("mensagem", "Desconhecido")
    status_detalhes = status_api.get("detalhes")
    atualizado_em = status_api.get("atualizado_em")
    if atualizado_em:
        try:
            atualizado_em_fmt = datetime.fromisoformat(atualizado_em).astimezone().strftime("%d/%m/%Y %H:%M:%S")
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
"""
    
    await update.message.reply_text(msg, parse_mode="HTML")

# ===== COMANDOS BÁSICOS =====

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

async def scan_handler(update, context):
    await update.message.reply_text("🔎 Iniciando scan manual...")
    chat_id = str(update.effective_chat.id)
    resultado = await scan_apostas(chat_id)
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

async def ver_filtros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    await ver_filtros_inline_detalhado(update, context, chat_id)

# ===== INICIALIZAÇÃO DO BOT =====

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
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), capturar_input_manual))

# Comandos admin
app.add_handler(CommandHandler("admin", admin_handler))

# Callbacks principais
app.add_handler(CallbackQueryHandler(callback_handler))

# Comando inválido (fallback)
app.add_handler(MessageHandler(filters.COMMAND, lambda update, context: update.message.reply_text("❓ Comando não reconhecido. Digite /ajuda para ver as opções disponíveis.")))

if __name__ == "__main__":
    print("🚀 Bot EV+ iniciado!")
    print(f"📊 {len(filtros_por_chat)} usuários carregados")
    app.run_polling()
    
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
        "🌍 <b>Passo 3/4: Regiões de Interesse</b>\n\n"
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
    
    # Vai para passo final
    await setup_passo4_callback(update, context)

async def setup_passo4_callback(update, context):
    """Passo 4: Configurações opcionais"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🌆 Apenas Noite (19h-23h)", callback_data="setup_horario|19:00|23:00")],
        [InlineKeyboardButton("☀️ Apenas Tarde (14h-18h)", callback_data="setup_horario|14:00|18:00")],
        [InlineKeyboardButton("🕐 Personalizar Horário", callback_data="setup_horario_custom")],
        [InlineKeyboardButton("⏭️ Pular (24h)", callback_data="setup_finalizar")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="setup_passo3")],
    ]
    
    msg = (
        "🕐 <b>Passo 4/4: Horários (Opcional)</b>\n\n"
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
    horario_inicio = filtros.get("horario_inicio")
    horario_fim = filtros.get("horario_fim")
    
    # EV texto
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
        "🔔 <b>A partir de agora você receberá alertas automáticos!</b>\n\n"
        "📡 <i>Monitoramento ativo a cada 5 minutos</i>\n"
        "💡 <i>Use /start para gerenciar suas configurações</i>"
    )
    
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
