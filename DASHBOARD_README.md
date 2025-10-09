# 🌐 Bot EV+ Dashboard Web

Dashboard web para monitorar o bot EV+ pelo navegador, sem precisar acessar a VM.

## 🚀 Como usar

### 1. Instalar dependências
```bash
# Na VM
pip install -r requirements_dashboard.txt
```

### 2. Iniciar o dashboard
```bash
# Opção 1: Em sessão tmux (RECOMENDADO - pode fechar a VM)
./start_dashboard_tmux.sh

# Opção 2: Script automático (mantém VM aberta)
./start_dashboard.sh

# Opção 3: Manual
python3 web_dashboard.py
```

### 3. Acessar no navegador
```
http://localhost:5000
# ou
http://IP_DA_VM:5000
```

## 📊 Funcionalidades

### 💻 Sistema
- CPU, Memória e Disco
- Processos Python ativos
- Status dos recursos

### 👥 Usuários
- Total de usuários
- Usuários ativos
- Usuários configurados
- Últimos registros

### 📈 Alertas
- Alertas enviados hoje
- Alertas desta semana
- Alertas por esporte
- Histórico recente

### 🔄 Feeds
- Status de cada feed (default, feed1, feed2, etc.)
- Listener e Scheduler rodando
- Número de usuários por feed
- Indicadores visuais de status

### 📝 Logs
- Logs recentes em tempo real
- Atualização automática
- Botão de refresh manual

## ⚙️ Configuração

### Variáveis de ambiente
```bash
# No arquivo .env
DASHBOARD_PORT=5000          # Porta do dashboard
DASHBOARD_HOST=0.0.0.0       # Host (0.0.0.0 = acessível externamente)
FEED_ID=default              # Feed a monitorar
```

### Portas
- **5000**: Dashboard web (padrão)
- **22**: SSH da VM
- **Outras**: Portas dos bots (se configuradas)

## 🔧 Acesso Remoto

### 1. Configurar firewall (se necessário)
```bash
# Ubuntu/Debian
sudo ufw allow 5000

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

### 2. Acessar de outro computador
```
http://IP_DA_VM:5000
```

### 3. Descobrir IP da VM
```bash
# Na VM
hostname -I
# ou
ip addr show
```

## 🎨 Interface

- **Design responsivo**: Funciona em desktop e mobile
- **Tema escuro**: Interface moderna e elegante
- **Atualização automática**: Dados atualizados a cada 30 segundos
- **Indicadores visuais**: Status coloridos para fácil identificação

## 🛠️ Desenvolvimento

### Estrutura dos arquivos
```
web_dashboard.py              # Servidor Flask principal
templates/
  └── dashboard.html          # Interface web
requirements_dashboard.txt    # Dependências
start_dashboard.sh            # Script de inicialização (VM aberta)
start_dashboard_tmux.sh       # Script para tmux (VM pode fechar)
stop_dashboard.sh             # Script para parar dashboard
monitor_dashboard.sh          # Script para monitorar status
```

### Comandos tmux
```bash
# Iniciar dashboard em tmux
./start_dashboard_tmux.sh

# Parar dashboard
./stop_dashboard.sh

# Ver status
./monitor_dashboard.sh

# Conectar à sessão (ver logs)
tmux attach -t dashboard_web

# Sair da sessão sem parar (Ctrl+B depois D)
# Ou simplesmente fechar o terminal
```

### APIs disponíveis
- `GET /api/stats/system` - Estatísticas do sistema
- `GET /api/stats/users` - Estatísticas dos usuários
- `GET /api/stats/alerts` - Estatísticas dos alertas
- `GET /api/stats/feeds` - Status dos feeds
- `GET /api/logs` - Logs recentes
- `POST /api/actions/restart_feed` - Reiniciar feed

## 🔒 Segurança

⚠️ **Importante**: O dashboard não tem autenticação por padrão. Para uso em produção:

1. **Configurar proxy reverso** (nginx/apache)
2. **Adicionar autenticação** (Basic Auth, JWT, etc.)
3. **Usar HTTPS** (certificado SSL)
4. **Restringir acesso** por IP

## 🐛 Troubleshooting

### Dashboard não inicia
```bash
# Verificar dependências
pip install -r requirements_dashboard.txt

# Verificar porta
netstat -tlnp | grep 5000
```

### Não consegue acessar externamente
```bash
# Verificar firewall
sudo ufw status

# Verificar se está rodando em 0.0.0.0
ps aux | grep web_dashboard
```

### Dados não aparecem
```bash
# Verificar banco de dados
ls -la data/default/bot.db

# Verificar logs
tail -f logs/listener_default.log
```

## 📱 Mobile

O dashboard é totalmente responsivo e funciona perfeitamente em:
- 📱 Smartphones
- 📱 Tablets
- 💻 Desktops
- 🖥️ Laptops

## 🎯 Próximas funcionalidades

- [ ] Autenticação de usuários
- [ ] Controle de feeds (start/stop)
- [ ] Gráficos de performance
- [ ] Notificações push
- [ ] Export de dados
- [ ] Configurações via web
