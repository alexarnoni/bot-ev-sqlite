# Bugfix Design — Aviso de Mercado Incorreto

## Overview

O aviso de "jogo duplicado" (`_montar_aviso_mesmo_jogo`) exibe nomes de mercado incorretos/crus (ex: "Totals" ao invés de "Mais de 2.5 Gols") porque `formatar_market_name()` depende de campos auxiliares (`market.hdp`, `betSide`, `event.sport`, `event.home`, `event.away`) que não existem no dict retornado por `buscar_alertas_mesmo_jogo()`.

A correção adota a estratégia de **pré-formatação**: salvar o nome do mercado já formatado (`mercado_fmt`) no banco de dados no momento do envio do alerta, e reutilizá-lo diretamente no aviso de duplicata, eliminando a necessidade de recalcular a formatação com dados incompletos.

## Glossário

- **Bug_Condition (C)**: A condição que dispara o bug — `_montar_aviso_mesmo_jogo` chama `formatar_market_name()` com um dict que não possui os campos auxiliares necessários para formatação correta
- **Property (P)**: O comportamento desejado — o aviso de duplicata deve exibir o mesmo nome de mercado formatado que apareceu na mensagem original do alerta
- **Preservation**: O envio de alertas novos, a formatação da mensagem principal, os botões de tracking e o comportamento de `buscar_alertas_mesmo_jogo` para registros antigos devem permanecer inalterados
- **`formatar_market_name()`**: Função em `src/utils/formatadores.py` que traduz e formata o nome do mercado usando campos auxiliares do evento (hdp, total, betSide, sport, home, away)
- **`montar_nome_mercado()`**: Função interna chamada por `formatar_market_name()` que executa a lógica de formatação completa
- **`buscar_alertas_mesmo_jogo()`**: Método em `src/bot/bets_tracker.py` que retorna alertas anteriores do mesmo jogo (match por chat_id + home + away + commence_time)
- **`_montar_aviso_mesmo_jogo()`**: Método em `src/bot/bot_ev.py` que monta o bloco de aviso "⚠️ Já foi enviado alerta deste jogo" usando os alertas retornados
- **`market_name_fmt`**: Nova coluna TEXT na tabela `bets_placed` que armazena o nome do mercado pré-formatado

## Bug Details

### Bug Condition

O bug manifesta-se quando `_montar_aviso_mesmo_jogo()` recebe alertas anteriores de `buscar_alertas_mesmo_jogo()` e tenta formatar o nome do mercado chamando `formatar_market_name(a.get('market_type', ''), aposta=a)`. O dict `a` contém apenas as colunas do SELECT (`id, market_type, bet_side, odd_alerta, odd_apostada, ev_alerta, status, valor_apostado, timestamp_alerta`), sem os campos auxiliares que `montar_nome_mercado()` precisa (`market.hdp`, `market.name`, `betSide`, `event.sport`, `event.home`, `event.away`).

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type AlertaAnterior (dict retornado por buscar_alertas_mesmo_jogo)
  OUTPUT: boolean

  RETURN input.market_name_fmt IS NULL
     AND montar_nome_mercado(input) produz saída incorreta
         (porque input NÃO contém: market.hdp, market.name, betSide,
          event.sport, event.home, event.away)
