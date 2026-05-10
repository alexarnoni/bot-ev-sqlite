# Plano de Implementação: Visual Improvements

## Visão Geral

Três melhorias visuais pontuais em `src/bot/bot_listener.py`: mensagem de confirmação com odd apostada, bloco comparativo de EV no lembrete pós-jogo, e separadores no histórico. Todas são alterações de formatação de strings sem impacto em banco de dados ou arquitetura.

## Tasks

- [x] 1. Atualizar mensagem de confirmação com odd apostada
  - Localizar a linha `await update.message.reply_text(f"✅ Aposta de R$ {valor:.2f} registrada!", parse_mode='HTML')` em `bet_text_handler()` (~linha 3240)
  - Substituir por lógica condicional: se `odd_apostada` existir, usar formato `"✅ Aposta registrada — R$ {valor:.2f} @ {odd_apostada:.2f}"`, senão `"✅ Aposta registrada — R$ {valor:.2f}"`
  - Manter `parse_mode='HTML'`
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Adicionar bloco comparativo de EV em `_formatar_lembrete()`
  - Localizar a função `_formatar_lembrete()` em `src/bot/bot_listener.py` (~linha 3399)
  - Extrair `ev_alerta`, `odd_alerta` e `odd_apostada` do dict `aposta`
  - Implementar lógica condicional: se `odd_apostada` difere de `odd_alerta`, `odd_alerta > 0` e `(1 + ev_alerta) > 0`, calcular `prob_implicita = 1 / (odd_alerta / (1 + ev_alerta))` e `ev_real = (odd_apostada * prob_implicita) - 1`
  - Inserir bloco formatado com `"📊 Odd alerta: ... → Odd apostada: ..."` e `"📈 EV original: ... → EV real: ..."` antes de `"Qual foi o resultado?"`
  - Omitir bloco completamente quando condições não satisfeitas
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 3. Adicionar separadores visuais em `historico_command()`
  - Localizar o loop `for ap in historico:` em `historico_command()` (~linha 3456)
  - Definir `separador = "─────────────────"` antes do loop
  - Adicionar `f"{separador}\n\n"` ao final de cada entrada no loop
  - Manter cabeçalho com título e período inalterado
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 4. Escrever testes de propriedade (Hypothesis)
  - [x] 4.1 Criar arquivo `tests/test_pbt_visual_improvements.py` com imports e setup
    - Importar `hypothesis`, `given`, `strategies`
    - Importar/recriar as funções de formatação para teste isolado
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2_

  - [ ]* 4.2 Propriedade 1: Formato da mensagem de confirmação
    - **Property 1: Formato da mensagem de confirmação**
    - Gerar `valor` (float positivo) e `odd_apostada` (float positivo ou None)
    - Verificar que a string contém `"R$ {valor:.2f}"` e contém `"@ {odd:.2f}"` sse odd não é None
    - **Validates: Requirements 1.1, 1.2**

  - [ ]* 4.3 Propriedade 2: Bloco EV presente quando odds diferem
    - **Property 2: Bloco EV presente e correto quando odds diferem**
    - Gerar aposta com `odd_apostada ≠ odd_alerta`, `odd_alerta > 0`, `(1 + ev_alerta) > 0`
    - Verificar presença de "📊" e "📈" na saída e posição antes de "Qual foi o resultado?"
    - **Validates: Requirements 2.1, 2.3**

  - [ ]* 4.4 Propriedade 3: Bloco EV omitido quando condições não satisfeitas
    - **Property 3: Bloco EV omitido quando condições não satisfeitas**
    - Gerar aposta com odds iguais, ou odd_apostada=None, ou odd_alerta=0, ou ev_alerta≤-1
    - Verificar ausência de "📊" e "📈" na saída
    - **Validates: Requirements 2.4, 2.5**

  - [ ]* 4.5 Propriedade 4: Corretude do cálculo de EV
    - **Property 4: Corretude do cálculo de EV**
    - Gerar `odd_alerta > 0`, `ev_alerta > -1`, `odd_apostada > 0`
    - Verificar que ev_real == `(odd_apostada * (1 + ev_alerta) / odd_alerta) - 1` com tolerância de ponto flutuante
    - **Validates: Requirements 2.2**

  - [ ]* 4.6 Propriedade 5: Estrutura do histórico com separadores
    - **Property 5: Estrutura do histórico com separadores**
    - Gerar lista de 1-20 apostas com dados aleatórios
    - Verificar presença do cabeçalho e que cada aposta é seguida pelo separador `"─────────────────"`
    - **Validates: Requirements 3.1, 3.2**

- [x] 5. Checkpoint final
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

## Notas

- Tasks marcadas com `*` são opcionais e podem ser puladas para um MVP mais rápido
- Cada task referencia requisitos específicos para rastreabilidade
- Testes de propriedade validam propriedades universais de corretude definidas no design
- Todas as alterações são restritas a `src/bot/bot_listener.py` e ao novo arquivo de testes
