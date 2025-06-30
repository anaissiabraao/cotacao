# 🚀 GeRot Enterprise - Sistema de Gerenciamento de Rotinas

## 📋 Sobre o Projeto

**GeRot Enterprise** é um sistema completo de gerenciamento de rotinas empresariais desenvolvido para a **Portoex Solutions**. O sistema oferece controle hierárquico, dashboards interativos, notificações push e integração com dados corporativos.

## ✨ Funcionalidades Implementadas

### 🏢 **Estrutura Empresarial Hierárquica**
- **Admin Master**: Visão completa de todos os setores
- **Líderes**: Controle e gestão de seus setores
- **Colaboradores**: Gerenciamento de tarefas pessoais

### 🌐 **Autenticação Avançada**
- **OAuth Google**: Login com contas `@portoex.com.br`
- **Autenticação tradicional**: Login/senha
- **Validação de domínio**: Segurança empresarial

### 📱 **PWA (Progressive Web App)**
- **Instalação nativa**: iOS e Android
- **Offline support**: Funciona sem internet
- **Push notifications**: Notificações em tempo real
- **Design responsivo**: Mobile-first

### 📊 **Dashboards e Relatórios**
- **Gráficos interativos**: Plotly.js + Chart.js
- **Métricas em tempo real**: Produtividade e KPIs
- **Relatórios avançados**: Por setor e usuário
- **Integração Excel**: Dados corporativos

### 🔧 **APIs REST Completas**
- `/api/users` - Gestão de usuários
- `/api/sectors` - Controle de setores
- `/api/routines` - Rotinas e tarefas
- `/api/reports` - Relatórios dinâmicos

## 🚀 Como Executar

### 📋 Pré-requisitos
- Python 3.8+
- Ambiente virtual (venv)

### ⚡ Execução Rápida

```bash
# 1. Ativar ambiente virtual
.\.venv\Scripts\Activate

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Executar versão de produção
python app_production.py

# 4. Acessar no navegador
http://localhost:5000
```

### 🔐 Credenciais de Acesso

- **Admin Master**: `admin_master` / `admin123!@#`
- **OAuth Google**: Qualquer email `@portoex.com.br`

## 🏗️ Arquitetura do Sistema

### 📁 Estrutura de Arquivos

```
GeRot/
├── app_production.py          # Aplicação principal de produção
├── app_enterprise.py          # Versão empresarial
├── config_production.py       # Configurações de produção
├── dados.xlsx                 # Base de dados corporativa
├── requirements.txt           # Dependências Python
├── render.yaml               # Configuração deploy Render
├── static/
│   ├── manifest.json         # PWA manifest
│   └── icons/               # Ícones do app
├── templates/
│   ├── enterprise_login.html          # Login empresarial
│   ├── admin_dashboard_advanced.html  # Dashboard avançado
│   ├── admin_master_dashboard.html    # Admin master
│   ├── leader_dashboard.html          # Líderes
│   └── team_dashboard.html           # Colaboradores
└── docs/                     # Documentação
```

### 🏢 Setores Configurados

1. **Administrativo** - Gestão geral
2. **Comercial** - Vendas e relacionamento  
3. **Operacional** - Logística e operações
4. **Financeiro** - Controladoria
5. **TI** - Tecnologia da informação
6. **Comércio Exterior** - Import/Export
7. **Segurança** - Segurança portuária

### 📊 Base de Dados

O arquivo `dados.xlsx` contém:
- **100 colaboradores** distribuídos nos setores
- **3 planilhas**: Colaboradores, Resumo_Setores, Metas_2025
- **Integração automática** com dashboards

## 🌐 Deploy no Render

### ⚙️ Configuração Automática

O arquivo `render.yaml` está configurado para deploy automático:

```yaml
services:
  - type: web
    name: gerot-enterprise
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app_production:app
```

### 🔑 Variáveis de Ambiente

```bash
FLASK_ENV=production
SECRET_KEY=auto-generated
GOOGLE_OAUTH_CLIENT_ID=configured
GOOGLE_OAUTH_CLIENT_SECRET=configured
VAPID_PRIVATE_KEY=configured
VAPID_PUBLIC_KEY=configured
```

## 📱 Funcionalidades Mobile

### 📲 PWA Features
- **Instalação**: Adicionar à tela inicial
- **Offline**: Cache de dados essenciais
- **Push**: Notificações em tempo real
- **Native feel**: Interface como app nativo

### 🔔 Notificações Push

O sistema envia notificações para:
- ✅ Novas tarefas atribuídas
- 🎯 Metas atingidas
- 📊 Relatórios disponíveis
- 👥 Atividades da equipe

## 🎯 APIs Disponíveis

### 👥 Usuários
```http
GET /api/users              # Listar usuários
GET /api/users/{id}         # Detalhes do usuário
```

### 🏢 Setores
```http
GET /api/sectors            # Listar setores
```

### 📋 Rotinas
```http
GET /api/routines           # Rotinas do dia
```

### 📊 Relatórios
```http
GET /api/reports                    # Relatório geral
GET /api/reports/productivity       # Produtividade
GET /api/reports/sectors           # Por setores
GET /api/reports/goals             # Metas
```

## 🔧 Tecnologias Utilizadas

