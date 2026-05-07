"""
Bot package - Telegram bot modules
"""
from src.bot.bot_core import definir_stake, calcular_ev, calcular_odd_minima
from src.bot.bot_ev import enviar_alerta, enviar_alerta_instantaneo, enviar_alertas_batch, AlertSender, get_alert_sender
