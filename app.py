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

# Importar utilitários
from utils import MAPA_BASES

# Carregar variáveis de ambiente
load_dotenv()

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
        # Adicionar cabeçalho de sessão na resposta
        response = f(*args, **kwargs)
        if hasattr(response, 'headers'):
            response.headers['X-Session-ID'] = session.get('usuario_logado', '')
        return response
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
                response = jsonify({
                    'success': True, 
                    'message': 'Login realizado com sucesso!',
                    'usuario': USUARIOS_SISTEMA[usuario]['nome'],
                    'tipo': USUARIOS_SISTEMA[usuario]['tipo'],
                    'redirect': '/'
                })
                response.set_cookie('session_auth', usuario, httponly=True, samesite='Strict')
                return response
            else:
                flash(f'Bem-vindo, {USUARIOS_SISTEMA[usuario]["nome"]}!', 'success')
                response = redirect(url_for('index'))
                response.set_cookie('session_auth', usuario, httponly=True, samesite='Strict')
                return response
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
        tipo_filtro = data.get("tipo_filtro")  # Obter tipo_filtro do request logo no início
        base_filtro = data.get("base_filtro")  # Obter base_filtro do request logo no início

        log_acesso(usuario, 'CALCULO_FRACIONADO', ip_cliente, 
                  f"Cálculo Fracionado: {cidade_origem}/{uf_origem} -> {cidade_destino}/{uf_destino}, Peso: {peso}kg")

        if not all([uf_origem, cidade_origem, uf_destino, cidade_destino]):
            return jsonify({"error": "Todos os campos são obrigatórios."})

        # Definir peso real e peso cubado
        peso_real = float(peso)
        peso_cubado = float(cubagem) * 166  # Usando 166kg/m³ conforme regra da ANTT

        # USAR APENAS A BASE_UNIFICADA.XLSX - SEM SIMULAÇÕES
        cotacoes_base = calcular_frete_base_unificada(
            cidade_origem, uf_origem, 
            cidade_destino, uf_destino, 
            peso, valor_nf, cubagem,
            tipo_filtro
        )

        if not cotacoes_base or cotacoes_base.get('total_opcoes', 0) == 0:
            return jsonify({
                "error": "Nenhuma cotação real encontrada na planilha para esta rota. Verifique se existe dados para origem/destino na Base_Unificada.xlsx"
            })

        # Pegar cotações ranking da planilha
        cotacoes_ranking = cotacoes_base.get('cotacoes_ranking', [])
        
        if not cotacoes_ranking:
            return jsonify({
                "error": "Nenhuma cotação válida encontrada na Base_Unificada.xlsx"
            })

        # NOVO: Calcular também rotas com agentes
        print(f"[AGENTES] Aplicando filtros - Tipo: {tipo_filtro}, Base: {base_filtro}")
        
        # Ajustar base_filtro para RIO, RAO ou SAO quando necessário
        if tipo_filtro == "Agente" and not base_filtro:
            if uf_origem == "RJ" or "RIO DE JANEIRO" in cidade_origem.upper():
                base_filtro = "RIO"
                print(f"[AGENTES] Ajustando base para RIO automaticamente")
            elif "RIBEIRAO PRETO" in cidade_origem.upper() or "RAO" in cidade_origem.upper():
                base_filtro = "RAO"
                print(f"[AGENTES] Ajustando base para RAO automaticamente")
            elif uf_origem == "SP":
                base_filtro = "SAO"
                print(f"[AGENTES] Ajustando base para SAO automaticamente")
        
        rotas_agentes = calcular_frete_com_agentes(
            cidade_origem, uf_origem,
            cidade_destino, uf_destino,
            peso, valor_nf, cubagem,
            base_filtro
        )

        # Melhor opção (menor custo)
        melhor_opcao = cotacoes_ranking[0] if cotacoes_ranking else {}

        # Incrementar contador
        CONTADOR_FRACIONADO += 1
        
        # ID do histórico
        id_historico = f"Fra{CONTADOR_FRACIONADO:03d}"

        # Identificar qual peso foi usado na melhor opção (sempre o maior)
        maior_peso_usado = melhor_opcao.get('maior_peso', max(peso_real, peso_cubado))
        peso_usado_tipo = melhor_opcao.get('peso_usado_tipo', 'Real' if maior_peso_usado == peso_real else 'Cubado')

        # Combinar cotações diretas com rotas de agentes
        ranking_completo = cotacoes_ranking.copy()
        
        # Adicionar rotas com agentes ao ranking completo
        todas_opcoes = []
        
        # Adicionar opções diretas da planilha
        for opcao in cotacoes_base.get('cotacoes_ranking', []):
            # Verificar se devemos filtrar por tipo
            if tipo_filtro and tipo_filtro != opcao.get('tipo', 'Direto'):
                continue
                
            todas_opcoes.append({
                'tipo': opcao.get('tipo', 'Direto'),
                'modalidade': opcao.get('modalidade', 'N/A'),
                'agente': opcao.get('agente', ''),
                'fonte': opcao.get('fonte', 'Base_Unificada.xlsx'),
                'valor_base': opcao.get('valor_base', 0),
                'pedagio': opcao.get('pedagio', 0),
                'gris': opcao.get('gris', 0),
                'total': opcao.get('total', 0),
                'prazo': opcao.get('prazo', 0),
                'peso_real': opcao.get('peso_real', 0),
                'peso_cubado': opcao.get('peso_cubado', 0),
                'maior_peso': opcao.get('maior_peso', 0),
                'peso_usado': opcao.get('peso_usado', 'Real'),
                'observacoes': opcao.get('observacoes', ''),
                'base_origem': opcao.get('base_origem', 'N/A'),
                'nome_base_origem': opcao.get('nome_base_origem', opcao.get('base_origem', 'N/A')),
                'detalhes': opcao
            })
        
        # Adicionar rotas com agentes
        if rotas_agentes and rotas_agentes.get('rotas'):
            for rota in rotas_agentes.get('rotas', []):
                if not rota:  # Pular rotas inválidas
                    continue
                    
                # Verificar se devemos filtrar por tipo
                if tipo_filtro and tipo_filtro != 'Agente':
                    continue
                    
                # Filtrar somente agentes da base especificada - SEM N/A
                if rota.get('fornecedor_coleta') == 'N/A' or rota.get('fornecedor_transferencia') == 'N/A' or rota.get('agente_entrega', {}).get('fornecedor') == 'N/A':
                    continue  # Pular rotas com informações incompletas
                
                # Mapear Base Origem para nome da cidade
                base_coleta = rota.get('agente_coleta', {}).get('base_destino', '')
                nome_base_coleta = MAPA_BASES.get(base_coleta, base_coleta)
                
                base_transferencia = rota.get('transferencia', {}).get('base_destino', '')
                nome_base_transferencia = MAPA_BASES.get(base_transferencia, base_transferencia)
                
                # Extrair custos detalhados
                detalhamento = rota.get('detalhamento_custos', {})
                custo_coleta = detalhamento.get('coleta', 0) if detalhamento else rota.get('agente_coleta', {}).get('custo', 0)
                custo_transferencia = detalhamento.get('transferencia', 0) if detalhamento else rota.get('transferencia', {}).get('custo', 0)
                custo_entrega = detalhamento.get('entrega', 0) if detalhamento else rota.get('agente_entrega', {}).get('custo', 0)
                pedagio = detalhamento.get('pedagio', 0) if detalhamento else rota.get('transferencia', {}).get('pedagio', 0)
                gris_total = detalhamento.get('gris_total', 0) if detalhamento else (
                    rota.get('transferencia', {}).get('gris', 0) + 
                    rota.get('agente_coleta', {}).get('gris', 0) + 
                    rota.get('agente_entrega', {}).get('gris', 0)
                )
                
                # Exemplo: "Jem/Dfl (R$ 124,50) + SOL (R$ 345,77)"
                fornecedor_coleta = rota.get('fornecedor_coleta', '')
                fornecedor_transferencia = rota.get('fornecedor_transferencia', '')
                fornecedor_entrega = rota.get('agente_entrega', {}).get('fornecedor', '')
                
                # Formatação para a COLUNA "Fornecedor/Rota" (mostrar fornecedores + valores)
                modalidade_display = f"{fornecedor_coleta} (R$ {custo_coleta:.2f}) + {fornecedor_transferencia} (R$ {custo_transferencia:.2f}) + {fornecedor_entrega} (R$ {custo_entrega:.2f})"
                
                # Determinar base de origem para coleta
                base_origem_coleta = rota.get('agente_coleta', {}).get('base_origem', rota.get('base_origem', ''))
                
                todas_opcoes.append({
                    'tipo': 'Agente',  # Identificar claramente como rota com agente
                    'modalidade': modalidade_display,  # Mostrar fornecedores + valores na tabela principal
                    'agente': f"{fornecedor_coleta} + {fornecedor_transferencia} + {fornecedor_entrega}",
                    'fonte': 'Sistema de Agentes',
                    'valor_base': custo_coleta + custo_transferencia + custo_entrega,
                    'pedagio': pedagio,
                    'gris': gris_total,
                    'total': rota.get('total', 0),
                    'prazo': rota.get('prazo_total', rota.get('prazo', 0)),
                    'peso_real': rota.get('peso_real', peso_real),
                    'peso_cubado': rota.get('peso_cubado', peso_cubado),
                    'maior_peso': rota.get('maior_peso', max(peso_real, peso_cubado)),
                    'peso_usado': rota.get('peso_usado', 'Real' if peso_real >= peso_cubado else 'Cubado'),
                    'observacoes': f"Rota: {nome_base_coleta} → {nome_base_transferencia}. Coleta: {fornecedor_coleta} (R$ {custo_coleta:.2f}). Transferência: {fornecedor_transferencia} (R$ {custo_transferencia:.2f}). Entrega: {fornecedor_entrega} (R$ {custo_entrega:.2f}).{f' Pedágio: R$ {pedagio:.2f}.' if pedagio > 0 else ''}{f' GRIS: R$ {gris_total:.2f}.' if gris_total > 0 else ''}",
                    'base_origem': base_origem_coleta,
                    'nome_base_origem': MAPA_BASES.get(base_origem_coleta, base_origem_coleta),
                    'base_destino_transferencia': base_transferencia,
                    'nome_base_destino_transferencia': nome_base_transferencia,
                    'fornecedor_coleta': fornecedor_coleta,
                    'fornecedor_transferencia': fornecedor_transferencia,
                    'fornecedor_entrega': fornecedor_entrega,
                    'detalhamento_custos': {
                        'coleta': custo_coleta,
                        'transferencia': custo_transferencia,
                        'entrega': custo_entrega,
                        'pedagio': pedagio,
                        'gris_total': gris_total
                    },
                    'detalhes': rota
                })

        # Ordenar todas as opções por custo total
        todas_opcoes = [item for item in todas_opcoes if item.get('total') is not None]
        todas_opcoes = sorted(todas_opcoes, key=lambda x: x.get('total', float('inf')))
        
        # Usar o ranking unificado para o HTML

        
        ranking_completo = todas_opcoes


        
        # Atualizar melhor opção com base no ranking unificado
        if ranking_completo:
            melhor_opcao_unificada = ranking_completo[0]
            if melhor_opcao_unificada.get('total', float('inf')) < melhor_opcao.get('total', float('inf')):
                print(f"[DEBUG] Melhor opção atualizada de {melhor_opcao.get('modalidade')} (R$ {melhor_opcao.get('total', 0):.2f}) para {melhor_opcao_unificada.get('modalidade', melhor_opcao_unificada.get('fornecedor_coleta', 'N/A'))} (R$ {melhor_opcao_unificada.get('total', 0):.2f})")
                melhor_opcao = melhor_opcao_unificada

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
            
            # Informações do ranking REAL - SEM SIMULAÇÕES
            "cotacoes_ranking": cotacoes_ranking,  
            "ranking_completo": ranking_completo,  # Ranking unificado com agentes
            "fornecedores_disponiveis": list(set(c['modalidade'] for c in cotacoes_ranking)),
            "total_opcoes": cotacoes_base['total_opcoes'],
            "fornecedores_count": cotacoes_base['fornecedores_count'],
            "cotacoes_rejeitadas": 0,  # Sem simulações, sem rejeições
            "criterios_qualidade": "APENAS dados reais da planilha Base_Unificada.xlsx",
            
            # NOVO: Adicionar rotas com agentes
            "rotas_agentes": rotas_agentes if rotas_agentes else None,
            "tem_rotas_agentes": bool(rotas_agentes and rotas_agentes.get('total_opcoes', 0) > 0),
            
            # Melhor opção
            "fornecedor": melhor_opcao.get('modalidade', 'N/A'),
            "agente": melhor_opcao.get('agente', 'N/A'),
            "base_origem": melhor_opcao.get('origem', cidade_origem),
            "base_destino": melhor_opcao.get('destino', cidade_destino),
            "valor_base": melhor_opcao.get('valor_base', 0),
            "pedagio": melhor_opcao.get('pedagio', 0),
            "gris": melhor_opcao.get('gris', 0),
            "custo_total": melhor_opcao.get('total', 0),
            "prazo_total": melhor_opcao.get('prazo', 1),
            "observacoes": melhor_opcao.get('observacoes', ''),
            
            # Fonte dos dados
            "dados_fonte": cotacoes_base.get('dados_fonte', 'Base_Unificada.xlsx'),
            "estrategia_busca": "PLANILHA_REAL_APENAS",
            "cidades_origem": [cidade_origem],
            "cidades_destino": [cidade_destino],
            "rota_pontos": [],
            "distancia": 0,
            "detalhamento": f"Busca APENAS na planilha real - {len(cotacoes_ranking)} opções encontradas"
        }

        # Sem mapa na aba fracionado - dados vêm da planilha
        resultado_final["rota_pontos"] = []
        resultado_final["distancia"] = 0

        # Adicionar melhor opção de agente se existir
        melhor_agente = None
        if rotas_agentes and rotas_agentes.get('rotas'):
            rotas_agentes_lista = rotas_agentes.get('rotas', [])
            if rotas_agentes_lista:
                # Ordenar por custo total para garantir que pegamos a melhor opção
                # Verificar e filtrar itens com 'total' None ou inválido
                rotas_agentes_lista = [item for item in rotas_agentes_lista if item.get('total') is not None]
                
                # Recalcular o valor total para cada rota
                for item in rotas_agentes_lista:
                    # Garantir que temos os componentes necessários
                    coleta = item.get('agente_coleta', {})
                    transferencia = item.get('transferencia', {})
                    entrega = item.get('agente_entrega', {})
                    
                    # Extrair custos individuais
                    custo_coleta = coleta.get('custo', 0) or 0
                    custo_transferencia = transferencia.get('custo', 0) or 0
                    custo_entrega = entrega.get('custo', 0) or 0
                    pedagio = transferencia.get('pedagio', 0) or 0
                    gris_coleta = coleta.get('gris', 0) or 0
                    gris_transferencia = transferencia.get('gris', 0) or 0
                    gris_entrega = entrega.get('gris', 0) or 0
                    
                    # Recalcular o total
                    total_calculado = custo_coleta + custo_transferencia + custo_entrega + pedagio + gris_coleta + gris_transferencia + gris_entrega
                    
                    # Atualizar o total na rota
                    item['total'] = total_calculado
                    
                    # Adicionar detalhamento dos custos para facilitar visualização
                    item['detalhamento_custos'] = {
                        'coleta': custo_coleta,
                        'transferencia': custo_transferencia,
                        'entrega': custo_entrega,
                        'pedagio': pedagio,
                        'gris_total': gris_coleta + gris_transferencia + gris_entrega
                    }
                    
                    print(f"[DEBUG] Rota {item.get('fornecedor_coleta', '')}/{item.get('fornecedor_transferencia', '')}/{item.get('agente_entrega', {}).get('fornecedor', '')}: Coleta={custo_coleta:.2f} + Transferência={custo_transferencia:.2f} + Entrega={custo_entrega:.2f} = Total {total_calculado:.2f}")
                
                # Agora ordenar com segurança
                rotas_agentes_lista = sorted(rotas_agentes_lista, key=lambda x: x.get('total', float('inf')))
                
                # Verificar se ainda temos rotas após a filtragem
                if rotas_agentes_lista:
                    melhor_agente = rotas_agentes_lista[0]  # A primeira rota é a melhor
                    
                    # Adicionar informações completas para exibição
                    if melhor_agente:
                        melhor_agente['tipo'] = 'Transferência'
                        if 'fornecedor' not in melhor_agente and 'fornecedor_coleta' in melhor_agente:
                            melhor_agente['fornecedor'] = f"{melhor_agente.get('fornecedor_coleta', 'N/A')}/{melhor_agente.get('fornecedor_transferencia', 'N/A')}/{melhor_agente.get('agente_entrega', {}).get('fornecedor', 'N/A')}"
                        
                        # Adicionar informações para Jem/Dfl
                        if 'Jem' in melhor_agente.get('fornecedor_coleta', '') or 'Dfl' in melhor_agente.get('fornecedor_coleta', ''):
                            melhor_agente['modalidade'] = 'Jem/Dfl'
                    
                    print(f"[DEBUG] Melhor agente encontrado: {melhor_agente.get('fornecedor', melhor_agente.get('fornecedor_coleta'))} - {melhor_agente.get('base_origem')} → {melhor_agente.get('base_destino_transferencia')} - R$ {melhor_agente.get('total', 0):.2f}")
                else:
                    print(f"[DEBUG] Nenhuma rota válida encontrada após filtragem")

        # Adicionar HTML formatado
        resultado_final["html"] = formatar_resultado_fracionado({
            'melhor_opcao': melhor_opcao,
            'melhor_direto': melhor_opcao,  # Melhor opção direta
            'melhor_agente': melhor_agente,  # Melhor opção com agente
            'cotacoes_ranking': cotacoes_ranking,
            'ranking_completo': ranking_completo,  # Ranking unificado com agentes
            'total_opcoes': cotacoes_base['total_opcoes'],
            'fornecedores_count': cotacoes_base['fornecedores_count'],
            'dados_fonte': cotacoes_base.get('dados_fonte', 'Base_Unificada.xlsx'),
            'id_historico': id_historico,
            'cotacoes_rejeitadas': 0,
            'criterios_qualidade': 'Dados reais da planilha',
            'tipo_filtro': tipo_filtro,  # Passar o tipo de filtro
            # Passar TODOS os dados necessários
            'origem': cidade_origem,
            'uf_origem': uf_origem,
            'destino': cidade_destino,
            'uf_destino': uf_destino,
            'peso': peso_real,
            'peso_cubado': peso_cubado,
            'cubagem': cubagem,
            'valor_nf': valor_nf,
            'estrategia_busca': "PLANILHA_REAL_APENAS",
            # NOVO: Passar rotas com agentes
            'rotas_agentes': rotas_agentes,
            'mapa_bases': MAPA_BASES
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
            "melhor_opcao": melhor_opcao.get('modalidade', 'N/A'),
            "custo": melhor_opcao.get('total', 0),
            "resultado_completo": resultado_final
        })

        # Manter apenas os últimos 50 registros
        if len(HISTORICO_PESQUISAS) > 50:
            HISTORICO_PESQUISAS.pop(0)

        # Tratar valores NaN ou não serializáveis para JSON
        def sanitize_for_json(obj):
            if isinstance(obj, dict):
                # Converter todas as chaves para string para evitar erro de serialização
                sanitized = {}
                for k, v in obj.items():
                    # Converter chave para string se for número
                    key = str(k) if isinstance(k, (int, float)) else k
                    sanitized[key] = sanitize_for_json(v)
                return sanitized
            elif isinstance(obj, list):
                return [sanitize_for_json(item) for item in obj]
            elif pd.isna(obj):
                return None
            elif isinstance(obj, (float, int, str, bool)) or obj is None:
                return obj
            elif hasattr(obj, 'to_dict'):  # Para objetos pandas
                return sanitize_for_json(obj.to_dict())
            else:
                return str(obj)
        
        # Sanitizar resultado final para garantir que é serializável em JSON
        resultado_final = sanitize_for_json(resultado_final)

        return jsonify(resultado_final)

    except Exception as e:
        log_acesso(usuario, 'ERRO_CALCULO_FRACIONADO', ip_cliente, f"Erro: {str(e)}")
        print(f"Erro ao calcular frete fracionado: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erro ao calcular frete fracionado: {str(e)}"})

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
        
        dados = request.get_json()
        tipo = dados.get("tipo")
        dados_exportacao = dados.get("dados")
        
        if not dados_exportacao:
            return jsonify({"error": "Nenhum dado fornecido para exportação"}), 400
        
        # Criar DataFrame com os dados
        df = pd.DataFrame(dados_exportacao)
        
        # Criar buffer em memória
        buffer = io.BytesIO()
        
        # Escrever dados para o buffer
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=f"Dados_{tipo}", index=False)
        
        buffer.seek(0)
        
        # Nome do arquivo com timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"dados_{tipo}_{timestamp}.xlsx"
        
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Erro ao exportar Excel: {e}")
        return jsonify({"error": f"Erro ao exportar dados: {str(e)}"}), 500