### 🐍 Backend
- **Flask 2.3.3** - Framework web
- **SQLite** - Banco de dados
- **Flask-Dance** - OAuth Google
- **Pandas** - Manipulação Excel
- **Plotly** - Gráficos interativos
- **PyWebPush** - Notificações push

### 🎨 Frontend
- **HTML5/CSS3** - Interface moderna
- **JavaScript ES6** - Interatividade
- **Chart.js** - Gráficos
- **PWA APIs** - Funcionalidades nativas

### ☁️ Deploy
- **Render** - Hospedagem
- **Gunicorn** - Servidor WSGI
- **PostgreSQL** - Banco produção

## 📈 Próximas Funcionalidades

- [ ] **Analytics avançados** - Métricas detalhadas
- [ ] **Integração WhatsApp** - Notificações
- [ ] **Exports PDF** - Relatórios
- [ ] **Backup automático** - Segurança
- [ ] **Multi-idiomas** - Internacionalização

## 🤝 Contribuição

1. Fork do projeto
2. Criar branch (`git checkout -b feature/nova-funcionalidade`)
3. Commit (`git commit -am 'Adiciona nova funcionalidade'`)
4. Push (`git push origin feature/nova-funcionalidade`)
5. Pull Request

## 📞 Suporte

- **Email**: admin@portoex.com.br
- **Sistema**: GeRot Enterprise v2.0
- **Empresa**: Portoex Solutions

## 📄 Licença

Este projeto está licenciado sob a MIT License - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

**🎉 GeRot Enterprise - Transformando a gestão de rotinas corporativas!**

Desenvolvido com ❤️ para **Portoex Solutions**

# 🚛 Sistema de Cotação de Fretes - Portoex Solutions

## 📋 Sobre o Projeto

Sistema completo de cotação de fretes desenvolvido para a **Portoex Solutions**. O sistema oferece cálculos precisos para fretes fracionados, dedicados e aéreos, com interface moderna e intuitiva.

## ✨ Funcionalidades Principais

### 🌐 **All In - Cotação Unificada**
- Cálculo simultâneo de todas as modalidades
- Comparativo visual entre opções
- Calculadora de volumes avançada
- Validação de capacidades em tempo real

### 📦 **Frete Fracionado**
- Agente + Transferência + Agente
- Agente Direto
- Cálculo de GRIS
- Validação de peso e volume

### 🚛 **Frete Dedicado**
- 8 tipos de veículos com capacidades:
  - FIORINO: 500 kg / 1,2 m³
  - VAN: 1.500 kg / 6 m³
  - VUC: 3.000 kg / 15 m³
  - 3/4: 3.500 kg / 12 m³
  - TOCO: 7.000 kg / 40 m³
  - TRUCK: 12.000 kg / 70 m³
  - CARRETA: 28.000 kg / 110 m³
  - CARRETA LS: 30.000 kg / 120 m³
- Custos operacionais detalhados
- Margens comerciais personalizadas
- Validação visual de capacidade

### ✈️ **Frete Aéreo**
- Integração com GOLLOG
- Cálculo de taxas e impostos
- Prazos estimados
- Rotas otimizadas

### 🧮 **Calculadora de Volumes**
- Cálculo simples (L x A x C)
- Modo avançado multi-SKU
- Validação em tempo real
- Conversão automática

### 📊 **Análises e Relatórios**
- Histórico de cotações
- Dashboard interativo
- Métricas de utilização
- Exportação de dados

## 🚀 Como Executar

### 📋 Pré-requisitos
- Python 3.8+
- Ambiente virtual (venv)
- Dependências no requirements.txt

### ⚡ Execução Rápida

```bash
# 1. Clonar o repositório
git clone https://github.com/portoex/cotacao.git

# 2. Criar e ativar ambiente virtual
python -m venv .venv
.\.venv\Scripts\activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Executar a aplicação
python app.py

# 5. Acessar no navegador
http://localhost:5000
```

## 🏗️ Estrutura do Projeto

```
cotacao/
├── app.py                    # Aplicação principal
├── improved_chico_automate_fpdf.py  # Processamento de fretes
├── Base_Unificada.xlsx      # Base de dados
├── requirements.txt         # Dependências
├── static/
│   ├── js/
│   │   ├── chico_automate.js    # Lógica frontend
│   │   └── correcao_mapa_dedicado.js
│   └── images/
├── templates/
│   ├── index.html          # Interface principal
│   ├── admin.html         # Painel admin
│   └── login.html         # Autenticação
└── docs/                  # Documentação
```

## 🔧 Tecnologias Utilizadas

### 🐍 Backend
- **Flask** - Framework web
- **Pandas** - Processamento de dados
- **FPDF2** - Geração de PDFs
- **Requests** - Integração APIs

### 🎨 Frontend
- **JavaScript ES6** - Interatividade
- **Leaflet** - Mapas interativos
- **Chart.js** - Gráficos
- **Select2** - Campos de busca

### 📊 Dados
- **Excel** - Base de dados
- **SQLite** - Cache e histórico
- **APIs** - Integração externa

## 📈 Próximas Atualizações

- [ ] **Cotações em lote** - Múltiplos cálculos
- [ ] **API REST** - Integração sistemas
- [ ] **Mobile app** - Versão Android/iOS
- [ ] **Relatórios avançados** - Business Intelligence

## 📄 Licença

Este projeto está sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

**🚛 Sistema de Cotação - Portoex Solutions**

Desenvolvido com ❤️ para **Portoex Solutions**
