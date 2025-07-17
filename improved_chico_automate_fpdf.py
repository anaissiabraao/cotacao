import pandas as pd
import datetime
import math
import requests
import polyline
import time
from fpdf import FPDF
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash
import io
import os
import re
import unicodedata
import json
import uuid
from dotenv import load_dotenv
import tempfile
from functools import lru_cache

# Carregar variáveis de ambiente
load_dotenv()

# Imports para PostgreSQL (com fallback se não disponível)
try:
    from models import db, HistoricoCalculo, LogSistema
    POSTGRESQL_AVAILABLE = True
    print("[PostgreSQL] ✅ Modelos importados com sucesso")
except ImportError as e:
    POSTGRESQL_AVAILABLE = False
    print(f"[PostgreSQL] ⚠️ PostgreSQL não disponível: {e}")
    print("[PostgreSQL] Usando fallback para logs em arquivo")

# Cache global para agentes
_BASE_AGENTES_CACHE = None
_ULTIMO_CARREGAMENTO = 0
_CACHE_VALIDADE = 300  # 5 minutos

# SISTEMA DE USUÁRIOS E CONTROLE DE ACESSO
USUARIOS_SISTEMA = {
    'comercial.ptx': {
        'senha': 'ptx@123',
        'tipo': 'comercial',
        'nome': 'Usuário Comercial',
        'permissoes': ['calcular', 'historico', 'exportar']
    },
    'adm.ptx': {
        'senha': 'portoex@123', 
        'tipo': 'administrador',
        'nome': 'Administrador',
        'permissoes': ['calcular', 'historico', 'exportar', 'logs', 'setup', 'admin']
    }
}

# Controle de logs de acesso
LOGS_SISTEMA = []
HISTORICO_DETALHADO = []

def log_acesso(usuario, acao, ip, detalhes=""):
    """Registra log de acesso do sistema"""
    import datetime
    log_entry = {
        'timestamp': datetime.datetime.now(),
        'data_hora': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        'usuario': usuario,
        'acao': acao,
        'ip': ip,
        'detalhes': detalhes,
        'user_agent': request.headers.get('User-Agent', 'N/A') if request else 'N/A'
    }
    LOGS_SISTEMA.append(log_entry)
    
    # Manter apenas os últimos 1000 logs
    if len(LOGS_SISTEMA) > 200:
        LOGS_SISTEMA.pop(0)
    
    print(f"[LOG] {log_entry['data_hora']} - {usuario} - {acao} - IP: {ip}")

