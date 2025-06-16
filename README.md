# PortoEx - Sistema de Gestão de Fretes

Sistema abrangente de gestão e cotação de fretes para empresas de logística, desenvolvido com Flask e integração com múltiplas fontes de dados.

## 🚀 Funcionalidades

### Cálculo de Fretes
- **Frete Fracionado**: Cotação inteligente usando dados reais da planilha Base_Unificada.xlsx
- **Frete Dedicado**: Cálculo por tipo de veículo (Fiorino, Van, 3/4, Toco, Truck, Carreta)
- **Frete Aéreo**: Integração com base GOLLOG para modal aéreo

### Recursos Avançados
- **Múltiplas Fontes**: Integração com planilhas Excel e APIs externas
- **Geolocalização**: Cálculo de rotas reais com OSRM e OpenRoute
- **Mapeamento**: Visualização de rotas no mapa com Leaflet
- **Ranking**: Sistema de ranking por melhor custo-benefício
- **Histórico**: Controle completo de cotações com IDs únicos
- **Exportação**: PDF e Excel com gráficos e análises

### Sistema de Usuários
- **Autenticação**: Sistema seguro com sessões
- **Níveis de Acesso**: Comercial e Administrador
- **Logs**: Rastreamento completo de atividades
- **Dashboard**: Painel administrativo com estatísticas

## 🛠️ Tecnologias

- **Backend**: Python Flask
- **Frontend**: HTML5, CSS3, JavaScript
- **Dados**: Pandas, Excel (openpyxl)
- **Mapas**: Leaflet, OSRM, OpenRoute
- **PDF**: FPDF com gráficos matplotlib
- **Banco**: SQLite para logs
- **Deploy**: Docker, Heroku ready

## 📋 Pré-requisitos

- Python 3.8+
- Arquivo `Base_Unificada.xlsx` com dados de frete
- Conexão com internet para APIs de geolocalização

## 🔧 Instalação

1. **Clone o repositório**
   ```bash
   git clone https://github.com/seu-usuario/portoex.git
   cd portoex
   ```

2. **Crie o ambiente virtual**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # ou
   venv\Scripts\activate     # Windows
   ```

3. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure variáveis de ambiente**
   ```bash
   cp .env.example .env
   # Edite o .env com suas configurações
   ```

5. **Execute a aplicação**
   ```bash
   python app.py
   ```

6. **Acesse o sistema**
   - URL: `http://localhost:5000`
   - Login comercial: `comercial.ptx` / `ptx@123`
   - Login admin: `adm.ptx` / `portoex@123`

## 📁 Estrutura do Projeto

```
portoex/
├── app.py                          # Aplicação principal Flask
├── requirements.txt                # Dependências Python
├── Dockerfile                      # Container Docker
├── Procfile                       # Deploy Heroku
├── .env.example                   # Variáveis de ambiente
├── Base_Unificada.xlsx           # Base de dados de frete
├── templates/                     # Templates HTML
│   ├── index.html                # Página principal
│   ├── login.html                # Página de login
│   ├── admin.html                # Dashboard administrativo
│   ├── admin_logs.html           # Visualização de logs
│   ├── admin_historico.html      # Histórico detalhado
│   └── admin_setup.html          # Configurações
├── static/                       # Arquivos estáticos
│   ├── js/
│   │   ├── chico_automate.js     # JavaScript principal
│   │   └── correcao_mapa_dedicado.js
│   └── images/
│       └── portoex-logo.png      # Logo da empresa
├── utils/                        # Utilitários
│   ├── geocoding.py             # Funções de geolocalização
│   ├── calculations.py          # Cálculos de frete
│   └── data_processing.py       # Processamento de dados
└── docs/                         # Documentação
    ├── API.md                   # Documentação da API
    ├── DEPLOYMENT.md            # Guia de deploy
    └── CHANGELOG.md             # Histórico de versões
```

## 🗃️ Base de Dados

### Base_Unificada.xlsx
Estrutura esperada da planilha:
- **Coluna A**: Modalidade
- **Coluna B**: Agente/Fornecedor
- **Coluna C**: Origem
- **Coluna D**: Base Origem
- **Coluna E**: Destino
- **Coluna F-N**: Faixas de peso (10kg, 20kg, 30kg, etc.)
- **Coluna O**: Pedágio por 100kg
- **Coluna P**: GRIS Mínimo
- **Coluna Q**: GRIS Excedente (%)
- **Coluna R**: Prazo (dias)

## 🔧 Configuração

### Variáveis de Ambiente (.env)
```env
SECRET_KEY=sua_chave_secreta_muito_segura
DEBUG=False
PORT=5000
FLASK_ENV=production
DATABASE_URL=sqlite:///sistema_logs.db
```

### Usuários do Sistema
```python
USUARIOS_SISTEMA = {
    'comercial.ptx': {
        'senha': '***',
        'tipo': 'comercial',
        'permissoes': ['calcular', 'historico', 'exportar']
    },
    'adm.ptx': {
        'senha': '***',
        'tipo': 'administrador',
        'permissoes': ['calcular', 'historico', 'exportar', 'logs', 'setup', 'admin']
    }
}
```

## 🚀 Deploy

### Docker
```bash
docker build -t portoex .
docker run -p 5000:5000 portoex
```

### Heroku
```bash
heroku create seu-app-portoex
git push heroku main
```

## 📊 API Endpoints

### Autenticação
- `POST /login` - Login de usuário
- `GET /logout` - Logout

### Cálculos
- `POST /calcular` - Frete dedicado
- `POST /calcular_frete_fracionado` - Frete fracionado  
- `POST /calcular_aereo` - Frete aéreo

### Dados
- `GET /estados` - Lista de estados
- `GET /municipios/<uf>` - Municípios por UF
- `GET /historico` - Histórico de cotações

### Exportação
- `POST /gerar-pdf` - Exportar PDF
- `POST /exportar-excel` - Exportar Excel

### Administração (Requer permissão admin)
- `GET /admin` - Dashboard
- `GET /admin/logs` - Logs do sistema
- `POST /admin/limpar-logs` - Limpar logs

## 🧪 Testes

```bash
# Executar testes
python -m pytest tests/

# Teste de funcionamento básico
python test_request.py
```

## 📝 Licença

Este projeto está sob licença proprietária. Todos os direitos reservados à PortoEx.

## 👥 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/NovaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona NovaFeature'`)
4. Push para a branch (`git push origin feature/NovaFeature`)
5. Abra um Pull Request

## 📞 Suporte

Para suporte técnico, entre em contato:
- Email: abraao.anaissi@portoex.com.br
- Telefone: (47) 98839-5126

## 📈 Roadmap

- [ ] Integração com mais transportadoras
- [ ] API REST completa
- [ ] Dashboard analítico avançado
- [ ] Mobile app
- [ ] Integração com ERP

---

**PortoEx** - Transformando a logística brasileira 🚛📦 
