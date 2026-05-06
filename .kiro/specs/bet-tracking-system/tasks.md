# Implementation Plan: Bet Tracking System

## Overview

Implementação incremental do sistema de tracking de apostas, seguindo a ordem definida no design: migração do banco → módulo de lógica pura → configurações → camada de envio → handlers de callbacks → jobs do scheduler → comandos de consulta. Cada etapa é validada antes de avançar para a próxima.

## Tasks

- [x] 1. Migração do banco de dados — `database.py`
  - Adicionar a tabela `bets_placed` ao método `_init_db()` como item 13, após a tabela `api_cache`, usando `CREATE TABLE IF NOT EXISTS` com todas as colunas e `CHECK(status IN (...))` conforme o design
  - Adicionar os dois blocos `ALTER TABLE ... ADD COLUMN` com try/except para `commence_time_ajustado` e `tentativas_lembrete` (compatibilidade com bancos existentes)
  - Criar os três índices: `idx_bets_chat`, `idx_bets_status`, `idx_bets_pending_reminder`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Módulo `bets_tracker.py` — lógica pura
  - [x] 2.1 Criar o arquivo `bets_tracker.py` com constantes, helpers e exceção
    - Definir `DURACAO_ESPORTE`, `DURACAO_DEFAULT`, `STATUSES_FINAIS`, `TIMESTAMP_FORMAT`
    - Implementar `now_utc_str()`, `gerar_alert_hash()`, `calcular_lucro()`
    - Definir `StatusFinalError` e `DadosAlerta` (TypedDict)
    - _Requirements: 2.4, 3.7, 4.2, 5.2_

  - [x] 2.2 Escrever testes de Property 2 — cálculo de lucro
    - **Property 2: Cálculo de lucro é consistente com o status**
    - Casos 2.1 a 2.8 conforme tabela do design (ganhou/perdeu/empate/cashout)
    - **Validates: Requirements 3.3, 3.4, 3.5, 3.6, 3.7**

  - [x] 2.3 Implementar `BetsTracker.__init__` e `registrar_alerta()`
    - Construtor recebe instância de `Database`; não chama `get_db()` internamente
    - `registrar_alerta()`: `INSERT OR IGNORE`, retorna `bet_id` do registro inserido ou existente via `lastrowid` ou `SELECT id WHERE alert_hash=?`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 2.4 Escrever testes de Property 1 — idempotência de inserção
    - **Property 1: Idempotência de inserção por alert_hash**
    - Casos 1.1, 1.2, 1.3 conforme tabela do design
    - **Validates: Requirements 2.2, 2.3**

  - [x] 2.5 Implementar `marcar_apostou()`, `marcar_pulei()`, `marcar_resultado()`, `marcar_resultado_expirado()`
    - `marcar_apostou()`: atualiza `valor_apostado` e `timestamp_apostou`; levanta `StatusFinalError` se status final
    - `marcar_pulei()`: atualiza `status='pulei'`; levanta `StatusFinalError` se status final
    - `marcar_resultado()`: atualiza status, calcula lucro via `calcular_lucro()`, registra `timestamp_resultado`; levanta `StatusFinalError` se status final
    - `marcar_resultado_expirado()`: atualiza `status='expirado'` sem levantar `StatusFinalError`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 2.6 Escrever testes de Property 5 — idempotência de callbacks em status final
    - **Property 5: Callbacks em status final são idempotentes**
    - Casos 5.1 a 5.6: verificar que nenhum campo é alterado quando status já é final
    - **Validates: Requirements 15.1, 15.2, 15.3**

  - [x] 2.7 Implementar métodos de lembrete: `get_pendentes_para_lembrete()`, `marcar_lembrete_enviado()`, `adiar_lembrete()`, `incrementar_tentativa_lembrete()`
    - `get_pendentes_para_lembrete()`: usa `COALESCE(commence_time_ajustado, commence_time)` + `DURACAO_ESPORTE` para filtrar apostas cujo jogo já terminou e `timestamp_lembrete_enviado IS NULL`
    - `marcar_lembrete_enviado()`: atualiza `timestamp_lembrete_enviado` e zera `tentativas_lembrete=0`
    - `adiar_lembrete()`: avança `commence_time_ajustado` em +3h a partir do `COALESCE`; seta `timestamp_lembrete_enviado=NULL`; levanta `StatusFinalError` se status final
    - `incrementar_tentativa_lembrete()`: incrementa e retorna novo valor
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 12.3, 12.4, 12.7_

  - [ ]* 2.8 Escrever testes de Property 3 — adiar preserva commence_time original
    - **Property 3: Adiar lembrete preserva commence_time original**
    - Casos 3.1, 3.2, 3.3 conforme tabela do design
    - **Validates: Requirements 5.4**

  - [x] 2.9 Implementar `expirar_alertas_antigos()` e métodos de consulta: `get_resumo()`, `get_pendentes()`, `get_historico()`, `get_bet_status()`
    - `expirar_alertas_antigos()`: `UPDATE status='expirado' WHERE status='pendente' AND valor_apostado IS NULL AND commence_time + 2h < now`; retorna count
    - `get_resumo()`: agrega apenas status `ganhou/perdeu/empate/cashout`; calcula ROI; exclui `pendente/pulei/expirado`
    - `get_pendentes()`: filtra `status='pendente' AND valor_apostado IS NOT NULL`; ordena por `COALESCE`
    - `get_historico()`: filtra status finalizados; ordena por `timestamp_resultado DESC`; aplica limit
    - `get_bet_status()`: retorna `str | None`
    - _Requirements: 4.1, 4.2, 4.3, 5.1, 6.1, 6.2, 6.3, 6.4_

  - [ ]* 2.10 Escrever testes de Property 4 — get_resumo exclui status não-finalizados
    - **Property 4: get_resumo exclui status não-finalizados dos totais**
    - Caso 4.1: 1 aposta de cada status; verificar `total_apostas=4` e totais apenas sobre finalizados
    - **Validates: Requirements 6.1**

