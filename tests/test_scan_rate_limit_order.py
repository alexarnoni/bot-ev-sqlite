"""
Teste exploratório da Bug Condition: Scan com snapshot disponível é bloqueado por rate limits.

**Validates: Requirements 1.1, 1.2, 1.3**

Property 1: Bug Condition - Quando existe um snapshot válido no cache (idade ≤ 120s,
bookmakers compatíveis) e algum bloqueio está ativo (API offline, rate limit global ou
local atingido), a função scan_apostas_usuario NÃO DEVE retornar mensagens de erro de
rate limit ou API offline — deve usar o snapshot diretamente.

CRITICAL: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio

from src.utils.messages import api_offline, global_rate_limit, scan_rate_limit, user_not_found, no_events


# Dados de teste reutilizáveis
VALID_USER = {
    'chat_id': '12345',
    'nome': 'Test User',
    'filtros': {
        'ev_faixa_min': 0.05,
        'ev_faixa_max': 1.0,
        'horario_inicio': None,
        'horario_fim': None,
        'data_inicio': None,
        'data_fim': None,
        'filtro_dias': None,
    },
    'ligas': [],
    'esportes': [],
    'bookmakers': ['Bet365'],
}

VALID_SNAPSHOT = {
    'bookmakers': ['Bet365'],
    'timestamp': '2025-01-15T10:00:00+00:00',
    'eventos': [
        {
            'home': 'Team A',
            'away': 'Team B',
            'league': 'Premier League',
            'sport': 'soccer',
            'market_type': 'h2h',
            'bet_side': 'home',
            'bookmaker': 'Bet365',
            'bet365_odds': 2.0,
            'ev': 0.06,
            'commence_time': '2099-12-31T20:00:00Z',
            'event_url': 'http://example.com',
        }
    ],
}


class TestBugConditionSnapshotBlockedByRateLimits:
    """
    Property 1: Bug Condition - Scan com snapshot disponível é bloqueado por rate limits.

    Estes testes verificam que quando existe um snapshot válido no cache,
    a função scan_apostas_usuario NÃO retorna mensagens de erro de rate limit
    ou API offline — deve usar o snapshot diretamente.

    EXPECTED: Estes testes FALHAM no código não corrigido (confirmando o bug).
    """

    @pytest.mark.asyncio
    async def test_snapshot_disponivel_com_api_offline_nao_retorna_erro(self):
        """
        Req 1.3: Quando snapshot válido existe e API está offline,
        scan_apostas_usuario NÃO deve retornar api_offline().
        Deve usar o snapshot diretamente.
        """
        with patch('src.scanner.scanner._buscar_usuario_especifico', new_callable=AsyncMock) as mock_user, \
             patch('src.scanner.scanner.get_odds_api_status', new_callable=AsyncMock) as mock_api_status, \
             patch('src.scanner.scanner.get_global_rate_limiter') as mock_global_rl, \
             patch('src.scanner.scanner.api_rate_limiter') as mock_local_rl, \
             patch('src.scanner.scanner.get_snapshot_cache') as mock_cache, \
             patch('src.scanner.scanner._processar_apostas_usuario', new_callable=AsyncMock) as mock_processar:

            # Setup: usuário válido
            mock_user.return_value = VALID_USER

            # Setup: API offline
            mock_api_status.return_value = False

            # Setup: rate limits OK (não são o problema neste caso)
            mock_global_rl_instance = MagicMock()
            mock_global_rl_instance.can_make_request.return_value = True
            mock_global_rl.return_value = mock_global_rl_instance

            mock_local_rl.can_make_request = AsyncMock(return_value=True)

            # Setup: snapshot válido disponível
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_snapshot.return_value = VALID_SNAPSHOT
            mock_cache.return_value = mock_cache_instance

            # Setup: processamento retorna lista vazia (sem alertas)
            mock_processar.return_value = []

            from src.scanner.scanner import scan_apostas_usuario
            result = await scan_apostas_usuario('12345')

            # ASSERT: NÃO deve retornar mensagem de API offline
            assert result != api_offline(), (
                f"BUG CONFIRMADO: scan_apostas_usuario retornou '{result}' "
                f"(api_offline) mesmo com snapshot válido disponível. "
                f"O snapshot deveria ter sido usado diretamente."
            )

    @pytest.mark.asyncio
    async def test_snapshot_disponivel_com_rate_limit_global_nao_retorna_erro(self):
        """
        Req 1.1: Quando snapshot válido existe e rate limit global está atingido,
        scan_apostas_usuario NÃO deve retornar global_rate_limit().
        Deve usar o snapshot diretamente.
        """
        with patch('src.scanner.scanner._buscar_usuario_especifico', new_callable=AsyncMock) as mock_user, \
             patch('src.scanner.scanner.get_odds_api_status', new_callable=AsyncMock) as mock_api_status, \
             patch('src.scanner.scanner.get_global_rate_limiter') as mock_global_rl, \
             patch('src.scanner.scanner.api_rate_limiter') as mock_local_rl, \
             patch('src.scanner.scanner.get_snapshot_cache') as mock_cache, \
             patch('src.scanner.scanner._processar_apostas_usuario', new_callable=AsyncMock) as mock_processar:

            # Setup: usuário válido
            mock_user.return_value = VALID_USER

            # Setup: API online (não é o problema neste caso)
            mock_api_status.return_value = True

            # Setup: rate limit GLOBAL atingido
            mock_global_rl_instance = MagicMock()
            mock_global_rl_instance.can_make_request.return_value = False
            mock_global_rl.return_value = mock_global_rl_instance

            # Setup: rate limit local OK
            mock_local_rl.can_make_request = AsyncMock(return_value=True)

            # Setup: snapshot válido disponível
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_snapshot.return_value = VALID_SNAPSHOT
            mock_cache.return_value = mock_cache_instance

            # Setup: processamento retorna lista vazia
            mock_processar.return_value = []

            from src.scanner.scanner import scan_apostas_usuario
            result = await scan_apostas_usuario('12345')

            # ASSERT: NÃO deve retornar mensagem de rate limit global
            assert result != global_rate_limit(), (
                f"BUG CONFIRMADO: scan_apostas_usuario retornou '{result}' "
                f"(global_rate_limit) mesmo com snapshot válido disponível. "
                f"O snapshot deveria ter sido usado diretamente."
            )

    @pytest.mark.asyncio
    async def test_snapshot_disponivel_com_rate_limit_local_nao_retorna_erro(self):
        """
        Req 1.2: Quando snapshot válido existe e rate limit local está atingido,
        scan_apostas_usuario NÃO deve retornar scan_rate_limit().
        Deve usar o snapshot diretamente.
        """
        with patch('src.scanner.scanner._buscar_usuario_especifico', new_callable=AsyncMock) as mock_user, \
             patch('src.scanner.scanner.get_odds_api_status', new_callable=AsyncMock) as mock_api_status, \
             patch('src.scanner.scanner.get_global_rate_limiter') as mock_global_rl, \
             patch('src.scanner.scanner.api_rate_limiter') as mock_local_rl, \
             patch('src.scanner.scanner.get_snapshot_cache') as mock_cache, \
             patch('src.scanner.scanner._processar_apostas_usuario', new_callable=AsyncMock) as mock_processar:

            # Setup: usuário válido
            mock_user.return_value = VALID_USER

            # Setup: API online
            mock_api_status.return_value = True

            # Setup: rate limit global OK
            mock_global_rl_instance = MagicMock()
            mock_global_rl_instance.can_make_request.return_value = True
            mock_global_rl.return_value = mock_global_rl_instance

            # Setup: rate limit LOCAL atingido
            mock_local_rl.can_make_request = AsyncMock(return_value=False)

            # Setup: snapshot válido disponível
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_snapshot.return_value = VALID_SNAPSHOT
            mock_cache.return_value = mock_cache_instance

            # Setup: processamento retorna lista vazia
            mock_processar.return_value = []

            from src.scanner.scanner import scan_apostas_usuario
            result = await scan_apostas_usuario('12345')

            # ASSERT: NÃO deve retornar mensagem de rate limit local
            assert result != scan_rate_limit(), (
                f"BUG CONFIRMADO: scan_apostas_usuario retornou '{result}' "
                f"(scan_rate_limit) mesmo com snapshot válido disponível. "
                f"O snapshot deveria ter sido usado diretamente."
            )

    @pytest.mark.asyncio
    async def test_snapshot_disponivel_com_todos_bloqueios_nao_retorna_erro(self):
        """
        Req 1.1 + 1.2 + 1.3: Quando snapshot válido existe e TODOS os bloqueios
        estão ativos (API offline + rate limit global + rate limit local),
        scan_apostas_usuario NÃO deve retornar nenhuma mensagem de erro.
        Deve usar o snapshot diretamente.
        """
        with patch('src.scanner.scanner._buscar_usuario_especifico', new_callable=AsyncMock) as mock_user, \
             patch('src.scanner.scanner.get_odds_api_status', new_callable=AsyncMock) as mock_api_status, \
             patch('src.scanner.scanner.get_global_rate_limiter') as mock_global_rl, \
             patch('src.scanner.scanner.api_rate_limiter') as mock_local_rl, \
             patch('src.scanner.scanner.get_snapshot_cache') as mock_cache, \
             patch('src.scanner.scanner._processar_apostas_usuario', new_callable=AsyncMock) as mock_processar:

            # Setup: usuário válido
            mock_user.return_value = VALID_USER

            # Setup: API offline
            mock_api_status.return_value = False

            # Setup: rate limit GLOBAL atingido
            mock_global_rl_instance = MagicMock()
            mock_global_rl_instance.can_make_request.return_value = False
            mock_global_rl.return_value = mock_global_rl_instance

            # Setup: rate limit LOCAL atingido
            mock_local_rl.can_make_request = AsyncMock(return_value=False)

            # Setup: snapshot válido disponível
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_snapshot.return_value = VALID_SNAPSHOT
            mock_cache.return_value = mock_cache_instance

            # Setup: processamento retorna lista vazia
            mock_processar.return_value = []

            from src.scanner.scanner import scan_apostas_usuario
            result = await scan_apostas_usuario('12345')

            # ASSERT: NÃO deve retornar NENHUMA mensagem de erro
            error_messages = [api_offline(), global_rate_limit(), scan_rate_limit()]
            assert result not in error_messages, (
                f"BUG CONFIRMADO: scan_apostas_usuario retornou '{result}' "
                f"mesmo com snapshot válido disponível e todos os bloqueios ativos. "
                f"O snapshot deveria ter sido usado diretamente, ignorando rate limits."
            )



class TestPreservationSemSnapshot:
    """
    Property 2: Preservation - Sem snapshot, rate limits continuam bloqueando.

    **Validates: Requirements 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4**

    Estes testes documentam o comportamento baseline quando NÃO existe snapshot
    válido no cache. Este comportamento DEVE ser preservado após a correção.

    EXPECTED: Estes testes PASSAM no código não corrigido (confirma baseline).
    """

    @pytest.mark.asyncio
    async def test_sem_snapshot_api_offline_retorna_api_offline(self):
        """
        Req 2.6: Sem snapshot + API offline → retorna api_offline().
        Comportamento que deve ser preservado após a correção.
        """
        with patch('src.scanner.scanner._buscar_usuario_especifico', new_callable=AsyncMock) as mock_user, \
             patch('src.scanner.scanner.get_odds_api_status', new_callable=AsyncMock) as mock_api_status, \
             patch('src.scanner.scanner.get_global_rate_limiter') as mock_global_rl, \
             patch('src.scanner.scanner.api_rate_limiter') as mock_local_rl, \
             patch('src.scanner.scanner.get_snapshot_cache') as mock_cache:

            # Setup: usuário válido
            mock_user.return_value = VALID_USER

            # Setup: API offline
            mock_api_status.return_value = False

            # Setup: rate limits OK (irrelevante - API offline é verificada primeiro)
            mock_global_rl_instance = MagicMock()
            mock_global_rl_instance.can_make_request.return_value = True
            mock_global_rl.return_value = mock_global_rl_instance
            mock_local_rl.can_make_request = AsyncMock(return_value=True)

            # Setup: SEM snapshot disponível
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_snapshot.return_value = None
            mock_cache.return_value = mock_cache_instance

            from src.scanner.scanner import scan_apostas_usuario
            result = await scan_apostas_usuario('12345')

            # ASSERT: Deve retornar api_offline() quando não há snapshot
            assert result == api_offline(), (
                f"PRESERVATION FALHOU: Esperava '{api_offline()}' mas obteve '{result}'. "
                f"Sem snapshot disponível e API offline, deve retornar api_offline()."
            )

    @pytest.mark.asyncio
    async def test_sem_snapshot_rate_limit_global_retorna_global_rate_limit(self):
        """
        Req 2.4: Sem snapshot + rate limit global atingido → retorna global_rate_limit().
        Comportamento que deve ser preservado após a correção.
        """
        with patch('src.scanner.scanner._buscar_usuario_especifico', new_callable=AsyncMock) as mock_user, \
             patch('src.scanner.scanner.get_odds_api_status', new_callable=AsyncMock) as mock_api_status, \
             patch('src.scanner.scanner.get_global_rate_limiter') as mock_global_rl, \
             patch('src.scanner.scanner.api_rate_limiter') as mock_local_rl, \
             patch('src.scanner.scanner.get_snapshot_cache') as mock_cache:

            # Setup: usuário válido
            mock_user.return_value = VALID_USER

            # Setup: API online
            mock_api_status.return_value = True

            # Setup: rate limit GLOBAL atingido
            mock_global_rl_instance = MagicMock()
            mock_global_rl_instance.can_make_request.return_value = False
            mock_global_rl.return_value = mock_global_rl_instance

            # Setup: rate limit local OK
            mock_local_rl.can_make_request = AsyncMock(return_value=True)

            # Setup: SEM snapshot disponível
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_snapshot.return_value = None
            mock_cache.return_value = mock_cache_instance

            from src.scanner.scanner import scan_apostas_usuario
            result = await scan_apostas_usuario('12345')

            # ASSERT: Deve retornar global_rate_limit() quando não há snapshot
            assert result == global_rate_limit(), (
                f"PRESERVATION FALHOU: Esperava '{global_rate_limit()}' mas obteve '{result}'. "
                f"Sem snapshot disponível e rate limit global atingido, deve retornar global_rate_limit()."
            )

    @pytest.mark.asyncio
    async def test_sem_snapshot_rate_limit_local_retorna_scan_rate_limit(self):
        """
        Req 2.5: Sem snapshot + rate limit local atingido → retorna scan_rate_limit().
        Comportamento que deve ser preservado após a correção.
        """
        with patch('src.scanner.scanner._buscar_usuario_especifico', new_callable=AsyncMock) as mock_user, \
             patch('src.scanner.scanner.get_odds_api_status', new_callable=AsyncMock) as mock_api_status, \
             patch('src.scanner.scanner.get_global_rate_limiter') as mock_global_rl, \
             patch('src.scanner.scanner.api_rate_limiter') as mock_local_rl, \
             patch('src.scanner.scanner.get_snapshot_cache') as mock_cache:

            # Setup: usuário válido
            mock_user.return_value = VALID_USER

            # Setup: API online
            mock_api_status.return_value = True

            # Setup: rate limit global OK
            mock_global_rl_instance = MagicMock()
            mock_global_rl_instance.can_make_request.return_value = True
            mock_global_rl.return_value = mock_global_rl_instance

            # Setup: rate limit LOCAL atingido
            mock_local_rl.can_make_request = AsyncMock(return_value=False)

            # Setup: SEM snapshot disponível
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_snapshot.return_value = None
            mock_cache.return_value = mock_cache_instance

            from src.scanner.scanner import scan_apostas_usuario
            result = await scan_apostas_usuario('12345')

            # ASSERT: Deve retornar scan_rate_limit() quando não há snapshot
            assert result == scan_rate_limit(), (
                f"PRESERVATION FALHOU: Esperava '{scan_rate_limit()}' mas obteve '{result}'. "
                f"Sem snapshot disponível e rate limit local atingido, deve retornar scan_rate_limit()."
            )

    @pytest.mark.asyncio
    async def test_sem_snapshot_tudo_ok_chama_buscar_apostas_api(self):
        """
        Req 3.1: Sem snapshot + tudo OK → chama _buscar_apostas_api normalmente.
        Comportamento que deve ser preservado após a correção.
        """
        with patch('src.scanner.scanner._buscar_usuario_especifico', new_callable=AsyncMock) as mock_user, \
             patch('src.scanner.scanner.get_odds_api_status', new_callable=AsyncMock) as mock_api_status, \
             patch('src.scanner.scanner.get_global_rate_limiter') as mock_global_rl, \
             patch('src.scanner.scanner.api_rate_limiter') as mock_local_rl, \
             patch('src.scanner.scanner.get_snapshot_cache') as mock_cache, \
             patch('src.scanner.scanner._buscar_apostas_api', new_callable=AsyncMock) as mock_buscar_api, \
             patch('src.scanner.scanner._processar_apostas_usuario', new_callable=AsyncMock) as mock_processar:

            # Setup: usuário válido
            mock_user.return_value = VALID_USER

            # Setup: API online
            mock_api_status.return_value = True

            # Setup: rate limits OK
            mock_global_rl_instance = MagicMock()
            mock_global_rl_instance.can_make_request.return_value = True
            mock_global_rl.return_value = mock_global_rl_instance
            mock_local_rl.can_make_request = AsyncMock(return_value=True)

            # Setup: SEM snapshot disponível
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_snapshot.return_value = None
            mock_cache.return_value = mock_cache_instance

            # Setup: API retorna eventos
            mock_buscar_api.return_value = VALID_SNAPSHOT['eventos']

            # Setup: processamento retorna alertas
            mock_processar.return_value = []

            from src.scanner.scanner import scan_apostas_usuario
            result = await scan_apostas_usuario('12345')

            # ASSERT: _buscar_apostas_api deve ter sido chamada (sem snapshot, precisa da API)
            mock_buscar_api.assert_called_once_with([VALID_USER])

            # ASSERT: Resultado não é mensagem de erro de rate limit
            error_messages = [api_offline(), global_rate_limit(), scan_rate_limit()]
            assert result not in error_messages, (
                f"PRESERVATION FALHOU: Obteve '{result}' mas não deveria ser erro de rate limit "
                f"quando tudo está OK e não há snapshot."
            )

    @pytest.mark.asyncio
    async def test_usuario_nao_encontrado_retorna_user_not_found(self):
        """
        Req 3.2: Usuário não encontrado → retorna user_not_found() independente do cache.
        Comportamento que deve ser preservado após a correção.
        """
        with patch('src.scanner.scanner._buscar_usuario_especifico', new_callable=AsyncMock) as mock_user, \
             patch('src.scanner.scanner.get_odds_api_status', new_callable=AsyncMock) as mock_api_status, \
             patch('src.scanner.scanner.get_global_rate_limiter') as mock_global_rl, \
             patch('src.scanner.scanner.api_rate_limiter') as mock_local_rl, \
             patch('src.scanner.scanner.get_snapshot_cache') as mock_cache:

            # Setup: usuário NÃO encontrado
            mock_user.return_value = None

            # Setup: API online (irrelevante para este caso)
            mock_api_status.return_value = True

            # Setup: rate limits OK (irrelevante para este caso)
            mock_global_rl_instance = MagicMock()
            mock_global_rl_instance.can_make_request.return_value = True
            mock_global_rl.return_value = mock_global_rl_instance
            mock_local_rl.can_make_request = AsyncMock(return_value=True)

            # Setup: snapshot disponível (irrelevante - usuário não existe)
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_snapshot.return_value = VALID_SNAPSHOT
            mock_cache.return_value = mock_cache_instance

            from src.scanner.scanner import scan_apostas_usuario
            result = await scan_apostas_usuario('99999')

            # ASSERT: Deve retornar user_not_found() independente do estado do cache
            assert result == user_not_found(), (
                f"PRESERVATION FALHOU: Esperava '{user_not_found()}' mas obteve '{result}'. "
                f"Usuário não encontrado deve sempre retornar user_not_found()."
            )

    @pytest.mark.asyncio
    async def test_sem_snapshot_sem_apostas_retorna_no_events(self):
        """
        Req 3.3: Sem snapshot + tudo OK + nenhuma aposta encontrada → retorna no_events().
        Comportamento que deve ser preservado após a correção.
        """
        with patch('src.scanner.scanner._buscar_usuario_especifico', new_callable=AsyncMock) as mock_user, \
             patch('src.scanner.scanner.get_odds_api_status', new_callable=AsyncMock) as mock_api_status, \
             patch('src.scanner.scanner.get_global_rate_limiter') as mock_global_rl, \
             patch('src.scanner.scanner.api_rate_limiter') as mock_local_rl, \
             patch('src.scanner.scanner.get_snapshot_cache') as mock_cache, \
             patch('src.scanner.scanner._buscar_apostas_api', new_callable=AsyncMock) as mock_buscar_api:

            # Setup: usuário válido
            mock_user.return_value = VALID_USER

            # Setup: API online
            mock_api_status.return_value = True

            # Setup: rate limits OK
            mock_global_rl_instance = MagicMock()
            mock_global_rl_instance.can_make_request.return_value = True
            mock_global_rl.return_value = mock_global_rl_instance
            mock_local_rl.can_make_request = AsyncMock(return_value=True)

            # Setup: SEM snapshot disponível
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_snapshot.return_value = None
            mock_cache.return_value = mock_cache_instance

            # Setup: API retorna lista vazia (nenhuma aposta)
            mock_buscar_api.return_value = []

            from src.scanner.scanner import scan_apostas_usuario
            result = await scan_apostas_usuario('12345')

            # ASSERT: Deve retornar no_events() quando não há apostas
            assert result == no_events(), (
                f"PRESERVATION FALHOU: Esperava '{no_events()}' mas obteve '{result}'. "
                f"Sem snapshot e sem apostas na API, deve retornar no_events()."
            )
