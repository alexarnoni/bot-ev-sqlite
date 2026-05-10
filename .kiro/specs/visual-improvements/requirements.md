# Requirements Document

## Introdução

Melhorias visuais nas mensagens do bot Telegram de apostas esportivas com EV+. O objetivo é tornar as mensagens de confirmação, lembrete pós-jogo e histórico mais informativas e legíveis, incluindo exibição da odd apostada na confirmação, cálculo de EV real quando a odd apostada difere da odd do alerta, e separadores visuais no histórico.

## Glossário

- **Bot_Listener**: Módulo principal do bot Telegram responsável por processar comandos e interações do usuário (`src/bot/bot_listener.py`)
- **Mensagem_Confirmação**: Mensagem enviada ao usuário após registrar uma aposta com sucesso
- **Lembrete_Pós_Jogo**: Mensagem formatada pela função `_formatar_lembrete()` que solicita ao usuário o resultado de uma aposta pendente
- **Histórico**: Listagem de apostas finalizadas exibida pelo comando `/historico`
- **Odd_Apostada**: Odd efetivamente utilizada pelo usuário ao registrar a aposta
- **Odd_Alerta**: Odd original do alerta enviado pelo scanner
- **EV_Alerta**: Expected Value calculado no momento do alerta
- **EV_Real**: Expected Value recalculado com base na odd efetivamente apostada
- **Prob_Implícita**: Probabilidade implícita derivada da odd do alerta e do EV do alerta, calculada como `1 / (odd_alerta / (1 + ev_alerta))`
- **Bloco_EV**: Bloco de texto opcional exibido no lembrete pós-jogo comparando odds e EVs

## Requisitos

### Requisito 1: Mensagem de confirmação com odd apostada

**User Story:** Como apostador, quero ver a odd apostada na mensagem de confirmação, para ter certeza de que o registro ficou correto.

#### Critérios de Aceitação

1. WHEN uma aposta é registrada com sucesso, THE Bot_Listener SHALL exibir a mensagem de confirmação no formato `"✅ Aposta registrada — R$ {valor:.2f} @ {odd_apostada:.2f}"` quando a odd apostada estiver disponível
2. WHEN uma aposta é registrada sem odd apostada, THE Bot_Listener SHALL exibir a mensagem de confirmação no formato `"✅ Aposta registrada — R$ {valor:.2f}"` omitindo o trecho da odd
3. THE Bot_Listener SHALL enviar a mensagem de confirmação com parse_mode HTML

### Requisito 2: Bloco comparativo de EV no lembrete pós-jogo

**User Story:** Como apostador, quero ver a comparação entre a odd do alerta e a odd que efetivamente apostei no lembrete pós-jogo, para entender o impacto no EV real da aposta.

#### Critérios de Aceitação

1. WHEN odd_apostada difere de odd_alerta E odd_alerta é maior que zero E (1 + ev_alerta) é maior que zero, THE Lembrete_Pós_Jogo SHALL exibir o Bloco_EV contendo a linha `"📊 Odd alerta: {odd_alerta:.2f} → Odd apostada: {odd_apostada:.2f}"` e a linha `"📈 EV original: {ev_alerta*100:.1f}% → EV real: {ev_real*100:.1f}%"`
2. THE Lembrete_Pós_Jogo SHALL calcular prob_implícita como `1 / (odd_alerta / (1 + ev_alerta))` e ev_real como `(odd_apostada * prob_implícita) - 1`
3. THE Lembrete_Pós_Jogo SHALL posicionar o Bloco_EV após os dados da aposta e antes da pergunta "Qual foi o resultado?"
4. WHEN odd_apostada é igual a odd_alerta OU odd_apostada é None, THE Lembrete_Pós_Jogo SHALL omitir o Bloco_EV completamente
5. WHEN odd_alerta é zero OU (1 + ev_alerta) é zero ou negativo, THE Lembrete_Pós_Jogo SHALL omitir o Bloco_EV completamente

### Requisito 3: Separadores visuais no histórico de apostas

**User Story:** Como apostador, quero ver separadores visuais entre cada aposta no histórico, para facilitar a leitura e distinguir uma aposta da outra.

#### Critérios de Aceitação

1. THE Histórico SHALL exibir cada aposta no formato: emoji + times na primeira linha, dados (mercado, odd, valor, lucro) na segunda linha, seguido de um separador `"─────────────────"` e uma linha em branco
2. THE Histórico SHALL manter o cabeçalho com título e período antes da listagem de apostas
3. THE Histórico SHALL enviar a mensagem com parse_mode HTML
