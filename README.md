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

## 📞 Suporte

- **Email**: abraao.anaissi@portoex.com.br
- **Sistema**: Anaissi Data Strategy
- **Empresa**: Portoex Solutions  

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

Desenvolvido por DEV - Abraão Anaissi para **Portoex Solutions**
