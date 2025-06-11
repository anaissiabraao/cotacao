# Guia de Deploy - PortoEx

## Pré-requisitos
- Python 3.8+
- Git
- Arquivo `Base_Unificada.xlsx`

## Deploy Local

### 1. Configuração do Ambiente
```bash
# Clone o repositório
git clone https://github.com/seu-usuario/portoex.git
cd portoex

# Crie ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
# ou
source venv/bin/activate  # Linux/Mac

# Instale dependências
pip install -r requirements.txt
```

### 2. Configuração
```bash
# Copie arquivo de ambiente
copy env.example .env  # Windows
# ou
cp env.example .env    # Linux/Mac

# Configure Base_Unificada.xlsx
# Coloque o arquivo na raiz do projeto
```

### 3. Execução
```bash
python app.py
```

## Deploy com Docker

### 1. Build da Imagem
```bash
docker build -t portoex .
```

### 2. Execução
```bash
docker run -p 5000:5000 -v $(pwd)/Base_Unificada.xlsx:/app/Base_Unificada.xlsx portoex
```

## Deploy no Heroku

### 1. Preparação
```bash
# Instale Heroku CLI
# Faça login
heroku login
```

### 2. Criação do App
```bash
# Crie app
heroku create seu-app-portoex

# Configure variáveis
heroku config:set SECRET_KEY=sua_chave_secreta
heroku config:set FLASK_ENV=production
```

### 3. Deploy
```bash
git push heroku main
```

### 4. Upload do Excel
Use o dashboard do Heroku para fazer upload do arquivo `Base_Unificada.xlsx`.

## Deploy em VPS (Ubuntu)

### 1. Configuração do Servidor
```bash
# Atualize sistema
sudo apt update && sudo apt upgrade -y

# Instale Python e dependências
sudo apt install python3 python3-pip python3-venv nginx -y
```

### 2. Configuração da Aplicação
```bash
# Clone repositório
git clone https://github.com/seu-usuario/portoex.git
cd portoex

# Configure ambiente
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure arquivo .env
cp env.example .env
nano .env
```

### 3. Configuração do Nginx
```nginx
server {
    listen 80;
    server_name seu-dominio.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. Configuração do Systemd
```ini
[Unit]
Description=PortoEx Flask App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/path/to/portoex
Environment=PATH=/path/to/portoex/venv/bin
ExecStart=/path/to/portoex/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

## Configurações de Produção

### Variáveis de Ambiente
```env
SECRET_KEY=chave_muito_segura_aleatoria
DEBUG=False
FLASK_ENV=production
PORT=5000
```

### Banco de Dados
O sistema usa SQLite por padrão. Para produção, considere PostgreSQL:
```env
DATABASE_URL=postgresql://user:pass@localhost/portoex
```

## Monitoramento

### Logs
```bash
# Visualizar logs
tail -f logs/app.log

# Logs do sistema
journalctl -u portoex -f
```

### Saúde da Aplicação
- Endpoint: `GET /health`
- Monitoramento de CPU/Memória
- Alertas por email/Slack

## Backup

### Arquivos Importantes
- `Base_Unificada.xlsx`
- `sistema_logs.db`
- Configurações `.env`

### Script de Backup
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf backup_$DATE.tar.gz Base_Unificada.xlsx sistema_logs.db .env
```

## Troubleshooting

### Problemas Comuns
1. **Arquivo Excel não encontrado**
   - Verifique caminho do `Base_Unificada.xlsx`
   
2. **Erro de permissão**
   - Verifique permissões das pastas
   
3. **Falha na geocodificação**
   - Verifique conexão com internet
   - APIs externas podem estar indisponíveis

### Logs de Debug
```python
# Ative debug no .env
DEBUG=True

# Verifique logs no terminal
``` 