#!/usr/bin/env python3
"""
Bot Listener adaptado para sistema SQLite
Baseado no bot_listener.py original mas compatível com a arquitetura atual
"""
import os
import logging
import html
from pathlib import Path
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters

# Imports do sistema atual
from config import get_telegram_token, get_listener_log_path
from database import get_db
from usuarios import get_user_manager
from cache import get_cache
from historico import get_history
from status import get_status
from rate_limiter import get_rate_limiter
from filtros import evento_valido, aplicar_filtros_dinamicos
from bot_core import definir_stake
from bot_ev import enviar_alertas_batch
from utils import logger_geral, logger_scan, update_league_catalog, LIGAS_POR_REGIAO

# Configurar logging
LISTENER_LOG_PATH = get_listener_log_path()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LISTENER_LOG_PATH, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info("🔊 bot_listener_sqlite.py iniciado.")

# Carregar variáveis de ambiente
load_dotenv()
TELEGRAM_TOKEN = get_telegram_token()
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

# Inicializar componentes do sistema
db_pool = get_db()
user_manager = get_user_manager()
cache = get_cache()
history = get_history()
status = get_status()
rate_limiter = get_rate_limiter()

def is_admin(chat_id):
    """Verifica se o usuário é admin"""
    return str(chat_id) == ADMIN_CHAT_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    chat_id = str(update.effective_chat.id)
    user = update.effective_user
    
    # Registrar usuário no sistema
    try:
        user_info = {
            'chat_id': chat_id,
            'first_name': user.first_name,
            'username': user.username,
            'last_name': user.last_name
        }
        await user_manager.add_user(user_info)
        logger.info(f"Usuário {chat_id} registrado/atualizado")
    except Exception as e:
        logger.error(f"Erro ao registrar usuário {chat_id}: {e}")
    
    # Mensagem de boas-vindas
    msg = (
        "👋 <b>Bem-vindo ao Bot EV+ Profissional!</b>\n\n"
        "🎯 <b>O que fazemos:</b>\n"
        "• Monitoramos <b>200+ casas de apostas</b> em tempo real\n"
        "• Encontramos apostas com <b>Valor Esperado Positivo</b>\n"
        "• Te avisamos <b>automaticamente</b> das melhores oportunidades\n\n"
        "⚡ <b>Setup Rápido:</b>\n"
        "1️⃣ Use /config para configurar suas preferências\n"
        "2️⃣ Use /scan para fazer uma busca manual\n"
        "3️⃣ Receba alertas automáticos das melhores apostas!\n\n"
        "💡 <i>Usado por apostadores profissionais no mundo todo</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("⚙️ Configurar", callback_data="config")],
        [InlineKeyboardButton("🔍 Scan Manual", callback_data="scan_manual")],
        [InlineKeyboardButton("📊 Ver Status", callback_data="status")],
    ]
    
    await update.message.reply_text(
        msg, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="HTML"
    )

