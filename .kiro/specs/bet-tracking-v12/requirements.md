# Documento de Requisitos — v1.2: Aviso de Jogo Duplicado, Odd Apostada e Gestão de Banca

## Introdução

Esta versão (v1.2) implementa três melhorias interligadas no Bot EV+:
1. **Aviso de jogo duplicado** — ao enviar um alerta, o sistema verifica se já existem alertas anteriores para o mesmo jogo e avisa o usuário.
2. **Odd apostada** — permite ao usuário informar a odd real no momento da aposta, usada no cálculo de lucro em vez da odd do alerta.
3. **Gestão de banca** — o usuário pode configurar bankroll e valor por unidade, visualizar resumo financeiro e resetar todos os dados.

## Glossário

- **Sistema**: O Bot EV+ (conjunto de módulos Python que compõem o bot Telegram de apostas com valor esperado positivo)
- **BetsTracker**: Módulo de lógica de tracking de apostas (`src/bot/bets_tracker.py`)
- **AlertSender**: Classe responsável por formatar e enviar alertas via Telegram (`src/bot/bot_ev.py`)
- **Listener**: Módulo que recebe e processa comandos do usuário via Telegram (`src/bot/bot_listener.py`)
- **Scheduler**: Módulo que executa scans periódicos e envia lembretes (`src/scanner/main_scheduler.py`)
- **Database**: Módulo de persistência SQLite (`src/core/database.py`)
- **odd_apostada**: Odd real informada pelo usuário no momento em que confirma a aposta
- **odd_alerta**: Odd capturada automaticamente no momento do envio do alerta
- **bankroll**: Capital total disponível do usuário para apostas
- **valor_unidade**: Valor monetário de uma unidade de stake do usuário
- **commence_time**: Timestamp ISO 8601 do início do evento esportivo
- **chat_id**: Identificador único do usuário no Telegram
- **user_bankroll**: Tabela de configuração de banca por usuário

## Requisitos

### Requisito 1: Migração de Banco — Coluna odd_apostada

**User Story:** Como desenvolvedor, eu quero que a coluna `odd_apostada` exista na tabela `bets_placed`, para que o sistema possa armazenar a odd real informada pelo usuário.

#### Critérios de Aceitação

1. WHEN o Database é inicializado, THE Database SHALL executar a migração `ALTER TABLE bets_placed ADD COLUMN odd_apostada REAL DEFAULT NULL` de forma idempotente (sem erro se a coluna já existir)
2. THE Database SHALL manter o valor NULL em `odd_apostada` para registros existentes que não possuem odd informada pelo usuário

### Requisito 2: Migração de Banco — Tabela user_bankroll

**User Story:** Como desenvolvedor, eu quero uma tabela `user_bankroll` no banco de dados, para que o sistema possa persistir a configuração de banca de cada usuário.

#### Critérios de Aceitação

1. WHEN o Database é inicializado, THE Database SHALL criar a tabela `user_bankroll` com as colunas: `chat_id` (TEXT, PRIMARY KEY), `bankroll` (REAL, NOT NULL), `valor_unidade` (REAL, NOT NULL), `timestamp` (TEXT)
2. THE Database SHALL criar a tabela de forma idempotente (CREATE TABLE IF NOT EXISTS)
3. THE Database SHALL posicionar a criação da tabela `user_bankroll` após a criação da tabela `bets_placed` no método `_init_db()`

### Requisito 3: Busca de Alertas do Mesmo Jogo

**User Story:** Como usuário, eu quero ser avisado quando recebo um novo alerta para um jogo que já recebi alerta anteriormente, para que eu possa tomar decisões mais informadas.

#### Critérios de Aceitação

1. WHEN o BetsTracker recebe uma consulta de alertas do mesmo jogo, THE BetsTracker SHALL retornar todos os registros em `bets_placed` onde `chat_id` é igual ao informado, `home` é igual ao informado, `away` é igual ao informado e os primeiros 16 caracteres de `commence_time` são iguais aos primeiros 16 caracteres do `commence_time` informado
2. THE BetsTracker SHALL retornar uma lista vazia quando não existem alertas anteriores para o mesmo jogo
3. THE BetsTracker SHALL expor esta funcionalidade através do método `buscar_alertas_mesmo_jogo(chat_id, home, away, commence_time)`

