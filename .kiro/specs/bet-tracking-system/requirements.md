# Requirements Document

## Introduction

Adição de um sistema de tracking de apostas pessoais ao Bot EV+ existente. O bot já envia alertas de apostas com Valor Esperado positivo (EV+) via Telegram. Esta feature permite que cada usuário registre se apostou ou não em cada alerta recebido, informe o valor apostado, e depois do jogo registre o resultado. Todos os dados são persistidos em SQLite para geração de relatórios de ROI (Retorno sobre Investimento).

O sistema é composto por: (1) migração do banco de dados com nova tabela, (2) módulo de lógica de tracking sem dependência do Telegram, (3) modificações nos templates de alerta para incluir botões de ação, (4) novos handlers de callbacks e comandos no listener, e (5) novos jobs periódicos no scheduler.

## Glossary

- **Alert_Sender**: Componente em `bot_ev.py` responsável por formatar e enviar alertas via Telegram.
- **Bets_Tracker**: Novo módulo `bets_tracker.py` com toda a lógica de persistência e consulta de apostas rastreadas.
- **Bot_Listener**: Componente em `bot_listener.py` responsável por handlers de comandos e callbacks do Telegram.
- **Scheduler**: Componente em `main_scheduler.py` responsável por jobs periódicos.
- **Database**: Módulo `database.py` com a camada de acesso ao SQLite.
- **alert_hash**: String única que identifica um alerta específico, derivada dos dados do evento. Usado exclusivamente para evitar duplicatas na inserção (`UNIQUE`). Não é usado como parâmetro em operações de update ou query após a inserção.
- **bet_id**: Identificador inteiro primário (`id`) de uma aposta registrada na tabela `bets_placed`. É o identificador canônico para todas as operações de update, query e callbacks do Telegram.
- **status**: Estado atual de uma aposta rastreada. Valores possíveis: `pendente`, `ganhou`, `perdeu`, `empate`, `cashout`, `pulei`, `expirado`.
- **status final**: Qualquer status que encerra o ciclo de vida de uma aposta: `ganhou`, `perdeu`, `empate`, `cashout`, `pulei`, `expirado`.
- **ROI**: Return on Investment — lucro líquido dividido pelo total apostado, expresso em percentual.
- **EV**: Expected Value (Valor Esperado) — vantagem estatística de uma aposta sobre a casa.
- **THRESHOLD_EV_ALTO**: Constante configurável em `config.py` com valor padrão `0.08` (8%). Alertas com EV igual ou superior a este valor recebem template destacado.
- **commence_time**: Data e hora de início do evento esportivo original, em formato ISO 8601 UTC. Nunca é modificado após a inserção.
- **commence_time_ajustado**: Data e hora ajustada do evento após adiamento pelo usuário. Quando preenchido, tem precedência sobre `commence_time` nos cálculos de lembrete.
- **DURACAO_ESPORTE**: Dicionário em `bets_tracker.py` com a duração estimada em horas de cada esporte, usado para calcular quando o jogo terminou.
- **tentativas_lembrete**: Contador de tentativas consecutivas de envio de lembrete que falharam para uma aposta específica.

---

## Requirements

### Requirement 1: Migração do Banco de Dados

**User Story:** Como desenvolvedor, quero uma nova tabela `bets_placed` no SQLite, para que o sistema possa persistir todas as apostas rastreadas com seus metadados e resultados.

#### Acceptance Criteria

