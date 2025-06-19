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

# Carregar variáveis de ambiente
load_dotenv()

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
    if len(LOGS_SISTEMA) > 1000:
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
        print(f"[DEBUG] Sessão sem usuario_logado. Keys da sessão: {list(session.keys())}")
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
            print(f"[DEBUG] Sessão criada para {usuario}. Keys: {list(session.keys())}")
            
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
            return [lat, lon]
        return None
    except Exception as e:
        print(f"[geocode] Erro ao geocodificar {municipio}, {uf}: {e}")
        return None

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

def calcular_custos_dedicado(df, uf_origem, municipio_origem, uf_destino, municipio_destino, distancia, pedagio_real=0):
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
            print(f"[PEDÁGIO] Iniciando cálculo real de pedágios para {origem_nome} -> {destino_nome}")
            
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
@middleware_auth
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
@middleware_auth
def municipios(uf):
    try:
        response = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios")
        response.raise_for_status()
        data = response.json()
        municipios = [{"id": m["nome"], "text": m["nome"]} for m in data]
        return jsonify(sorted(municipios, key=lambda x: x["text"]))
    except Exception as e:
        print(f"Erro ao obter municípios de {uf}: {e}")
        return jsonify([])

@app.route("/historico")
@middleware_auth
def historico():
    return jsonify(HISTORICO_PESQUISAS)

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
        custos = calcular_custos_dedicado(df_unificado, uf_origem, municipio_origem, uf_destino, municipio_destino, rota_info["distancia"], pedagio_real)
        
        # Gerar análise final com custos atualizados
        analise = gerar_analise_trajeto(coord_origem, coord_destino, rota_info, custos, "Dedicado", municipio_origem, uf_origem, municipio_destino, uf_destino)
        ultimoResultadoDedicado = analise
        HISTORICO_PESQUISAS.append(analise)
        if len(HISTORICO_PESQUISAS) > 50:
            HISTORICO_PESQUISAS.pop(0)
        rota_pontos = rota_info.get("rota_pontos", [])
        print(f"[DEBUG] rota_pontos final: {rota_pontos}")
        if not isinstance(rota_pontos, list) or len(rota_pontos) == 0:
            rota_pontos = [coord_origem, coord_destino]
        for i, pt in enumerate(rota_pontos):
            if not isinstance(pt, list) or len(pt) < 2:
                rota_pontos[i] = [0, 0]
        resposta = {
            "distancia": rota_info["distancia"],
            "duracao": rota_info["duracao"],
            "custos": custos,
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
                "custos": custos
            }
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

        # Buscar dados aéreos da base GOLLOG
        df_aereo = ler_gollog_aereo()
        custos_aereo = {}
        
        if df_aereo is not None:
            # Filtrar por origem e destino
            uf_origem_norm = normalizar_uf(uf_origem)
            uf_destino_norm = normalizar_uf(uf_destino)
            cidade_origem_norm = normalizar_cidade(municipio_origem)
            cidade_destino_norm = normalizar_cidade(municipio_destino)
            
            opcoes_aereas = []
            for _, row in df_aereo.iterrows():
                if (normalizar_uf(row.get("uf_origem")) == uf_origem_norm and 
                    normalizar_cidade(row.get("cidade_origem")) == cidade_origem_norm and
                    normalizar_uf(row.get("uf_destino")) == uf_destino_norm and
                    normalizar_cidade(row.get("cidade_destino")) == cidade_destino_norm):
                    
                    # Calcular custo baseado no peso
                    peso_cubado = max(float(peso), float(cubagem) * 300)
                    custo_base = float(row.get("custo_base", 0))
                    
                    # Para modal aéreo, usar fórmula específica
                    if peso_cubado <= 5:
                        custo = custo_base
                    else:
                        # Taxa adicional por kg para modal aéreo
                        taxa_adicional = custo_base * 0.1  # 10% do valor base por kg adicional
                        custo = custo_base + (peso_cubado - 5) * taxa_adicional
                    
                    opcoes_aereas.append({
                        "modalidade": row.get("modalidade", "STANDARD"),
                        "tipo_servico": row.get("tipo_servico", "AEREO"),
                        "custo": round(custo, 2),
                        "prazo": int(row.get("prazo", 1))
                    })
            
            # Agrupar por modalidade
            for opcao in opcoes_aereas:
                modalidade = opcao["modalidade"]
                if modalidade not in custos_aereo:
                    custos_aereo[modalidade] = opcao["custo"]
                else:
                    # Manter o menor custo
                    custos_aereo[modalidade] = min(custos_aereo[modalidade], opcao["custo"])

        # Se não encontrou dados específicos, usar valores padrão
        if not custos_aereo:
            # Valores base para modal aéreo (por kg)
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
        if len(HISTORICO_PESQUISAS) > 50:
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
    global ultimoResultadoFracionado, CONTADOR_FRACIONADO
    ip_cliente = obter_ip_cliente()
    usuario = session.get('usuario_logado', 'DESCONHECIDO')
    
    try:
        # Extrair e validar dados do JSON
        data = request.get_json()
        uf_origem = data.get("estado_origem")
        cidade_origem = data.get("municipio_origem")
        uf_destino = data.get("estado_destino")
        cidade_destino = data.get("municipio_destino")
        peso = data.get("peso", 10)
        cubagem = data.get("cubagem", 0.05)
        valor_nf = data.get("valor_nf")  # Novo campo opcional

        log_acesso(usuario, 'CALCULO_FRACIONADO', ip_cliente, 
                  f"Cálculo Fracionado: {cidade_origem}/{uf_origem} -> {cidade_destino}/{uf_destino}, Peso: {peso}kg")

        if not all([uf_origem, cidade_origem, uf_destino, cidade_destino]):
            return jsonify({"error": "Todos os campos são obrigatórios."})

        # Definir peso real e peso cubado
        peso_real = float(peso)
        peso_cubado = float(cubagem) * 166  # Usando 166kg/m³ conforme regra da ANTT

        # USAR APENAS ROTAS COM AGENTES - SEM FRETES DIRETOS
        rotas_agentes = calcular_frete_com_agentes(
            cidade_origem, uf_origem,
            cidade_destino, uf_destino,
            peso, valor_nf, cubagem
        )

        if not rotas_agentes or rotas_agentes.get('total_opcoes', 0) == 0:
            return jsonify({
                "error": "Nenhuma rota com agentes encontrada para esta origem/destino. Sistema trabalha apenas com Agent Collection + Transfer + Agent Delivery."
            })

        # Pegar rotas com agentes
        cotacoes_ranking = rotas_agentes.get('rotas', [])
        
        if not cotacoes_ranking:
            return jsonify({
                "error": "Nenhuma rota válida com agentes encontrada"
            })

        # Melhor opção (menor custo)
        melhor_opcao = cotacoes_ranking[0] if cotacoes_ranking else {}

        # Incrementar contador
        CONTADOR_FRACIONADO += 1
        
        # ID do histórico
        id_historico = f"Fra{CONTADOR_FRACIONADO:03d}"

        # Identificar qual peso foi usado na melhor opção (rotas com agentes)
        maior_peso_usado = melhor_opcao.get('maior_peso', max(peso_real, peso_cubado))
        peso_usado_tipo = melhor_opcao.get('peso_usado', 'Real' if maior_peso_usado == peso_real else 'Cubado')

        # Criar resultado final apenas com dados REAIS
        resultado_final = {
            "id_historico": id_historico,
            "data_hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "origem": cidade_origem,
            "uf_origem": uf_origem,
            "destino": cidade_destino,
            "uf_destino": uf_destino,
            "peso": peso_real,
            "peso_cubado": peso_cubado,
            "maior_peso": maior_peso_usado,
            "peso_usado": peso_usado_tipo,
            "cubagem": cubagem,
            "valor_nf": valor_nf,
            "tipo_calculo": "Fracionado",
            
            # Informações do ranking COM AGENTES - SEM FRETES DIRETOS
            "cotacoes_ranking": cotacoes_ranking,  
            "ranking_completo": cotacoes_ranking,  
            "fornecedores_disponiveis": list(set(c.get('resumo', 'N/A') for c in cotacoes_ranking)),
            "total_opcoes": rotas_agentes['total_opcoes'],
            "fornecedores_count": len(set(c.get('resumo', 'N/A') for c in cotacoes_ranking)),
            "cotacoes_rejeitadas": 0,  # Sem simulações, sem rejeições
            "criterios_qualidade": "APENAS rotas com agentes: Agent Collection + Transfer + Agent Delivery",
            
            # Dados de rotas com agentes
            "rotas_agentes": rotas_agentes,
            "tem_rotas_agentes": True,
            
            # Melhor opção (rota com agentes)
            "fornecedor": melhor_opcao.get('resumo', 'N/A'),
            "agente": melhor_opcao.get('agente_coleta', {}).get('fornecedor', 'N/A'),
            "base_origem": melhor_opcao.get('agente_coleta', {}).get('origem', cidade_origem),
            "base_destino": melhor_opcao.get('agente_entrega', {}).get('destino', cidade_destino),
            "valor_base": melhor_opcao.get('total', 0),
            "pedagio": melhor_opcao.get('transferencia', {}).get('pedagio', 0),
            "gris": melhor_opcao.get('transferencia', {}).get('gris', 0),
            "custo_total": melhor_opcao.get('total', 0),
            "prazo_total": melhor_opcao.get('prazo_total', 1),
            "observacoes": melhor_opcao.get('observacoes', ''),
            
            # Fonte dos dados
                            "dados_fonte": "Frete Fracionado",
            "estrategia_busca": "AGENTES_REAL_APENAS",
            "cidades_origem": [cidade_origem],
            "cidades_destino": [cidade_destino],
            "rota_pontos": [],
            "distancia": 0,
            "detalhamento": f"Busca APENAS rotas com agentes reais - {len(cotacoes_ranking)} opções encontradas"
        }

        # Sem mapa na aba fracionado - dados vêm da planilha
        resultado_final["rota_pontos"] = []
        resultado_final["distancia"] = 0

        # Adicionar HTML formatado
        resultado_final["html"] = formatar_resultado_fracionado({
            'melhor_opcao': melhor_opcao,
            'cotacoes_ranking': cotacoes_ranking,
            'total_opcoes': rotas_agentes['total_opcoes'],
            'fornecedores_count': len(set(c.get('resumo', 'N/A') for c in cotacoes_ranking)),
            'dados_fonte': 'Frete Fracionado',
            'id_historico': id_historico,
            'cotacoes_rejeitadas': 0,
            'criterios_qualidade': 'Rotas com agentes reais',
            # Passar TODOS os dados necessários
            'origem': cidade_origem,
            'uf_origem': uf_origem,
            'destino': cidade_destino,
            'uf_destino': uf_destino,
            'peso': peso_real,
            'peso_cubado': peso_cubado,
            'cubagem': cubagem,
            'valor_nf': valor_nf,
            'estrategia_busca': "AGENTES_REAL_APENAS",
            # Dados de rotas com agentes
            'rotas_agentes': rotas_agentes
        })

        # Salvar no histórico
        ultimoResultadoFracionado = resultado_final

        # Adicionar ao histórico global
        HISTORICO_PESQUISAS.append({
            "id": id_historico,
            "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "tipo": "Fracionado",
            "origem": f"{cidade_origem}/{uf_origem}",
            "destino": f"{cidade_destino}/{uf_destino}",
            "peso": peso,
            "melhor_opcao": melhor_opcao.get('resumo', 'N/A'),
            "custo": melhor_opcao.get('total', 0),
            "resultado_completo": resultado_final
        })

        # Manter apenas os últimos 50 registros
        if len(HISTORICO_PESQUISAS) > 50:
            HISTORICO_PESQUISAS.pop(0)

        # Sanitizar dados antes de converter para JSON
        resultado_sanitizado = sanitizar_json(resultado_final)
        return jsonify(resultado_sanitizado)

    except Exception as e:
        log_acesso(usuario, 'ERRO_CALCULO_FRACIONADO', ip_cliente, f"Erro: {str(e)}")
        print(f"Erro ao calcular frete fracionado: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erro ao calcular frete fracionado: {str(e)}"})

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

