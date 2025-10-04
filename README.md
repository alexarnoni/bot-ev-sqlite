# Bot EV+ com SQLite

Sistema de alertas de apostas esportivas com valor positivo (EV+) usando SQLite como banco de dados.

## 🚀 Características

- **Scheduler fixo**: Scan a cada 2 minutos
- **API Odds**: Integração com odds-api.io
- **Multi-feed**: Suporte a múltiplos feeds isolados
- **SQLite**: Banco de dados robusto e escalável
- **Setup wizard**: Configuração em 4 passos
- **Filtros avançados**: EV, horários, ligas, esportes
- **Cache inteligente**: Evita duplicatas
- **Histórico completo**: Todos os alertas salvos

## 📋 Pré-requisitos

- Python 3.11+
- Conta na Odds API (odds-api.io)
- Token do Telegram Bot

## 🛠️ Instalação

### Windows (Recomendado)

1. **Execute o setup automático**
```batch
setup.bat
```

2. **Configure o arquivo .env**
Edite o arquivo `.env` e adicione seus tokens:
```env
TELEGRAM_TOKEN_FEED_TEST=seu_token_aqui
ODDS_API_KEY=sua_chave_api_aqui
```

3. **Teste o sistema**
```batch
run_test.bat
```

4. **Inicie o bot**
```batch
start_bot.bat
```

### Linux/Mac

1. **Clone o repositório**
```bash
git clone <repo-url>
cd bot-ev-sqlite
```

2. **Instale as dependências**
```bash
pip install -r requirements.txt
```

3. **Configure as variáveis de ambiente**
```bash
# Tokens dos bots (um por feed)
export BOT_TOKEN_DEFAULT="seu_token_bot_default"
export BOT_TOKEN_FEED1="seu_token_bot_feed1"
export BOT_TOKEN_FEED2="seu_token_bot_feed2"

# API Odds
export ODDS_API_KEY="sua_chave_odds_api"

# Usuários admin (opcional)
export ADMIN_USERS="123456789,987654321"

# Configuração de feeds
export FEEDS="default feed1 feed2"
export FEED_ID="default"
```

## 🗄️ Migração de Dados

Se você tem dados em formato JSON/Pickle/CSV, use o script de migração:

```bash
# Migração com backup
python migrate_to_sqlite.py default --backup

# Migração simples
python migrate_to_sqlite.py default
```

## 🚀 Execução

### Iniciar um feed específico
```bash
./start.sh default
```

### Iniciar múltiplos feeds
```bash
# Feed 1
FEED_ID=feed1 ./start.sh

# Feed 2  
FEED_ID=feed2 ./start.sh
```

### Execução manual
```bash
# Bot listener
python bot_listener.py

# Scheduler
python main_scheduler.py
```

## 📱 Comandos do Bot

### Comandos básicos
- `/start` - Configurar ou acessar menu principal
- `/scan` - Fazer scan manual
- `/stats` - Ver suas estatísticas
- `/filtros` - Ver/editar filtros
- `/ligas` - Ver ligas disponíveis
- `/esportes` - Ver esportes disponíveis
- `/bookmakers` - Ver bookmakers disponíveis

### Comandos admin
- `/admin` - Menu administrativo
- `/admin_users` - Lista usuários
- `/admin_stats` - Estatísticas do sistema
- `/admin_broadcast` - Broadcast para usuários

## ⚙️ Configuração

### Setup Wizard (4 passos)

1. **Bookmakers**: Selecione os bookmakers que você usa
2. **EV Mínimo**: Escolha o valor esperado mínimo (3%, 5%, 12% ou personalizado)
3. **Regiões**: Selecione as regiões das ligas de interesse
4. **Horários**: Defina o período para receber alertas

### Filtros disponíveis

- **EV**: Valor esperado mínimo e máximo
- **Horários**: Período do dia (cruza meia-noite)
- **Datas**: Período específico ou dinâmico (próximos X dias)
- **Ligas**: Lista específica de ligas
- **Esportes**: Futebol, basquete, tênis, etc.
- **Bookmakers**: Lista de casas de apostas

## 🗃️ Estrutura do Banco

### Tabelas principais

- `users` - Usuários do bot
- `user_bookmakers` - Bookmakers por usuário
- `user_filters` - Filtros de cada usuário
- `user_leagues` - Ligas por usuário
- `user_sports` - Esportes por usuário
- `alert_cache` - Cache de alertas enviados
- `alert_history` - Histórico de alertas
- `pending_alerts` - Alertas pendentes
- `league_catalog` - Catálogo de ligas
- `system_status` - Status do sistema
- `rate_limiter` - Controle de rate limiting

## 📊 Monitoramento

### Logs
```bash
# Ver logs do listener
tmux attach -t listener_default

# Ver logs do scheduler
tmux attach -t main_default
```

### Estatísticas
- Total de usuários ativos
- Alertas enviados nas últimas 24h
- EV médio do sistema
- Status da API
- Rate limiting

## 🔧 Manutenção

### Limpeza automática
- Cache: 30 dias
- Logs de rate limiting: 2 horas
- Limpeza do banco: 3h da manhã

### Backup
```bash
# Backup manual
cp data/default/bot.db backup_bot_$(date +%Y%m%d).db
```

### Restauração
```bash
# Restaurar backup
cp backup_bot_20240115.db data/default/bot.db
```

## 🐛 Troubleshooting

### Problemas comuns

1. **Bot não responde**
   - Verifique se o token está correto
   - Confirme se o bot está rodando: `tmux list-sessions`

2. **API não funciona**
   - Verifique a chave da Odds API
   - Confirme se não excedeu o rate limit

3. **Banco de dados**
   - Verifique permissões do diretório `data/`
   - Confirme se o SQLite está funcionando

### Logs de erro
```bash
# Ver logs detalhados
tail -f logs/bot_geral.log
tail -f logs/bot_scan.log
tail -f logs/bot_alertas.log
```

## 📈 Performance

### Otimizações implementadas

- **Índices SQLite**: Buscas rápidas
- **Cache inteligente**: Evita duplicatas
- **Rate limiting**: Respeita limites da API
- **Processamento paralelo**: Múltiplos usuários simultâneos
- **Limpeza automática**: Mantém banco otimizado

### Capacidade

- **Usuários**: Milhares de usuários simultâneos
- **Alertas**: Centenas de alertas por minuto
- **Bookmakers**: Todos os principais suportados
- **Ligas**: 200+ ligas de 50+ países

## 🔒 Segurança

- **Isolamento por feed**: Dados completamente separados
- **Foreign keys**: Integridade referencial
- **Transações ACID**: Consistência garantida
- **Rate limiting**: Proteção contra abuso
- **Validação de dados**: Entrada sanitizada

## 📞 Suporte

Para suporte técnico:
- Telegram: @seu_suporte
- Email: suporte@exemplo.com
- Issues: GitHub Issues

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para detalhes.

---

**Bot EV+ v2.0** - Sistema de alertas de apostas com valor positivo
