# Documento de Requisitos do Bugfix

## Introdução

Ao registrar uma aposta no fluxo de confirmação (`bet_text_handler`), quando o usuário informa apenas o valor (sem a odd), a mensagem de confirmação exibe somente "✅ Aposta registrada — R$ X.XX", omitindo a odd. O comportamento correto é SEMPRE exibir a odd na confirmação — quando `odd_apostada` não é fornecida, o sistema deve usar `odd_alerta` do registro no banco de dados como fallback.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN o usuário registra uma aposta informando apenas o valor (sem odd) THEN o sistema exibe a confirmação "✅ Aposta registrada — R$ X.XX" sem nenhuma odd

1.2 WHEN o usuário registra uma aposta informando apenas o valor (sem odd) THEN a mensagem editada no alerta original exibe "💰 R$ X.XX" sem a odd

### Expected Behavior (Correct)

2.1 WHEN o usuário registra uma aposta informando apenas o valor (sem odd) THEN o sistema SHALL exibir a confirmação "✅ Aposta registrada — R$ X.XX @ Y.YY" usando `odd_alerta` do banco de dados como fallback

2.2 WHEN o usuário registra uma aposta informando apenas o valor (sem odd) THEN a mensagem editada no alerta original SHALL exibir "💰 R$ X.XX @ Y.YY" usando `odd_alerta` do banco de dados como fallback

### Unchanged Behavior (Regression Prevention)

3.1 WHEN o usuário registra uma aposta informando valor E odd (ex: "50 1.47") THEN o sistema SHALL CONTINUE TO exibir a confirmação "✅ Aposta registrada — R$ X.XX @ Z.ZZ" usando a odd fornecida pelo usuário

3.2 WHEN o usuário registra uma aposta informando valor E odd THEN a mensagem editada no alerta original SHALL CONTINUE TO exibir "💰 R$ X.XX @ Z.ZZ" usando a odd fornecida pelo usuário

3.3 WHEN o usuário envia um formato inválido de valor THEN o sistema SHALL CONTINUE TO exibir mensagem de erro "❌ Formato inválido..."

---

## Bug Condition (Derivação Formal)

### Função de Condição do Bug

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type BetRegistration (valor: float, odd_apostada: float | None, bet_id: int)
  OUTPUT: boolean

  // Retorna true quando o usuário não fornece odd na aposta
  RETURN X.odd_apostada IS NULL
END FUNCTION
```

### Propriedade: Fix Checking

```pascal
// Property: Fix Checking — Confirmação sempre exibe odd
FOR ALL X WHERE isBugCondition(X) DO
  odd_alerta ← buscar_odd_alerta(X.bet_id)
  resultado ← bet_text_handler'(X)
  ASSERT resultado.texto_confirmacao CONTAINS "@ " + format(odd_alerta, ".2f")
  ASSERT resultado.mensagem_editada CONTAINS "@ " + format(odd_alerta, ".2f")
END FOR
```

### Propriedade: Preservation Checking

```pascal
// Property: Preservation Checking — Comportamento inalterado para apostas com odd fornecida
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT bet_text_handler(X) = bet_text_handler'(X)
END FOR
```