1. THE Database SHALL criar a tabela `bets_placed` com as colunas: `id` (INTEGER PRIMARY KEY AUTOINCREMENT), `alert_hash` (TEXT NOT NULL UNIQUE), `chat_id` (TEXT NOT NULL), `feed_id` (TEXT NOT NULL), `home` (TEXT), `away` (TEXT), `league` (TEXT), `sport` (TEXT), `market_type` (TEXT), `bet_side` (TEXT), `bookmaker` (TEXT), `odd_alerta` (REAL), `ev_alerta` (REAL), `commence_time` (TEXT), `commence_time_ajustado` (TEXT DEFAULT NULL), `valor_apostado` (REAL DEFAULT NULL), `status` (TEXT DEFAULT 'pendente'), `valor_cashout` (REAL DEFAULT NULL), `lucro` (REAL DEFAULT NULL), `tentativas_lembrete` (INTEGER DEFAULT 0), `timestamp_alerta` (TEXT), `timestamp_apostou` (TEXT), `timestamp_resultado` (TEXT), `timestamp_lembrete_enviado` (TEXT).
2. THE Database SHALL criar os índices: `idx_bets_chat` em `(chat_id)`, `idx_bets_status` em `(status)`, `idx_bets_pending_reminder` em `(status, commence_time, timestamp_lembrete_enviado)`.
3. WHEN a tabela `bets_placed` já existir, THE Database SHALL executar a criação com `CREATE TABLE IF NOT EXISTS` sem erro.
4. THE Database SHALL aceitar apenas os valores `pendente`, `ganhou`, `perdeu`, `empate`, `cashout`, `pulei`, `expirado` para a coluna `status`.
5. WHEN a migration for executada em um banco existente com dados, THE Database SHALL preservar todos os dados das tabelas existentes.

---

### Requirement 2: Módulo Bets_Tracker — Registro de Alertas

**User Story:** Como sistema, quero registrar automaticamente cada alerta enviado na tabela `bets_placed`, para que o usuário possa depois informar se apostou e qual foi o resultado.

#### Acceptance Criteria

1. WHEN o Alert_Sender enviar um alerta com sucesso, THE Bets_Tracker SHALL inserir um registro em `bets_placed` com `status = 'pendente'`, `valor_apostado = NULL`, e snapshot dos campos: `alert_hash`, `chat_id`, `feed_id`, `home`, `away`, `league`, `sport`, `market_type`, `bet_side`, `bookmaker`, `odd_alerta`, `ev_alerta`, `commence_time`, `timestamp_alerta`.
2. WHEN o mesmo `alert_hash` já existir na tabela, THE Bets_Tracker SHALL ignorar a inserção usando `INSERT OR IGNORE` sem retornar erro.
3. THE Bets_Tracker SHALL expor o método `registrar_alerta(alert_hash, chat_id, feed_id, dados_alerta)` que retorna o `bet_id` (`id`) do registro inserido ou existente.
4. THE Bets_Tracker SHALL ser instanciável sem dependência de módulos do Telegram.

---

### Requirement 3: Módulo Bets_Tracker — Atualização de Status

**User Story:** Como usuário, quero marcar se apostei ou pulei cada alerta, e depois registrar o resultado, para que meu histórico de apostas seja preciso.

#### Acceptance Criteria

1. WHEN o usuário clicar em "Apostei" e informar um valor válido, THE Bets_Tracker SHALL atualizar `valor_apostado` e `timestamp_apostou` para o registro identificado por `bet_id`.
2. WHEN o usuário clicar em "Pulei", THE Bets_Tracker SHALL atualizar `status = 'pulei'` para o registro identificado por `bet_id`.
3. WHEN o usuário registrar resultado como "Ganhei", THE Bets_Tracker SHALL atualizar `status = 'ganhou'`, calcular `lucro = (odd_alerta - 1) * valor_apostado`, e registrar `timestamp_resultado` para o registro identificado por `bet_id`.
4. WHEN o usuário registrar resultado como "Perdi", THE Bets_Tracker SHALL atualizar `status = 'perdeu'`, calcular `lucro = -valor_apostado`, e registrar `timestamp_resultado` para o registro identificado por `bet_id`.
5. WHEN o usuário registrar resultado como "Empate", THE Bets_Tracker SHALL atualizar `status = 'empate'`, calcular `lucro = 0`, e registrar `timestamp_resultado` para o registro identificado por `bet_id`.
6. WHEN o usuário registrar resultado como "Cashout" com `valor_cashout` informado, THE Bets_Tracker SHALL atualizar `status = 'cashout'`, calcular `lucro = valor_cashout - valor_apostado`, e registrar `timestamp_resultado` para o registro identificado por `bet_id`.
7. THE Bets_Tracker SHALL expor a função utilitária `calcular_lucro(odd, valor_apostado, status, valor_cashout=None)` que retorna o lucro calculado conforme as regras dos critérios 3 a 6.

---

### Requirement 4: Módulo Bets_Tracker — Expiração Automática

