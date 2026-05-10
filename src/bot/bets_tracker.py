"""
Módulo de tracking de apostas — lógica pura sem dependência do Telegram.
Persiste e consulta apostas rastreadas na tabela bets_placed.
"""
import hashlib
from datetime import datetime, timezone, timedelta
from typing import TypedDict

from src.core.database import Database

# --- Constantes ---

DURACAO_ESPORTE: dict[str, float] = {
    "soccer":           2.5,
    "basketball":       2.5,
    "tennis":           3.0,
    "americanfootball": 3.5,
    "baseball":         3.5,
    "hockey":           2.5,
    "mma":              2.0,
    "boxing":           2.0,
    "esports":          2.0,
}
DURACAO_DEFAULT: float = 3.0

STATUSES_FINAIS: frozenset[str] = frozenset({
    "ganhou", "perdeu", "empate", "cashout", "pulei", "expirado"
})

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


# --- Exceção de defesa em profundidade ---

class StatusFinalError(Exception):
    """
    Levantada quando uma operação de mutação é tentada em uma aposta
    que já possui status final. Serve como defesa em profundidade
    contra bugs futuros nos handlers.
    """


# --- TypedDict para dados do alerta ---

class DadosAlerta(TypedDict):
    home: str
    away: str
    league: str
    sport: str
    market_type: str
    bet_side: str
    bookmaker: str
    odd_alerta: float
    ev_alerta: float
    commence_time: str


# --- Funções utilitárias ---

def now_utc_str() -> str:
    """Retorna timestamp UTC atual no formato padrão do banco."""
    return datetime.now(timezone.utc).strftime(TIMESTAMP_FORMAT)


def gerar_alert_hash(
    chat_id: str,
    home: str,
    away: str,
    market_type: str,
    bet_side: str,
    bookmaker: str,
    commence_time: str,
) -> str:
    """SHA-256 truncado em 32 chars dos campos canônicos do alerta."""
    raw = f"{chat_id}|{home}|{away}|{market_type}|{bet_side}|{bookmaker}|{commence_time}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def calcular_lucro(
    odd: float,
    valor_apostado: float,
    status: str,
    valor_cashout: float | None = None,
) -> float:
    """
    Calcula lucro líquido conforme o resultado.
    - ganhou:  (odd - 1) * valor_apostado
    - perdeu:  -valor_apostado
    - empate:  0.0
    - cashout: valor_cashout - valor_apostado
    Levanta ValueError para status inválido ou cashout sem valor.
    """
    if status == "ganhou":
        return (odd - 1) * valor_apostado
    elif status == "perdeu":
        return -valor_apostado
    elif status == "empate":
        return 0.0
    elif status == "cashout":
        if valor_cashout is None:
            raise ValueError("valor_cashout é obrigatório para status 'cashout'")
        return valor_cashout - valor_apostado
    else:
        raise ValueError(f"Status inválido para cálculo de lucro: {status}")


# --- Classe principal ---

