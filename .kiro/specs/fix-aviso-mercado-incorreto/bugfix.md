# Documento de Requisitos do Bugfix

## Introdução

O aviso de "jogo duplicado" (`_montar_aviso_mesmo_jogo`) exibe o nome do mercado incorreto/cru porque chama `formatar_market_name()` com dados insuficientes. A função `formatar_market_name` precisa de campos auxiliares (hdp, total, bet_side completo, dados do evento) que não estão disponíveis no dict retornado por `buscar_alertas_mesmo_jogo()`. A correção consiste em salvar o nome do mercado já formatado no momento do registro do alerta e reutilizá-lo no aviso de duplicata.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `_montar_aviso_mesmo_jogo()` é chamado com alertas retornados por `buscar_alertas_mesmo_jogo()` THEN o sistema chama `formatar_market_name(a.get('market_type', ''), aposta=a)` com um dict que não contém os campos auxiliares necessários (hdp, total, market.name, betSide, event.sport, event.home, event.away), resultando em um nome de mercado incorreto ou genérico (ex: "Totals" ao invés de "Mais de 2.5 Gols")

1.2 WHEN o mercado é do tipo handicap, totals ou player props THEN o sistema exibe apenas o nome cru do mercado (ex: "Handicap", "Totals") sem o valor da linha e sem a tradução correta, pois `get_hdp(evento)` retorna 0 e `bet_side` está incompleto no dict de `buscar_alertas_mesmo_jogo`

### Expected Behavior (Correct)

2.1 WHEN `_montar_aviso_mesmo_jogo()` é chamado com alertas retornados por `buscar_alertas_mesmo_jogo()` THEN o sistema SHALL exibir o mesmo nome de mercado formatado que foi mostrado na mensagem original do alerta (ex: "Mais de 2.5 Gols", "Handicap — Time A +1.5")

2.2 WHEN o mercado é do tipo handicap, totals ou player props THEN o sistema SHALL exibir o nome completo com valor da linha e tradução correta, idêntico ao que apareceu no alerta original, utilizando o valor pré-formatado salvo na coluna `market_name_fmt` da tabela `bets_placed`

### Unchanged Behavior (Regression Prevention)

3.1 WHEN um alerta é enviado pela primeira vez (sem alertas anteriores do mesmo jogo) THEN o sistema SHALL CONTINUE TO formatar o nome do mercado normalmente via `formatar_market_name()` e exibir a mensagem completa com mercado correto

3.2 WHEN `buscar_alertas_mesmo_jogo()` retorna uma lista vazia THEN o sistema SHALL CONTINUE TO retornar string vazia como aviso e não exibir bloco de aviso na mensagem

3.3 WHEN o campo `market_name_fmt` for NULL (registros antigos anteriores à migração) THEN o sistema SHALL CONTINUE TO usar `market_type` como fallback para exibição do nome do mercado no aviso

3.4 WHEN o usuário interage com os botões de tracking (Apostei/Pulei/resultado) THEN o sistema SHALL CONTINUE TO funcionar normalmente sem ser afetado pela nova coluna

---

## Bug Condition (Pseudocódigo Estruturado)

### Função de Condição do Bug

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type AlertaAnterior (dict retornado por buscar_alertas_mesmo_jogo)
  OUTPUT: boolean

  // O bug ocorre quando o dict do alerta anterior não possui os campos
  // auxiliares necessários para formatar_market_name produzir saída correta
  RETURN X.market_name_fmt IS NULL
     AND (X.market_type contém "handicap" OR "totals" OR "player props" OR qualquer mercado que precise de hdp/total/bet_side completo)
END FUNCTION
```

### Property: Fix Checking

```pascal
// Para todos os alertas onde o nome formatado foi salvo, o aviso deve usá-lo
FOR ALL X WHERE X.market_name_fmt IS NOT NULL DO
  resultado ← _montar_aviso_mesmo_jogo'([X])
  ASSERT resultado contém X.market_name_fmt
END FOR
```

### Property: Preservation Checking

```pascal
// Para alertas sem market_name_fmt (registros antigos), fallback para market_type
FOR ALL X WHERE X.market_name_fmt IS NULL DO
  resultado ← _montar_aviso_mesmo_jogo'([X])
  ASSERT resultado contém X.market_type
END FOR

// Para alertas novos, o envio continua funcionando normalmente
FOR ALL aposta WHERE enviar_alerta é chamado DO
  ASSERT F(aposta) = F'(aposta)  // mensagem principal idêntica
  ASSERT bets_placed.market_name_fmt é salvo com valor correto
END FOR
```
