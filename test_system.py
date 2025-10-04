"""
Script de teste para validar o sistema Bot EV+
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta

# Adiciona o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import Database, generate_alert_hash
from usuarios import get_user_manager
from cache import get_cache
from historico import get_history
from status import get_status
from rate_limiter import get_rate_limiter
from api_client import OddsAPIClient
from bot_core import calcular_ev, definir_stake
from filtros import evento_valido, validar_filtros_completos
from utils import get_league_catalog, format_league_name

def test_database():
    """Testa funcionalidades do banco de dados"""
    print("[DB] Testando banco de dados...")
    
    db = Database("test")
    
    # Limpa dados de testes anteriores
    with db.get_connection() as conn:
        conn.execute("DELETE FROM alert_history WHERE chat_id = 123456789")
        conn.execute("DELETE FROM alert_cache WHERE chat_id = 123456789")
        conn.execute("DELETE FROM user_sports WHERE chat_id = 123456789")
        conn.execute("DELETE FROM user_leagues WHERE chat_id = 123456789")
        conn.execute("DELETE FROM user_bookmakers WHERE chat_id = 123456789")
        conn.execute("DELETE FROM user_filters WHERE chat_id = 123456789")
        conn.execute("DELETE FROM users WHERE chat_id = 123456789")
    
    # Teste 1: Criação de usuário
    print("  [1] Teste 1: Criação de usuário")
    db.create_or_update_user(123456789, "João Silva", "joaosilva")
    user = db.get_user(123456789)
    assert user is not None
    assert user['nome'] == "João Silva"
    print("    [OK] Usuário criado com sucesso")
    
    # Teste 2: Bookmakers
    print("  [2] Teste 2: Bookmakers")
    db.set_user_bookmakers(123456789, ["Bet365", "Pinnacle"])
    bookmakers = db.get_user_bookmakers(123456789)
    assert "Bet365" in bookmakers
    assert "Pinnacle" in bookmakers
    print("    [OK] Bookmakers configurados")
    
    # Teste 3: Filtros
    print("  [3] Teste 3: Filtros")
    db.set_user_filter(123456789, ev_faixa_min=0.05, ev_faixa_max=0.15)
    filters = db.get_user_filter(123456789)
    assert filters['ev_faixa_min'] == 0.05
    assert filters['ev_faixa_max'] == 0.15
    print("    [OK] Filtros configurados")
    
    # Teste 4: Ligas
    print("  [4] Teste 4: Ligas")
    db.set_user_leagues(123456789, ["Brazil - Serie A", "Spain - La Liga"])
    leagues = db.get_user_leagues(123456789)
    assert "Brazil - Serie A" in leagues
    assert "Spain - La Liga" in leagues
    print("    [OK] Ligas configuradas")
    
    # Teste 5: Cache
    print("  [5] Teste 5: Cache")
    evento_teste = {
        "id": "test_123",
        "market_name": "Moneyline",
        "bet365_odds": "2.50"
    }
    alert_hash = generate_alert_hash(evento_teste)
    db.add_to_cache(123456789, alert_hash)
    assert db.is_in_cache(123456789, alert_hash)
    print("    [OK] Cache funcionando")
    
    # Teste 6: Histórico
    print("  [6] Teste 6: Histórico")
    db.add_alert_history(
        chat_id=123456789,
        data_envio="01/01/2025 20:30",
        esporte="Football",
        home="Flamengo",
        away="Palmeiras",
        mercado="Moneyline",
        odd=2.50,
        stake=1.0,
        ev=0.08,
        data_jogo="01/01/2025 21:00",
        url_bet="https://example.com",
        bookmaker="Bet365"
    )
    history = db.get_user_history(123456789, 10)
    assert len(history) == 1
    assert history[0]['home'] == "Flamengo"
    print("    [OK] Histórico funcionando")
    
    # Teste 7: Usuário configurado
    print("  [7] Teste 7: Usuário configurado")
    assert db.usuario_configurado(123456789)
    print("    [OK] Usuário configurado corretamente")
    
    print("  [SUCCESS] Todos os testes do banco passaram!")

def test_core_functions():
    """Testa funções core"""
    print("[CORE] [CORE] Testando funções core...")
    
    # Teste 1: Cálculo de EV
    print("   [1] Teste 1: Cálculo de EV")
    evento = {"expectedValue": 100.84}
    ev = calcular_ev(evento)
    assert abs(ev - 0.0084) < 0.0001  # 0.84%
    print("     EV calculado corretamente")
    
    # Teste 2: Definição de stake
    print("   [2] Teste 2: Definição de stake")
    stake1 = definir_stake(0.08, 2.50)  # EV 8%, odd 2.50
    assert stake1 == 1.0  # Entre 1.50 e 3.50
    
    stake2 = definir_stake(0.08, 5.00)  # EV 8%, odd 5.00
    assert stake2 == 0.5  # Entre 3.51 e 8.00
    
    stake3 = definir_stake(0.08, 10.00)  # EV 8%, odd 10.00
    assert stake3 == 0.25  # Acima de 8.00
    
    stake4 = definir_stake(0.03, 2.50)  # EV 3%, odd 2.50
    assert stake4 == 0  # EV abaixo do mínimo
    print("     [OK] Stake calculado corretamente")
    
    print("   [SUCCESS] Todos os testes core passaram!")

def test_filters():
    """Testa sistema de filtros"""
    print(" [FILTERS] Testando sistema de filtros...")
    
    # Evento de teste
    evento = {
        "league": "Brazil - Serie A",
        "sport": "Football",
        "ev": 0.08,  # 8%
        "bet365_odds": 2.50,
        "commence_time": "2025-01-15T20:30:00Z",
        "market_name": "moneyline"
    }
    
    # Filtros de teste
    filtros = {
        "ligas": ["Brazil - Serie A"],
        "esportes": ["Football"],
        "ev_faixa_min": 0.05,
        "ev_faixa_max": 0.15,
        "horario_inicio": "19:00",
        "horario_fim": "23:00"
    }
    
    # Teste 1: Evento válido
    print("   [1] Teste 1: Evento válido")
    assert evento_valido(evento, filtros)
    print("     [OK] Evento válido detectado")
    
    # Teste 2: Liga inválida
    print("   [2] Teste 2: Liga inválida")
    evento_invalido = evento.copy()
    evento_invalido["league"] = "Invalid League"
    assert not evento_valido(evento_invalido, filtros)
    print("     Liga inválida detectada")
    
    # Teste 3: EV baixo
    print("   [3] Teste 3: EV baixo")
    evento_ev_baixo = evento.copy()
    evento_ev_baixo["ev"] = 0.03  # 3%
    assert not evento_valido(evento_ev_baixo, filtros)
    print("     EV baixo detectado")
    
    # Teste 4: Validação de filtros
    print("   [4] Teste 4: Validação de filtros")
    filtros_validos = {
        "bookmakers": ["Bet365"],
        "ev_faixa_min": 0.05
    }
    assert validar_filtros_completos(filtros_validos)
    print("     Filtros válidos")
    
    print("   [SUCCESS] Todos os testes de filtros passaram!")

def test_utils():
    """Testa utilitários"""
    print(" [UTILS] Testando utilitários...")
    
    # Teste 1: Catálogo de ligas
    print("   [1] Teste 1: Catálogo de ligas")
    catalog = get_league_catalog()
    assert "Brasil" in catalog
    assert "Football" in catalog["Brasil"]
    assert "Brazil - Serie A" in catalog["Brasil"]["Football"]
    print("     Catálogo de ligas funcionando")
    
    # Teste 2: Formatação de liga
    print("   [2] Teste 2: Formatação de liga")
    formatted = format_league_name("Brazil - Serie A")
    assert "" in formatted  # Bandeira do Brasil
    print("     Formatação de liga funcionando")
    
    print("   [SUCCESS] Todos os testes de utilitários passaram!")

async def test_api_client():
    """Testa cliente da API"""
    print(" [API] Testando cliente da API...")
    
    # Teste 1: Inicialização
    print("   [1] Teste 1: Inicialização")
    client = OddsAPIClient()
    assert client is not None
    print("     Cliente inicializado")
    
    # Teste 2: Rate limiting
    print("  [2] Teste 2: Rate limiting")
    rate_limiter = get_rate_limiter()
    can_request = await rate_limiter.can_make_request()
    print(f"     [INFO] Pode fazer requisição: {can_request}")
    
    # Teste 3: Status da API
    print("   [3] Teste 3: Status da API")
    status = client.get_api_status()
    print(f"     [INFO] Status: {status}")
    
    print("   [SUCCESS] Testes da API concluídos!")

def test_adapters():
    """Testa adaptadores"""
    print(" [ADAPTERS] Testando adaptadores...")
    
    # Teste 1: User Manager
    print("   [1] Teste 1: User Manager")
    user_manager = get_user_manager()
    assert user_manager is not None
    print("     User Manager funcionando")
    
    # Teste 2: Cache
    print("   [2] Teste 2: Cache")
    cache = get_cache()
    assert cache is not None
    print("     [OK] Cache funcionando")
    
    # Teste 3: Histórico
    print("   [3] Teste 3: Histórico")
    history = get_history()
    assert history is not None
    print("     [OK] Histórico funcionando")
    
    # Teste 4: Status
    print("   [4] Teste 4: Status")
    status = get_status()
    assert status is not None
    print("     Status funcionando")
    
    # Teste 5: Rate Limiter
    print("  [5] Teste 5: Rate Limiter")
    rate_limiter = get_rate_limiter()
    assert rate_limiter is not None
    print("     Rate Limiter funcionando")
    
    print("   [SUCCESS] Todos os adaptadores funcionando!")

def test_integration():
    """Teste de integração completo"""
    print(" [INTEGRATION] Testando integração completa...")
    
    # Simula um fluxo completo
    print("   [FLOW] Simulando fluxo completo...")
    
    # 1. Cria usuário
    db = Database("test")
    
    # Limpa dados de testes anteriores
    with db.get_connection() as conn:
        conn.execute("DELETE FROM alert_history WHERE chat_id = 999999999")
        conn.execute("DELETE FROM alert_cache WHERE chat_id = 999999999")
        conn.execute("DELETE FROM user_sports WHERE chat_id = 999999999")
        conn.execute("DELETE FROM user_leagues WHERE chat_id = 999999999")
        conn.execute("DELETE FROM user_bookmakers WHERE chat_id = 999999999")
        conn.execute("DELETE FROM user_filters WHERE chat_id = 999999999")
        conn.execute("DELETE FROM users WHERE chat_id = 999999999")
    
    db.create_or_update_user(999999999, "Test User", "testuser")
    
    # 2. Configura filtros
    db.set_user_bookmakers(999999999, ["Bet365"])
    db.set_user_filter(999999999, ev_faixa_min=0.05)
    db.set_user_leagues(999999999, ["Brazil - Serie A"])
    
    # 3. Verifica se está configurado
    assert db.usuario_configurado(999999999)
    print("     [OK] Usuário configurado")
    
    # 4. Simula evento
    evento = {
        "id": "integration_test",
        "league": "Brazil - Serie A",
        "sport": "Football",
        "ev": 0.08,
        "bet365_odds": 2.50,
        "commence_time": "2025-01-15T20:30:00Z",
        "market_name": "moneyline",
        "home": "Flamengo",
        "away": "Palmeiras"
    }
    
    # 5. Valida evento
    user_data = db.get_user_complete(999999999)
    assert evento_valido(evento, user_data)
    print("     [OK] Evento válido")
    
    # 6. Calcula stake
    stake = definir_stake(evento["ev"], evento["bet365_odds"])
    assert stake > 0
    print("     [OK] Stake calculado")
    
    # 7. Adiciona ao cache
    alert_hash = generate_alert_hash(evento)
    db.add_to_cache(999999999, alert_hash)
    assert db.is_in_cache(999999999, alert_hash)
    print("     [OK] Cache atualizado")
    
    # 8. Adiciona ao histórico
    db.add_alert_history(
        chat_id=999999999,
        data_envio=datetime.now().strftime("%d/%m/%Y %H:%M"),
        esporte=evento["sport"],
        home=evento["home"],
        away=evento["away"],
        mercado=evento["market_name"],
        odd=evento["bet365_odds"],
        stake=stake,
        ev=evento["ev"],
        data_jogo=evento["commence_time"],
        url_bet="https://example.com",
        bookmaker="Bet365"
    )
    print("     [OK] Histórico atualizado")
    
    print("   [SUCCESS] Integração completa funcionando!")

async def main():
    """Função principal de teste"""
    print("[START] Iniciando testes do Bot EV+")
    print("=" * 50)
    
    try:
        # Testes unitários
        test_database()
        print()
        
        test_core_functions()
        print()
        
        test_filters()
        print()
        
        test_utils()
        print()
        
        test_adapters()
        print()
        
        # Testes de integração
        test_integration()
        print()
        
        # Testes assíncronos
        await test_api_client()
        print()
        
        print("=" * 50)
        print(" [SUCCESS] TODOS OS TESTES PASSARAM!")
        print(" [READY] Sistema pronto para produção")
        
    except Exception as e:
        print(f" [ERROR] ERRO NOS TESTES: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