@app.route("/gerar-pdf", methods=["POST"])
def gerar_pdf():
    try:
        import matplotlib
        matplotlib.use('Agg')  # Backend sem interface gráfica
        import matplotlib.pyplot as plt
        import io
        import datetime
        import json
        import os
        import tempfile
        
        # Tentar importar matplotlib para gráficos
        try:
            matplotlib.use('Agg')  # Backend sem interface gráfica
            import matplotlib.pyplot as plt
            matplotlib_available = True
        except ImportError:
            print("Matplotlib não disponível - gráficos não serão gerados")
            matplotlib_available = False
        
        dados = request.get_json()
        analise = dados.get("analise")
        pdf = FPDF()
        pdf.add_page()
        
        # Adicionar logo no cabeçalho
        logo_paths = [
            os.path.join(app.static_folder, 'portoex-logo.png'),
            os.path.join(os.path.dirname(__file__), 'static', 'portoex-logo.png'),
            'static/portoex-logo.png',
            'portoex-logo.png'
        ]
        
        logo_added = False
        for logo_path in logo_paths:
            if os.path.exists(logo_path):
                try:
                    # Posicionar logo no canto superior esquerdo
                    pdf.image(logo_path, x=10, y=10, w=30)  # x, y, largura
                    pdf.ln(25)  # Espaço após a logo
                    logo_added = True
                    print(f"Logo adicionada ao PDF de: {logo_path}")
                    break
                except Exception as e:
                    print(f"Erro ao adicionar logo de {logo_path}: {e}")
                    continue
        
        if not logo_added:
            print("Logo não pôde ser adicionada ao PDF")
            pdf.ln(10)  # Espaço sem logo
        
        # Função para limpar caracteres especiais para PDF
        def limpar_texto_pdf(texto):
            if not texto:
                return ""
            # Substituir caracteres especiais problemáticos
            replacements = {
                'ₓ': 'x',
                '₂': '2', 
                '₃': '3',
                'ᵒ': 'o',
                '°': 'graus',
                '²': '2',
                '³': '3',
                'µ': 'u',
                '–': '-',
                '—': '-',
                '"': '"',
                '"': '"',
                ''': "'",
                ''': "'",
                '…': '...'
            }
            for old, new in replacements.items():
                texto = str(texto).replace(old, new)
            return texto
        
        # Função para gerar gráfico de custos
        def gerar_grafico_custos(custos_dict):
            if not matplotlib_available:
                return None
            
            try:
                # Configurar o gráfico
                plt.figure(figsize=(8, 5))
                tipos = list(custos_dict.keys())
                valores = list(custos_dict.values())
                
                # Criar gráfico de barras
                bars = plt.bar(tipos, valores, color='#0a6ed1', alpha=0.8)
                
                # Adicionar valores nas barras
                for bar, valor in zip(bars, valores):
                    height = bar.get_height()
                    plt.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                            f'R$ {valor:.0f}', ha='center', va='bottom', fontsize=10)
                
                # Configurar títulos e labels
                plt.title('Custos por Tipo de Veículo', fontsize=14, fontweight='bold', pad=20)
                plt.xlabel('Tipo de Veículo', fontsize=12)
                plt.ylabel('Custo (R$)', fontsize=12)
                plt.xticks(rotation=45, ha='right')
                plt.grid(axis='y', alpha=0.3)
                plt.tight_layout()
                
                # Salvar em arquivo temporário
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                plt.savefig(temp_file.name, dpi=150, bbox_inches='tight')
                plt.close()
                
                return temp_file.name
            except Exception as e:
                print(f"Erro ao gerar gráfico: {e}")
                return None
        
        # Função para gerar mapa estático da rota
        def gerar_mapa_estatico(rota_pontos):
            if not rota_pontos or len(rota_pontos) < 2:
                return None
            
            try:
                # Calcular bounds da rota
                lats = [p[0] for p in rota_pontos]
                lngs = [p[1] for p in rota_pontos]
                
                min_lat, max_lat = min(lats), max(lats)
                min_lng, max_lng = min(lngs), max(lngs)
                
                # Adicionar margem
                margin = 0.1
                min_lat -= margin
                max_lat += margin
                min_lng -= margin
                max_lng += margin
                
                # Usar API de mapa estático (OpenStreetMap)
                # Como o OSM não tem API oficial de mapa estático, vamos usar uma alternativa
                
                # Opção 1: Usar MapBox Static API (requer token)
                # Opção 2: Usar uma imagem placeholder com informações da rota
                
                # Por enquanto, vamos gerar uma imagem simples com matplotlib
                if not matplotlib_available:
                    return None
                
                # Criar mapa simples com matplotlib
                plt.figure(figsize=(8, 6))
                
                # Plotar a rota
                lats_plot = [p[0] for p in rota_pontos]
                lngs_plot = [p[1] for p in rota_pontos]
                
                plt.plot(lngs_plot, lats_plot, 'b-', linewidth=2, label='Rota')
                
                # Marcar origem e destino
                plt.plot(lngs_plot[0], lats_plot[0], 'go', markersize=10, label='Origem')
                plt.plot(lngs_plot[-1], lats_plot[-1], 'ro', markersize=10, label='Destino')
                
                # Configurar o mapa
                plt.xlabel('Longitude')
                plt.ylabel('Latitude')
                plt.title('Mapa da Rota', fontsize=14, fontweight='bold')
                plt.grid(True, alpha=0.3)
                plt.legend()
                plt.axis('equal')
                
                # Definir limites
                plt.xlim(min_lng, max_lng)
                plt.ylim(min_lat, max_lat)
                
                plt.tight_layout()
                
                # Salvar em arquivo temporário
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                plt.savefig(temp_file.name, dpi=150, bbox_inches='tight')
                plt.close()
                
                return temp_file.name
                
            except Exception as e:
                print(f"Erro ao gerar mapa estático: {e}")
                return None
        
        # Cabeçalho
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 12, "PortoEx - Relatório de Frete", 0, 1, "C")
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 0, 1)
        pdf.ln(5)
        
        # Dados principais
        if analise:
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, limpar_texto_pdf(f"ID: {analise.get('id_historico', 'N/A')} - Tipo: {analise.get('tipo', 'N/A')}"), 0, 1)
            pdf.ln(3)
            
            # === SEÇÃO: INFORMAÇÕES BÁSICAS ===
            pdf.set_font("Arial", "B", 12)
            pdf.set_fill_color(240, 248, 255)  # Fundo azul claro
            pdf.cell(0, 8, "INFORMAÇÕES BÁSICAS", 0, 1, "L", True)
            pdf.ln(2)
            
            pdf.set_font("Arial", "", 11)
            origem = limpar_texto_pdf(analise.get("origem", "N/A"))
            destino = limpar_texto_pdf(analise.get("destino", "N/A"))
            
            pdf.cell(0, 6, f"Origem: {origem}", 0, 1)
            pdf.cell(0, 6, f"Destino: {destino}", 0, 1)
            pdf.cell(0, 6, limpar_texto_pdf(f"Distância: {analise.get('distancia', 'N/A')} km"), 0, 1)
            
            if analise.get("tempo_estimado"):
                pdf.cell(0, 6, limpar_texto_pdf(f"Tempo estimado: {analise.get('tempo_estimado')}"), 0, 1)
            if analise.get("peso"):
                pdf.cell(0, 6, limpar_texto_pdf(f"Peso: {analise.get('peso')} kg"), 0, 1)
            if analise.get("cubagem"):
                pdf.cell(0, 6, limpar_texto_pdf(f"Cubagem: {analise.get('cubagem')} m³"), 0, 1)
            
            pdf.ln(5)
            
            # === SEÇÃO: ANÁLISE DA ROTA ===
            pdf.set_font("Arial", "B", 12)
            pdf.set_fill_color(240, 248, 255)
            pdf.cell(0, 8, "ANÁLISE DA ROTA", 0, 1, "L", True)
            pdf.ln(2)
            
            pdf.set_font("Arial", "", 11)
            if analise.get("consumo_combustivel"):
                pdf.cell(0, 6, limpar_texto_pdf(f"Consumo estimado de combustível: {analise.get('consumo_combustivel')} L"), 0, 1)
            if analise.get("emissao_co2"):
                pdf.cell(0, 6, limpar_texto_pdf(f"Emissão de CO2: {analise.get('emissao_co2')} kg"), 0, 1)
            if analise.get("pedagio_estimado"):
                pdf.cell(0, 6, limpar_texto_pdf(f"Pedágio estimado: R$ {analise.get('pedagio_estimado')}"), 0, 1)
            if analise.get("provider"):
                pdf.cell(0, 6, limpar_texto_pdf(f"Provedor de rota: {analise.get('provider')}"), 0, 1)
            if analise.get("duracao_minutos"):
                horas = int(analise.get("duracao_minutos", 0) / 60)
                minutos = int(analise.get("duracao_minutos", 0) % 60)
                pdf.cell(0, 6, limpar_texto_pdf(f"Duração da viagem: {horas}h {minutos}min"), 0, 1)
            
            pdf.ln(5)
            
            # === SEÇÃO: TABELA DE CUSTOS ===
            custos = analise.get("custos")
            if custos:
                pdf.set_font("Arial", "B", 12)
                pdf.set_fill_color(240, 248, 255)
                pdf.cell(0, 8, "CUSTOS POR TIPO DE VEÍCULO", 0, 1, "L", True)
                pdf.ln(2)
                
                # Cabeçalho da tabela
                pdf.set_font("Arial", "B", 10)
                pdf.set_fill_color(220, 220, 220)
                pdf.cell(60, 8, "Tipo de Veículo", 1, 0, "C", True)
                pdf.cell(40, 8, "Custo (R$)", 1, 0, "C", True)
                pdf.cell(50, 8, "Custo por km (R$)", 1, 1, "C", True)
                
                # Dados da tabela
                pdf.set_font("Arial", "", 10)
                distancia = analise.get('distancia', 1)
                for tipo, valor in custos.items():
                    custo_km = valor / distancia if distancia > 0 else 0
                    pdf.cell(60, 7, limpar_texto_pdf(str(tipo)), 1, 0, "L")
                    pdf.cell(40, 7, limpar_texto_pdf(f"R$ {valor:.2f}"), 1, 0, "C")
                    pdf.cell(50, 7, limpar_texto_pdf(f"R$ {custo_km:.2f}"), 1, 1, "C")
                
                pdf.ln(5)
                
                # === SEÇÃO: ANÁLISE DE CUSTOS ===
                pdf.set_font("Arial", "B", 12)
                pdf.set_fill_color(240, 248, 255)
                pdf.cell(0, 8, "ANÁLISE DE CUSTOS", 0, 1, "L", True)
                pdf.ln(2)
                
                pdf.set_font("Arial", "", 11)
                valores = list(custos.values())
                menor_custo = min(valores)
                maior_custo = max(valores)
                custo_medio = sum(valores) / len(valores)
                
                tipo_menor = [k for k, v in custos.items() if v == menor_custo][0]
                tipo_maior = [k for k, v in custos.items() if v == maior_custo][0]
                
                pdf.cell(0, 6, limpar_texto_pdf(f"Opção mais econômica: {tipo_menor} - R$ {menor_custo:.2f}"), 0, 1)
                pdf.cell(0, 6, limpar_texto_pdf(f"Opção mais cara: {tipo_maior} - R$ {maior_custo:.2f}"), 0, 1)
                pdf.cell(0, 6, limpar_texto_pdf(f"Custo médio: R$ {custo_medio:.2f}"), 0, 1)
                diferenca = maior_custo - menor_custo
                pdf.cell(0, 6, limpar_texto_pdf(f"Diferença entre maior e menor: R$ {diferenca:.2f}"), 0, 1)
                
                pdf.ln(5)
        else:
            pdf.cell(0, 10, "Nenhum dado disponível", 0, 1)
        
        # === ESPAÇO PARA GRÁFICO (será implementado) ===
        pdf.set_font("Arial", "B", 12)
        pdf.set_fill_color(240, 248, 255)
        pdf.cell(0, 8, "GRÁFICO DE CUSTOS", 0, 1, "L", True)
        pdf.ln(2)
        
        # Gerar e inserir gráfico se houver custos
        if analise and analise.get("custos") and matplotlib_available:
            grafico_path = gerar_grafico_custos(analise.get("custos"))
            if grafico_path:
                try:
                    # Inserir gráfico no PDF
                    pdf.image(grafico_path, x=15, w=180)  # Centralizado, largura 180mm
                    pdf.ln(10)
                    # Limpar arquivo temporário
                    os.unlink(grafico_path)
                except Exception as e:
                    print(f"Erro ao inserir gráfico no PDF: {e}")
                    pdf.set_font("Arial", "", 11)
                    pdf.cell(0, 6, "Erro ao gerar gráfico", 0, 1)
            else:
                pdf.set_font("Arial", "", 11)
                pdf.cell(0, 6, "Não foi possível gerar o gráfico", 0, 1)
        else:
            pdf.set_font("Arial", "", 11)
            if not matplotlib_available:
                pdf.cell(0, 6, "Matplotlib não disponível - instale com: pip install matplotlib", 0, 1)
            else:
                pdf.cell(0, 6, "Nenhum dado de custos disponível para gráfico", 0, 1)
        
        pdf.ln(10)
        
        # === ESPAÇO PARA MAPA (será implementado) ===
        pdf.set_font("Arial", "B", 12)
        pdf.set_fill_color(240, 248, 255)
        pdf.cell(0, 8, "MAPA DA ROTA", 0, 1, "L", True)
        pdf.ln(2)
        
        # Gerar e inserir mapa se houver pontos de rota
        if analise and analise.get("rota_pontos") and matplotlib_available:
            mapa_path = gerar_mapa_estatico(analise.get("rota_pontos"))
            if mapa_path:
                try:
                    # Inserir mapa no PDF
                    pdf.image(mapa_path, x=15, w=180)  # Centralizado, largura 180mm
                    pdf.ln(5)
                    # Limpar arquivo temporário
                    os.unlink(mapa_path)
                    
                    # Adicionar informações sobre o mapa
                    pdf.set_font("Arial", "", 9)
                    rota_pontos = analise.get("rota_pontos", [])
                    pdf.cell(0, 4, f"Pontos na rota: {len(rota_pontos)}", 0, 1)
                    if len(rota_pontos) >= 2:
                        origem_lat, origem_lng = rota_pontos[0]
                        destino_lat, destino_lng = rota_pontos[-1]
                        pdf.cell(0, 4, f"Origem: {origem_lat:.4f}, {origem_lng:.4f}", 0, 1)
                        pdf.cell(0, 4, f"Destino: {destino_lat:.4f}, {destino_lng:.4f}", 0, 1)
                        
                except Exception as e:
                    print(f"Erro ao inserir mapa no PDF: {e}")
                    pdf.set_font("Arial", "", 11)
                    pdf.cell(0, 6, "Erro ao gerar mapa", 0, 1)
            else:
                pdf.set_font("Arial", "", 11)
                pdf.cell(0, 6, "Não foi possível gerar o mapa", 0, 1)
        else:
            pdf.set_font("Arial", "", 11)
            if not matplotlib_available:
                pdf.cell(0, 6, "Matplotlib não disponível - instale com: pip install matplotlib", 0, 1)
            elif not analise or not analise.get("rota_pontos"):
                pdf.cell(0, 6, "Nenhum dado de rota disponível para o mapa", 0, 1)
            else:
                pdf.cell(0, 6, "Dados de rota insuficientes para gerar mapa", 0, 1)
        
        pdf_bytes = pdf.output(dest="S").encode("latin-1")
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
    Usando dados médios de pedágios por km no Brasil
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
    Versão melhorada do OpenRouteService para obter polyline detalhada
    """
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {
            "Authorization": OPENROUTE_API_KEY
        }
        params = {
            "start": f"{origem[1]},{origem[0]}",
            "end": f"{destino[1]},{destino[0]}",
            "format": "json",
            "geometry_format": "polyline"
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if "features" in data and data["features"]:
                route = data["features"][0]
                properties = route.get("properties", {})
                segments = properties.get("segments", [{}])[0]
                
                distance = segments.get("distance", 0)
                duration = segments.get("duration", 0)
                
                # Obter polyline da geometria
                geometry = route.get("geometry")
                polyline = None
                route_points = []
                
                if geometry:
                    if isinstance(geometry, str):
                        polyline = geometry
                    elif isinstance(geometry, dict) and geometry.get("coordinates"):
                        # Converter coordenadas para polyline
                        coords = geometry["coordinates"]
                        route_points = [[coord[1], coord[0]] for coord in coords]
                        
                        # Para TollGuru, precisamos de polyline codificada
                        try:
                            import polyline as polyline_lib
                            polyline = polyline_lib.encode(route_points)
                        except ImportError:
                            # Fallback simples se polyline lib não disponível
                            polyline = f"polyline_points_{len(route_points)}"
                
                return {
                    "distancia": distance / 1000,
                    "duracao": duration / 60,
                    "polyline": polyline,
                    "rota_pontos": route_points,
                    "provider": "OpenRouteService"
                }
        
        return None
        
    except Exception as e:
        print(f"[OPENROUTE] Erro: {e}")
        return None

def carregar_base_completa():
    """
    Carrega a base completa SEM filtrar registros com Destino vazio (necessário para Agentes)
    """
    debug = os.getenv('DEBUG_AGENTES', 'false').lower() == 'true'
    
    if not BASE_UNIFICADA_FILE:
        if debug:
            print("[AGENTES] Erro: BASE_UNIFICADA_FILE não está definido")
        return None
    
    if not os.path.exists(BASE_UNIFICADA_FILE):
        if debug:
            print(f"[AGENTES] Erro: Arquivo não encontrado: {BASE_UNIFICADA_FILE}")
            print(f"[AGENTES] Diretório atual: {os.getcwd()}")
            print("[AGENTES] Conteúdo do diretório:")
            for f in os.listdir('.'):
                print(f"- {f} (dir: {os.path.isdir(f)})")
        return None
    
    try:
        if debug:
            print(f"[AGENTES] Tentando carregar arquivo: {BASE_UNIFICADA_FILE}")
            
        # Tenta ler o arquivo Excel
        df_base = pd.read_excel(BASE_UNIFICADA_FILE)
        
        if debug:
            print(f"[AGENTES] Base carregada com sucesso. Total de registros: {len(df_base)}")
            if len(df_base) > 0:
                print("[AGENTES] Primeiras colunas:", ", ".join([str(col) for col in df_base.columns.tolist()[:10]]))
            else:
                print("[AGENTES] Aviso: A base está vazia")
        
        return df_base
        
    except Exception as e:
        if debug:
            print(f"[AGENTES] Erro ao carregar o arquivo Excel: {str(e)}")
            import traceback
            traceback.print_exc()
        return None
        return None

# Cache para armazenar a base de dados carregada
_BASE_AGENTES_CACHE = None
_ULTIMO_CARREGAMENTO = 0
_CACHE_VALIDADE = 300  # 5 minutos em segundos

def carregar_base_agentes():
    """
    Carrega a base de agentes com cache para evitar leitura repetida do arquivo
    """
    global _BASE_AGENTES_CACHE, _ULTIMO_CARREGAMENTO
    
    agora = time.time()
    
    # Se o cache ainda é válido, retorna os dados em cache
    if _BASE_AGENTES_CACHE is not None and (agora - _ULTIMO_CARREGAMENTO) < _CACHE_VALIDADE:
        if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
            print("[AGENTES] Retornando dados do cache")
        return _BASE_AGENTES_CACHE
    
    if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
        print("[AGENTES] Carregando base de agentes...")
    
    # Se não, carrega os dados
    df_base = carregar_base_completa()
    if df_base is None:
        if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
            print("[AGENTES] Erro: Não foi possível carregar a base completa")
        return None
    
    # Verifica se as colunas necessárias existem
    colunas_necessarias = ['Tipo', 'Origem']
    colunas_faltando = [col for col in colunas_necessarias if col not in df_base.columns]
    
    if colunas_faltando:
        if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
            print(f"[AGENTES] Erro: Colunas faltando na base: {', '.join(colunas_faltando)}")
            print(f"[AGENTES] Colunas disponíveis: {', '.join(df_base.columns)}")
        return None
    
    # Processa os dados uma única vez
    try:
        df_agentes = df_base[df_base['Tipo'] == 'Agente'].copy()
        df_transferencias = df_base[df_base['Tipo'] == 'Transferência'].copy()
        
        if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
            print(f"[AGENTES] {len(df_agentes)} agentes e {len(df_transferencias)} transferências carregados")
        
        # Pré-processa os dados para melhor performance
        df_agentes['Origem_Normalizada'] = df_agentes['Origem'].apply(normalizar_cidade)
        
        # Atualiza o cache
        _BASE_AGENTES_CACHE = (df_agentes, df_transferencias)
        _ULTIMO_CARREGAMENTO = agora
        
        if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
            print("[AGENTES] Base de agentes carregada com sucesso")
            
        return _BASE_AGENTES_CACHE
        
    except Exception as e:
        if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
            print(f"[AGENTES] Erro ao processar base de agentes: {str(e)}")
        return None
    
    return _BASE_AGENTES_CACHE

# Cache para mapeamento de cidades para bases
MAPA_BASES_CACHE = {
    'SAO PAULO': 'SAO',
    'ARACAJU': 'AJU', 
    'CAMPINAS': 'CPQ',
    'BRASILIA': 'BSB',
    'BELO HORIZONTE': 'BHZ',
    'RIO DE JANEIRO': 'RIO',
    'CURITIBA': 'CWB',
    'PORTO ALEGRE': 'POA'
}

def calcular_frete_com_agentes(origem, uf_origem, destino, uf_destino, peso, valor_nf=None, cubagem=None, base_filtro=None):
    """
    Calcula frete com sistema de agentes: Coleta -> Transferência -> Entrega
    Estrutura CORRETA: Agente Coleta (Cliente → Base) + Transferência (Base → Base) + Agente Entrega (Base → Cliente)
    Exemplo: Agente busca no cliente e leva até RAO (R$ 124,50) + RAO → RIO direto (R$ 345,77) + Agente entrega da base RIO até cliente final (R$ 60,00)
    """
    print(f"[AGENTES] Calculando rotas com agentes: {origem}/{uf_origem} → {destino}/{uf_destino}")
    print(f"[AGENTES] Peso: {peso}kg, Base filtro: {base_filtro}")
    
    try:
        # Carregar base unificada para usar dados reais de transferência
        df_base = carregar_base_unificada()
        if df_base is None:
            print("[AGENTES] Erro: Não foi possível carregar a base de dados")
            return None

        # Carregar base de agentes reais
        dados_agentes = carregar_base_agentes()
        if dados_agentes is None:
            print("[AGENTES] Erro: Não foi possível carregar a base de agentes")
            return None
        
        # Desempacotar os dados retornados pela função
        df_agentes, df_transferencias = dados_agentes
        
        # Calcular peso cubado
        peso_real = float(peso)
        peso_cubado = float(cubagem) * 166 if cubagem and cubagem > 0 else peso_real * 0.17
        maior_peso = max(peso_real, peso_cubado)
        
        # Definir bases disponíveis (conforme especificado pelo usuário)
        bases_disponiveis = {
            'FILIAL': 'São Paulo',        # Base real na planilha - SOMENTE São Paulo Capital
            'RAO': 'Ribeirão Preto',      # Base real na planilha - Ribeirão Preto
            'MII': 'Minas Gerais',       # Base real na planilha  
            'SJK': 'São José dos Campos', # Base real na planilha
            'RIO': 'Rio de Janeiro',      # Base real na planilha
            'POA': 'Porto Alegre',       # Para cidades do RS
            'CWB': 'Curitiba',           # Para cidades do PR
            'BHZ': 'Belo Horizonte',     # Para cidades de MG
            'BSB': 'Brasília',           # Para cidades do DF
            'GYN': 'Goiânia',            # Para cidades de GO - NOVA BASE
            'SSA': 'Salvador',           # Para cidades da BA
            'FOR': 'Fortaleza',          # Para cidades do CE
            'REC': 'Recife',             # Para cidades de PE
            'NAT': 'Natal',              # Para cidades do RN
            'JPA': 'João Pessoa',        # Para cidades da PB
            'MCZ': 'Maceió',             # Para cidades de AL
            'AJU': 'Aracaju',            # Para cidades de SE
            'SLZ': 'São Luís',           # Para cidades do MA
            'THE': 'Teresina',           # Para cidades do PI
            'CGB': 'Cuiabá',             # Para cidades de MT
            'CGR': 'Campo Grande',       # Para cidades de MS
            'VIX': 'Vitória',            # Para cidades do ES
            'MAO': 'Manaus',             # Para cidades do AM
            'MAB': 'Marabá',             # Para cidades do PA
            'PMW': 'Palmas'              # Para cidades do TO
        }
        
        # Determinar base de origem baseada na UF de origem ou filtro especificado
        if base_filtro and base_filtro in bases_disponiveis:
            base_origem = base_filtro
        else:
            # Mapear UF para base mais próxima usando códigos reais da planilha
            if uf_origem == 'SP':
                # São Paulo: FILIAL só atende São Paulo Capital, RAO atende Ribeirão Preto
                origem_normalizada = normalizar_cidade(origem)
                if origem_normalizada == 'SAO PAULO':
                    base_origem = 'FILIAL'  # São Paulo Capital usa FILIAL
                elif origem_normalizada == 'RIBEIRAO PRETO':
                    base_origem = 'RAO'     # Ribeirão Preto usa RAO
                else:
                    base_origem = 'FILIAL'  # Outras cidades SP usam FILIAL como padrão
            else:
                mapa_uf_base = {
                    'RJ': 'RIO',
                    'MG': 'BHZ',     # Minas Gerais usa BHZ (Belo Horizonte) - CORRIGIDO  
                    'RS': 'POA',
                    'PR': 'CWB',
                    'DF': 'BSB',
                    'GO': 'GYN',     # Goiás usa GYN (Goiânia) - CORRIGIDO
                    'BA': 'SSA',
                    'CE': 'FOR',
                    'PE': 'REC',
                    'RN': 'NAT',     # Rio Grande do Norte
                    'PB': 'JPA',     # Paraíba
                    'AL': 'MCZ',     # Alagoas
                    'SE': 'AJU',     # Sergipe
                    'MA': 'SLZ',     # Maranhão
                    'PI': 'THE',     # Piauí
                    'MT': 'CGB',     # Mato Grosso
                    'MS': 'CGR',     # Mato Grosso do Sul
                    'ES': 'VIX',     # Espírito Santo
                    'AM': 'MAO',     # Amazonas
                    'PA': 'MAB',     # Pará
                    'TO': 'PMW'      # Tocantins
                }
                base_origem = mapa_uf_base.get(uf_origem, 'FILIAL')  # Default para FILIAL
        
        # Determinar base de destino baseada na UF de destino usando códigos reais
        if uf_destino == 'SP':
            # São Paulo: FILIAL só atende São Paulo Capital, RAO atende Ribeirão Preto
            destino_normalizado = normalizar_cidade(destino)
            if destino_normalizado == 'SAO PAULO':
                base_destino = 'FILIAL'  # São Paulo Capital usa FILIAL
            elif destino_normalizado == 'RIBEIRAO PRETO':
                base_destino = 'RAO'     # Ribeirão Preto usa RAO
            else:
                base_destino = 'FILIAL'  # Outras cidades SP usam FILIAL como padrão
        else:
            mapa_uf_base = {
                'RJ': 'RIO',
                'MG': 'BHZ',     # Minas Gerais usa BHZ (Belo Horizonte) - CORRIGIDO
                'RS': 'POA',
                'PR': 'CWB',
                'DF': 'BSB',
                'GO': 'GYN',     # Goiás usa GYN (Goiânia) - CORRIGIDO
                'BA': 'SSA',
                'CE': 'FOR',
                'PE': 'REC',
                'RN': 'NAT',     # Rio Grande do Norte
                'PB': 'JPA',     # Paraíba
                'AL': 'MCZ',     # Alagoas
                'SE': 'AJU',     # Sergipe
                'MA': 'SLZ',     # Maranhão
                'PI': 'THE',     # Piauí
                'MT': 'CGB',     # Mato Grosso
                'MS': 'CGR',     # Mato Grosso do Sul
                'ES': 'VIX',     # Espírito Santo
                'AM': 'MAO',     # Amazonas
                'PA': 'MAB',     # Pará
                'TO': 'PMW'      # Tocantins
            }
            base_destino = mapa_uf_base.get(uf_destino, 'RIO')  # Default para RIO
        
        print(f"[AGENTES] Base origem: {base_origem} ({bases_disponiveis.get(base_origem)})")
        print(f"[AGENTES] Base destino: {base_destino} ({bases_disponiveis.get(base_destino)})")
        
        # Debug: verificar se RAO e FILIAL estão sendo usados corretamente
        if base_origem == 'FILIAL':
            print(f"[AGENTES] ✅ FILIAL sendo usada para origem: {origem} (São Paulo Capital)")
        elif base_origem == 'RAO':
            print(f"[AGENTES] ✅ RAO sendo usada para origem: {origem} (Ribeirão Preto)")
        
        if base_destino == 'FILIAL':
            print(f"[AGENTES] ✅ FILIAL sendo usada para destino: {destino} (São Paulo Capital)")
        elif base_destino == 'RAO':
            print(f"[AGENTES] ✅ RAO sendo usada para destino: {destino} (Ribeirão Preto)")
        
        rotas_encontradas = []
        
        # Se origem e destino são da mesma base, não usar agente (usar direto)
        if base_origem == base_destino:
            print(f"[AGENTES] Origem e destino na mesma base ({base_origem}), usando transferência direta")
            return None
        
        # 1. BUSCAR TRANSFERÊNCIA ENTRE BASES NA PLANILHA REAL
        transferencias_encontradas = []
        
        # Usar dados de transferência do cache
        transferencias_base = df_transferencias.copy()
        
        # Filtrar transferências diretas entre as bases na planilha
        origem_base = bases_disponiveis.get(base_origem, '')
        destino_base = bases_disponiveis.get(base_destino, '')
        
        # Normalizar nomes das bases para busca
        origem_base_norm = normalizar_cidade(origem_base)
        destino_base_norm = normalizar_cidade(destino_base)
        
        print(f"[AGENTES] Buscando transferência: {origem_base_norm} → {destino_base_norm}")
        
        # Normalizar colunas para busca
        transferencias_base['Origem_Normalizada'] = transferencias_base['Origem'].apply(normalizar_cidade)
        transferencias_base['Destino_Normalizado'] = transferencias_base['Destino'].apply(normalizar_cidade)
        
        # Buscar correspondência entre bases
        matches_transferencia = transferencias_base[
            (transferencias_base['Origem_Normalizada'] == origem_base_norm) &
            (transferencias_base['Destino_Normalizado'] == destino_base_norm)
        ]
        
        if matches_transferencia.empty:
            # Tentar busca mais flexível
            matches_transferencia = transferencias_base[
                (transferencias_base['Origem_Normalizada'].str.contains(origem_base_norm[:3], case=False, na=False)) &
                (transferencias_base['Destino_Normalizado'].str.contains(destino_base_norm[:3], case=False, na=False))
            ]
        
        print(f"[AGENTES] Transferências encontradas: {len(matches_transferencia)} registros")
        
        # Processar transferências encontradas
        for _, linha_trans in matches_transferencia.iterrows():
            try:
                linha_processada = processar_linha_transferencia(linha_trans, maior_peso, valor_nf)
                if linha_processada:
                    transferencias_encontradas.append(linha_processada)
                    print(f"[AGENTES] ✅ Transferência: {linha_trans.get('Fornecedor')} - {origem_base} → {destino_base} - R$ {linha_processada['custo']:.2f}")
                
            except Exception as e:
                print(f"[AGENTES] Erro ao processar transferência: {e}")
                continue
        
        # 2. BUSCAR AGENTES REAIS NA BASE DE DADOS
        # Verificar se df_agentes foi carregado corretamente
        if df_agentes is None or df_agentes.empty:
            print("[AGENTES] Base de agentes vazia ou não carregada")
            return None
        
        print(f"[AGENTES] Colunas disponíveis na base de agentes: {list(df_agentes.columns)}")
        
        # NOVA LÓGICA: Agentes fazem coleta/entrega entre cidade do cliente e base
        # Agentes de COLETA: buscam na cidade de origem e levam para a base de origem
        origem_normalizada = normalizar_cidade(origem)
        agentes_coleta = df_agentes[
            (df_agentes['Tipo'] == 'Agente') &
            (df_agentes['Base Origem'] == base_origem) &
            (df_agentes['Origem_Normalizada'] == origem_normalizada)
        ]
        
        # Agentes de ENTREGA: saem da base de destino e entregam na cidade de destino
        destino_normalizado = normalizar_cidade(destino)
        agentes_entrega = df_agentes[
            (df_agentes['Tipo'] == 'Agente') &
            (df_agentes['Base Origem'] == base_destino) &
            (df_agentes['Origem_Normalizada'] == destino_normalizado)
        ]
        
        print(f"[AGENTES] Agentes de coleta encontrados: {len(agentes_coleta)}")
        print(f"[AGENTES] Agentes de entrega encontrados: {len(agentes_entrega)}")
        
        # 3. COMBINAR COLETA + TRANSFERÊNCIA + ENTREGA COM DADOS REAIS
        for _, agente_col in agentes_coleta.iterrows():
            for transferencia in transferencias_encontradas:
                for _, agente_ent in agentes_entrega.iterrows():
                    try:
                        # Calcular custos da coleta usando dados reais
                        linha_coleta_processada = processar_linha_transferencia(agente_col, maior_peso, valor_nf)
                        if not linha_coleta_processada:
                            continue
                            
                        # Calcular custos da entrega usando dados reais
                        linha_entrega_processada = processar_linha_transferencia(agente_ent, maior_peso, valor_nf)
                        if not linha_entrega_processada:
                            continue
                        
                        # TOTAL DA ROTA: COLETA + TRANSFERÊNCIA + ENTREGA
                        total_rota = (linha_coleta_processada['custo'] + linha_coleta_processada['pedagio'] + linha_coleta_processada['gris'] +
                                    transferencia['custo'] + transferencia['pedagio'] + transferencia['gris'] +
                                    linha_entrega_processada['custo'] + linha_entrega_processada['pedagio'] + linha_entrega_processada['gris'])
                        
                        # Prazo total (soma dos prazos)
                        prazo_total = (linha_coleta_processada['prazo'] + transferencia['prazo'] + linha_entrega_processada['prazo'])
                        
                        # Criar rota completa
                        rota = {
                            'fornecedor_coleta': agente_col.get('Fornecedor', 'N/A'),
                            'fornecedor_transferencia': transferencia['fornecedor'],
                            'agente_entrega': {'fornecedor': agente_ent.get('Fornecedor', 'N/A')},
                            'agente_coleta': {
                                'base_origem': origem,
                                'base_destino': base_origem,
                                'custo': float(linha_coleta_processada['custo']),
                                'origem': agente_col.get('Origem', ''),
                                'destino': agente_col.get('Destino', ''),
                                'fornecedor': agente_col.get('Fornecedor', 'N/A')
                            },
                            'transferencia': {
                                'base_origem': base_origem,
                                'base_destino': base_destino,
                                'custo': float(transferencia['custo']),
                                'pedagio': float(transferencia['pedagio']),
                                'gris': float(transferencia['gris']),
                                'fornecedor': transferencia['fornecedor'],
                                'origem': f"Base {base_origem}",
                                'destino': f"Base {base_destino}",
                                'frete': float(transferencia['custo']) - float(transferencia['pedagio']) - float(transferencia['gris'])
                            },
                            'agente_entrega_detalhes': {
                                'base_origem': base_destino,
                                'base_destino': destino,
                                'custo': float(linha_entrega_processada['custo']),
                                'origem': agente_ent.get('Origem', ''),
                                'destino': agente_ent.get('Destino', ''),
                                'fornecedor': agente_ent.get('Fornecedor', 'N/A')
                            },
                            'agente_entrega': {
                                'fornecedor': agente_ent.get('Fornecedor', 'N/A'),
                                'base_origem': base_destino,
                                'destino': destino,
                                'custo': float(linha_entrega_processada['custo']),
                                'valor_minimo': 0.0,  # Será implementado na nova lógica
                                'excedente': 0.0      # Será implementado na nova lógica
                            },
                            'total': float(total_rota),
                            'prazo_total': int(prazo_total),
                            'peso_real': float(peso_real),
                            'peso_cubado': float(peso_cubado),
                            'maior_peso': float(maior_peso),
                            'peso_usado': 'Cubado' if maior_peso == peso_cubado else 'Real',
                            'base_origem': base_origem,
                            'base_destino_transferencia': base_destino,
                            'resumo': f"{agente_col.get('Fornecedor', 'N/A')} + {transferencia['fornecedor']} + {agente_ent.get('Fornecedor', 'N/A')}",
                            'detalhamento_custos': {
                                'coleta': float(linha_coleta_processada['custo']),
                                'transferencia': float(transferencia['custo']),
                                'entrega': float(linha_entrega_processada['custo']),
                                'pedagio': float(linha_coleta_processada['pedagio'] + transferencia['pedagio'] + linha_entrega_processada['pedagio']),
                                'gris_total': float(linha_coleta_processada['gris'] + transferencia['gris'] + linha_entrega_processada['gris'])
                            }
                        }
                        
                        # Implementar nova lógica de cálculo para agentes
                        # Adicionar valores mínimo e excedente para coleta e entrega
                        valor_minimo_coleta = float(agente_col.get('VALOR MÍNIMO ATÉ 10', 0) or 0)
                        excedente_coleta = float(agente_col.get('EXCEDENTE', 0) or 0)
                        valor_minimo_entrega = float(agente_ent.get('VALOR MÍNIMO ATÉ 10', 0) or 0)
                        excedente_entrega = float(agente_ent.get('EXCEDENTE', 0) or 0)
                        
                        # Atualizar dados de coleta e entrega com nova lógica
                        rota['agente_coleta'].update({
                            'valor_minimo': valor_minimo_coleta,
                            'excedente': excedente_coleta
                        })
                        
                        rota['agente_entrega'].update({
                            'valor_minimo': valor_minimo_entrega,
                            'excedente': excedente_entrega
                        })
                        
                        rotas_encontradas.append(rota)
                        
                        print(f"[AGENTES] ✅ Rota completa: {agente_col.get('Fornecedor')} (R$ {linha_coleta_processada['custo']:.2f}) + {transferencia['fornecedor']} (R$ {transferencia['custo']:.2f}) + {agente_ent.get('Fornecedor')} (R$ {linha_entrega_processada['custo']:.2f}) = R$ {total_rota:.2f}")
                        
                    except Exception as e:
                        print(f"[AGENTES] Erro ao combinar rota: {e}")
                        continue
        
        # Ordenar por custo total
        rotas_encontradas = sorted(rotas_encontradas, key=lambda x: x.get('total', float('inf')))
        
        print(f"[AGENTES] ✅ {len(rotas_encontradas)} rotas com agentes calculadas")
        
        return {
            'rotas': rotas_encontradas,
            'total_opcoes': len(rotas_encontradas),
            'origem': f"{origem}/{uf_origem}",
            'destino': f"{destino}/{uf_destino}",
            'base_origem': base_origem,
            'base_destino': base_destino,
            'transferencias_disponiveis': len(transferencias_encontradas)
        }
        
    except Exception as e:
        print(f"[AGENTES] Erro geral: {e}")
        import traceback
        traceback.print_exc()
        return None

# Dicionário de faixas de peso pré-calculadas para otimização
FAIXAS_PESO = [
    (10, 10), (20, 20), (30, 30), (50, 50), 
    (70, 70), (100, 100), (300, 300), (500, 500)
]

def processar_linha_transferencia(linha, peso, valor_nf):
    """
    Processa uma linha de transferência e retorna os custos calculados.
    
    NOVA LÓGICA PARA AGENTES:
    - Peso: Usar maior entre peso cubado ou real
    - Se peso ≤ 10kg: usar Coluna G (VALOR MÍNIMO ATÉ 10)
    - Se peso > 10kg: calcular com Coluna Q (EXCEDENTE) = peso × valor excedente
    - Retornar: GRIS (se tiver) e prazo
    
    Args:
        linha (pandas.Series ou dict): Linha da transferência com os dados
        peso (float): Peso da carga em kg (já deve ser o maior entre real e cubado)
        valor_nf (float): Valor da nota fiscal para cálculo do GRIS
        
    Returns:
        dict: Dicionário com os valores calculados ou None em caso de erro
    """
    try:
        # Converter pandas Series para dict se necessário
        if hasattr(linha, 'to_dict'):
            linha_dict = linha.to_dict()
        else:
            linha_dict = linha
        
        # Verificar se é um dicionário válido
        if not isinstance(linha_dict, dict):
            print(f"[ERRO] Formato inválido da linha: {type(linha_dict)}")
            return None
        
        # NOVA LÓGICA: Aplicar regra específica para agentes
        valor_base = 0.0
        faixa_peso_usada = ""
        valor_kg_usado = 0.0
        
        # Verificar se é agente (Tipo == 'Agente')
        is_agente = linha_dict.get('Tipo') == 'Agente'
        
        if is_agente:
            # LÓGICA PARA AGENTES
            if peso <= 10:
                # Peso ≤ 10kg: usar VALOR MÍNIMO ATÉ 10 (Coluna G)
                valor_minimo = float(linha_dict.get('VALOR MÍNIMO ATÉ 10', 0) or 0)
                valor_base = valor_minimo  # Valor fixo independente do peso
                faixa_peso_usada = "Valor Mínimo (≤10kg)"
                valor_kg_usado = valor_minimo / 10 if valor_minimo > 0 else 0  # Para referência
            else:
                # Peso > 10kg: calcular com EXCEDENTE (Coluna Q)
                valor_excedente = float(linha_dict.get('EXCEDENTE', 0) or 0)
                valor_base = peso * valor_excedente
                faixa_peso_usada = "Excedente (>10kg)"
                valor_kg_usado = valor_excedente
        else:
            # LÓGICA PARA TRANSFERÊNCIAS (mantém a lógica original)
            if peso <= 10:
                faixa_peso_usada = 'VALOR MÍNIMO ATÉ 10'
                valor_kg_coluna = 'VALOR MÍNIMO ATÉ 10'
            elif peso <= 20:
                faixa_peso_usada = 20
                valor_kg_coluna = 20
            elif peso <= 30:
                faixa_peso_usada = 30
                valor_kg_coluna = 30
            elif peso <= 50:
                faixa_peso_usada = 50
                valor_kg_coluna = 50
            elif peso <= 70:
                faixa_peso_usada = 70
                valor_kg_coluna = 70
            elif peso <= 100:
                faixa_peso_usada = 100
                valor_kg_coluna = 100
            elif peso <= 300:
                faixa_peso_usada = 300
                valor_kg_coluna = 300
            elif peso <= 500:
                faixa_peso_usada = 500
                valor_kg_coluna = 500
            else:
                faixa_peso_usada = 'Acima 500'
                valor_kg_coluna = 'Acima 500'
            
            # Obter valor por kg para a faixa
            try:
                if valor_kg_coluna in linha_dict:
                    valor_kg_usado = float(linha_dict[valor_kg_coluna] or 0)
                else:
                    # Se não encontrar a coluna, tentar usar o valor mínimo
                    valor_kg_usado = float(linha_dict.get('VALOR MÍNIMO ATÉ 10', 0) or 0)
            except (ValueError, TypeError):
                valor_kg_usado = 0
            
            # Calcular valor base para transferências
            valor_base = peso * valor_kg_usado
        
        # Calcular pedágio
        pedagio = 0.0
        try:
            valor_pedagio = float(linha_dict.get('Pedagio (100 Kg)', 0) or 0)
            if valor_pedagio > 0 and peso > 0:
                pedagio = math.ceil(peso / 100) * valor_pedagio
        except (ValueError, TypeError):
            pedagio = 0.0
        
        # Calcular GRIS
        gris = 0.0
        try:
            if valor_nf and valor_nf > 0:
                gris_exc = linha_dict.get('Gris Exc')
                gris_min = linha_dict.get('Gris Min', 0)
                
                if gris_exc is not None and not pd.isna(gris_exc):
                    gris_exc = float(gris_exc)
                    # Se maior que 1, assumir que é percentual (ex: 3.5 = 3.5%)
                    gris_percentual = gris_exc / 100 if gris_exc > 1 else gris_exc
                    gris_calculado = valor_nf * gris_percentual
                    
                    if gris_min is not None and not pd.isna(gris_min):
                        gris_min = float(gris_min)
                        gris = max(gris_calculado, gris_min)
                    else:
                        gris = gris_calculado
                        
                    # Verificar se o resultado é NaN
                    if pd.isna(gris) or math.isnan(gris):
                        gris = 0.0
        except (ValueError, TypeError):
            gris = 0.0
        
        # Calcular prazo
        prazo = 3  # Valor padrão
        try:
            prazo_valor = linha_dict.get('Prazo')
            if prazo_valor is not None and not pd.isna(prazo_valor):
                prazo = int(float(prazo_valor))
        except (ValueError, TypeError):
            prazo = 3
        
        # Obter informações do fornecedor
        fornecedor = linha_dict.get('Fornecedor', 'N/A')
        
        # Garantir que nenhum valor seja NaN
        valor_base = 0.0 if pd.isna(valor_base) or math.isnan(valor_base) else valor_base
        pedagio = 0.0 if pd.isna(pedagio) or math.isnan(pedagio) else pedagio
        gris = 0.0 if pd.isna(gris) or math.isnan(gris) else gris
        valor_kg_usado = 0.0 if pd.isna(valor_kg_usado) or math.isnan(valor_kg_usado) else valor_kg_usado
        
        total = valor_base + pedagio + gris
        total = 0.0 if pd.isna(total) or math.isnan(total) else total
        
        # Retornar resultado formatado
        return {
            'custo': round(valor_base, 2),
            'pedagio': round(pedagio, 2),
            'gris': round(gris, 2),
            'total': round(total, 2),
            'prazo': prazo,
            'faixa_peso': faixa_peso_usada,
            'valor_kg': round(valor_kg_usado, 4),
            'fornecedor': fornecedor,
            'is_agente': is_agente
        }
        
    except Exception as e:
        print(f"[ERRO] Erro ao processar transferência: {str(e)}")
        return None

@app.route("/debug/capacidades")
def debug_capacidades():
    """
    Rota de debug para verificar as capacidades dos veículos em tempo real
    """
    try:
        # Gerar análise de teste
        analise_teste = gerar_analise_trajeto(
            [-15.83, -47.86], [-23.55, -46.64], 
            {'distancia': 100, 'duracao': 60, 'provider': 'teste', 'rota_pontos': []}, 
            {}, 'Debug'
        )
        
        capacidades = analise_teste.get('capacidades_veiculos', {})
        
        # Formatar resposta HTML
        html_response = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Debug - Capacidades dos Veículos</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .veiculo { margin: 10px 0; padding: 10px; border: 1px solid #ccc; border-radius: 5px; }
                .correto { background-color: #d4edda; border-color: #c3e6cb; }
                .incorreto { background-color: #f8d7da; border-color: #f5c6cb; }
                .timestamp { color: #666; font-size: 0.9em; }
            </style>
        </head>
        <body>
            <h1>🔧 Debug - Capacidades dos Veículos</h1>
            <p class="timestamp">Timestamp: """ + datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S") + """</p>
            <h2>Capacidades Atuais:</h2>
        """
        
        for veiculo, dados in capacidades.items():
            peso_max = dados['peso_max']
            volume_max = dados['volume_max']
            descricao = dados['descricao']
            
            # Verificar se está correto
            correto = True
            problema = ""
            
            if veiculo == 'FIORINO' and peso_max != 500:
                correto = False
                problema = f"❌ PROBLEMA: Deveria ser 500kg, mas está {peso_max}kg"
            elif veiculo == 'FIORINO' and peso_max == 500:
                problema = "✅ Correto: 500kg"
            
            css_class = "correto" if correto else "incorreto"
            
            html_response += f"""
            <div class="veiculo {css_class}">
                <h3>{veiculo}</h3>
                <p><strong>Peso Máximo:</strong> {peso_max}kg</p>
                <p><strong>Volume Máximo:</strong> {volume_max}m³</p>
                <p><strong>Descrição:</strong> {descricao}</p>
                {f'<p><strong>Status:</strong> {problema}</p>' if problema else ''}
            </div>
            """
        
        html_response += """
            <h2>Ações:</h2>
            <p><a href="/clear-cache">🔄 Limpar Cache</a></p>
            <p><a href="/debug/capacidades">🔄 Recarregar Esta Página</a></p>
            <p><a href="/">🏠 Voltar ao Sistema</a></p>
        </body>
        </html>
        """
        
        return html_response
        
    except Exception as e:
        return f"""
        <html>
        <body>
            <h1>❌ Erro no Debug</h1>
            <p>Erro: {str(e)}</p>
            <p><a href="/">Voltar ao Sistema</a></p>
        </body>
        </html>
        """

def carregar_base_unificada():
    """
    Carrega a base unificada com dados de frete fracionado.
    """
    if not BASE_UNIFICADA_FILE or not os.path.exists(BASE_UNIFICADA_FILE):
        print("Base_Unificada.xlsx não encontrada")
        return None
    
    try:
        df_base = pd.read_excel(BASE_UNIFICADA_FILE)
        
        # Debug: Verificar colunas carregadas
        print(f"Base Unificada carregada com {len(df_base)} registros")
        print(f"Colunas encontradas: {df_base.columns.tolist()}")
        
        # Verificar se as colunas esperadas existem
        colunas_esperadas = ['Fornecedor', 'Base Origem', 'Origem', 'Base Destino', 'Destino']
        colunas_faltando = [col for col in colunas_esperadas if col not in df_base.columns]
        
        if colunas_faltando:
            print(f"ERRO: Colunas faltando: {colunas_faltando}")
            print(f"Colunas disponíveis: {df_base.columns.tolist()}")
            return None
        
        # Limpar dados nulos nas colunas principais
        df_base = df_base.dropna(subset=['Fornecedor', 'Origem', 'Destino'])
        
        print(f"Base processada com {len(df_base)} registros válidos")
        return df_base
        
    except Exception as e:
        print(f"Erro ao carregar Base_Unificada.xlsx: {e}")
        return None

def carregar_base_agentes():
    """
    Carrega a base de agentes com cache para evitar leitura repetida do arquivo
    """
    global _BASE_AGENTES_CACHE, _ULTIMO_CARREGAMENTO
    
    agora = time.time()
    
    # Se o cache ainda é válido, retorna os dados em cache
    if _BASE_AGENTES_CACHE is not None and (agora - _ULTIMO_CARREGAMENTO) < _CACHE_VALIDADE:
        if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
            print("[AGENTES] Retornando dados do cache")
        return _BASE_AGENTES_CACHE
    
    if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
        print("[AGENTES] Carregando base de agentes...")
    
    # Se não, carrega os dados
    df_base = carregar_base_completa()
    if df_base is None:
        if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
            print("[AGENTES] Erro: Não foi possível carregar a base completa")
        return None
    
    # Verifica se as colunas necessárias existem
    colunas_necessarias = ['Tipo', 'Origem']
    colunas_faltando = [col for col in colunas_necessarias if col not in df_base.columns]
    
    if colunas_faltando:
        if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
            print(f"[AGENTES] Erro: Colunas faltando na base: {', '.join(colunas_faltando)}")
            print(f"[AGENTES] Colunas disponíveis: {', '.join(df_base.columns)}")
        return None
    
    # Processa os dados uma única vez
    try:
        df_agentes = df_base[df_base['Tipo'] == 'Agente'].copy()
        df_transferencias = df_base[df_base['Tipo'] == 'Transferência'].copy()
        
        if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
            print(f"[AGENTES] {len(df_agentes)} agentes e {len(df_transferencias)} transferências carregados")
        
        # Pré-processa os dados para melhor performance
        df_agentes['Origem_Normalizada'] = df_agentes['Origem'].apply(normalizar_cidade)
        
        # Atualiza o cache
        _BASE_AGENTES_CACHE = (df_agentes, df_transferencias)
        _ULTIMO_CARREGAMENTO = agora
        
        if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
            print("[AGENTES] Base de agentes carregada com sucesso")
            
        return _BASE_AGENTES_CACHE
        
    except Exception as e:
        if os.getenv('DEBUG_AGENTES', 'false').lower() == 'true':
            print(f"[AGENTES] Erro ao processar base de agentes: {str(e)}")
        return None
    
    return _BASE_AGENTES_CACHE

def formatar_resultado_fracionado(resultado):
    """
    Gera HTML formatado para exibir resultado do frete fracionado APENAS com ROTAS DE AGENTES REAIS
    """
    melhor_opcao = resultado.get('melhor_opcao', {})
    dados_fonte = resultado.get('dados_fonte', 'Rotas com Agentes')
    
    # Definir variáveis necessárias para rotas com agentes
    criterios_qualidade = resultado.get('criterios_qualidade', 'APENAS rotas com agentes reais')
    cotacoes_rejeitadas = resultado.get('cotacoes_rejeitadas', 0)
    
    html = f"""
    <div class="success">
        <h3><i class="fa-solid fa-check-circle"></i> Cotação com Agentes Calculada - {resultado.get('id_historico', 'N/A')}</h3>
        
        <div class="analise-container">
            <div class="analise-title">🏆 Melhor Rota com Agentes</div>
            <div class="analise-item"><strong>Rota:</strong> {melhor_opcao.get('resumo', 'N/A')}</div>
            <div class="analise-item"><strong>Fonte:</strong> {dados_fonte}</div>
            <div class="analise-item" style="font-size: 1.3rem; font-weight: bold; color: #0a6ed1; background: #e8f4fd; padding: 12px; border-radius: 8px; text-align: center;">
                💰 <strong>CUSTO TOTAL: R$ {melhor_opcao.get('total', 0):,.2f}</strong>
            </div>
            <div class="analise-item" style="font-size: 1.1rem; font-weight: bold; text-align: center;">
                ⏱️ <strong>Prazo: {melhor_opcao.get('prazo_total', 'N/A')} dias úteis</strong>
            </div>
        </div>

        <!-- Filtros de Qualidade Aplicados -->
        <div class="analise-container">
            <div class="analise-title">🔍 Filtros de Qualidade Aplicados</div>
            <div class="analise-item"><strong>Critérios Obrigatórios:</strong> {criterios_qualidade}</div>
            <div class="analise-item"><strong>Cotações Aceitas:</strong> 
                <span style="color: #27ae60; font-weight: bold;">{resultado.get('total_opcoes', 0)}</span>
            </div>
            <div class="analise-item"><strong>Cotações Rejeitadas:</strong> 
                <span style="color: #e74c3c; font-weight: bold;">{cotacoes_rejeitadas}</span>
            </div>
        </div>

        <!-- Informações da Rota -->
        <div class="analise-container">
            <div class="analise-title">📍 Informações da Rota</div>
            <div class="analise-item"><strong>Origem:</strong> {resultado.get('origem', 'N/A')} - {resultado.get('uf_origem', 'N/A')}</div>
            <div class="analise-item"><strong>Destino:</strong> {resultado.get('destino', 'N/A')} - {resultado.get('uf_destino', 'N/A')}</div>
            <div class="analise-item"><strong>Peso Real:</strong> {resultado.get('peso', 0)} kg</div>
            <div class="analise-item"><strong>Peso Cubado:</strong> {resultado.get('peso_cubado', 0):.2f} kg</div>
            <div class="analise-item"><strong>Cubagem:</strong> {resultado.get('cubagem', 0):.4f} m³</div>
            {f'<div class="analise-item"><strong>Valor da NF:</strong> R$ {resultado.get("valor_nf", 0):,.2f}</div>' if resultado.get('valor_nf') else '<div class="analise-item"><strong>Valor da NF:</strong> <span style="color: #f39c12;">Não informado</span></div>'}
        </div>
    """
    
    # Tabela com ranking das opções disponíveis
    ranking_completo = resultado.get('cotacoes_ranking', [])
    
    if ranking_completo:
        html += """
        <div class="analise-container">
            <div class="analise-title">📊 Todas as Rotas com Agentes Encontradas</div>
            <table class="result-table" style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <thead style="background: #f8f9fa;">
                    <tr>
                        <th style="padding: 12px; text-align: left; border: 1px solid #dee2e6;">Posição</th>
                        <th style="padding: 12px; text-align: left; border: 1px solid #dee2e6;">Rota Completa</th>
                        <th style="padding: 12px; text-align: right; border: 1px solid #dee2e6;">Custo Total</th>
                        <th style="padding: 12px; text-align: center; border: 1px solid #dee2e6;">Prazo</th>
                        <th style="padding: 12px; text-align: center; border: 1px solid #dee2e6;">Detalhes</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for i, opcao in enumerate(ranking_completo, 1):
            # Determinar medalha/posição
            if i == 1:
                posicao_icon = "🥇"
                row_style = "background: #fff3cd; border-left: 4px solid #ffc107;"
            elif i == 2:
                posicao_icon = "🥈"
                row_style = "background: #f8f9fa; border-left: 4px solid #6c757d;"
            elif i == 3:
                posicao_icon = "🥉"
                row_style = "background: #fff3cd; border-left: 4px solid #fd7e14;"
            else:
                posicao_icon = f"{i}º"
                row_style = "background: #ffffff;"
            
            agente_coleta = opcao.get('agente_coleta', {})
            transferencia = opcao.get('transferencia', {})
            agente_entrega = opcao.get('agente_entrega', {})
            
            html += f"""
                    <tr style="{row_style}">
                        <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; font-size: 1.1em;">{posicao_icon}</td>
                        <td style="padding: 12px; border: 1px solid #dee2e6;">
                            <strong>{opcao.get('resumo', 'N/A')}</strong><br>
                            <small style="color: #6c757d;">
                                Coleta: {agente_coleta.get('fornecedor', 'N/A')} → 
                                Transfer: {transferencia.get('fornecedor', 'N/A')} → 
                                Entrega: {agente_entrega.get('fornecedor', 'N/A')}
                            </small>
                        </td>
                        <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: bold; color: #0a6ed1; font-size: 1.1em;">
                            R$ {opcao.get('total', 0):,.2f}
                        </td>
                        <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                            {opcao.get('prazo_total', 'N/A')} dias
                        </td>
                        <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                            <button class="btn-secondary" onclick="toggleDetails('detalhes_coleta_{i}')" style="margin: 2px; font-size: 0.8rem; padding: 4px 8px; background: #007bff;">
                                Ver Coleta
                            </button><br>
                            <button class="btn-secondary" onclick="toggleDetails('detalhes_transfer_{i}')" style="margin: 2px; font-size: 0.8rem; padding: 4px 8px; background: #fd7e14;">
                                Ver Transfer
                            </button><br>
                            <button class="btn-secondary" onclick="toggleDetails('detalhes_entrega_{i}')" style="margin: 2px; font-size: 0.8rem; padding: 4px 8px; background: #28a745;">
                                Ver Entrega
                            </button>
                        </td>
                    </tr>
                    
                    <!-- Detalhes da Coleta -->
                    <tr id="detalhes_coleta_{i}" style="display: none;">
                        <td colspan="5" style="padding: 15px; background: #e3f2fd; border: 1px solid #dee2e6;">
                            <strong style="color: #007bff;">🚚 Agente de Coleta:</strong><br>
                            • <strong>Fornecedor:</strong> {agente_coleta.get('fornecedor', 'N/A')}<br>
                            • <strong>Origem:</strong> {agente_coleta.get('origem', 'N/A')}<br>
                            • <strong>Base Destino:</strong> {agente_coleta.get('base_destino', 'N/A')}<br>
                            • <strong>Custo:</strong> R$ {agente_coleta.get('custo', 0):.2f}<br>
                            • <strong>Prazo:</strong> {agente_coleta.get('prazo', 'N/A')} dias<br>
                            • <strong>Peso Máximo:</strong> {agente_coleta.get('peso_maximo', 'N/A')} kg
                        </td>
                    </tr>
                    
                    <!-- Detalhes da Transferência -->
                    <tr id="detalhes_transfer_{i}" style="display: none;">
                        <td colspan="5" style="padding: 15px; background: #fff3e0; border: 1px solid #dee2e6;">
                            <strong style="color: #fd7e14;">🚛 Transferência entre Bases:</strong><br>
                            • <strong>Fornecedor:</strong> {transferencia.get('fornecedor', 'N/A')}<br>
                            • <strong>Origem:</strong> {transferencia.get('origem', 'N/A')}<br>
                            • <strong>Destino:</strong> {transferencia.get('destino', 'N/A')}<br>
                            • <strong>Custo Base:</strong> R$ {transferencia.get('custo', 0):.2f}<br>
                            • <strong>Pedágio:</strong> R$ {transferencia.get('pedagio', 0):.2f}<br>
                            • <strong>GRIS:</strong> R$ {transferencia.get('gris', 0):.2f}<br>
                            • <strong>Prazo:</strong> {transferencia.get('prazo', 'N/A')} dias
                        </td>
                    </tr>
                    
                    <!-- Detalhes da Entrega -->
                    <tr id="detalhes_entrega_{i}" style="display: none;">
                        <td colspan="5" style="padding: 15px; background: #e8f5e8; border: 1px solid #dee2e6;">
                            <strong style="color: #28a745;">🏠 Agente de Entrega:</strong><br>
                            • <strong>Fornecedor:</strong> {agente_entrega.get('fornecedor', 'N/A')}<br>
                            • <strong>Base Origem:</strong> {agente_entrega.get('base_origem', 'N/A')}<br>
                            • <strong>Destino:</strong> {agente_entrega.get('destino', 'N/A')}<br>
                            • <strong>Custo:</strong> R$ {agente_entrega.get('custo', 0):.2f}<br>
                            • <strong>Prazo:</strong> {agente_entrega.get('prazo', 'N/A')} dias<br>
                            • <strong>Peso Máximo:</strong> {agente_entrega.get('peso_maximo', 'N/A')} kg
                        </td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
            <div style="margin-top: 10px; font-size: 0.85rem; color: #666; text-align: center;">
                <strong>Legenda:</strong> 
                🥇 Melhor preço | 🥈 2º melhor | 🥉 3º melhor | 
                🚚 Frete Fracionado
            </div>
        </div>
        """
    else:
        # Caso não haja opções
        html += """
        <div class="analise-container">
            <div class="analise-title">⚠️ Nenhuma Rota Disponível</div>
            <div class="analise-item" style="color: #e74c3c;">
                <strong>Problema:</strong> Não foram encontradas rotas com agentes para esta origem/destino.
            </div>
        </div>
        """
    
    html += """
    </div>
    
    <script>
    function toggleDetails(elementId) {
        var element = document.getElementById(elementId);
        if (element.style.display === "none") {
            element.style.display = "block";
        } else {
            element.style.display = "none";
        }
    }
    </script>
    """
    
    # Resumo final apenas com dados reais
    total_opcoes = len(ranking_completo)
    
    if total_opcoes > 0:        
        html += f"""
        <div class="analise-container">
            <div class="analise-title">📈 Resumo da Consulta</div>
            <div class="analise-item"><strong>📊 Total de Rotas:</strong> <span style="color: #27ae60; font-weight: bold;">{total_opcoes}</span></div>
            <div class="analise-item"><strong>💰 Melhor Rota:</strong> {ranking_completo[0].get('resumo', 'N/A')} - R$ {ranking_completo[0].get('total', 0):,.2f}</div>
            <div class="analise-item"><strong>📊 Fonte dos Dados:</strong> <span style="color: #27ae60;">Frete Fracionado</span></div>
        </div>
        """
    
    # Botões de exportação
    html += f"""
        <div style="margin-top: 20px; text-align: center;">
            <button class="btn-primary" onclick="exportarPDF('Fracionado')" style="margin-right: 10px;">
                <i class="fa-solid fa-file-pdf"></i> Exportar PDF
            </button>
            <button class="btn-primary" onclick="exportarExcel('Fracionado')">
                <i class="fa-solid fa-file-excel"></i> Exportar Excel
            </button>
        </div>
    """
    
    return html

if __name__ == "__main__":
    # Usar configurações de ambiente para produção
    debug_mode = os.getenv("DEBUG", "False").lower() == "true"
    port = int(os.getenv("PORT", 5000))
    
    if os.getenv("FLASK_ENV") == "production":
        # Em produção, não usar o servidor de desenvolvimento
        app.run(host="0.0.0.0", port=port, debug=debug_mode)
    else:
        # Em desenvolvimento, usar o servidor de desenvolvimento
        app.run(host="0.0.0.0", port=port, debug=True)
