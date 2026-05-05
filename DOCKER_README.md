# Bot EV+ v3.0 - Docker Setup Guide

## 🐳 Configuração Docker Completa

### 📋 Pré-requisitos
- Docker instalado
- Docker Compose instalado
- Tokens do Telegram Bot
- Chave da Odds API

### 🚀 Setup Rápido

1. **Configure as variáveis de ambiente:**
```bash
cp env.docker.example .env
# Edite o arquivo .env com seus tokens
```

2. **Inicie o sistema completo:**
```bash
docker-compose up -d
```

3. **Verifique os containers:**
```bash
docker-compose ps
```

### 📊 Estrutura dos Containers

- **global-scanner**: Scanner global único (1 request a cada 2min)
- **feed-default**: Feed principal
- **feed-1**: Feed secundário 1
- **feed-2**: Feed secundário 2
- **feed-3**: Feed secundário 3
- **feed-4**: Feed secundário 4
- **dashboard**: Dashboard web (opcional)
- **metrics**: Monitor de métricas (opcional)

### 🔧 Comandos Úteis

```bash
# Ver logs do scanner global
docker-compose logs global-scanner

# Ver logs de um feed específico
docker-compose logs feed-default

# Ver métricas em tempo real
docker-compose logs -f metrics

# Reiniciar apenas um serviço
docker-compose restart feed-default

# Parar todos os serviços
docker-compose down

# Rebuild e iniciar
docker-compose up --build -d
```

### 📈 Monitoramento

```bash
# Status dos containers
docker-compose ps

# Uso de recursos
docker stats

# Logs em tempo real
docker-compose logs -f
```

### 🛠️ Desenvolvimento

```bash
# Executar apenas o scanner global
docker run --rm -it bot-ev scanner

# Executar apenas um feed
docker run --rm -it bot-ev feed default

# Executar testes
docker run --rm -it bot-ev test

# Ver métricas
docker run --rm -it bot-ev python metrics_viewer.py summary
```

### 🔒 Segurança

- Todos os dados ficam em volumes persistentes
- Tokens são carregados via variáveis de ambiente
- Rede isolada entre containers
- Restart automático em caso de falha

### 📁 Estrutura de Volumes

```
./data/          # Dados persistentes (SQLite, cache)
./logs/          # Logs do sistema
./.env           # Variáveis de ambiente
```

### 🎯 Vantagens do Docker

- ✅ Isolamento completo
- ✅ Fácil deploy e rollback
- ✅ Escalabilidade horizontal
- ✅ Monitoramento integrado
- ✅ Backup simplificado
- ✅ Zero conflitos de dependências