- [x] 3. Checkpoint — Verificar módulo bets_tracker.py
  - Garantir que todos os testes em `tests/test_bets_tracker.py` passam, ask the user if questions arise.

- [x] 4. Modificações em `config.py`
  - Alterar `RATE_LIMIT_REQUESTS_PER_HOUR` de `4800` para `90`
  - Adicionar `THRESHOLD_EV_ALTO = 0.08` mantendo todas as constantes e funções existentes
  - _Requirements: 13.1, 13.2, 13.3_

- [x] 5. Modificações em `bot_ev.py` — templates e botões
  - [x] 5.1 Adicionar imports e criar funções de template
    - Importar `InlineKeyboardButton`, `InlineKeyboardMarkup` de `telegram`
    - Importar `THRESHOLD_EV_ALTO` de `config`
    - Criar `_formatar_alerta_normal()`: inicia com `🟢 <b>Alerta EV+</b>`, corpo idêntico ao template atual
    - Criar `_formatar_alerta_destacado()`: inicia com `🚨🚨 <b>ALERTA EV ALTO</b> 🚨🚨`, adiciona `⭐` ao EV, inclui linha `⚡ Aposte rápido`
    - _Requirements: 7.1, 7.2_

  - [x] 5.2 Criar `_montar_keyboard()` e atualizar `enviar_alerta()` e `enviar_alerta_instantaneo()`
    - `_montar_keyboard(bet_id)`: retorna `InlineKeyboardMarkup` com `[✅ Apostei | bet_yes:{bet_id}]` e `[❌ Pulei | bet_no:{bet_id}]`
    - `enviar_alerta()`: chamar `gerar_alert_hash(chat_id, home, away, market_type, bet_side, bookmaker, commence_time)` → chamar `registrar_alerta(alert_hash, ...)` → obter `bet_id` → escolher template por `THRESHOLD_EV_ALTO` → montar keyboard → enviar com `parse_mode='HTML'`, `disable_web_page_preview=True`
    - `enviar_alerta_instantaneo()`: mesmo fluxo com `gerar_alert_hash` + `registrar_alerta`, sempre usa `_formatar_alerta_destacado`
    - _Requirements: 7.3, 7.4, 7.5, 7.6_