**User Story:** Como sistema, quero expirar automaticamente alertas antigos sem resposta, para que o histórico não fique poluído com apostas que o usuário ignorou.

#### Acceptance Criteria

1. WHEN `expirar_alertas_antigos()` for chamado, THE Bets_Tracker SHALL atualizar `status = 'expirado'` para todos os registros onde `status = 'pendente'`, `valor_apostado IS NULL`, e `commence_time + 2 horas < agora (UTC)`.
2. THE Bets_Tracker SHALL expor o método `expirar_alertas_antigos()` sem parâmetros obrigatórios.
3. WHEN nenhum registro atender aos critérios de expiração, THE Bets_Tracker SHALL executar sem erro e retornar 0.

---

### Requirement 5: Módulo Bets_Tracker — Lembretes Pós-Jogo

**User Story:** Como sistema, quero identificar apostas que precisam de resultado registrado após o término do jogo, para que o bot possa enviar lembretes automáticos ao usuário.

#### Acceptance Criteria

1. WHEN `get_pendentes_para_lembrete()` for chamado, THE Bets_Tracker SHALL retornar todos os registros onde `status = 'pendente'`, `valor_apostado IS NOT NULL`, `COALESCE(commence_time_ajustado, commence_time) + DURACAO_ESPORTE[sport] < agora (UTC)`, e `timestamp_lembrete_enviado IS NULL`.
2. THE Bets_Tracker SHALL usar a tabela `DURACAO_ESPORTE` com os valores: `soccer: 2.5h`, `basketball: 2.5h`, `tennis: 3.0h`, `americanfootball: 3.5h`, `baseball: 3.5h`, `hockey: 2.5h`, `mma: 2.0h`, `boxing: 2.0h`, `esports: 2.0h`, e `DURACAO_DEFAULT: 3.0h` para esportes não listados.
3. WHEN `marcar_lembrete_enviado(bet_id)` for chamado, THE Bets_Tracker SHALL atualizar `timestamp_lembrete_enviado` com o timestamp atual UTC e zerar `tentativas_lembrete = 0` para o registro identificado por `bet_id`.
4. WHEN o usuário clicar em "Adiar 3h", THE Bets_Tracker SHALL limpar `timestamp_lembrete_enviado` (setar NULL) e preencher `commence_time_ajustado` com `COALESCE(commence_time_ajustado, commence_time) + 3 horas` para o registro identificado por `bet_id`. O campo `commence_time` original SHALL permanecer inalterado.

---

### Requirement 6: Módulo Bets_Tracker — Consultas e Relatórios

**User Story:** Como usuário, quero consultar meu histórico de apostas e ver meu ROI, para que eu possa avaliar minha performance como apostador.

#### Acceptance Criteria

1. WHEN `get_resumo(chat_id, dias=30)` for chamado, THE Bets_Tracker SHALL retornar um dicionário com: total de apostas finalizadas, total apostado, lucro total, ROI percentual, contagem por status (`ganhou`, `perdeu`, `empate`, `cashout`), e EV médio — considerando apenas registros com status finalizado (`ganhou`, `perdeu`, `empate`, `cashout`) dos últimos `dias` dias. Registros com status `pendente`, `pulei` ou `expirado` SHALL ser excluídos do cálculo de EV médio e dos totais.
2. WHEN `get_pendentes(chat_id)` for chamado, THE Bets_Tracker SHALL retornar todos os registros com `status = 'pendente'` e `valor_apostado IS NOT NULL` para o `chat_id` informado, ordenados por `COALESCE(commence_time_ajustado, commence_time)` ascendente.
3. WHEN `get_historico(chat_id, limit=20)` for chamado, THE Bets_Tracker SHALL retornar os últimos `limit` registros com status finalizado (`ganhou`, `perdeu`, `empate`, `cashout`) para o `chat_id` informado, ordenados por `timestamp_resultado` descendente.
4. WHEN não houver apostas no período consultado, THE Bets_Tracker SHALL retornar estrutura vazia sem erro (dicionário com zeros para `get_resumo`, lista vazia para `get_pendentes` e `get_historico`).

---

### Requirement 7: Templates de Alerta com Botões de Ação