def obter_ip_cliente():
    """Obtém o IP real do cliente considerando proxies"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr

def verificar_autenticacao():
    """Verifica se o usuário está autenticado"""
    usuario_na_sessao = 'usuario_logado' in session
    usuario_existe = session.get('usuario_logado') in USUARIOS_SISTEMA if usuario_na_sessao else False
    
    # Debug para identificar problemas de sessão
    if not usuario_na_sessao:
        # Debug removido
        pass
    elif not usuario_existe:
        print(f"[DEBUG] Usuário '{session.get('usuario_logado')}' não existe no sistema")
    
    return usuario_na_sessao and usuario_existe

def verificar_permissao(permissao_requerida):
    """Verifica se o usuário tem a permissão específica"""
    if not verificar_autenticacao():
        return False
    
    usuario = session['usuario_logado']
    permissoes = USUARIOS_SISTEMA[usuario]['permissoes']
    return permissao_requerida in permissoes

def usuario_logado():
    """Retorna dados do usuário logado"""
    if verificar_autenticacao():
        usuario = session['usuario_logado']
        return USUARIOS_SISTEMA[usuario]
    return None

def middleware_auth(f):
    """Decorator para rotas que precisam de autenticação"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not verificar_autenticacao():
            if request.is_json:
                return jsonify({'error': 'Acesso negado. Faça login primeiro.', 'redirect': '/login'}), 401
            else:
                flash('Você precisa fazer login para acessar esta página.', 'error')
                return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def middleware_admin(f):
    """Decorator para rotas que precisam de permissão de administrador"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not verificar_autenticacao():
            return redirect(url_for('login'))
        
        if not verificar_permissao('admin'):
            if request.is_json:
                return jsonify({'error': 'Acesso negado. Permissão de administrador requerida.'}), 403
            else:
                flash('Acesso negado. Você não tem permissão de administrador.', 'error')
                return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Lista de estados como fallback
ESTADOS_FALLBACK = [
    {"id": "AC", "text": "Acre"}, {"id": "AL", "text": "Alagoas"}, {"id": "AP", "text": "Amapá"},
    {"id": "AM", "text": "Amazonas"}, {"id": "BA", "text": "Bahia"}, {"id": "CE", "text": "Ceará"},
    {"id": "DF", "text": "Distrito Federal"}, {"id": "ES", "text": "Espírito Santo"}, {"id": "GO", "text": "Goiás"},
    {"id": "MA", "text": "Maranhão"}, {"id": "MT", "text": "Mato Grosso"}, {"id": "MS", "text": "Mato Grosso do Sul"},
    {"id": "MG", "text": "Minas Gerais"}, {"id": "PA", "text": "Pará"}, {"id": "PB", "text": "Paraíba"},
    {"id": "PR", "text": "Paraná"}, {"id": "PE", "text": "Pernambuco"}, {"id": "PI", "text": "Piauí"},
    {"id": "RJ", "text": "Rio de Janeiro"}, {"id": "RN", "text": "Rio Grande do Norte"}, {"id": "RS", "text": "Rio Grande do Sul"},
    {"id": "RO", "text": "Rondônia"}, {"id": "RR", "text": "Roraima"}, {"id": "SC", "text": "Santa Catarina"},
    {"id": "SP", "text": "São Paulo"}, {"id": "SE", "text": "Sergipe"}, {"id": "TO", "text": "Tocantins"}
]

@lru_cache(maxsize=200)
def normalizar_cidade(cidade):
    """
    Normaliza o nome da cidade removendo acentos, caracteres especiais e padronizando o formato.
    """
    if not cidade:
        return ""
    
    cidade = str(cidade).strip()
    
    # Mapeamento de cidades conhecidas - EXPANDIDO
    mapeamento_cidades = {
        "SAO PAULO": "SAO PAULO",
        "SÃO PAULO": "SAO PAULO",
        "S. PAULO": "SAO PAULO",
        "S PAULO": "SAO PAULO",
        "SP": "SAO PAULO",
        "SAOPAULO": "SAO PAULO",
        "SAÕPAULO": "SAO PAULO",
        "RIO DE JANEIRO": "RIO DE JANEIRO",
        "RJ": "RIO DE JANEIRO",
        "RIODEJANEIRO": "RIO DE JANEIRO",
        "RIO": "RIO DE JANEIRO",
        "R. DE JANEIRO": "RIO DE JANEIRO",
        "R DE JANEIRO": "RIO DE JANEIRO",
        "BELO HORIZONTE": "BELO HORIZONTE",
        "BH": "BELO HORIZONTE",
        "BELOHORIZONTE": "BELO HORIZONTE",
        "B. HORIZONTE": "BELO HORIZONTE",
        "B HORIZONTE": "BELO HORIZONTE",
        "BRASILIA": "BRASILIA",
        "BRASÍLIA": "BRASILIA",
        "BSB": "BRASILIA",
        "ARACAJU": "ARACAJU",
        "RIBEIRAO PRETO": "RIBEIRAO PRETO",
        "RIBEIRÃO PRETO": "RIBEIRAO PRETO",
        "RIBEIRÃOPRETO": "RIBEIRAO PRETO",
        "RIBEIRAOPRETO": "RIBEIRAO PRETO",
        "RAO": "RIBEIRAO PRETO",
        "SALVADOR": "SALVADOR",
        "PORTO ALEGRE": "PORTO ALEGRE",
        "PORTOALEGRE": "PORTO ALEGRE",
        "RECIFE": "RECIFE",
        "FORTALEZA": "FORTALEZA",
        "CURITIBA": "CURITIBA",
        "GOIANIA": "GOIANIA",
        "GOIÂNIA": "GOIANIA",
        "MANAUS": "MANAUS",
        "BELÉM": "BELEM",
        "BELEM": "BELEM",
        "ITAJAI": "ITAJAI",
        "ITAJAÍ": "ITAJAI",
        "ITAJAY": "ITAJAI",
        "ITJ": "ITAJAI",
        "CAXIAS DO SUL": "CAXIAS DO SUL",
        "CAXIAS": "CAXIAS DO SUL",
        "CXS": "CAXIAS DO SUL",
        "CXJ": "CAXIAS DO SUL",
        "CAXIASDOSUL": "CAXIAS DO SUL",
        "CAXIAS-RS": "CAXIAS DO SUL",
        "CAXIAS DO SUL-RS": "CAXIAS DO SUL",
        "JARAGUA DO SUL": "JARAGUA DO SUL",
        "JARAGUÁ DO SUL": "JARAGUA DO SUL",
        "JARAGUA": "JARAGUA DO SUL",
        "JGS": "JARAGUA DO SUL",
        "JARAGUADOSUL": "JARAGUA DO SUL",
        "JARAGUA-SC": "JARAGUA DO SUL",
        "JARAGUA DO SUL-SC": "JARAGUA DO SUL",
        "JARAGUÁ-SC": "JARAGUA DO SUL",
        "JARAGUÁ DO SUL-SC": "JARAGUA DO SUL"
    }
    
    cidade_upper = cidade.upper()
    if cidade_upper in mapeamento_cidades:
        return mapeamento_cidades[cidade_upper]
    
    # Remover acentos
    cidade = unicodedata.normalize('NFKD', cidade).encode('ASCII', 'ignore').decode('ASCII')
    
    # Remover caracteres especiais e converter para maiúsculas
    cidade = re.sub(r'[^a-zA-Z0-9\s]', '', cidade).upper()
    
    # Remover espaços extras
    cidade = re.sub(r'\s+', ' ', cidade).strip()
    
    # Remover sufixos de UF
    cidade = re.sub(r'\s+[A-Z]{2}$', '', cidade)
    
    # Substituir abreviações comuns
    cidade = cidade.replace(" S ", " SANTO ")
    cidade = cidade.replace(" STO ", " SANTO ")
    cidade = cidade.replace(" STA ", " SANTA ")
    
    return cidade

@lru_cache(maxsize=30)
def normalizar_uf(uf):
    """
    Normaliza a UF, tratando abreviações e nomes completos.
    """
    if not uf:
        return ""
    
    uf = str(uf).strip().upper()
    
    # Mapeamento de estados
    mapeamento_estados = {
        "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAPÁ": "AP",
        "AMAZONAS": "AM", "BAHIA": "BA", "CEARA": "CE", "CEARÁ": "CE",
        "DISTRITO FEDERAL": "DF", "ESPIRITO SANTO": "ES", "ESPÍRITO SANTO": "ES",
        "GOIAS": "GO", "GOIÁS": "GO", "MARANHAO": "MA", "MARANHÃO": "MA",
        "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS", "MINAS GERAIS": "MG",
        "PARA": "PA", "PARÁ": "PA", "PARAIBA": "PB", "PARAÍBA": "PB",
        "PARANA": "PR", "PARANÁ": "PR", "PERNAMBUCO": "PE", "PIAUI": "PI",
        "PIAUÍ": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN",
        "RIO GRANDE DO SUL": "RS", "RONDONIA": "RO", "RONDÔNIA": "RO",
        "RORAIMA": "RR", "SANTA CATARINA": "SC", "SAO PAULO": "SP",
        "SÃO PAULO": "SP", "SERGIPE": "SE", "TOCANTINS": "TO"
    }
    
    if uf in mapeamento_estados:
        return mapeamento_estados[uf]
    
    if len(uf) == 2 and uf.isalpha():
        return uf
    
    match = re.search(r'\(([A-Z]{2})\)', uf)
    if match:
        return match.group(1)
    
    match = re.search(r'\s+([A-Z]{2})$', uf)
    if match:
        return match.group(1)
    
    if len(uf) >= 2 and uf[:2].isalpha():
        return uf[:2]
    
    return ""

def normalizar_cidade_nome(cidade):
    """
    Normaliza o nome da cidade, removendo a parte após o hífen.
    """
    if not cidade:
        return ""
    
    cidade = str(cidade)
    partes = cidade.split("-")
    cidade_sem_uf = partes[0].strip()
    
    return normalizar_cidade(cidade_sem_uf)

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv("SECRET_KEY", "chave_secreta_portoex_2025_muito_segura")

# Configurações de sessão mais robustas
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=7)
app.config["SESSION_COOKIE_SECURE"] = False  # Para desenvolvimento local
app.config["SESSION_COOKIE_HTTPONLY"] = True  # Segurança
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # Compatibilidade com AJAX

# Configurações para evitar cache
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Desabilitar cache em todas as respostas
@app.after_request
def after_request(response):
    # Não aplicar cache apenas para conteúdo estático, mas manter sessões
    if request.endpoint != 'static':
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = "0"
        response.headers["Pragma"] = "no-cache"
    return response

# Rota para limpar dados do navegador
@app.route("/clear-cache")
def clear_cache():
    response = redirect("/")
    # Não limpar cookies de sessão
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# Rotas de autenticação
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.is_json:
            data = request.get_json()
            usuario = data.get('usuario')
            senha = data.get('senha')
        else:
            usuario = request.form.get('usuario')
            senha = request.form.get('senha')
        
        ip_cliente = obter_ip_cliente()
        
        if usuario in USUARIOS_SISTEMA and USUARIOS_SISTEMA[usuario]['senha'] == senha:
            # Limpar sessão anterior
            session.clear()
            
            # Configurar nova sessão
            session['usuario_logado'] = usuario
            session['tipo_usuario'] = USUARIOS_SISTEMA[usuario]['tipo']
            session['nome_usuario'] = USUARIOS_SISTEMA[usuario]['nome']
            session.permanent = True
            
            # Debug - verificar se sessão foi criada
            # Debug removido
            
            log_acesso(usuario, 'LOGIN_SUCESSO', ip_cliente, f"Login realizado com sucesso")
            
            if request.is_json:
                return jsonify({
                    'success': True, 
                    'message': 'Login realizado com sucesso!',
                    'usuario': USUARIOS_SISTEMA[usuario]['nome'],
                    'tipo': USUARIOS_SISTEMA[usuario]['tipo'],
                    'redirect': '/'
                })
            else:
                flash(f'Bem-vindo, {USUARIOS_SISTEMA[usuario]["nome"]}!', 'success')
                return redirect(url_for('index'))
        else:
            log_acesso(usuario or 'DESCONHECIDO', 'LOGIN_FALHA', ip_cliente, f"Tentativa de login com credenciais inválidas")
            
            if request.is_json:
                return jsonify({'success': False, 'error': 'Usuário ou senha incorretos.'}), 401
            else:
                flash('Usuário ou senha incorretos.', 'error')
    
    # Se já está logado, redirecionar para home
    if verificar_autenticacao():
        return redirect(url_for('index'))
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    if verificar_autenticacao():
        usuario = session.get('usuario_logado', 'DESCONHECIDO')
        ip_cliente = obter_ip_cliente()
        log_acesso(usuario, 'LOGOUT', ip_cliente, "Logout realizado")
        
        session.clear()
        flash('Logout realizado com sucesso!', 'info')
    
    return redirect(url_for('login'))

# Health check endpoint para Render
@app.route("/health")
def health_check():
    """Endpoint de health check para verificar se a aplicação está funcionando."""
    try:
        # Verificar se a aplicação está funcionando
        status = {
            "status": "healthy",
            "timestamp": pd.Timestamp.now().isoformat(),
            "version": "1.0.0",
            "services": {
                "database": "online" if len(df_unificado) > 0 else "offline",
                "records": len(df_unificado)
            }
        }
        return jsonify(status), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy", 
            "error": str(e),
            "timestamp": pd.Timestamp.now().isoformat()
        }), 503

# Inicializar variáveis globais
HISTORICO_PESQUISAS = []
CONTADOR_DEDICADO = 1
CONTADOR_FRACIONADO = 1
ultimoResultadoDedicado = None
ultimoResultadoFracionado = None
app.config["UPLOAD_FOLDER"] = "static"

# Carregar bases de dados
possible_paths = [
    "/home/ubuntu/upload/Base_Unificada.xlsx",
    "Base_Unificada.xlsx",
    "C:\\Users\\Usuário\\OneDrive\\Desktop\\SQL data\\Chico automate\\Base_Unificada.xlsx",
]

# Adicionar caminho para Base_Unificada.xlsx
base_unificada_paths = [
    "/home/ubuntu/upload/Base_Unificada.xlsx",  # Render
    "/opt/render/project/src/Base_Unificada.xlsx",  # Render
    "/app/Base_Unificada.xlsx",  # Outro possível caminho no Render
    "Base_Unificada.xlsx",  # Diretório atual
    "../Base_Unificada.xlsx",  # Diretório pai
    "C:\\Users\\Usuário\\OneDrive\\Desktop\\SQL data\\Chico automate\\Base_Unificada.xlsx",  # Caminho local
    os.path.join(os.path.dirname(__file__), "Base_Unificada.xlsx"),  # Mesmo diretório do script
    os.path.join(os.getcwd(), "Base_Unificada.xlsx"),  # Diretório de trabalho atual
]

EXCEL_FILE = None
for path in possible_paths:
    if os.path.exists(path):
        EXCEL_FILE = path
        break

BASE_UNIFICADA_FILE = None
for path in base_unificada_paths:
    if os.path.exists(path):
        BASE_UNIFICADA_FILE = path
        break

if EXCEL_FILE is None:
    print("Arquivo Base_Unificada.xlsx não encontrado!")
    exit(1)

if BASE_UNIFICADA_FILE is None:
    print("Arquivo Base_Unificada.xlsx não encontrado nos seguintes caminhos:")
    for path in base_unificada_paths:
        print(f"- {path} (existe: {os.path.exists(path)})")
    BASE_UNIFICADA_FILE = None  # Continuar sem erro crítico

print(f"Usando arquivo principal: {EXCEL_FILE}")
if BASE_UNIFICADA_FILE:
    print(f"Usando Base Unificada: {BASE_UNIFICADA_FILE}")

# Carregar o arquivo Excel e detectar o nome correto da planilha
def detectar_sheet_name(excel_file):
    try:
        # Tentar abrir o arquivo e listar as planilhas disponíveis
        xl = pd.ExcelFile(excel_file)
        sheets = xl.sheet_names
        print(f"Planilhas encontradas no arquivo: {sheets}")
        
        # Priorizar planilhas com nomes específicos
        preferencias = ['Base', 'Sheet1', 'Sheet', 'Dados', 'Data']
        for pref in preferencias:
            if pref in sheets:
                return pref
        
        # Se não encontrar nenhuma das preferidas, usar a primeira
        return sheets[0] if sheets else None
    except Exception as e:
        print(f"Erro ao detectar planilha: {e}")
        return None

# Carregar dados diretamente da Base_Unificada.xlsx
try:
    print(f"Carregando dados de: {EXCEL_FILE}")
    df_unificado = pd.read_excel(EXCEL_FILE)
    print(f"Dados carregados com sucesso! Shape: {df_unificado.shape}")
    
    # Verificar se as colunas esperadas existem
    colunas_esperadas = ['Fornecedor', 'Base Origem', 'Origem', 'Base Destino', 'Destino']
    colunas_existentes = df_unificado.columns.tolist()
    print(f"Colunas no arquivo: {colunas_existentes}")
    
    # Se todas as colunas esperadas existem, continuar
    if all(col in colunas_existentes for col in colunas_esperadas):
        print("Arquivo Base_Unificada.xlsx possui estrutura correta para frete fracionado!")
    else:
        print("Aviso: Arquivo pode não ter a estrutura esperada para frete fracionado, mas continuando...")
        
except Exception as e:
    print(f"Erro ao carregar Base_Unificada.xlsx: {e}")
    print("Tentando carregar com sheet específico...")
    
    sheet_name = detectar_sheet_name(EXCEL_FILE)
    if not sheet_name:
        print("Erro: Não foi possível encontrar uma planilha válida no arquivo Excel.")
        # Criar DataFrame vazio como fallback
        df_unificado = pd.DataFrame()
    else:
        try:
            df_unificado = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name)
            print(f"Planilha '{sheet_name}' carregada com sucesso!")
        except Exception as e2:
            print(f"Erro ao carregar planilha '{sheet_name}': {e2}")
            df_unificado = pd.DataFrame()

def geocode(municipio, uf):
    try:
        # Normalizar cidade e UF
        cidade_norm = normalizar_cidade(municipio)
        uf_norm = normalizar_uf(uf)
        
        # Primeiro, tentar obter do cache de coordenadas
        from utils.coords_cache import COORDS_CACHE
        chave_cache = f"{cidade_norm}-{uf_norm}"
        
        print(f"[geocode] Buscando coordenadas para: {chave_cache}")
        
        if chave_cache in COORDS_CACHE:
            coords = COORDS_CACHE[chave_cache]
            print(f"[geocode] ✅ Encontrado no cache: {coords}")
            return coords
        
        # Se não encontrou no cache, tentar a API do OpenStreetMap
        print(f"[geocode] Não encontrado no cache, tentando API...")
        
        try:
            query = f"{cidade_norm}, {uf_norm}, Brasil"
            url = f"https://nominatim.openstreetmap.org/search"
            params = {"q": query, "format": "json", "limit": 1}
            headers = {"User-Agent": "PortoEx/1.0"}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()
            
            if not data:
                params = {"q": f"{cidade_norm}, Brasil", "format": "json", "limit": 1}
                response = requests.get(url, params=params, headers=headers, timeout=10)
                data = response.json()
            
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                coords = [lat, lon]
                print(f"[geocode] ✅ Encontrado via API: {coords}")
                return coords
        except Exception as api_error:
            print(f"[geocode] Erro na API: {str(api_error)}")
        
        # 4. Fallback: coordenadas baseadas no estado
        coords_estados = {
            'AC': [-8.77, -70.55], 'AL': [-9.71, -35.73], 'AP': [1.41, -51.77], 'AM': [-3.07, -61.66],
            'BA': [-12.96, -38.51], 'CE': [-3.72, -38.54], 'DF': [-15.78, -47.93], 'ES': [-19.19, -40.34],
            'GO': [-16.64, -49.31], 'MA': [-2.55, -44.30], 'MT': [-12.64, -55.42], 'MS': [-20.51, -54.54],
            'MG': [-18.10, -44.38], 'PA': [-5.53, -52.29], 'PB': [-7.06, -35.55], 'PR': [-24.89, -51.55],
            'PE': [-8.28, -35.07], 'PI': [-8.28, -43.68], 'RJ': [-22.84, -43.15], 'RN': [-5.22, -36.52],
            'RS': [-30.01, -51.22], 'RO': [-11.22, -62.80], 'RR': [1.99, -61.33], 'SC': [-27.33, -49.44],
            'SP': [-23.55, -46.64], 'SE': [-10.90, -37.07], 'TO': [-10.25, -48.25]
        }
        
        if uf_norm in coords_estados:
            coords = coords_estados[uf_norm]
            print(f"[geocode] ✅ Usando coordenadas do estado {uf_norm}: {coords}")
            return coords
        
        # 5. Fallback final: Brasília
        coords = [-15.7801, -47.9292]
        print(f"[geocode] ⚠️ Usando coordenadas padrão (Brasília): {coords}")
        return coords
        
    except Exception as e:
        print(f"[geocode] Erro crítico ao geocodificar {municipio}, {uf}: {e}")
        # Garantir que sempre retorna coordenadas válidas
        return [-15.7801, -47.9292]  # Brasília

def calcular_distancia_osrm(origem, destino):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{origem[1]},{origem[0]};{destino[1]},{destino[0]}?overview=full&geometries=geojson"
        response = requests.get(url, params={"steps": "false"}, timeout=15)
        data = response.json()
        if data.get("code") == "Ok":
            route = data["routes"][0]
            distance = route["distance"] / 1000  # km
            duration = route["duration"] / 60  # min
            geometry = route.get("geometry")
            route_points = []
            if geometry and "coordinates" in geometry:
                route_points = [[coord[1], coord[0]] for coord in geometry["coordinates"]]
            if not route_points:
                route_points = [origem, destino]
            for i, pt in enumerate(route_points):
                if not isinstance(pt, list) or len(pt) < 2:
                    route_points[i] = [0, 0]
            return {
                "distancia": round(distance, 2),
                "duracao": round(duration, 2),
                "rota_pontos": route_points,
                "consumo_combustivel": distance * 0.12,
                "pedagio_estimado": distance * 0.05,
                "provider": "OSRM"
            }
        return None
    except Exception as e:
        print(f"[OSRM] Erro ao calcular distância: {e}")
        return None

def calcular_distancia_openroute(origem, destino):
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {
            "Authorization": "5b3ce3597851110001cf6248a355ae5a9ee94a6ca9c6d876c7e4d534"
        }
        params = {
            "start": f"{origem[1]},{origem[0]}",
            "end": f"{destino[1]},{destino[0]}"
        }
        response = requests.get(url, headers=headers, params=params, timeout=15)
        data = response.json()
        if "features" in data and data["features"]:
            route = data["features"][0]
            segments = route.get("properties", {}).get("segments", [{}])[0]
            distance = segments.get("distance", 0) / 1000  # Converter para km
            duration = segments.get("duration", 0) / 60  # Converter para minutos
            geometry = route.get("geometry")
            route_points = [[coord[1], coord[0]] for coord in geometry.get("coordinates", [])]
            return {
                "distancia": distance,
                "duracao": duration,
                "rota_pontos": route_points,
                "consumo_combustivel": distance * 0.12,  # Litros por km
                "pedagio_estimado": distance * 0.05,  # Valor por km
                "provider": "OpenRoute"
            }
        return None
    except Exception as e:
        print(f"Erro ao calcular distância OpenRoute: {e}")
        return None

def calcular_distancia_reta(origem, destino):
    """
    Calcula a distância em linha reta entre dois pontos.
    Usado especialmente para modal aéreo.
    """
    try:
        lat1, lon1 = origem[0], origem[1]
        lat2, lon2 = destino[0], destino[1]
        R = 6371  # Raio da Terra em km
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        duration = (distance / 800) * 60  # Velocidade de avião: ~800 km/h
        route_points = [[lat1, lon1], [lat2, lon2]]
        return {
            "distancia": distance,
            "duracao": duration,
            "rota_pontos": route_points,
            "consumo_combustivel": distance * 0.4,  # Litros por km (avião)
            "pedagio_estimado": 0,  # Não há pedágio para avião
            "provider": "Linha Reta"
        }
    except Exception as e:
        print(f"Erro ao calcular distância em linha reta: {e}")
        return None

def determinar_faixa(distancia):
    faixas = [
        (0, 20), (20, 50), (50, 100), (100, 150), (150, 200),
        (200, 250), (250, 300), (300, 400), (400, 600), (600, 800),
        (800, 1000), (1000, 1500), (1500, 2000), (2000, 2500),
        (2500, 3000), (3000, 3500), (3500, 4000), (4000, 4500),
        (4500, 6000)
    ]
    for min_val, max_val in faixas:
        if min_val < distancia <= max_val:
            return f"{min_val}-{max_val}"
    return None

# Tabela fixa de custos para frete dedicado por faixa de distância e tipo de veículo
TABELA_CUSTOS_DEDICADO = {
    "0-20": {"FIORINO": 150.0, "VAN": 200.0, "3/4": 250.0, "TOCO": 300.0, "TRUCK": 350.0, "CARRETA": 500.0},
    "20-50": {"FIORINO": 200.0, "VAN": 250.0, "3/4": 300.0, "TOCO": 400.0, "TRUCK": 500.0, "CARRETA": 700.0},
    "50-100": {"FIORINO": 300.0, "VAN": 400.0, "3/4": 500.0, "TOCO": 600.0, "TRUCK": 700.0, "CARRETA": 1000.0},
    "100-150": {"FIORINO": 400.0, "VAN": 500.0, "3/4": 600.0, "TOCO": 800.0, "TRUCK": 1000.0, "CARRETA": 1500.0},
    "150-200": {"FIORINO": 500.0, "VAN": 600.0, "3/4": 800.0, "TOCO": 1000.0, "TRUCK": 1200.0, "CARRETA": 1800.0},
    "200-250": {"FIORINO": 600.0, "VAN": 800.0, "3/4": 1000.0, "TOCO": 1200.0, "TRUCK": 1500.0, "CARRETA": 2200.0},
    "250-300": {"FIORINO": 700.0, "VAN": 900.0, "3/4": 1200.0, "TOCO": 1500.0, "TRUCK": 1800.0, "CARRETA": 2500.0},
    "300-400": {"FIORINO": 900.0, "VAN": 1200.0, "3/4": 1500.0, "TOCO": 1800.0, "TRUCK": 2200.0, "CARRETA": 3000.0},
    "400-600": {"FIORINO": 1200.0, "VAN": 1600.0, "3/4": 2000.0, "TOCO": 2500.0, "TRUCK": 3000.0, "CARRETA": 4000.0}
}

# Valores por km acima de 600km
DEDICADO_KM_ACIMA_600 = {
    "FIORINO": 3.0,
    "VAN": 4.0,
    "3/4": 4.5,
    "TOCO": 5.0,
    "TRUCK": 5.5,
    "CARRETA": 8.0
}

def calcular_custos_dedicado(uf_origem, municipio_origem, uf_destino, municipio_destino, distancia, pedagio_real=0):
    try:
        # Inicializar dicionário de custos
        custos = {}
        
        # Garantir que pedagio_real e distancia são números válidos
        pedagio_real = float(pedagio_real) if pedagio_real is not None else 0.0
        distancia = float(distancia) if distancia is not None else 0.0
        
        # Determinar a faixa de distância
        faixa = determinar_faixa(distancia)
        
        # Calcular custos baseado na faixa de distância
        if faixa and faixa in TABELA_CUSTOS_DEDICADO:
            # Usar tabela de custos fixos por faixa
            tabela = TABELA_CUSTOS_DEDICADO[faixa]
            for tipo_veiculo, valor in tabela.items():
                custo_total = float(valor) + pedagio_real
                custos[tipo_veiculo] = round(custo_total, 2)
                
        elif distancia > 600:
            # Para distâncias acima de 600km, usar custo por km
            for tipo_veiculo, valor_km in DEDICADO_KM_ACIMA_600.items():
                custo_total = (distancia * float(valor_km)) + pedagio_real
                custos[tipo_veiculo] = round(custo_total, 2)
        else:
            # Custos padrão + pedágio real (fallback)
            custos_base = {
                "FIORINO": 150.0, 
                "VAN": 200.0, 
                "3/4": 250.0, 
                "TOCO": 300.0, 
                "TRUCK": 350.0, 
                "CARRETA": 500.0
            }
            for tipo_veiculo, valor in custos_base.items():
                custo_total = float(valor) + pedagio_real
                custos[tipo_veiculo] = round(custo_total, 2)
        
        # Garantir que todos os valores são números válidos
        for tipo_veiculo in list(custos.keys()):
            if not isinstance(custos[tipo_veiculo], (int, float)) or custos[tipo_veiculo] < 0:
                custos[tipo_veiculo] = 0.0
        
        print(f"[DEBUG] Custos calculados: {custos}")
        return custos
        
    except Exception as e:
        print(f"[ERRO] Erro ao calcular custos dedicado: {e}")
        # Retornar custos padrão em caso de erro
        return {
            "FIORINO": 150.0, 
            "VAN": 200.0, 
            "3/4": 250.0, 
            "TOCO": 300.0, 
            "TRUCK": 350.0, 
            "CARRETA": 500.0
        }

def gerar_analise_trajeto(origem_info, destino_info, rota_info, custos, tipo="Dedicado", municipio_origem=None, uf_origem=None, municipio_destino=None, uf_destino=None):
    global CONTADOR_DEDICADO, CONTADOR_FRACIONADO # Adicionado CONTADOR_FRACIONADO
    
    # Usar os nomes das cidades passados como parâmetro, ou fallback para as coordenadas
    if municipio_origem and uf_origem:
        origem_nome = f"{municipio_origem} - {uf_origem}"
    else:
        origem_nome = origem_info[2] if len(origem_info) > 2 else "Origem"
    
    if municipio_destino and uf_destino:
        destino_nome = f"{municipio_destino} - {uf_destino}"
    else:
        destino_nome = destino_info[2] if len(destino_info) > 2 else "Destino"
    
    horas = int(rota_info["duracao"] / 60)
    minutos = int(rota_info["duracao"] % 60)
    tempo_estimado = f"{horas}h {minutos}min"
    
    # Ajustar consumo de combustível baseado no tipo de modal
    if tipo == "Aéreo":
        consumo_combustivel = rota_info["distancia"] * 0.4  # Maior consumo para aviões
        emissao_co2 = consumo_combustivel * 3.15  # Maior emissão para aviação
        pedagio_real = 0  # Não há pedágio para modal aéreo
        pedagio_detalhes = None
    else:
        consumo_combustivel = rota_info["distancia"] * 0.12  # Consumo médio para veículos terrestres
        emissao_co2 = consumo_combustivel * 2.3
        
        # CÁLCULO REAL DE PEDÁGIOS para Frete Dedicado
        if tipo == "Dedicado":
            # Debug removido
            
            # Tentar calcular pedágios reais usando APIs
            pedagio_result = None
            
            # Primeira tentativa: Google Routes API com pedágios reais
            if len(origem_info) >= 2 and len(destino_info) >= 2:
                pedagio_result = calcular_pedagios_reais(origem_info[:2], destino_info[:2], peso_veiculo=7500)
            
            # Fallback: Estimativas brasileiras
            if not pedagio_result:
                print(f"[PEDÁGIO] API falhou, usando estimativas brasileiras")
                pedagio_result = calcular_pedagios_fallback_brasil(rota_info["distancia"], "CARRETA")
            
            if pedagio_result:
                pedagio_real = pedagio_result["pedagio_real"]
                pedagio_detalhes = pedagio_result["detalhes_pedagio"]
                print(f"[PEDÁGIO] ✅ Pedágio final: R$ {pedagio_real:.2f} ({pedagio_result['fonte']})")
            else:
                # Último fallback - estimativa simples
                pedagio_real = rota_info["distancia"] * 0.05
                pedagio_detalhes = {"fonte": "Estimativa simples", "valor_por_km": 0.05}
                print(f"[PEDÁGIO] ⚠️ Usando estimativa simples: R$ {pedagio_real:.2f}")
        else:
            # Para outros tipos de frete, manter a estimativa antiga
            pedagio_real = rota_info["distancia"] * 0.05
            pedagio_detalhes = None
    
    # Gerar ID único com formato #DedXXX, #FraXXX ou #AerXXX
    tipo_sigla = tipo[:3].upper()
    if tipo_sigla == "DED":
        CONTADOR_DEDICADO += 1
        id_historico = f"#Ded{CONTADOR_DEDICADO:03d}"
    elif tipo_sigla == "AER":
        CONTADOR_DEDICADO += 1 # Usar contador dedicado para aéreo também?
        id_historico = f"#Aer{CONTADOR_DEDICADO:03d}"
    elif tipo_sigla == "FRA": # Corrigido para FRA
        CONTADOR_FRACIONADO += 1
        id_historico = f"#Fra{CONTADOR_FRACIONADO:03d}"
    else:
        id_historico = f"#{tipo_sigla}{CONTADOR_DEDICADO:03d}"
    
    analise = {
        "id_historico": id_historico,
        "tipo": tipo,
        "origem": origem_nome,
        "destino": destino_nome,
        "distancia": round(rota_info["distancia"], 2),
        "tempo_estimado": tempo_estimado,
        "duracao_minutos": round(rota_info["duracao"], 2),
        "consumo_combustivel": round(consumo_combustivel, 2),
        "emissao_co2": round(emissao_co2, 2),
        "pedagio_estimado": round(pedagio_real, 2),  # Agora é o valor real
        "pedagio_real": round(pedagio_real, 2),      # Valor real de pedágios
        "pedagio_detalhes": pedagio_detalhes,        # Detalhes do cálculo
        "provider": rota_info["provider"],
        "custos": custos,
        "data_hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "rota_pontos": rota_info["rota_pontos"],
        # Capacidades dos veículos para comparação com carga
        "capacidades_veiculos": {
            'FIORINO': { 'peso_max': 500, 'volume_max': 1.20, 'descricao': 'Utilitário pequeno' },
            'VAN': { 'peso_max': 1500, 'volume_max': 6.0, 'descricao': 'Van/Kombi' },
            '3/4': { 'peso_max': 3500, 'volume_max': 12.0, 'descricao': 'Caminhão 3/4' },
            'TOCO': { 'peso_max': 7000, 'volume_max': 40.0, 'descricao': 'Caminhão toco' },
            'TRUCK': { 'peso_max': 12000, 'volume_max': 70.0, 'descricao': 'Caminhão truck' },
            'CARRETA': { 'peso_max': 28000, 'volume_max': 110.0, 'descricao': 'Carreta/bitrem' }
        }
    }
    return analise

def get_municipios_uf(uf):
    try:
        response = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios")
        response.raise_for_status()
        data = response.json()
        return {normalizar_cidade(m["nome"]): m["nome"] for m in data}
    except Exception as e:
        print(f"Erro ao obter municípios de {uf}: {e}")
        return {}

# Carregar base GOLLOG para modal aéreo
def ler_gollog_aereo():
    """
    Lê a base GOLLOG para modal aéreo.
    """
    try:
        gollog_path = "/home/ubuntu/upload/GOLLOG_Base_Unica.xlsx"
        if not os.path.exists(gollog_path):
            gollog_path = "GOLLOG_Base_Unica.xlsx"
        
        if os.path.exists(gollog_path):
            df_gollog = pd.read_excel(gollog_path)
            
            # Normalizar colunas para compatibilidade
            df_aereo = []
            for _, row in df_gollog.iterrows():
                # Mapear colunas da base GOLLOG
                item = {
                    "uf_origem": normalizar_uf(row.get("UF_ORIGEM", "")),
                    "cidade_origem": normalizar_cidade(row.get("CIDADE_ORIGEM", "")),
                    "uf_destino": normalizar_uf(row.get("UF_DESTINO", "")),
                    "cidade_destino": normalizar_cidade(row.get("CIDADE_DESTINO", "")),
                    "fornecedor": "GOLLOG",
                    "custo_base": float(row.get("CUSTO_BASE", 0)),
                    "prazo": int(row.get("PRAZO", 1)),
                    "modalidade": row.get("MODALIDADE", "STANDARD"),
                    "tipo_servico": row.get("TIPO_SERVICO", "AEREO")
                }
                df_aereo.append(item)
            
            return pd.DataFrame(df_aereo)
        else:
            print("Base GOLLOG não encontrada")
            return None
    except Exception as e:
        print(f"Erro ao ler base GOLLOG: {e}")
        return None

def carregar_base_unificada():
    """
    Carrega a Base Unificada completa para cálculos de frete
    """
    try:
        if not BASE_UNIFICADA_FILE:
            print("[BASE] ❌ BASE_UNIFICADA_FILE não está definido")
            return None
        
        if not os.path.exists(BASE_UNIFICADA_FILE):
            print(f"[BASE] ❌ Arquivo não encontrado: {BASE_UNIFICADA_FILE}")
            return None
        
        print(f"[BASE] 📁 Carregando arquivo: {BASE_UNIFICADA_FILE}")
        
        # Tentar carregar o arquivo Excel
        df_base = pd.read_excel(BASE_UNIFICADA_FILE)
        
        if df_base.empty:
            print("[BASE] ⚠️ Arquivo carregado está vazio")
            return None
        
        print(f"[BASE] ✅ Base carregada com sucesso: {len(df_base)} registros")
        print(f"[BASE] Colunas disponíveis: {list(df_base.columns)}")
        
        return df_base
        
    except Exception as e:
        print(f"[BASE] ❌ Erro ao carregar base unificada: {e}")
        return None

def calcular_frete_fracionado_base_unificada(origem, uf_origem, destino, uf_destino, peso, cubagem, valor_nf=None):
    """
    Calcular frete fracionado usando a Base Unificada com lógica correta de agentes
    """
    try:
        print(f"[FRACIONADO] 📦 Iniciando cálculo: {origem}/{uf_origem} → {destino}/{uf_destino}")
        print(f"[FRACIONADO] Peso: {peso}kg, Cubagem: {cubagem}m³, Valor NF: R$ {valor_nf:,}" if valor_nf else f"[FRACIONADO] Peso: {peso}kg, Cubagem: {cubagem}m³")
        
        # Usar a função correta de calcular frete com agentes do backup
        rotas_agentes = calcular_frete_com_agentes(
            origem, uf_origem,
            destino, uf_destino,
            peso, valor_nf, cubagem
        )
        
        if not rotas_agentes or rotas_agentes.get('total_opcoes', 0) == 0:
            print("[FRACIONADO] ❌ Nenhuma rota com agentes encontrada")
            return None
            
        # Preparar dados no formato esperado
        opcoes = rotas_agentes.get('rotas', [])
        if not opcoes:
            print("[FRACIONADO] ❌ Lista de rotas vazia")
            return None
            
        # Converter rotas para formato compatível
        opcoes_formatadas = []
        for rota in opcoes:
            # Extrair fornecedor corretamente do resumo
            resumo = rota.get('resumo', 'N/A')
            if resumo and resumo != 'N/A' and ' - ' in resumo:
                fornecedor = resumo.split(' - ')[0]  # Extrai só o nome antes do " - "
            else:
                # Fallback - tentar dos detalhes da transferência
                transferencia_info = rota.get('transferencia', {})
                if isinstance(transferencia_info, dict):
                    fornecedor = transferencia_info.get('fornecedor', 'N/A')
                else:
                    fornecedor = 'N/A'
            
            opcao = {
                'fornecedor': fornecedor,  # 🔧 CORRIGIDO - agora extrai corretamente
                'origem': origem,
                'destino': destino,
                'total': rota.get('total', 0),
                'prazo': rota.get('prazo_total', 1),
                'peso_cubado': rota.get('maior_peso', max(float(peso), float(cubagem) * 300)),
                'peso_usado': rota.get('maior_peso', max(float(peso), float(cubagem) * 300)),
                'modalidade': rota.get('tipo_rota', 'ROTA_COMPLETA').upper(),
                'tipo': rota.get('tipo_rota', 'ROTA_COMPLETA'),
                'tipo_rota': rota.get('tipo_rota', 'transferencia_direta'),  # 🆕 Adicionado
                'resumo': resumo,  # 🆕 Manter resumo original
                'detalhes': rota,  # Manter detalhes completos
                'custo_base': rota.get('detalhamento_custos', {}).get('coleta', 0) + rota.get('detalhamento_custos', {}).get('transferencia', 0) + rota.get('detalhamento_custos', {}).get('entrega', 0),
                'gris': rota.get('detalhamento_custos', {}).get('gris_total', 0),
                'pedagio': rota.get('detalhamento_custos', {}).get('pedagio', 0)
            }
            opcoes_formatadas.append(opcao)
        
        # Calcular peso cubado
        peso_float = float(peso)
        cubagem_float = float(cubagem)
        peso_cubado = max(peso_float, cubagem_float * 300)  # 1m³ = 300kg
        
        print(f"[FRACIONADO] ✅ {len(opcoes_formatadas)} opções encontradas com agentes")
        
        resultado = {
            'opcoes': opcoes_formatadas,
            'total_opcoes': len(opcoes_formatadas),
            'melhor_opcao': opcoes_formatadas[0] if opcoes_formatadas else None,
            'origem': origem,
            'uf_origem': uf_origem,
            'destino': destino,
            'uf_destino': uf_destino,
            'peso': peso,
            'cubagem': cubagem,
            'peso_cubado': peso_cubado,
            'valor_nf': valor_nf
        }
        
        return resultado
        
    except Exception as e:
        print(f"[FRACIONADO] ❌ Erro no cálculo: {e}")
        import traceback
        traceback.print_exc()
        return None

def obter_municipios_com_base(uf):
    """
    Obtém municípios que possuem base no estado especificado
    Analisa a base de dados para encontrar cidades com agentes ou transferências
    """
    try:
        print(f"[MUNICIPIOS_BASE] 🔍 Buscando municípios com base em {uf}...")
        
        # Carregar base de dados
        df_base = carregar_base_unificada()
        if df_base is None:
            return []
        
        # Normalizar UF
        uf_norm = normalizar_uf(uf)
        
        # Coletar cidades únicas que têm base no estado
        cidades_com_base = set()
        
        # 1. Buscar nas origens e destinos onde UF corresponde
        # Filtrar registros do estado
        df_estado = df_base[
            (df_base['UF'] == uf_norm) |
            (df_base['UF'].str.contains(uf_norm, case=False, na=False))
        ]
        
        # Adicionar cidades de origem
        for cidade in df_estado['Origem'].dropna().unique():
            cidade_norm = normalizar_cidade_nome(str(cidade))
            if cidade_norm:
                cidades_com_base.add(cidade_norm)
        
        # Adicionar cidades de destino
        for cidade in df_estado['Destino'].dropna().unique():
            cidade_norm = normalizar_cidade_nome(str(cidade))
            if cidade_norm:
                cidades_com_base.add(cidade_norm)
        
        # Adicionar bases
        for base in df_estado['Base Origem'].dropna().unique():
            base_norm = normalizar_cidade_nome(str(base))
            if base_norm and len(base_norm) > 3:  # Evitar códigos muito curtos
                cidades_com_base.add(base_norm)
        
        for base in df_estado['Base Destino'].dropna().unique():
            base_norm = normalizar_cidade_nome(str(base))
            if base_norm and len(base_norm) > 3:
                cidades_com_base.add(base_norm)
        
        # 2. Adicionar principais cidades conhecidas do estado
        cidades_principais = {
            'RS': ['PORTO ALEGRE', 'CAXIAS DO SUL', 'PELOTAS', 'CANOAS', 'SANTA MARIA', 
                   'GRAVATAI', 'NOVO HAMBURGO', 'SAO LEOPOLDO', 'RIO GRANDE', 'PASSO FUNDO'],
            'SC': ['FLORIANOPOLIS', 'JOINVILLE', 'BLUMENAU', 'SAO JOSE', 'CHAPECO',
                   'ITAJAI', 'JARAGUA DO SUL', 'CRICIUMA', 'NAVEGANTES', 'LAGES'],
            'PR': ['CURITIBA', 'LONDRINA', 'MARINGA', 'PONTA GROSSA', 'CASCAVEL',
                   'SAO JOSE DOS PINHAIS', 'FOZ DO IGUACU', 'COLOMBO', 'GUARAPUAVA', 'PARANAGUA']
        }
        
        if uf_norm in cidades_principais:
            for cidade in cidades_principais[uf_norm]:
                cidades_com_base.add(cidade)
        
        # Converter para lista de dicionários
        municipios = []
        for cidade in sorted(cidades_com_base):
            if cidade and len(cidade) > 2:  # Filtrar entradas vazias ou muito curtas
                municipios.append({
                    'nome': cidade,
                    'uf': uf_norm,
                    'tem_base': True
                })
        
        print(f"[MUNICIPIOS_BASE] ✅ Encontrados {len(municipios)} municípios com base em {uf}")
        return municipios[:20]  # Limitar a 20 municípios para não sobrecarregar
        
    except Exception as e:
        print(f"[MUNICIPIOS_BASE] ❌ Erro ao obter municípios: {e}")
        return []

def calcular_frete_com_agentes(origem, uf_origem, destino, uf_destino, peso, valor_nf=None, cubagem=None):
    """
    Calcula frete com sistema de agentes - APENAS rotas completas válidas
    
    Retorna:
        dict: Contendo rotas encontradas e informações sobre agentes ausentes
            - rotas: Lista de rotas encontradas
            - total_opcoes: Número total de rotas
            - origem/destino: Informações da origem/destino
            - agentes_faltando: Dicionário com informações sobre agentes ausentes
            - avisos: Lista de mensagens de aviso
    """
    try:
        # Inicializar variáveis para rastrear agentes ausentes
        agentes_faltando = {
            'origem': False,
            'destino': False,
            'agentes_proximos_origem': [],
            'agentes_proximos_destino': []
        }
        avisos = []  # Lista para armazenar mensagens de aviso
        
        # Carregar base unificada
        df_base = carregar_base_unificada()
        if df_base is None:
            print("[AGENTES] Erro: Não foi possível carregar a base de dados")
            return None

        # Separar tipos e filtrar agente ML (agente especial)
        df_agentes = df_base[
            (df_base['Tipo'] == 'Agente') & 
            (df_base['Fornecedor'] != 'ML')
        ].copy()
        df_transferencias = df_base[df_base['Tipo'] == 'Transferência'].copy()
        df_diretos = df_base[df_base['Tipo'] == 'Direto'].copy()
        
        print(f"[AGENTES] Agentes carregados (excluindo ML): {len(df_agentes)}")
        print(f"[AGENTES] Transferências carregadas: {len(df_transferencias)}")
        print(f"[AGENTES] Diretos carregados: {len(df_diretos)}")
        
        # Normalizar cidades e UFs
        origem_norm = normalizar_cidade_nome(origem)
        destino_norm = normalizar_cidade_nome(destino)
        uf_origem = normalizar_uf(uf_origem)
        uf_destino = normalizar_uf(uf_destino)
        
        # Calcular peso cubado
        peso_real = float(peso)
        peso_cubado = max(peso_real, float(cubagem) * 300) if cubagem else peso_real
        
        rotas_encontradas = []
        rotas_processadas = set()  # Controle de duplicatas
        MAX_ROTAS = 50  # Limite máximo de rotas para evitar processamento excessivo
        
        def gerar_chave_rota(agente_col_forn, transf_forn, agente_ent_forn):
            """Gera chave única para controle de duplicatas"""
            return f"{agente_col_forn}+{transf_forn}+{agente_ent_forn}"
        
        # Verificar se existem agentes na origem/destino exatos
        agentes_origem = df_agentes[
            (df_agentes['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_norm)) &
            (df_agentes['UF'] == uf_origem)
        ]
        
        agentes_destino = df_agentes[
            (df_agentes['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_norm)) &
            (df_agentes['UF'] == uf_destino)
        ]
        
        # Verificar se faltam agentes exatos e buscar próximos
        if agentes_origem.empty:
            agentes_faltando['origem'] = True
            print(f"[AGENTES] ⚠️ Nenhum agente encontrado em {origem_norm}/{uf_origem}")
            avisos.append(f"Atenção: Nenhum agente encontrado em {origem_norm}/{uf_origem}")
            
            # Buscar agentes próximos
            cidades_proximas = encontrar_municipios_proximos(origem, uf_origem, raio_km=50, limite=3)
            if cidades_proximas:
                agentes_faltando['agentes_proximos_origem'] = [
                    {'cidade': cid, 'uf': uf, 'distancia_km': dist} 
                    for cid, uf, dist in cidades_proximas
                ]
                cidades_str = ", ".join([f"{c[0]}/{c[1]} ({c[2]}km)" for c in cidades_proximas])
                avisos.append(f"Agentes próximos disponíveis em: {cidades_str}")
                print(f"[AGENTES] 🔍 Agentes próximos a {origem_norm}: {cidades_str}")
        
        if agentes_destino.empty:
            agentes_faltando['destino'] = True
            print(f"[AGENTES] ⚠️ Nenhum agente encontrado em {destino_norm}/{uf_destino}")
            avisos.append(f"Atenção: Nenhum agente encontrado em {destino_norm}/{uf_destino}")
            
            # Buscar agentes próximos
            cidades_proximas = encontrar_municipios_proximos(destino, uf_destino, raio_km=50, limite=3)
            if cidades_proximas:
                agentes_faltando['agentes_proximos_destino'] = [
                    {'cidade': cid, 'uf': uf, 'distancia_km': dist} 
                    for cid, uf, dist in cidades_proximas
                ]
                cidades_str = ", ".join([f"{c[0]}/{c[1]} ({c[2]}km)" for c in cidades_proximas])
                avisos.append(f"Agentes próximos disponíveis em: {cidades_str}")
                print(f"[AGENTES] 🔍 Agentes próximos a {destino_norm}: {cidades_str}")
        
        # Verificar se não há agentes exatos e buscar os mais próximos
        if agentes_origem.empty:
            agentes_faltando['origem'] = True
            print(f"[AGENTES] ⚠️ Nenhum agente encontrado em {origem}/{uf_origem}")
            # Buscar municípios próximos com agentes
            agentes_faltando['agentes_proximos_origem'] = encontrar_municipios_proximos(
                origem, uf_origem, raio_km=100, limite=3
            )
            print(f"[AGENTES] 🔍 Agentes próximos a {origem}: {agentes_faltando['agentes_proximos_origem']}")
        
        if agentes_destino.empty:
            agentes_faltando['destino'] = True
            print(f"[AGENTES] ⚠️ Nenhum agente encontrado em {destino}/{uf_destino}")
            # Buscar municípios próximos com agentes
            agentes_faltando['agentes_proximos_destino'] = encontrar_municipios_proximos(
                destino, uf_destino, raio_km=100, limite=3
            )
            print(f"[AGENTES] 🔍 Agentes próximos a {destino}: {agentes_faltando['agentes_proximos_destino']}")
        
        # 1. BUSCAR SERVIÇOS DIRETOS (PORTA-A-PORTA)
        # Primeiro tentar cidades exatas
        servicos_diretos = df_diretos[
            (df_diretos['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_norm)) &
            (df_diretos['Destino'].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_norm))
        ]
        
        # Se não encontrar, tentar cidades na mesma UF
        if servicos_diretos.empty:
            print(f"[DIRETOS] 🔍 Busca expandida de serviços diretos em {uf_origem} → {uf_destino}...")
            # Verificando as colunas disponíveis para UF
            if 'UF Origem' in df_diretos.columns and 'UF Destino' in df_diretos.columns:
                servicos_diretos = df_diretos[
                    (df_diretos['UF Origem'] == uf_origem) &
                    (df_diretos['UF Destino'] == uf_destino)
                ]
            else:
                # Fallback usando a coluna UF e Base Origem/Base Destino para determinar UFs
                servicos_diretos = df_diretos[
                    (df_diretos['Base Origem'].str.contains(uf_origem, case=False, na=False)) &
                    (df_diretos['Base Destino'].str.contains(uf_destino, case=False, na=False))
                ]
                if servicos_diretos.empty and 'UF' in df_diretos.columns:
                    # Tentar usar apenas a coluna UF se disponível
                    print(f"[DIRETOS] 🔄 Tentando busca alternativa usando coluna UF...")
                    # A coluna UF geralmente contém pares de UF como "PR-SP"
                    servicos_diretos = df_diretos[
                        df_diretos['UF'].apply(lambda x: str(x).startswith(uf_origem) and str(x).endswith(uf_destino))
                    ]
            print(f"[DIRETOS] Busca expandida encontrou: {len(servicos_diretos)} serviços")
        
        for _, servico in servicos_diretos.iterrows():
            try:
                peso_cubado_servico = calcular_peso_cubado_por_tipo(peso_real, cubagem, servico.get('Tipo', 'Direto'), servico.get('Fornecedor'))
                opcao = processar_linha_fracionado(servico, peso_cubado_servico, valor_nf, "DIRETO PORTA-A-PORTA")
                if opcao:
                    rota = {
                        'tipo_rota': 'direto_porta_porta',
                        'resumo': f"{opcao['fornecedor']} - Serviço Direto Porta-a-Porta",
                        'total': opcao['total'],
                        'prazo_total': opcao['prazo'],
                        'maior_peso': peso_cubado,
                        'peso_usado': 'Real' if peso_real >= peso_cubado else 'Cubado',
                        'rota_bases': f"{origem} → {destino} (Direto)",
                        'detalhamento_custos': {
                            'coleta': opcao['custo_base'],  # ✅ DIRETO inclui coleta
                            'transferencia': 0,             # ✅ DIRETO não tem transferência
                            'entrega': 0,                   # ✅ DIRETO inclui entrega no custo base
                            'pedagio': opcao['pedagio'],
                            'gris_total': opcao['gris']
                        },
                        'observacoes': "Serviço direto porta-a-porta (coleta e entrega incluídas)",
                        'servico_direto': opcao,
                        'agente_coleta': {
                            'fornecedor': opcao['fornecedor'],
                            'funcao': 'Coleta na origem (incluída no serviço direto)',
                            'total': opcao['custo_base'],
                            'base_destino': 'Direto para destino'
                        },
                        'transferencia': {
                            'fornecedor': 'Não aplicável',
                            'rota': f"{origem} → {destino}",
                            'total': 0,
                            'observacao': 'Serviço direto sem transferência'
                        },
                        'agente_entrega': {
                            'fornecedor': opcao['fornecedor'],
                            'funcao': 'Entrega no destino (incluída no serviço direto)',
                            'total': 0,
                            'base_origem': 'Direto da origem'
                        }
                    }
                    rotas_encontradas.append(rota)
                    print(f"[DIRETO] ✅ Serviço direto: {opcao['fornecedor']} - R$ {opcao['total']:.2f}")
            except Exception as e:
                print(f"[DIRETO] ❌ Erro ao processar serviço direto: {e}")
                continue
        
        # 2. BUSCAR ROTAS COM AGENTES + TRANSFERÊNCIAS
        # Agentes de coleta - BUSCA GLOBAL E INTELIGENTE
        agentes_coleta = df_agentes[
            df_agentes['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_norm)
        ]
        
        # Se não encontrar agentes na cidade exata, usar estratégia global
        if agentes_coleta.empty:
            print(f"[AGENTES] 🔍 Busca global de agentes de coleta...")
            
            # ESTRATÉGIA 0.5: Buscar agentes em cidades próximas primeiro
            print(f"[AGENTES] 🗺️ ESTRATÉGIA 0.5: Buscando agentes em cidades próximas a {origem_norm}...")
            
            # Mapa de cidades próximas para cidades pequenas
            cidades_proximas_mapa = {
                # RS - Cidades pequenas e suas cidades HUB mais próximas
                'ARAMBARE': ['PORTO ALEGRE', 'CANOAS', 'GRAVATAI', 'NOVO HAMBURGO'],
                'AGUDO': ['SANTA MARIA', 'SANTA CRUZ DO SUL'],
                'ALEGRETE': ['URUGUAIANA', 'SANTANA DO LIVRAMENTO'],
                
                # SC - Cidades pequenas e suas cidades HUB mais próximas  
                'AGRONOMICA': ['BLUMENAU', 'POMERODE', 'INDAIAL', 'RIO DO SUL'],
                'AGUAS MORNAS': ['FLORIANOPOLIS', 'SAO JOSE', 'PALHOCA'],
                'ALFREDO WAGNER': ['FLORIANOPOLIS', 'LAGES'],
                
                # Padrão para qualquer cidade pequena por estado
                '_DEFAULT_RS': ['PORTO ALEGRE', 'CAXIAS DO SUL', 'CANOAS', 'PELOTAS', 'SANTA MARIA'],
                '_DEFAULT_SC': ['FLORIANOPOLIS', 'JOINVILLE', 'BLUMENAU', 'ITAJAI', 'CHAPECO'],
                '_DEFAULT_PR': ['CURITIBA', 'LONDRINA', 'MARINGA', 'CASCAVEL', 'PONTA GROSSA']
            }
            
            # Buscar cidades próximas
            cidades_proximas = cidades_proximas_mapa.get(origem_norm, [])
            if not cidades_proximas:
                # Usar cidades padrão do estado
                cidades_proximas = cidades_proximas_mapa.get(f'_DEFAULT_{uf_origem}', [])
            
            if cidades_proximas:
                # Buscar agentes em qualquer uma das cidades próximas
                agentes_coleta = df_agentes[
                    df_agentes['Origem'].apply(
                        lambda x: any(cidade in normalizar_cidade_nome(str(x)) for cidade in cidades_proximas)
                    ) & (df_agentes['Tipo'] == 'Agente')
                ]
                
                if not agentes_coleta.empty:
                    print(f"[AGENTES] ✅ Encontrados {len(agentes_coleta)} agentes em cidades próximas: {cidades_proximas[:3]}")
                else:
                    print(f"[AGENTES] ⚠️ Nenhum agente encontrado nas cidades próximas")
            
            # Se ainda não encontrou, continuar com estratégias existentes
            if agentes_coleta.empty:
                # ESTRATÉGIA 1: Buscar agentes do estado, mas filtrar para só cidades próximas ou HUBs
                print(f"[AGENTES] 📍 ESTRATÉGIA 1: Buscando agentes em {uf_origem} (apenas cidades válidas)...")
                cidades_validas = set([origem_norm] + cidades_proximas)
                agentes_coleta = df_agentes[
                    (df_agentes['UF'] == uf_origem) &
                    (df_agentes['Tipo'] == 'Agente') &
                    (df_agentes['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) in cidades_validas))
                ]
                
                # ESTRATÉGIA 2: Se ainda vazio, buscar agentes que mencionem o estado
                if agentes_coleta.empty:
                    print(f"[AGENTES] 📍 ESTRATÉGIA 2: Busca flexível por {uf_origem}...")
                    agentes_coleta = df_agentes[
                        (df_agentes['Base Origem'].str.contains(uf_origem, case=False, na=False) |
                         df_agentes['Base Destino'].str.contains(uf_origem, case=False, na=False) |
                         df_agentes['UF'].str.contains(uf_origem, case=False, na=False))
                    ]
            
            # ESTRATÉGIA 3: Buscar agentes em cidades HUB do estado
            if agentes_coleta.empty or len(agentes_coleta) > 20:
                print(f"[AGENTES] 📍 ESTRATÉGIA 3: Priorizando agentes em cidades HUB...")
                
                # Busca cidades próximas usando geolocalização
                cidades_proximas = encontrar_municipios_proximos(origem, uf_origem, raio_km=100, limite=3)
                cidades_hub = [c[0] for c in cidades_proximas]  # Extrai apenas os nomes das cidades
                
                if cidades_hub:
                    agentes_hub = df_agentes[
                        df_agentes['Origem'].apply(
                            lambda x: any(hub in normalizar_cidade_nome(str(x)) for hub in cidades_hub)
                        )
        ]
        
                    if not agentes_hub.empty:
                        agentes_coleta = agentes_hub
                        print(f"[AGENTES] ✅ Priorizados {len(agentes_coleta)} agentes em cidades HUB")
            
            # Limitar resultados para não sobrecarregar
            if len(agentes_coleta) > 10:
                agentes_coleta = agentes_coleta.head(10)
                print(f"[AGENTES] ⚠️ Limitado a 10 agentes de coleta")
            
            print(f"[AGENTES] ✅ Total de agentes de coleta encontrados: {len(agentes_coleta)}")
        
        # Agentes de entrega - BUSCA GLOBAL E INTELIGENTE
        agentes_entrega = df_agentes[
            df_agentes['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_norm)
        ]
        
        # Se não encontrar agentes na cidade exata, usar estratégia global
        if agentes_entrega.empty:
            print(f"[AGENTES] 🔍 Busca global de agentes de entrega...")
            
            # ESTRATÉGIA 0.5: Buscar agentes em cidades próximas primeiro
            print(f"[AGENTES] 🗺️ ESTRATÉGIA 0.5: Buscando agentes em cidades próximas a {destino_norm}...")
            
            # Usar o mesmo mapa de cidades próximas
            cidades_proximas_mapa = {
                # RS - Cidades pequenas e suas cidades HUB mais próximas
                'ARAMBARE': ['PORTO ALEGRE', 'CANOAS', 'GRAVATAI', 'NOVO HAMBURGO'],
                'AGUDO': ['SANTA MARIA', 'SANTA CRUZ DO SUL'],
                'ALEGRETE': ['URUGUAIANA', 'SANTANA DO LIVRAMENTO'],
                
                # SC - Cidades pequenas e suas cidades HUB mais próximas  
                'AGRONOMICA': ['BLUMENAU', 'POMERODE', 'INDAIAL', 'RIO DO SUL'],
                'AGUAS MORNAS': ['FLORIANOPOLIS', 'SAO JOSE', 'PALHOCA'],
                'ALFREDO WAGNER': ['FLORIANOPOLIS', 'LAGES'],
                
                # Padrão para qualquer cidade pequena por estado
                '_DEFAULT_RS': ['PORTO ALEGRE', 'CAXIAS DO SUL', 'CANOAS', 'PELOTAS', 'SANTA MARIA'],
                '_DEFAULT_SC': ['FLORIANOPOLIS', 'JOINVILLE', 'BLUMENAU', 'ITAJAI', 'CHAPECO'],
                '_DEFAULT_PR': ['CURITIBA', 'LONDRINA', 'MARINGA', 'CASCAVEL', 'PONTA GROSSA']
            }
            
            # Buscar cidades próximas
            cidades_proximas = cidades_proximas_mapa.get(destino_norm, [])
            if not cidades_proximas:
                # Usar cidades padrão do estado
                cidades_proximas = cidades_proximas_mapa.get(f'_DEFAULT_{uf_destino}', [])
            
            if cidades_proximas:
                # Buscar agentes em qualquer uma das cidades próximas
                agentes_entrega = df_agentes[
                    df_agentes['Origem'].apply(
                        lambda x: any(cidade in normalizar_cidade_nome(str(x)) for cidade in cidades_proximas)
                    ) & (df_agentes['Tipo'] == 'Agente')
                ]
                
                if not agentes_entrega.empty:
                    print(f"[AGENTES] ✅ Encontrados {len(agentes_entrega)} agentes em cidades próximas: {cidades_proximas[:3]}")
                else:
                    print(f"[AGENTES] ⚠️ Nenhum agente encontrado nas cidades próximas")
            
            # Se ainda não encontrou, continuar com estratégias existentes
            if agentes_entrega.empty:
                # ESTRATÉGIA 1: Buscar QUALQUER agente no estado de destino
                print(f"[AGENTES] 📍 ESTRATÉGIA 1: Buscando agentes em {uf_destino}...")
                agentes_entrega = df_agentes[
                    (df_agentes['UF'] == uf_destino) &
                    (df_agentes['Tipo'] == 'Agente')
                ]
                
                # ESTRATÉGIA 2: Se ainda vazio, buscar agentes que mencionem o estado
                if agentes_entrega.empty:
                    print(f"[AGENTES] 📍 ESTRATÉGIA 2: Busca flexível por {uf_destino}...")
                    agentes_entrega = df_agentes[
                        (df_agentes['Base Origem'].str.contains(uf_destino, case=False, na=False) |
                         df_agentes['Base Destino'].str.contains(uf_destino, case=False, na=False) |
                         df_agentes['UF'].str.contains(uf_destino, case=False, na=False))
                    ]
            
            # ESTRATÉGIA 3: Buscar agentes em cidades HUB do estado
            if agentes_entrega.empty or len(agentes_entrega) > 20:
                print(f"[AGENTES] 📍 ESTRATÉGIA 3: Priorizando agentes em cidades HUB...")
                
                # Busca cidades próximas usando geolocalização
                cidades_proximas = encontrar_municipios_proximos(origem, uf_origem, raio_km=100, limite=3)
                cidades_hub = [c[0] for c in cidades_proximas]  # Extrai apenas os nomes das cidades
                
                if cidades_hub:
                    agentes_hub = df_agentes[
                        df_agentes['Origem'].apply(
                            lambda x: any(hub in normalizar_cidade_nome(str(x)) for hub in cidades_hub)
                        )
                    ]
                    
                    if not agentes_hub.empty:
                        agentes_entrega = agentes_hub
                        print(f"[AGENTES] ✅ Priorizados {len(agentes_entrega)} agentes em cidades HUB")
            
            # ESTRATÉGIA 4: Se ainda não tem agentes suficientes, expandir busca
            if len(agentes_entrega) < 3:
                print(f"[AGENTES] 📍 ESTRATÉGIA 4: Expandindo busca para estados vizinhos...")
                
                # Mapa de estados vizinhos
                estados_vizinhos = {
                    'RS': ['SC'],
                    'SC': ['RS', 'PR'],
                    'PR': ['SC', 'SP', 'MS'],
                    'SP': ['PR', 'MG', 'RJ', 'MS'],
                    'RJ': ['SP', 'MG', 'ES'],
                    'MG': ['SP', 'RJ', 'ES', 'BA', 'GO']
                }
                
                vizinhos = estados_vizinhos.get(uf_destino, [])
                for estado_viz in vizinhos[:1]:  # Pegar apenas o vizinho mais próximo
                    agentes_viz = df_agentes[
                        (df_agentes['UF'] == estado_viz) &
                        (df_agentes['Tipo'] == 'Agente')
                    ].head(5)  # Limitar a 5 agentes
                    
                    if not agentes_viz.empty:
                        print(f"[AGENTES] ✅ Adicionados {len(agentes_viz)} agentes de {estado_viz}")
                        agentes_entrega = pd.concat([agentes_entrega, agentes_viz])
            
            # Limitar resultados para não sobrecarregar
            if len(agentes_entrega) > 10:
                agentes_entrega = agentes_entrega.head(10)
                print(f"[AGENTES] ⚠️ Limitado a 10 agentes de entrega")
            
            print(f"[AGENTES] ✅ Total de agentes de entrega encontrados: {len(agentes_entrega)}")

        # AVISO: Verificar se há agentes de entrega, mas continuar com rotas parciais
        if agentes_entrega.empty:
            print(f"[AGENTES] ⚠️ AVISO: Não há agentes de entrega disponíveis em {destino}/{uf_destino}")
            print(f"[AGENTES] Continuando busca por rotas parciais e transferências diretas...")
        else:
            print(f"[AGENTES] ✅ Agentes de entrega encontrados: {len(agentes_entrega)}")

        # 🔧 BUSCAR TRANSFERÊNCIAS DIRETAS CIDADE → CIDADE (PRIORIDADE MÁXIMA)
        # Primeiro tentar cidades exatas
        transferencias_origem_destino = df_transferencias[
            (df_transferencias['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_norm)) &
            (df_transferencias['Destino'].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_norm))
        ]
        
        # Se não encontrar, tentar estratégias mais abrangentes
        if transferencias_origem_destino.empty:
            print(f"[TRANSFERENCIAS] 🔍 Busca inteligente por rotas disponíveis...")
            
            # ESTRATÉGIA 1: Buscar TODAS as transferências que saem da origem para o estado destino
            print(f"[TRANSFERENCIAS] 📍 ESTRATÉGIA 1: Buscando transferências {origem_norm} → qualquer cidade em {uf_destino}...")
            transf_origem_para_uf = df_transferencias[
                (df_transferencias['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_norm)) &
                ((df_transferencias['UF'] == f"{uf_origem}-{uf_destino}") |
                 (df_transferencias['UF'].str.contains(uf_destino, case=False, na=False)) |
                 (df_transferencias['Base Destino'].str.contains(uf_destino, case=False, na=False)))
            ]
            
            if not transf_origem_para_uf.empty:
                print(f"[TRANSFERENCIAS] ✅ Encontradas {len(transf_origem_para_uf)} transferências de {origem_norm} para {uf_destino}")
                transferencias_origem_destino = transf_origem_para_uf
            
            # ESTRATÉGIA 2: Buscar transferências de qualquer cidade em RS para o destino específico
            if transferencias_origem_destino.empty:
                print(f"[TRANSFERENCIAS] 📍 ESTRATÉGIA 2: Buscando transferências de qualquer cidade em {uf_origem} → {destino_norm}...")
                transf_uf_para_destino = df_transferencias[
                    ((df_transferencias['UF'] == f"{uf_origem}-{uf_destino}") |
                     (df_transferencias['UF'].str.startswith(uf_origem, na=False)) |
                     (df_transferencias['Base Origem'].str.contains(uf_origem, case=False, na=False))) &
                    (df_transferencias['Destino'].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_norm))
                ]
                
                if not transf_uf_para_destino.empty:
                    print(f"[TRANSFERENCIAS] ✅ Encontradas {len(transf_uf_para_destino)} transferências de {uf_origem} para {destino_norm}")
                    transferencias_origem_destino = transf_uf_para_destino
            
            # ESTRATÉGIA 3: Buscar QUALQUER transferência entre os estados
            if transferencias_origem_destino.empty:
                print(f"[TRANSFERENCIAS] 📍 ESTRATÉGIA 3: Buscando QUALQUER transferência {uf_origem} → {uf_destino}...")
                
                # Múltiplas tentativas com diferentes padrões
                patterns_uf = [
                    f"{uf_origem}-{uf_destino}",
                    f"{uf_origem}/{uf_destino}",
                    f"{uf_origem} {uf_destino}",
                    f"{uf_origem}{uf_destino}"
                ]
                
                # ESTRATÉGIA 4: Buscar cidades próximas usando geolocalização
                if transferencias_origem_destino.empty:
                    print("[TRANSFERENCIAS] 🔍 ESTRATÉGIA 4: Buscando cidades próximas com agentes via geolocalização...")
                    
                    # Buscar cidades próximas à origem e destino
                    cidades_proximas_origem = encontrar_municipios_proximos(origem, uf_origem, raio_km=100, limite=3)
                    cidades_proximas_destino = encontrar_municipios_proximos(destino, uf_destino, raio_km=100, limite=3)
                    
                    print(f"[GEOLOC] 🌍 Cidades próximas a {origem}/{uf_origem}:")
                    for cidade, uf, dist in cidades_proximas_origem:
                        print(f"  - {cidade}/{uf} ({dist:.1f} km)")
                        
                    print(f"[GEOLOC] 🌍 Cidades próximas a {destino}/{uf_destino}:")
                    for cidade, uf, dist in cidades_proximas_destino:
                        print(f"  - {cidade}/{uf} ({dist:.1f} km)")
                    
                    # Buscar transferências entre cidades próximas
                    for cidade_origem, uf_origem_prox, _ in cidades_proximas_origem:
                        for cidade_destino, uf_destino_prox, _ in cidades_proximas_destino:
                            # Buscar transferências diretas entre cidades próximas
                            transf = df_unificado[
                                (df_unificado['Tipo'] == 'Transferência') &
                                (df_unificado['Origem'].str.contains(cidade_origem, case=False, na=False)) &
                                (df_unificado['Destino'].str.contains(cidade_destino, case=False, na=False)) &
                                (df_unificado['UF Origem'] == uf_origem_prox) &
                                (df_unificado['UF Destino'] == uf_destino_prox)
                            ]
                            
                            if not transf.empty:
                                transferencias_origem_destino = pd.concat([transferencias_origem_destino, transf])
                                print(f"[GEOLOC] 🔄 Encontrada transferência via cidades próximas: {cidade_origem} → {cidade_destino}")
                                
                                # Limita o número de transferências para evitar sobrecarga
                                if len(transferencias_origem_destino) >= 5:
                                    break
                        
                        if len(transferencias_origem_destino) >= 5:
                            break
                
                # ESTRATÉGIA 5: Busca final genérica - qualquer transferência entre os estados
            if 'UF Origem' in df_transferencias.columns and 'UF Destino' in df_transferencias.columns:
                transferencias_origem_destino = df_transferencias[
                    (df_transferencias['UF Origem'] == uf_origem) &
                    (df_transferencias['UF Destino'] == uf_destino)
                ]
            else:
                # Fallback usando a coluna UF e Base Origem/Base Destino para determinar UFs
                transferencias_origem_destino = df_transferencias[
                    (df_transferencias['Base Origem'].str.contains(uf_origem, case=False, na=False)) &
                    (df_transferencias['Base Destino'].str.contains(uf_destino, case=False, na=False))
                ]
                
                # Se ainda vazio, tentar busca mais flexível por Base Origem OU Base Destino
                if transferencias_origem_destino.empty:
                    print(f"[TRANSFERENCIAS] 🔍 Tentando busca flexível por bases em {uf_origem} e {uf_destino}...")
                    # Buscar qualquer transferência que mencione as UFs nas bases
                    transferencias_origem_destino = df_transferencias[
                        ((df_transferencias['Base Origem'].str.contains(uf_origem, case=False, na=False)) |
                         (df_transferencias['Origem'].str.contains(uf_origem, case=False, na=False))) &
                        ((df_transferencias['Base Destino'].str.contains(uf_destino, case=False, na=False)) |
                         (df_transferencias['Destino'].str.contains(uf_destino, case=False, na=False)))
                    ]
                
                # Buscar na coluna UF com vários padrões
                if transferencias_origem_destino.empty and 'UF' in df_transferencias.columns:
                    # Tentar usar a coluna UF com diferentes padrões
                    print(f"[TRANSFERENCIAS] 🔄 Tentando busca avançada na coluna UF...")
                        # Verificar vários padrões comuns: "RS-SC", "RS/SC", etc
                    patterns = [f"{uf_origem}{sep}{uf_destino}" for sep in ["-", "/", " ", ""]]
                    mask = df_transferencias['UF'].apply(
                        lambda x: any(pattern.lower() in str(x).lower() for pattern in patterns)
                    )
                    transferencias_origem_destino = df_transferencias[mask]
                    
                        # Se ainda não encontrar, verificar UF invertida (ex: "SC-RS" em vez de "RS-SC")
                    if transferencias_origem_destino.empty:
                        patterns_inv = [f"{uf_destino}{sep}{uf_origem}" for sep in ["-", "/", " ", ""]]
                        mask = df_transferencias['UF'].apply(
                            lambda x: any(pattern.lower() in str(x).lower() for pattern in patterns_inv)
                        )
                        transferencias_origem_destino = df_transferencias[mask]
            
            print(f"[TRANSFERENCIAS] Busca expandida encontrou: {len(transferencias_origem_destino)} transferências")
        
        print(f"[TRANSFERENCIAS] 🎯 Busca direta {origem} → {destino}: {len(transferencias_origem_destino)} encontradas")
        if not transferencias_origem_destino.empty:
            for _, transf in transferencias_origem_destino.iterrows():
                print(f"[TRANSFERENCIAS] ✅ Direta: {transf.get('Fornecedor')} | {transf.get('Origem')} → {transf.get('Destino')}")
        else:
            print(f"[TRANSFERENCIAS] ❌ Nenhuma transferência direta {origem} → {destino}")
            print(f"[TRANSFERENCIAS] 🔍 Buscando rotas alternativas via bases...")
            
            # Mapa de proximidade geográfica entre estados (apenas adjacentes diretos)
            # Limitado apenas a estados realmente próximos
            proximidade_estados = {
                'RS': ['SC'],  # RS só faz fronteira com SC
                'SC': ['RS', 'PR'],  # SC faz fronteira com RS e PR
                'PR': ['SC', 'SP', 'MS'],  # PR faz fronteira com SC, SP e MS
                'SP': ['PR', 'MG', 'RJ', 'MS'],
                'RJ': ['SP', 'MG', 'ES'],
                'MG': ['SP', 'RJ', 'ES', 'BA', 'GO', 'MS', 'DF'],
                'MS': ['PR', 'SP', 'MG', 'GO', 'MT'],
                'ES': ['RJ', 'MG', 'BA'],
                'BA': ['ES', 'MG', 'GO', 'TO', 'PI', 'PE', 'AL', 'SE'],
                # Remover estados distantes do Sul
            }
            
            # Função para calcular nível de proximidade entre estados
            def calcular_proximidade_estados(estado1, estado2):
                if not estado1 or not estado2:
                    return 999  # Estados inválidos = baixa prioridade
                    
                estado1 = estado1.upper()
                estado2 = estado2.upper()
                
                if estado1 == estado2:
                    return 0  # Mesmo estado = máxima prioridade
                elif estado1 in proximidade_estados and estado2 in proximidade_estados[estado1]:
                    return 1  # Estado adjacente = alta prioridade
                elif estado2 in proximidade_estados and estado1 in proximidade_estados[estado2]:
                    return 1  # Estado adjacente = alta prioridade
                else:
                    # Verificar se há um estado intermediário conectando os dois
                    for estado_intermediario in proximidade_estados.get(estado1, []):
                        if estado2 in proximidade_estados.get(estado_intermediario, []):
                            return 2  # Um estado de distância = prioridade média
                    return 3  # Mais distante = baixa prioridade
            
            # MÉTODO 3: Buscar transferências via estados ADJACENTES apenas
            print(f"[TRANSFERENCIAS] 🌍 MÉTODO 3: Buscando transferências via estados adjacentes...")
            
            # Para RS → SC, só considerar estados que fazem fronteira direta
            estados_proximos = []
            
            # Se origem é RS e destino é SC, são adjacentes diretos
            if uf_origem == 'RS' and uf_destino == 'SC':
                print(f"[TRANSFERENCIAS] ✅ {uf_origem} e {uf_destino} são estados adjacentes")
                # Não precisa de estado intermediário, mas vamos buscar rotas via cidades principais
                # Focar em cidades de divisa ou principais
                estados_proximos = []  # Sem estados intermediários necessários
            
            # Se origem é RS e destino não é adjacente, usar SC como intermediário
            elif uf_origem == 'RS' and uf_destino in ['PR', 'SP']:
                estados_proximos = [('SC', 1)]  # SC como intermediário
            
            # Para outros casos no Sul
            elif uf_origem in ['RS', 'SC', 'PR'] and uf_destino in ['RS', 'SC', 'PR']:
                # Verificar adjacência direta
                if uf_destino in proximidade_estados.get(uf_origem, []):
                    estados_proximos = []  # São adjacentes, não precisa intermediário
                else:
                    # Encontrar estado intermediário comum
                    for estado_inter in ['SC', 'PR']:  # Apenas estados do Sul
                        if (estado_inter in proximidade_estados.get(uf_origem, []) and 
                            uf_destino in proximidade_estados.get(estado_inter, [])):
                            estados_proximos.append((estado_inter, 1))
                            break
            
            # Máximo de estados intermediários a tentar
            max_estados_intermediarios = 2  # Reduzido para focar apenas em rotas diretas
            estados_tentados = 0
            max_transferencias = 5  # Limite reduzido
            
            # Buscar transferências via estados intermediários próximos
            print(f"[TRANSFERENCIAS] 🔍 Buscando por estados intermediários: {[e[0] for e in estados_proximos[:max_estados_intermediarios]]}")
            
            for estado_intermediario, nivel_proximidade in estados_proximos:
                if estados_tentados >= max_estados_intermediarios or len(transferencias_origem_destino) >= max_transferencias:
                    break
                
                estados_tentados += 1
                print(f"[TRANSFERENCIAS] 🔄 Tentando via estado {estado_intermediario} (proximidade: {nivel_proximidade})")
                
                # Tentar usar geolocalização para encontrar municípios com base no estado intermediário
                try:
                    # Primeiro, tenta encontrar municípios com agentes no estado intermediário
                    municipios_intermediario = obter_municipios_com_base(estado_intermediario)
                    print(f"[GEOLOC] 🌍 Analisando {len(municipios_intermediario)} municípios com base em {estado_intermediario}")
                    
                    # Se não encontrou municípios com agentes, busca cidades próximas em um raio de 80km
                    if not municipios_intermediario:
                        print(f"[GEOLOC] ⚠️ Nenhum município com agente encontrado em {estado_intermediario}, buscando cidades próximas em um raio de 80km...")
                        
                        # Obtém a localização geográfica do centro do estado
                        try:
                            # Tenta obter coordenadas de uma cidade principal do estado
                            cidades_estado = {
                                'RS': 'Porto Alegre', 'SC': 'Florianópolis', 'PR': 'Curitiba',
                                'SP': 'São Paulo', 'RJ': 'Rio de Janeiro', 'MG': 'Belo Horizonte',
                                'ES': 'Vitória', 'BA': 'Salvador', 'SE': 'Aracaju', 'AL': 'Maceió',
                                'PE': 'Recife', 'PB': 'João Pessoa', 'RN': 'Natal', 'CE': 'Fortaleza',
                                'PI': 'Teresina', 'MA': 'São Luís', 'PA': 'Belém', 'AP': 'Macapá',
                                'AM': 'Manaus', 'RR': 'Boa Vista', 'AC': 'Rio Branco', 'RO': 'Porto Velho',
                                'MT': 'Cuiabá', 'MS': 'Campo Grande', 'GO': 'Goiânia', 'DF': 'Brasília',
                                'TO': 'Palmas'
                            }
                            
                            cidade_referencia = cidades_estado.get(estado_intermediario, estado_intermediario)
                            localizacao = geocode(cidade_referencia, estado_intermediario)
                            
                            if localizacao:
                                # Busca cidades em um raio de 80km
                                cidades_proximas = encontrar_municipios_proximos(
                                    cidade_referencia, 
                                    estado_intermediario, 
                                    raio_km=80, 
                                    limite=10  # Limita a 10 cidades para não sobrecarregar
                                )
                                
                                if cidades_proximas:
                                    print(f"[GEOLOC] 🔍 Encontradas {len(cidades_proximas)} cidades próximas em um raio de 80km")
                                    municipios_intermediario = [
                                        {'nome': cidade, 'uf': uf, 'distancia': dist} 
                                        for cidade, uf, dist in grcidades_proximas
                                    ]
                        except Exception as e:
                            print(f"[GEOLOC] ⚠️ Erro ao buscar cidades próximas: {str(e)}")
                    
                    # Se encontrou municípios (seja com agentes ou cidades próximas), tenta encontrar transferências
                    if municipios_intermediario:
                        transferencias_primeiro_trecho = pd.DataFrame()  # Começar com DF vazio
                        
                        # Adiciona mensagem de aviso se estiver usando localização alternativa
                        if not municipios_intermediario[0].get('tem_agente', True):
                            print("[GEOLOC] ℹ️ Utilizando localização alternativa (sem agente no local exato)")
                            # Adiciona mensagem ao contexto para ser usada na resposta
                            if 'aviso' not in locals():
                                aviso = "⚠️ Atenção: Não foram encontrados agentes no local exato. Os resultados incluem opções em cidades próximas. Por favor, consulte o parceiro para confirmar disponibilidade."
                        else:
                            print("[GEOLOC] ℹ️ Utilizando localização com agente no local exato")
                        
                        # Ordenar municípios por distância (se disponível) ou alfabeticamente
                        municipios_ordenados = sorted(
                            municipios_intermediario, 
                            key=lambda x: x.get('distancia', float('inf'))
                        )
                        
                        for municipio in municipios_ordenados:
                            nome_municipio = municipio['nome']
                            distancia = municipio.get('distancia', 'N/A')
                            print(f"[GEOLOC] 📍 Verificando transferências via {nome_municipio}/{estado_intermediario} (distância: {distancia}km)")
                            
                            # Buscar transferências que passam por esse município
                            transf_via_municipio = df_transferencias[
                                ((df_transferencias['Base Origem'].str.contains(uf_origem, case=False, na=False)) |
                                 (df_transferencias['Origem'].str.contains(uf_origem, case=False, na=False))) &
                                ((df_transferencias['Base Destino'].str.contains(nome_municipio, case=False, na=False)) |
                                 (df_transferencias['Destino'].str.contains(nome_municipio, case=False, na=False)))
                            ]
                            
                            # Adicionar ao dataframe principal se encontrou
                            if not transf_via_municipio.empty:
                                print(f"[GEOLOC] ✅ Encontradas {len(transf_via_municipio)} transferências via {nome_municipio} (distância: {distancia}km)")
                                
                                # Adiciona flag de localização alternativa
                                if distancia != 'N/A' and float(distancia) > 0:
                                    transf_via_municipio['localizacao_alternativa'] = True
                                    transf_via_municipio['mensagem_aviso'] = f"⚠️ Agente localizado em {nome_municipio} (a {distancia}km do destino solicitado). Por favor, consulte o parceiro para confirmar disponibilidade."
                                
                                transferencias_primeiro_trecho = pd.concat([transferencias_primeiro_trecho, transf_via_municipio])
                                
                                # Limita o número de transferências para evitar sobrecarga
                                if len(transferencias_primeiro_trecho) >= 5:
                                    print(f"[GEOLOC] ⏹️ Limite de 5 transferências atingido")
                                    break
                                
                                # Se já encontrou transferências suficientes, parar
                                if len(transferencias_primeiro_trecho) >= 3:
                                    break
                        
                        # Se não encontrou nada via municípios, voltar à busca normal por estado
                        if transferencias_primeiro_trecho.empty:
                            print(f"[GEOLOC] ℹ️ Não encontrou transferências via municípios, voltando à busca por estado")
                            transferencias_primeiro_trecho = df_transferencias[
                                ((df_transferencias['Base Origem'].str.contains(uf_origem, case=False, na=False)) |
                                 (df_transferencias['Origem'].str.contains(uf_origem, case=False, na=False))) &
                                ((df_transferencias['Base Destino'].str.contains(estado_intermediario, case=False, na=False)) |
                                 (df_transferencias['Destino'].str.contains(estado_intermediario, case=False, na=False)))
                            ]
                    else:
                        # Caso não tenha encontrado municípios com base, usar a busca normal por estado
                        transferencias_primeiro_trecho = df_transferencias[
                            ((df_transferencias['Base Origem'].str.contains(uf_origem, case=False, na=False)) |
                             (df_transferencias['Origem'].str.contains(uf_origem, case=False, na=False))) &
                            ((df_transferencias['Base Destino'].str.contains(estado_intermediario, case=False, na=False)) |
                             (df_transferencias['Destino'].str.contains(estado_intermediario, case=False, na=False)))
                        ]
                except Exception as e:
                    print(f"[GEOLOC] ❌ Erro ao usar geolocaliização para primeiro trecho: {e}")
                    # Em caso de erro, voltar à busca normal por estado
                    transferencias_primeiro_trecho = df_transferencias[
                        ((df_transferencias['Base Origem'].str.contains(uf_origem, case=False, na=False)) |
                         (df_transferencias['Origem'].str.contains(uf_origem, case=False, na=False))) &
                        ((df_transferencias['Base Destino'].str.contains(estado_intermediario, case=False, na=False)) |
                         (df_transferencias['Destino'].str.contains(estado_intermediario, case=False, na=False)))
                    ]
                
                # Tentar usar geolocalização para encontrar municípios com base no estado intermediário para o segundo trecho
                try:
                    # Para o segundo trecho, já temos os municípios do estado intermediário
                    # Agora também vamos verificar municípios de destino com base
                    municipios_destino = obter_municipios_com_base(uf_destino)
                    print(f"[GEOLOC] 🌍 Analisando {len(municipios_destino)} municípios com base em {uf_destino}")
                    
                    # Se encontrou municípios com base no destino, priorizamos eles
                    if municipios_destino and 'municipios_intermediario' in locals() and municipios_intermediario:
                        transferencias_segundo_trecho = pd.DataFrame()  # Começar com DF vazio
                        
                        # Tentar todas as combinações de municípios de origem e destino
                        for mun_inter in municipios_intermediario[:5]:  # Limitar a 5 municípios de origem
                            nome_mun_inter = mun_inter['nome']
                            
                            for mun_dest in municipios_destino[:5]:  # Limitar a 5 municípios de destino
                                nome_mun_dest = mun_dest['nome']
                                
                                print(f"[GEOLOC] 📍 Verificando rota {nome_mun_inter}/{estado_intermediario} → {nome_mun_dest}/{uf_destino}")
                                
                                # Buscar transferências entre esses municípios
                                transf_municipio_a_municipio = df_transferencias[
                                    ((df_transferencias['Base Origem'].str.contains(nome_mun_inter, case=False, na=False)) |
                                     (df_transferencias['Origem'].str.contains(nome_mun_inter, case=False, na=False))) &
                                    ((df_transferencias['Base Destino'].str.contains(nome_mun_dest, case=False, na=False)) |
                                     (df_transferencias['Destino'].str.contains(nome_mun_dest, case=False, na=False)))
                                ]
                                
                                # Se encontrou, adicionar ao dataframe principal
                                if not transf_municipio_a_municipio.empty:
                                    print(f"[GEOLOC] ✅ Encontradas {len(transf_municipio_a_municipio)} transferências {nome_mun_inter} → {nome_mun_dest}")
                                    transferencias_segundo_trecho = pd.concat([transferencias_segundo_trecho, transf_municipio_a_municipio])
                                    
                                    # Se já encontrou transferências suficientes, parar
                                    if len(transferencias_segundo_trecho) >= 3:
                                        break
                            
                            # Se já encontrou transferências suficientes, parar o loop externo também
                            if len(transferencias_segundo_trecho) >= 3:
                                break
                    
                    # Se não encontrou nada ou não temos municípios, voltar à busca normal por estado
                    if 'transferencias_segundo_trecho' not in locals() or transferencias_segundo_trecho.empty:
                        print(f"[GEOLOC] ℹ️ Não encontrou transferências via municípios no segundo trecho, voltando à busca por estado")
                        transferencias_segundo_trecho = df_transferencias[
                            ((df_transferencias['Base Origem'].str.contains(estado_intermediario, case=False, na=False)) |
                             (df_transferencias['Origem'].str.contains(estado_intermediario, case=False, na=False))) &
                            ((df_transferencias['Base Destino'].str.contains(uf_destino, case=False, na=False)) |
                             (df_transferencias['Destino'].str.contains(uf_destino, case=False, na=False)))
                        ]
                except Exception as e:
                    print(f"[GEOLOC] ❌ Erro ao usar geolocaliização para segundo trecho: {e}")
                    # Em caso de erro, voltar à busca normal por estado
                    transferencias_segundo_trecho = df_transferencias[
                        ((df_transferencias['Base Origem'].str.contains(estado_intermediario, case=False, na=False)) |
                         (df_transferencias['Origem'].str.contains(estado_intermediario, case=False, na=False))) &
                        ((df_transferencias['Base Destino'].str.contains(uf_destino, case=False, na=False)) |
                         (df_transferencias['Destino'].str.contains(uf_destino, case=False, na=False)))
                    ]
                
                if not transferencias_primeiro_trecho.empty and not transferencias_segundo_trecho.empty:
                    print(f"[TRANSFERENCIAS] ✅ Encontradas {len(transferencias_primeiro_trecho)} transferências para {estado_intermediario} e {len(transferencias_segundo_trecho)} de {estado_intermediario} para {uf_destino}")
                    
                    # Marcar as transferências como 'via_estado_intermediario' para identificar que são do MÉTODO 3
                    for _, transf in transferencias_primeiro_trecho.iterrows():
                        # Cria uma cópia da transferência e adiciona metadados
                        transf_dict = transf.to_dict()
                        transf_dict['via_estado_intermediario'] = estado_intermediario
                        transf_dict['nivel_proximidade'] = nivel_proximidade
                        transf_dict['metodo'] = '3_PROXIMIDADE_GEOGRAFICA'
                        
                        # Adiciona à lista de transferências
                        transferencias_origem_destino = pd.concat([transferencias_origem_destino, pd.DataFrame([transf_dict])])
                    
                    # Também armazenar as transferências do segundo trecho (estado intermediário -> destino)
                    # para uso posterior na construção da rota completa
                    for _, transf2 in transf_intermediario_destino.iterrows():
                        # Armazenar em uma lista separada para uso posterior
                        if 'transferencias_segundo_trecho' not in locals():
                            transferencias_segundo_trecho = []
                        transferencias_segundo_trecho.append({
                            'transferencia': transf2,
                            'estado_intermediario': estado_intermediario,
                            'nivel_proximidade': nivel_proximidade
                        })
                        
                    # Se já temos transferências suficientes, podemos parar
                    if len(transferencias_origem_destino) >= max_transferencias:
                        print(f"[TRANSFERENCIAS] ✅ Limite de transferências atingido ({max_transferencias})")
                        break
        
        # Função genérica para obter cidade da base (sem mapeamento específico)
        def obter_cidade_base(codigo_base):
            if len(str(codigo_base)) > 3:
                return str(codigo_base)
            return str(codigo_base)
            
        # Mapa de proximidade geográfica entre estados (adjacentes + próximos)
        # Usado para priorizar transferências entre estados vizinhos
        ESTADOS_PROXIMOS = {
            'RS': ['SC', 'PR'],
            'SC': ['RS', 'PR'],
            'PR': ['SC', 'SP', 'MS'],
            'SP': ['RJ', 'MG', 'MS', 'PR'],
            'RJ': ['SP', 'MG', 'ES'],
            'ES': ['BA', 'MG', 'RJ'],
            'MG': ['SP', 'GO', 'DF', 'BA', 'ES', 'RJ'],
            'MS': ['SP', 'PR', 'MT', 'GO'],
            'MT': ['MS', 'GO', 'RO'],
            'GO': ['DF', 'MG', 'BA', 'TO', 'MT', 'MS'],
            'DF': ['GO', 'MG'],
            'BA': ['SE', 'AL', 'PE', 'MG', 'ES'],
            'SE': ['BA', 'AL'],
            'AL': ['SE', 'BA', 'PE'],
            'PE': ['PB', 'CE', 'BA', 'AL'],
            'PB': ['RN', 'CE', 'PE'],
            'RN': ['CE', 'PB'],
            'CE': ['PI', 'PE', 'PB', 'RN'],
            'PI': ['CE', 'MA', 'BA'],
            'MA': ['PA', 'PI'],
            'TO': ['PA', 'MT', 'GO', 'BA'],
            'PA': ['AP', 'MA', 'TO'],
            'AP': ['PA'],
            'AM': ['RR', 'RO', 'AC'],
            'RR': ['AM'],
            'AC': ['AM', 'RO'],
            'RO': ['AM', 'MT', 'AC']
        }
        
        # Função para calcular proximidade entre estados (0 = mesmo estado, 1 = vizinhos, 2 = segundo grau...)
        def calcular_proximidade_estados(uf1, uf2):
            if uf1 == uf2:
                return 0
            if uf1 in ESTADOS_PROXIMOS and uf2 in ESTADOS_PROXIMOS[uf1]:
                return 1
            # Verificar vizinhos de segundo grau
            if uf1 in ESTADOS_PROXIMOS:
                for estado_vizinho in ESTADOS_PROXIMOS[uf1]:
                    if uf2 in ESTADOS_PROXIMOS.get(estado_vizinho, []):
                        return 2
            return 3  # Distantes
        
        # Buscar transferências para bases dos agentes de entrega
        # Priorizar agentes em estados vizinhos ou próximos ao estado de origem
        if not agentes_entrega.empty:
            # Adicionar campo de proximidade para ordenar agentes
            agentes_list = []
            for _, agente in agentes_entrega.iterrows():
                uf_agente = agente.get('UF', '')
                proximidade = calcular_proximidade_estados(uf_origem, uf_agente)
                agentes_list.append((agente, proximidade))
            
            # Ordenar agentes por proximidade geográfica
            agentes_list.sort(key=lambda x: x[1])
            print(f"[AGENTES] 📍 Agentes ordenados por proximidade geográfica: {len(agentes_list)}")
        else:
            agentes_list = []
            print(f"[AGENTES] ⚠️ Nenhum agente de entrega para ordenar por proximidade")
        
        # Percorrer agentes ordenados por proximidade - LIMITAR APENAS A ESTADOS PRÓXIMOS
        transferencias_para_bases = []
        for agente_ent, proximidade in agentes_list:
            # FILTRAR: Só considerar agentes em estados próximos (proximidade <= 1)
            if proximidade > 1:
                print(f"[TRANSFERENCIAS] ⏭️ Ignorando agente {agente_ent.get('Fornecedor', 'N/A')} - estado muito distante (proximidade: {proximidade})")
                continue
                
            print(f"[TRANSFERENCIAS] 🔍 Buscando transferências para base do agente {agente_ent.get('Fornecedor', 'N/A')} (proximidade: {proximidade})")
            fornecedor_ent = agente_ent.get('Fornecedor', 'N/A')
            base_agente = agente_ent.get('Base Origem') or agente_ent.get('Base Destino', '')
            
            if base_agente:
                cidade_base = obter_cidade_base(str(base_agente))
                cidade_base_norm = normalizar_cidade_nome(str(cidade_base))
                
                # Buscar transferências com fallback para colunas UF
                print(f"[TRANSFERENCIAS] 🔍 Buscando transferência: {origem_norm} → {cidade_base_norm}")
                transf_para_base = df_transferencias[
                    (df_transferencias['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_norm)) &
                    (df_transferencias['Destino'].apply(lambda x: normalizar_cidade_nome(str(x)) == cidade_base_norm))
                ]
                
                # Se não encontrar, tentar busca expandida usando UF
                if transf_para_base.empty:
                    base_uf = agente_ent.get('UF', '')
                    if base_uf:
                        print(f"[TRANSFERENCIAS] 🔍 Busca expandida para base {cidade_base_norm} via UF {uf_origem} → {base_uf}...")
                        # Verificando as colunas disponíveis para UF
                        if 'UF Origem' in df_transferencias.columns and 'UF Destino' in df_transferencias.columns:
                            transf_para_base = df_transferencias[
                                (df_transferencias['UF Origem'] == uf_origem) &
                                (df_transferencias['UF Destino'] == base_uf)
                            ]
                        else:
                            # Fallback usando a coluna UF e Base Origem/Base Destino para determinar UFs
                            transf_para_base = df_transferencias[
                                (df_transferencias['Base Origem'].str.contains(uf_origem, case=False, na=False)) &
                                (df_transferencias['Base Destino'].str.contains(base_uf, case=False, na=False))
                            ]
                            
                            # Se ainda vazio, tentar busca mais flexível por Base Origem OU Base Destino
                            if transf_para_base.empty:
                                print(f"[TRANSFERENCIAS] 🔍 Tentando busca flexível de bases entre {uf_origem} e {base_uf}...")
                                # Buscar qualquer transferência que mencione as UFs nas bases ou nas cidades
                                transf_para_base = df_transferencias[
                                    ((df_transferencias['Base Origem'].str.contains(uf_origem, case=False, na=False)) |
                                     (df_transferencias['Origem'].str.contains(uf_origem, case=False, na=False))) &
                                    ((df_transferencias['Base Destino'].str.contains(base_uf, case=False, na=False)) |
                                     (df_transferencias['Destino'].str.contains(base_uf, case=False, na=False)))
                                ]
                            
                            # Buscar na coluna UF com vários padrões
                            if transf_para_base.empty and 'UF' in df_transferencias.columns:
                                # Tentar usar a coluna UF com diferentes padrões
                                print(f"[TRANSFERENCIAS] 🔄 Tentando busca avançada na coluna UF entre {uf_origem} e {base_uf}...")
                                # Verificar vários padrões comuns: "PR-MG", "PR/MG", etc
                                patterns = [f"{uf_origem}{sep}{base_uf}" for sep in ["-", "/", " ", ""]]
                                mask = df_transferencias['UF'].apply(
                                    lambda x: any(pattern.lower() in str(x).lower() for pattern in patterns)
                                )
                                transf_para_base = df_transferencias[mask]
                                
                                # Se ainda não encontrar, verificar UF invertida (ex: "MG-PR" em vez de "PR-MG")
                                if transf_para_base.empty:
                                    patterns_inv = [f"{base_uf}{sep}{uf_origem}" for sep in ["-", "/", " ", ""]]
                                    mask = df_transferencias['UF'].apply(
                                        lambda x: any(pattern.lower() in str(x).lower() for pattern in patterns_inv)
                                    )
                                    transf_para_base = df_transferencias[mask]
                
                if not transf_para_base.empty:
                    for _, transf in transf_para_base.iterrows():
                        transferencias_para_bases.append({
                            'transferencia': transf,
                            'agente_entrega': agente_ent,
                            'base_destino': cidade_base_norm,
                            'codigo_base': base_agente
                        })

        # Declarar a variável para armazenar transferências do segundo trecho do MÉTODO 3
        if 'transferencias_segundo_trecho' not in locals():
            transferencias_segundo_trecho = []
            print(f"[TRANSFERENCIAS] ℹ️ Não há transferências de segundo trecho do MÉTODO 3")
        else:
            print(f"[TRANSFERENCIAS] ✅ Encontradas {len(transferencias_segundo_trecho)} transferências de segundo trecho para rotas via estados próximos")
        
        # Se há agentes de coleta E transferências cidade→cidade, criar rotas
        if not agentes_coleta.empty and not transferencias_origem_destino.empty:
            for _, agente_col in agentes_coleta.iterrows():
                fornecedor_col = agente_col.get('Fornecedor', 'N/A')
                peso_cubado_col = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_col.get('Tipo', 'Agente'), agente_col.get('Fornecedor'))
                custo_coleta = calcular_custo_agente(agente_col, peso_cubado_col, valor_nf)
                if custo_coleta:
                    for _, transf in transferencias_origem_destino.iterrows():
                        # Verificar limite antes de continuar
                        if len(rotas_encontradas) >= MAX_ROTAS:
                            break
                        fornecedor_transf = transf.get('Fornecedor', 'N/A')
                        peso_cubado_transf = calcular_peso_cubado_por_tipo(peso_real, cubagem, transf.get('Tipo', 'Transferência'), transf.get('Fornecedor'))
                        custo_transferencia = calcular_custo_agente(transf, peso_cubado_transf, valor_nf)
                        if custo_transferencia:
                            # SEMPRE incluir agente de entrega
                            for _, agente_ent in agentes_entrega.iterrows():
                                fornecedor_ent = agente_ent.get('Fornecedor', 'N/A')
                                
                                # 🔧 CONTROLE DE DUPLICATAS MELHORADO
                                chave_rota = gerar_chave_rota(fornecedor_col, fornecedor_transf, fornecedor_ent)
                                if chave_rota in rotas_processadas:
                                    print(f"[AGENTES] ⚠️ Rota duplicada ignorada: {chave_rota}")
                                    continue
                                rotas_processadas.add(chave_rota)
                                
                                peso_cubado_ent = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_ent.get('Tipo', 'Agente'), agente_ent.get('Fornecedor'))
                                custo_entrega = calcular_custo_agente(agente_ent, peso_cubado_ent, valor_nf)
                                if custo_entrega:
                                    total = custo_coleta['total'] + custo_transferencia['total'] + custo_entrega['total']
                                    prazo_total = max(
                                        custo_coleta.get('prazo', 1),
                                        custo_transferencia.get('prazo', 1),
                                        custo_entrega.get('prazo', 1)
                                    )
                                    
                                    # 🆕 VALIDAÇÃO ADICIONAL - evitar valores inválidos
                                    if total <= 0:
                                        print(f"[AGENTES] ❌ Rota com total inválido ignorada: {chave_rota}")
                                        continue
                                    
                                    rota = {
                                        'tipo_rota': 'coleta_transferencia_entrega',
                                        'resumo': f"{custo_coleta['fornecedor']} (Coleta) + {custo_transferencia['fornecedor']} (Transferência) + {custo_entrega['fornecedor']} (Entrega)",
                                        'total': total,
                                        'prazo_total': prazo_total,
                                        'maior_peso': peso_cubado,
                                        'peso_usado': 'Real' if peso_real >= peso_cubado else 'Cubado',
                                        'detalhamento_custos': {
                                            'coleta': custo_coleta['total'],
                                            'transferencia': custo_transferencia['total'],
                                            'entrega': custo_entrega['total'],
                                            'pedagio': custo_coleta.get('pedagio', 0) + custo_transferencia.get('pedagio', 0) + custo_entrega.get('pedagio', 0),
                                            'gris_total': custo_coleta.get('gris', 0) + custo_transferencia.get('gris', 0) + custo_entrega.get('gris', 0)
                                        },
                                        'observacoes': f"Rota completa: {fornecedor_col} + {fornecedor_transf} + {fornecedor_ent}",
                                        'status_rota': 'COMPLETA',
                                        'agente_coleta': custo_coleta,
                                        'transferencia': custo_transferencia,
                                        'agente_entrega': custo_entrega,
                                        'chave_unica': chave_rota  # 🆕 Para debug
                                    }
                                    rotas_encontradas.append(rota)
                                    print(f"[AGENTES] ✅ Rota COMPLETA adicionada: {chave_rota} - R$ {total:.2f}")
                                    
                                    # Verificar limite máximo
                                    if len(rotas_encontradas) >= MAX_ROTAS:
                                        print(f"[AGENTES] ⚠️ Limite máximo de {MAX_ROTAS} rotas atingido - interrompendo busca")
                                        break

        # Se há agentes de coleta mas não há transferências diretas, tentar via bases
        elif not agentes_coleta.empty and transferencias_origem_destino.empty:
            if transferencias_para_bases:
                for item in transferencias_para_bases:
                    transf = item['transferencia']
                    agente_ent = item['agente_entrega']
                    base_destino = item['base_destino']
                    
                    for _, agente_col in agentes_coleta.iterrows():
                        fornecedor_col = agente_col.get('Fornecedor', 'N/A')
                        fornecedor_transf = transf.get('Fornecedor', 'N/A')
                        fornecedor_ent = agente_ent.get('Fornecedor', 'N/A')
                        
                        # Controle de duplicatas para rota via base
                        chave_rota = gerar_chave_rota(fornecedor_col, fornecedor_transf, fornecedor_ent)
                        if chave_rota in rotas_processadas:
                            continue
                        rotas_processadas.add(chave_rota)
                        
                        peso_cubado_col = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_col.get('Tipo', 'Agente'), agente_col.get('Fornecedor'))
                        peso_cubado_transf = calcular_peso_cubado_por_tipo(peso_real, cubagem, transf.get('Tipo', 'Transferência'), transf.get('Fornecedor'))
                        peso_cubado_ent = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_ent.get('Tipo', 'Agente'), agente_ent.get('Fornecedor'))
                        custo_coleta = calcular_custo_agente(agente_col, peso_cubado_col, valor_nf)
                        custo_transferencia = calcular_custo_agente(transf, peso_cubado_transf, valor_nf)
                        custo_entrega = calcular_custo_agente(agente_ent, peso_cubado_ent, valor_nf)
                        
                        if custo_coleta and custo_transferencia and custo_entrega:
                            total = custo_coleta['total'] + custo_transferencia['total'] + custo_entrega['total']
                            prazo_total = max(
                                custo_coleta.get('prazo', 1),
                                custo_transferencia.get('prazo', 1),
                                custo_entrega.get('prazo', 1)
                            )
                            
                            rota = {
                                'tipo_rota': 'coleta_transferencia_entrega_via_base',
                                'resumo': f"{fornecedor_col} (Coleta) + {fornecedor_transf} (Transferência) + {fornecedor_ent} (Entrega via {base_destino})",
                                'total': total,
                                'prazo_total': prazo_total,
                                'maior_peso': peso_cubado,
                                'peso_usado': 'Real' if peso_real >= peso_cubado else 'Cubado',
                                'detalhamento_custos': {
                                    'coleta': custo_coleta['total'],
                                    'transferencia': custo_transferencia['total'],
                                    'entrega': custo_entrega['total'],
                                    'pedagio': custo_coleta.get('pedagio', 0) + custo_transferencia.get('pedagio', 0) + custo_entrega.get('pedagio', 0),
                                    'gris_total': custo_coleta.get('gris', 0) + custo_transferencia.get('gris', 0) + custo_entrega.get('gris', 0)
                                },
                                'observacoes': f"Rota via base: {fornecedor_col} → {base_destino} → {destino}",
                                'status_rota': 'COMPLETA',
                                'agente_coleta': custo_coleta,
                                'transferencia': custo_transferencia,
                                'agente_entrega': custo_entrega
                            }
                            rotas_encontradas.append(rota)

        # 🎯 PRIORIDADE 1: TRANSFERÊNCIAS DIRETAS + AGENTES DE ENTREGA
        if not transferencias_origem_destino.empty and not agentes_entrega.empty:
            print(f"[ROTAS] 🏆 PRIORIDADE MÁXIMA: Transferências diretas + Agentes de entrega")
            
            for _, transf in transferencias_origem_destino.iterrows():
                fornecedor_transf = transf.get('Fornecedor', 'N/A')
                base_origem_transf = transf.get('Base Origem', origem_norm) 
                base_destino_transf = transf.get('Base Destino', destino_norm)
                peso_cubado_transf = calcular_peso_cubado_por_tipo(peso_real, cubagem, transf.get('Tipo', 'Transferência'), transf.get('Fornecedor'))
                custo_transferencia = calcular_custo_agente(transf, peso_cubado_transf, valor_nf)
                
                if custo_transferencia:
                    for _, agente_ent in agentes_entrega.iterrows():
                        fornecedor_ent = agente_ent.get('Fornecedor', 'N/A')
                        base_origem_ent = agente_ent.get('Base Origem', base_destino_transf)
                        peso_cubado_ent = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_ent.get('Tipo', 'Agente'), agente_ent.get('Fornecedor'))
                        custo_entrega = calcular_custo_agente(agente_ent, peso_cubado_ent, valor_nf)
                        
                        if custo_entrega:
                            total = custo_transferencia['total'] + custo_entrega['total']
                            prazo_total = max(custo_transferencia.get('prazo', 1), custo_entrega.get('prazo', 1))
                            
                            # ✅ ROTA BASES CORRIGIDA - mostra cidades reais, não bases intermediárias
                            rota_bases = f"{transf.get('Origem')} → {transf.get('Destino')}"
                            
                            rota = {
                                'tipo_rota': 'cliente_entrega_transferencia_agente_entrega',
                                'resumo': f"Cliente entrega na base → {fornecedor_transf} (Transferência) → {fornecedor_ent} (Entrega)",
                                'total': total,
                                'prazo_total': prazo_total,
                                'maior_peso': peso_cubado,
                                'peso_usado': 'Real' if peso_real >= peso_cubado else 'Cubado',
                                'rota_bases': rota_bases,  # ✅ CORREÇÃO: Mostra rota real das cidades
                                'detalhamento_custos': {
                                    'coleta': 0,  # Cliente entrega
                                    'transferencia': custo_transferencia['total'],
                                    'entrega': custo_entrega['total'],
                                    'pedagio': custo_transferencia.get('pedagio', 0) + custo_entrega.get('pedagio', 0),
                                    'gris_total': custo_transferencia.get('gris', 0) + custo_entrega.get('gris', 0)
                                },
                                'observacoes': f"Cliente entrega em {transf.get('Origem')} → Transferência direta → Entrega no {destino}",
                                'status_rota': 'DIRETA_COM_AGENTE_ENTREGA',
                                'agente_coleta': {
                                    'fornecedor': 'Cliente entrega na origem',
                                    'custo': 0,
                                    'total': 0,
                                    'pedagio': 0,
                                    'gris': 0,
                                    'seguro': 0,
                                    'prazo': 0,
                                    'sem_agente': True,
                                    'observacao': f"Cliente deve entregar a mercadoria em {transf.get('Origem')}"
                                },
                                'transferencia': {
                                    'fornecedor': fornecedor_transf,
                                    'rota': rota_bases,
                                    'total': custo_transferencia['total'],
                                    'pedagio': custo_transferencia.get('pedagio', 0),
                                    'gris': custo_transferencia.get('gris', 0),
                                    'prazo': custo_transferencia.get('prazo', 1),
                                    'base_origem': transf.get('Origem'),
                                    'base_destino': transf.get('Destino')
                                },
                                'agente_entrega': {
                                    'fornecedor': fornecedor_ent,
                                    'total': custo_entrega['total'],
                                    'pedagio': custo_entrega.get('pedagio', 0),
                                    'gris': custo_entrega.get('gris', 0),
                                    'prazo': custo_entrega.get('prazo', 1)
                                }
                            }
                            rotas_encontradas.append(rota)
                            print(f"[ROTAS] ✅ Rota DIRETA criada: {rota_bases} - R$ {total:.2f}")

        # Se não há agentes de coleta mas há transferências + agentes de entrega (FALLBACK apenas se não há rotas diretas)
        elif agentes_coleta.empty and not transferencias_origem_destino.empty and len(rotas_encontradas) == 0:
            print(f"[ROTAS] 🔄 FALLBACK: Sem agentes de coleta - Calculando: Transferência + Agente Entrega")
            
            for _, transf in transferencias_origem_destino.iterrows():
                fornecedor_transf = transf.get('Fornecedor', 'N/A')
                base_origem_transf = transf.get('Base Origem', origem_norm)
                base_destino_transf = transf.get('Base Destino', destino_norm)
                peso_cubado_transf = calcular_peso_cubado_por_tipo(peso_real, cubagem, transf.get('Tipo', 'Transferência'), transf.get('Fornecedor'))
                custo_transferencia = calcular_custo_agente(transf, peso_cubado_transf, valor_nf)

        # 3. ROTAS PARCIAIS: Agente Coleta + Transferência (sem agente de entrega)
        if not agentes_coleta.empty and agentes_entrega.empty:
            print(f"[AGENTES] 🔄 Calculando rotas parciais: Agente Coleta + Transferência ({len(agentes_coleta)} agentes)")
            
            for _, agente_col in agentes_coleta.iterrows():
                for _, transf in transferencias_origem_destino.iterrows():
                    try:
                        fornecedor_col = agente_col.get('Fornecedor', 'N/A')
                        fornecedor_transf = transf.get('Fornecedor', 'N/A')
                        
                        # Controle de duplicatas para rotas parciais
                        chave_rota = gerar_chave_rota(fornecedor_col, fornecedor_transf, "SEM_ENTREGA")
                        if chave_rota in rotas_processadas:
                            continue
                        rotas_processadas.add(chave_rota)
                        
                        peso_cubado_col = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_col.get('Tipo', 'Agente'), agente_col.get('Fornecedor'))
                        peso_cubado_transf = calcular_peso_cubado_por_tipo(peso_real, cubagem, transf.get('Tipo', 'Transferência'), transf.get('Fornecedor'))
                        
                        custo_coleta = calcular_custo_agente(agente_col, peso_cubado_col, valor_nf)
                        custo_transferencia = calcular_custo_agente(transf, peso_cubado_transf, valor_nf)
                        
                        if custo_coleta and custo_transferencia:
                            total = custo_coleta['total'] + custo_transferencia['total']
                            prazo_total = max(custo_coleta.get('prazo', 1), custo_transferencia.get('prazo', 1))
                            
                            rota = {
                                'tipo_rota': 'coleta_transferencia',
                                'resumo': f"{fornecedor_col} (Coleta) + {fornecedor_transf} (Transferência) - Cliente retira no destino",
                                'total': total,
                                'prazo_total': prazo_total,
                                'maior_peso': peso_cubado,
                                'peso_usado': 'Real' if peso_real >= peso_cubado else 'Cubado',
                                'detalhamento_custos': {
                                    'coleta': custo_coleta['total'],
                                    'transferencia': custo_transferencia['total'],
                                    'entrega': 0,
                                    'pedagio': custo_coleta.get('pedagio', 0) + custo_transferencia.get('pedagio', 0),
                                    'gris_total': custo_coleta.get('gris', 0) + custo_transferencia.get('gris', 0)
                                },
                                'observacoes': f"ROTA PARCIAL: Cliente deve retirar a mercadoria em {destino}",
                                'status_rota': 'PARCIAL',
                                'agente_coleta': custo_coleta,
                                'transferencia': custo_transferencia,
                                'agente_entrega': {
                                    'fornecedor': 'Cliente retira no destino',
                                    'custo': 0,
                                    'total': 0,
                                    'pedagio': 0,
                                    'gris': 0,
                                    'seguro': 0,
                                    'prazo': 0,
                                    'sem_agente': True,
                                    'observacao': f"Cliente deve retirar a mercadoria em {destino}"
                                }
                            }
                            rotas_encontradas.append(rota)
                    except Exception as e:
                        continue

        # 4. ROTAS PARCIAIS: Transferência + Agente Entrega (sem agente de coleta)
        elif agentes_coleta.empty and not agentes_entrega.empty:
            print(f"[AGENTES] 🔄 Calculando rotas parciais: Transferência + Agente Entrega ({len(agentes_entrega)} agentes)")
            
            for _, transf in transferencias_origem_destino.iterrows():
                for _, agente_ent in agentes_entrega.iterrows():
                    try:
                        fornecedor_transf = transf.get('Fornecedor', 'N/A')
                        fornecedor_ent = agente_ent.get('Fornecedor', 'N/A')
                        
                        peso_cubado_transf = calcular_peso_cubado_por_tipo(peso_real, cubagem, transf.get('Tipo', 'Transferência'), transf.get('Fornecedor'))
                        peso_cubado_ent = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_ent.get('Tipo', 'Agente'), agente_ent.get('Fornecedor'))
                        
                        custo_transferencia = calcular_custo_agente(transf, peso_cubado_transf, valor_nf)
                        custo_entrega = calcular_custo_agente(agente_ent, peso_cubado_ent, valor_nf)
                        
                        if custo_transferencia and custo_entrega:
                            total = custo_transferencia['total'] + custo_entrega['total']
                            prazo_total = max(custo_transferencia.get('prazo', 1), custo_entrega.get('prazo', 1))
                            
                            rota = {
                                'tipo_rota': 'transferencia_entrega',
                                'resumo': f"{fornecedor_transf} (Transferência) + {fornecedor_ent} (Entrega) - Cliente entrega na origem",
                                'total': total,
                                'prazo_total': prazo_total,
                                'maior_peso': peso_cubado,
                                'peso_usado': 'Real' if peso_real >= peso_cubado else 'Cubado',
                                'detalhamento_custos': {
                                    'coleta': 0,
                                    'transferencia': custo_transferencia['total'],
                                    'entrega': custo_entrega['total'],
                                    'pedagio': custo_transferencia.get('pedagio', 0) + custo_entrega.get('pedagio', 0),
                                    'gris_total': custo_transferencia.get('gris', 0) + custo_entrega.get('gris', 0)
                                },
                                'observacoes': f"ROTA PARCIAL: Cliente deve entregar a mercadoria em {origem}",
                                'status_rota': 'PARCIAL',
                                'agente_coleta': {
                                    'fornecedor': 'Cliente entrega na origem',
                                    'custo': 0,
                                    'total': 0,
                                    'pedagio': 0,
                                    'gris': 0,
                                    'seguro': 0,
                                    'prazo': 0,
                                    'sem_agente': True,
                                    'observacao': f"Cliente deve entregar a mercadoria em {origem}"
                                },
                                'transferencia': custo_transferencia,
                                'agente_entrega': custo_entrega
                            }
                            rotas_encontradas.append(rota)
                    except Exception as e:
                        continue

        # 5. TRANSFERÊNCIAS DIRETAS: Quando não há agentes (nem coleta nem entrega)
        elif agentes_coleta.empty and agentes_entrega.empty and not transferencias_origem_destino.empty:
            print(f"[AGENTES] 🔄 Calculando transferências diretas: {len(transferencias_origem_destino)} opções")
            
            for _, transf in transferencias_origem_destino.iterrows():
                try:
                    fornecedor_transf = transf.get('Fornecedor', 'N/A')
                    
                    # Controle de duplicatas para transferências diretas
                    chave_rota = gerar_chave_rota("SEM_COLETA", fornecedor_transf, "SEM_ENTREGA")
                    if chave_rota in rotas_processadas:
                        continue
                    rotas_processadas.add(chave_rota)
                    
                    peso_cubado_transf = calcular_peso_cubado_por_tipo(peso_real, cubagem, transf.get('Tipo', 'Transferência'), transf.get('Fornecedor'))
                    custo_transferencia = calcular_custo_agente(transf, peso_cubado_transf, valor_nf)
                    
                    if custo_transferencia:
                        rota = {
                            'tipo_rota': 'transferencia_direta',
                            'resumo': f"{fornecedor_transf} - Transferência Direta (Cliente entrega e retira)",
                            'total': custo_transferencia['total'],
                            'prazo_total': custo_transferencia.get('prazo', 1),
                            'maior_peso': peso_cubado,
                            'peso_usado': 'Real' if peso_real >= peso_cubado else 'Cubado',
                            'detalhamento_custos': {
                                'coleta': 0,
                                'transferencia': custo_transferencia['total'],
                                'entrega': 0,
                                'pedagio': custo_transferencia.get('pedagio', 0),
                                'gris_total': custo_transferencia.get('gris', 0)
                            },
                            'observacoes': f"TRANSFERÊNCIA DIRETA: Cliente entrega em {origem} e retira em {destino}",
                            'status_rota': 'DIRETA',
                            'agente_coleta': {
                                'fornecedor': 'Cliente entrega na origem',
                                'custo': 0,
                                'total': 0,
                                'pedagio': 0,
                                'gris': 0,
                                'seguro': 0,
                                'prazo': 0,
                                'sem_agente': True,
                                'observacao': f"Cliente deve entregar a mercadoria em {origem}"
                            },
                            'transferencia': custo_transferencia,
                            'agente_entrega': {
                                'fornecedor': 'Cliente retira no destino',
                                'custo': 0,
                                    'total': 0,
                                    'pedagio': 0,
                                    'gris': 0,
                                    'seguro': 0,
                                    'prazo': 0,
                                    'sem_agente': True,
                                'observacao': f"Cliente deve retirar a mercadoria em {destino}"
                            }
                        }
                        rotas_encontradas.append(rota)
                except Exception as e:
                    continue

        # 🔧 PRIORIZAÇÃO: ROTAS COMPLETAS > ROTAS PARCIAIS
        rotas_completas = [r for r in rotas_encontradas if r.get('tipo_rota') == 'coleta_transferencia_entrega']
        rotas_parciais = [r for r in rotas_encontradas if r.get('tipo_rota') != 'coleta_transferencia_entrega']
        
        # Se há rotas completas, descartar rotas parciais
        if rotas_completas:
            print(f"[PRIORIZAÇÃO] 🏆 {len(rotas_completas)} rotas COMPLETAS encontradas - descartando {len(rotas_parciais)} rotas parciais")
            rotas_encontradas = rotas_completas
        else:
            print(f"[PRIORIZAÇÃO] ⚠️ Apenas {len(rotas_parciais)} rotas PARCIAIS disponíveis")
            rotas_encontradas = rotas_parciais

        # Ordenar por menor custo
        rotas_encontradas.sort(key=lambda x: x['total'])
        
        # 🔧 VALIDAÇÃO E CORREÇÃO FINAL DAS ROTAS
        rotas_encontradas = [validar_e_corrigir_rota_fracionada(rota) for rota in rotas_encontradas]
        
        # 🔧 VALIDAÇÃO FINAL - REMOVER DUPLICATAS RESIDUAIS (MELHORADO)
        rotas_unicas = []
        chaves_finais = set()
        
        for rota in rotas_encontradas:
            # Gerar chave única baseada no conteúdo da rota
            agente_col = rota.get('agente_coleta', {})
            transferencia = rota.get('transferencia', {})
            agente_ent = rota.get('agente_entrega', {})
            
            col_fornecedor = agente_col.get('fornecedor', 'N/A') if isinstance(agente_col, dict) else 'N/A'
            transf_fornecedor = transferencia.get('fornecedor', 'N/A') if isinstance(transferencia, dict) else 'N/A'
            ent_fornecedor = agente_ent.get('fornecedor', 'N/A') if isinstance(agente_ent, dict) else 'N/A'
            
            # 🔧 CORREÇÃO: Chave menos restritiva para permitir mais variações
            tipo_rota = rota.get('tipo_rota', 'N/A')
            chave_final = f"{tipo_rota}:{col_fornecedor}+{transf_fornecedor}+{ent_fornecedor}"
            
            if chave_final not in chaves_finais:
                chaves_finais.add(chave_final)
                rotas_unicas.append(rota)
            else:
                print(f"[AGENTES] 🗑️ Rota duplicada removida na validação final: {chave_final}")
        
        # Substituir a lista original
        rotas_encontradas = rotas_unicas
        
        # 🆕 RELATÓRIO FINAL DE ROTAS
        if len(rotas_encontradas) > 0:
            print(f"\n[AGENTES] 📊 RELATÓRIO FINAL DE ROTAS:")
            print(f"[AGENTES] Total de rotas únicas encontradas: {len(rotas_encontradas)}")
            print(f"[AGENTES] Rotas processadas (controle duplicatas): {len(rotas_processadas)}")
            
            # 🆕 RELATÓRIO DETALHADO POR TIPO DE ROTA
            tipos_rota = {}
            for rota in rotas_encontradas:
                tipo = rota.get('tipo_rota', 'N/A')
                if tipo not in tipos_rota:
                    tipos_rota[tipo] = []
                tipos_rota[tipo].append(rota)
            
            print(f"[AGENTES] 📈 DISTRIBUIÇÃO POR TIPO DE ROTA:")
            for tipo, lista_rotas in tipos_rota.items():
                # Identificar se é rota completa ou parcial
                if tipo == 'coleta_transferencia_entrega':
                    status_rota = "🏆 COMPLETA"
                else:
                    status_rota = "⚠️ PARCIAL"
                
                print(f"[AGENTES]   {tipo}: {len(lista_rotas)} rotas {status_rota}")
                
                # Verificar se há agentes faltando
                for rota in lista_rotas[:2]:  # Mostrar só as 2 primeiras de cada tipo
                    agente_col = rota.get('agente_coleta', {})
                    agente_ent = rota.get('agente_entrega', {})
                    sem_coleta = agente_col.get('sem_agente', False) if isinstance(agente_col, dict) else False
                    sem_entrega = agente_ent.get('sem_agente', False) if isinstance(agente_ent, dict) else False
                    
                    alertas = []
                    if sem_coleta:
                        alertas.append("SEM COLETA")
                    if sem_entrega:
                        alertas.append("SEM ENTREGA")
                    
                    alerta_texto = f" [{', '.join(alertas)}]" if alertas else ""
                    print(f"[AGENTES]     - R$ {rota.get('total', 0):.2f}{alerta_texto}: {rota.get('resumo', 'N/A')}")
            
            # Mostrar as 5 melhores rotas
            print(f"[AGENTES] 🏆 TOP 5 MELHORES ROTAS:")
            for i, rota in enumerate(rotas_encontradas[:5], 1):
                tipo_rota = rota.get('tipo_rota', 'N/A')
                total = rota.get('total', 0)
                resumo = rota.get('resumo', 'N/A')
                
                # Identificar tipo de rota para o usuário
                if tipo_rota == 'coleta_transferencia_entrega':
                    status_display = "🏆 COMPLETA"
                else:
                    status_display = "⚠️ PARCIAL"
                
                # Verificar se tem agentes faltando
                agente_col = rota.get('agente_coleta', {})
                agente_ent = rota.get('agente_entrega', {})
                sem_coleta = agente_col.get('sem_agente', False) if isinstance(agente_col, dict) else False
                sem_entrega = agente_ent.get('sem_agente', False) if isinstance(agente_ent, dict) else False
                
                alertas = []
                if sem_coleta:
                    alertas.append("SEM COLETA")
                if sem_entrega:
                    alertas.append("SEM ENTREGA")
                
                alerta_texto = f" [{', '.join(alertas)}]" if alertas else ""
                print(f"[AGENTES]   {i}º) {status_display}: R$ {total:.2f}{alerta_texto}")
                print(f"[AGENTES]       {resumo}")
            
            # Verificar duplicatas por valor total
            valores_totais = {}
            for rota in rotas_encontradas:
                total = round(rota.get('total', 0), 2)
                if total in valores_totais:
                    valores_totais[total] += 1
                else:
                    valores_totais[total] = 1
            
            duplicatas_valor = [total for total, count in valores_totais.items() if count > 1]
            if duplicatas_valor:
                print(f"[AGENTES] ⚠️ ATENÇÃO: Rotas com valores totais duplicados: {duplicatas_valor}")
                for total_dup in duplicatas_valor:
                    rotas_dup = [r for r in rotas_encontradas if round(r.get('total', 0), 2) == total_dup]
                    print(f"[AGENTES]     R$ {total_dup}: {len(rotas_dup)} rotas")
                    for rota_dup in rotas_dup:
                        print(f"[AGENTES]       - {rota_dup.get('resumo', 'N/A')}")
        
        if len(rotas_encontradas) == 0:
            print(f"\n[AGENTES] ❌ NENHUMA ROTA ENCONTRADA")
            return {
                'rotas': [],
                'total_opcoes': 0,
                'origem': f"{origem}/{uf_origem}",
                'destino': f"{destino}/{uf_destino}",
                'aviso': f"Nenhuma rota válida encontrada para {origem} → {destino}",
                'tipo_aviso': 'SEM_ROTA_COMPLETA',
                'agentes_faltando': agentes_faltando,
                'avisos': avisos if avisos else []
            }
        
        print(f"\n[AGENTES] ✅ PROCESSO CONCLUÍDO: {len(rotas_encontradas)} rotas ÚNICAS encontradas")
        
        # Preparar resposta
        resposta = {
            'rotas': rotas_encontradas,
            'total_opcoes': len(rotas_encontradas),
            'origem': f"{origem}/{uf_origem}",
            'destino': f"{destino}/{uf_destino}",
            'estatisticas': {
                'rotas_processadas': len(rotas_processadas),
                'rotas_finais': len(rotas_encontradas),
                'duplicatas_evitadas': len(rotas_processadas) - len(rotas_encontradas) if len(rotas_processadas) > len(rotas_encontradas) else 0
            },
            'agentes_faltando': agentes_faltando,
            'avisos': avisos if avisos else []
        }
        
        # Adicionar avisos adicionais se necessário
        if agentes_faltando['origem'] and not agentes_faltando['agentes_proximos_origem']:
            resposta['avisos'].append("Não foram encontrados agentes próximos à cidade de origem.")
            
        if agentes_faltando['destino'] and not agentes_faltando['agentes_proximos_destino']:
            resposta['avisos'].append("Não foram encontrados agentes próximos à cidade de destino.")
            
        return resposta
        
    except Exception as e:
        print(f"[AGENTES] ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return None

def calcular_custo_agente(linha, peso_cubado, valor_nf):
    """
    Calcula o custo de um agente ou transferência específico
    
    Para transferências, segue regras específicas:
    - Ignora colunas M e N (valores zero)
    - Para pesos > 100kg, usa coluna 'ACIMA 100'
    - Usa o maior entre peso real e cubado
    - Aplica valor mínimo para pesos até 10kg
    """
    try:
        fornecedor = linha.get('Fornecedor', 'N/A')
        prazo_raw = linha.get('Prazo', 1)
        prazo = int(prazo_raw) if prazo_raw and str(prazo_raw).isdigit() else 1
        
        # ✅ VERIFICAR PESO MÁXIMO TRANSPORTADO (MELHORADO)
        peso_maximo = None
        alerta_peso = None
        excede_peso = False
        
        if 'PESO MÁXIMO TRANSPORTADO' in linha and pd.notna(linha.get('PESO MÁXIMO TRANSPORTADO')):
            try:
                peso_maximo = float(linha.get('PESO MÁXIMO TRANSPORTADO', 0))
                
                # SÓ VALIDAR SE PESO MÁXIMO > 0 (correção do problema 4)
                if peso_maximo > 0 and peso_cubado > peso_maximo:
                    alerta_peso = f"⚠️ ATENÇÃO: Peso cubado ({peso_cubado}kg) excede o limite máximo do agente {fornecedor} ({peso_maximo}kg)"
                    print(f"[CUSTO] {alerta_peso}")
                    excede_peso = True
            except (ValueError, TypeError):
                pass
        
        # 🔧 LÓGICA ESPECÍFICA PARA TRANSFERÊNCIAS
        fornecedor_upper = str(fornecedor).upper()
        tipo_servico = str(linha.get('Tipo', '')).upper()
        
        if tipo_servico == 'TRANSFERÊNCIA' or 'TRANSFERENCIA' in tipo_servico:
            print(f"[CUSTO-TRANSF] 🔧 Aplicando lógica para transferência: {fornecedor}")
            
            # Para transferências, usar o maior entre peso real e cubado
            peso_calculo = peso_cubado  # Já é o máximo entre peso real e cubado
            
            # 1. Verificar valor mínimo para até 10kg
            if 'VALOR MÍNIMO ATÉ 10' in linha and pd.notna(linha.get('VALOR MÍNIMO ATÉ 10')):
                valor_minimo = float(linha.get('VALOR MÍNIMO ATÉ 10', 0))
                
                # Se peso for até 10kg, usar valor mínimo
                if peso_calculo <= 10:
                    valor_base = valor_minimo
                    print(f"[CUSTO-TRANSF] ✅ Peso ≤ 10kg: Valor mínimo R$ {valor_base:.2f}")
                    return {
                        'custo_base': round(valor_base, 2),
                        'pedagio': 0.0,
                        'gris': 0.0,
                        'total': round(valor_base, 2),
                        'prazo': prazo,
                        'peso_maximo': peso_maximo,
                        'alerta_peso': alerta_peso,
                        'excede_peso': excede_peso
                    }
            
            # 2. Para pesos acima de 100kg, usar a coluna apropriada baseada no peso
            if peso_calculo > 100:
                # Removendo verificações de 150 e 200 que estão com 0
                # Diretamente usar coluna 300 para >100kg
                valor_por_kg = float(linha.get(300, 0))
                valor_base = peso_calculo * valor_por_kg
                print(f"[CUSTO-TRANSF] ✅ Peso >100kg: {peso_calculo}kg × R$ {valor_por_kg:.4f} = R$ {valor_base:.2f}")
            else:
                # 3. Para pesos entre 10kg e 100kg, encontrar a faixa correta (ignorando colunas M e N)
                # Mapeamento de faixas de peso para colunas (usando as colunas disponíveis na base)
                faixas_peso = [10, 20, 30, 50, 70, 100, 150, 200, 300, 500]
                colunas_peso = ['VALOR MÍNIMO ATÉ 10', 20, 30, 50, 70, 100, 150, 200, 300, 'Acima 500']
                
                # Encontrar a menor faixa que seja maior ou igual ao peso
                valor_base_kg = 0
                for i, faixa in enumerate(faixas_peso):
                    if peso_calculo <= faixa:
                        valor_base_kg = float(linha.get(str(colunas_peso[i]), 0))
                        valor_base = peso_calculo * valor_base_kg
                        print(f"[CUSTO-TRANSF] ✅ Peso {peso_calculo}kg na faixa até {faixa}kg: {peso_calculo}kg × R$ {valor_base_kg:.4f} = R$ {valor_base:.2f}")
                        break
                else:
                    # Se não encontrou faixa, usar o último valor
                    valor_base_kg = float(linha.get(colunas_peso[-1], 0))
                    valor_base = peso_calculo * valor_base_kg
                    print(f"[CUSTO-TRANSF] ⚠️ Usando última faixa disponível: {peso_calculo}kg × R$ {valor_base_kg:.4f} = R$ {valor_base:.2f}")
            
            custo_base = valor_base
            
        # 🔧 LÓGICA ESPECÍFICA PARA JEM/DFL - CORREÇÃO DO CÁLCULO
        elif 'JEM' in fornecedor_upper or 'DFL' in fornecedor_upper:
            print(f"[CUSTO-JEM] 🔧 Aplicando lógica específica para JEM/DFL: {fornecedor}")
            
            # JEM/DFL usa VALOR MÍNIMO + EXCEDENTE
            valor_base = 0
            
            if 'VALOR MÍNIMO ATÉ 10' in linha and 'EXCEDENTE' in linha:
                valor_min = linha.get('VALOR MÍNIMO ATÉ 10', 0)
                excedente = linha.get('EXCEDENTE', 0)
                
                if pd.notna(valor_min) and pd.notna(excedente):
                    valor_min = float(valor_min)
                    excedente = float(excedente)
                    
                    if peso_cubado <= 10:
                        valor_base = valor_min
                        print(f"[CUSTO-JEM] ✅ Peso ≤ 10kg: Valor mínimo R$ {valor_base:.2f}")
                    else:
                        peso_excedente = peso_cubado - 10
                        valor_base = valor_min + (peso_excedente * excedente)
                        print(f"[CUSTO-JEM] ✅ Peso > 10kg: Mínimo R$ {valor_min:.2f} + ({peso_excedente:.1f}kg × R$ {excedente:.3f}) = R$ {valor_base:.2f}")
            
            print(f"[CUSTO-JEM] Fornecedor: {fornecedor}, Peso: {peso_cubado}kg, Base: R$ {valor_base:.2f}")
            custo_base = valor_base
        
        else:
            # LÓGICA PADRÃO PARA OUTROS FORNECEDORES
            valor_base = 0
            if 'VALOR MÍNIMO ATÉ 10' in linha and pd.notna(linha.get('VALOR MÍNIMO ATÉ 10')):
                valor_base = float(linha.get('VALOR MÍNIMO ATÉ 10', 0))
        
            # Calcular excedente se peso cubado > 10kg
            excedente_valor = 0
            if peso_cubado > 10:
                peso_excedente = peso_cubado - 10
                if 'EXCEDENTE' in linha and pd.notna(linha.get('EXCEDENTE')):
                    excedente_por_kg = float(linha.get('EXCEDENTE', 0))
                    excedente_valor = peso_excedente * excedente_por_kg
        
                valor_base = valor_base + excedente_valor
        
            custo_base = valor_base
        
        # 🔧 CALCULAR PEDÁGIO (CORRIGIDO)
        # Para transferências, não há pedágio
        if tipo_servico == 'TRANSFERÊNCIA' or 'TRANSFERENCIA' in tipo_servico:
            print("[CUSTO-TRANSF] ℹ️ Transferência: Pedágio não aplicável")
            pedagio = 0.0
        else:
            pedagio = 0.0
            try:
                valor_pedagio = float(linha.get('Pedagio (100 Kg)', 0) or 0)
                if valor_pedagio > 0 and peso_cubado > 0:
                    blocos_pedagio = math.ceil(peso_cubado / 100)
                    pedagio = blocos_pedagio * valor_pedagio
                    print(f"[PEDAGIO] {fornecedor}: {blocos_pedagio} blocos × R$ {valor_pedagio:.2f} = R$ {pedagio:.2f}")
            except (ValueError, TypeError):
                pedagio = 0.0
        
        # 🔧 CALCULAR GRIS (CORRIGIDO)
        # Para transferências, não há GRIS
        if tipo_servico == 'TRANSFERÊNCIA' or 'TRANSFERENCIA' in tipo_servico:
            print("[CUSTO-TRANSF] ℹ️ Transferência: GRIS não aplicável")
            gris_valor = 0.0
        else:
            gris_valor = 0.0
            try:
                if valor_nf and valor_nf > 0:
                    gris_exc = linha.get('Gris Exc')
                    gris_min = linha.get('Gris Min', 0)
                    if gris_exc is not None and not pd.isna(gris_exc):
                        gris_exc = float(gris_exc)
                        # CORREÇÃO: Gris Exc na planilha sempre está em formato percentual
                        gris_percentual = gris_exc / 100
                        gris_calculado = valor_nf * gris_percentual
                        if gris_min is not None and not pd.isna(gris_min):
                            gris_min = float(gris_min)
                            gris_valor = max(gris_calculado, gris_min)
                        else:
                            gris_valor = gris_calculado
                        # Verificar se o resultado é NaN
                        if pd.isna(gris_valor) or math.isnan(gris_valor):
                            gris_valor = 0.0
            except (ValueError, TypeError):
                gris_valor = 0.0
        
        # Calcular total
        total = custo_base + pedagio + gris_valor
        
        # 🔧 CALCULAR SEGURO SE DISPONÍVEL
        seguro = 0
        if valor_nf and valor_nf > 0:
            if 'Seguro' in linha and pd.notna(linha.get('Seguro')):
                seguro_perc = float(linha.get('Seguro', 0))
                if seguro_perc > 0:
                    # Se o valor é menor que 1, assumir que é percentual (ex: 0.15 = 0.15%)
                    if seguro_perc < 1:
                        seguro = valor_nf * (seguro_perc / 100)
                    else:
                        # Se maior que 1, pode ser valor absoluto ou percentual alto
                        seguro = valor_nf * (seguro_perc / 100) if seguro_perc < 100 else seguro_perc
                    print(f"[SEGURO] {fornecedor}: {seguro_perc}% de R$ {valor_nf:,.2f} = R$ {seguro:.2f}")
        
        # Total
        total = custo_base + gris_valor + pedagio + seguro
        
        # Verificar se os valores são válidos
        if total <= 0:
            print(f"[CUSTO] ❌ Total inválido para {fornecedor}: R$ {total:.2f}")
            return None
        
        resultado = {
            'fornecedor': fornecedor,
            'origem': linha.get('Origem', ''),
            'destino': linha.get('Destino', ''),
            'custo_base': round(custo_base, 2),
            'gris': round(gris_valor, 2),
            'pedagio': round(pedagio, 2),
            'seguro': round(seguro, 2),  # 🆕 Adicionado campo seguro
            'total': round(total, 2),
            'prazo': prazo,
            'peso_usado': peso_cubado,
            'peso_maximo': peso_maximo,
            'alerta_peso': alerta_peso,
            'excede_peso': peso_cubado > peso_maximo if peso_maximo and peso_maximo > 0 else False,
            'tipo': linha.get('Tipo', 'N/A')
        }
        
        print(f"[CUSTO] ✅ {fornecedor}: Base=R${custo_base:.2f} + GRIS=R${gris_valor:.2f} + Pedágio=R${pedagio:.2f} + Seguro=R${seguro:.2f} = R${total:.2f}")
        return resultado
        
    except Exception as e:
        print(f"[CUSTO] ❌ Erro ao calcular custo para {linha.get('Fornecedor', 'N/A')}: {e}")
        import traceback
        traceback.print_exc()
        return None

def processar_linha_fracionado(linha, peso_cubado, valor_nf, tipo_servico="FRACIONADO"):
    """
    Processa uma linha da base unificada para extrair dados de frete fracionado
    """
    try:
        fornecedor = linha.get('Fornecedor', 'N/A')
        
        # Calcular custo usando a função existente
        custo_resultado = calcular_custo_agente(linha, peso_cubado, valor_nf)
        
        if not custo_resultado:
            return None
        
        # Retornar dados formatados
        return {
            'fornecedor': fornecedor,
            'origem': linha.get('Origem', ''),
            'destino': linha.get('Destino', ''),
            'custo_base': custo_resultado['custo_base'],
            'pedagio': custo_resultado['pedagio'],
            'gris': custo_resultado['gris'],
            'total': custo_resultado['total'],
            'prazo': custo_resultado['prazo'],
            'peso_usado': peso_cubado,
            'tipo_servico': tipo_servico,
            'peso_maximo': custo_resultado.get('peso_maximo'),
            'alerta_peso': custo_resultado.get('alerta_peso'),
            'excede_peso': custo_resultado.get('excede_peso', False)
        }
        
    except Exception as e:
        print(f"[PROCESSAR] ❌ Erro ao processar linha {fornecedor}: {e}")
        return None

def calcular_peso_cubado_por_tipo(peso_real, cubagem, tipo_linha, fornecedor=None):
    """
    Calcula peso cubado aplicando fatores específicos por tipo de serviço
    """
    try:
        peso_real = float(peso_real)
        cubagem = float(cubagem) if cubagem else 0
        
        if cubagem <= 0:
            print(f"[AÉREO] Buscando: {origem_norm}/{uf_origem_norm} → {destino_norm}/{uf_destino_norm}")
        
        # Buscar rotas aéreas correspondentes
        opcoes_aereas = []
        

        for _, linha in df_aereo.iterrows():
            origem_base = normalizar_cidade_nome(str(linha.get('Origem', '')))
            destino_base = normalizar_cidade_nome(str(linha.get('Destino', '')))
            # Verificar se a rota corresponde
            if origem_base == origem_norm and destino_base == destino_norm:
                # Processar dados da linha
                fornecedor = linha.get('Fornecedor', 'N/A')
                prazo_raw = int(linha.get('Prazo', 1))
                # Para modal aéreo: prazo 0 = 1 dia
                prazo = 1 if prazo_raw == 0 else prazo_raw
                # Calcular custo baseado no peso
                peso_float = float(peso)
                # Valores da planilha
                valor_minimo = float(linha.get('VALOR MÍNIMO ATÉ 10', 0))
                excedente = float(linha.get('EXCEDENTE', 0))
                # Calcular custo total
                if peso_float <= 10:
                    custo_base = valor_minimo
                else:
                    peso_excedente = peso_float - 10
                    custo_base = valor_minimo + (peso_excedente * excedente)
                # GRIS para aéreo (se informado) - CORRIGIDO
                gris_valor = 0.0
                try:
                    if valor_nf and valor_nf > 0:
                        gris_exc = linha.get('Gris Exc')
                        gris_min = linha.get('Gris Min', 0)
                        if gris_exc is not None and not pd.isna(gris_exc):
                            gris_exc = float(gris_exc)
                            # CORREÇÃO: Gris Exc na planilha sempre está em formato percentual
                            gris_percentual = gris_exc / 100
                            gris_calculado = valor_nf * gris_percentual
                            if gris_min is not None and not pd.isna(gris_min):
                                gris_min = float(gris_min)
                                gris_valor = max(gris_calculado, gris_min)
                            else:
                                gris_valor = gris_calculado
                            # Verificar se o resultado é NaN
                            if pd.isna(gris_valor) or math.isnan(gris_valor):
                                gris_valor = 0.0
                except (ValueError, TypeError):
                    gris_valor = 0.0

                    # Pedágio para aéreo (normalmente zero) - CORRIGIDO
                    pedagio = 0.0
                    try:
                        valor_pedagio = float(linha.get('Pedagio (100 Kg)', 0) or 0)
                        if valor_pedagio > 0 and peso_float > 0:
                            blocos_pedagio = math.ceil(peso_float / 100)
                            pedagio = blocos_pedagio * valor_pedagio
                    except (ValueError, TypeError):
                        pedagio = 0.0

                    # Total
                    total = custo_base + gris_valor + pedagio

                    opcao = {
                        'fornecedor': fornecedor,
                        'origem': linha.get('Origem', ''),
                        'destino': linha.get('Destino', ''),
                        'custo_base': round(custo_base, 2),
                        'gris': round(gris_valor, 2),
                        'pedagio': round(pedagio, 2),
                        'total': round(total, 2),
                        'prazo': prazo,
                        'peso_usado': peso_float,
                        'modalidade': 'AÉREO'
                    }

                    opcoes_aereas.append(opcao)
                    print(f"[AÉREO] ✅ {fornecedor}: R$ {total:,.2f} (prazo: {prazo} dias)")
                    
        
        if not opcoes_aereas:
            print(f"[AÉREO] ❌ Nenhuma rota aérea encontrada para {origem_norm} → {destino_norm}")
            return None
        
        # Ordenar por menor custo
        opcoes_aereas.sort(key=lambda x: x['total'])
        
        # Preparar mensagens de aviso sobre agentes ausentes
        avisos = []
        if agentes_faltando['origem']:
            if agentes_faltando['agentes_proximos_origem']:
                cidades_proximas = ", ".join([f"{m[0]}/{m[1]} ({m[2]:.1f}km)" for m in agentes_faltando['agentes_proximos_origem']])
                avisos.append(f"Atenção: Nenhum agente encontrado em {origem}/{uf_origem}. Cidades próximas com agentes: {cidades_proximas}")
            else:
                avisos.append(f"Atenção: Nenhum agente encontrado em {origem}/{uf_origem} e não foram encontradas cidades próximas com agentes.")
        
        if agentes_faltando['destino']:
            if agentes_faltando['agentes_proximos_destino']:
                cidades_proximas = ", ".join([f"{m[0]}/{m[1]} ({m[2]:.1f}km)" for m in agentes_faltando['agentes_proximos_destino']])
                avisos.append(f"Atenção: Nenhum agente encontrado em {destino}/{uf_destino}. Cidades próximas com agentes: {cidades_proximas}")
            else:
                avisos.append(f"Atenção: Nenhum agente encontrado em {destino}/{uf_destino} e não foram encontradas cidades próximas com agentes.")
        
        # Preparar resultado final
        resultado = {
            'opcoes': opcoes_aereas,
            'total_opcoes': len(opcoes_aereas),
            'melhor_opcao': opcoes_aereas[0] if opcoes_aereas else None,
            'origem': origem,
            'uf_origem': uf_origem,
            'destino': destino,
            'uf_destino': uf_destino,
            'peso': peso,
            'valor_nf': valor_nf,
            'agentes_faltando': agentes_faltando,
            'avisos': avisos if avisos else None
        }
        
        print(f"[AÉREO] ✅ {len(opcoes_aereas)} opções aéreas encontradas")
        return resultado
        
    except Exception as e:
        print(f"[AÉREO] ❌ Erro no cálculo aéreo: {e}")
        return None

def gerar_pedagios_estimados_mapa(rota_info, tipo_veiculo, valor_total_pedagio, distancia_total):
    """
    Gera localizações estimadas de pedágios ao longo da rota para exibir no mapa
    """
    try:
        pedagios_mapa = []
        
        # Se não temos pontos da rota, não podemos gerar localizações
        if not rota_info.get("rota_pontos") or len(rota_info["rota_pontos"]) < 2:
            return []
        
        rota_pontos = rota_info["rota_pontos"]
        
        # Estimar número de pedágios baseado na distância (aproximadamente a cada 120-180km)
        num_pedagios_estimado = max(1, int(distancia_total / 150))
        
        # Se a rota é muito curta, pode não ter pedágios
        if distancia_total < 80:
            return []
        
        # Calcular valor médio por pedágio
        valor_por_pedagio = valor_total_pedagio / num_pedagios_estimado if num_pedagios_estimado > 0 else 0
        
        # Distribuir pedágios ao longo da rota
        total_pontos = len(rota_pontos)
        
        for i in range(num_pedagios_estimado):
            # Posicionar pedágios em intervalos regulares ao longo da rota
            # Evitar muito próximo do início e fim
            posicao_percentual = 0.15 + (i * 0.7 / max(1, num_pedagios_estimado - 1))
            if num_pedagios_estimado == 1:
                posicao_percentual = 0.5  # No meio da rota
            
            indice_ponto = int(posicao_percentual * (total_pontos - 1))
            indice_ponto = max(0, min(indice_ponto, total_pontos - 1))
            
            lat, lon = rota_pontos[indice_ponto]
            
            # Variação no valor do pedágio baseada no tipo de estrada/região
            variacao = 0.8 + (i * 0.4 / max(1, num_pedagios_estimado - 1))  # Entre 80% e 120%
            valor_pedagio = valor_por_pedagio * variacao
            
            # Determinar nome estimado do pedágio baseado na posição
            nomes_estimados = [
                f"Pedágio {i+1} - Rodovia Principal",
                f"Praça {i+1} - Via Expressa", 
                f"Pedágio {i+1} - Concessionária",
                f"Posto {i+1} - Rodovia Federal"
            ]
            nome_pedagio = nomes_estimados[i % len(nomes_estimados)]
            
            pedagio_info = {
                "id": f"pedagio_{i+1}",
                "nome": nome_pedagio,
                "lat": lat,
                "lon": lon,
                "valor": valor_pedagio,
                "tipo_veiculo": tipo_veiculo,
                "distancia_origem": (i + 1) * (distancia_total / (num_pedagios_estimado + 1)),
                "concessionaria": f"Concessionária {chr(65 + i)}",  # A, B, C, etc.
                "tipo_estrada": "Rodovia Federal" if i % 2 == 0 else "Rodovia Estadual"
            }
            
            pedagios_mapa.append(pedagio_info)
        
        print(f"[PEDÁGIO_MAPA] Gerados {len(pedagios_mapa)} pedágios estimados para o mapa")
        return pedagios_mapa
        
    except Exception as e:
        print(f"[PEDÁGIO_MAPA] Erro ao gerar pedágios para mapa: {e}")
        return []

def gerar_ranking_fracionado(opcoes_fracionado, origem, destino, peso, cubagem, valor_nf=None):
    """
    Gera ranking das opções de frete fracionado no formato similar ao dedicado
    """
    try:
        if not opcoes_fracionado or len(opcoes_fracionado) == 0:
            return None
        
        # Calcular peso cubado
        peso_real = float(peso)
        peso_cubado = max(peso_real, float(cubagem) * 300) if cubagem else peso_real
        
        # Preparar ranking das opções
        ranking_opcoes = []
        
        for i, opcao in enumerate(opcoes_fracionado, 1):
            # Extrair detalhes da opção
            detalhes_opcao = opcao.get('detalhes', {})
            tipo_rota = opcao.get('tipo_rota', 'transferencia_direta')
            
            # Determinar informações do serviço e agentes
            agentes_info = extrair_informacoes_agentes(opcao, tipo_rota)
            
            # 🔧 CORREÇÃO: Melhor descrição dos tipos de serviço e fornecedores
            resumo_original = opcao.get('resumo', '')
            
            # Determinar tipo de serviço para mostrar no ranking
            if tipo_rota == 'transferencia_direta':
                tipo_servico = f"TRANSFERÊNCIA DIRETA - {agentes_info['fornecedor_principal']}"
                descricao = f"Transferência direta via {agentes_info['fornecedor_principal']}"
                capacidade_info = {
                    'peso_max': 'Ilimitado',
                    'volume_max': 'Ilimitado',
                    'descricao': 'Transferência rodoviária direta'
                }
            elif tipo_rota == 'direto_porta_porta':
                tipo_servico = f"SERVIÇO DIRETO PORTA-A-PORTA - {agentes_info['fornecedor_principal']}"
                rota_bases = opcao.get('rota_bases', f"{origem} → {destino} (Direto)")
                descricao = f"ROTA: {rota_bases}<br/>Coleta e entrega incluídas no serviço"
                capacidade_info = {
                    'peso_max': '500kg',
                    'volume_max': '15m³',
                    'descricao': 'Serviço porta-a-porta completo'
                }
            elif tipo_rota == 'agente_direto':
                tipo_servico = f"AGENTE DIRETO - {agentes_info['fornecedor_principal']}"
                descricao = f"Porta-a-porta direto via {agentes_info['fornecedor_principal']}"
                capacidade_info = {
                    'peso_max': '500kg',
                    'volume_max': '15m³',
                    'descricao': 'Coleta e entrega direta'
                }
            elif tipo_rota == 'cliente_entrega_transferencia_agente_entrega':
                tipo_servico = f"CLIENTE ENTREGA + TRANSFERÊNCIA + AGENTE ENTREGA"
                rota_bases = opcao.get('rota_bases', 'Rota não definida')
                descricao = f"ROTA: {rota_bases}<br/>Cliente entrega na base → Transferência → Agente entrega no destino"
                capacidade_info = {
                    'peso_max': '300kg',
                    'volume_max': '10m³',
                    'descricao': 'Cliente entrega + transferência + agente entrega'
                }
            elif tipo_rota == 'coleta_transferencia':
                tipo_servico = f"COLETA + TRANSFERÊNCIA"
                descricao = f"COLETA: {agentes_info['agente_coleta']} → TRANSFERÊNCIA: {agentes_info['transferencia']}"
                capacidade_info = {
                    'peso_max': '300kg',
                    'volume_max': '10m³',
                    'descricao': 'Coleta local + transferência'
                }
            elif tipo_rota == 'transferencia_entrega':
                tipo_servico = f"TRANSFERÊNCIA + ENTREGA"
                descricao = f"TRANSFERÊNCIA: {agentes_info['transferencia']} → ENTREGA: {agentes_info['agente_entrega']}"
                capacidade_info = {
                    'peso_max': '300kg',
                    'volume_max': '10m³',
                    'descricao': 'Transferência + entrega local'
                }
            elif tipo_rota == 'coleta_transferencia_entrega':
                # 🆕 VERIFICAR SE A ROTA É COMPLETA OU PARCIAL
                detalhes_rota = detalhes_opcao
                status_rota = detalhes_rota.get('status_rota', 'COMPLETA')
                transferencia_info = detalhes_rota.get('transferencia', {})
                if status_rota == 'PARCIAL' or transferencia_info.get('fornecedor') == 'SEM TRANSFERÊNCIA':
                    tipo_servico = f"ROTA PARCIAL (FALTA TRANSFERÊNCIA)"
                    descricao = f"COLETA: {agentes_info['agente_coleta']} → ⚠️ SEM TRANSFERÊNCIA → ENTREGA: {agentes_info['agente_entrega']}"
                    capacidade_info = {
                        'peso_max': '300kg',
                        'volume_max': '10m³',
                        'descricao': 'Rota incompleta - falta transferência entre bases'
                    }
                else:
                    tipo_servico = f"ROTA COMPLETA (3 ETAPAS)"
                    descricao = f"COLETA: {agentes_info['agente_coleta']} → TRANSFERÊNCIA: {agentes_info['transferencia']} → ENTREGA: {agentes_info['agente_entrega']}"
                    capacidade_info = {
                        'peso_max': '300kg',
                        'volume_max': '10m³',
                        'descricao': 'Rota completa com agentes'
                    }
            else:
                tipo_servico = f"FRETE FRACIONADO - {agentes_info['fornecedor_principal']}"
                descricao = resumo_original or f"Frete fracionado via {agentes_info['fornecedor_principal']}"
                capacidade_info = {
                    'peso_max': '300kg',
                    'volume_max': '10m³',
                    'descricao': 'Frete fracionado padrão'
                }
            
            # Determinar ícone baseado na posição
            if i == 1:
                icone = "🥇"
            elif i == 2:
                icone = "🥈"
            elif i == 3:
                icone = "🥉"
            else:
                icone = f"{i}º"
            
            # Extrair detalhamento de custos
            detalhamento_custos = extrair_detalhamento_custos(opcao, peso_cubado, valor_nf)
            
            opcao_ranking = {
                'posicao': i,
                'icone': icone,
                'tipo_servico': tipo_servico,
                'fornecedor': agentes_info['fornecedor_principal'],
                'descricao': descricao,
                'custo_total': opcao.get('total', 0),
                'prazo': opcao.get('prazo_total', 1),
                'peso_usado': f"{peso_cubado}kg",
                'peso_usado_tipo': 'Real' if peso_real >= peso_cubado else 'Cubado',
                'capacidade': capacidade_info,
                'eh_melhor_opcao': (i == 1),
                
                # 🆕 DETALHES EXPANDIDOS
                'detalhes_expandidos': {
                    'agentes_info': agentes_info,
                    'custos_detalhados': detalhamento_custos,
                    'rota_info': {
                        'origem': origem,
                        'destino': destino,
                        'peso_real': peso_real,
                        'cubagem': cubagem,
                        'peso_cubado': peso_cubado,
                        'valor_nf': valor_nf,
                        'tipo_peso_usado': 'Real' if peso_real >= peso_cubado else 'Cubado'
                    },
                    'observacoes': opcao.get('observacoes', ''),
                    # ✅ DADOS DOS AGENTES COM PESO MÁXIMO (NOVO)
                    'dados_agentes': {
                        'agente_coleta': opcao.get('agente_coleta', {}),
                        'transferencia': opcao.get('transferencia', {}),
                        'agente_entrega': opcao.get('agente_entrega', {})
                    }
                },
                
                # Manter dados originais para compatibilidade
                'detalhes': opcao
            }
            
            ranking_opcoes.append(opcao_ranking)
        
        # Informações da cotação (similar ao dedicado)
        melhor_opcao = ranking_opcoes[0] if ranking_opcoes else None
        
        # Calcular informações de rota (estimativas para fracionado)
        distancia_estimada = 800  # Distância aproximada
        tempo_estimado = f"{int(distancia_estimada/80)}h {int((distancia_estimada/80)*60)%60}min"
        
        resultado_formatado = {
            'id_calculo': f"#Fra{len(ranking_opcoes):03d}",
            'tipo_frete': 'Fracionado',
            'origem': origem,
            'destino': destino,
            'peso': peso,
            'cubagem': cubagem,
            'peso_cubado': peso_cubado,
            'peso_usado_tipo': 'Real' if peso_real >= peso_cubado else 'Cubado',
            'valor_nf': valor_nf,
            'distancia': distancia_estimada,
            'tempo_estimado': tempo_estimado,
            'consumo_estimado': round(distancia_estimada * 0.08, 2),  # Menor consumo para fracionado
            'emissao_co2': round(distancia_estimada * 0.08 * 2.3, 2),
            'melhor_opcao': melhor_opcao,
            'ranking_opcoes': ranking_opcoes,
            'total_opcoes': len(ranking_opcoes),
            'data_calculo': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }
        
        # 🔧 CORREÇÃO: Sanitizar resultado para evitar valores NaN no JSON
        return sanitizar_json(resultado_formatado)
        
    except Exception as e:
        print(f"[RANKING] Erro ao gerar ranking fracionado: {e}")
        import traceback
        traceback.print_exc()
        return None

def extrair_informacoes_agentes(opcao, tipo_rota):
    """
    Extrai informações dos agentes de uma opção de frete
    """
    try:
        # Primeiro tentar acessar dados diretamente da opção, depois de detalhes
        detalhes = opcao.get('detalhes', {})
        
        info = {
            'fornecedor_principal': 'N/A',
            'agente_coleta': 'N/A',
            'transferencia': 'N/A', 
            'agente_entrega': 'N/A',
            'base_origem': 'N/A',
            'base_destino': 'N/A'
        }
        
        if tipo_rota == 'transferencia_direta':
            # Usar o fornecedor já extraído corretamente
            fornecedor = opcao.get('fornecedor', 'N/A')
            info['fornecedor_principal'] = fornecedor
            info['transferencia'] = fornecedor
            
        elif tipo_rota == 'agente_direto':
            # Buscar na estrutura do agente direto
            agente_direto = opcao.get('agente_direto', {})
            fornecedor = agente_direto.get('fornecedor', opcao.get('fornecedor', 'N/A'))
            info['fornecedor_principal'] = fornecedor
            
        elif tipo_rota == 'coleta_transferencia':
            # Buscar dados diretamente na raiz da opção
            agente_coleta = opcao.get('agente_coleta', detalhes.get('agente_coleta', {}))
            transferencia = opcao.get('transferencia', detalhes.get('transferencia', {}))
            
            info['agente_coleta'] = agente_coleta.get('fornecedor', 'N/A')
            info['transferencia'] = transferencia.get('fornecedor', 'N/A')
            info['fornecedor_principal'] = info['agente_coleta']
            
            # Extrair bases para coleta + transferência
            base_origem = (
                agente_coleta.get('base_destino') or
                agente_coleta.get('destino') or
                transferencia.get('origem') or
                'ORIGEM'
            )
            base_destino = (
                transferencia.get('destino') or
                transferencia.get('base_destino') or
                'DESTINO'
            )
            
            info['base_origem'] = base_origem
            info['base_destino'] = base_destino
            
        elif tipo_rota == 'transferencia_entrega':
            # Buscar dados diretamente na raiz da opção
            transferencia = opcao.get('transferencia', detalhes.get('transferencia', {}))
            agente_entrega = opcao.get('agente_entrega', detalhes.get('agente_entrega', {}))
            
            info['transferencia'] = transferencia.get('fornecedor', 'N/A')
            info['agente_entrega'] = agente_entrega.get('fornecedor', 'N/A')
            info['fornecedor_principal'] = info['transferencia']
            
            # Extrair bases para transferência + entrega
            base_origem = (
                transferencia.get('origem') or
                transferencia.get('base_origem') or
                'ORIGEM'
            )
            base_destino = (
                agente_entrega.get('base_origem') or
                agente_entrega.get('origem') or
                transferencia.get('destino') or
                transferencia.get('base_destino') or
                'DESTINO'
            )
            
            info['base_origem'] = base_origem
            info['base_destino'] = base_destino
            
        elif tipo_rota == 'cliente_entrega_transferencia_agente_entrega':
            # ✅ NOVO TIPO DE ROTA: Cliente entrega na base + Transferência + Agente entrega
            agente_coleta = opcao.get('agente_coleta', detalhes.get('agente_coleta', {}))
            transferencia = opcao.get('transferencia', detalhes.get('transferencia', {}))
            agente_entrega = opcao.get('agente_entrega', detalhes.get('agente_entrega', {}))
            
            # Extrair informações específicas para este tipo de rota
            info['agente_coleta'] = 'Cliente entrega na base'
            info['transferencia'] = transferencia.get('fornecedor', 'N/A')
            info['agente_entrega'] = agente_entrega.get('fornecedor', 'N/A')
            info['fornecedor_principal'] = info['transferencia']
            
            # 🔧 CORREÇÃO: Extrair bases da rota corretamente
            base_origem = (
                transferencia.get('base_origem') or
                transferencia.get('origem') or
                agente_coleta.get('base_destino') or
                opcao.get('origem') or  # Usar cidade de origem como fallback
                'Origem'  # Fallback final
            )
            base_destino = (
                transferencia.get('base_destino') or
                transferencia.get('destino') or
                agente_entrega.get('base_origem') or
                agente_entrega.get('origem') or
                opcao.get('destino') or  # Usar cidade de destino como fallback
                'Destino'  # Fallback final
            )
            
            info['base_origem'] = base_origem
            info['base_destino'] = base_destino
            
        elif tipo_rota == 'coleta_transferencia_entrega':
            # Buscar dados diretamente na raiz da opção com fallbacks
            agente_coleta = opcao.get('agente_coleta', detalhes.get('agente_coleta', {}))
            transferencia = opcao.get('transferencia', detalhes.get('transferencia', {}))
            agente_entrega = opcao.get('agente_entrega', detalhes.get('agente_entrega', {}))
            
            # Múltiplos fallbacks para extrair fornecedores
            coleta_fornecedor = (
                agente_coleta.get('fornecedor') or
                agente_coleta.get('Fornecedor') or
                (agente_coleta.get('origem', '').split(' + ')[0] if ' + ' in str(agente_coleta.get('origem', '')) else 'N/A')
            )
            
            transf_fornecedor = (
                transferencia.get('fornecedor') or
                transferencia.get('Fornecedor') or
                'N/A'
            )
            
            entrega_fornecedor = (
                agente_entrega.get('fornecedor') or
                agente_entrega.get('Fornecedor') or
                'N/A'
            )
            
            info['agente_coleta'] = coleta_fornecedor
            info['transferencia'] = transf_fornecedor
            info['agente_entrega'] = entrega_fornecedor
            info['fornecedor_principal'] = transf_fornecedor
            
            # 🔧 CORREÇÃO: Melhor extração de bases para rota
            # Priorizar dados da transferência que contém a rota real
            base_origem = (
                transferencia.get('base_origem') or
                transferencia.get('origem') or
                agente_coleta.get('base_destino') or
                agente_coleta.get('destino') or
                opcao.get('origem') or  # Usar cidade de origem como fallback
                'Ribeirão Preto'  # Fallback final
            )

            base_destino = (
                transferencia.get('base_destino') or
                transferencia.get('destino') or
                agente_entrega.get('base_origem') or
                agente_entrega.get('origem') or
                opcao.get('destino') or  # Usar cidade de destino como fallback
                'Rio de Janeiro'  # Fallback final
            )
            
            info['base_origem'] = base_origem
            info['base_destino'] = base_destino
            
        else:
            # Fallback: Tentar extrair do resumo se disponível
            resumo = opcao.get('resumo', '')
            if resumo and '+' in resumo:
                partes = [p.strip() for p in resumo.split('+')]
                if len(partes) >= 3:
                    info['agente_coleta'] = partes[0]
                    info['transferencia'] = partes[1] 
                    info['agente_entrega'] = partes[2]
                    info['fornecedor_principal'] = partes[1]
                elif len(partes) == 2:
                    info['agente_coleta'] = partes[0]
                    info['transferencia'] = partes[1]
                    info['fornecedor_principal'] = partes[1]
            else:
                # Último fallback: usar fornecedor genérico
                fornecedor = opcao.get('fornecedor', 'N/A')
                info['fornecedor_principal'] = fornecedor
                info['transferencia'] = fornecedor
        
        return info
        
    except Exception as e:
        print(f"[AGENTES-INFO] ❌ Erro ao extrair informações: {e}")
        import traceback
        traceback.print_exc()
        return {
            'fornecedor_principal': 'N/A',
            'agente_coleta': 'N/A',
            'transferencia': 'N/A',
            'agente_entrega': 'N/A',
            'base_origem': 'N/A',
            'base_destino': 'N/A'
        }

def extrair_detalhamento_custos(opcao, peso_cubado, valor_nf):
    """
    Extrai detalhamento completo de custos de uma opção
    """
    try:
        detalhes = opcao.get('detalhes', {})
        
        # Extrair dados dos agentes primeiro
        agente_coleta = opcao.get('agente_coleta', {})
        transferencia = opcao.get('transferencia', {})
        agente_entrega = opcao.get('agente_entrega', {})
        
        # Priorizar dados já calculados do detalhamento_custos
        detalhamento_pre_calculado = detalhes.get('detalhamento_custos', {})
        
        if detalhamento_pre_calculado and any(detalhamento_pre_calculado.values()):
            # Usar dados já calculados se não estiverem vazios
            custo_coleta = detalhamento_pre_calculado.get('coleta', 0)
            custo_transferencia = detalhamento_pre_calculado.get('transferencia', 0)
            custo_entrega = detalhamento_pre_calculado.get('entrega', 0)
            pedagio_total = detalhamento_pre_calculado.get('pedagio', 0)
            gris_total = detalhamento_pre_calculado.get('gris_total', 0)
            seguro_total = detalhamento_pre_calculado.get('seguro_total', 0)
            
            # 🔧 CORREÇÃO: Extrair pedágios e GRIS dos agentes individuais corretamente
            pedagio_coleta = agente_coleta.get('pedagio', 0) if isinstance(agente_coleta, dict) else 0
            pedagio_transferencia = transferencia.get('pedagio', 0) if isinstance(transferencia, dict) else 0
            pedagio_entrega = agente_entrega.get('pedagio', 0) if isinstance(agente_entrega, dict) else 0
            
            gris_coleta = agente_coleta.get('gris', 0) if isinstance(agente_coleta, dict) else 0
            gris_transferencia = transferencia.get('gris', 0) if isinstance(transferencia, dict) else 0
            gris_entrega = agente_entrega.get('gris', 0) if isinstance(agente_entrega, dict) else 0
            
            seguro_coleta = agente_coleta.get('seguro', 0) if isinstance(agente_coleta, dict) else 0
            seguro_transferencia = transferencia.get('seguro', 0) if isinstance(transferencia, dict) else 0
            seguro_entrega = agente_entrega.get('seguro', 0) if isinstance(agente_entrega, dict) else 0
            
            # 🆕 CORREÇÃO: Se valores individuais estão zerados, usar os totais diretamente
            # Priorizar sempre os valores pré-calculados se existirem
            if pedagio_total > 0:
                # Se temos total mas não temos individuais, usar o total
                if (pedagio_coleta + pedagio_transferencia + pedagio_entrega) == 0:
                    pedagio_coleta = pedagio_total  # Simplificado: todo pedagio considerado na primeira etapa válida
                    pedagio_transferencia = 0
                    pedagio_entrega = 0
            
            if gris_total > 0:
                # Se temos total mas não temos individuais, usar o total
                if (gris_coleta + gris_transferencia + gris_entrega) == 0:
                    gris_coleta = gris_total  # Simplificado: todo GRIS considerado na primeira etapa válida
                    gris_transferencia = 0
                    gris_entrega = 0
            
            custos = {
                # Custos detalhados por etapa (pré-calculados)
                'custo_coleta': custo_coleta,
                'custo_transferencia': custo_transferencia,
                'custo_entrega': custo_entrega,
                'custo_base_frete': custo_coleta + custo_transferencia + custo_entrega,
                
                # 🔧 CORREÇÃO: Usar totais corretos ou valores distribuídos
                'pedagio': max(pedagio_total, pedagio_coleta + pedagio_transferencia + pedagio_entrega),
                'pedagio_coleta': pedagio_coleta,
                'pedagio_transferencia': pedagio_transferencia,
                'pedagio_entrega': pedagio_entrega,
                
                'gris': max(gris_total, gris_coleta + gris_transferencia + gris_entrega),
                'gris_coleta': gris_coleta,
                'gris_transferencia': gris_transferencia,
                'gris_entrega': gris_entrega,
                
                'seguro': max(seguro_total, seguro_coleta + seguro_transferencia + seguro_entrega),
                'seguro_coleta': seguro_coleta,
                'seguro_transferencia': seguro_transferencia,
                'seguro_entrega': seguro_entrega,
                
                # Outros custos
                'icms': 0,
                'outros': 0,
                'total_custos': opcao.get('total', 0)
            }
            
        else:
            # Fallback: Extrair custos dos agentes individuais com múltiplos formatos
            
            # Extrair custos com múltiplos fallbacks
            def extrair_custo_agente(agente_data):
                if not agente_data:
                    return 0
                # Tentar diferentes campos onde o custo pode estar
                return (
                    agente_data.get('total', 0) or
                    agente_data.get('custo', 0) or
                    agente_data.get('valor', 0) or
                    agente_data.get('price', 0) or
                    0
                )
            
            def extrair_pedagio_agente(agente_data):
                if not agente_data:
                    return 0
                return (
                    agente_data.get('pedagio', 0) or
                    agente_data.get('toll', 0) or
                    0
                )
            
            def extrair_gris_agente(agente_data):
                if not agente_data:
                    return 0
                return (
                    agente_data.get('gris', 0) or
                    agente_data.get('gris_value', 0) or
                    0
                )
            
            # Extrair custos individuais
            custo_coleta = extrair_custo_agente(agente_coleta)
            custo_transferencia = extrair_custo_agente(transferencia)
            custo_entrega = extrair_custo_agente(agente_entrega)
            
            # Extrair pedágios
            pedagio_coleta = extrair_pedagio_agente(agente_coleta)
            pedagio_transferencia = extrair_pedagio_agente(transferencia)
            pedagio_entrega = extrair_pedagio_agente(agente_entrega)
            
            # Extrair GRIS
            gris_coleta = extrair_gris_agente(agente_coleta)
            gris_transferencia = extrair_gris_agente(transferencia)
            gris_entrega = extrair_gris_agente(agente_entrega)
            
            # 🆕 Extrair SEGURO
            def extrair_seguro_agente(agente_data):
                if not agente_data:
                    return 0
                return (
                    agente_data.get('seguro', 0) or
                    agente_data.get('insurance', 0) or
                    0
                )
            
            seguro_coleta = extrair_seguro_agente(agente_coleta)
            seguro_transferencia = extrair_seguro_agente(transferencia)
            seguro_entrega = extrair_seguro_agente(agente_entrega)
            
            # Se ainda assim os custos estão zerados, distribuir o total
            total_custos_extraidos = custo_coleta + custo_transferencia + custo_entrega
            total_opcao = opcao.get('total', 0)
            
            if total_custos_extraidos == 0 and total_opcao > 0:
                # Distribuir proporcionalmente baseado no tipo de rota
                tipo_rota = opcao.get('tipo_rota', '')
                if tipo_rota == 'coleta_transferencia_entrega':
                    # Distribuição típica: 30% coleta + 50% transferência + 20% entrega
                    custo_coleta = total_opcao * 0.30
                    custo_transferencia = total_opcao * 0.50  
                    custo_entrega = total_opcao * 0.20
                elif tipo_rota == 'transferencia_entrega' or tipo_rota == 'transferencia_direta_entrega' or tipo_rota == 'cliente_entrega_transferencia_agente_entrega':
                    # 🔧 CORREÇÃO: Sem agente de coleta - 70% transferência + 30% entrega
                    custo_coleta = 0.0  # ✅ Cliente entrega na base (sem custo de agente)
                    custo_transferencia = total_opcao * 0.70
                    custo_entrega = total_opcao * 0.30
                elif tipo_rota == 'coleta_transferencia':
                    # 🔧 CORREÇÃO: Sem agente de entrega - 40% coleta + 60% transferência  
                    custo_coleta = total_opcao * 0.40
                    custo_transferencia = total_opcao * 0.60
                    custo_entrega = 0.0  # ✅ Sem agente de entrega
                elif tipo_rota == 'transferencia_direta':
                    # 🔧 CORREÇÃO: Só transferência - 100% transferência
                    custo_coleta = 0.0  # ✅ Sem agente de coleta
                    custo_transferencia = total_opcao
                    custo_entrega = 0.0  # ✅ Sem agente de entrega
                elif tipo_rota == 'agente_direto':
                    # 100% no agente direto (será mostrado como transferência)
                    custo_coleta = 0.0
                    custo_transferencia = total_opcao
                    custo_entrega = 0.0
                else:
                    # Fallback: tudo na transferência
                    custo_coleta = 0.0
                    custo_transferencia = total_opcao
                    custo_entrega = 0.0
            
            custos = {
                # Custos detalhados por etapa
                'custo_coleta': custo_coleta,
                'custo_transferencia': custo_transferencia,
                'custo_entrega': custo_entrega,
                'custo_base_frete': custo_coleta + custo_transferencia + custo_entrega,
                
                # Pedágios por etapa
                'pedagio_coleta': pedagio_coleta,
                'pedagio_transferencia': pedagio_transferencia,
                'pedagio_entrega': pedagio_entrega,
                'pedagio': pedagio_coleta + pedagio_transferencia + pedagio_entrega,
                
                # GRIS por etapa  
                'gris_coleta': gris_coleta,
                'gris_transferencia': gris_transferencia,
                'gris_entrega': gris_entrega,
                'gris': gris_coleta + gris_transferencia + gris_entrega,
                
                # 🔧 SEGURO por etapa (CORRIGIDO)
                'seguro_coleta': seguro_coleta,
                'seguro_transferencia': seguro_transferencia,
                'seguro_entrega': seguro_entrega,
                'seguro': seguro_coleta + seguro_transferencia + seguro_entrega,
                
                # Outros custos
                'icms': 0,
                'outros': 0,
                'total_custos': opcao.get('total', 0)
            }
        
        # ✅ SEGURO: APENAS SE CONFIGURADO NA BASE (SEM ESTIMATIVAS)
        # Removida estimativa automática - seguro deve vir apenas da base de dados
        
        # ✅ TAXAS ADICIONAIS (TDA para serviços diretos)
        custos['tda'] = 0
        if opcao.get('tipo_rota') == 'direto_porta_porta':
            # Tentar extrair TDA dos detalhes do serviço direto
            servico_direto = opcao.get('servico_direto', {})
            custos['tda'] = servico_direto.get('tda', 0)
        
        # Outros custos (diferença entre o total e o que foi detalhado)
        custos_contabilizados = (
            custos['custo_base_frete'] + 
            custos['pedagio'] + 
            custos['gris'] + 
            custos['seguro'] +
            custos['tda']
        )
        custos['outros'] = max(0, custos['total_custos'] - custos_contabilizados)
        
        # 🔧 Log final do detalhamento (SEM ICMS)
        print(f"[DETALHAMENTO] Base: R${custos['custo_base_frete']:.2f} + Pedágio: R${custos['pedagio']:.2f} + GRIS: R${custos['gris']:.2f} + Seguro: R${custos['seguro']:.2f} + TDA: R${custos['tda']:.2f} + Outros: R${custos['outros']:.2f} = Total: R${custos['total_custos']:.2f}")
        
        return custos
        
    except Exception as e:
        print(f"[CUSTOS] ❌ Erro ao extrair detalhamento: {e}")
        return {
            'custo_base_frete': opcao.get('total', 0),
            'pedagio': 0,
            'gris': 0,
            'seguro': 0,
            'tda': 0,  # ✅ TDA em vez de ICMS
            'outros': 0,
            'total_custos': opcao.get('total', 0)
        }

# Rotas da aplicação
@app.route("/")
@middleware_auth
def index():
    ip_cliente = obter_ip_cliente()
    usuario = session.get('usuario_logado', 'DESCONHECIDO')
    log_acesso(usuario, 'ACESSO_HOME', ip_cliente, "Acesso à página principal")
    
    df_aereo = ler_gollog_aereo()
    dados_aereo = []
    if df_aereo is not None:
        dados_aereo = df_aereo.to_dict(orient="records")
    
    # Passar dados do usuário para o template
    usuario_dados = usuario_logado()
    return render_template("index.html", 
                         dados_aereo=dados_aereo, 
                         historico=HISTORICO_PESQUISAS,
                         usuario=usuario_dados)

@app.route("/estados")
def estados():
    try:
        response = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados")
        response.raise_for_status()
        data = response.json()
        estados = [{"id": estado["sigla"], "text": estado["nome"]} for estado in data]
        return jsonify(sorted(estados, key=lambda x: x["text"]))
    except Exception as e:
        print(f"Erro ao obter estados: {e}")
        return jsonify(ESTADOS_FALLBACK)

@app.route("/municipios/<uf>")
def municipios(uf):
    try:
        # Normalizar o UF
        uf = str(uf).strip().upper()
        print(f"[DEBUG] Buscando municípios para UF: {uf}")
        
        # Se o UF não estiver no formato padrão, tentar encontrar pela descrição
        if len(uf) > 2:
            estados_map = {
                'ACRE': 'AC', 'ALAGOAS': 'AL', 'AMAPA': 'AP', 'AMAZONAS': 'AM',
                'BAHIA': 'BA', 'CEARA': 'CE', 'DISTRITO FEDERAL': 'DF',
                'ESPIRITO SANTO': 'ES', 'GOIAS': 'GO', 'MARANHAO': 'MA',
                'MATO GROSSO': 'MT', 'MATO GROSSO DO SUL': 'MS', 'MINAS GERAIS': 'MG',
                'PARA': 'PA', 'PARAIBA': 'PB', 'PARANA': 'PR', 'PERNAMBUCO': 'PE',
                'PIAUI': 'PI', 'RIO DE JANEIRO': 'RJ', 'RIO GRANDE DO NORTE': 'RN',
                'RIO GRANDE DO SUL': 'RS', 'RONDONIA': 'RO', 'RORAIMA': 'RR',
                'SANTA CATARINA': 'SC', 'SAO PAULO': 'SP', 'SERGIPE': 'SE',
                'TOCANTINS': 'TO'
            }
            uf_norm = uf.replace('-', ' ').replace('_', ' ').upper()
            if uf_norm in estados_map:
                uf = estados_map[uf_norm]
                print(f"[DEBUG] UF normalizado para: {uf}")
        
        # Se ainda assim o UF não estiver no formato correto, retornar erro
        if len(uf) != 2:
            print(f"[ERROR] UF inválido: {uf}")
            return jsonify([])
        
        # Buscar o ID do estado primeiro
        estados_response = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados", timeout=10)
        estados_response.raise_for_status()
        estados_data = estados_response.json()
        estado_id = None
        
        for estado in estados_data:
            if estado['sigla'] == uf:
                estado_id = estado['id']
                break
        
        if not estado_id:
            print(f"[ERROR] Estado não encontrado para UF: {uf}")
            return jsonify([])
        
        # Buscar municípios usando o ID do estado
        print(f"[DEBUG] Buscando municípios para estado ID: {estado_id}")
        response = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{estado_id}/municipios", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            print(f"[ERROR] Nenhum município encontrado para UF: {uf}")
            return jsonify([])
        
        municipios = [{"id": m["nome"], "text": m["nome"]} for m in data]
        print(f"[DEBUG] Encontrados {len(municipios)} municípios para UF: {uf}")
        return jsonify(sorted(municipios, key=lambda x: x["text"]))
    except requests.exceptions.Timeout:
        print(f"[ERROR] Timeout ao buscar municípios para UF: {uf}")
        return jsonify([])
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Erro na requisição HTTP para UF {uf}: {str(e)}")
        return jsonify([])
    except Exception as e:
        print(f"[ERROR] Erro ao obter municípios de {uf}: {str(e)}")
        return jsonify([])

@app.route("/api/base-agentes")
def api_base_agentes():
    """API endpoint para fornecer dados da Base Unificada para o mapa de agentes"""
    try:
        print("[API] Carregando base unificada para mapa de agentes...")
        
        # Carregar base unificada
        df_base = carregar_base_unificada()
        if df_base is None:
            print("[API] Erro: Base unificada não disponível")
            return jsonify({
                "error": "Base de dados não disponível",
                "agentes": []
            })
        
        print(f"[API] Base carregada: {len(df_base)} registros")
        
        # Mapear estados para UF
        estados_uf = {
            'Acre': 'AC', 'Alagoas': 'AL', 'Amapá': 'AP', 'Amazonas': 'AM',
            'Bahia': 'BA', 'Ceará': 'CE', 'Distrito Federal': 'DF', 'Espírito Santo': 'ES',
            'Goiás': 'GO', 'Maranhão': 'MA', 'Mato Grosso': 'MT', 'Mato Grosso do Sul': 'MS',
            'Minas Gerais': 'MG', 'Pará': 'PA', 'Paraíba': 'PB', 'Paraná': 'PR',
            'Pernambuco': 'PE', 'Piauí': 'PI', 'Rio de Janeiro': 'RJ', 'Rio Grande do Norte': 'RN',
            'Rio Grande do Sul': 'RS', 'Rondônia': 'RO', 'Roraima': 'RR', 'Santa Catarina': 'SC',
            'São Paulo': 'SP', 'Sergipe': 'SE', 'Tocantins': 'TO'
        }
        
        # Função para extrair UF de uma cidade
        def extrair_uf_cidade(cidade_texto):
            if not cidade_texto or (hasattr(pd, 'isna') and pd.isna(cidade_texto)) or str(cidade_texto).strip() == 'nan':
                return None
            
            cidade_str = str(cidade_texto).strip()
            
            # Tentar encontrar UF no final do texto
            import re
            
            # Procurar por padrões como "São Paulo - SP" ou "São Paulo/SP"
            match = re.search(r'[-/\s]([A-Z]{2})$', cidade_str)
            if match:
                return match.group(1)
            
            # Procurar por nome de estado completo
            for estado, uf in estados_uf.items():
                if estado.lower() in cidade_str.lower():
                    return uf
            
            # Se não encontrou, tentar deduzir por cidades conhecidas
            cidades_conhecidas = {
                'São Paulo': 'SP', 'Rio de Janeiro': 'RJ', 'Belo Horizonte': 'MG',
                'Salvador': 'BA', 'Brasília': 'DF', 'Fortaleza': 'CE',
                'Recife': 'PE', 'Porto Alegre': 'RS', 'Manaus': 'AM',
                'Curitiba': 'PR', 'Goiânia': 'GO', 'Belém': 'PA',
                'Guarulhos': 'SP', 'Campinas': 'SP', 'São Bernardo do Campo': 'SP',
                'Nova Iguaçu': 'RJ', 'Duque de Caxias': 'RJ', 'São Gonçalo': 'RJ',
                'Maceió': 'AL', 'Natal': 'RN', 'Campo Grande': 'MS',
                'Teresina': 'PI', 'São Luís': 'MA', 'João Pessoa': 'PB',
                'Aracaju': 'SE', 'Cuiabá': 'MT', 'Florianópolis': 'SC',
                'Vitória': 'ES', 'Palmas': 'TO', 'Macapá': 'AP',
                'Rio Branco': 'AC', 'Boa Vista': 'RR', 'Porto Velho': 'RO'
            }
            
            for cidade, uf in cidades_conhecidas.items():
                if cidade.lower() in cidade_str.lower():
                    return uf
            
            return None
        
        # Processar dados usando as colunas corretas
        agentes_processados = []
        
        for index, row in df_base.iterrows():
            try:
                # Campos básicos usando as colunas corretas - com tratamento de NaN
                fornecedor = str(row.get('Fornecedor', 'N/A')).strip() if pd.notna(row.get('Fornecedor', 'N/A')) else 'N/A'
                tipo = str(row.get('Tipo', 'N/A')).strip() if pd.notna(row.get('Tipo', 'N/A')) else 'N/A'
                origem = str(row.get('Origem', '')).strip() if pd.notna(row.get('Origem', '')) else ''  # Coluna D (município)
                destino = str(row.get('Destino', '')).strip() if pd.notna(row.get('Destino', '')) else ''
                base_origem = str(row.get('Base Origem', '')).strip() if pd.notna(row.get('Base Origem', '')) else ''
                base_destino = str(row.get('Base Destino', '')).strip() if pd.notna(row.get('Base Destino', '')) else ''
                uf_direto = str(row.get('UF', '')).strip() if pd.notna(row.get('UF', '')) else ''  # Coluna Z (UF)
                
                # Usar UF diretamente da coluna Z
                if uf_direto and uf_direto.upper() not in ['NAN', 'NONE', '']:
                    uf_final = uf_direto.upper()
                else:
                    # Fallback: tentar extrair da origem
                    uf_final = extrair_uf_cidade(origem)
                    if not uf_final:
                        uf_final = extrair_uf_cidade(destino)
                
                # Validar UF (deve ter exatamente 2 caracteres e ser alfanumérico)
                if uf_final and len(str(uf_final)) == 2 and str(uf_final).isalpha():
                    # Criar entrada do agente - garantir que todos os campos são strings válidas
                    agente = {
                        'Fornecedor': fornecedor if fornecedor else 'N/A',
                        'Tipo': tipo if tipo else 'N/A',
                        'Origem': origem if origem else '',
                        'Destino': destino if destino else '',
                        'Base Origem': base_origem if base_origem else '',
                        'Base Destino': base_destino if base_destino else '',
                        'UF': str(uf_final).upper()
                    }
                    
                    agentes_processados.append(agente)
                    
            except Exception as e:
                print(f"[API] Erro ao processar linha {index}: {e}")
                continue
        
        print(f"[API] Processados {len(agentes_processados)} agentes")
        
        # Debug: mostrar estatísticas por estado
        if agentes_processados:
            from collections import Counter
            ufs_counter = Counter([agente['UF'] for agente in agentes_processados])
            print(f"[API] Agentes por UF: {dict(list(ufs_counter.most_common(10)))}")
        
        # Retornar apenas os dados necessários
        return jsonify(agentes_processados)
        
    except Exception as e:
        print(f"[API] Erro ao carregar base de agentes: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "agentes": []
        })

@app.route("/historico")
@middleware_auth
def historico():
    """Retorna o histórico de pesquisas com dados mais detalhados"""
    try:
        # Formatar o histórico para melhor exibição
        historico_formatado = []
        
        for item in HISTORICO_PESQUISAS:
            if isinstance(item, dict):
                historico_item = {
                    'id_historico': item.get('id_historico', 'N/A'),
                    'tipo': item.get('tipo', 'Cálculo'),
                    'origem': item.get('origem', 'N/A'),
                    'destino': item.get('destino', 'N/A'),
                    'distancia': item.get('distancia', 'N/A'),
                    'data_hora': item.get('data_hora', 'N/A'),
                    'duracao_minutos': item.get('duracao_minutos', 'N/A'),
                    'provider': item.get('provider', 'N/A'),
                    'custos': item.get('custos', {})
                }
                historico_formatado.append(historico_item)
        
        return jsonify(historico_formatado)
    except Exception as e:
        print(f"[ERROR] Erro ao carregar histórico: {e}")
        return jsonify([])

@app.route("/calcular", methods=["POST"])
@middleware_auth
def calcular():
    global ultimoResultadoDedicado
    ip_cliente = obter_ip_cliente()
    usuario = session.get('usuario_logado', 'DESCONHECIDO')
    
    try:
        data = request.get_json()
        uf_origem = data.get("uf_origem")
        municipio_origem = data.get("municipio_origem")
        uf_destino = data.get("uf_destino")
        municipio_destino = data.get("municipio_destino")
        peso = data.get("peso", 0)
        cubagem = data.get("cubagem", 0)
        
        log_acesso(usuario, 'CALCULO_DEDICADO', ip_cliente, 
                  f"Cálculo: {municipio_origem}/{uf_origem} -> {municipio_destino}/{uf_destino}, Peso: {peso}kg")
        
        if not all([uf_origem, municipio_origem, uf_destino, municipio_destino]):
            return jsonify({"error": "Origem e destino são obrigatórios"})
        coord_origem = geocode(municipio_origem, uf_origem)
        coord_destino = geocode(municipio_destino, uf_destino)
        print(f"[DEBUG] coord_origem: {coord_origem}")
        print(f"[DEBUG] coord_destino: {coord_destino}")
        if not coord_origem or not coord_destino:
            return jsonify({"error": "Não foi possível geocodificar origem ou destino"})
        rota_info = calcular_distancia_osrm(coord_origem, coord_destino) or \
                    calcular_distancia_openroute(coord_origem, coord_destino) or \
                    calcular_distancia_reta(coord_origem, coord_destino)
        print(f"[DEBUG] rota_info: {rota_info}")
        if not rota_info:
            return jsonify({"error": "Não foi possível calcular a rota"})
        # Primeiro gerar análise para calcular pedágios reais
        analise_preliminar = gerar_analise_trajeto(coord_origem, coord_destino, rota_info, {}, "Dedicado", municipio_origem, uf_origem, municipio_destino, uf_destino)
        
        # Usar pedágio real para calcular custos
        pedagio_real = analise_preliminar.get('pedagio_real', 0)
        custos = calcular_custos_dedicado(uf_origem, municipio_origem, uf_destino, municipio_destino, rota_info["distancia"], pedagio_real)
        
        # Gerar análise final com custos atualizados
        analise = gerar_analise_trajeto(coord_origem, coord_destino, rota_info, custos, "Dedicado", municipio_origem, uf_origem, municipio_destino, uf_destino)
        ultimoResultadoDedicado = analise
        HISTORICO_PESQUISAS.append(analise)
        if len(HISTORICO_PESQUISAS) > 15:
            HISTORICO_PESQUISAS.pop(0)
        
        # 🆕 GERAR RANKING "ALL IN" PARA FRETE DEDICADO
        peso_informado = data.get("peso", 0)
        cubagem_informada = data.get("cubagem", 0)
        valor_nf = data.get("valor_nf")
        
        ranking_dedicado = gerar_ranking_dedicado(
            custos, analise, rota_info, 
            peso_informado, cubagem_informada, valor_nf
        )
        
        rota_pontos = rota_info.get("rota_pontos", [])
        print(f"[DEBUG] rota_pontos final: {rota_pontos}")
        if not isinstance(rota_pontos, list) or len(rota_pontos) == 0:
            rota_pontos = [coord_origem, coord_destino]
        for i, pt in enumerate(rota_pontos):
            if not isinstance(pt, list) or len(pt) < 2:
                rota_pontos[i] = [0, 0]
        
        # 🚀 RESPOSTA NO FORMATO "ALL IN" DEDICADO
        resposta = {
            "tipo": "Dedicado",
            "distancia": rota_info["distancia"],
            "duracao": rota_info["duracao"],
            "custos": custos,  # Para compatibilidade
            "rota_pontos": rota_pontos,
            "analise": {
                "tempo_estimado": analise["tempo_estimado"],
                "consumo_combustivel": analise["consumo_combustivel"],
                "emissao_co2": analise["emissao_co2"],
                "pedagio_estimado": analise["pedagio_estimado"],
                "pedagio_real": analise.get("pedagio_real", 0),
                "pedagio_detalhes": analise.get("pedagio_detalhes"),
                "origem": analise["origem"],
                "destino": analise["destino"],
                "distancia": analise["distancia"],
                "duracao_minutos": analise["duracao_minutos"],
                "provider": analise["provider"],
                "data_hora": analise["data_hora"],
                "rota_pontos": rota_pontos,
                "id_historico": analise["id_historico"],
                "tipo": "Dedicado",
                "custos": custos,
                # Adicionar informações para mapa com pedágios
                "pedagios_mapa": gerar_pedagios_estimados_mapa(rota_info, "CARRETA", analise.get("pedagio_real", 0), rota_info["distancia"]) if analise.get("pedagio_real", 0) > 0 else None
            },
            # 🎯 DADOS DO RANKING "ALL IN" (NOVO FORMATO)
            "ranking_dedicado": ranking_dedicado,
            "melhor_opcao": ranking_dedicado['melhor_opcao'] if ranking_dedicado else None,
            "total_opcoes": ranking_dedicado['total_opcoes'] if ranking_dedicado else len(custos)
        }
        return jsonify(resposta)
    except Exception as e:
        log_acesso(usuario, 'ERRO_CALCULO_DEDICADO', ip_cliente, f"Erro: {str(e)}")
        print(f"Erro ao calcular frete dedicado: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erro ao calcular frete dedicado: {str(e)}"})

@app.route("/calcular_aereo", methods=["POST"])
@middleware_auth
def calcular_aereo():
    global ultimoResultadoAereo # Adicionado para exportação
    ip_cliente = obter_ip_cliente()
    usuario = session.get('usuario_logado', 'DESCONHECIDO')
    
    try:
        data = request.get_json()
        uf_origem = data.get("uf_origem")
        municipio_origem = data.get("municipio_origem")
        uf_destino = data.get("uf_destino")
        municipio_destino = data.get("municipio_destino")
        peso = data.get("peso", 5)
        cubagem = data.get("cubagem", 0.02)

        log_acesso(usuario, 'CALCULO_AEREO', ip_cliente, 
                  f"Cálculo Aéreo: {municipio_origem}/{uf_origem} -> {municipio_destino}/{uf_destino}, Peso: {peso}kg")

        if not all([uf_origem, municipio_origem, uf_destino, municipio_destino]):
            return jsonify({"error": "Origem e destino são obrigatórios"})

        # Geocodificar origem e destino
        coord_origem = geocode(municipio_origem, uf_origem)
        coord_destino = geocode(municipio_destino, uf_destino)

        if not coord_origem or not coord_destino:
            return jsonify({"error": "Não foi possível geocodificar origem ou destino"})

        # Para modal aéreo, usar sempre distância em linha reta
        rota_info = calcular_distancia_reta(coord_origem, coord_destino)

        if not rota_info:
            return jsonify({"error": "Não foi possível calcular a rota"})

        # Buscar dados aéreos da Base Unificada
        valor_nf = data.get("valor_nf")  # Capturar valor da NF se informado
        resultado_aereo = calcular_frete_aereo_base_unificada(
            municipio_origem, uf_origem,
            municipio_destino, uf_destino,
            peso, valor_nf
        )
        
        custos_aereo = {}
        
        if resultado_aereo and resultado_aereo.get('opcoes'):
            # Usar dados da base unificada
            opcoes = resultado_aereo['opcoes']
            
            # Agrupar por fornecedor/modalidade
            for opcao in opcoes:
                fornecedor = opcao['fornecedor']
                custos_aereo[fornecedor] = opcao['total']
        else:
            # Se não encontrou dados específicos, usar valores padrão
            peso_cubado = max(float(peso), float(cubagem) * 300)
            custos_aereo = {
                "ECONOMICO": round(peso_cubado * 8.5, 2),
                "RAPIDO": round(peso_cubado * 12.0, 2),
                "URGENTE": round(peso_cubado * 18.5, 2)
            }

        # Gerar análise
        analise = gerar_analise_trajeto(coord_origem, coord_destino, rota_info, custos_aereo, "Aéreo", municipio_origem, uf_origem, municipio_destino, uf_destino)
        
        # Armazenar resultado para exportação
        ultimoResultadoAereo = analise
        
        # Registrar no histórico
        HISTORICO_PESQUISAS.append(analise)
        if len(HISTORICO_PESQUISAS) > 15:
            HISTORICO_PESQUISAS.pop(0)

        resposta = {
            "distancia": rota_info["distancia"],
            "duracao": rota_info["duracao"],
            "custos": custos_aereo,
            "rota_pontos": rota_info["rota_pontos"],
            "analise": analise,
            "tipo": "Aéreo"
        }
        
        return jsonify(resposta)
    
    except Exception as e:
        log_acesso(usuario, 'ERRO_CALCULO_AEREO', ip_cliente, f"Erro: {str(e)}")
        print(f"Erro ao calcular frete aéreo: {e}")
        return jsonify({"error": f"Erro ao calcular frete aéreo: {str(e)}"})

@app.route("/calcular_frete_fracionado", methods=["POST"])
@middleware_auth
def calcular_frete_fracionado():
    global ultimoResultadoFracionado
    ip_cliente = obter_ip_cliente()
    usuario = session.get('usuario_logado', 'DESCONHECIDO')
    
    try:
        data = request.get_json()
        uf_origem = data.get("uf_origem")
        municipio_origem = data.get("municipio_origem")
        uf_destino = data.get("uf_destino")
        municipio_destino = data.get("municipio_destino")
        peso = data.get("peso", 1)
        cubagem = data.get("cubagem", 0.01)
        valor_nf = data.get("valor_nf")

        log_acesso(usuario, 'CALCULO_FRACIONADO', ip_cliente, 
                  f"Cálculo Fracionado: {municipio_origem}/{uf_origem} -> {municipio_destino}/{uf_destino}, Peso: {peso}kg, Cubagem: {cubagem}m³")

        if not all([uf_origem, municipio_origem, uf_destino, municipio_destino]):
            return jsonify({"error": "Origem e destino são obrigatórios"})

        # Buscar dados fracionados da Base Unificada
        resultado_fracionado = calcular_frete_fracionado_base_unificada(
            municipio_origem, uf_origem,
            municipio_destino, uf_destino,
            peso, cubagem, valor_nf
        )
        
        # Verificar se há avisos especiais (sem agente de entrega)
        if resultado_fracionado and resultado_fracionado.get('tipo_aviso') == 'SEM_AGENTE_ENTREGA':
            return jsonify({
                "error": f"⚠️ {resultado_fracionado.get('aviso')}",
                "ranking_fracionado": None,
                "tipo": "Fracionado",
                "aviso_tipo": "SEM_AGENTE_ENTREGA",
                "detalhes": "Não há agentes de entrega disponíveis na cidade de destino. Verifique se há cobertura na região."
            })
        
        if not resultado_fracionado or not resultado_fracionado.get('opcoes'):
            return jsonify({
                "error": "Nenhuma opção de frete fracionado encontrada para esta rota",
                "ranking_fracionado": None,
                "tipo": "Fracionado"
            })
        
        opcoes = resultado_fracionado['opcoes']
        
        # 🆕 GERAR RANKING NO FORMATO DEDICADO
        ranking_fracionado = gerar_ranking_fracionado(
            opcoes, 
            f"{municipio_origem}/{uf_origem}",
            f"{municipio_destino}/{uf_destino}",
            peso, cubagem, valor_nf
        )
        
        if not ranking_fracionado:
            return jsonify({
                "error": "Erro ao gerar ranking das opções",
                "ranking_fracionado": None,
                "tipo": "Fracionado"
            })
        
        # Preparar custos para compatibilidade (formato antigo)
        custos_fracionado = {}
        for opcao in ranking_fracionado['ranking_opcoes']:
            servico = opcao['tipo_servico']
            custos_fracionado[servico] = opcao['custo_total']
        
        # Análise para histórico
        analise = {
            'id_historico': ranking_fracionado['id_calculo'],
            'tipo': 'Fracionado',
            'origem': ranking_fracionado['origem'],
            'destino': ranking_fracionado['destino'],
            'distancia': ranking_fracionado['distancia'],
            'tempo_estimado': ranking_fracionado['tempo_estimado'],
            'peso_cubado': ranking_fracionado['peso_cubado'],
            'valor_nf': valor_nf,
            'data_hora': ranking_fracionado['data_calculo'],
            'ranking_opcoes': ranking_fracionado['ranking_opcoes'],
            'melhor_opcao': ranking_fracionado['melhor_opcao']
        }
        
        # Armazenar resultado para exportação
        ultimoResultadoFracionado = analise
        
        # Registrar no histórico
        HISTORICO_PESQUISAS.append(analise)
        if len(HISTORICO_PESQUISAS) > 15:
            HISTORICO_PESQUISAS.pop(0)

        # 🚀 RESPOSTA NO FORMATO DEDICADO
        resposta = {
            "tipo": "Fracionado",
            "distancia": ranking_fracionado['distancia'],
            "duracao": (ranking_fracionado['distancia'] / 80) * 60,  # Estimativa
            "custos": custos_fracionado,  # Para compatibilidade
            "rota_pontos": [[-21.2, -47.8], [-26.9, -48.7]],  # Coordenadas aproximadas
            "analise": {
                "id_historico": ranking_fracionado['id_calculo'],
                "tipo": "Fracionado",
                "origem": ranking_fracionado['origem'],
                "destino": ranking_fracionado['destino'],
                "distancia": ranking_fracionado['distancia'],
                "tempo_estimado": ranking_fracionado['tempo_estimado'],
                "consumo_estimado": ranking_fracionado['consumo_estimado'],
                "emissao_co2": ranking_fracionado['emissao_co2'],
                "peso_cubado": ranking_fracionado['peso_cubado'],
                "peso_usado_tipo": ranking_fracionado['peso_usado_tipo'],
                "valor_nf": valor_nf,
                "data_hora": ranking_fracionado['data_calculo'],
                "provider": "Base Unificada"
            },
            # 🎯 DADOS DO RANKING (NOVO FORMATO)
            "ranking_fracionado": ranking_fracionado,
            "melhor_opcao": ranking_fracionado['melhor_opcao'],
            "total_opcoes": ranking_fracionado['total_opcoes']
        }
        
        # 🔧 CORREÇÃO: Sanitizar JSON para evitar valores NaN
        resposta_sanitizada = sanitizar_json(resposta)
        return jsonify(resposta_sanitizada)
    
    except Exception as e:
        log_acesso(usuario, 'ERRO_CALCULO_FRACIONADO', ip_cliente, f"Erro: {str(e)}")
        print(f"Erro ao calcular frete fracionado: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erro ao calcular frete fracionado: {str(e)}"})

def log_debug(msg):
    """Função para controlar logs de debug. Pode ser facilmente desativada."""
    DEBUG = False  # Mudar para True para ativar logs
    if DEBUG:
        print(msg)

def sanitizar_json(obj):
    """
    Sanitiza objeto Python para ser convertido em JSON válido.
    Converte NaN, inf, -inf para valores válidos.
    """
    import math
    import pandas as pd
    
    if isinstance(obj, dict):
        return {key: sanitizar_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [sanitizar_json(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitizar_json(item) for item in obj)
    elif pd.isna(obj) or (isinstance(obj, float) and math.isnan(obj)):
        return None  # ou 0, dependendo do contexto
    elif isinstance(obj, float) and math.isinf(obj):
        return None  # ou um valor muito grande/pequeno
    elif hasattr(obj, 'item'):  # numpy types
        return sanitizar_json(obj.item())
    elif hasattr(obj, 'to_dict'):  # pandas objects
        return sanitizar_json(obj.to_dict())
    else:
        return obj

def encontrar_municipios_proximos(municipio, uf, raio_km=100, limite=5):
    """
    Encontra municípios próximos ao município especificado dentro de um raio em km.
    Retorna uma lista de tuplas (municipio, uf, distancia_km) ordenada por distância.
    """
    try:
        # Primeiro, obter as coordenadas do município de origem
        origem_coords = geocode(municipio, uf)
        if not origem_coords:
            print(f"[GEO] ❌ Não foi possível obter coordenadas para {municipio}/{uf}")
            return []
            
        # Carregar todos os municípios do estado
        municipios_estado = obter_municipios_uf(uf)
        if not municipios_estado:
            print(f"[GEO] ❌ Não foi possível carregar municípios para {uf}")
            return []
            
        # Calcular distância para cada município
        municipios_com_distancia = []
        
        for muni in municipios_estado:
            if muni['nome'].lower() == municipio.lower():
                continue  # Pular o próprio município
                
            # Obter coordenadas do município de destino
            dest_coords = geocode(muni['nome'], uf)
            if not dest_coords:
                continue
                
            # Calcular distância em km (fórmula de Haversine)
            lat1, lon1 = origem_coords
            lat2, lon2 = dest_coords
            
            # Raio da Terra em km
            R = 6371.0
            
            # Converter graus para radianos
            lat1_rad = math.radians(lat1)
            lon1_rad = math.radians(lon1)
            lat2_rad = math.radians(lat2)
            lon2_rad = math.radians(lon2)
            
            # Diferença das coordenadas
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad
            
            # Fórmula de Haversine
            a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distancia = R * c
            
            # Adicionar à lista se estiver dentro do raio
            if distancia <= raio_km:
                municipios_com_distancia.append((muni['nome'], uf, round(distancia, 1)))
        
        # Ordenar por distância e limitar o número de resultados
        municipios_com_distancia.sort(key=lambda x: x[2])
        return municipios_com_distancia[:limite]
        
    except Exception as e:
        print(f"[GEO] ❌ Erro ao buscar municípios próximos: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def validar_e_corrigir_rota_fracionada(rota):
    """
    Valida e corrige dados de uma rota fracionada para garantir consistência
    """
    try:
        # Verificar se a rota tem os campos obrigatórios
        if not isinstance(rota, dict):
            return rota
            
        # Verificar tipo da rota
        tipo_rota = rota.get('tipo_rota', '')
        
        # Corrigir agente de coleta se necessário
        agente_coleta = rota.get('agente_coleta', {})
        if isinstance(agente_coleta, dict):
            if ('Cliente entrega na origem' in str(agente_coleta.get('fornecedor', '')) or 
                agente_coleta.get('sem_agente', False)):
                # Garantir que todos os valores estão zerados
                agente_coleta.update({
                    'custo': 0,
                    'total': 0,
                    'pedagio': 0,
                    'gris': 0,
                    'seguro': 0,
                    'prazo': 0,
                    'sem_agente': True
                })
        
        # Corrigir agente de entrega se necessário  
        agente_entrega = rota.get('agente_entrega', {})
        if isinstance(agente_entrega, dict):
            if ('Cliente retira no destino' in str(agente_entrega.get('fornecedor', '')) or 
                agente_entrega.get('sem_agente', False)):
                # Garantir que todos os valores estão zerados
                agente_entrega.update({
                    'custo': 0,
                    'total': 0,
                    'pedagio': 0,
                    'gris': 0,
                    'seguro': 0,
                    'prazo': 0,
                    'sem_agente': True
                })
        
        # Validar detalhamento de custos
        detalhamento = rota.get('detalhamento_custos', {})
        if isinstance(detalhamento, dict):
            # Se não há agente de coleta, garantir que coleta está zerada
            if agente_coleta.get('sem_agente', False):
                detalhamento['coleta'] = 0
            
            # Se não há agente de entrega, garantir que entrega está zerada
            if agente_entrega.get('sem_agente', False):
                detalhamento['entrega'] = 0
        
        print(f"[VALIDACAO] ✅ Rota {tipo_rota} validada e corrigida")
        return rota
        
    except Exception as e:
        print(f"[VALIDACAO] ❌ Erro ao validar rota: {e}")
        return rota

@app.route("/teste-municipios")
def teste_municipios():
    """Página de teste para verificar o carregamento de municípios"""
    return '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Teste de Municípios</title>
    <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet"/>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/i18n/pt-BR.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .form-group { margin: 15px 0; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        select { width: 300px; }
        .status { margin: 10px 0; padding: 10px; border-radius: 5px; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
    </style>
</head>
<body>
    <h1>🧪 Teste de Carregamento de Municípios</h1>
    <p><a href="/" target="_blank">← Voltar para o sistema principal</a></p>
    
    <div class="form-group">
        <label for="estado">Estado:</label>
        <select id="estado" name="estado">
            <option value="">Carregando estados...</option>
        </select>
    </div>
    
    <div class="form-group">
        <label for="municipio">Município:</label>
        <select id="municipio" name="municipio">
            <option value="">Selecione primeiro um estado</option>
        </select>
    </div>
    
    <div id="status" class="status info">
        Aguardando carregamento dos estados...
    </div>

    <script>
        console.log('🧪 Iniciando teste de municípios...');
        
        function updateStatus(message, type = 'info') {
            const statusDiv = document.getElementById('status');
            statusDiv.textContent = message;
            statusDiv.className = `status ${type}`;
            console.log(`[${type.toUpperCase()}] ${message}`);
        }

        async function carregarEstados() {
            try {
                updateStatus('Carregando estados...', 'info');
                
                const response = await fetch('/estados');
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const estados = await response.json();
                console.log('Estados recebidos:', estados);
                
                const select = document.getElementById('estado');
                select.innerHTML = '<option value="">Selecione o estado</option>';
                
                estados.forEach(estado => {
                    const option = document.createElement('option');
                    option.value = estado.id;
                    option.textContent = estado.text;
                    select.appendChild(option);
                });
                
                $('#estado').select2({
                    language: 'pt-BR',
                    placeholder: 'Digite para buscar...',
                    allowClear: true,
                    width: '100%'
                });
                
                updateStatus(`✅ ${estados.length} estados carregados com sucesso!`, 'success');
                
            } catch (error) {
                console.error('Erro ao carregar estados:', error);
                updateStatus(`❌ Erro ao carregar estados: ${error.message}`, 'error');
            }
        }

        async function carregarMunicipios(uf) {
            try {
                updateStatus(`Carregando municípios de ${uf}...`, 'info');
                
                const response = await fetch(`/municipios/${encodeURIComponent(uf)}`);
                console.log(`Status da resposta: ${response.status}`);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const municipios = await response.json();
                console.log(`Municípios recebidos (${municipios.length}):`, municipios.slice(0, 5));
                
                if (!Array.isArray(municipios)) {
                    throw new Error(`Resposta não é um array: ${typeof municipios}`);
                }
                
                const select = document.getElementById('municipio');
                
                if ($(select).hasClass('select2-hidden-accessible')) {
                    $('#municipio').select2('destroy');
                }
                
                select.innerHTML = '<option value="">Selecione o município</option>';
                
                municipios.forEach(municipio => {
                    const option = document.createElement('option');
                    option.value = municipio.id;
                    option.textContent = municipio.text;
                    select.appendChild(option);
                });
                
                $('#municipio').select2({
                    language: 'pt-BR',
                    placeholder: 'Digite para buscar...',
                    allowClear: true,
                    width: '100%'
                });
                
                updateStatus(`✅ ${municipios.length} municípios de ${uf} carregados com sucesso!`, 'success');
                
            } catch (error) {
                console.error(`Erro ao carregar municípios de ${uf}:`, error);
                updateStatus(`❌ Erro ao carregar municípios de ${uf}: ${error.message}`, 'error');
            }
        }

        document.getElementById('estado').addEventListener('change', function() {
            const uf = this.value;
            if (uf) {
                carregarMunicipios(uf);
            } else {
                const municipioSelect = document.getElementById('municipio');
                if ($(municipioSelect).hasClass('select2-hidden-accessible')) {
                    $('#municipio').select2('destroy');
                }
                municipioSelect.innerHTML = '<option value="">Selecione primeiro um estado</option>';
                updateStatus('Selecione um estado para carregar os municípios', 'info');
            }
        });

        document.addEventListener('DOMContentLoaded', function() {
            carregarEstados();
        });
    </script>
</body>
</html>'''

@app.route("/aereo")
def aereo():
    df_aereo = ler_gollog_aereo()
    if df_aereo is not None:
        # Ordenar por custo_base, se existir
        if "custo_base" in df_aereo.columns:
            df_aereo = df_aereo.sort_values(by="custo_base", ascending=True)
        dados = df_aereo.to_dict(orient="records")
        return jsonify(dados)
    else:
        return jsonify({"error": "Não foi possível carregar dados aéreos"})

@app.route("/debug-municipios")
def debug_municipios():
    """Página de debug para testar carregamento de municípios"""
    return send_file('test_municipios_debug.html')

@app.route("/gerar-pdf", methods=["POST"])
def gerar_pdf():
    try:
        import datetime
        import json
        import os
        import io
        
        dados = request.get_json()
        analise = dados.get("analise", {})
        dados_cotacao = dados.get("dados", {})
        
        pdf = FPDF()
        pdf.add_page()
        
        # Função para limpar caracteres especiais para PDF
        def limpar_texto_pdf(texto):
            if not texto:
                return ""
            # Remover caracteres não ASCII
            return ''.join(char for char in str(texto) if ord(char) < 128)
        
        # Adicionar logo se disponível
        logo_paths = [
            os.path.join(app.static_folder, 'portoex-logo.png'),
            'static/portoex-logo.png'
        ]
        
        logo_added = False
        for logo_path in logo_paths:
            if os.path.exists(logo_path):
                try:
                    pdf.image(logo_path, x=10, y=10, w=30)
                    pdf.ln(25)
                    logo_added = True
                    break
                except:
                    continue
        
        if not logo_added:
            pdf.ln(10)
        
        # Cabeçalho
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 12, "PortoEx - Relatorio de Frete", 0, 1, "C")
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 0, 1)
        pdf.ln(5)
        
        # Informações básicas
        pdf.set_font("Arial", "B", 12)
        pdf.set_fill_color(240, 248, 255)
        pdf.cell(0, 8, "INFORMACOES BASICAS", 0, 1, "L", True)
        pdf.ln(2)
        pdf.set_font("Arial", "", 11)

        # ID e Tipo
        id_historico = analise.get('id_historico', 'N/A')
        tipo_analise = analise.get('tipo', dados_cotacao.get('tipo', 'N/A'))
        pdf.cell(0, 6, limpar_texto_pdf(f"ID: {id_historico}"), 0, 1)
        pdf.cell(0, 6, limpar_texto_pdf(f"Tipo: {tipo_analise}"), 0, 1)

        # Origem e Destino
        origem = dados_cotacao.get('origem', analise.get('origem', 'N/A'))
        destino = dados_cotacao.get('destino', analise.get('destino', 'N/A'))
        pdf.cell(0, 6, limpar_texto_pdf(f"Origem: {origem}"), 0, 1)
        pdf.cell(0, 6, limpar_texto_pdf(f"Destino: {destino}"), 0, 1)

        # Peso e Cubagem
        peso = dados_cotacao.get('peso', analise.get('peso', 'N/A'))
        cubagem = dados_cotacao.get('cubagem', analise.get('cubagem', 'N/A'))
        if peso != 'N/A':
            pdf.cell(0, 6, limpar_texto_pdf(f"Peso: {peso} kg"), 0, 1)
        if cubagem != 'N/A':
            pdf.cell(0, 6, limpar_texto_pdf(f"Cubagem: {cubagem} m3"), 0, 1)
        pdf.ln(5)
            
        # Resultados das cotações
        rotas_agentes = dados_cotacao.get('rotas_agentes', {})
        cotacoes = rotas_agentes.get('cotacoes_ranking', [])
        
        if cotacoes:
                pdf.set_font("Arial", "B", 12)
                pdf.set_fill_color(240, 248, 255)
                pdf.cell(0, 8, "RESULTADOS DAS COTACOES", 0, 1, "L", True)
                pdf.ln(2)
                
                pdf.set_font("Arial", "", 10)
            
                for i, cotacao in enumerate(cotacoes[:10], 1):  # Máximo 10 cotações
                    resumo = cotacao.get('resumo', 'N/A')
                total = cotacao.get('total', 0)
                prazo = cotacao.get('prazo_total', 'N/A')
                
                pdf.cell(0, 5, limpar_texto_pdf(f"{i}. {resumo}"), 0, 1)
                pdf.cell(0, 5, limpar_texto_pdf(f"   Valor: R$ {total:,.2f} - Prazo: {prazo} dias"), 0, 1)
                pdf.ln(1)
        
        # Rodapé
        pdf.ln(10)
        pdf.set_font("Arial", "I", 8)
        pdf.cell(0, 4, "Relatorio gerado automaticamente pelo sistema PortoEx", 0, 1, "C")
        
        # Gerar PDF com codificação correta
        try:
            pdf_bytes = pdf.output(dest="S")
            if isinstance(pdf_bytes, str):
                pdf_bytes = pdf_bytes.encode('latin-1')
        except Exception as e:
            print(f"Erro na codificacao do PDF: {e}")
            pdf_bytes = pdf.output(dest="S").encode('latin-1', errors='ignore')
        
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"relatorio_frete_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        
    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        return jsonify({"error": f"Erro ao gerar PDF: {str(e)}"})


@app.route("/exportar-excel", methods=["POST"])
def exportar_excel():
    try:
        import pandas as pd
        import io
        import datetime
        
        dados = request.get_json()
        tipo = dados.get("tipo")
        dados_exportacao = dados.get("dados")
        
        # Criar DataFrame baseado no tipo
        if tipo == "Dedicado":
            df_export = pd.DataFrame([{
                "ID": dados_exportacao.get("id_historico"),
                "Tipo": dados_exportacao.get("tipo"),
                "Origem": dados_exportacao.get("origem"),
                "Destino": dados_exportacao.get("destino"),
                "Distância (km)": dados_exportacao.get("distancia"),
                "Tempo Estimado": dados_exportacao.get("tempo_estimado"),
                "Consumo Combustível (L)": dados_exportacao.get("consumo_combustivel"),
                "Emissão CO2 (kg)": dados_exportacao.get("emissao_co2"),
                "Pedágio Estimado (R$)": dados_exportacao.get("pedagio_estimado"),
                "Provider": dados_exportacao.get("provider"),
                "Data/Hora": dados_exportacao.get("data_hora")
            }])
        elif tipo == "Fracionado":
            # Extrair dados das rotas com agentes
            rotas_agentes = dados_exportacao.get("rotas_agentes", {})
            cotacoes_ranking = rotas_agentes.get("cotacoes_ranking", [])
            
            # Dados básicos da consulta
            dados_basicos = {
                "ID": dados_exportacao.get("id_historico"),
                "Tipo": "Frete Fracionado",
                "Origem": f"{dados_exportacao.get('cidades_origem', ['N/A'])[0] if isinstance(dados_exportacao.get('cidades_origem'), list) else dados_exportacao.get('cidades_origem', 'N/A')}",
                "UF Origem": dados_exportacao.get("uf_origem", "N/A"),
                "Destino": f"{dados_exportacao.get('cidades_destino', ['N/A'])[0] if isinstance(dados_exportacao.get('cidades_destino'), list) else dados_exportacao.get('cidades_destino', 'N/A')}",
                "UF Destino": dados_exportacao.get("uf_destino", "N/A"),
                "Peso (kg)": dados_exportacao.get("peso"),
                "Cubagem (m³)": dados_exportacao.get("cubagem"),
                "Peso Cubado (kg)": dados_exportacao.get("peso_cubado"),
                "Valor NF (R$)": dados_exportacao.get("valor_nf", 0),
                "Data/Hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            }
            
            # Se há rotas com agentes, criar planilha detalhada
            if cotacoes_ranking:
                lista_rotas = []
                for i, rota in enumerate(cotacoes_ranking, 1):
                    agente_coleta = rota.get('agente_coleta', {})
                    transferencia = rota.get('transferencia', {})
                    agente_entrega = rota.get('agente_entrega', {})
                    
                    dados_rota = dados_basicos.copy()
                    dados_rota.update({
                        "Posição Ranking": i,
                        "Rota Resumo": rota.get('resumo', 'N/A'),
                        "Custo Total (R$)": rota.get('total', 0),
                        "Prazo Total (dias)": rota.get('prazo_total', 'N/A'),
                        
                        # Agente de Coleta
                        "Agente Coleta": agente_coleta.get('fornecedor', 'N/A'),
                        "Coleta Origem": agente_coleta.get('origem', 'N/A'),
                        "Coleta Base Destino": agente_coleta.get('base_destino', 'N/A'),
                        "Coleta Custo (R$)": agente_coleta.get('custo', 0),
                        "Coleta Prazo (dias)": agente_coleta.get('prazo', 'N/A'),
                        "Coleta Peso Máximo (kg)": agente_coleta.get('peso_maximo', 'N/A'),
                        
                        # Transferência
                        "Transferência Fornecedor": transferencia.get('fornecedor', 'N/A'),
                        "Transferência Origem": transferencia.get('origem', 'N/A'),
                        "Transferência Destino": transferencia.get('destino', 'N/A'),
                        "Transferência Custo (R$)": transferencia.get('custo', 0),
                        "Transferência Pedágio (R$)": transferencia.get('pedagio', 0),
                        "Transferência GRIS (R$)": transferencia.get('gris', 0),
                        "Transferência Prazo (dias)": transferencia.get('prazo', 'N/A'),
                        
                        # Agente de Entrega
                        "Agente Entrega": agente_entrega.get('fornecedor', 'N/A'),
                        "Entrega Base Origem": agente_entrega.get('base_origem', 'N/A'),
                        "Entrega Destino": agente_entrega.get('destino', 'N/A'),
                        "Entrega Custo (R$)": agente_entrega.get('custo', 0),
                        "Entrega Prazo (dias)": agente_entrega.get('prazo', 'N/A'),
                        "Entrega Peso Máximo (kg)": agente_entrega.get('peso_maximo', 'N/A'),
                        
                        # Observações
                        "Observações": rota.get('observacoes', ''),
                        "Estratégia": dados_exportacao.get('estrategia_busca', 'N/A'),
                        "Fonte Dados": dados_exportacao.get('dados_fonte', 'N/A')
                    })
                    lista_rotas.append(dados_rota)
                
                df_export = pd.DataFrame(lista_rotas)
            else:
                # Se não há rotas, criar DataFrame básico
                df_export = pd.DataFrame([dados_basicos])
        else:
            df_export = pd.DataFrame([dados_exportacao])
        
        # Criar arquivo Excel em memória
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df_export.to_excel(writer, sheet_name="Dados", index=False)
            
            # Obter o workbook e worksheet para formatação
            workbook = writer.book
            worksheet = writer.sheets['Dados']
            
            # Formatar colunas de valor monetário
            money_format = workbook.add_format({'num_format': '#,##0.00'})
            
            # Aplicar formatação para colunas de valor
            if tipo == "Fracionado":
                valor_cols = ['H', 'J', 'M', 'Q', 'R', 'S', 'V']  # Colunas com valores monetários
                for col in valor_cols:
                    worksheet.set_column(f'{col}:{col}', 12, money_format)
                
                # Ajustar largura das colunas principais
                worksheet.set_column('A:A', 8)   # ID
                worksheet.set_column('B:B', 15)  # Tipo
                worksheet.set_column('C:D', 15)  # Origem/UF
                worksheet.set_column('E:F', 15)  # Destino/UF
                worksheet.set_column('G:G', 10)  # Peso
                worksheet.set_column('L:L', 20)  # Rota Resumo
                worksheet.set_column('AA:AA', 20) # Data/Hora
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"dados_frete_{tipo.lower()}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
    except Exception as e:
        print(f"Erro ao exportar Excel: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erro ao exportar Excel: {str(e)}"})

# APIs para cálculo de pedágios reais
GOOGLE_ROUTES_API_KEY = os.getenv("GOOGLE_ROUTES_API_KEY", "SUA_CHAVE_AQUI")
TOLLGURU_API_KEY = os.getenv("TOLLGURU_API_KEY", "SUA_CHAVE_TOLLGURU")
OPENROUTE_API_KEY = "5b3ce3597851110001cf6248a355ae5a9ee94a6ca9c6d876c7e4d534"  # Chave pública

def calcular_pedagios_reais(origem, destino, peso_veiculo=1000):
    """
    Sistema inteligente de cálculo de pedágios usando múltiplas APIs
    Prioridade: TollGuru (especializada) > Google Routes > OpenRoute + Estimativa Brasileira
    """
    try:
        print(f"[PEDÁGIO] 🎯 Calculando pedágios reais: {origem} -> {destino} (peso: {peso_veiculo}kg)")
        
        # 1. Tentar TollGuru primeiro (mais especializada em pedágios)
        result = calcular_pedagios_tollguru(origem, destino, peso_veiculo)
        if result:
            print(f"[PEDÁGIO] ✅ TollGuru bem-sucedida: R$ {result['pedagio_real']:.2f}")
            return result
        
        # 2. Fallback para Google Routes
        result = calcular_pedagios_google_routes(origem, destino, peso_veiculo)
        if result:
            print(f"[PEDÁGIO] ✅ Google Routes bem-sucedida: R$ {result['pedagio_real']:.2f}")
            return result
        
        # 3. Fallback final: OpenRoute + Estimativa Brasileira
        print(f"[PEDÁGIO] ⚠️ APIs externas indisponíveis - usando OpenRoute + estimativa brasileira")
        
        # Obter rota real usando OpenRoute
        rota_info = calcular_distancia_openroute_detalhada(origem, destino)
        if not rota_info:
            # Se OpenRoute falhar, usar OSRM
            rota_info = calcular_distancia_osrm(origem, destino)
        
        if not rota_info:
            print(f"[PEDÁGIO] ❌ Não foi possível obter rota - usando distância estimada")
            # Cálculo de distância aproximada usando haversine
            import math
            lat1, lon1 = origem[0], origem[1]
            lat2, lon2 = destino[0], destino[1]
            
            # Fórmula haversine
            R = 6371  # Raio da Terra em km
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distancia = R * c
            
            rota_info = {
                "distancia": distancia,
                "duracao": distancia / 80 * 60,  # Assumir 80 km/h média
                "provider": "Cálculo Aproximado"
            }
        
        distancia = rota_info.get("distancia", 0)
        
        # Estimativa brasileira avançada de pedágios por tipo de veículo e distância
        estimativas_pedagio = {
            "FIORINO": {"base": 0.03, "mult_dist": 1.0},      # R$ 0.03/km base
            "VAN": {"base": 0.05, "mult_dist": 1.1},          # R$ 0.05/km base + 10% em longas distâncias
            "3/4": {"base": 0.07, "mult_dist": 1.2},          # R$ 0.07/km base + 20%
            "TOCO": {"base": 0.10, "mult_dist": 1.3},         # R$ 0.10/km base + 30%
            "TRUCK": {"base": 0.14, "mult_dist": 1.4},        # R$ 0.14/km base + 40%
            "CARRETA": {"base": 0.18, "mult_dist": 1.5}       # R$ 0.18/km base + 50%
        }
        
        # Determinar tipo de veículo baseado no peso
        if peso_veiculo <= 500:
            tipo_veiculo = "FIORINO"
        elif peso_veiculo <= 1500:
            tipo_veiculo = "VAN"
        elif peso_veiculo <= 3500:
            tipo_veiculo = "3/4"
        elif peso_veiculo <= 7000:
            tipo_veiculo = "TOCO"
        elif peso_veiculo <= 12000:
            tipo_veiculo = "TRUCK"
        elif peso_veiculo <= 28000:
            tipo_veiculo = "CARRETA"
        
        config = estimativas_pedagio.get(tipo_veiculo, estimativas_pedagio["TOCO"])
        taxa_base = config["base"]
        
        # Ajustar taxa para longas distâncias (mais pedágios em rodovias principais)
        if distancia > 300:
            taxa_final = taxa_base * config["mult_dist"]
            ajuste_info = f"Longa distância ({distancia:.1f}km) - taxa aumentada {config['mult_dist']}x"
        else:
            taxa_final = taxa_base
            ajuste_info = "Distância normal - taxa base"
        
        pedagio_estimado = distancia * taxa_final
        
        # Gerar localizações estimadas de pedágios ao longo da rota
        pedagios_mapa = gerar_pedagios_estimados_mapa(rota_info, tipo_veiculo, pedagio_estimado, distancia)

        result = {
            "pedagio_real": pedagio_estimado,
            "moeda": "BRL",
            "distancia": distancia,
            "duracao": rota_info.get("duracao", 0),
            "fonte": f"{rota_info.get('provider', 'OpenRoute/OSRM')} + Estimativa Brasileira Avançada",
            "detalhes_pedagio": {
                "veiculo_tipo": tipo_veiculo,
                "peso_veiculo": peso_veiculo,
                "taxa_base_km": taxa_base,
                "taxa_final_km": taxa_final,
                "ajuste_distancia": ajuste_info,
                "calculo": f"{distancia:.1f} km × R$ {taxa_final:.3f}/km = R$ {pedagio_estimado:.2f}",
                "metodo": "Estimativa brasileira por peso/distância",
                "fonte_rota": rota_info.get('provider', 'Aproximação'),
                "fonte": "Sistema Integrado - Estimativa Brasileira",
                "num_pedagios": len(pedagios_mapa),
                "pedagios_detalhados": True,
                "pedagios_mapa": pedagios_mapa
            }
        }
        
        print(f"[PEDÁGIO] ✅ Estimativa brasileira: R$ {pedagio_estimado:.2f} ({tipo_veiculo})")
        return result
        
    except Exception as e:
        print(f"[PEDÁGIO] ❌ Erro geral no cálculo de pedágios: {e}")
        return None

def calcular_pedagios_google_routes(origem, destino, peso_veiculo=1000):
    """
    Calcula pedágios usando Google Routes API
    """
    try:
        if not GOOGLE_ROUTES_API_KEY or GOOGLE_ROUTES_API_KEY == "SUA_CHAVE_AQUI":
            print(f"[GOOGLE] ⚠️ Chave da Google Routes API não configurada")
            return None
            
        print(f"[GOOGLE] Tentando calcular pedágios: {origem} -> {destino}")
        
        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_ROUTES_API_KEY,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.travelAdvisory.tollInfo,routes.legs.steps.localizedValues"
        }
        
        # Configurar veículo baseado no peso
        if peso_veiculo <= 1000:
            vehicle_type = "TWO_WHEELER"
        elif peso_veiculo <= 3500:
            vehicle_type = "LIGHT_VEHICLE" 
        elif peso_veiculo <= 7500:
            vehicle_type = "MEDIUM_VEHICLE"
        else:
            vehicle_type = "HEAVY_VEHICLE"
        
        payload = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": origem[0],
                        "longitude": origem[1]
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": destino[0],
                        "longitude": destino[1]
                    }
                }
            },
            "travelMode": "DRIVE",
            "routeModifiers": {
                "vehicleInfo": {
                    "emissionType": "GASOLINE"
                },
                "tollPasses": [
                    "BR_AUTOPASS",  # Passe de pedágio brasileiro
                    "BR_CONECTCAR",
                    "BR_SEM_PARAR"
                ]
            },
            "extraComputations": ["TOLLS"],
            "units": "METRIC"
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if "routes" in data and len(data["routes"]) > 0:
                route = data["routes"][0]
                
                # Extrair informações de pedágio
                toll_info = route.get("travelAdvisory", {}).get("tollInfo", {})
                estimated_price = toll_info.get("estimatedPrice", [])
                
                total_toll = 0.0
                currency = "BRL"
                
                if estimated_price:
                    for price in estimated_price:
                        if price.get("currencyCode") == "BRL":
                            units = float(price.get("units", 0))
                            nanos = float(price.get("nanos", 0)) / 1000000000
                            total_toll += units + nanos
                            currency = price.get("currencyCode", "BRL")
                            break
            
                # Extrair distância e duração
                distance_meters = route.get("distanceMeters", 0)
                duration_seconds = route.get("duration", "0s")
                
                # Converter duração de string para segundos
                if isinstance(duration_seconds, str):
                    duration_seconds = int(duration_seconds.replace("s", ""))
                
                result = {
                    "pedagio_real": total_toll,
                    "moeda": currency,
                    "distancia": distance_meters / 1000,  # Converter para km
                    "duracao": duration_seconds / 60,  # Converter para minutos
                    "fonte": "Google Routes API",
                    "detalhes_pedagio": {
                        "veiculo_tipo": vehicle_type,
                        "passes_tentados": ["BR_AUTOPASS", "BR_CONECTCAR", "BR_SEM_PARAR"],
                        "preco_estimado": estimated_price
                    }
                }
                
                print(f"[GOOGLE] ✅ Pedágio calculado: R$ {total_toll:.2f}")
                return result
            else:
                print(f"[GOOGLE] ❌ Nenhuma rota encontrada")
                return None
                
        else:
            print(f"[GOOGLE] ❌ Erro na API: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"[GOOGLE] ❌ Erro: {e}")
        return None

def calcular_pedagios_fallback_brasil(distancia_km, tipo_veiculo="CARRETA"):
    """
    Fallback para cálculo de pedágios baseado em estimativas brasileiras
    Usando dados médios de pedágio por km no Brasil
    """
    try:
        # Valores médios de pedágio por km no Brasil (2024)
        valores_km = {
            "FIORINO": 0.03,      # R$ 0,03/km
            "VAN": 0.04,          # R$ 0,04/km  
            "3/4": 0.05,          # R$ 0,05/km
            "TOCO": 0.08,         # R$ 0,08/km
            "TRUCK": 0.12,        # R$ 0,12/km
            "CARRETA": 0.15       # R$ 0,15/km
        }
        
        valor_por_km = valores_km.get(tipo_veiculo, 0.08)  # Default para TOCO
        pedagio_estimado = distancia_km * valor_por_km
        
        return {
            "pedagio_real": pedagio_estimado,
            "moeda": "BRL",
            "distancia": distancia_km,
            "fonte": "Estimativa Brasil (fallback)",
            "detalhes_pedagio": {
                "valor_por_km": valor_por_km,
                "tipo_veiculo": tipo_veiculo,
                "calculo": f"{distancia_km:.1f} km × R$ {valor_por_km:.3f}/km"
            }
        }
        
    except Exception as e:
        print(f"[PEDÁGIO] Erro no fallback: {e}")
        return None

def calcular_pedagios_tollguru(origem, destino, peso_veiculo=1000):
    """
    Calcula pedágios reais usando TollGuru API - especializada em pedágios
    Mais precisa que Google Routes para cálculos de pedágio
    """
    try:
        if not TOLLGURU_API_KEY or TOLLGURU_API_KEY == "SUA_CHAVE_TOLLGURU":
            print(f"[TOLLGURU] ⚠️ Chave TollGuru não configurada")
            return None
            
        print(f"[TOLLGURU] Calculando pedágios reais: {origem} -> {destino}")
        
        # Primeiro obter rota do OpenRouteService
        rota_info = calcular_distancia_openroute_detalhada(origem, destino)
        if not rota_info or not rota_info.get('polyline'):
            print(f"[TOLLGURU] ❌ Não foi possível obter rota detalhada")
            return None
        
        # Configurar tipo de veículo baseado no peso
        if peso_veiculo <= 1000:
            vehicle_type = "2AxlesAuto"
        elif peso_veiculo <= 3500:
            vehicle_type = "2AxlesTruck" 
        elif peso_veiculo <= 7500:
            vehicle_type = "3AxlesTruck"
        elif peso_veiculo <= 15000:
            vehicle_type = "4AxlesTruck"
        else:
            vehicle_type = "5AxlesTruck"
        
        # Chamar TollGuru API
        url = "https://apis.tollguru.com/toll/v2"
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": TOLLGURU_API_KEY
        }
        
        payload = {
            "source": "openroute",
            "polyline": rota_info['polyline'],
            "vehicleType": vehicle_type,
            "departure_time": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "country": "BR"  # Brasil
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('route'):
                route = data['route']
                costs = route.get('costs', {})
                tolls = costs.get('tolls', [])
                
                total_toll = 0.0
                currency = "BRL"
                toll_details = []
                
                for toll in tolls:
                    if toll.get('currency') == 'BRL':
                        total_toll += float(toll.get('cost', 0))
                        toll_details.append({
                            'name': toll.get('name', 'Desconhecido'),
                            'cost': toll.get('cost', 0),
                            'currency': toll.get('currency', 'BRL')
                        })
                               
                result = {
                    "pedagio_real": total_toll,
                    "moeda": currency,
                    "distancia": route.get('distance', {}).get('value', 0) / 1000,
                    "duracao": route.get('duration', {}).get('value', 0) / 60,
                    "fonte": "TollGuru API (Especializada)",
                    "detalhes_pedagio": {
                        "veiculo_tipo": vehicle_type,
                        "num_pedagios": len(tolls),
                        "pedagios_detalhados": toll_details,
                        "rota_fonte": "OpenRouteService"
                    }
                }
                
                print(f"[TOLLGURU] ✅ Pedágio real: R$ {total_toll:.2f} ({len(tolls)} pedágios)")
                return result
            else:
                print(f"[TOLLGURU] ❌ Resposta inválida da API")
                return None
                
        else:
            print(f"[TOLLGURU] ❌ Erro na API: {response.status_code}")
            print(f"[TOLLGURU] Resposta: {response.text}")
            return None
            
    except Exception as e:
        print(f"[TOLLGURU] ❌ Erro: {e}")
        return None

def gerar_pedagios_estimados_mapa(rota_info, tipo_veiculo, valor_total_pedagio, distancia_total):
    """
    Gera localizações estimadas de pedágios ao longo da rota para exibir no mapa
    """
    try:
        pedagios_mapa = []
        
        # Se não temos pontos da rota, não podemos gerar localizações
        if not rota_info.get("rota_pontos") or len(rota_info["rota_pontos"]) < 2:
            return []
        
        rota_pontos = rota_info["rota_pontos"]
        
        # Estimar número de pedágios baseado na distância (aproximadamente a cada 120-180km)
        num_pedagios_estimado = max(1, int(distancia_total / 150))
        
        # Se a rota é muito curta, pode não ter pedágios
        if distancia_total < 80:
            return []
        
        # Calcular valor médio por pedágio
        valor_por_pedagio = valor_total_pedagio / num_pedagios_estimado if num_pedagios_estimado > 0 else 0
        
        # Distribuir pedágios ao longo da rota
        total_pontos = len(rota_pontos)
        
        for i in range(num_pedagios_estimado):
            # Posicionar pedágios em intervalos regulares ao longo da rota
            # Evitar muito próximo do início e fim
            posicao_percentual = 0.15 + (i * 0.7 / max(1, num_pedagios_estimado - 1))
            if num_pedagios_estimado == 1:
                posicao_percentual = 0.5  # No meio da rota
            
            indice_ponto = int(posicao_percentual * (total_pontos - 1))
            indice_ponto = max(0, min(indice_ponto, total_pontos - 1))
            
            lat, lon = rota_pontos[indice_ponto]
            
            # Variação no valor do pedágio baseada no tipo de estrada/região
            variacao = 0.8 + (i * 0.4 / max(1, num_pedagios_estimado - 1))  # Entre 80% e 120%
            valor_pedagio = valor_por_pedagio * variacao
            
            # Determinar nome estimado do pedágio baseado na posição
            nomes_estimados = [
                f"Pedágio {i+1} - Rodovia Principal",
                f"Praça {i+1} - Via Expressa", 
                f"Pedágio {i+1} - Concessionária",
                f"Posto {i+1} - Rodovia Federal"
            ]
            nome_pedagio = nomes_estimados[i % len(nomes_estimados)]
            
            pedagio_info = {
                "id": f"pedagio_{i+1}",
                "nome": nome_pedagio,
                "lat": lat,
                "lon": lon,
                "valor": valor_pedagio,
                "tipo_veiculo": tipo_veiculo,
                "distancia_origem": (i + 1) * (distancia_total / (num_pedagios_estimado + 1)),
                "concessionaria": f"Concessionária {chr(65 + i)}",  # A, B, C, etc.
                "tipo_estrada": "Rodovia Federal" if i % 2 == 0 else "Rodovia Estadual"
            }
            
            pedagios_mapa.append(pedagio_info)
        
        print(f"[PEDÁGIO_MAPA] Gerados {len(pedagios_mapa)} pedágios estimados para o mapa")
        return pedagios_mapa
        
    except Exception as e:
        print(f"[PEDÁGIO_MAPA] Erro ao gerar pedágios para mapa: {e}")
        return []

def calcular_distancia_openroute_detalhada(origem, destino):
    """
    Versão detalhada do cálculo de distância usando OpenRoute Service
    que inclui informações de polyline para APIs de pedágio
    """
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {
            "Authorization": OPENROUTE_API_KEY
        }
        params = {
            "start": f"{origem[1]},{origem[0]}",
            "end": f"{destino[1]},{destino[0]}",
            "format": "geojson"
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        data = response.json()
        
        if "features" in data and data["features"]:
            route = data["features"][0]
            segments = route.get("properties", {}).get("segments", [{}])[0]
            distance = segments.get("distance", 0) / 1000  # Converter para km
            duration = segments.get("duration", 0) / 60  # Converter para minutos
            geometry = route.get("geometry")
            
            # Extrair polyline para usar com APIs de pedágio
            coordinates = geometry.get("coordinates", [])
            polyline_encoded = None
            
            # Tentar gerar polyline (simplificado)
            if coordinates:
                try:
                    import polyline
                    # Converter coordenadas para formato lat,lng
                    points = [[coord[1], coord[0]] for coord in coordinates]
                    polyline_encoded = polyline.encode(points)
                except:
                    polyline_encoded = None
            
            route_points = [[coord[1], coord[0]] for coord in coordinates]
            
            return {
                "distancia": distance,
                "duracao": duration,
                "rota_pontos": route_points,
                "polyline": polyline_encoded,
                "consumo_combustivel": distance * 0.12,
                "pedagio_estimado": distance * 0.05,
                "provider": "OpenRoute Service"
            }
        
        return None
        
    except Exception as e:
        print(f"[OPENROUTE] Erro ao calcular distância detalhada: {e}")
        return None

@app.route("/analisar-base")
def analisar_base():
    """
    Analisar a base de dados para mapear cidades e suas abreviações
    """
    try:
        df = carregar_base_unificada()
        
        # Separar por tipo
        df_transferencias = df[df['Tipo'] == 'Transferência'].copy()
        df_agentes = df[df['Tipo'] == 'Agente'].copy()
        
        # Análise de cidades únicas nas transferências
        origens_transf = df_transferencias['Origem'].unique()
        destinos_transf = df_transferencias['Destino'].unique()
        
        # Análise de cidades únicas nos agentes
        origens_agentes = df_agentes['Origem'].unique()
        bases_origem = df_agentes['Base Origem'].dropna().unique()
        bases_destino = df_agentes['Base Destino'].dropna().unique()
        
        print("=== ANÁLISE DA BASE DE DADOS ===")
        print(f"Total transferências: {len(df_transferencias)}")
        print(f"Total agentes: {len(df_agentes)}")
        
        print("\n=== CIDADES EM TRANSFERÊNCIAS ===")
        print(f"Origens únicas: {len(origens_transf)}")
        print(f"Destinos únicas: {len(destinos_transf)}")
        
        # Buscar variações de Itajaí
        print("\n=== VARIAÇÕES DE ITAJAÍ ===")
        itajai_origens = [cidade for cidade in origens_transf if 'ITJ' in str(cidade).upper() or 'ITAJAI' in str(cidade).upper() or 'ITAJAY' in str(cidade).upper()]
        itajai_destinos = [cidade for cidade in destinos_transf if 'ITJ' in str(cidade).upper() or 'ITAJAI' in str(cidade).upper() or 'ITAJAY' in str(cidade).upper()]
        
        print(f"Itajaí como origem: {itajai_origens}")
        print(f"Itajaí como destino: {itajai_destinos}")
        
        # Buscar variações de Ribeirão Preto / RAO
        print("\n=== VARIAÇÕES DE RIBEIRÃO PRETO ===")
        rao_origens = [cidade for cidade in origens_transf if 'RAO' in str(cidade).upper() or 'RIBEIRAO' in str(cidade).upper()]
        rao_destinos = [cidade for cidade in destinos_transf if 'RAO' in str(cidade).upper() or 'RIBEIRAO' in str(cidade).upper()]
        
        print(f"Ribeirão Preto como origem: {rao_origens}")
        print(f"Ribeirão Preto como destino: {rao_destinos}")
        
        # Análise de bases dos agentes
        print("\n=== BASES DOS AGENTES ===")
        print(f"Bases origem únicas: {len(bases_origem)}")
        print(f"Bases destino únicas: {len(bases_destino)}")
        
        # Buscar agentes em Ribeirão Preto
        agentes_rp = df_agentes[df_agentes['Origem'].str.contains('RIBEIRAO|RAO', case=False, na=False)]
        print(f"\n=== AGENTES EM RIBEIRÃO PRETO ===")
        for _, agente in agentes_rp.iterrows():
            print(f"Fornecedor: {agente['Fornecedor']}, Origem: {agente['Origem']}, Base Origem: {agente.get('Base Origem', 'N/A')}, Base Destino: {agente.get('Base Destino', 'N/A')}")
        
        # Buscar transferências que saem de RAO, RP ou similares
        print(f"\n=== TRANSFERÊNCIAS DE RIBEIRÃO PRETO/RAO ===")
        transf_rp = df_transferencias[df_transferencias['Origem'].str.contains('RIBEIRAO|RAO|RP', case=False, na=False)]
        print(f"Total: {len(transf_rp)}")
        for _, transf in transf_rp.head(10).iterrows():
            print(f"Fornecedor: {transf['Fornecedor']}, Origem: {transf['Origem']}, Destino: {transf['Destino']}")
        
        # Buscar transferências que vão para ITJ, Itajaí ou similares
        print(f"\n=== TRANSFERÊNCIAS PARA ITAJAÍ/ITJ ===")
        transf_itj = df_transferencias[df_transferencias['Destino'].str.contains('ITJ|ITAJAI', case=False, na=False)]
        print(f"Total: {len(transf_itj)}")
        for _, transf in transf_itj.head(10).iterrows():
            print(f"Fornecedor: {transf['Fornecedor']}, Origem: {transf['Origem']}, Destino: {transf['Destino']}")
        
        # Criar mapeamento de estados
        print(f"\n=== MAPEAMENTO POR ESTADO ===")
        
        # SC (Santa Catarina)
        cidades_sc = [cidade for cidade in list(origens_transf) + list(destinos_transf) if any(indicador in str(cidade).upper() for indicador in ['ITJ', 'FLORIANOPOLIS', 'FLN', 'JOINVILLE', 'BLUMENAU', 'CHAPECO'])]
        print(f"SC: {list(set(cidades_sc))[:10]}")
        
        # SP (São Paulo)  
        cidades_sp = [cidade for cidade in list(origens_transf) + list(destinos_transf) if any(indicador in str(cidade).upper() for indicador in ['SAO PAULO', 'SP', 'CAMPINAS', 'RIBEIRAO', 'RAO', 'SANTOS', 'GUARULHOS'])]
        print(f"SP: {list(set(cidades_sp))[:10]}")
        
        return jsonify({
            'success': True,
            'transferencias': len(df_transferencias),
            'agentes': len(df_agentes),
            'itajai_destinos': itajai_destinos,
            'rao_origens': rao_origens,
            'agentes_rp': len(agentes_rp),
            'transf_itj': len(transf_itj)
        })
        
    except Exception as e:
        print(f"Erro na análise: {e}")
        return jsonify({'error': str(e)}), 500

def gerar_ranking_dedicado(custos, analise, rota_info, peso=0, cubagem=0, valor_nf=None):
    """
    Gera ranking das opções de frete dedicado no formato "all in"
    """
    try:
        # Preparar ranking das opções baseado nos custos
        ranking_opcoes = []
        
        # Ordenar custos por valor crescente
        custos_ordenados = sorted(custos.items(), key=lambda x: x[1])
        
        for i, (tipo_veiculo, custo) in enumerate(custos_ordenados, 1):
            # Determinar características do veículo
            if tipo_veiculo == "VAN":
                capacidade_info = {
                    'peso_max': '1.500kg',
                    'volume_max': '8m³',
                    'descricao': 'Veículo compacto para cargas leves'
                }
                icone_veiculo = "🚐"
            elif tipo_veiculo == "TRUCK":
                capacidade_info = {
                    'peso_max': '8.000kg', 
                    'volume_max': '25m³',
                    'descricao': 'Caminhão médio para cargas variadas'
                }
                icone_veiculo = "🚛"
            elif tipo_veiculo == "CARRETA":
                capacidade_info = {
                    'peso_max': '27.000kg',
                    'volume_max': '90m³', 
                    'descricao': 'Carreta para cargas pesadas'
                }
                icone_veiculo = "🚚"
            else:
                capacidade_info = {
                    'peso_max': 'Variável',
                    'volume_max': 'Variável',
                    'descricao': 'Veículo dedicado'
                }
                icone_veiculo = "🚛"
            
            # Determinar ícone da posição
            if i == 1:
                icone_posicao = "🥇"
            elif i == 2:
                icone_posicao = "🥈"
            elif i == 3:
                icone_posicao = "🥉"
            else:
                icone_posicao = f"{i}º"
            
            # Calcular prazo estimado baseado na distância
            distancia = analise.get('distancia', 500)
            prazo_estimado = max(1, int(distancia / 500)) # 1 dia para cada 500km
            
            # Calcular detalhamento de custos (estimativa)
            custo_base = custo * 0.70  # 70% do total
            combustivel = custo * 0.20  # 20% combustível
            pedagio = analise.get('pedagio_real', custo * 0.10)  # 10% pedágio ou valor real
            
            opcao_ranking = {
                'posicao': i,
                'icone': f"{icone_posicao} {icone_veiculo}",
                'tipo_servico': f"FRETE DEDICADO - {tipo_veiculo}",
                'fornecedor': 'Porto Express',
                'descricao': f"Frete dedicado com {tipo_veiculo.lower()} exclusivo",
                'custo_total': custo,
                'prazo': prazo_estimado,
                'peso_usado': f"{peso}kg" if peso else "Não informado",
                'capacidade': capacidade_info,
                'eh_melhor_opcao': (i == 1),
                
                # Detalhes expandidos
                'detalhes_expandidos': {
                    'custos_detalhados': {
                        'custo_base': round(custo_base, 2),
                        'combustivel': round(combustivel, 2),
                        'pedagio': round(pedagio, 2),
                        'outros': round(custo - custo_base - combustivel - pedagio, 2),
                        'total': custo
                    },
                    'rota_info': {
                        'origem': analise.get('origem', ''),
                        'destino': analise.get('destino', ''),
                        'distancia': analise.get('distancia', 0),
                        'tempo_viagem': analise.get('tempo_estimado', ''),
                        'pedagio_real': analise.get('pedagio_real', 0),
                        'consumo_estimado': analise.get('consumo_combustivel', 0),
                        'emissao_co2': analise.get('emissao_co2', 0)
                    },
                    'veiculo_info': {
                        'tipo': tipo_veiculo,
                        'capacidade_peso': capacidade_info['peso_max'],
                        'capacidade_volume': capacidade_info['volume_max'],
                        'descricao': capacidade_info['descricao']
                    }
                }
            }
            
            ranking_opcoes.append(opcao_ranking)
        
        # Informações consolidadas da cotação
        melhor_opcao = ranking_opcoes[0] if ranking_opcoes else None
        
        resultado_formatado = {
            'id_calculo': analise.get('id_historico', f"#Ded{len(ranking_opcoes):03d}"),
            'tipo_frete': 'Dedicado',
            'origem': analise.get('origem', ''),
            'destino': analise.get('destino', ''),
            'peso': peso,
            'cubagem': cubagem,
            'valor_nf': valor_nf,
            'distancia': analise.get('distancia', 0),
            'tempo_estimado': analise.get('tempo_estimado', ''),
            'consumo_estimado': analise.get('consumo_combustivel', 0),
            'emissao_co2': analise.get('emissao_co2', 0),
            'pedagio_real': analise.get('pedagio_real', 0),
            'pedagio_estimado': analise.get('pedagio_estimado', 0),
            'melhor_opcao': melhor_opcao,
            'ranking_opcoes': ranking_opcoes,
            'total_opcoes': len(ranking_opcoes),
            'data_calculo': analise.get('data_hora', ''),
            'provider': analise.get('provider', 'OSRM'),
            'rota_pontos': rota_info.get('rota_pontos', [])
        }
        
        return resultado_formatado
        
    except Exception as e:
        print(f"[RANKING DEDICADO] Erro ao gerar ranking: {e}")
        import traceback
        traceback.print_exc()
        return None

def calcular_peso_cubado_por_tipo(peso_real, cubagem, tipo_linha, fornecedor=None):
    """
    Calcula peso cubado aplicando fatores específicos por tipo de serviço:
    - Agentes (tipo 'Agente'): cubagem × 250
    - Transferências JEM e Concept: cubagem × 166
    """
    try:
        peso_real = float(peso_real)
        cubagem = float(cubagem) if cubagem else 0
        
        if cubagem <= 0:
            return peso_real
            
        # Aplicar fator específico baseado no tipo
        if tipo_linha == 'Agente':
            fator_cubagem = 250  # kg/m³ para agentes
            tipo_calculo = "Agente (250kg/m³)"
        elif tipo_linha == 'Transferência' and fornecedor and ('JEM'in str(fornecedor).upper() or 'CONCEPT' in str(fornecedor).upper()) or 'SOL' in str(fornecedor).upper():
            fator_cubagem = 166  # kg/m³ para JEM, Concept e SOL
            tipo_calculo = f"Transferência {fornecedor} (166kg/m³)"
            
        peso_cubado = cubagem * fator_cubagem
        peso_final = max(peso_real, peso_cubado)
        
        print(f"[PESO_CUBADO] {tipo_calculo}: {peso_real}kg vs {peso_cubado}kg = {peso_final}kg")
        return peso_final
        
    except Exception as e:
        print(f"[PESO_CUBADO] Erro no cálculo: {e}")
        return float(peso_real) if peso_real else 0

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)