END FUNCTION
```

### Examples

- **Totals/Over-Under**: Mercado original "Mais de 2.5 Gols" → aviso exibe "Totals" (porque `get_hdp(a)` retorna 0 e `bet_side` não está no formato esperado)
- **Handicap**: Mercado original "Handicap — Flamengo +1.5" → aviso exibe "Handicap" (porque `get_hdp(a)` retorna 0 e `home`/`away` não estão no dict)
- **Player Props**: Mercado original "LeBron James - Mais de 25.5 Pontos" → aviso exibe "Player Props" (porque nenhum campo auxiliar está disponível)
- **Moneyline**: Mercado original "Moneyline (Flamengo)" → aviso exibe "Moneyline" (porque `home`/`away` não estão no dict para traduzir o lado)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- O envio de alertas novos (primeira vez, sem duplicatas) deve continuar formatando o mercado normalmente via `formatar_market_name()`
- A mensagem principal do alerta (template normal e destacado) deve permanecer idêntica
- Os botões de tracking (Apostei/Pulei) e todo o fluxo de `BetsTracker` devem funcionar sem alteração
- `buscar_alertas_mesmo_jogo()` deve continuar retornando registros antigos (anteriores à migração) normalmente
- Quando `market_name_fmt` for NULL (registros antigos), o sistema deve usar `market_type` como fallback

**Scope:**
Todos os inputs que NÃO envolvem a exibição do nome do mercado no aviso de duplicata devem ser completamente não afetados pela correção. Isso inclui:
- Envio de alertas sem alertas anteriores do mesmo jogo
- Interação com botões de tracking
- Consultas de resumo, histórico e pendentes
- Lembretes e expiração de alertas

## Hypothesized Root Cause

Based na análise do código, a causa raiz é:

1. **SELECT insuficiente em `buscar_alertas_mesmo_jogo()`**: O método seleciona apenas `id, market_type, bet_side, odd_alerta, odd_apostada, ev_alerta, status, valor_apostado, timestamp_alerta` — não inclui campos como `home`, `away`, `sport`, nem dados de handicap/total que `montar_nome_mercado()` precisa.

2. **Dados não disponíveis na tabela `bets_placed`**: Mesmo que o SELECT fosse expandido, a tabela `bets_placed` não armazena `hdp`, `total`, `market.name` (nome raw do mercado da API), nem o `betSide` no formato original da API. Esses dados existem apenas no dict `aposta`/`evento` no momento do envio.

3. **Arquitetura de formatação tardia**: `_montar_aviso_mesmo_jogo()` tenta reformatar o mercado a partir de dados mínimos, quando a formatação correta só é possível no momento do envio original, onde todos os campos auxiliares estão disponíveis.

4. **Solução correta**: Salvar o resultado de `formatar_market_name()` (que já é calculado em `_formatar_alerta_normal` e `_formatar_alerta_destacado` como `mercado_fmt`) na tabela `bets_placed` no momento do registro, e reutilizá-lo diretamente no aviso.

## Correctness Properties

Property 1: Bug Condition - Nome do Mercado Pré-Formatado é Usado no Aviso

_For any_ alerta anterior onde `market_name_fmt` IS NOT NULL (registros novos após a migração), a função `_montar_aviso_mesmo_jogo` corrigida SHALL usar o valor de `market_name_fmt` diretamente na linha do aviso, sem chamar `formatar_market_name()`.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - Fallback para Registros Antigos e Comportamento Geral

_For any_ alerta anterior onde `market_name_fmt` IS NULL (registros antigos anteriores à migração), a função `_montar_aviso_mesmo_jogo` corrigida SHALL usar `market_type` como fallback, e para todos os outros fluxos (envio de alertas, botões de tracking, consultas), o sistema SHALL produzir exatamente o mesmo resultado que o código original.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

Assumindo que a análise de causa raiz está correta:

**File**: `src/core/database.py`

**Function**: `_init_db()`

**Specific Changes**:
1. **Migration para nova coluna**: Adicionar `ALTER TABLE bets_placed ADD COLUMN market_name_fmt TEXT DEFAULT NULL` no bloco de migrations incrementais (após as migrations existentes de `commence_time_ajustado`, `tentativas_lembrete`, `odd_apostada`)

---

**File**: `src/bot/bot_ev.py`

**Function**: `enviar_alerta()` e `enviar_alerta_instantaneo()`

**Specific Changes**:
2. **Salvar `mercado_fmt` após `registrar_alerta()`**: Após obter `bet_id` de `registrar_alerta()`, executar UPDATE na tabela `bets_placed` para salvar o valor de `mercado_fmt` (que já é calculado dentro de `_formatar_alerta_normal`/`_formatar_alerta_destacado`) na coluna `market_name_fmt`. O `mercado_fmt` deve ser calculado ANTES do registro ou passado como parâmetro para ser salvo logo após.

   Implementação prática:
   - Calcular `mercado_fmt = formatar_market_name(market_type, aposta=aposta)` antes de chamar `registrar_alerta()`
   - Após obter `bet_id`, executar: `UPDATE bets_placed SET market_name_fmt = ? WHERE id = ?`

---

**File**: `src/bot/bets_tracker.py`

**Function**: `buscar_alertas_mesmo_jogo()`

**Specific Changes**:
3. **Adicionar `market_name_fmt` ao SELECT**: Incluir a coluna `market_name_fmt` na lista de colunas selecionadas para que o dict retornado contenha o nome pré-formatado.

   De:
   ```sql
   SELECT id, market_type, bet_side, odd_alerta, odd_apostada,
          ev_alerta, status, valor_apostado, timestamp_alerta
   ```
   Para:
   ```sql
   SELECT id, market_type, bet_side, odd_alerta, odd_apostada,
          ev_alerta, status, valor_apostado, timestamp_alerta, market_name_fmt
   ```

---

**File**: `src/bot/bot_ev.py`

**Function**: `_montar_aviso_mesmo_jogo()`

**Specific Changes**:
4. **Usar `market_name_fmt` com fallback**: Substituir a chamada `formatar_market_name(a.get('market_type', ''), aposta=a)` por `a.get('market_name_fmt') or a.get('market_type', '')`.

   De:
   ```python
   mercado = formatar_market_name(a.get('market_type', ''), aposta=a)
   ```
   Para:
   ```python
   mercado = a.get('market_name_fmt') or a.get('market_type', '')
   ```

5. **Remover import desnecessário**: O import de `formatar_market_name` dentro de `_montar_aviso_mesmo_jogo` pode ser removido (manter apenas `formatar_odd`).

## Testing Strategy

### Validation Approach

A estratégia de testes segue duas fases: primeiro, demonstrar o bug no código não corrigido com contraexemplos, depois verificar que a correção funciona e preserva o comportamento existente.

### Exploratory Bug Condition Checking

**Goal**: Demonstrar contraexemplos que evidenciam o bug ANTES de implementar a correção. Confirmar ou refutar a análise de causa raiz.

**Test Plan**: Criar testes que simulam o fluxo completo: registrar um alerta com mercado complexo (totals, handicap), depois chamar `buscar_alertas_mesmo_jogo()` e `_montar_aviso_mesmo_jogo()` para verificar que o nome do mercado exibido é incorreto.

**Test Cases**:
1. **Totals Test**: Registrar alerta com `market_type="totals"` e `hdp=2.5`, chamar `_montar_aviso_mesmo_jogo` — esperado falhar mostrando "Totals" ao invés de "Mais de 2.5 Gols"
2. **Handicap Test**: Registrar alerta com `market_type="spreads"` e `hdp=1.5`, chamar `_montar_aviso_mesmo_jogo` — esperado falhar mostrando "Handicap" ao invés de "Handicap — Time +1.5"
3. **Player Props Test**: Registrar alerta com `market_type="player props - jogador (points)"`, chamar `_montar_aviso_mesmo_jogo` — esperado falhar mostrando "Player Props" genérico
4. **Moneyline Test**: Registrar alerta com `market_type="h2h"` e `bet_side="home"`, chamar `_montar_aviso_mesmo_jogo` — esperado falhar mostrando "Moneyline" sem o nome do time

**Expected Counterexamples**:
- `formatar_market_name` retorna nome genérico/cru porque `get_hdp(a)` retorna 0 e campos de time/esporte estão ausentes
- Causa confirmada: dict de `buscar_alertas_mesmo_jogo` não contém campos auxiliares necessários

### Fix Checking

**Goal**: Verificar que para todos os inputs onde a condição do bug se aplica, a função corrigida produz o comportamento esperado.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  // Simula envio de alerta com mercado complexo
  mercado_fmt := formatar_market_name(input.market_type, aposta=input.evento_completo)
  // Salva no banco
  salvar_market_name_fmt(bet_id, mercado_fmt)
  // Busca alertas anteriores
  alertas := buscar_alertas_mesmo_jogo(...)
  // Monta aviso
  aviso := _montar_aviso_mesmo_jogo'(alertas)
  ASSERT aviso contém mercado_fmt
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todos os inputs onde a condição do bug NÃO se aplica, a função corrigida produz o mesmo resultado que a função original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  // Registros antigos sem market_name_fmt
  ASSERT _montar_aviso_mesmo_jogo'([input]) contém input.market_type

  // Envio de alertas novos continua funcionando
  ASSERT enviar_alerta'(chat_id, aposta) produz mesma mensagem que enviar_alerta(chat_id, aposta)
END FOR
```