**User Story:** Como usuário, quero ver botões de ação em cada alerta recebido, para que eu possa registrar rapidamente se apostei ou pulei sem precisar digitar comandos.

#### Acceptance Criteria

1. WHEN o Alert_Sender enviar um alerta com `ev < THRESHOLD_EV_ALTO`, THE Alert_Sender SHALL usar o template normal iniciando com `🟢 Alerta EV+` seguido dos dados do evento.
2. WHEN o Alert_Sender enviar um alerta com `ev >= THRESHOLD_EV_ALTO`, THE Alert_Sender SHALL usar o template destacado iniciando com `🚨🚨 ALERTA EV ALTO 🚨🚨`, adicionar `⭐` ao lado do valor de EV, e incluir a linha `⚡ Aposte rápido` no corpo da mensagem.
3. THE Alert_Sender SHALL incluir `InlineKeyboardMarkup` com dois botões em toda mensagem de alerta: `[✅ Apostei]` com `callback_data = f"bet_yes:{bet_id}"` e `[❌ Pulei]` com `callback_data = f"bet_no:{bet_id}"`.
4. THE Alert_Sender SHALL usar o `bet_id` (inteiro da tabela `bets_placed`) no `callback_data`, não o `alert_hash`, para respeitar o limite de 64 bytes do Telegram.
5. WHEN o Alert_Sender for enviar a mensagem, THE Alert_Sender SHALL primeiro chamar `bets_tracker.registrar_alerta(...)` para obter o `bet_id`, depois montar os botões com esse `bet_id`, e então enviar a mensagem.
6. THE Alert_Sender SHALL manter o comportamento existente de envio (parse_mode HTML, disable_web_page_preview) ao adicionar os botões.

---

### Requirement 8: Fluxo "Apostei" no Bot_Listener

**User Story:** Como usuário, quero clicar em "Apostei" e informar o valor apostado em uma conversa natural, para que o registro seja feito sem precisar lembrar de comandos.

#### Acceptance Criteria

1. WHEN o usuário clicar no botão `bet_yes:{bet_id}`, THE Bot_Listener SHALL editar a mensagem original removendo os botões e adicionando o texto `⏳ Aguardando valor da aposta...`.
2. WHEN o usuário clicar em `bet_yes:{bet_id}`, THE Bot_Listener SHALL armazenar `bet_id` em `context.user_data['esperando_valor_aposta']`.
3. WHEN o usuário enviar uma mensagem de texto enquanto `context.user_data['esperando_valor_aposta']` estiver definido, THE Bot_Listener SHALL validar o texto contra o padrão `^\d+([.,]\d{1,2})?$`.
4. WHEN o valor informado for válido, THE Bot_Listener SHALL normalizar vírgula para ponto, chamar `bets_tracker.marcar_apostou(bet_id, valor)`, limpar `context.user_data['esperando_valor_aposta']`, e editar a mensagem original adicionando a linha `💰 Apostado: R$ X,XX`.
5. WHEN o valor informado for inválido, THE Bot_Listener SHALL responder com mensagem de erro pedindo novo valor sem limpar o estado de espera.
6. WHEN o bot reiniciar e `context.user_data['esperando_valor_aposta']` for perdido, THE Bot_Listener SHALL aceitar que o usuário precisará clicar no botão novamente (estado em memória não é persistido).
7. WHEN o usuário receber um callback de botão enquanto `context.user_data['esperando_valor_aposta']` ou `context.user_data['esperando_valor_cashout']` estiver definido, THE Bot_Listener SHALL processar o callback normalmente sem interferência. Apenas mensagens de texto (não callbacks) SHALL consumir os estados `esperando_valor_aposta` e `esperando_valor_cashout`.

---

### Requirement 9: Fluxo "Pulei" no Bot_Listener

**User Story:** Como usuário, quero clicar em "Pulei" para registrar que não apostei naquele alerta, para que meu histórico reflita apenas apostas reais.

#### Acceptance Criteria

