# Bugfix: Confirmação Sempre Exibir Odd (Alerta como Fallback)

## Overview

Ao registrar uma aposta no fluxo `bet_text_handler`, quando o usuário informa apenas o valor (sem a odd), as mensagens de confirmação omitem a odd. O fix consiste em buscar `odd_alerta` do banco de dados como fallback quando `odd_apostada` não é fornecida, garantindo que a odd seja SEMPRE exibida nas mensagens de confirmação e na edição do alerta original.

A correção é localizada em dois arquivos: adicionar um método de consulta em `BetsTracker` e ajustar a lógica de montagem de texto em `bet_text_handler`.

## Glossário

- **Bug_Condition (C)**: A condição que dispara o bug — quando o usuário registra uma aposta sem informar a odd (`odd_apostada` é `None`)
- **Property (P)**: O comportamento desejado — mensagens de confirmação SEMPRE exibem a odd (usando `odd_alerta` como fallback)
- **Preservation**: Comportamento existente que deve permanecer inalterado — quando o usuário fornece a odd, ela continua sendo usada; mensagens de erro para formato inválido continuam funcionando
- **`bet_text_handler`**: Handler em `src/bot/bot_listener.py` que captura valor/odd do usuário e monta as mensagens de confirmação
- **`BetsTracker`**: Classe em `src/bot/bets_tracker.py` que gerencia persistência e consultas de apostas
- **`odd_alerta`**: Odd original do alerta armazenada no banco na coluna `bets_placed.odd_alerta`
- **`odd_apostada`**: Odd informada pelo usuário no momento do registro (pode ser `None`)
- **`bet_id_aposta`**: ID do registro da aposta no banco, obtido de `context.user_data['esperando_valor_aposta']`

## Bug Details

### Bug Condition

O bug se manifesta quando o usuário registra uma aposta informando apenas o valor (ex: "50"), sem incluir a odd. O `bet_text_handler` monta as mensagens de confirmação condicionalmente — se `odd_apostada` é `None`, simplesmente omite a odd do texto, em vez de buscar `odd_alerta` do banco como fallback.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type BetRegistration {valor: float, odd_apostada: float | None, bet_id: int}
  OUTPUT: boolean

  RETURN input.odd_apostada IS NULL
         AND input.bet_id EXISTS in bets_placed
         AND bets_placed[input.bet_id].odd_alerta > 0
