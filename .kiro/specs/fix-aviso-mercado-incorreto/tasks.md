# Plano de Implementação

- [x] 1. Escrever teste exploratório da condição do bug
  - **Property 1: Bug Condition** - Nome do Mercado Incorreto no Aviso de Duplicata
  - **CRITICAL**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **NÃO tente corrigir o teste ou o código quando ele falhar**
  - **NOTE**: Este teste codifica o comportamento esperado — ele validará a correção quando passar após a implementação
  - **GOAL**: Demonstrar contraexemplos que evidenciam que `_montar_aviso_mesmo_jogo` exibe nomes de mercado incorretos
  - **Scoped PBT Approach**: Escopo da propriedade para casos concretos de falha: mercados do tipo totals/handicap com valores de hdp/total que deveriam aparecer formatados no aviso
  - Criar teste em `tests/test_bug_aviso_mercado.py` usando Hypothesis
  - Simular o fluxo: registrar alerta com mercado complexo (totals com hdp=2.5, handicap com hdp=1.5) → chamar `buscar_alertas_mesmo_jogo()` → chamar `_montar_aviso_mesmo_jogo()` com os alertas retornados
  - Condição do bug (de isBugCondition no design): `input.market_name_fmt IS NULL AND montar_nome_mercado(input) produz saída incorreta`
  - Assertar que o aviso contém o nome formatado correto (ex: "Mais de 2.5 Gols" ao invés de "Totals")
  - Executar teste no código NÃO corrigido
  - **RESULTADO ESPERADO**: Teste FALHA (isto é correto — prova que o bug existe)
  - Documentar contraexemplos encontrados (ex: `formatar_market_name("totals", aposta=dict_sem_hdp)` retorna "Totals" ao invés de "Mais de 2.5 Gols")
  - Marcar tarefa como completa quando o teste estiver escrito, executado e a falha documentada
  - _Requirements: 1.1, 1.2_

- [x] 2. Escrever testes de preservação (ANTES de implementar a correção)
  - **Property 2: Preservation** - Fallback para Registros Antigos e Comportamento Geral
  - **IMPORTANT**: Seguir metodologia observation-first
  - Observar: `_montar_aviso_mesmo_jogo([])` retorna `""` no código não corrigido
  - Observar: `_montar_aviso_mesmo_jogo([{"market_type": "h2h", ...}])` retorna string contendo "h2h" ou nome formatado no código não corrigido
  - Observar: alertas sem `market_name_fmt` (registros antigos) usam `market_type` como fallback
  - Criar teste property-based em `tests/test_preservacao_aviso_mercado.py` usando Hypothesis
  - Gerar dicts de alertas anteriores com `market_name_fmt = None` e valores aleatórios de `market_type` — verificar que o resultado contém `market_type` como fallback
  - Gerar listas vazias — verificar que retorna string vazia
  - Verificar que o fluxo de `registrar_alerta` continua funcionando normalmente para todos os tipos de mercado
  - Executar testes no código NÃO corrigido
  - **RESULTADO ESPERADO**: Testes PASSAM (confirma comportamento baseline a preservar)
  - Marcar tarefa como completa quando testes estiverem escritos, executados e passando no código não corrigido
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 3. Correção do bug — Aviso de Mercado Incorreto

  - [x] 3.1 Implementar a correção
    - Adicionar migration em `src/core/database.py` na função `_init_db()`: `ALTER TABLE bets_placed ADD COLUMN market_name_fmt TEXT DEFAULT NULL` (após as migrations existentes de `odd_apostada`)
    - Em `src/bot/bot_ev.py`, nas funções `enviar_alerta()` e `enviar_alerta_instantaneo()`: calcular `mercado_fmt = formatar_market_name(market_type, aposta=aposta)` antes de `registrar_alerta()`, e após obter `bet_id`, executar UPDATE para salvar `market_name_fmt` na tabela `bets_placed`
    - Em `src/bot/bets_tracker.py`, na função `buscar_alertas_mesmo_jogo()`: adicionar `market_name_fmt` ao SELECT
    - Em `src/bot/bot_ev.py`, na função `_montar_aviso_mesmo_jogo()`: substituir `formatar_market_name(a.get('market_type', ''), aposta=a)` por `a.get('market_name_fmt') or a.get('market_type', '')`
    - _Bug_Condition: isBugCondition(input) where input.market_name_fmt IS NULL AND montar_nome_mercado(input) produz saída incorreta_
    - _Expected_Behavior: Para alertas com market_name_fmt NOT NULL, usar market_name_fmt diretamente no aviso_
    - _Preservation: Para alertas com market_name_fmt NULL (registros antigos), usar market_type como fallback; fluxo de envio de alertas, botões de tracking e consultas inalterados_
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 3.4_

  - [x] 3.2 Verificar que o teste exploratório da condição do bug agora passa
    - **Property 1: Expected Behavior** - Nome do Mercado Pré-Formatado é Usado no Aviso
    - **IMPORTANT**: Re-executar o MESMO teste da tarefa 1 — NÃO escrever um novo teste
    - O teste da tarefa 1 codifica o comportamento esperado
    - Quando este teste passar, confirma que o comportamento esperado é satisfeito
    - Executar teste exploratório da condição do bug da tarefa 1
    - **RESULTADO ESPERADO**: Teste PASSA (confirma que o bug foi corrigido)
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verificar que os testes de preservação ainda passam
    - **Property 2: Preservation** - Fallback para Registros Antigos e Comportamento Geral
    - **IMPORTANT**: Re-executar os MESMOS testes da tarefa 2 — NÃO escrever novos testes
    - Executar testes de preservação da tarefa 2
    - **RESULTADO ESPERADO**: Testes PASSAM (confirma que não há regressões)
    - Confirmar que todos os testes ainda passam após a correção (sem regressões)

- [x] 4. Checkpoint — Garantir que todos os testes passam
  - Executar suite completa de testes
  - Garantir que todos os testes passam, perguntar ao usuário se surgirem dúvidas