1. WHEN o usuário clicar no botão `bet_no:{bet_id}`, THE Bot_Listener SHALL editar a mensagem original removendo os botões e adicionando o texto `❌ Pulado`.
2. WHEN o usuário clicar em `bet_no:{bet_id}`, THE Bot_Listener SHALL chamar `bets_tracker.marcar_pulei(bet_id)`.
3. WHEN o botão de um alerta já com status final for clicado novamente, THE Bot_Listener SHALL responder com `query.answer("Esta aposta já foi marcada", show_alert=True)` sem modificar a mensagem nem os dados (ver Req 15).

---

### Requirement 10: Fluxo de Lembrete Pós-Jogo no Bot_Listener

**User Story:** Como usuário, quero receber uma mensagem após o término do jogo pedindo o resultado, para que eu não precise lembrar de registrar manualmente.

#### Acceptance Criteria

1. WHEN o Scheduler chamar o job de lembrete e houver apostas pendentes de resultado, THE Bot_Listener SHALL enviar uma nova mensagem ao usuário com os dados da aposta e os botões: `[🟢 Ganhei]` (`bet_result_win:{bet_id}`), `[🔴 Perdi]` (`bet_result_loss:{bet_id}`), `[⚪ Empate]` (`bet_result_push:{bet_id}`), `[💸 Cashout]` (`bet_cashout:{bet_id}`), `[⏰ Adiar 3h]` (`bet_postpone:{bet_id}`).
2. WHEN o usuário clicar em `bet_result_win:{bet_id}`, THE Bot_Listener SHALL chamar `bets_tracker.marcar_resultado(bet_id, 'ganhou')` e confirmar ao usuário.
3. WHEN o usuário clicar em `bet_result_loss:{bet_id}`, THE Bot_Listener SHALL chamar `bets_tracker.marcar_resultado(bet_id, 'perdeu')` e confirmar ao usuário.
4. WHEN o usuário clicar em `bet_result_push:{bet_id}`, THE Bot_Listener SHALL chamar `bets_tracker.marcar_resultado(bet_id, 'empate')` e confirmar ao usuário.
5. WHEN o usuário clicar em `bet_cashout:{bet_id}`, THE Bot_Listener SHALL editar a mensagem de lembrete removendo os botões e adicionando o texto `⏳ Aguardando valor do cashout...`, armazenar `bet_id` em `context.user_data['esperando_valor_cashout']`, aguardar mensagem de texto do usuário, validar o valor conforme Req 14, normalizar vírgula para ponto, chamar `bets_tracker.marcar_resultado(bet_id, 'cashout', valor_cashout=valor)`, limpar `context.user_data['esperando_valor_cashout']`, e confirmar ao usuário com a linha `💸 Cashout: R$ X,XX`.
6. WHEN o usuário clicar em `bet_postpone:{bet_id}`, THE Bot_Listener SHALL chamar `bets_tracker.adiar_lembrete(bet_id)` que limpa `timestamp_lembrete_enviado` e preenche `commence_time_ajustado` com +3h (ver Req 5.4).

---

### Requirement 11: Comandos de Consulta no Bot_Listener

**User Story:** Como usuário, quero comandos para consultar meu histórico e performance, para que eu possa acompanhar meu ROI diretamente no Telegram.

#### Acceptance Criteria

1. WHEN o usuário enviar `/banca` ou `/banca {dias}`, THE Bot_Listener SHALL responder com o resumo de ROI dos últimos `dias` dias (padrão 30), incluindo: total de apostas, total apostado, lucro, ROI%, e contagem por resultado.
2. WHEN o usuário enviar `/pendentes`, THE Bot_Listener SHALL responder com a lista de apostas com `status = 'pendente'` e `valor_apostado IS NOT NULL` aguardando resultado, exibindo jogo, mercado, odd, valor apostado e horário do jogo.
3. WHEN o usuário enviar `/historico`, THE Bot_Listener SHALL responder com as últimas 20 apostas finalizadas, exibindo jogo, resultado, odd, valor apostado e lucro.
4. WHEN não houver dados para exibir em qualquer dos comandos acima, THE Bot_Listener SHALL responder com mensagem informativa indicando ausência de dados.

---

### Requirement 12: Jobs Periódicos no Scheduler

**User Story:** Como sistema, quero jobs automáticos para enviar lembretes e expirar alertas antigos, para que o tracking funcione sem intervenção manual.

#### Acceptance Criteria

