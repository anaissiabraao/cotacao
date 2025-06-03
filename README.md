# PortoEx - Sistema de Cotações de Frete

Sistema de cotações de frete que calcula custos para fretes fracionados e dedicados.

## Deploy no Render.com

1. Crie uma conta no [Render.com](https://render.com)
2. Clique em "New +" e selecione "Web Service"
3. Conecte seu repositório Git (GitHub, GitLab ou Bitbucket)
4. Configure o serviço:
   - Nome: `portoex-cotacao`
   - Ambiente: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn improved_chico_automate_fpdf:app`
   - Plano: Free

5. Adicione as variáveis de ambiente:
   - `FLASK_APP`: improved_chico_automate_fpdf.py
   - `FLASK_ENV`: production
   - `SECRET_KEY`: (gere uma chave segura)
   - `DEBUG`: False

6. Clique em "Create Web Service"

O aplicativo estará disponível em: https://portoex-cotacao.onrender.com

## Desenvolvimento Local

1. Clone o repositório
2. Crie um ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure as variáveis de ambiente:
   - Copie `.env.example` para `.env`
   - Ajuste as variáveis conforme necessário

5. Execute o servidor:
   ```bash
   python improved_chico_automate_fpdf.py
   ```

## Estrutura do Projeto

- `improved_chico_automate_fpdf.py`: Aplicação principal
- `requirements.txt`: Dependências do projeto
- `Procfile`: Configuração para deploy
- `.env`: Variáveis de ambiente (não versionado)
- `.gitignore`: Arquivos ignorados pelo Git

## Funcionalidades

- Cálculo de fretes fracionados
- Cálculo de fretes dedicados
- Geração de relatórios em PDF
- Exportação para Excel
- Histórico de cotações
- Dashboard de métricas

## Segurança

- Autenticação de usuários
- Sessões seguras
- HTTPS forçado
- Proteção contra CSRF
- Cookies seguros

## Suporte

Para suporte, entre em contato com a equipe de desenvolvimento. 