- [x] 6. Callbacks "Apostei" e "Pulei" + text handler em `bot_listener.py`
  - [x] 6.1 Adicionar imports e instância global de `BetsTracker`
    - Importar `BetsTracker`, `StatusFinalError`, `STATUSES_FINAIS` de `bets_tracker`
    - Instanciar `bets_tracker = BetsTracker(db)` usando a instância global `db` já existente
    - _Requirements: 2.4_

  - [x] 6.2 Implementar `bet_yes_callback`
    - Extrair `bet_id` do `callback_data`
    - Verificar status via `get_bet_status(bet_id)`; se `None` → `query.answer("Aposta não encontrada", show_alert=True)`; se status final → `query.answer("Esta aposta já foi registrada", show_alert=True)`
    - Se pendente: editar mensagem removendo botões e adicionando `⏳ Aguardando valor da aposta...`; setar `context.user_data['esperando_valor_aposta'] = bet_id`
    - _Requirements: 8.1, 8.2, 15.1, 15.3_

  - [x] 6.3 Implementar `bet_no_callback`
    - Extrair `bet_id`; verificar status (mesma lógica de idempotência)
    - Se pendente: chamar `bets_tracker.marcar_pulei(bet_id)`; editar mensagem adicionando `❌ Pulado`
    - _Requirements: 9.1, 9.2, 9.3, 15.1_

  - [x] 6.4 Implementar `text_handler`
    - Verificar `context.user_data` para `esperando_valor_aposta` ou `esperando_valor_cashout`
    - Validar texto contra `^\d+([.,]\d{1,2})?$`; rejeitar valor ≤ 0 após conversão
    - Se válido: normalizar vírgula→ponto, converter para `float`
    - Fluxo aposta: chamar `marcar_apostou(bet_id, valor)`; limpar estado; editar mensagem adicionando `💰 Apostado: R$ X,XX`
    - Fluxo cashout: chamar `marcar_resultado(bet_id, 'cashout', valor_cashout=valor)`; limpar estado; editar mensagem adicionando `💸 Cashout: R$ X,XX`
    - Se inválido: responder com erro sem limpar estado de espera
    - _Requirements: 8.3, 8.4, 8.5, 8.7, 10.5, 14.1, 14.2, 14.3, 14.4, 14.5_

  - [ ]* 6.5 Escrever testes de Property 6 — validação monetária
    - **Property 6: Validação monetária rejeita entradas inválidas**
    - Casos 6.1 a 6.10 conforme tabela do design (válidos e inválidos)
    - **Validates: Requirements 14.1, 14.2, 14.3**

  - [x] 6.6 Registrar handlers `bet_yes_callback` e `bet_no_callback` no `ApplicationBuilder`
    - Adicionar `CallbackQueryHandler` com padrões `^bet_yes:\d+$` e `^bet_no:\d+$`
    - Adicionar `MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)`
    - _Requirements: 8.1, 9.1_

  - [x] 6.7 Checkpoint manual — testar envio de alerta com botões e fluxo Apostei
    - Subir o bot localmente e disparar um alerta manualmente (via scan ou comando de teste)
    - Verificar que a mensagem chega com os botões `[✅ Apostei]` e `[❌ Pulei]`
    - Clicar em "Apostei", verificar que a mensagem edita para `⏳ Aguardando valor da aposta...`
    - Digitar um valor válido (ex: `50`) e verificar que a mensagem edita para `💰 Apostado: R$ 50,00`
    - Verificar que o registro aparece na tabela `bets_placed` com `valor_apostado=50.0` e `status='pendente'`
    - _Requirements: 7.3, 8.1, 8.2, 8.3, 8.4_

