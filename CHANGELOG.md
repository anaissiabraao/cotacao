# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-07-01

### Adicionado
- Script `fix_and_run.py` para correção automática e execução da aplicação
- Script `test_app.py` para testes em desenvolvimento
- Fallback robusto para frete fracionado quando não há rotas com agentes
- Tratamento completo de erros HTTP 520
- Resposta estruturada sempre retornada, mesmo sem rotas disponíveis
- Orientações informativas para usuário quando sistema não encontra rotas

### Corrigido
- **CRÍTICO**: Erro HTTP 520 no cálculo de frete fracionado eliminado
- Problemas de indentação na função `geocode`
- Exibição incorreta do nome da rota ao invés do agente na seção "All In - Coleta"
- Geocodificação mais robusta com múltiplos fallbacks
- Coordenadas sempre retornadas (nunca None)

### Melhorado
- Sistema de fallback para quando não há agentes disponíveis
- Interface mais informativa com sugestões claras ao usuário
- Tratamento de exceções mais robusto em todo o sistema
- Logs mais detalhados para debugging
- Experiência do usuário mais consistente
- Performance na inicialização da aplicação

### Técnico
- Fallbacks em cascata: Cache → API → Estados → Brasília
- Sanitização de dados JSON mais robusta
- Validação de entrada melhorada
- Estrutura de resposta padronizada
- Compatibilidade com mobile mantida

## [1.1.0] - 2025-01-20

### Adicionado
- Aba "All In" para cotação unificada de todas as modalidades
- Calculadora de volumes avançada em todas as abas
- Exibição de capacidade de carga e volume para cada veículo
- Validação visual de capacidade excedida nos veículos
- Detalhamento de custos operacionais por veículo
- Margens comerciais personalizadas por tipo de veículo
- Interface interativa para seleção de veículos

### Melhorado
- Layout responsivo em todas as abas
- Feedback visual para usuário em todas as interações
- Performance no cálculo de rotas e custos
- Organização do código e documentação

## [1.0.0] - 2025-01-15

### Adicionado
- Sistema completo de gestão de fretes
- Cálculo de frete fracionado com dados reais da Base_Unificada.xlsx
- Cálculo de frete dedicado por tipo de veículo
- Cálculo de frete aéreo com base GOLLOG
- Sistema de autenticação e controle de acesso
- Dashboard administrativo com logs e estatísticas
- Geolocalização e cálculo de rotas reais
- Mapeamento interativo com Leaflet
- Sistema de ranking por custo-benefício
- Exportação para PDF e Excel com gráficos
- Histórico de cotações com IDs únicos
- Integração com APIs externas (OSRM, OpenRoute)
- Interface responsiva e intuitiva
- Sistema de logs completo
- Suporte a Docker e Heroku

### Funcionalidades Principais
- **Frete Fracionado**: Dados reais da planilha Excel
- **Frete Dedicado**: 6 tipos de veículos
- **Frete Aéreo**: Base GOLLOG integrada
- **Usuários**: Comercial e Administrador
- **Mapa**: Rotas reais visualizadas
- **Ranking**: Melhor custo-benefício
- **Exportação**: PDF e Excel
- **API**: RESTful completa

### Tecnologias
- Backend: Python Flask 2.3.3
- Frontend: HTML5, CSS3, JavaScript
- Dados: Pandas, Excel
- Mapas: Leaflet, OSRM
- Deploy: Docker, Heroku

## [0.1.0] - 2024-12-01

### Adicionado
- Versão inicial do projeto
- Estrutura básica Flask
- Cálculos preliminares de frete 