class BetsTracker:
    def __init__(self, db: Database):
        """Recebe instância de Database. Não chama get_db() internamente."""
        self.db = db

    # --- Registro ---
    def registrar_alerta(
        self,
        alert_hash: str,
        chat_id: str,
        feed_id: str,
        dados_alerta: DadosAlerta,
    ) -> int:
        """
        INSERT OR IGNORE em bets_placed.
        Retorna bet_id (id) do registro inserido ou já existente.
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO bets_placed (
                    alert_hash, chat_id, feed_id,
                    home, away, league, sport, market_type, bet_side,
                    bookmaker, odd_alerta, ev_alerta, commence_time,
                    timestamp_alerta
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert_hash, chat_id, feed_id,
                dados_alerta.get('home', ''),
                dados_alerta.get('away', ''),
                dados_alerta.get('league', ''),
                dados_alerta.get('sport', ''),
                dados_alerta.get('market_type', ''),
                dados_alerta.get('bet_side', ''),
                dados_alerta.get('bookmaker', ''),
                dados_alerta.get('odd_alerta', 0),
                dados_alerta.get('ev_alerta', 0),
                dados_alerta.get('commence_time', ''),
                now_utc_str(),
            ))

            if cursor.lastrowid and cursor.lastrowid > 0:
                return cursor.lastrowid

            # Registro já existia — busca o id
            row = conn.execute(
                "SELECT id FROM bets_placed WHERE alert_hash = ?",
                (alert_hash,)
            ).fetchone()
            return row['id'] if row else 0

    # --- Verificação de status ---
    def get_bet_status(self, bet_id: int) -> str | None:
        """
        Retorna o status atual de uma aposta ou None se não encontrada.
        Usado pelos handlers para verificar idempotência.
        """
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM bets_placed WHERE id = ?", (bet_id,)
            ).fetchone()
            return row['status'] if row else None

    # --- Atualização de status ---
    def marcar_apostou(self, bet_id: int, valor: float, odd_apostada: float | None = None) -> None:
        """
        UPDATE valor_apostado, odd_apostada e timestamp_apostou.
        Se odd_apostada for None, copia odd_alerta do registro.
        Levanta StatusFinalError se a aposta já tem status final.
        """
        status = self.get_bet_status(bet_id)
        if status in STATUSES_FINAIS:
            raise StatusFinalError(f"Aposta {bet_id} já tem status final: {status}")

        with self.db.get_connection() as conn:
            if odd_apostada is None:
                # Fallback: copia odd_alerta
                row = conn.execute(
                    "SELECT odd_alerta FROM bets_placed WHERE id = ?", (bet_id,)
                ).fetchone()
                odd_apostada = row['odd_alerta'] if row else None

            conn.execute("""
                UPDATE bets_placed
                SET valor_apostado = ?, odd_apostada = ?, timestamp_apostou = ?
                WHERE id = ?
            """, (valor, odd_apostada, now_utc_str(), bet_id))

    def marcar_pulei(self, bet_id: int) -> None:
        """
        UPDATE status='pulei'.
        Levanta StatusFinalError se a aposta já tem status final.
        """
        status = self.get_bet_status(bet_id)
        if status in STATUSES_FINAIS:
            raise StatusFinalError(f"Aposta {bet_id} já tem status final: {status}")

        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE bets_placed SET status = 'pulei' WHERE id = ?
            """, (bet_id,))

    def marcar_resultado(
        self,
        bet_id: int,
        resultado: str,
        valor_cashout: float | None = None,
    ) -> None:
        """
        Atualiza status, calcula lucro e registra timestamp_resultado.
        resultado in {'ganhou','perdeu','empate','cashout'}.
        Para 'cashout', valor_cashout é obrigatório.
        Levanta StatusFinalError se a aposta já tem status final.
        """
        status = self.get_bet_status(bet_id)
        if status in STATUSES_FINAIS:
            raise StatusFinalError(f"Aposta {bet_id} já tem status final: {status}")

        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT odd_alerta, odd_apostada, valor_apostado FROM bets_placed WHERE id = ?",
                (bet_id,)
            ).fetchone()

            odd = (row['odd_apostada'] or row['odd_alerta']) if row else 0
            valor_apostado = row['valor_apostado'] if row else 0

            lucro = calcular_lucro(odd, valor_apostado or 0, resultado, valor_cashout)

            conn.execute("""
                UPDATE bets_placed
                SET status = ?, lucro = ?, valor_cashout = ?,
                    timestamp_resultado = ?
                WHERE id = ?
            """, (resultado, lucro, valor_cashout, now_utc_str(), bet_id))

    def marcar_resultado_expirado(self, bet_id: int) -> None:
        """
        UPDATE status='expirado'.
        Usado pelo scheduler após 5 tentativas de lembrete falhas.
        Não levanta StatusFinalError — expiração forçada pelo sistema é sempre permitida.
        """
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE bets_placed SET status = 'expirado' WHERE id = ?
            """, (bet_id,))

    # --- Lembretes ---
    def get_pendentes_para_lembrete(self) -> list[dict]:
        """
        Retorna apostas pendentes cujo jogo já terminou e que ainda não
        receberam lembrete.
        """
        now = datetime.now(timezone.utc)
        with self.db.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM bets_placed
                WHERE status = 'pendente'
                  AND valor_apostado IS NOT NULL
                  AND timestamp_lembrete_enviado IS NULL
            """).fetchall()

        resultado = []
        for row in rows:
            row_dict = dict(row)
            sport = row_dict.get('sport', '') or ''
            duracao = DURACAO_ESPORTE.get(sport.lower(), DURACAO_DEFAULT)

            ct = row_dict.get('commence_time_ajustado') or row_dict.get('commence_time', '')
            if not ct:
                continue

            try:
                # Parse do commence_time
                if 'T' in ct:
                    jogo_time = datetime.fromisoformat(ct.replace('Z', '+00:00'))
                else:
                    jogo_time = datetime.strptime(ct, TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)

                fim_jogo = jogo_time + timedelta(hours=duracao)
                if now > fim_jogo:
                    resultado.append(row_dict)
            except (ValueError, TypeError):
                continue

        return resultado

    def marcar_lembrete_enviado(self, bet_id: int) -> None:
        """
        Atualiza timestamp_lembrete_enviado e zera tentativas_lembrete.
        """
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE bets_placed
                SET timestamp_lembrete_enviado = ?, tentativas_lembrete = 0
                WHERE id = ?
            """, (now_utc_str(), bet_id))



    def incrementar_tentativa_lembrete(self, bet_id: int) -> int:
        """
        Incrementa tentativas_lembrete em 1 e retorna o novo valor.
        """
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE bets_placed
                SET tentativas_lembrete = tentativas_lembrete + 1
                WHERE id = ?
            """, (bet_id,))
            row = conn.execute(
                "SELECT tentativas_lembrete FROM bets_placed WHERE id = ?",
                (bet_id,)
            ).fetchone()
            return row['tentativas_lembrete'] if row else 0

    # --- Expiração ---
    def expirar_alertas_antigos(self) -> int:
        """
        Expira alertas pendentes sem valor apostado cujo commence_time + 2h < agora.
        Retorna número de linhas afetadas.
        """
        limite = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(TIMESTAMP_FORMAT)
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                UPDATE bets_placed
                SET status = 'expirado'
                WHERE status = 'pendente'
                  AND valor_apostado IS NULL
                  AND commence_time < ?
            """, (limite,))
            return cursor.rowcount

    # --- Consultas ---
    def get_resumo(self, chat_id: str, dias: int = 30) -> dict:
        """
        Retorna resumo de ROI considerando apenas status finalizados
        (ganhou, perdeu, empate, cashout) dos últimos `dias` dias.
        """
        limite = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime(TIMESTAMP_FORMAT)
        with self.db.get_connection() as conn:
            rows = conn.execute("""
                SELECT status, valor_apostado, lucro, ev_alerta
                FROM bets_placed
                WHERE chat_id = ?
                  AND status IN ('ganhou', 'perdeu', 'empate', 'cashout')
                  AND timestamp_resultado >= ?
            """, (chat_id, limite)).fetchall()

        if not rows:
            return {
                "total_apostas": 0,
                "total_apostado": 0.0,
                "lucro_total": 0.0,
                "roi_pct": 0.0,
                "ganhou": 0,
                "perdeu": 0,
                "empate": 0,
                "cashout": 0,
                "ev_medio": 0.0,
            }

        total_apostas = len(rows)
        total_apostado = sum(r['valor_apostado'] or 0 for r in rows)
        lucro_total = sum(r['lucro'] or 0 for r in rows)
        roi_pct = (lucro_total / total_apostado * 100) if total_apostado > 0 else 0.0

        contagem = {"ganhou": 0, "perdeu": 0, "empate": 0, "cashout": 0}
        ev_soma = 0.0
        for r in rows:
            contagem[r['status']] = contagem.get(r['status'], 0) + 1
            ev_soma += r['ev_alerta'] or 0

        ev_medio = ev_soma / total_apostas if total_apostas > 0 else 0.0

        return {
            "total_apostas": total_apostas,
            "total_apostado": total_apostado,
            "lucro_total": lucro_total,
            "roi_pct": roi_pct,
            "ganhou": contagem["ganhou"],
            "perdeu": contagem["perdeu"],
            "empate": contagem["empate"],
            "cashout": contagem["cashout"],
            "ev_medio": ev_medio,
        }

    def get_pendentes(self, chat_id: str) -> list[dict]:
        """
        Retorna apostas pendentes com valor apostado, ordenadas por commence_time.
        """
        with self.db.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM bets_placed
                WHERE chat_id = ?
                  AND status = 'pendente'
                  AND valor_apostado IS NOT NULL
                ORDER BY COALESCE(commence_time_ajustado, commence_time) ASC
            """, (chat_id,)).fetchall()
            return [dict(r) for r in rows]

    def buscar_alertas_mesmo_jogo(self, chat_id: str, home: str, away: str, commence_time: str) -> list[dict]:
        """
        Retorna alertas anteriores para o mesmo jogo (match por chat_id + home + away + commence_time[:16]).
        """
        ct_prefix = commence_time[:16] if commence_time else ""
        with self.db.get_connection() as conn:
            rows = conn.execute("""
                SELECT id, market_type, bet_side, odd_alerta, odd_apostada,
                       ev_alerta, status, valor_apostado, timestamp_alerta, market_name_fmt
                FROM bets_placed
                WHERE chat_id = ?
                  AND home = ?
                  AND away = ?
                  AND substr(commence_time, 1, 16) = ?
            """, (chat_id, home, away, ct_prefix)).fetchall()
            return [dict(r) for r in rows] if rows else []

    def get_historico(self, chat_id: str, limit: int = 20) -> list[dict]:
        """
        Retorna últimas apostas finalizadas ordenadas por timestamp_resultado DESC.
        """
        with self.db.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM bets_placed
                WHERE chat_id = ?
                  AND status IN ('ganhou', 'perdeu', 'empate', 'cashout')
                ORDER BY timestamp_resultado DESC
                LIMIT ?
            """, (chat_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def configurar_bankroll(self, chat_id: str, bankroll: float, valor_unidade: float) -> None:
        """Salva ou atualiza bankroll e valor_unidade do usuário."""
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO user_bankroll (chat_id, bankroll, valor_unidade, timestamp)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    bankroll = excluded.bankroll,
                    valor_unidade = excluded.valor_unidade,
                    timestamp = excluded.timestamp
            """, (chat_id, bankroll, valor_unidade, now_utc_str()))

    def get_bankroll(self, chat_id: str) -> dict | None:
        """Retorna bankroll e valor_unidade ou None se não configurado."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT bankroll, valor_unidade FROM user_bankroll WHERE chat_id = ?",
                (chat_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_odd_alerta(self, bet_id: int) -> float:
        """Retorna odd_alerta de uma aposta pelo ID. Retorna 0.0 se não encontrada."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT odd_alerta FROM bets_placed WHERE id = ?", (bet_id,)
            ).fetchone()
            return row['odd_alerta'] if row and row['odd_alerta'] else 0.0

    def resetar_banca(self, chat_id: str) -> None:
        """Apaga todas as apostas e configuração de bankroll do usuário."""
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM bets_placed WHERE chat_id = ?", (chat_id,))
            conn.execute("DELETE FROM user_bankroll WHERE chat_id = ?", (chat_id,))
