# 🚛 PortoEx - Sistema de Cotação de Fretes

Sistema moderno e configurável para cotação de fretes com interface web completa e banco de dados PostgreSQL.

## 🎯 Características

- ✅ **Interface Web Completa** - Gestão total via navegador
- ✅ **PostgreSQL Integrado** - Base de dados robusta
- ✅ **Sistema Configurável** - Fórmulas editáveis via interface
- ✅ **Importação CSV** - Upload automático de dados
- ✅ **Memórias de Cálculo** - Lógicas preservadas e configuráveis
- ✅ **Código Saneado** - 93.6% menos linhas que a versão anterior

## 🚀 Instalação Rápida

### 1. Clonar Repositório
```bash
git clone [url-do-repositorio]
cd cotacao
```

### 2. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 3. Configurar PostgreSQL
```bash
# Criar banco de dados
createdb base_unificada

# Criar usuário
psql -c "CREATE USER cotacao WITH PASSWORD '1234';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE base_unificada TO cotacao;"
```

### 4. Configurar Variáveis de Ambiente
```bash
cp env.example .env
# Editar .env com suas configurações
```

### 5. Executar Sistema
```bash
python app2.py
```

Acesse: `http://localhost:8000`

## 📊 Estrutura do Projeto

```
cotacao/
├── app2.py                    # Aplicação principal (580 linhas)
├── models.py                  # Modelos PostgreSQL
├── config.py                  # Configurações
├── requirements.txt           # Dependências
├── static/                    # Arquivos estáticos
│   ├── css/style.css
│   ├── js/chico_automate.js
│   └── portoex-logo.png
├── templates/                 # Templates HTML
│   ├── index.html             # Página principal
│   ├── login.html             # Login
│   ├── admin_melhorado.html   # Dashboard admin
│   ├── admin_base_dados.html  # Gestão da base
│   ├── admin_calculadoras.html # Configurar fórmulas
│   └── admin_agentes_memoria.html # Memórias de cálculo
└── data/                      # Dados (vazio - usa PostgreSQL)
```

## 🖥️ Funcionalidades

### **📊 Dashboard Administrativo**
- Estatísticas em tempo real
- Logs de atividades
- Interface moderna e responsiva

### **🗄️ Gestão da Base de Dados**
- Visualizar 20.000+ registros
- Edição inline de valores
- Importação CSV automática
- Exportação para backup

### **🧮 Calculadoras Configuráveis**
- Tipos de cálculo personalizáveis
- Fórmulas matemáticas editáveis
- Configurações por agente
- Testes em tempo real

### **🧠 Memórias de Cálculo**
- Lógicas de agentes preservadas
- Configurações de GRIS, pedágio, seguro
- Sistema híbrido (banco + fallback)

## 🎯 Uso do Sistema

### **Para Operadores:**
1. Acesse `http://localhost:8000`
2. Faça login
3. Consulte fretes normalmente
4. Configure via `/admin` se necessário

### **Para Administradores:**
1. Acesse `http://localhost:8000/admin`
2. Gerencie base de dados
3. Configure calculadoras
4. Monitore sistema

## 🔧 APIs Disponíveis

### **Cálculo de Fretes:**
- `POST /calcular_frete_fracionado` - Frete fracionado
- `POST /calcular` - Frete dedicado  
- `POST /calcular_aereo` - Frete aéreo

### **Administração:**
- `GET /api/admin/base-dados` - Listar dados
- `POST /api/admin/base-dados/importar` - Importar CSV
- `GET /api/admin/agentes-memoria` - Memórias de cálculo

## 🚀 Deploy

### **Render (Recomendado):**
```bash
# O arquivo render.yaml está configurado
# Apenas faça push para o repositório conectado
```

### **Docker:**
```bash
docker build -t portoex .
docker run -p 8000:8000 portoex
```

### **Produção:**
```bash
gunicorn --config gunicorn.conf.py app2:app
```

## 🛡️ Segurança

- ✅ Validação de dados de entrada
- ✅ Sanitização de consultas SQL
- ✅ Logs de auditoria completos
- ✅ Backup automático antes de importações

## 📈 Performance

- ✅ Cache inteligente de consultas
- ✅ Paginação otimizada
- ✅ Consultas PostgreSQL otimizadas
- ✅ Interface responsiva

## 🆘 Suporte

### **Problemas Comuns:**

**PostgreSQL não conecta:**
```bash
# Verificar se PostgreSQL está rodando
# Verificar credenciais em .env
# Verificar permissões do usuário cotacao
```

**Dados não aparecem:**
```bash
# Verificar se base_unificada tem dados
# Usar importação CSV se necessário
# Verificar logs no console
```

## 📝 Changelog

### v2.0.0 (Atual)
- ✅ Sistema completamente saneado
- ✅ Código reduzido em 93.6%
- ✅ PostgreSQL como única fonte de dados
- ✅ Interface web completa
- ✅ Sistema de importação CSV
- ✅ Memórias de cálculo configuráveis

## 📄 Licença

MIT License - Veja arquivo LICENSE para detalhes.

---

**Sistema PortoEx - Versão Saneada e Otimizada** 🚀