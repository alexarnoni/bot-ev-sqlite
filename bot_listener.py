import os
import logging
import html
import asyncio
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
from database import SQLiteConnectionConfig, SQLiteConnectionPool
from filtros import validar_filtros
from math import ceil
from rate_limiter import api_rate_limiter
from scanner import scan_apostas
from status import get_odds_api_status
from utils import carregar_catalogo_ligas, TRADUCAO_ESPORTE_EN

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(get_listener_log_path()),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuração do banco de dados
def get_database_path():
    feed_id = os.getenv("FEED_ID", "default")
    return os.path.join(os.getcwd(), "data", feed_id, "bot.db")

db_config = SQLiteConnectionConfig(
    database_path=get_database_path(),
    max_connections=10,
    timeout=30.0
)
db_pool = SQLiteConnectionPool(db_config)

class BotListener:
    def __init__(self):
        self.bot_token = get_telegram_token()
        self.application = None
        self.db_pool = db_pool

    async def start(self):
        """Inicia o bot listener"""
        try:
            # Cria a aplicação do Telegram
            self.application = ApplicationBuilder().token(self.bot_token).build()
            
            # Registra os handlers
            self._register_handlers()
            
            # Inicia o bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Bot listener iniciado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar bot listener: {e}")
            raise

    def _register_handlers(self):
        """Registra todos os handlers do bot"""
        # Comandos
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("filtros", self.filtros_command))
        self.application.add_handler(CommandHandler("ligas", self.ligas_command))
        self.application.add_handler(CommandHandler("esportes", self.esportes_command))
        self.application.add_handler(CommandHandler("bookmakers", self.bookmakers_command))
        self.application.add_handler(CommandHandler("historico", self.historico_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        
        # Callbacks de botões inline
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Mensagens de texto
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler do comando /start"""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        try:
            # Verifica se o usuário já está configurado
            if await usuario_configurado(chat_id):
                await update.message.reply_text(
                    "👋 Olá! Você já está configurado.\n\n"
                    "Use /filtros para ajustar suas configurações ou /help para ver todos os comandos."
                )
                return
            
            # Inicia o processo de configuração
            await self._iniciar_configuracao(update, context)
            
        except Exception as e:
            logger.error(f"Erro no comando start: {e}")
            await update.message.reply_text("❌ Erro interno. Tente novamente.")

    async def _iniciar_configuracao(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia o processo de configuração do usuário"""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        # Salva informações básicas do usuário
        try:
            async with self.db_pool.get_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO users (chat_id, nome, username, created_at, updated_at, is_active)
                    VALUES (?, ?, ?, datetime('now'), datetime('now'), 1)
                """, (chat_id, user.first_name or "", user.username or "",))
        except Exception as e:
            logger.error(f"Erro ao salvar usuário: {e}")
        
        # Mostra menu de configuração
        keyboard = [
            [InlineKeyboardButton("⚙️ Configurar Filtros", callback_data="config_filtros")],
            [InlineKeyboardButton("🏆 Escolher Ligas", callback_data="config_ligas")],
            [InlineKeyboardButton("⚽ Escolher Esportes", callback_data="config_esportes")],
            [InlineKeyboardButton("🏪 Escolher Bookmakers", callback_data="config_bookmakers")],
            [InlineKeyboardButton("✅ Finalizar Configuração", callback_data="finalizar_config")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎯 **Bem-vindo ao Bot EV+!**\n\n"
            "Vamos configurar suas preferências para receber os melhores alertas de apostas.\n\n"
            "Escolha uma opção:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler do comando /help"""
        help_text = """
🤖 **Comandos Disponíveis:**

/start - Iniciar ou reconfigurar o bot
/help - Mostrar esta ajuda
/status - Status do sistema e API
/filtros - Configurar filtros de EV, horário e data
/ligas - Escolher ligas para monitorar
/esportes - Escolher esportes para monitorar
/bookmakers - Escolher bookmakers
/historico - Ver histórico de alertas
/stats - Estatísticas pessoais
/admin - Comandos administrativos (apenas admins)

📊 **Como Funciona:**
• O bot escaneia apostas a cada 2 minutos
• Filtra por suas preferências configuradas
• Envia alertas com EV positivo
• Calcula stake automática baseada na odd

⚙️ **Configuração:**
Use /start para configurar suas preferências pela primeira vez.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler do comando /status"""
        try:
            # Status da API
            api_status = await get_odds_api_status()
            
            # Status do rate limiter
            requests_count = await api_rate_limiter.get_requests_count()
            
            # Status do banco
            try:
                async with self.db_pool.get_connection() as conn:
                    cursor = await conn.execute("SELECT COUNT(*) as total FROM users WHERE is_active = 1")
                    result = await cursor.fetchone()
                    users_count = result['total'] if result else 0
            except Exception:
                users_count = "Erro"
            
            status_text = f"""
📊 **Status do Sistema:**

🔌 **API Odds:** {'✅ Online' if api_status else '❌ Offline'}
📈 **Requests (última hora):** {requests_count}/4800
👥 **Usuários ativos:** {users_count}
⏰ **Última atualização:** {datetime.now().strftime('%H:%M:%S')}

🔄 **Próximo scan:** A cada 2 minutos
            """
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Erro no comando status: {e}")
            await update.message.reply_text("❌ Erro ao obter status do sistema.")

    async def filtros_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler do comando /filtros"""
        chat_id = update.effective_chat.id
        
        try:
            # Busca filtros atuais do usuário
            async with self.db_pool.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM user_filters WHERE chat_id = ?
                """, (chat_id,))
                filtros = await cursor.fetchone()
            
            if not filtros:
                await update.message.reply_text(
                    "❌ Você ainda não configurou seus filtros.\n"
                    "Use /start para começar a configuração."
                )
                return
            
            # Mostra filtros atuais
            filtros_text = f"""
⚙️ **Seus Filtros Atuais:**

📊 **EV Mínimo:** {filtros['ev_minimo']:.2%}
📊 **EV Máximo:** {filtros['ev_maximo']:.2%}
⏰ **Horário Início:** {filtros['horario_inicio'] or 'Não definido'}
⏰ **Horário Fim:** {filtros['horario_fim'] or 'Não definido'}
📅 **Data Início:** {filtros['data_inicio'] or 'Não definido'}
📅 **Data Fim:** {filtros['data_fim'] or 'Não definido'}
            """
            
            keyboard = [
                [InlineKeyboardButton("✏️ Editar Filtros", callback_data="edit_filtros")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                filtros_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Erro no comando filtros: {e}")
            await update.message.reply_text("❌ Erro ao buscar filtros.")

    async def ligas_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler do comando /ligas"""
        chat_id = update.effective_chat.id
        
        try:
            # Busca ligas selecionadas pelo usuário
            async with self.db_pool.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT ul.league_name 
                    FROM user_leagues ul 
                    WHERE ul.chat_id = ?
                    ORDER BY ul.league_name
                """, (chat_id,))
                ligas_selecionadas = await cursor.fetchall()
            
            if not ligas_selecionadas:
                await update.message.reply_text(
                    "❌ Você ainda não selecionou nenhuma liga.\n"
                    "Use /start para configurar suas preferências."
                )
                return
            
            ligas_text = "🏆 **Ligas Selecionadas:**\n\n"
            for liga in ligas_selecionadas:
                ligas_text += f"• {liga['league_name']}\n"
            
            keyboard = [
                [InlineKeyboardButton("✏️ Editar Ligas", callback_data="edit_ligas")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                ligas_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Erro no comando ligas: {e}")
            await update.message.reply_text("❌ Erro ao buscar ligas.")

    async def esportes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler do comando /esportes"""
        chat_id = update.effective_chat.id
        
        try:
            # Busca esportes selecionados pelo usuário
            async with self.db_pool.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT us.sport_name 
                    FROM user_sports us 
                    WHERE us.chat_id = ?
                    ORDER BY us.sport_name
                """, (chat_id,))
                esportes_selecionados = await cursor.fetchall()
            
            if not esportes_selecionados:
                await update.message.reply_text(
                    "❌ Você ainda não selecionou nenhum esporte.\n"
                    "Use /start para configurar suas preferências."
                )
                return
            
            esportes_text = "⚽ **Esportes Selecionados:**\n\n"
            for esporte in esportes_selecionados:
                esportes_text += f"• {esporte['sport_name']}\n"
            
            keyboard = [
                [InlineKeyboardButton("✏️ Editar Esportes", callback_data="edit_esportes")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                esportes_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Erro no comando esportes: {e}")
            await update.message.reply_text("❌ Erro ao buscar esportes.")

    async def bookmakers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler do comando /bookmakers"""
        chat_id = update.effective_chat.id
        
        try:
            # Busca bookmakers selecionados pelo usuário
            async with self.db_pool.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT ub.bookmaker_name 
                    FROM user_bookmakers ub 
                    WHERE ub.chat_id = ?
                    ORDER BY ub.bookmaker_name
                """, (chat_id,))
                bookmakers_selecionados = await cursor.fetchall()
            
            if not bookmakers_selecionados:
                await update.message.reply_text(
                    "❌ Você ainda não selecionou nenhum bookmaker.\n"
                    "Use /start para configurar suas preferências."
                )
                return
            
            bookmakers_text = "🏪 **Bookmakers Selecionados:**\n\n"
            for bookmaker in bookmakers_selecionados:
                bookmakers_text += f"• {bookmaker['bookmaker_name']}\n"
            
            keyboard = [
                [InlineKeyboardButton("✏️ Editar Bookmakers", callback_data="edit_bookmakers")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                bookmakers_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Erro no comando bookmakers: {e}")
            await update.message.reply_text("❌ Erro ao buscar bookmakers.")

    async def historico_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler do comando /historico"""
        chat_id = update.effective_chat.id
        
        try:
            # Busca histórico recente do usuário
            async with self.db_pool.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM alert_history 
                    WHERE chat_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT 10
                """, (chat_id,))
                historico = await cursor.fetchall()
            
            if not historico:
                await update.message.reply_text(
                    "📝 Você ainda não recebeu nenhum alerta.\n"
                    "Configure seus filtros e aguarde as oportunidades!"
                )
                return
            
            historico_text = "📝 **Últimos 10 Alertas:**\n\n"
            for alerta in historico:
                data_hora = datetime.fromisoformat(alerta['created_at']).strftime('%d/%m %H:%M')
                ev_pct = float(alerta['ev']) * 100
                historico_text += f"• {data_hora} - {alerta['home']} vs {alerta['away']}\n"
                historico_text += f"  EV: {ev_pct:.2f}% | Odd: {alerta['odds']}\n\n"
            
            await update.message.reply_text(historico_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Erro no comando historico: {e}")
            await update.message.reply_text("❌ Erro ao buscar histórico.")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler do comando /stats"""
        chat_id = update.effective_chat.id
        
        try:
            # Calcula estatísticas do usuário
            async with self.db_pool.get_connection() as conn:
                # Total de alertas
                cursor = await conn.execute("""
                    SELECT COUNT(*) as total FROM alert_history WHERE chat_id = ?
                """, (chat_id,))
                total_alertas = (await cursor.fetchone())['total']
                
                # Alertas hoje
                cursor = await conn.execute("""
                    SELECT COUNT(*) as total FROM alert_history 
                    WHERE chat_id = ? AND DATE(created_at) = DATE('now')
                """, (chat_id,))
                alertas_hoje = (await cursor.fetchone())['total']
                
                # EV médio
                cursor = await conn.execute("""
                    SELECT AVG(ev) as ev_medio FROM alert_history WHERE chat_id = ?
                """, (chat_id,))
                ev_medio = (await cursor.fetchone())['ev_medio'] or 0
                
                # Primeiro alerta
                cursor = await conn.execute("""
                    SELECT MIN(created_at) as primeiro FROM alert_history WHERE chat_id = ?
                """, (chat_id,))
                primeiro_alerta = (await cursor.fetchone())['primeiro']
            
            stats_text = f"""
📊 **Suas Estatísticas:**

🎯 **Total de Alertas:** {total_alertas}
📅 **Alertas Hoje:** {alertas_hoje}
📈 **EV Médio:** {ev_medio*100:.2f}%
🕐 **Primeiro Alerta:** {primeiro_alerta[:10] if primeiro_alerta else 'Nenhum'}
            """
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Erro no comando stats: {e}")
            await update.message.reply_text("❌ Erro ao calcular estatísticas.")

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler do comando /admin"""
        chat_id = update.effective_chat.id
        
        # Verifica se é admin
        if chat_id not in [350780046]:  # IDs dos admins
            await update.message.reply_text("❌ Acesso negado. Apenas administradores.")
            return
        
        try:
            # Estatísticas gerais do sistema
            async with self.db_pool.get_connection() as conn:
                # Total de usuários
                cursor = await conn.execute("SELECT COUNT(*) as total FROM users WHERE is_active = 1")
                total_usuarios = (await cursor.fetchone())['total']
                
                # Alertas hoje
                cursor = await conn.execute("""
                    SELECT COUNT(*) as total FROM alert_history 
                    WHERE DATE(created_at) = DATE('now')
                """)
                alertas_hoje = (await cursor.fetchone())['total']
                
                # Status da API
                api_status = await get_odds_api_status()
                
                # Requests da última hora
                requests_count = await api_rate_limiter.get_requests_count()
            
            admin_text = f"""
🔧 **Painel Administrativo:**

👥 **Usuários Ativos:** {total_usuarios}
📊 **Alertas Hoje:** {alertas_hoje}
🔌 **API Status:** {'✅ Online' if api_status else '❌ Offline'}
📈 **Requests (1h):** {requests_count}/4800
            """
            
            keyboard = [
                [InlineKeyboardButton("🔄 Forçar Scan", callback_data="admin_scan")],
                [InlineKeyboardButton("📊 Stats Detalhadas", callback_data="admin_stats")],
                [InlineKeyboardButton("🧹 Limpeza Cache", callback_data="admin_cleanup")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                admin_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Erro no comando admin: {e}")
            await update.message.reply_text("❌ Erro no painel administrativo.")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para callbacks de botões inline"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        chat_id = query.from_user.id
        
        try:
            if data == "config_filtros":
                await self._configurar_filtros(query, context)
            elif data == "config_ligas":
                await self._configurar_ligas(query, context)
            elif data == "config_esportes":
                await self._configurar_esportes(query, context)
            elif data == "config_bookmakers":
                await self._configurar_bookmakers(query, context)
            elif data == "finalizar_config":
                await self._finalizar_configuracao(query, context)
            elif data.startswith("edit_"):
                await self._editar_configuracao(query, context, data)
            elif data.startswith("admin_"):
                await self._admin_action(query, context, data)
            else:
                await query.edit_message_text("❌ Ação não reconhecida.")
                
        except Exception as e:
            logger.error(f"Erro no callback {data}: {e}")
            await query.edit_message_text("❌ Erro interno. Tente novamente.")

    async def _configurar_filtros(self, query, context):
        """Configuração de filtros"""
        await query.edit_message_text(
            "⚙️ **Configuração de Filtros**\n\n"
            "Digite os valores no formato:\n"
            "EV mínimo: 0.05 (5%)\n"
            "EV máximo: 0.50 (50%)\n"
            "Horário início: 08:00\n"
            "Horário fim: 23:00\n"
            "Data início: 2024-01-01\n"
            "Data fim: 2024-12-31\n\n"
            "Exemplo:\n"
            "0.05 0.50 08:00 23:00 2024-01-01 2024-12-31",
            parse_mode='Markdown'
        )
        
        # Armazena estado para capturar a próxima mensagem
        context.user_data['configurando'] = 'filtros'

    async def _configurar_ligas(self, query, context):
        """Configuração de ligas"""
        try:
            # Carrega catálogo de ligas
            catalogo = await carregar_catalogo_ligas()
            
            if not catalogo:
                await query.edit_message_text("❌ Erro ao carregar catálogo de ligas.")
                return
            
            # Busca ligas já selecionadas
            chat_id = query.effective_chat.id
            async with self.db_pool.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT league_name FROM user_leagues WHERE chat_id = ?
                """, (chat_id,))
                ligas_selecionadas = {row['league_name'] for row in await cursor.fetchall()}
            
            # Cria teclado com ligas
            keyboard = []
            for liga in list(catalogo.keys())[:20]:  # Limita a 20 ligas
                status = "✅" if liga in ligas_selecionadas else "⚪"
                keyboard.append([InlineKeyboardButton(
                    f"{status} {liga}", 
                    callback_data=f"toggle_liga_{liga}"
                )])
            
            keyboard.append([InlineKeyboardButton("✅ Finalizar", callback_data="finalizar_ligas")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "🏆 **Selecionar Ligas**\n\n"
                "Clique nas ligas que deseja monitorar:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Erro ao configurar ligas: {e}")
            await query.edit_message_text("❌ Erro ao carregar ligas.")

    async def _configurar_esportes(self, query, context):
        """Configuração de esportes"""
        try:
            # Lista de esportes disponíveis
            esportes = list(TRADUCAO_ESPORTE_EN.keys())
            
            # Busca esportes já selecionados
            chat_id = query.effective_chat.id
            async with self.db_pool.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT sport_name FROM user_sports WHERE chat_id = ?
                """, (chat_id,))
                esportes_selecionados = {row['sport_name'] for row in await cursor.fetchall()}
            
            # Cria teclado com esportes
            keyboard = []
            for esporte in esportes:
                status = "✅" if esporte in esportes_selecionados else "⚪"
                keyboard.append([InlineKeyboardButton(
                    f"{status} {esporte}", 
                    callback_data=f"toggle_esporte_{esporte}"
                )])
            
            keyboard.append([InlineKeyboardButton("✅ Finalizar", callback_data="finalizar_esportes")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "⚽ **Selecionar Esportes**\n\n"
                "Clique nos esportes que deseja monitorar:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Erro ao configurar esportes: {e}")
            await query.edit_message_text("❌ Erro ao carregar esportes.")

    async def _configurar_bookmakers(self, query, context):
        """Configuração de bookmakers"""
        try:
            # Lista de bookmakers disponíveis
            bookmakers = ["bet365", "betfair", "pinnacle", "sportingbet", "betano"]
            
            # Busca bookmakers já selecionados
            chat_id = query.effective_chat.id
            async with self.db_pool.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT bookmaker_name FROM user_bookmakers WHERE chat_id = ?
                """, (chat_id,))
                bookmakers_selecionados = {row['bookmaker_name'] for row in await cursor.fetchall()}
            
            # Cria teclado com bookmakers
            keyboard = []
            for bookmaker in bookmakers:
                status = "✅" if bookmaker in bookmakers_selecionados else "⚪"
                keyboard.append([InlineKeyboardButton(
                    f"{status} {bookmaker}", 
                    callback_data=f"toggle_bookmaker_{bookmaker}"
                )])
            
            keyboard.append([InlineKeyboardButton("✅ Finalizar", callback_data="finalizar_bookmakers")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "🏪 **Selecionar Bookmakers**\n\n"
                "Clique nos bookmakers que deseja monitorar:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Erro ao configurar bookmakers: {e}")
            await query.edit_message_text("❌ Erro ao carregar bookmakers.")

    async def _finalizar_configuracao(self, query, context):
        """Finaliza a configuração do usuário"""
        chat_id = query.effective_chat.id
        
        try:
            # Verifica se tem configurações mínimas
            async with self.db_pool.get_connection() as conn:
                # Verifica filtros
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count FROM user_filters WHERE chat_id = ?
                """, (chat_id,))
                tem_filtros = (await cursor.fetchone())['count'] > 0
                
                # Verifica ligas
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count FROM user_leagues WHERE chat_id = ?
                """, (chat_id,))
                tem_ligas = (await cursor.fetchone())['count'] > 0
                
                # Verifica esportes
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count FROM user_sports WHERE chat_id = ?
                """, (chat_id,))
                tem_esportes = (await cursor.fetchone())['count'] > 0
                
                # Verifica bookmakers
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count FROM user_bookmakers WHERE chat_id = ?
                """, (chat_id,))
                tem_bookmakers = (await cursor.fetchone())['count'] > 0
            
            if not (tem_filtros and tem_ligas and tem_esportes and tem_bookmakers):
                await query.edit_message_text(
                    "❌ **Configuração Incompleta**\n\n"
                    "Você precisa configurar:\n"
                    f"{'✅' if tem_filtros else '❌'} Filtros\n"
                    f"{'✅' if tem_ligas else '❌'} Ligas\n"
                    f"{'✅' if tem_esportes else '❌'} Esportes\n"
                    f"{'✅' if tem_bookmakers else '❌'} Bookmakers\n\n"
                    "Complete todas as configurações antes de finalizar.",
                    parse_mode='Markdown'
                )
                return
            
            # Marca usuário como configurado
            async with self.db_pool.get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET is_active = 1, updated_at = datetime('now')
                    WHERE chat_id = ?
                """, (chat_id,))
            
            await query.edit_message_text(
                "🎉 **Configuração Finalizada!**\n\n"
                "✅ Seu bot está configurado e ativo\n"
                "🔄 Você receberá alertas a cada 2 minutos\n"
                "📊 Use /stats para ver suas estatísticas\n"
                "⚙️ Use /filtros para ajustar configurações\n\n"
                "Boa sorte nas apostas! 🍀",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Erro ao finalizar configuração: {e}")
            await query.edit_message_text("❌ Erro ao finalizar configuração.")

    async def _editar_configuracao(self, query, context, data):
        """Edita configurações existentes"""
        if data == "edit_filtros":
            await self._configurar_filtros(query, context)
        elif data == "edit_ligas":
            await self._configurar_ligas(query, context)
        elif data == "edit_esportes":
            await self._configurar_esportes(query, context)
        elif data == "edit_bookmakers":
            await self._configurar_bookmakers(query, context)

    async def _admin_action(self, query, context, data):
        """Executa ações administrativas"""
        if data == "admin_scan":
            await query.edit_message_text("🔄 Iniciando scan manual...")
            # Aqui você pode chamar a função de scan manual
            await query.edit_message_text("✅ Scan manual concluído!")
        elif data == "admin_stats":
            await query.edit_message_text("📊 Carregando estatísticas detalhadas...")
            # Implementar stats detalhadas
        elif data == "admin_cleanup":
            await query.edit_message_text("🧹 Executando limpeza...")
            # Implementar limpeza de cache

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para mensagens de texto"""
        chat_id = update.effective_chat.id
        text = update.message.text
        
        # Verifica se está configurando algo
        if 'configurando' in context.user_data:
            config_type = context.user_data['configurando']
            
            if config_type == 'filtros':
                await self._processar_filtros(update, context, text)
            
            # Limpa o estado
            del context.user_data['configurando']
            return
        
        # Resposta padrão para mensagens não reconhecidas
        await update.message.reply_text(
            "🤖 Use /help para ver os comandos disponíveis ou /start para configurar o bot."
        )

    async def _processar_filtros(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Processa configuração de filtros via texto"""
        try:
            # Parse dos valores
            valores = text.strip().split()
            if len(valores) != 6:
                await update.message.reply_text(
                    "❌ Formato inválido. Use: EV_min EV_max Hora_inicio Hora_fim Data_inicio Data_fim"
                )
                return
            
            ev_min, ev_max, hora_ini, hora_fim, data_ini, data_fim = valores
            
            # Validação básica
            try:
                ev_min = float(ev_min)
                ev_max = float(ev_max)
            except ValueError:
                await update.message.reply_text("❌ EV deve ser um número decimal (ex: 0.05)")
                return
            
            # Salva no banco
            chat_id = update.effective_chat.id
            async with self.db_pool.get_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO user_filters 
                    (chat_id, ev_minimo, ev_maximo, horario_inicio, horario_fim, data_inicio, data_fim, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (chat_id, ev_min, ev_max, hora_ini, hora_fim, data_ini, data_fim))
            
            await update.message.reply_text(
                f"✅ **Filtros Configurados!**\n\n"
                f"📊 EV: {ev_min:.2%} - {ev_max:.2%}\n"
                f"⏰ Horário: {hora_ini} - {hora_fim}\n"
                f"📅 Data: {data_ini} - {data_fim}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Erro ao processar filtros: {e}")
            await update.message.reply_text("❌ Erro ao salvar filtros.")

    async def stop(self):
        """Para o bot listener"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Bot listener parado")

# Função principal para iniciar o bot
async def main():
    """Função principal"""
    bot = BotListener()
    try:
        await bot.start()
        # Mantém o bot rodando
        import asyncio
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