### Requisito 4: Registro de Odd Apostada

**User Story:** Como usuário, eu quero informar a odd real no momento em que confirmo a aposta, para que o cálculo de lucro reflita a odd que realmente obtive.

#### Critérios de Aceitação

1. WHEN o BetsTracker executa `marcar_apostou()` com `odd_apostada` informada, THE BetsTracker SHALL salvar o valor de `odd_apostada` no registro da aposta
2. WHEN o BetsTracker executa `marcar_apostou()` sem `odd_apostada` (valor None), THE BetsTracker SHALL copiar o valor de `odd_alerta` para o campo `odd_apostada` como fallback
3. WHEN o BetsTracker executa `marcar_resultado()`, THE BetsTracker SHALL usar `odd_apostada` para o cálculo de lucro, com fallback para `odd_alerta` caso `odd_apostada` seja NULL

### Requisito 5: Configuração de Bankroll

**User Story:** Como usuário, eu quero configurar meu bankroll e valor por unidade, para que o bot possa calcular e exibir informações financeiras personalizadas.

#### Critérios de Aceitação

1. WHEN o BetsTracker recebe uma solicitação de configuração de banca, THE BetsTracker SHALL salvar ou atualizar `bankroll` e `valor_unidade` na tabela `user_bankroll` para o `chat_id` informado
2. WHEN o BetsTracker recebe uma consulta de banca, THE BetsTracker SHALL retornar `bankroll` e `valor_unidade` do usuário, ou None se não configurado
3. THE BetsTracker SHALL expor a configuração via método `configurar_bankroll(chat_id, bankroll, valor_unidade)`
4. THE BetsTracker SHALL expor a consulta via método `get_bankroll(chat_id)`

### Requisito 6: Reset de Banca

**User Story:** Como usuário, eu quero poder resetar todos os meus dados de apostas e configuração de banca, para recomeçar do zero quando necessário.

#### Critérios de Aceitação

1. WHEN o BetsTracker recebe uma solicitação de reset, THE BetsTracker SHALL deletar todos os registros de `bets_placed` do `chat_id` informado
2. WHEN o BetsTracker recebe uma solicitação de reset, THE BetsTracker SHALL deletar o registro de `user_bankroll` do `chat_id` informado
3. THE BetsTracker SHALL expor esta funcionalidade via método `resetar_banca(chat_id)`

### Requisito 7: Aviso de Jogo Duplicado nos Alertas

**User Story:** Como usuário, eu quero ver um aviso no corpo do alerta quando já recebi alertas anteriores para o mesmo jogo, para que eu saiba que já tenho exposição naquele evento.

#### Critérios de Aceitação

1. WHEN o AlertSender prepara um alerta e existem alertas anteriores para o mesmo jogo, THE AlertSender SHALL construir uma mensagem de aviso contendo informações dos alertas anteriores (mercado, odd, status)
2. WHEN o AlertSender prepara um alerta e não existem alertas anteriores para o mesmo jogo, THE AlertSender SHALL não incluir aviso na mensagem
3. THE AlertSender SHALL expor a construção do aviso via método `_montar_aviso_mesmo_jogo(alertas_anteriores)`
4. WHEN o AlertSender envia um alerta via `enviar_alerta()`, THE AlertSender SHALL chamar `buscar_alertas_mesmo_jogo()` antes de `registrar_alerta()` e passar o aviso resultante para o template
5. WHEN o AlertSender envia um alerta via `enviar_alerta_instantaneo()`, THE AlertSender SHALL chamar `buscar_alertas_mesmo_jogo()` antes de `registrar_alerta()` e passar o aviso resultante para o template

### Requisito 8: Injeção do Aviso nos Templates

**User Story:** Como usuário, eu quero que o aviso de jogo duplicado apareça de forma visível no corpo da mensagem de alerta, para que eu não precise procurar a informação.