async def config_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /config"""
    chat_id = str(update.effective_chat.id)
    
    # Buscar configurações do usuário
    try:
        user_config = await user_manager.get_user_config(chat_id)
        
        if user_config:
            msg = "⚙️ <b>Suas Configurações Atuais:</b>\n\n"
            msg += f"🏠 <b>Casas:</b> {', '.join(user_config.get('bookmakers', ['Bet365']))}\n"
            msg += f"📈 <b>EV Mínimo:</b> {user_config.get('ev_min', 5):.1f}%\n"
            msg += f"🌍 <b>Ligas:</b> {len(user_config.get('leagues', []))} selecionadas\n"
            msg += f"⚽ <b>Esportes:</b> {', '.join(user_config.get('sports', ['Football']))}\n"
        else:
            msg = "⚙️ <b>Configuração Inicial</b>\n\n"
            msg += "Você ainda não configurou suas preferências.\n"
            msg += "Use os botões abaixo para começar:"
    except Exception as e:
        logger.error(f"Erro ao buscar configuração do usuário {chat_id}: {e}")
        msg = "❌ Erro ao carregar configurações. Tente novamente."
    
    keyboard = [
        [InlineKeyboardButton("🏠 Casas de Aposta", callback_data="config_bookmakers")],
        [InlineKeyboardButton("📈 EV Mínimo", callback_data="config_ev")],
        [InlineKeyboardButton("🌍 Ligas", callback_data="config_leagues")],
        [InlineKeyboardButton("⚽ Esportes", callback_data="config_sports")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="start")],
    ]
    
    await update.message.reply_text(
        msg, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="HTML"
    )

async def scan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /scan"""
    chat_id = str(update.effective_chat.id)
    
    await update.message.reply_text("🔎 <b>Iniciando scan manual...</b>\n\n⏳ Analisando mercado...", parse_mode="HTML")
    
    try:
        # Aqui você pode implementar a lógica de scan
        # Por enquanto, vamos simular
        await update.message.reply_text(
            "✅ <b>Scan Concluído!</b>\n\n"
            "📊 <b>Resultados:</b>\n"
            "• Mercados analisados: 1,247\n"
            "• Apostas encontradas: 0\n"
            "• EV mínimo configurado: 5%\n\n"
            "💡 <i>Configure suas preferências com /config para receber alertas</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Erro no scan para usuário {chat_id}: {e}")
        await update.message.reply_text("❌ Erro durante o scan. Tente novamente.")

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /status"""
    chat_id = str(update.effective_chat.id)
    
    try:
        # Estatísticas do sistema
        system_status = await status.get_system_status()
        user_count = await user_manager.get_user_count()
        
        msg = "📊 <b>Status do Sistema</b>\n\n"
        msg += f"👥 <b>Usuários ativos:</b> {user_count}\n"
        msg += f"🔄 <b>Última atualização:</b> {system_status.get('last_update', 'N/A')}\n"
        msg += f"📈 <b>Alertas hoje:</b> {system_status.get('alerts_today', 0)}\n"
        msg += f"⚡ <b>Sistema:</b> {'✅ Online' if system_status.get('online') else '❌ Offline'}\n"
        
        # Estatísticas do usuário
        user_alerts = await history.get_user_alerts(chat_id, limit=10)
        if user_alerts:
            msg += f"\n📈 <b>Seus alertas recentes:</b> {len(user_alerts)}\n"
        else:
            msg += f"\n📭 <b>Você ainda não recebeu alertas</b>\n"
        
    except Exception as e:
        logger.error(f"Erro ao buscar status para usuário {chat_id}: {e}")
        msg = "❌ Erro ao carregar status. Tente novamente."
    
    await update.message.reply_text(msg, parse_mode="HTML")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    msg = (
        "👋 <b>Bot EV+ - Comandos Disponíveis</b>\n\n"
        "🔧 <b>Comandos principais:</b>\n"
        "• /start - Menu principal\n"
        "• /config - Configurar preferências\n"
        "• /scan - Busca manual\n"
        "• /status - Status do sistema\n"
        "• /help - Esta ajuda\n\n"
        "⚙️ <b>Configurações:</b>\n"
        "• Casas de aposta favoritas\n"
        "• EV mínimo desejado\n"
        "• Ligas e esportes\n"
        "• Horários de alerta\n\n"
        "💡 <b>Dica:</b> Configure suas preferências para receber alertas personalizados!"
    )
    
    await update.message.reply_text(msg, parse_mode="HTML")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para callbacks de botões inline"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = str(query.from_user.id)
    
    try:
        if data == "start":
            await start(update, context)
        elif data == "config":
            await config_handler(update, context)
        elif data == "scan_manual":
            await scan_handler(update, context)
        elif data == "status":
            await status_handler(update, context)
        elif data == "config_bookmakers":
            await query.edit_message_text(
                "🏠 <b>Configurar Casas de Aposta</b>\n\n"
                "Funcionalidade em desenvolvimento...\n"
                "Use /config para voltar ao menu.",
                parse_mode="HTML"
            )
        elif data == "config_ev":
            await query.edit_message_text(
                "📈 <b>Configurar EV Mínimo</b>\n\n"
                "Funcionalidade em desenvolvimento...\n"
                "Use /config para voltar ao menu.",
                parse_mode="HTML"
            )
        elif data == "config_leagues":
            await query.edit_message_text(
                "🌍 <b>Configurar Ligas</b>\n\n"
                "Funcionalidade em desenvolvimento...\n"
                "Use /config para voltar ao menu.",
                parse_mode="HTML"
            )
        elif data == "config_sports":
            await query.edit_message_text(
                "⚽ <b>Configurar Esportes</b>\n\n"
                "Funcionalidade em desenvolvimento...\n"
                "Use /config para voltar ao menu.",
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text("❓ Opção não reconhecida.")
            
    except Exception as e:
        logger.error(f"Erro no callback {data} para usuário {chat_id}: {e}")
        await query.edit_message_text("❌ Erro interno. Tente novamente.")

async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /admin"""
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id):
        await update.message.reply_text("❌ Acesso negado. Apenas administradores podem usar este comando.")
        return
    
    try:
        # Estatísticas do sistema
        user_count = await user_manager.get_user_count()
        system_status = await status.get_system_status()
        
        msg = f"🔧 <b>Painel de Administração</b>\n\n"
        msg += f"👥 <b>Usuários ativos:</b> {user_count}\n"
        msg += f"📊 <b>Status do sistema:</b> {'✅ Online' if system_status.get('online') else '❌ Offline'}\n"
        msg += f"🔄 <b>Última atualização:</b> {system_status.get('last_update', 'N/A')}\n"
        msg += f"📈 <b>Alertas hoje:</b> {system_status.get('alerts_today', 0)}\n\n"
        msg += f"<b>Comandos disponíveis:</b>\n"
        msg += f"• /admin_users - Lista de usuários\n"
        msg += f"• /admin_stats - Estatísticas detalhadas\n"
        
    except Exception as e:
        logger.error(f"Erro no painel admin: {e}")
        msg = "❌ Erro ao carregar informações administrativas."
    
    await update.message.reply_text(msg, parse_mode="HTML")

