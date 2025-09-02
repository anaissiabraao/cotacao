# 🔧 Variáveis de Ambiente - Render

## 📋 Variáveis Necessárias

Configure estas variáveis no painel do Render:

### 🔑 **Obrigatórias:**

| CHAVE | VALOR | Descrição |
|-------|-------|-----------|
| `DATABASE_URL` | `postgresql://...` | URL do PostgreSQL (criada automaticamente pelo Render) |
| `SECRET_KEY` | `sua_chave_secreta_aqui` | Chave secreta para sessões Flask |
| `FLASK_ENV` | `production` | Ambiente Flask (production/development) |
| `PYTHON_VERSION` | `3.11.11` | Versão do Python |

### 🔧 **Opcionais:**

| CHAVE | VALOR | Descrição |
|-------|-------|-----------|
| `DEBUG` | `False` | Modo debug (False em produção) |
| `WEB_CONCURRENCY` | `4` | Número de workers Gunicorn |

## 🚀 **Como Configurar:**

### **1. No Painel do Render:**
1. Acesse seu projeto no Render
2. Vá em **Environment** → **Environment Variables**
3. Adicione cada variável:

### **2. DATABASE_URL (Automática):**
- ✅ Criada automaticamente pelo Render
- Formato: `postgresql://user:password@host:port/database`

### **3. SECRET_KEY (Manual):**
- Gere uma chave secreta forte
- Exemplo: `portoex_secret_key_2025_abc123xyz789`

### **4. FLASK_ENV (Manual):**
- Valor: `production`
- Para desenvolvimento: `development`

## 🔍 **Verificação:**

Após configurar, a aplicação deve mostrar:
```
[CONFIG] ✅ DATABASE_URL encontrado: postgresql://...
[CONFIG] ✅ PostgreSQL de desenvolvimento disponível
[POSTGRESQL] ✅ Conexão com PostgreSQL estabelecida
[POSTGRESQL] 📊 Total de registros na base: X
```

## ❌ **Problemas Comuns:**

### **Erro: `name 'text' is not defined`**
- ✅ **Corrigido**: Import adicionado no topo do arquivo

### **Erro: `DATABASE_URL not found`**
- Verifique se a variável está configurada no Render
- Nome exato: `DATABASE_URL` (maiúsculas)

### **Erro: `connection refused`**
- Aguarde o PostgreSQL inicializar (pode levar alguns minutos)
- Verifique se o serviço PostgreSQL está ativo

## 📊 **Status das Variáveis:**

- ✅ `DATABASE_URL` - Automática pelo Render
- ✅ `SECRET_KEY` - Manual (configurar)
- ✅ `FLASK_ENV` - Manual (configurar)
- ✅ `PYTHON_VERSION` - Manual (configurar)
- ⚠️ `DEBUG` - Opcional (False em produção)
- ⚠️ `WEB_CONCURRENCY` - Opcional (4)

## 🎯 **Próximos Passos:**

1. **Configure as variáveis** no painel do Render
2. **Faça deploy** das correções
3. **Teste a conexão** via painel admin
4. **Adicione dados reais** via interface