END FUNCTION
```

### Exemplos

- **Exemplo 1**: Usuário envia "50" → Sistema exibe "✅ Aposta registrada — R$ 50.00" (sem odd). Esperado: "✅ Aposta registrada — R$ 50.00 @ 1.85" (usando odd_alerta=1.85 do banco)
- **Exemplo 2**: Usuário envia "100" → Mensagem editada exibe "💰 R$ 100.00" (sem odd). Esperado: "💰 R$ 100.00 @ 2.10" (usando odd_alerta=2.10 do banco)
- **Exemplo 3**: Usuário envia "50 1.47" → Sistema exibe "✅ Aposta registrada — R$ 50.00 @ 1.47" (correto, usa odd fornecida)
- **Caso limite**: Usuário envia "50" mas `odd_alerta` no banco é 0.0 → Sistema deve exibir "✅ Aposta registrada — R$ 50.00 @ 0.00" (fallback para 0.0)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Quando o usuário fornece valor E odd (ex: "50 1.47"), a odd fornecida continua sendo usada nas mensagens de confirmação
- Mensagens de erro para formato inválido ("❌ Formato inválido...") continuam funcionando normalmente
- O fluxo de cashout (`esperando_valor_cashout`) permanece inalterado
- A chamada a `bets_tracker.marcar_apostou()` continua recebendo os mesmos parâmetros
- A edição da mensagem original (remoção do "⏳ Valor apostado e odd...") continua funcionando

**Scope:**
Todas as entradas que NÃO envolvem a condição do bug (odd_apostada é None) devem ser completamente não afetadas pelo fix. Isso inclui:
- Registros de aposta com odd fornecida pelo usuário
- Entradas com formato inválido
- Fluxo de cashout
- Qualquer outro handler de texto

## Hypothesized Root Cause

Com base na análise do código, a causa raiz é clara e direta:

1. **Lógica condicional incompleta no `bet_text_handler`**: O código atual usa `if odd_apostada:` para decidir se inclui a odd nas mensagens. Quando `odd_apostada` é `None` (usuário não forneceu), o código simplesmente omite a odd em vez de buscar `odd_alerta` do banco.

2. **Ausência de método de consulta de `odd_alerta`**: A classe `BetsTracker` não possui um método dedicado para consultar apenas `odd_alerta` dado um `bet_id`. Embora `marcar_apostou` internamente faça essa consulta como fallback para gravar no banco, o valor não é retornado ao caller.

3. **Variável `bet_id_aposta` disponível no escopo**: O `bet_id_aposta` (obtido de `context.user_data.get('esperando_valor_aposta')`) está disponível no escopo onde as mensagens são montadas, permitindo a consulta ao banco.

## Correctness Properties

Property 1: Bug Condition - Confirmação sempre exibe odd via fallback

_For any_ input onde a condição do bug é verdadeira (odd_apostada é None e existe odd_alerta > 0 no banco), a função corrigida SHALL exibir a odd_alerta nas mensagens de confirmação ("✅ Aposta registrada — R$ X.XX @ Y.YY") e na mensagem editada ("💰 R$ X.XX @ Y.YY").

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - Comportamento inalterado quando odd é fornecida

_For any_ input onde a condição do bug NÃO é verdadeira (odd_apostada é fornecida pelo usuário), a função corrigida SHALL produzir exatamente o mesmo resultado que a função original, preservando o uso da odd fornecida pelo usuário nas mensagens de confirmação.

**Validates: Requirements 3.1, 3.2, 3.3**

## Fix Implementation

### Changes Required

Assumindo que a análise de causa raiz está correta:

**Arquivo**: `src/bot/bets_tracker.py`

**Classe**: `BetsTracker`

**Mudança 1 — Adicionar método `get_odd_alerta`**:
1. **Novo método de consulta**: Adicionar `get_odd_alerta(bet_id: int) -> float` que consulta `odd_alerta` da tabela `bets_placed` para o `bet_id` fornecido
   - Retorna `odd_alerta` se o registro existir
   - Retorna `0.0` se o registro não for encontrado

---

**Arquivo**: `src/bot/bot_listener.py`

**Função**: `bet_text_handler`

**Mudança 2 — Fallback para odd na mensagem editada** (~linha 3225):
1. **Substituir** a montagem condicional de `confirmacao`:
   - De: `confirmacao = f"💰 R$ {valor:.2f} @ {odd_apostada}" if odd_apostada else f"💰 R$ {valor:.2f}"`
   - Para: calcular `odd_exibir = odd_apostada if odd_apostada else bets_tracker.get_odd_alerta(bet_id_aposta)` e usar `confirmacao = f"💰 R$ {valor:.2f} @ {odd_exibir:.2f}"`

**Mudança 3 — Fallback para odd na mensagem de confirmação** (~linha 3240):
1. **Substituir** o bloco condicional `if odd_apostada: ... else: ...`:
   - De: bloco if/else que omite odd quando `odd_apostada` é falsy
   - Para: usar `odd_exibir` (já calculado acima) e sempre exibir `texto_confirmacao = f"✅ Aposta registrada — R$ {valor:.2f} @ {odd_exibir:.2f}"`

**Mudança 4 — Reutilizar variável `odd_exibir`**:
1. A variável `odd_exibir` deve ser calculada UMA vez antes da montagem de `confirmacao`, e reutilizada em ambas as mensagens

**Mudança 5 — Garantir `bets_tracker` acessível**:
1. Verificar que `bets_tracker` (instância global) está acessível no escopo de `bet_text_handler` (já é — usado na linha `bets_tracker.marcar_apostou(...)`)

## Testing Strategy

### Validation Approach

A estratégia de testes segue uma abordagem em duas fases: primeiro, demonstrar o bug no código não corrigido com contraexemplos, depois verificar que o fix funciona corretamente e preserva o comportamento existente.

### Exploratory Bug Condition Checking

**Goal**: Demonstrar contraexemplos que evidenciam o bug ANTES de implementar o fix. Confirmar ou refutar a análise de causa raiz.

**Test Plan**: Escrever testes que simulam o fluxo de `bet_text_handler` com `odd_apostada=None` e verificam que as mensagens de confirmação contêm a odd. Executar no código NÃO corrigido para observar falhas.

**Test Cases**:
1. **Registro sem odd**: Simular envio de "50" quando `odd_alerta=1.85` no banco (vai falhar no código não corrigido)
2. **Mensagem editada sem odd**: Verificar que a mensagem editada contém "@ 1.85" (vai falhar no código não corrigido)
3. **Odd zero no banco**: Simular envio de "50" quando `odd_alerta=0.0` no banco (vai falhar no código não corrigido)

**Expected Counterexamples**:
- Mensagem de confirmação não contém "@ " seguido de odd formatada
- Mensagem editada não contém "@ " seguido de odd formatada
- Causa: lógica condicional `if odd_apostada:` omite odd quando é None

### Fix Checking

**Goal**: Verificar que para todas as entradas onde a condição do bug é verdadeira, a função corrigida produz o comportamento esperado.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  odd_alerta := bets_tracker.get_odd_alerta(input.bet_id)
  result := bet_text_handler_fixed(input)
  ASSERT result.texto_confirmacao CONTAINS f"@ {odd_alerta:.2f}"
  ASSERT result.mensagem_editada CONTAINS f"@ {odd_alerta:.2f}"
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todas as entradas onde a condição do bug NÃO é verdadeira, a função corrigida produz o mesmo resultado que a função original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT bet_text_handler_original(input) = bet_text_handler_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing é recomendado para preservation checking porque:
- Gera muitos casos de teste automaticamente no domínio de entrada
- Captura edge cases que testes manuais podem perder
- Fornece garantias fortes de que o comportamento é inalterado para entradas não-buggy

**Test Plan**: Observar comportamento no código NÃO corrigido para registros com odd fornecida, depois escrever testes property-based capturando esse comportamento.

**Test Cases**:
1. **Preservação com odd fornecida**: Verificar que "50 1.47" continua gerando "✅ Aposta registrada — R$ 50.00 @ 1.47"
2. **Preservação de formato inválido**: Verificar que "abc" continua gerando mensagem de erro
3. **Preservação do fluxo de cashout**: Verificar que o fluxo de cashout não é afetado

### Unit Tests

- Testar `BetsTracker.get_odd_alerta()` com bet_id existente
- Testar `BetsTracker.get_odd_alerta()` com bet_id inexistente (retorna 0.0)
- Testar montagem de `odd_exibir` quando `odd_apostada` é None
- Testar montagem de `odd_exibir` quando `odd_apostada` é fornecida

### Property-Based Tests

- Gerar valores aleatórios de `odd_apostada` (None ou float > 0) e `odd_alerta` (float >= 0) e verificar que a mensagem sempre contém uma odd formatada
- Gerar configurações aleatórias de aposta com odd fornecida e verificar preservação do comportamento original
- Testar que para qualquer combinação de valor/odd, o formato "@ X.XX" está presente na saída

### Integration Tests

- Testar fluxo completo: registrar alerta → solicitar aposta → enviar apenas valor → verificar mensagens
- Testar fluxo completo: registrar alerta → solicitar aposta → enviar valor e odd → verificar mensagens
- Testar que `marcar_apostou` é chamado corretamente independente do fallback de odd na exibição