- [x] 7. Job de lembrete pós-jogo em `main_scheduler.py`
  - [x] 7.0 Implementar funções auxiliares de formatação do lembrete
    - Implementar `_formatar_lembrete(aposta: dict) -> str`: formata mensagem HTML com jogo, liga, mercado, odd, valor apostado e horário do jogo (usando `COALESCE(commence_time_ajustado, commence_time)`)
    - Implementar `_montar_keyboard_resultado(bet_id: int) -> InlineKeyboardMarkup`: retorna keyboard com 5 botões em 2 linhas — `[🟢 Ganhei | 🔴 Perdi | ⚪ Empate]` e `[💸 Cashout | ⏰ Adiar 3h]`
    - Essas funções podem residir em `bot_listener.py` ou em módulo auxiliar; devem estar disponíveis antes da task 7.2
    - _Requirements: 10.1_

  - [x] 7.1 Adicionar import e instância de `BetsTracker` em `BotScheduler.__init__`
    - Importar `BetsTracker` de `bets_tracker`
    - Instanciar `self.bets_tracker = BetsTracker(self.db)` no `__init__`
    - _Requirements: 12.1_

  - [x] 7.2 Implementar `lembrete_pos_jogo_job()`
    - Chamar `self.bets_tracker.get_pendentes_para_lembrete()`
    - Para cada aposta: extrair `chat_id = aposta['chat_id']` e `bet_id = aposta['id']`
    - Formatar mensagem com `_formatar_lembrete(aposta)` e montar keyboard com `_montar_keyboard_resultado(bet_id)`
    - Sucesso: chamar `marcar_lembrete_enviado(bet_id)`
    - Falha: logar erro; chamar `incrementar_tentativa_lembrete(bet_id)`; se retorno `>= 5` → chamar `marcar_resultado_expirado(bet_id)`; `timestamp_lembrete_enviado` permanece NULL
    - _Requirements: 12.1, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [x] 7.3 Adicionar job ao `start()` com `IntervalTrigger(minutes=15)` e `max_instances=1`
    - Manter todos os jobs existentes sem modificação
    - _Requirements: 12.1, 12.5_

- [x] 8. Callbacks de resultado em `bot_listener.py`
  - [x] 8.1 Implementar `bet_result_win_callback`, `bet_result_loss_callback`, `bet_result_push_callback`
    - Cada callback: extrair `bet_id`; verificar status (idempotência); se status final → `query.answer`
    - `win`: chamar `marcar_resultado(bet_id, 'ganhou')`; editar mensagem adicionando `🟢 Ganhou (+R$ X,XX)`
    - `loss`: chamar `marcar_resultado(bet_id, 'perdeu')`; editar mensagem adicionando `🔴 Perdeu (-R$ X,XX)`
    - `push`: chamar `marcar_resultado(bet_id, 'empate')`; editar mensagem adicionando `⚪ Empate (R$ 0,00)`
    - _Requirements: 10.2, 10.3, 10.4, 15.1, 15.3_

  - [x] 8.2 Implementar `bet_cashout_callback`
    - Verificar status (idempotência)
    - Se pendente: editar mensagem adicionando `⏳ Aguardando valor do cashout...`; setar `context.user_data['esperando_valor_cashout'] = bet_id`
    - _Requirements: 10.5, 15.1_

  - [x] 8.3 Implementar `bet_postpone_callback`
    - Verificar status (idempotência); se status final → `query.answer`
    - Se pendente: chamar `bets_tracker.adiar_lembrete(bet_id)`; responder com `query.answer('Lembrete adiado por 3 horas', show_alert=False)` (toast não-bloqueante); manter a mensagem de lembrete com os botões intactos (não editar a mensagem)
    - _Requirements: 10.6, 15.2_

  - [x] 8.4 Registrar handlers de resultado no `ApplicationBuilder`
    - Adicionar `CallbackQueryHandler` para `^bet_result_win:\d+$`, `^bet_result_loss:\d+$`, `^bet_result_push:\d+$`, `^bet_cashout:\d+$`, `^bet_postpone:\d+$`
    - _Requirements: 10.1_