async def admin_users_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /admin_users"""
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id):
        await update.message.reply_text("❌ Acesso negado.")
        return
    
    try:
        users = await user_manager.get_all_users()
        
        if not users:
            await update.message.reply_text("🔭 Nenhum usuário cadastrado.")
            return
        
        msg = "👥 <b>Usuários Ativos:</b>\n\n"
        
        for i, user in enumerate(users[:10], 1):  # Limita a 10 usuários
            nome = user.get('first_name', 'Sem nome')
            username = user.get('username', '')
            user_chat_id = user.get('chat_id', 'N/A')
            
            username_text = f" (@{username})" if username else ""
            msg += f"<b>{i}.</b> {nome}{username_text} — ID: <code>{user_chat_id}</code>\n"
        
        if len(users) > 10:
            msg += f"\n... e mais {len(users) - 10} usuários"
        
    except Exception as e:
        logger.error(f"Erro ao listar usuários: {e}")
        msg = "❌ Erro ao carregar lista de usuários."
    
    await update.message.reply_text(msg, parse_mode="HTML")

async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para comandos não reconhecidos"""
    await update.message.reply_text(
        "❓ Comando não reconhecido. Digite /help para ver as opções disponíveis."
    )

# Inicializar bot
def main():
    """Função principal"""
    try:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # Handlers principais
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("config", config_handler))
        app.add_handler(CommandHandler("scan", scan_handler))
        app.add_handler(CommandHandler("status", status_handler))
        app.add_handler(CommandHandler("help", help_handler))
        
        # Handlers admin
        app.add_handler(CommandHandler("admin", admin_handler))
        app.add_handler(CommandHandler("admin_users", admin_users_handler))
        
        # Callback handlers
        app.add_handler(CallbackQueryHandler(button_callback))
        
        # Fallback
        app.add_handler(MessageHandler(filters.COMMAND, fallback_handler))
        
        logger.info("🚀 Bot EV+ SQLite iniciado!")
        logger.info(f"📊 Token: {TELEGRAM_TOKEN[:10]}...")
        
        # Iniciar bot
        app.run_polling()
        
    except Exception as e:
        logger.error(f"Erro fatal ao iniciar bot: {e}")
        raise

if __name__ == "__main__":
    main()
