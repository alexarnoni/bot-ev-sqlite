# Bot EV+ v3.0 - Docker Configuration
FROM python:3.11-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    sqlite3 \
    tmux \
    && rm -rf /var/lib/apt/lists/*

# Definir diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Criar diretórios necessários
RUN mkdir -p data/global data/default data/feed1 data/feed2 data/feed3 data/feed4 logs

# Definir variáveis de ambiente padrão
ENV FEED_ID=default
ENV PYTHONUNBUFFERED=1

# Expor porta para dashboard web (opcional)
EXPOSE 8080

# Script de inicialização
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Comando padrão
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