- [x] 9. Checkpoint — Verificar integração callbacks + tracker
  - Garantir que todos os testes passam e que o fluxo completo (alerta → apostei → resultado) funciona sem erros, ask the user if questions arise.

- [x] 10. Comandos `/banca`, `/pendentes`, `/historico` em `bot_listener.py`
  - [x] 10.1 Implementar `banca_command`
    - Aceitar `/banca` (padrão 30 dias) ou `/banca {dias}`
    - Chamar `bets_tracker.get_resumo(chat_id, dias)`
    - Formatar resposta com: total apostas, W/L/Push/Cashout, total investido, retorno, lucro, ROI%
    - Se sem dados: responder com mensagem informativa
    - _Requirements: 11.1, 11.4_

  - [x] 10.2 Implementar `pendentes_command`
    - Chamar `bets_tracker.get_pendentes(chat_id)`
    - Listar cada aposta com: jogo, mercado, odd, valor apostado, horário
    - Se sem dados: responder com mensagem informativa
    - _Requirements: 11.2, 11.4_

  - [x] 10.3 Implementar `historico_command`
    - Chamar `bets_tracker.get_historico(chat_id)`
    - Listar cada aposta com: jogo, resultado, odd, valor apostado, lucro
    - Se sem dados: responder com mensagem informativa
    - _Requirements: 11.3, 11.4_

  - [x] 10.4 Registrar `CommandHandler` para `banca`, `pendentes`, `historico` no `ApplicationBuilder`
    - _Requirements: 11.1, 11.2, 11.3_

- [x] 11. Job de expiração em `main_scheduler.py`
  - Implementar `expiracao_job()`: chamar `self.bets_tracker.expirar_alertas_antigos()`; logar count se `> 0`
  - Adicionar job ao `start()` com `IntervalTrigger(minutes=30)` e `max_instances=1`
  - Manter todos os jobs existentes sem modificação
  - _Requirements: 4.1, 4.2, 4.3, 12.2, 12.5_

- [ ] 12. Testes unitários completos — `tests/test_bets_tracker.py`
  - [ ]* 12.1 Completar todos os 31 casos de teste definidos no design
    - Property 1 (casos 1.1–1.3): idempotência de inserção
    - Property 2 (casos 2.1–2.8): cálculo de lucro
    - Property 3 (casos 3.1–3.3): adiar preserva commence_time
    - Property 4 (caso 4.1): get_resumo exclui não-finalizados
    - Property 5 (casos 5.1–5.6): idempotência de callbacks em status final
    - Property 6 (casos 6.1–6.10): validação monetária
    - **Validates: Requirements 2.2, 2.3, 3.3–3.7, 5.4, 6.1, 14.1–14.3, 15.1–15.3**

- [x] 13. Checkpoint final — Garantir que todos os testes passam
  - Garantir que todos os testes passam, ask the user if questions arise.

## Notes

- Tasks marcadas com `*` são opcionais e podem ser puladas para um MVP mais rápido
- Cada task referencia os requisitos específicos para rastreabilidade
- A ordem das tasks segue a dependência entre módulos: `database.py` → `bets_tracker.py` → `config.py` → `bot_ev.py` → `bot_listener.py` → `main_scheduler.py`
- Os testes de Property 5 (idempotência) testam a lógica do `BetsTracker` diretamente, sem dependência do Telegram
- Os testes de Property 6 (validação monetária) testam a função de validação isolada do handler
- `StatusFinalError` serve como defesa em profundidade — os handlers já verificam o status antes de chamar o tracker, mas o tracker também protege contra chamadas diretas