#### Critérios de Aceitação

1. THE AlertSender SHALL atualizar as assinaturas dos métodos `_formatar_alerta_destacado()` e `_formatar_alerta_normal()` para aceitar o parâmetro `aviso` (string opcional)
2. WHEN o parâmetro `aviso` é fornecido e não vazio, THE AlertSender SHALL injetar o texto do aviso logo após o cabeçalho da mensagem (após a primeira linha do template)
3. WHEN o parâmetro `aviso` é None ou vazio, THE AlertSender SHALL não alterar o template

### Requisito 9: Parser de Valor e Odd

**User Story:** Como usuário, eu quero poder informar o valor apostado e opcionalmente a odd real em uma única mensagem, para que o processo de confirmação de aposta seja mais rápido.

#### Critérios de Aceitação

1. WHEN o Listener recebe texto no formato `"50"`, THE Listener SHALL interpretar como valor=50.0 e odd=None
2. WHEN o Listener recebe texto no formato `"50 1.47"`, THE Listener SHALL interpretar como valor=50.0 e odd=1.47
3. WHEN o Listener recebe texto no formato `"50 1,47"` (vírgula como separador decimal), THE Listener SHALL interpretar como valor=50.0 e odd=1.47
4. THE Listener SHALL expor esta funcionalidade via método `_parsear_valor_e_odd(texto)` que retorna uma tupla `(valor, odd)`
5. WHEN o Listener processa a confirmação de aposta em `bet_text_handler()`, THE Listener SHALL usar `_parsear_valor_e_odd()` em vez de `_validar_valor()`

### Requisito 10: Exibição de Odd Apostada nos Comandos

**User Story:** Como usuário, eu quero ver a odd real (odd_apostada) nos comandos /pendentes e /historico, para que as informações exibidas reflitam a odd que realmente obtive.

#### Critérios de Aceitação

1. WHEN o Listener formata a lista de apostas pendentes em `pendentes_command()`, THE Listener SHALL exibir `odd_apostada` quando disponível, com fallback para `odd_alerta`
2. WHEN o Listener formata o histórico em `historico_command()`, THE Listener SHALL exibir `odd_apostada` quando disponível, com fallback para `odd_alerta`
3. WHEN o Scheduler formata o lembrete pós-jogo em `_formatar_lembrete()`, THE Scheduler SHALL exibir `odd_apostada` quando disponível, com fallback para `odd_alerta`

### Requisito 11: Comando /banca com Lógica Dual

**User Story:** Como usuário, eu quero usar o comando /banca tanto para configurar minha banca quanto para ver o resumo financeiro, para que a interação seja simples e intuitiva.

#### Critérios de Aceitação

1. WHEN o Listener recebe `/banca` com argumentos (ex: `/banca 1000 50`), THE Listener SHALL interpretar como configuração de bankroll=1000 e valor_unidade=50, salvar via `configurar_bankroll()` e confirmar ao usuário
2. WHEN o Listener recebe `/banca` sem argumentos, THE Listener SHALL exibir o resumo financeiro contendo: bankroll configurado, valor por unidade, total apostado, lucro/prejuízo acumulado e ROI
3. IF o Listener recebe `/banca` sem argumentos e o usuário não tem banca configurada, THEN THE Listener SHALL exibir mensagem orientando o uso correto do comando

### Requisito 12: Comando /reset com Confirmação

**User Story:** Como usuário, eu quero poder resetar meus dados de apostas com uma confirmação explícita, para evitar exclusões acidentais.

#### Critérios de Aceitação

1. WHEN o Listener recebe `/reset` sem a palavra `CONFIRMAR`, THE Listener SHALL exibir mensagem de aviso explicando que o comando apagará todos os dados e instruir o uso de `/reset CONFIRMAR`
2. WHEN o Listener recebe `/reset CONFIRMAR`, THE Listener SHALL executar `resetar_banca()` e confirmar ao usuário que os dados foram apagados
3. THE Listener SHALL registrar o comando `/reset` no ApplicationBuilder como CommandHandler