@app.route("/historico/<id_historico>")
def historico_detalhe(id_historico):
    # Implementar visualização detalhada do histórico
    return render_template("index.html")

def formatar_resultado_fracionado(resultado):
    """
    Formata o resultado do frete fracionado para exibição HTML
    """
    if not resultado:
        return "<div class='error'>Nenhum resultado encontrado</div>"
    
    try:
        melhor_opcao = resultado.get('melhor_opcao', {})
        cotacoes_ranking = resultado.get('cotacoes_ranking', [])
        ranking_completo = resultado.get('ranking_completo', cotacoes_ranking)
        
        html = f"""
        <div class="resultado-fracionado">
            <div class="header-resultado">
                <h3>🚛 Resultado do Frete Fracionado</h3>
                <div class="id-calculo">ID: {resultado.get('id_historico', 'N/A')} | {resultado.get('data_hora', 'N/A')}</div>
            </div>
        """
        
        # Melhor opção em destaque
        if melhor_opcao:
            valor_total = melhor_opcao.get('total', 0)
            html += f"""
            <div class="melhor-opcao">
                <div class="titulo-melhor">🏆 Melhor Opção</div>
                <div class="fornecedor-destaque">{melhor_opcao.get('modalidade', 'N/A')}</div>
                <div class="valor-destaque">R$ {valor_total:,.2f}</div>
                <div class="prazo-destaque">Prazo: {melhor_opcao.get('prazo', 'N/A')} dias</div>
            </div>
            """
        
        # Informações da rota
        html += f"""
            <div class="analise-container">
                <div class="analise-title">📍 Informações da Rota</div>
                <div class="analise-item"><strong>Origem:</strong> {resultado.get('origem', 'N/A')} - {resultado.get('uf_origem', 'N/A')}</div>
                <div class="analise-item"><strong>Destino:</strong> {resultado.get('destino', 'N/A')} - {resultado.get('uf_destino', 'N/A')}</div>
                <div class="analise-item"><strong>Peso Real:</strong> {resultado.get('peso', 0)} kg</div>
                <div class="analise-item"><strong>Peso Cubado:</strong> {resultado.get('peso_cubado', 0):.2f} kg</div>
                <div class="analise-item"><strong>Maior Peso (Usado):</strong> <span style="color: #e74c3c; font-weight: bold;">{melhor_opcao.get('maior_peso', 0):.1f} kg ({melhor_opcao.get('peso_usado', 'N/A')})</span></div>
                <div class="analise-item"><strong>Cubagem:</strong> {resultado.get('cubagem', 0):.4f} m³</div>
                {f'<div class="analise-item"><strong>Valor da NF:</strong> R$ {resultado.get("valor_nf", 0):,.2f}</div>' if resultado.get('valor_nf') else '<div class="analise-item"><strong>Valor da NF:</strong> <span style="color: #f39c12;">Não informado</span></div>'}
            </div>
        """
        
        # Ranking completo
        if ranking_completo:
            html += """
            <div class="analise-container">
                <div class="analise-title">🥇 Ranking de Fornecedores</div>
                <table class="results" style="font-size: 0.9rem;">
                    <thead>
                        <tr>
                            <th>Pos</th>
                            <th>Tipo</th>
                            <th>Fornecedor/Rota</th>
                            <th>Base</th>
                            <th>TOTAL</th>
                            <th>Prazo</th>
                            <th>Detalhes</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for i, opcao in enumerate(ranking_completo[:10]):  # Mostrar até 10 melhores
                pos_class = ""
                if i == 0:
                    pos_class = "style='background-color: #e8f5e8; font-weight: bold;'"  # Verde para 1º
                elif i == 1:
                    pos_class = "style='background-color: #fff3e0; font-weight: bold;'"  # Laranja para 2º
                elif i == 2:
                    pos_class = "style='background-color: #f0f8ff; font-weight: bold;'"  # Azul claro para 3º
                    
                # Determinar informações de base
                base_info = opcao.get('nome_base_origem', opcao.get('base_origem', 'N/A'))
                if opcao.get('tipo') == 'Agente' and opcao.get('base_destino_transferencia'):
                    base_info = f"{opcao.get('base_origem', 'N/A')} → {opcao.get('base_destino_transferencia', 'N/A')}"
                
                # Formatação do fornecedor
                fornecedor_info = opcao.get('modalidade', 'N/A')
                
                html += f"""
                        <tr {pos_class}>
                        <td>{i+1}º</td>
                        <td>{opcao.get('tipo', 'N/A').capitalize()}</td>
                        <td>{fornecedor_info}</td>
                        <td>{base_info}</td>
                        <td>R$ {opcao.get('total', 0):,.2f}</td>
                        <td>{opcao.get('prazo', 'N/A')} dias</td>
                        <td>
                            <button class="btn-mini" onclick="toggleDetails('detalhes_opcao_{i}')" style="font-size: 0.8rem;">
                                👁️ Ver
                                </button>
                            </td>
                        </tr>
                    <tr id="detalhes_opcao_{i}" style="display: none; background-color: #f9f9f9;">
                        <td colspan="7" style="padding: 10px;">
                                <div style="font-size: 0.85rem;">
                                <strong>Fornecedor:</strong> {fornecedor_info}<br>
                                <strong>Tipo:</strong> {opcao.get('tipo', 'N/A').capitalize()}<br>
                                <strong>Base Origem:</strong> {opcao.get('base_origem', 'N/A')}<br>
                                {'<strong>Base Destino:</strong> ' + opcao.get('base_destino_transferencia', 'N/A') + '<br>' if opcao.get('tipo') == 'Agente' else ''}
                                {'<strong>Agente Coleta:</strong> ' + opcao.get('fornecedor_coleta', 'N/A') + '<br>' if opcao.get('tipo') == 'Agente' else ''}
                                {'<strong>Transferência:</strong> ' + opcao.get('fornecedor_transferencia', 'N/A') + '<br>' if opcao.get('tipo') == 'Agente' else ''}
                                {'<strong>Agente Entrega:</strong> ' + opcao.get('fornecedor_entrega', 'N/A') + '<br>' if opcao.get('tipo') == 'Agente' else ''}
                                <strong>Valor Base:</strong> R$ {opcao.get('valor_base', 0):,.2f}<br>
                                <strong>Pedágio:</strong> R$ {opcao.get('pedagio', 0):,.2f}<br>
                                <strong>GRIS:</strong> R$ {opcao.get('gris', 0):,.2f}<br>
                                <strong>TOTAL:</strong> <span style="color: #e74c3c; font-weight: bold;">R$ {opcao.get('total', 0):,.2f}</span><br>
                                <strong>Prazo:</strong> {opcao.get('prazo', 'N/A')} dias úteis<br>
                                {'<strong>Observações:</strong> ' + opcao.get('observacoes', '') + '<br>' if opcao.get('observacoes') else ''}
                                        </div>
                            </td>
                        </tr>
                """
            
            html += """
                    </tbody>
                </table>
            </div>
            """
        
        html += """
        </div>
        """
        
        return html
        
    except Exception as e:
        print(f"Erro ao formatar resultado fracionado: {e}")
        return f"<div class='error'>Erro ao formatar resultado: {str(e)}</div>"

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

def calcular_frete_base_unificada(origem, uf_origem, destino, uf_destino, peso, valor_nf=None, cubagem=None, tipo_filtro=None):
    """
    Calcula o frete usando APENAS dados REAIS da Base_Unificada.xlsx
    SEM SIMULAÇÕES - SEM BUSCAS WEB - APENAS DADOS REAIS DA PLANILHA
    """
    print(f"[BASE_UNIFICADA] Calculando frete para {origem}/{uf_origem} → {destino}/{uf_destino}")
    print(f"[BASE_UNIFICADA] Peso: {peso}kg, Valor NF: {valor_nf}, Cubagem: {cubagem}")
    
    # Carregar base unificada
    df_base = carregar_base_unificada()
    if df_base is None:
        print("[BASE_UNIFICADA] Erro: Não foi possível carregar a base de dados")
        return None
    
    # Processar dados da planilha
    resultado = processar_dados_planilha(df_base, origem, uf_origem, destino, uf_destino, peso, valor_nf, cubagem, tipo_filtro)
    
    if not resultado or resultado.get('total_opcoes', 0) == 0:
        print(f"[BASE_UNIFICADA] Nenhuma opção encontrada para {origem} → {destino}")
        return None
    
    print(f"[BASE_UNIFICADA] ✅ {resultado['total_opcoes']} opções encontradas")
    return resultado

def processar_dados_planilha(df_base, origem, uf_origem, destino, uf_destino, peso, valor_nf, cubagem=None, tipo_filtro=None):
    """
    Processa os dados da planilha Base_Unificada.xlsx para encontrar cotações válidas
    """
    try:
        print(f"[PROCESSAR] Iniciando processamento para {origem}/{uf_origem} → {destino}/{uf_destino}")
        
        # Normalizar cidades para busca
        origem_norm = normalizar_cidade(origem)
        destino_norm = normalizar_cidade(destino)
        uf_origem_norm = normalizar_uf(uf_origem)
        uf_destino_norm = normalizar_uf(uf_destino)
        
        # Calcular peso cubado
        peso_real = float(peso)
        peso_cubado = float(cubagem) * 166 if cubagem and cubagem > 0 else peso_real * 0.17
        maior_peso = max(peso_real, peso_cubado)
        
        print(f"[PROCESSAR] Peso real: {peso_real}kg, Peso cubado: {peso_cubado:.2f}kg, Maior peso: {maior_peso:.2f}kg")
        
        # Aplicar filtros na base de dados
        df_filtrado = df_base.copy()
        
        # Filtrar por tipo se especificado
        if tipo_filtro and tipo_filtro in ['Agente', 'Transferência']:
            df_filtrado = df_filtrado[df_filtrado['Tipo'] == tipo_filtro]
            print(f"[PROCESSAR] Filtrado por tipo '{tipo_filtro}': {len(df_filtrado)} registros")
        
        # Normalizar as colunas de origem e destino para comparação
        df_filtrado['Origem_Normalizada'] = df_filtrado['Origem'].apply(normalizar_cidade)
        df_filtrado['Destino_Normalizado'] = df_filtrado['Destino'].apply(normalizar_cidade)
        
        # Buscar correspondências diretas
        cotacoes_encontradas = []
        
        # Primeira tentativa: correspondência exata
        matches = df_filtrado[
            (df_filtrado['Origem_Normalizada'] == origem_norm) &
            (df_filtrado['Destino_Normalizado'] == destino_norm)
        ]
        
        print(f"[PROCESSAR] Correspondência exata: {len(matches)} registros")
        
        # Se não encontrou, tentar correspondência por UF
        if matches.empty:
            # Buscar por bases que atendam as UFs
            matches = df_filtrado[
                (df_filtrado['Origem_Normalizada'].str.contains(uf_origem_norm, case=False, na=False)) &
                (df_filtrado['Destino_Normalizado'].str.contains(uf_destino_norm, case=False, na=False))
            ]
            print(f"[PROCESSAR] Correspondência por UF: {len(matches)} registros")
        
        # Processar cada correspondência encontrada
        for _, linha in matches.iterrows():
            try:
                # Determinar a coluna de peso a usar
                coluna_peso = determinar_coluna_peso(maior_peso)
                
                # Verificar se a coluna existe e tem valor válido
                if coluna_peso not in linha or pd.isna(linha[coluna_peso]) or linha[coluna_peso] <= 0:
                    continue
                
                # Calcular valor base
                valor_minimo = linha.get('VALOR MÍNIMO ATÉ 10', 0) or 0
                excedente = linha.get('EXCEDENTE', 0) or 0
                
                if maior_peso <= 10:
                    valor_base = valor_minimo
                else:
                    valor_faixa = linha.get(coluna_peso, 0) or 0
                    valor_pelo_excedente = maior_peso * excedente
                    valor_base = max(valor_minimo, min(valor_faixa, valor_pelo_excedente) if valor_faixa > 0 else valor_pelo_excedente)
                
                # Calcular pedágio
                pedagio_100kg = linha.get('Pedagio (100 Kg)', 0) or 0
                pedagio = (pedagio_100kg * maior_peso) / 100 if pedagio_100kg > 0 else 0
                
                # Calcular GRIS
                gris = 0
                if valor_nf and valor_nf > 0:
                    gris_min = linha.get('Gris Min', 0) or 0
                    gris_exc = linha.get('Gris Exc', 0) or 0
                    gris = max(gris_min, (float(valor_nf) * gris_exc / 100)) if gris_exc > 0 else gris_min
                
                # Calcular total
                total = valor_base + pedagio + gris
                
                # Obter prazo
                prazo = linha.get('Prazo', 1) or 1
                
                # Criar registro da cotação
                cotacao = {
                    'tipo': linha.get('Tipo', 'Direto'),
                    'modalidade': linha.get('Fornecedor', 'N/A'),
                    'fornecedor': linha.get('Fornecedor', 'N/A'),
                    'agente': '',
                    'fonte': 'Base_Unificada.xlsx',
                    'base_origem': linha.get('Base Origem', 'N/A'),
                    'nome_base_origem': MAPA_BASES.get(linha.get('Base Origem', ''), linha.get('Base Origem', 'N/A')),
                    'base_destino': linha.get('Base Destino', 'N/A'),
                    'origem': linha.get('Origem', origem),
                    'destino': linha.get('Destino', destino),
                    'valor_base': float(valor_base),
                    'pedagio': float(pedagio),
                    'gris': float(gris),
                    'total': float(total),
                    'prazo': int(prazo) if prazo else 1,
                    'peso_real': float(peso_real),
                    'peso_cubado': float(peso_cubado),
                    'maior_peso': float(maior_peso),
                    'peso_usado': 'Cubado' if maior_peso == peso_cubado else 'Real',
                    'coluna_peso_usada': str(coluna_peso),
                    'observacoes': f"Dados reais da planilha. Coluna de peso: {coluna_peso}. Valor base: R$ {valor_base:.2f}",
                    'detalhes': {
                        'calculo_detalhado': {
                            'valor_minimo': float(valor_minimo),
                            'excedente': float(excedente),
                            'valor_faixa': float(linha.get(coluna_peso, 0) or 0),
                            'pedagio_100kg': float(pedagio_100kg),
                            'gris_min': float(linha.get('Gris Min', 0) or 0),
                            'gris_exc': float(linha.get('Gris Exc', 0) or 0)
                        }
                    }
                }
                
                cotacoes_encontradas.append(cotacao)
                
                print(f"[PROCESSAR] ✅ Cotação: {linha.get('Fornecedor')} - R$ {total:.2f} (Base: {valor_base:.2f} + Pedágio: {pedagio:.2f} + GRIS: {gris:.2f})")
                
            except Exception as e:
                print(f"[PROCESSAR] Erro ao processar linha: {e}")
                continue
        
        # Ordenar por custo total
        cotacoes_encontradas = sorted(cotacoes_encontradas, key=lambda x: x['total'])
        
        # Contar fornecedores
        fornecedores_count = {}
        for cotacao in cotacoes_encontradas:
            fornecedor = cotacao['fornecedor']
            fornecedores_count[fornecedor] = fornecedores_count.get(fornecedor, 0) + 1
        
        resultado = {
            'cotacoes_ranking': cotacoes_encontradas,
            'total_opcoes': len(cotacoes_encontradas),
            'fornecedores_count': fornecedores_count,
            'dados_fonte': 'Base_Unificada.xlsx',
            'origem_pesquisada': origem,
            'destino_pesquisado': destino,
            'peso_usado': maior_peso,
            'filtros_aplicados': {
                'tipo_filtro': tipo_filtro,
                'origem_norm': origem_norm,
                'destino_norm': destino_norm
            }
        }
        
        print(f"[PROCESSAR] ✅ Processamento concluído: {len(cotacoes_encontradas)} cotações válidas")
        return resultado
        
    except Exception as e:
        print(f"[PROCESSAR] Erro no processamento: {e}")
        import traceback
        traceback.print_exc()
        return None

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
        
        # Calcular peso cubado
        peso_real = float(peso)
        peso_cubado = float(cubagem) * 166 if cubagem and cubagem > 0 else peso_real * 0.17
        maior_peso = max(peso_real, peso_cubado)
        
        # Definir bases disponíveis (conforme especificado pelo usuário)
        bases_disponiveis = {
            'RAO': 'Ribeirão Preto',  # Para cidades de SP interior
            'RIO': 'Rio de Janeiro',   # Para cidades do RJ
            'SAO': 'São Paulo',       # Para cidades de SP capital
            'POA': 'Porto Alegre',    # Para cidades do RS
            'CWB': 'Curitiba',        # Para cidades do PR
            'BHZ': 'Belo Horizonte',  # Para cidades de MG
            'BSB': 'Brasília',        # Para cidades do DF/GO
            'SSA': 'Salvador',        # Para cidades da BA
            'FOR': 'Fortaleza',       # Para cidades do CE
            'REC': 'Recife'           # Para cidades de PE
        }
        
        # Determinar base de origem baseada na UF de origem ou filtro especificado
        if base_filtro and base_filtro in bases_disponiveis:
            base_origem = base_filtro
        else:
            # Mapear UF para base mais próxima
            mapa_uf_base = {
                'SP': 'SAO' if 'SAO PAULO' in origem.upper() else 'RAO',
                'RJ': 'RIO',
                'MG': 'BHZ',
                'RS': 'POA',
                'PR': 'CWB',
                'DF': 'BSB',
                'GO': 'BSB',
                'BA': 'SSA',
                'CE': 'FOR',
                'PE': 'REC'
            }
            base_origem = mapa_uf_base.get(uf_origem, 'RAO')  # Default para RAO
        
        # Determinar base de destino baseada na UF de destino
        mapa_uf_base = {
            'SP': 'SAO' if 'SAO PAULO' in destino.upper() else 'RAO',
            'RJ': 'RIO',
            'MG': 'BHZ', 
            'RS': 'POA',
            'PR': 'CWB',
            'DF': 'BSB',
            'GO': 'BSB',
            'BA': 'SSA',
            'CE': 'FOR',
            'PE': 'REC'
        }
        base_destino = mapa_uf_base.get(uf_destino, 'RIO')  # Default para RIO
        
        print(f"[AGENTES] Base origem: {base_origem} ({bases_disponiveis.get(base_origem)})")
        print(f"[AGENTES] Base destino: {base_destino} ({bases_disponiveis.get(base_destino)})")
        
        rotas_encontradas = []
        
        # Se origem e destino são da mesma base, não usar agente (usar direto)
        if base_origem == base_destino:
            print(f"[AGENTES] Origem e destino na mesma base ({base_origem}), usando transferência direta")
            return None
        
        # 1. BUSCAR TRANSFERÊNCIA ENTRE BASES NA PLANILHA REAL
        transferencias_encontradas = []
        
        # Filtrar transferências diretas entre as bases na planilha
        origem_base = bases_disponiveis.get(base_origem, '')
        destino_base = bases_disponiveis.get(base_destino, '')
        
        # Normalizar nomes das bases para busca
        origem_base_norm = normalizar_cidade(origem_base)
        destino_base_norm = normalizar_cidade(destino_base)
        
        print(f"[AGENTES] Buscando transferência: {origem_base_norm} → {destino_base_norm}")
        
        # Buscar na base de dados por transferências entre bases
        transferencias_base = df_base[
            (df_base['Tipo'] == 'Transferência') |
            (df_base['Fornecedor'].str.contains('Jem|JEM|Dfl|DFL', case=False, na=False))
        ]
        
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
        
        for _, linha_trans in matches_transferencia.iterrows():
            try:
                # Calcular custo da transferência
                coluna_peso = determinar_coluna_peso(maior_peso)
                
                valor_minimo = linha_trans.get('VALOR MÍNIMO ATÉ 10', 0) or 0
                excedente = linha_trans.get('EXCEDENTE', 0) or 0
                
                if maior_peso <= 10:
                    custo_transferencia = valor_minimo
                else:
                    valor_faixa = linha_trans.get(coluna_peso, 0) or 0
                    valor_pelo_excedente = maior_peso * excedente
                    custo_transferencia = max(valor_minimo, min(valor_faixa, valor_pelo_excedente) if valor_faixa > 0 else valor_pelo_excedente)
                
                # Calcular pedágio da transferência
                pedagio_100kg = linha_trans.get('Pedagio (100 Kg)', 0) or 0
                pedagio_transferencia = (pedagio_100kg * maior_peso) / 100 if pedagio_100kg > 0 else 0
                
                # Calcular GRIS da transferência
                gris_transferencia = 0
                if valor_nf and valor_nf > 0:
                    gris_min = linha_trans.get('Gris Min', 0) or 0
                    gris_exc = linha_trans.get('Gris Exc', 0) or 0
                    gris_transferencia = max(gris_min, (float(valor_nf) * gris_exc / 100)) if gris_exc > 0 else gris_min
                
                transferencias_encontradas.append({
                    'fornecedor': linha_trans.get('Fornecedor', 'N/A'),
                    'custo': float(custo_transferencia),
                    'pedagio': float(pedagio_transferencia),
                    'gris': float(gris_transferencia),
                    'prazo': int(linha_trans.get('Prazo', 1) or 1),
                    'base_origem': base_origem,
                    'base_destino': base_destino
                })
                
                print(f"[AGENTES] ✅ Transferência: {linha_trans.get('Fornecedor')} - {origem_base} → {destino_base} - R$ {custo_transferencia:.2f}")
                
            except Exception as e:
                print(f"[AGENTES] Erro ao processar transferência: {e}")
                continue
        
        # 2. USAR APENAS TRANSFERÊNCIAS REAIS DA BASE DE DADOS
        # Sistema agora trabalha exclusivamente com fornecedores reais
        
        # 3. USAR APENAS TRANSFERÊNCIAS REAIS - SEM AGENTES FICTÍCIOS
        # Retornar apenas as transferências reais encontradas na base
        for transferencia in transferencias_encontradas:
            try:
                rota = {
                    'fornecedor_transferencia': transferencia['fornecedor'],
                    'transferencia': {
                        'base_origem': base_origem,
                        'base_destino': base_destino,
                        'custo': float(transferencia['custo']),
                        'pedagio': float(transferencia['pedagio']),
                        'gris': float(transferencia['gris'])
                    },
                    'total': float(transferencia['custo'] + transferencia['pedagio'] + transferencia['gris']),
                    'prazo_total': int(transferencia['prazo']),
                    'peso_real': float(peso_real),
                    'peso_cubado': float(peso_cubado),
                    'maior_peso': float(maior_peso),
                    'peso_usado': 'Cubado' if maior_peso == peso_cubado else 'Real',
                    'base_origem': base_origem,
                    'base_destino_transferencia': base_destino,
                    'detalhamento_custos': {
                        'transferencia': float(transferencia['custo']),
                        'pedagio': float(transferencia['pedagio']),
                        'gris_total': float(transferencia['gris'])
                    }
                }
                
                rotas_encontradas.append(rota)
                
                print(f"[AGENTES] ✅ Transferência real: {transferencia['fornecedor']} - R$ {rota['total']:.2f}")
                
            except Exception as e:
                print(f"[AGENTES] Erro ao processar transferência: {e}")
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
        print(f"[AGENTES] Erro no cálculo de agentes: {e}")
        import traceback
        traceback.print_exc()
        return None

def determinar_coluna_peso(peso):
    """
    Determina a coluna de peso a ser usada com base no peso da carga
    """
    if peso <= 10:
        return 'VALOR MÍNIMO ATÉ 10'
    elif peso <= 20:
        return 20
    elif peso <= 30:
        return 30
    elif peso <= 50:
        return 50
    elif peso <= 70:
        return 70
    elif peso <= 100:
        return 100
    elif peso <= 300:
        return 300
    elif peso <= 500:
        return 500
    else:
        return 'Acima 500'

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
