# Implementation Plan: v1.2 — Aviso de Jogo Duplicado, Odd Apostada e Gestão de Banca

## Overview

Implementação incremental seguindo a ordem: `database.py` → `bets_tracker.py` → `bot_ev.py` → `bot_listener.py` → `main_scheduler.py`. Cada etapa constrói sobre a anterior, garantindo que não haja código órfão. Testes property-based (Hypothesis) validam as propriedades de correção definidas no design.

## Tasks

- [x] 1. Migração de banco de dados
  - [x] 1.1 Adicionar tabela `user_bankroll` em `src/core/database.py`
    - No método `_init_db()`, após a criação da tabela `bets_placed`, adicionar `CREATE TABLE IF NOT EXISTS user_bankroll` com colunas: `chat_id` (TEXT PRIMARY KEY), `bankroll` (REAL NOT NULL), `valor_unidade` (REAL NOT NULL), `timestamp` (TEXT)
    - Garantir que a migração `ALTER TABLE bets_placed ADD COLUMN odd_apostada REAL DEFAULT NULL` já existente continue funcionando
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3_

  - [x]* 1.2 Write property test: round-trip de criação de tabela
    - **Property 4: Round-trip de configuração de bankroll**
    - **Validates: Requirements 5.1, 5.2**
    - Testar que após INSERT na tabela `user_bankroll`, SELECT retorna os mesmos valores

- [x] 2. Implementar novos métodos no BetsTracker
  - [x] 2.1 Implementar `buscar_alertas_mesmo_jogo()` em `src/bot/bets_tracker.py`
    - Método recebe `(chat_id, home, away, commence_time)` e retorna `list[dict]`
    - Query filtra por `chat_id`, `home`, `away` e `substr(commence_time, 1, 16)` iguais
    - Retorna lista vazia se nenhum registro encontrado
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 2.2 Write property test: consulta alertas mesmo jogo
    - **Property 1: Consulta de alertas do mesmo jogo retorna registros corretos**
    - **Validates: Requirements 3.1, 3.2**
    - Usar Hypothesis para gerar alertas com commence_times variados e verificar que apenas os com primeiros 16 chars iguais são retornados

  - [x] 2.3 Implementar `configurar_bankroll()` e `get_bankroll()` em `src/bot/bets_tracker.py`
    - `configurar_bankroll(chat_id, bankroll, valor_unidade)`: INSERT OR REPLACE em `user_bankroll` com timestamp atual
    - `get_bankroll(chat_id)`: SELECT retorna `dict` com `bankroll` e `valor_unidade`, ou `None`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x]* 2.4 Write property test: round-trip bankroll
    - **Property 4: Round-trip de configuração de bankroll**
    - **Validates: Requirements 5.1, 5.2**
    - Para qualquer chat_id, bankroll > 0 e valor_unidade > 0, após configurar, get_bankroll retorna os mesmos valores

  - [x] 2.5 Implementar `resetar_banca()` em `src/bot/bets_tracker.py`
    - DELETE FROM bets_placed WHERE chat_id = ?
    - DELETE FROM user_bankroll WHERE chat_id = ?
    - _Requirements: 6.1, 6.2, 6.3_

  - [x]* 2.6 Write property test: reset apaga dados
    - **Property 5: Reset apaga todos os dados do usuário**
    - **Validates: Requirements 6.1, 6.2**
    - Após inserir N apostas e configurar bankroll, resetar_banca deve resultar em listas vazias e bankroll None

  - [x]* 2.7 Write property test: persistência de odd_apostada com fallback
    - **Property 2: Persistência de odd_apostada com fallback**
    - **Validates: Requirements 4.1, 4.2**
    - Testar que marcar_apostou com odd_apostada=None copia odd_alerta, e com valor informado persiste o valor

  - [x]* 2.8 Write property test: cálculo de lucro usa odd correta
    - **Property 3: Cálculo de lucro usa odd correta**
    - **Validates: Requirements 4.3**
    - Testar que marcar_resultado usa odd_apostada quando disponível, fallback odd_alerta

