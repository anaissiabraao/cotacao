# 🚀 Deploy no Render.com - Guia Completo

## ✅ Problemas Corrigidos

### 1. **Incompatibilidade pandas/numpy**
- ✅ **Corrigido**: Versões compatíveis no `requirements.txt`
- ✅ **numpy**: `1.24.3`
- ✅ **pandas**: `2.0.3`

### 2. **Configuração de Produção**
- ✅ **render.yaml**: Configuração específica do Render
- ✅ **Base_Unificada.xlsx**: Arquivo de dados incluído para demo
- ✅ **Gunicorn**: Servidor WSGI configurado

## 📋 Passo a Passo para Deploy

### **1. Conectar Repositório no Render**
1. Acesse [render.com](https://render.com)
2. Clique em **"New +"** → **"Web Service"**
3. Conecte seu GitHub e selecione: `anaissiabraao/cotacao`

### **2. Configurações do Deploy**
```
Name: portoex
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

### **3. Variáveis de Ambiente**
```
SECRET_KEY = [auto-gerado pelo Render]
DEBUG = False
FLASK_ENV = production
PYTHON_VERSION = 3.11.11
```

### **4. Configurações Avançadas**
- **Plan**: Free
- **Python Version**: 3.11.11
- **Health Check Path**: `/`
- **Auto-Deploy**: Yes

## 🔧 Arquivos de Configuração

### **requirements.txt** (Atualizado)
```
Flask==2.3.3
numpy==1.24.3
pandas==2.0.3
openpyxl==3.1.2
requests==2.31.0
fpdf2==2.7.5
python-dotenv==1.0.0
polyline==2.0.0
matplotlib==3.7.2
Werkzeug==2.3.7
Jinja2==3.1.2
gunicorn==21.2.0
xlsxwriter==3.1.6
unicodedata2==15.1.0
```

### **Procfile**
```
web: gunicorn app:app
```

### **render.yaml**
```yaml
services:
  - type: web
    name: portoex
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.11
      - key: SECRET_KEY
        generateValue: true
      - key: DEBUG
        value: False
      - key: FLASK_ENV
        value: production
    healthCheckPath: /
```

## 🎯 URL Final
Após deploy bem-sucedido, sua aplicação estará disponível em:
```
https://cotacao-9sd1.onrender.com
```

## 🔐 Credenciais de Acesso
- **Comercial**: `comercial.ptx` / `ptx@123`
- **Admin**: `adm.ptx` / `portoex@123`

## 📊 Funcionalidades Disponíveis em Produção
- ✅ Sistema de login
- ✅ Cálculo de frete dedicado
- ✅ Cálculo de frete fracionado
- ✅ Modal aéreo
- ✅ Exportação PDF/Excel
- ✅ Painel administrativo
- ✅ Histórico de consultas

## 🛠 Troubleshooting

### **Se o deploy falhar**:
1. Verifique os logs no dashboard do Render
2. Confirme que o repositório está atualizado
3. Verifique se o Python 3.11 está sendo usado

### **Se a aplicação não carregar**:
1. Verifique se o `Base_Unificada.xlsx` foi incluído
2. Confirme as variáveis de ambiente
3. Verifique os logs de runtime

## 📝 Notas de Produção
- **Dados de Demo**: O arquivo `Base_Unificada.xlsx` incluído contém dados de exemplo
- **Performance**: Primeira requisição pode ser lenta (cold start)
- **Limites**: Plano gratuito tem limitações de CPU/memória
- **SSL**: HTTPS habilitado automaticamente

## 🔄 Atualizações Futuras
Para atualizações:
1. Faça commit das mudanças localmente
2. Push para GitHub: `git push origin master`
3. Render fará deploy automaticamente

**🎉 Seu projeto PortoEx estará online e funcionando!** 