1. THE Scheduler SHALL adicionar um job de lembrete pós-jogo que executa a cada 15 minutos, chama `bets_tracker.get_pendentes_para_lembrete()`, e tenta enviar mensagem de lembrete para cada aposta retornada.
2. THE Scheduler SHALL adicionar um job de expiração que executa a cada 30 minutos e chama `bets_tracker.expirar_alertas_antigos()`.
3. WHEN o job de lembrete enviar a mensagem com sucesso, THE Scheduler SHALL chamar `bets_tracker.marcar_lembrete_enviado(bet_id)` que atualiza `timestamp_lembrete_enviado` e zera `tentativas_lembrete`.
4. WHEN o job de lembrete falhar ao enviar mensagem para um usuário específico, THE Scheduler SHALL registrar o erro em log, incrementar `tentativas_lembrete` para aquela aposta, e continuar processando os demais. O campo `timestamp_lembrete_enviado` SHALL permanecer NULL em caso de falha.
5. WHEN os jobs de lembrete e expiração forem adicionados, THE Scheduler SHALL manter todos os jobs existentes sem modificação.
6. WHEN `tentativas_lembrete >= 5` para uma aposta, THE Scheduler SHALL marcar aquela aposta como `status = 'expirado'` em vez de tentar novamente.
7. THE Bets_Tracker SHALL expor o método `incrementar_tentativa_lembrete(bet_id)` que incrementa `tentativas_lembrete` em 1 e retorna o novo valor, para uso pelo Scheduler no controle de falhas.

---

### Requirement 13: Configurações em config.py

**User Story:** Como desenvolvedor, quero constantes centralizadas em `config.py` para os parâmetros do sistema de tracking, para que ajustes futuros sejam feitos em um único lugar.

#### Acceptance Criteria

1. THE config.py SHALL definir a constante `THRESHOLD_EV_ALTO = 0.08` (8% em decimal).
2. THE config.py SHALL alterar `RATE_LIMIT_REQUESTS_PER_HOUR` de `4800` para `90`.
3. WHEN as constantes forem adicionadas, THE config.py SHALL manter todas as constantes e funções existentes sem modificação.

---

### Requirement 14: Validação de Valor Monetário

**User Story:** Como sistema, quero validar o valor informado pelo usuário antes de persistir, para que apenas valores monetários válidos sejam aceitos.

#### Acceptance Criteria

1. THE Bot_Listener SHALL aceitar valores no formato `^\d+([.,]\d{1,2})?$` (inteiro ou decimal com 1 ou 2 casas, separador vírgula ou ponto).
2. WHEN o valor usar vírgula como separador decimal, THE Bot_Listener SHALL normalizar para ponto antes de converter para float.
3. WHEN o valor for zero ou negativo após conversão, THE Bot_Listener SHALL rejeitar e solicitar novo valor.
4. WHEN o valor for válido, THE Bot_Listener SHALL converter para `float` antes de passar ao Bets_Tracker.
5. Esta regra de validação SHALL ser aplicada tanto ao fluxo de valor apostado (Req 8) quanto ao fluxo de valor de cashout (Req 10.5).

---

### Requirement 15: Idempotência de Callbacks

**User Story:** Como sistema, quero que callbacks acionados em apostas já finalizadas sejam ignorados de forma segura, para que cliques acidentais ou tardios não corrompam dados já registrados.

#### Acceptance Criteria

1. WHEN qualquer callback (`bet_yes`, `bet_no`, `bet_result_win`, `bet_result_loss`, `bet_result_push`, `bet_cashout`, `bet_postpone`) for acionado para uma aposta com status final (`ganhou`, `perdeu`, `empate`, `cashout`, `pulei`, `expirado`), THE Bot_Listener SHALL responder com `query.answer("Esta aposta já foi registrada", show_alert=True)` sem modificar a mensagem nem os dados persistidos.
2. WHEN o callback `bet_postpone` for acionado para uma aposta com status final, THE Bot_Listener SHALL aplicar a mesma regra do critério 1 — sem adiar nem modificar `commence_time_ajustado`.
3. THE Bot_Listener SHALL verificar o status atual da aposta no banco de dados antes de processar qualquer callback, não confiando apenas no estado da mensagem do Telegram.