**Testing Approach**: Property-based testing é recomendado para preservation checking porque:
- Gera muitos casos de teste automaticamente cobrindo diferentes tipos de mercado
- Captura edge cases que testes manuais podem perder (mercados raros, valores extremos de hdp)
- Fornece garantias fortes de que o comportamento é preservado para todos os inputs não-buggy

**Test Plan**: Observar comportamento no código NÃO corrigido para cliques de mouse e outras interações, depois escrever testes property-based capturando esse comportamento.

**Test Cases**:
1. **Fallback Preservation**: Verificar que registros com `market_name_fmt = NULL` usam `market_type` como fallback
2. **Mensagem Principal Preservation**: Verificar que a mensagem principal do alerta (template normal/destacado) permanece idêntica após a correção
3. **Tracking Buttons Preservation**: Verificar que botões Apostei/Pulei continuam funcionando normalmente
4. **Empty List Preservation**: Verificar que `_montar_aviso_mesmo_jogo([])` continua retornando string vazia

### Unit Tests

- Testar que `_montar_aviso_mesmo_jogo` usa `market_name_fmt` quando disponível
- Testar que `_montar_aviso_mesmo_jogo` usa `market_type` como fallback quando `market_name_fmt` é None
- Testar que `buscar_alertas_mesmo_jogo` retorna `market_name_fmt` no dict
- Testar que a migration adiciona a coluna corretamente
- Testar que `enviar_alerta` salva `market_name_fmt` no banco após `registrar_alerta`

### Property-Based Tests

- Gerar mercados aleatórios (totals, handicap, moneyline, player props) com valores de hdp/total aleatórios e verificar que o nome formatado salvo é idêntico ao exibido no aviso
- Gerar registros antigos (sem `market_name_fmt`) e verificar que o fallback para `market_type` funciona para qualquer valor de `market_type`
- Gerar listas de alertas anteriores com mix de registros novos e antigos e verificar que cada linha do aviso usa a fonte correta

### Integration Tests

- Testar fluxo completo: enviar alerta → registrar no banco → enviar segundo alerta do mesmo jogo → verificar que aviso exibe mercado correto
- Testar com banco existente (registros antigos sem `market_name_fmt`) → enviar novo alerta → verificar que aviso funciona com mix de registros
- Testar que a migration é idempotente (executar `_init_db()` múltiplas vezes sem erro)