- [x] 3. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implementar aviso de jogo duplicado no AlertSender
  - [x] 4.1 Implementar `_montar_aviso_mesmo_jogo()` em `src/bot/bot_ev.py`
    - Método recebe `list[dict]` de alertas anteriores
    - Retorna string vazia se lista vazia
    - Para lista não-vazia, retorna texto formatado: `⚠️ Jogo duplicado! Você já recebeu X alerta(s):\n• Mercado: {market_type} | Odd: {odd} | Status: {status}`
    - _Requirements: 7.1, 7.2, 7.3_

  - [x]* 4.2 Write property test: construção de aviso duplicado
    - **Property 6: Construção de aviso de jogo duplicado**
    - **Validates: Requirements 7.1, 7.2**
    - Para lista vazia retorna string vazia; para lista não-vazia retorna string contendo info de cada alerta

  - [x] 4.3 Alterar templates para aceitar parâmetro `aviso` em `src/bot/bot_ev.py`
    - Adicionar parâmetro `aviso: str = ""` em `_formatar_alerta_destacado()` e `_formatar_alerta_normal()`
    - Se `aviso` não vazio, injetar após a primeira linha do template (após o cabeçalho)
    - Se `aviso` vazio ou None, não alterar o template
    - _Requirements: 8.1, 8.2, 8.3_

  - [x]* 4.4 Write property test: injeção de aviso no template
    - **Property 7: Injeção de aviso no template**
    - **Validates: Requirements 8.2, 8.3**
    - Para aviso não-vazio, mensagem resultante contém o texto do aviso; para aviso vazio, mensagem não contém aviso

  - [x] 4.5 Integrar aviso em `enviar_alerta()` e `enviar_alerta_instantaneo()` em `src/bot/bot_ev.py`
    - Antes de `registrar_alerta()`, chamar `buscar_alertas_mesmo_jogo(chat_id, home, away, commence_time)`
    - Passar resultado para `_montar_aviso_mesmo_jogo()`
    - Passar aviso resultante para os métodos de formatação de template
    - _Requirements: 7.4, 7.5_

- [x] 5. Implementar parser e comandos no Listener
  - [x] 5.1 Implementar `_parsear_valor_e_odd()` em `src/bot/bot_listener.py`
    - Função recebe string de texto do usuário
    - Aceita formatos: `"50"` → (50.0, None), `"50 1.47"` → (50.0, 1.47), `"50 1,47"` → (50.0, 1.47)
    - Retorna `None` para input inválido (texto não-numérico, odd < 1.01, mais de 2 partes, valor <= 0)
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x]* 5.2 Write property test: parsing de valor e odd
    - **Property 8: Parsing de valor e odd**
    - **Validates: Requirements 9.1, 9.2, 9.3**
    - Testar round-trip para valores válidos e rejeição de inputs inválidos

  - [x] 5.3 Alterar `bet_text_handler()` para usar `_parsear_valor_e_odd()` em `src/bot/bot_listener.py`
    - Substituir chamada a `_validar_valor()` por `_parsear_valor_e_odd()`
    - Passar `odd_apostada` retornada para `marcar_apostou(bet_id, valor, odd_apostada)`
    - Manter mensagem de erro ao usuário quando retorno é None
    - _Requirements: 9.5_

  - [x] 5.4 Implementar `banca_command()` em `src/bot/bot_listener.py`
    - `/banca 1000 50` → validar argumentos (> 0), chamar `configurar_bankroll(chat_id, 1000, 50)`, confirmar ao usuário
    - `/banca` sem argumentos → chamar `get_bankroll(chat_id)`, exibir resumo (bankroll, valor_unidade, total apostado, lucro, ROI via `get_resumo()`)
    - `/banca` sem argumentos e sem banca configurada → mensagem orientando uso correto
    - Registrar handler: `CommandHandler("banca", banca_command)`
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 5.5 Implementar `reset_command()` em `src/bot/bot_listener.py`
    - `/reset` sem CONFIRMAR → mensagem de aviso explicando consequências
    - `/reset CONFIRMAR` → chamar `resetar_banca(chat_id)`, confirmar ao usuário
    - Registrar handler: `CommandHandler("reset", reset_command)`
    - _Requirements: 12.1, 12.2, 12.3_

  - [x] 5.6 Alterar `pendentes_command()` e `historico_command()` para exibir odd_apostada em `src/bot/bot_listener.py`
    - Exibir `odd_apostada` quando disponível (não-None), fallback para `odd_alerta`
    - _Requirements: 10.1, 10.2_

  - [x]* 5.7 Write property test: exibição de odd com fallback
    - **Property 9: Exibição de odd com fallback**
    - **Validates: Requirements 10.1, 10.2, 10.3**
    - Testar que a lógica de fallback odd_apostada → odd_alerta funciona corretamente

- [x] 6. Alterar Scheduler para exibir odd_apostada
  - [x] 6.1 Alterar `_formatar_lembrete()` em `src/scanner/main_scheduler.py`
    - Exibir `odd_apostada` quando disponível, fallback para `odd_alerta`
    - _Requirements: 10.3_

- [x] 7. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Implementation order follows user specification: database.py → bets_tracker.py → bot_ev.py → bot_listener.py → main_scheduler.py
