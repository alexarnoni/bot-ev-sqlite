"""
Testes unitários para o job consolidado lembrete_pos_jogo_job em main_scheduler.py
Validates: Requirements 5.3, 5.6
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def scheduler():
    """Cria instância mínima de BotScheduler com mocks."""
    with patch("src.scanner.main_scheduler.asyncio.get_event_loop"), \
         patch("src.scanner.main_scheduler.get_user_manager"), \
         patch("src.scanner.main_scheduler.get_cache"), \
         patch("src.scanner.main_scheduler.get_history"), \
         patch("src.scanner.main_scheduler.get_status"), \
         patch("src.scanner.main_scheduler.get_db"), \
         patch("src.scanner.main_scheduler.get_rate_limiter"), \
         patch("src.scanner.main_scheduler.get_snapshot_cache"):
        from src.scanner.main_scheduler import BotScheduler
        sched = BotScheduler.__new__(BotScheduler)
        sched.bets_tracker = MagicMock()
        return sched


class TestLembretePosJogoJob:
    """Testes para lembrete_pos_jogo_job: agrupamento e envio consolidado."""

    @pytest.mark.asyncio
    async def test_duas_apostas_chat_a_uma_chat_b_envia_duas_mensagens(self, scheduler):
        """Req 5.3: 2 apostas chat_A + 1 chat_B → 2 chamadas send_message."""
        scheduler.bets_tracker.get_pendentes_para_lembrete.return_value = [
            {"chat_id": "111", "id": 1},
            {"chat_id": "111", "id": 2},
            {"chat_id": "222", "id": 3},
        ]

        mock_bot_instance = AsyncMock()
        mock_bot_class = MagicMock(return_value=mock_bot_instance)

        with patch("src.scanner.main_scheduler.Bot", mock_bot_class, create=True), \
             patch("src.scanner.main_scheduler.get_telegram_token", return_value="fake-token", create=True), \
             patch.dict("sys.modules", {}):
            # Patch imports inside the method body
            with patch("telegram.Bot", mock_bot_class), \
                 patch("src.core.config.get_telegram_token", return_value="fake-token"):
                await scheduler.lembrete_pos_jogo_job()

        assert mock_bot_instance.send_message.await_count == 2
        # Verifica conteúdo das chamadas
        calls = mock_bot_instance.send_message.await_args_list
        chat_ids_chamados = {call.kwargs["chat_id"] for call in calls}
        assert chat_ids_chamados == {111, 222}

        # Verifica contagem correta na mensagem do chat_A (2 apostas)
        for call in calls:
            if call.kwargs["chat_id"] == 111:
                assert "2 aposta(s)" in call.kwargs["text"]
            elif call.kwargs["chat_id"] == 222:
                assert "1 aposta(s)" in call.kwargs["text"]

    @pytest.mark.asyncio
    async def test_lista_vazia_nenhuma_chamada_send_message(self, scheduler):
        """Req 5.3: lista vazia → nenhuma chamada send_message."""
        scheduler.bets_tracker.get_pendentes_para_lembrete.return_value = []

        mock_bot_instance = AsyncMock()
        mock_bot_class = MagicMock(return_value=mock_bot_instance)

        with patch("telegram.Bot", mock_bot_class), \
             patch("src.core.config.get_telegram_token", return_value="fake-token"):
            await scheduler.lembrete_pos_jogo_job()

        mock_bot_instance.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falha_send_message_chat_a_continua_para_chat_b(self, scheduler):
        """Req 5.6: falha em send_message para chat_A → continua para chat_B."""
        scheduler.bets_tracker.get_pendentes_para_lembrete.return_value = [
            {"chat_id": "111", "id": 1},
            {"chat_id": "222", "id": 2},
        ]

        mock_bot_instance = AsyncMock()
        # Primeira chamada falha, segunda sucede
        mock_bot_instance.send_message.side_effect = [
            Exception("Telegram API error"),
            None,
        ]
        mock_bot_class = MagicMock(return_value=mock_bot_instance)

        with patch("telegram.Bot", mock_bot_class), \
             patch("src.core.config.get_telegram_token", return_value="fake-token"):
            await scheduler.lembrete_pos_jogo_job()

        # Deve ter tentado enviar para ambos os chats
        assert mock_bot_instance.send_message.await_count == 2
        # A segunda chamada (chat_B) deve ter sido feita apesar da falha na primeira
        second_call = mock_bot_instance.send_message.await_args_list[1]
        assert second_call.kwargs["chat_id"] == 222
