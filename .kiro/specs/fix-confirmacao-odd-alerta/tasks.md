# Plano de Implementação

- [x] 1. Escrever teste exploratório da condição do bug
  - **Property 1: Bug Condition** - Confirmação omite odd quando odd_apostada é None
  - **CRITICAL**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: Este teste codifica o comportamento esperado — ele validará o fix quando passar após a implementação
  - **GOAL**: Demonstrar contraexemplos que evidenciam o bug
  - **Scoped PBT Approach**: Gerar valores aleatórios de `odd_alerta` (float > 0) com `odd_apostada=None` e verificar que as mensagens contêm "@ {odd_alerta:.2f}"
  - Condição do bug: `isBugCondition(input)` onde `input.odd_apostada IS NULL AND input.bet_id EXISTS in bets_placed AND bets_placed[input.bet_id].odd_alerta > 0`
  - Comportamento esperado: `texto_confirmacao` contém `f"@ {odd_alerta:.2f}"` E `mensagem_editada` contém `f"@ {odd_alerta:.2f}"`
  - Executar teste no código NÃO corrigido
  - **EXPECTED OUTCOME**: Teste FALHA (isso é correto — prova que o bug existe)
  - Documentar contraexemplos encontrados para entender a causa raiz
  - Marcar tarefa como completa quando o teste estiver escrito, executado e a falha documentada
  - _Requirements: 1.1, 1.2, 2.1, 2.2_

- [x] 2. Escrever testes de preservação (ANTES de implementar o fix)
  - **Property 2: Preservation** - Comportamento inalterado quando odd é fornecida
  - **IMPORTANT**: Seguir metodologia observation-first
  - Observar: quando `odd_apostada` é fornecida (ex: 1.47), `texto_confirmacao` contém `f"@ {odd_apostada:.2f}"` no código não corrigido
  - Observar: quando `odd_apostada` é fornecida, `mensagem_editada` contém `f"@ {odd_apostada}"` no código não corrigido
  - Observar: quando formato é inválido, mensagem de erro "❌" é retornada no código não corrigido
  - Escrever teste property-based: para todo `odd_apostada` (float > 0) e `valor` (float > 0), resultado contém `f"@ {odd_apostada:.2f}"` (de Preservation Requirements no design)
  - Verificar que o teste PASSA no código NÃO corrigido
  - **EXPECTED OUTCOME**: Testes PASSAM (confirma comportamento baseline a preservar)
  - Marcar tarefa como completa quando testes estiverem escritos, executados e passando no código não corrigido
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 3. Fix para confirmação sempre exibir odd (alerta como fallback)

  - [x] 3.1 Implementar o fix
    - Adicionar método `get_odd_alerta(bet_id: int) -> float` em `src/bot/bets_tracker.py` que consulta `odd_alerta` da tabela `bets_placed` e retorna 0.0 se não encontrado
    - Em `src/bot/bot_listener.py` (~linha 3225), calcular `odd_exibir = odd_apostada if odd_apostada else bets_tracker.get_odd_alerta(bet_id_aposta)`
    - Usar `odd_exibir` na montagem de `confirmacao`: `f"💰 R$ {valor:.2f} @ {odd_exibir:.2f}"`
    - Usar `odd_exibir` na montagem de `texto_confirmacao`: `f"✅ Aposta registrada — R$ {valor:.2f} @ {odd_exibir:.2f}"`
    - Remover o bloco condicional `if odd_apostada: ... else: ...` — sempre exibir a odd
    - _Bug_Condition: isBugCondition(input) onde input.odd_apostada IS NULL_
    - _Expected_Behavior: mensagens SEMPRE contêm f"@ {odd_exibir:.2f}" (expectedBehavior do design)_
    - _Preservation: quando odd_apostada é fornecida, odd_exibir = odd_apostada (Preservation Requirements do design)_
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1, 3.2_

  - [x] 3.2 Verificar que teste exploratório agora passa
    - **Property 1: Expected Behavior** - Confirmação sempre exibe odd via fallback
    - **IMPORTANT**: Re-executar o MESMO teste da tarefa 1 — NÃO escrever um novo teste
    - O teste da tarefa 1 codifica o comportamento esperado
    - Quando este teste passa, confirma que o comportamento esperado é satisfeito
    - Executar teste exploratório da tarefa 1
    - **EXPECTED OUTCOME**: Teste PASSA (confirma que o bug foi corrigido)
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verificar que testes de preservação ainda passam
    - **Property 2: Preservation** - Comportamento inalterado quando odd é fornecida
    - **IMPORTANT**: Re-executar os MESMOS testes da tarefa 2 — NÃO escrever novos testes
    - Executar testes de preservação da tarefa 2
    - **EXPECTED OUTCOME**: Testes PASSAM (confirma que não há regressões)
    - Confirmar que todos os testes ainda passam após o fix (sem regressões)

- [x] 4. Checkpoint - Garantir que todos os testes passam
  - Executar suite completa de testes
  - Garantir que todos os testes passam, perguntar ao usuário se surgirem dúvidas
