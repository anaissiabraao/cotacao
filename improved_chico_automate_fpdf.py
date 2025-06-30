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
        
        # Tentar obter do cache primeiro
        from utils.coords_cache import get_coords
        coords_cache = get_coords(cidade_norm, uf_norm)
        if coords_cache:
            return coords_cache
            
        # Se não estiver no cache, tentar API
        query = f"{cidade_norm}, {uf_norm}, Brasil"
        url = f"https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": 1}
        headers = {"User-Agent": "PortoEx/1.0"}
        
        try:
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
                
        except Exception as e:
            print(f"[geocode] Erro ao geocodificar {municipio}, {uf}: {str(e)}")
            # Em caso de erro na API, tentar usar cache como fallback
            return coords_cache
            
        return None
    except Exception as e:
        print(f"[geocode] Erro geral ao geocodificar {municipio}, {uf}: {str(e)}")
        return None
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

def calcular_frete_aereo_base_unificada(origem, uf_origem, destino, uf_destino, peso, valor_nf=None):
    """
    Calcular frete aéreo usando a Base Unificada (tipo 'Aéreo')
    """
    try:
        print(f"[AÉREO] Calculando frete aéreo: {origem}/{uf_origem} → {destino}/{uf_destino}")
        print(f"[AÉREO] Peso: {peso}kg, Valor NF: R$ {valor_nf:,}" if valor_nf else f"[AÉREO] Peso: {peso}kg")
        
        # Carregar base unificada
        df = carregar_base_unificada()
        if df is None or df.empty:
            print("[AÉREO] ❌ Erro ao carregar base unificada")
            return None
            
        # Filtrar apenas registros do tipo 'Aéreo'
        df_aereo = df[df['Tipo'] == 'Aéreo'].copy()
        print(f"[AÉREO] Registros aéreos na base: {len(df_aereo)}")
        
        if df_aereo.empty:
            print("[AÉREO] ❌ Nenhum registro aéreo encontrado na base")
            return None
        
        # Normalizar origem e destino
        origem_norm = normalizar_cidade_nome(origem)
        destino_norm = normalizar_cidade_nome(destino)
        uf_origem_norm = normalizar_uf(uf_origem)
        uf_destino_norm = normalizar_uf(uf_destino)
        
        print(f"[AÉREO] Buscando: {origem_norm}/{uf_origem_norm} → {destino_norm}/{uf_destino_norm}")
        
        # Buscar rotas aéreas correspondentes
        opcoes_aereas = []
        
        for _, linha in df_aereo.iterrows():
            origem_base = normalizar_cidade_nome(str(linha.get('Origem', '')))
            destino_base = normalizar_cidade_nome(str(linha.get('Destino', '')))
            
            # Verificar se a rota corresponde
            if origem_base == origem_norm and destino_base == destino_norm:
                try:
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
                    
                    # GRIS para aéreo (se informado)
                    gris_valor = 0
                    if valor_nf and valor_nf > 0:
                        gris_perc = float(linha.get('Gris Exc', 0)) / 100
                        gris_valor = valor_nf * gris_perc
                    
                    # Pedágio (normalmente zero para aéreo)
                    pedagio = float(linha.get('Pedagio (100 Kg)', 0)) * (peso_float / 100)
                    
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
                    
                except Exception as e:
                    print(f"[AÉREO] ⚠️ Erro ao processar linha: {e}")
                    continue
        
        if not opcoes_aereas:
            print(f"[AÉREO] ❌ Nenhuma rota aérea encontrada para {origem_norm} → {destino_norm}")
            return None
        
        # Ordenar por menor custo
        opcoes_aereas.sort(key=lambda x: x['total'])
        
        resultado = {
            'opcoes': opcoes_aereas,
            'total_opcoes': len(opcoes_aereas),
            'melhor_opcao': opcoes_aereas[0] if opcoes_aereas else None,
            'origem': origem,
            'uf_origem': uf_origem,
            'destino': destino,
            'uf_destino': uf_destino,
            'peso': peso,
            'valor_nf': valor_nf
        }
        
        print(f"[AÉREO] ✅ {len(opcoes_aereas)} opções aéreas encontradas")
        return resultado
        
    except Exception as e:
        print(f"[AÉREO] ❌ Erro no cálculo aéreo: {e}")
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

# Função removida - duplicada (versão correta mantida na linha 653)

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

def calcular_frete_aereo_base_unificada(origem, uf_origem, destino, uf_destino, peso, valor_nf=None):
    """
    Calcular frete aéreo usando a Base Unificada (tipo 'Aéreo')
    """
    try:
        print(f"[AÉREO] Calculando frete aéreo: {origem}/{uf_origem} → {destino}/{uf_destino}")
        print(f"[AÉREO] Peso: {peso}kg, Valor NF: R$ {valor_nf:,}" if valor_nf else f"[AÉREO] Peso: {peso}kg")
        
        # Carregar base unificada
        df = carregar_base_unificada()
        if df is None or df.empty:
            print("[AÉREO] ❌ Erro ao carregar base unificada")
            return None
            
        # Filtrar apenas registros do tipo 'Aéreo'
        df_aereo = df[df['Tipo'] == 'Aéreo'].copy()
        print(f"[AÉREO] Registros aéreos na base: {len(df_aereo)}")
        
        if df_aereo.empty:
            print("[AÉREO] ❌ Nenhum registro aéreo encontrado na base")
            return None
        
        # Normalizar origem e destino
        origem_norm = normalizar_cidade_nome(origem)
        destino_norm = normalizar_cidade_nome(destino)
        uf_origem_norm = normalizar_uf(uf_origem)
        uf_destino_norm = normalizar_uf(uf_destino)
        
        print(f"[AÉREO] Buscando: {origem_norm}/{uf_origem_norm} → {destino_norm}/{uf_destino_norm}")
        
        # Buscar rotas aéreas correspondentes
        opcoes_aereas = []
        
        for _, linha in df_aereo.iterrows():
            origem_base = normalizar_cidade_nome(str(linha.get('Origem', '')))
            destino_base = normalizar_cidade_nome(str(linha.get('Destino', '')))
            
            # Verificar se a rota corresponde
            if origem_base == origem_norm and destino_base == destino_norm:
                try:
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
                    
                    # GRIS para aéreo (se informado)
                    gris_valor = 0
                    if valor_nf and valor_nf > 0:
                        gris_perc = float(linha.get('Gris Exc', 0)) / 100
                        gris_valor = valor_nf * gris_perc
                    
                    # Pedágio (normalmente zero para aéreo)
                    pedagio = float(linha.get('Pedagio (100 Kg)', 0)) * (peso_float / 100)
                    
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
                    
                except Exception as e:
                    print(f"[AÉREO] ⚠️ Erro ao processar linha: {e}")
                    continue
        
        if not opcoes_aereas:
            print(f"[AÉREO] ❌ Nenhuma rota aérea encontrada para {origem_norm} → {destino_norm}")
            return None
        
        # Ordenar por menor custo
        opcoes_aereas.sort(key=lambda x: x['total'])
        
        resultado = {
            'opcoes': opcoes_aereas,
            'total_opcoes': len(opcoes_aereas),
            'melhor_opcao': opcoes_aereas[0] if opcoes_aereas else None,
            'origem': origem,
            'uf_origem': uf_origem,
            'destino': destino,
            'uf_destino': uf_destino,
            'peso': peso,
            'valor_nf': valor_nf
        }
        
        print(f"[AÉREO] ✅ {len(opcoes_aereas)} opções aéreas encontradas")
        return resultado
        
    except Exception as e:
        print(f"[AÉREO] ❌ Erro no cálculo aéreo: {e}")
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
    log_debug(f"[AGENTES] Calculando rotas com agentes: {origem}/{uf_origem} → {destino}/{uf_destino}")
    log_debug(f"[AGENTES] Peso: {peso}kg, Base filtro: {base_filtro}")
    
    try:
        # Carregar base unificada para usar dados reais de transferência
        df_base = carregar_base_unificada()
        if df_base is None:
            log_debug("[AGENTES] Erro: Não foi possível carregar a base de dados")
            return None

        # Carregar base de agentes reais
        dados_agentes = carregar_base_agentes()
        if dados_agentes is None:
            log_debug("[AGENTES] Erro: Não foi possível carregar a base de agentes")
            return None
        
        # Desempacotar os dados retornados pela função
        df_agentes, df_transferencias = dados_agentes
        
        # Calcular peso cubado diferenciado: 166 para fracionado, 250 para diretos
        peso_real = float(peso)
        
        # Função para calcular peso cubado baseado no tipo de serviço
        def calcular_peso_cubado_por_tipo(cubagem_m3, tipo_servico='fracionado'):
            if not cubagem_m3 or cubagem_m3 <= 0:
                return peso_real * 0.17  # Fallback padrão
            
            if tipo_servico == 'direto':
                return float(cubagem_m3) * 250  # 250 kg/m³ para diretos
            else:
                return float(cubagem_m3) * 166  # 166 kg/m³ para fracionado
        
        # Para esta função, usar peso cubado fracionado como base (será recalculado para diretos)
        peso_cubado_fracionado = calcular_peso_cubado_por_tipo(cubagem, 'fracionado')
        peso_cubado_direto = calcular_peso_cubado_por_tipo(cubagem, 'direto')
        
        # Usar peso cubado fracionado para transferências e agentes tradicionais
        maior_peso_fracionado = max(peso_real, peso_cubado_fracionado)
        # Usar peso cubado direto para agentes diretos
        maior_peso_direto = max(peso_real, peso_cubado_direto)
        
        log_debug(f"[AGENTES] Peso real: {peso_real}kg")
        log_debug(f"[AGENTES] Peso cubado fracionado (166): {peso_cubado_fracionado:.2f}kg")
        log_debug(f"[AGENTES] Peso cubado direto (250): {peso_cubado_direto:.2f}kg")
        log_debug(f"[AGENTES] Maior peso fracionado: {maior_peso_fracionado:.2f}kg")
        log_debug(f"[AGENTES] Maior peso direto: {maior_peso_direto:.2f}kg")
        
        # Para compatibilidade com código existente
        maior_peso = maior_peso_fracionado
        
        # NORMALIZAR CIDADES NO INÍCIO (para uso geral)
        origem_normalizada = normalizar_cidade(origem)
        destino_normalizado = normalizar_cidade(destino)
        
        # Definir bases disponíveis (conforme especificado pelo usuário)
        bases_disponiveis = {
            'FILIAL': 'São Paulo',        # Base real na planilha - SOMENTE São Paulo Capital
            'RAO': 'Ribeirão Preto',      # Base real na planilha - Ribeirão Preto
            'SJP': 'São José do Rio Preto', # Base real na planilha - São José do Rio Preto
            'MII': 'Minas Gerais',       # Base real na planilha  
            'SJK': 'São José dos Campos', # Base real na planilha
            'RIO': 'Rio de Janeiro',      # Base real na planilha
            'POA': 'Porto Alegre',       # Para cidades do RS
            'CWB': 'Curitiba',           # Para cidades do PR
            'LDB': 'Londrina',           # Base real na planilha - LONDRINA
            'ITJ': 'Itajaí',             # Para cidades de SC - NOVA BASE
            'CCM': 'Criciúma',           # Base SC adicional
            'CXJ': 'Caxias do Sul',      # Base RS adicional  
            'BHZ': 'Belo Horizonte',     # Para cidades de MG
            'BSB': 'Brasília',           # Para cidades do DF
            'GYN': 'Goiânia',            # Para cidades de GO - NOVA BASE
            'APS': 'Anápolis',           # Base GO adicional
            'UDI': 'Uberlândia',         # Base MG/GO adicional
            'CPQ': 'Campinas',           # Base SP adicional
            'PPB': 'Piracicaba',         # Base SP adicional
            'SSZ': 'Suzano',             # Base SP adicional
            'QVR': 'Queimados',          # Base RJ adicional  
            'CAW': 'Campos dos Goytacazes', # Base RJ adicional
            'JDF': 'Juiz de Fora',       # Base MG/RJ adicional
            'VAG': 'Varginha',           # Base MG adicional
            'POO': 'Poços de Caldas',    # Base MG adicional
            'PPY': 'Pouso Alegre',       # Base MG adicional
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
                elif origem_normalizada == 'SAO JOSE DO RIO PRETO':
                    base_origem = 'SJP'     # São José do Rio Preto usa SJP
                else:
                    base_origem = 'FILIAL'  # Outras cidades SP usam FILIAL como padrão
            else:
                mapa_uf_base = {
                    'RJ': 'RIO',
                    'MG': 'BHZ',     # Minas Gerais usa BHZ (Belo Horizonte) - CORRIGIDO  
                    'RS': 'POA',
                    'PR': 'CWB',
                    'SC': 'ITJ',     # Santa Catarina usa ITJ (Itajaí) - NOVO
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
            # São Paulo: FILIAL só atende São Paulo Capital, RAO atende Ribeirão Preto, SJP atende São José do Rio Preto
            destino_normalizado = normalizar_cidade(destino)
            if destino_normalizado == 'SAO PAULO':
                base_destino = 'FILIAL'  # São Paulo Capital usa FILIAL
            elif destino_normalizado == 'RIBEIRAO PRETO':
                base_destino = 'RAO'     # Ribeirão Preto usa RAO
            elif destino_normalizado == 'SAO JOSE DO RIO PRETO':
                base_destino = 'SJP'     # São José do Rio Preto usa SJP
            else:
                base_destino = 'FILIAL'  # Outras cidades SP usam FILIAL como padrão
        else:
            mapa_uf_base = {
                'RJ': 'RIO',
                'MG': 'BHZ',     # Minas Gerais usa BHZ (Belo Horizonte) - CORRIGIDO
                'RS': 'POA',
                'PR': 'CWB',
                'SC': 'ITJ',     # Santa Catarina usa ITJ (Itajaí) - NOVO
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
            base_destino = mapa_uf_base.get(uf_destino, 'FILIAL')  # Default para FILIAL ao invés de RIO
        
        log_debug(f"[AGENTES] Base origem: {base_origem} ({bases_disponiveis.get(base_origem)})")
        log_debug(f"[AGENTES] Base destino: {base_destino} ({bases_disponiveis.get(base_destino)})")
        
        # Debug: verificar se RAO e FILIAL estão sendo usados corretamente
        if base_origem == 'FILIAL':
            log_debug(f"[AGENTES] ✅ FILIAL sendo usada para origem: {origem} (São Paulo Capital)")
        elif base_origem == 'RAO':
            log_debug(f"[AGENTES] ✅ RAO sendo usada para origem: {origem} (Ribeirão Preto)")
        
        if base_destino == 'FILIAL':
            log_debug(f"[AGENTES] ✅ FILIAL sendo usada para destino: {destino} (São Paulo Capital)")
        elif base_destino == 'RAO':
            log_debug(f"[AGENTES] ✅ RAO sendo usada para destino: {destino} (Ribeirão Preto)")
        
        rotas_encontradas = []
        
        # LÓGICA SIMPLIFICADA: USAR APENAS A BASE DE ORIGEM DIRETA
        # Remover lógica de múltiplas bases por UF
        transferencias_encontradas = []
        
        # BUSCAR TRANSFERÊNCIAS APENAS ENTRE BASE ORIGEM → BASE DESTINO
        transferencias_base = df_transferencias.copy()
        transferencias_base['Origem_Normalizada'] = transferencias_base['Origem'].apply(normalizar_cidade)
        transferencias_base['Destino_Normalizado'] = transferencias_base['Destino'].apply(normalizar_cidade)
        
        log_debug(f"[AGENTES] Buscando transferência direta: {base_origem} → {base_destino}")
        
        # Obter nomes das bases para busca
        origem_base = bases_disponiveis.get(base_origem, '')
        destino_base = bases_disponiveis.get(base_destino, '')
        
        if origem_base and destino_base and base_origem != base_destino:
            # Normalizar nomes das bases para busca
            origem_base_norm = normalizar_cidade(origem_base)
            destino_base_norm = normalizar_cidade(destino_base)
            
            log_debug(f"[AGENTES] Buscando transferência: {origem_base_norm} → {destino_base_norm}")
            
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
            
            # Processar transferências encontradas
            for _, linha_trans in matches_transferencia.iterrows():
                try:
                    linha_processada = processar_linha_transferencia(linha_trans, maior_peso, valor_nf)
                    if linha_processada:
                        # Adicionar informações da combinação de bases
                        linha_processada['base_origem_codigo'] = base_origem
                        linha_processada['base_destino_codigo'] = base_destino
                        linha_processada['rota_bases'] = f"{base_origem} → {base_destino}"
                        
                        # Determinar tipo de rota
                        if uf_origem == uf_destino:
                            linha_processada['tipo_rota'] = 'local_com_transferencia'
                            tipo_rota = "LOCAL"
                        else:
                            linha_processada['tipo_rota'] = 'interestadual'
                            tipo_rota = "INTERESTADUAL"
                        
                        transferencias_encontradas.append(linha_processada)
                        log_debug(f"[AGENTES] ✅ Transferência {tipo_rota}: {linha_trans.get('Fornecedor')} - {origem_base} → {destino_base} - R$ {linha_processada['custo']:.2f}")
                    
                except Exception as e:
                    log_debug(f"[AGENTES] Erro ao processar transferência: {e}")
                    continue
        
        log_debug(f"[AGENTES] Total de transferências encontradas: {len(transferencias_encontradas)}")
        
        # 2. BUSCAR AGENTES REAIS NA BASE DE DADOS
        # Carregar base de agentes (retorna tupla: agentes, transferencias)
        resultado_base = carregar_base_agentes()
        if resultado_base is None:
            log_debug("[AGENTES] Erro ao carregar base de agentes")
            return None
        
        df_agentes, df_transferencias = resultado_base
        
        # Verificar se df_agentes foi carregado corretamente
        if df_agentes is None or df_agentes.empty:
            log_debug("[AGENTES] Base de agentes vazia ou não carregada")
            return None
        
        log_debug(f"[AGENTES] Colunas disponíveis na base de agentes: {list(df_agentes.columns)}")
        
        # Carregar base completa para incluir agentes diretos
        df_base_completa = carregar_base_completa()
        if df_base_completa is None:
            log_debug("[AGENTES] Erro ao carregar base completa")
            return None
        
        # Adicionar normalização para busca
        if 'Origem_Normalizada' not in df_base_completa.columns:
            df_base_completa['Origem_Normalizada'] = df_base_completa['Origem'].apply(normalizar_cidade)
        if 'Destino_Normalizado' not in df_base_completa.columns:
            df_base_completa['Destino_Normalizado'] = df_base_completa['Destino'].apply(normalizar_cidade)
        
        # NOVA LÓGICA: Agentes fazem coleta/entrega entre cidade do cliente e base
        # Busca flexível considerando múltiplas bases possíveis para uma UF
        
        # Adicionar normalização para busca
        if 'Origem_Normalizada' not in df_agentes.columns:
            df_agentes['Origem_Normalizada'] = df_agentes['Origem'].apply(normalizar_cidade)
        if 'Destino_Normalizado' not in df_agentes.columns:
            df_agentes['Destino_Normalizado'] = df_agentes['Destino'].apply(normalizar_cidade)
        
        # 1. BUSCAR AGENTES DIRETOS (PORTA-A-PORTA) - NOVA FUNCIONALIDADE
        log_debug(f"[AGENTES] 🚀 Buscando agentes diretos (porta-a-porta)...")
        agentes_diretos = df_base_completa[
            (df_base_completa['Tipo'] == 'Direto') &
            (df_base_completa['Origem_Normalizada'] == origem_normalizada) &
            (df_base_completa['Destino_Normalizado'] == destino_normalizado)
        ]
        
        log_debug(f"[AGENTES] Agentes diretos encontrados: {len(agentes_diretos)}")
        
        # Processar agentes diretos (sem transferência)
        for _, agente_direto in agentes_diretos.iterrows():
            try:
                # Validar se agente tem valores válidos
                colunas_peso = [col for col in agente_direto.index if isinstance(col, int) or col in ['VALOR MÍNIMO ATÉ 10', 'Acima 500']]
                valores_peso = [agente_direto.get(col, 0) for col in colunas_peso]
                
                # Pular agentes com todos valores zerados
                if all(v == 0 or pd.isna(v) for v in valores_peso):
                    log_debug(f"[AGENTES] ❌ Agente direto {agente_direto.get('Fornecedor')} pulado - valores zerados")
                    continue
                
                # Validar peso máximo do agente direto (USAR PESO DIRETO)
                validacao_peso_direto = validar_peso_maximo_agente(agente_direto, maior_peso_direto, "Agente Direto")
                
                # Processar linha do agente direto (USAR PESO DIRETO)
                linha_direto_processada = processar_linha_transferencia(agente_direto, maior_peso_direto, valor_nf)
                if not linha_direto_processada:
                    continue
                
                # ROTA DIRETA (SEM TRANSFERÊNCIA) - INCLUIR TDA E SEGURO
                total_rota_direta = (linha_direto_processada['custo'] + 
                                   linha_direto_processada['pedagio'] + 
                                   linha_direto_processada['gris'] +
                                   linha_direto_processada.get('tda', 0) +  # INCLUIR TDA
                                   linha_direto_processada.get('seguro', 0))  # INCLUIR SEGURO
                
                rota_direta = {
                    'tipo_rota': 'direta',
                    'fornecedor_direto': agente_direto.get('Fornecedor', 'N/A'),
                    'agente_direto': {
                        'fornecedor': agente_direto.get('Fornecedor', 'N/A'),
                        'origem': agente_direto.get('Origem', origem),
                        'destino': agente_direto.get('Destino', destino),
                        'base_origem': agente_direto.get('Base Origem', 'N/A'),
                        'custo': float(linha_direto_processada['custo']),
                        'pedagio': float(linha_direto_processada['pedagio']),
                        'gris': float(linha_direto_processada['gris']),
                        'tda': float(linha_direto_processada.get('tda', 0)),  # INCLUIR TDA
                        'seguro': float(linha_direto_processada.get('seguro', 0)),  # INCLUIR SEGURO
                        'prazo': linha_direto_processada['prazo'],
                        'peso_maximo': agente_direto.get('PESO MÁXIMO TRANSPORTADO', 'N/A'),
                        'validacao_peso': validacao_peso_direto
                    },
                    'total': float(total_rota_direta),
                    'prazo_total': int(linha_direto_processada['prazo']),
                    'peso_real': float(peso_real),
                    'peso_cubado': float(peso_cubado_direto),
                    'maior_peso': float(maior_peso_direto),
                    'peso_usado': 'Cubado' if maior_peso_direto == peso_cubado_direto else 'Real',
                    'resumo': f"DIRETO: {agente_direto.get('Fornecedor', 'N/A')} (Porta-a-Porta)",
                    'observacoes': "🚀 Serviço DIRETO porta-a-porta - sem transferência",
                    'detalhamento_custos': {
                        'servico_direto': float(linha_direto_processada['custo']),
                        'pedagio': float(linha_direto_processada['pedagio']),
                        'gris_total': float(linha_direto_processada['gris']),
                        'tda': float(linha_direto_processada.get('tda', 0)),  # INCLUIR TDA NO DETALHAMENTO
                        'seguro': float(linha_direto_processada.get('seguro', 0))  # INCLUIR SEGURO NO DETALHAMENTO
                    },
                    'alertas_peso': {
                        'tem_alerta': not validacao_peso_direto['valido'],
                        'alertas': [validacao_peso_direto.get('alerta')] if validacao_peso_direto.get('alerta') else []
                    }
                }
                
                rotas_encontradas.append(rota_direta)
                log_debug(f"[AGENTES] ✅ DIRETO: {agente_direto.get('Fornecedor')} - R$ {total_rota_direta:.2f}")
                
            except Exception as e:
                log_debug(f"[AGENTES] Erro ao processar agente direto: {e}")
                continue
        
        # 2. BUSCAR AGENTES TRADICIONAIS (COM TRANSFERÊNCIA)
        log_debug(f"[AGENTES] 🔄 Buscando agentes para rota {uf_origem} → {uf_destino}...")
        
        # BUSCA AMPLA DE AGENTES - NÃO RESTRINGIR APENAS ÀS BASES ESPECÍFICAS
        # Agentes de COLETA: buscam na cidade de origem (qualquer base)
        agentes_coleta = df_agentes[
            (df_agentes['Tipo'] == 'Agente') &
            (df_agentes['Origem_Normalizada'] == origem_normalizada)
        ]
        
        # Agentes de ENTREGA: operam a partir da base de destino
        # Como o campo 'Destino' está vazio nos agentes, vamos buscar por base
        agentes_entrega = df_agentes[
            (df_agentes['Tipo'] == 'Agente') &
            (df_agentes['Base Origem'] == base_destino)
        ]
        
        # BUSCA ADICIONAL: Agentes que atendem a cidade de destino diretamente
        agentes_entrega_diretos = df_agentes[
            (df_agentes['Tipo'] == 'Agente') &
            (df_agentes['Origem_Normalizada'] == destino_normalizado)
        ]
        
        # Combinar agentes de entrega (por base + diretos na cidade)
        agentes_entrega = pd.concat([agentes_entrega, agentes_entrega_diretos]).drop_duplicates()

        # Filtrar agentes com valores válidos
        def filtrar_agentes_validos(agentes_df):
            agentes_validos = []
            for _, agente in agentes_df.iterrows():
                colunas_peso = [col for col in agente.index if isinstance(col, int) or col in ['VALOR MÍNIMO ATÉ 10', 'Acima 500']]
                valores_peso = [agente.get(col, 0) for col in colunas_peso]
                
                # Manter apenas agentes com pelo menos um valor > 0
                if any(v > 0 and not pd.isna(v) for v in valores_peso):
                    agentes_validos.append(agente)
                else:
                    log_debug(f"[AGENTES] ❌ Agente {agente.get('Fornecedor')} pulado - valores zerados")
            
            return pd.DataFrame(agentes_validos) if agentes_validos else pd.DataFrame()
        
        agentes_coleta = filtrar_agentes_validos(agentes_coleta)
        agentes_entrega = filtrar_agentes_validos(agentes_entrega)
        
        log_debug(f"[AGENTES] Agentes de coleta encontrados: {len(agentes_coleta)}")
        log_debug(f"[AGENTES] Agentes de entrega encontrados: {len(agentes_entrega)}")
        
        # 3. COMBINAR COLETA + TRANSFERÊNCIA + ENTREGA COM DADOS REAIS
        # TODOS OS AGENTES DEVEM SER CONECTADOS POR TRANSFERÊNCIAS REAIS
        
        # 3.1 ROTAS COMPLETAS (Agente Coleta + Transferência + Agente Entrega)
        log_debug(f"[AGENTES] 🔄 Tentando rotas completas com transferência...")
        rotas_completas = 0
        for _, agente_col in agentes_coleta.iterrows():
            for transferencia in transferencias_encontradas:
                for _, agente_ent in agentes_entrega.iterrows():
                    try:
                        # Validar peso máximo do agente de coleta
                        validacao_coleta = validar_peso_maximo_agente(agente_col, maior_peso, "Agente de Coleta")
                        
                        # Validar peso máximo do agente de entrega
                        validacao_entrega = validar_peso_maximo_agente(agente_ent, maior_peso, "Agente de Entrega")
                        
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
                        
                        # Verificar se as bases das transferências coincidem com agentes
                        base_coleta = agente_col.get('Base Origem', 'N/A')
                        base_entrega = agente_ent.get('Base Origem', 'N/A')
                        base_origem_transferencia = transferencia.get('base_origem_codigo', base_origem)
                        base_destino_transferencia = transferencia.get('base_destino_codigo', base_destino)
                        
                        # Criar rota completa
                        rota = {
                            'tipo_rota': transferencia.get('tipo_rota', 'completa'),
                            'fornecedor_coleta': agente_col.get('Fornecedor', 'N/A'),
                            'fornecedor_transferencia': transferencia['fornecedor'],
                            'agente_entrega': {'fornecedor': agente_ent.get('Fornecedor', 'N/A')},
                            'agente_coleta': {
                                'base_origem': origem,
                                'base_destino': base_coleta,
                                'custo': float(linha_coleta_processada['custo']),
                                'pedagio': float(linha_coleta_processada['pedagio']),
                                'gris': float(linha_coleta_processada['gris']),
                                'origem': agente_col.get('Origem', ''),
                                'destino': agente_col.get('Destino', ''),
                                'fornecedor': agente_col.get('Fornecedor', 'N/A'),
                                'prazo': linha_coleta_processada['prazo'],
                                'peso_maximo': agente_col.get('PESO MÁXIMO TRANSPORTADO', 'N/A'),
                                'validacao_peso': validacao_coleta
                            },
                            'transferencia': {
                                'base_origem': base_origem_transferencia,
                                'base_destino': base_destino_transferencia,
                                'custo': float(transferencia['custo']),
                                'pedagio': float(transferencia['pedagio']),
                                'gris': float(transferencia['gris']),
                                'fornecedor': transferencia['fornecedor'],
                                'origem': f"Base {base_origem_transferencia}",
                                'destino': f"Base {base_destino_transferencia}",
                                'prazo': transferencia['prazo'],
                                'frete': float(transferencia['custo']) - float(transferencia['pedagio']) - float(transferencia['gris']),
                                'rota_bases': transferencia.get('rota_bases', f"{base_origem_transferencia} → {base_destino_transferencia}")
                            },
                            'agente_entrega_detalhes': {
                                'base_origem': base_entrega,
                                'base_destino': destino,
                                'custo': float(linha_entrega_processada['custo']),
                                'origem': agente_ent.get('Origem', ''),
                                'destino': agente_ent.get('Destino', ''),
                                'fornecedor': agente_ent.get('Fornecedor', 'N/A')
                            },
                            'agente_entrega': {
                                'fornecedor': agente_ent.get('Fornecedor', 'N/A'),
                                'base_origem': base_entrega,
                                'destino': destino,
                                'custo': float(linha_entrega_processada['custo']),
                                'pedagio': float(linha_entrega_processada['pedagio']),
                                'gris': float(linha_entrega_processada['gris']),
                                'valor_minimo': float(agente_ent.get('VALOR MÍNIMO ATÉ 10', 0) or 0),
                                'excedente': float(agente_ent.get('EXCEDENTE', 0) or 0),
                                'prazo': linha_entrega_processada['prazo'],
                                'peso_maximo': agente_ent.get('PESO MÁXIMO TRANSPORTADO', 'N/A'),
                                'validacao_peso': validacao_entrega
                            },
                            'total': float(total_rota),
                            'prazo_total': int(prazo_total),
                            'peso_real': float(peso_real),
                            'peso_cubado': float(peso_cubado_fracionado),
                            'maior_peso': float(maior_peso_fracionado),
                            'peso_usado': 'Cubado' if maior_peso_fracionado == peso_cubado_fracionado else 'Real',
                            'base_origem': base_origem_transferencia,
                            'base_destino_transferencia': base_destino_transferencia,
                            'resumo': f"{agente_col.get('Fornecedor', 'N/A')} + {transferencia['fornecedor']} + {agente_ent.get('Fornecedor', 'N/A')}",
                            'detalhamento_custos': {
                                'coleta': float(linha_coleta_processada['custo']),
                                'transferencia': float(transferencia['custo']),
                                'entrega': float(linha_entrega_processada['custo']),
                                'pedagio': float(linha_coleta_processada['pedagio'] + transferencia['pedagio'] + linha_entrega_processada['pedagio']),
                                'gris_total': float(linha_coleta_processada['gris'] + transferencia['gris'] + linha_entrega_processada['gris']),
                                'seguro': float(linha_entrega_processada.get('seguro', 0))  # INCLUIR SEGURO NO DETALHAMENTO
                            },
                            'alertas_peso': {
                                'tem_alerta': not validacao_coleta['valido'] or not validacao_entrega['valido'],
                                'alertas': [alerta for alerta in [validacao_coleta.get('alerta'), validacao_entrega.get('alerta')] if alerta]
                            }
                        }
                        
                        rotas_encontradas.append(rota)
                        rotas_completas += 1
                        
                        tipo_rota_desc = "LOCAL" if transferencia.get('tipo_rota') == 'local_com_transferencia' else "COMPLETA"
                        print(f"[AGENTES] ✅ Rota {tipo_rota_desc}: {agente_col.get('Fornecedor')} (R$ {linha_coleta_processada['custo']:.2f}) + {transferencia['fornecedor']} (R$ {transferencia['custo']:.2f}) + {agente_ent.get('Fornecedor')} (R$ {linha_entrega_processada['custo']:.2f}) = R$ {total_rota:.2f}")
                        
                    except Exception as e:
                        print(f"[AGENTES] Erro ao combinar rota: {e}")
                        continue
        
        print(f"[AGENTES] ✅ {rotas_completas} rotas completas encontradas")
        
        # 3.2 ROTAS PARCIAIS - APENAS TRANSFERÊNCIA + AGENTE ENTREGA
        # SEMPRE EXECUTAR ESTA SEÇÃO PARA OFERECER MAIS OPÇÕES
        if not agentes_entrega.empty:
            print(f"[AGENTES] 🔄 Calculando rotas parciais: Transferência + Agente Entrega ({len(agentes_entrega)} agentes)")
            
            # Dicionário para manter apenas a melhor rota por combinação
            melhores_rotas_entrega = {}
            
            for transferencia in transferencias_encontradas:
                for _, agente_ent in agentes_entrega.iterrows():
                    try:
                        # Validar peso máximo do agente de entrega
                        validacao_entrega = validar_peso_maximo_agente(agente_ent, maior_peso, "Agente de Entrega")
                        
                        linha_entrega_processada = processar_linha_transferencia(agente_ent, maior_peso, valor_nf)
                        if not linha_entrega_processada:
                            continue
                        
                        total_rota = (transferencia['custo'] + transferencia['pedagio'] + transferencia['gris'] +
                                    linha_entrega_processada['custo'] + linha_entrega_processada['pedagio'] + linha_entrega_processada['gris'])
                        
                        # Chave única por combinação transferência+agente
                        chave_combinacao = f"{transferencia['fornecedor']}_{agente_ent.get('Fornecedor', 'N/A')}"
                        
                        # Se esta combinação já existe, manter apenas a mais barata
                        if chave_combinacao in melhores_rotas_entrega:
                            if total_rota >= melhores_rotas_entrega[chave_combinacao]['total']:
                                continue  # Pular se não é melhor que a existente
                        
                        prazo_total = transferencia['prazo'] + linha_entrega_processada['prazo']
                        
                        # Definir variáveis de base para esta transferência
                        base_origem_transferencia = transferencia.get('base_origem_codigo', base_origem)
                        base_destino_transferencia = transferencia.get('base_destino_codigo', base_destino)
                        
                        rota_parcial = {
                            'tipo_rota': 'transferencia_entrega',
                            'fornecedor_transferencia': transferencia['fornecedor'],
                            'agente_coleta': {
                                'fornecedor': 'N/A - Sem agente coleta',
                                'custo': 0,
                                'pedagio': 0,
                                'gris': 0,
                                'observacao': 'Cliente deve levar carga até base de origem'
                            },
                            'transferencia': {
                                'base_origem': transferencia.get('base_origem_codigo', base_origem),
                                'base_destino': transferencia.get('base_destino_codigo', base_destino),
                                'custo': float(transferencia['custo']),
                                'pedagio': float(transferencia['pedagio']),
                                'gris': float(transferencia['gris']),
                                'fornecedor': transferencia['fornecedor'],
                                'origem': f"Base {base_origem_transferencia}",
                                'destino': f"Base {base_destino_transferencia}",
                                'prazo': transferencia['prazo'],
                                'frete': float(transferencia['custo']) - float(transferencia['pedagio']) - float(transferencia['gris']),
                                'rota_bases': transferencia.get('rota_bases', f"{base_origem_transferencia} → {base_destino_transferencia}")
                            },
                            'agente_entrega': {
                                'fornecedor': agente_ent.get('Fornecedor', 'N/A'),
                                'base_origem': transferencia.get('base_destino_codigo', base_destino),
                                'destino': destino,
                                'custo': float(linha_entrega_processada['custo']),
                                'pedagio': float(linha_entrega_processada['pedagio']),
                                'gris': float(linha_entrega_processada['gris']),
                                'origem': agente_ent.get('Origem', ''),
                                'prazo': linha_entrega_processada['prazo'],
                                'peso_maximo': agente_ent.get('PESO MÁXIMO TRANSPORTADO', 'N/A'),
                                'validacao_peso': validacao_entrega
                            },
                            'total': float(total_rota),
                            'prazo_total': int(prazo_total),
                            'peso_real': float(peso_real),
                            'peso_cubado': float(peso_cubado_fracionado),
                            'maior_peso': float(maior_peso_fracionado),
                            'peso_usado': 'Cubado' if maior_peso_fracionado == peso_cubado_fracionado else 'Real',
                            'base_origem': transferencia.get('base_origem_codigo', base_origem),
                            'base_destino_transferencia': transferencia.get('base_destino_codigo', base_destino),
                            'resumo': f"Transfer {transferencia['fornecedor']} + Entrega {agente_ent.get('Fornecedor')}",
                            'observacoes': f"⚠️ Cliente deve levar carga até base {transferencia.get('base_origem_codigo', base_origem)}",
                            'detalhamento_custos': {
                                'coleta': 0,
                                'transferencia': float(transferencia['custo']),
                                'entrega': float(linha_entrega_processada['custo']),
                                'pedagio': float(transferencia['pedagio'] + linha_entrega_processada['pedagio']),
                                'gris_total': float(transferencia['gris'] + linha_entrega_processada['gris']),
                                'seguro': float(linha_entrega_processada.get('seguro', 0))  # INCLUIR SEGURO NO DETALHAMENTO
                            },
                            'alertas_peso': {
                                'tem_alerta': not validacao_entrega['valido'],
                                'alertas': [validacao_entrega.get('alerta')] if validacao_entrega.get('alerta') else []
                            }
                        }
                        
                        # Salvar a melhor rota para esta combinação
                        melhores_rotas_entrega[chave_combinacao] = rota_parcial
                        print(f"[AGENTES] ✅ Melhor rota: Transfer {transferencia['fornecedor']} + Entrega {agente_ent.get('Fornecedor')} = R$ {total_rota:.2f}")
                        
                    except Exception as e:
                        print(f"[AGENTES] Erro ao processar rota parcial: {e}")
                        continue
            
            # Adicionar apenas as melhores rotas encontradas
            for rota in melhores_rotas_entrega.values():
                rotas_encontradas.append(rota)
        
        # 3.3 ROTAS PARCIAIS - AGENTE COLETA + TRANSFERÊNCIA APENAS
        # SEMPRE EXECUTAR ESTA SEÇÃO PARA OFERECER MAIS OPÇÕES
        if not agentes_coleta.empty:
            print(f"[AGENTES] 🔄 Calculando rotas parciais: Agente Coleta + Transferência ({len(agentes_coleta)} agentes)")
            
            # Dicionário para manter apenas a melhor rota por combinação
            melhores_rotas_coleta = {}
            
            for _, agente_col in agentes_coleta.iterrows():
                for transferencia in transferencias_encontradas:
                    try:
                        # Validar peso máximo do agente de coleta
                        validacao_coleta = validar_peso_maximo_agente(agente_col, maior_peso, "Agente de Coleta")
                        
                        linha_coleta_processada = processar_linha_transferencia(agente_col, maior_peso, valor_nf)
                        if not linha_coleta_processada:
                            continue
                        
                        total_rota = (linha_coleta_processada['custo'] + linha_coleta_processada['pedagio'] + linha_coleta_processada['gris'] +
                                    transferencia['custo'] + transferencia['pedagio'] + transferencia['gris'])
                        
                        # Chave única por combinação agente+fornecedor
                        chave_combinacao = f"{agente_col.get('Fornecedor', 'N/A')}_{transferencia['fornecedor']}"
                        
                        # Se esta combinação já existe, manter apenas a mais barata
                        if chave_combinacao in melhores_rotas_coleta:
                            if total_rota >= melhores_rotas_coleta[chave_combinacao]['total']:
                                continue  # Pular se não é melhor que a existente
                        
                        prazo_total = linha_coleta_processada['prazo'] + transferencia['prazo']
                        
                        rota_parcial = {
                            'tipo_rota': 'coleta_transferencia',
                            'fornecedor_coleta': agente_col.get('Fornecedor', 'N/A'),
                            'fornecedor_transferencia': transferencia['fornecedor'],
                            'agente_coleta': {
                                'fornecedor': agente_col.get('Fornecedor', 'N/A'),
                                'base_origem': origem,
                                'base_destino': agente_col.get('Base Destino', 'N/A'),
                                'custo': float(linha_coleta_processada['custo']),
                                'pedagio': float(linha_coleta_processada['pedagio']),
                                'gris': float(linha_coleta_processada['gris']),
                                'origem': agente_col.get('Origem', ''),
                                'destino': agente_col.get('Destino', ''),
                                'prazo': linha_coleta_processada['prazo'],
                                'peso_maximo': agente_col.get('PESO MÁXIMO TRANSPORTADO', 'N/A'),
                                'validacao_peso': validacao_coleta
                            },
                            'transferencia': {
                                'base_origem': transferencia.get('base_origem_codigo', base_origem),
                                'base_destino': transferencia.get('base_destino_codigo', base_destino),
                                'custo': float(transferencia['custo']),
                                'pedagio': float(transferencia['pedagio']),
                                'gris': float(transferencia['gris']),
                                'fornecedor': transferencia['fornecedor'],
                                'origem': f"Base {transferencia.get('base_origem_codigo', base_origem)}",
                                'destino': f"Base {transferencia.get('base_destino_codigo', base_destino)}",
                                'prazo': transferencia['prazo'],
                                'frete': float(transferencia['custo']) - float(transferencia['pedagio']) - float(transferencia['gris']),
                                'rota_bases': transferencia.get('rota_bases', f"{transferencia.get('base_origem_codigo', base_origem)} → {transferencia.get('base_destino_codigo', base_destino)}")
                            },
                            'agente_entrega': {
                                'fornecedor': 'N/A - Sem agente entrega',
                                'custo': 0,
                                'pedagio': 0,
                                'gris': 0,
                                'observacao': 'Cliente deve retirar carga na base de destino'
                            },
                            'total': float(total_rota),
                            'prazo_total': int(prazo_total),
                            'peso_real': float(peso_real),
                            'peso_cubado': float(peso_cubado_fracionado),
                            'maior_peso': float(maior_peso_fracionado),
                            'peso_usado': 'Cubado' if maior_peso_fracionado == peso_cubado_fracionado else 'Real',
                            'base_origem': transferencia.get('base_origem_codigo', base_origem),
                            'base_destino_transferencia': transferencia.get('base_destino_codigo', base_destino),
                            'resumo': f"Coleta {agente_col.get('Fornecedor')} + Transfer {transferencia['fornecedor']}",
                            'observacoes': f"⚠️ Cliente deve retirar carga na base {transferencia.get('base_destino_codigo', base_destino)}",
                            'detalhamento_custos': {
                                'coleta': float(linha_coleta_processada['custo']),
                                'transferencia': float(transferencia['custo']),
                                'entrega': 0,
                                'pedagio': float(linha_coleta_processada['pedagio'] + transferencia['pedagio']),
                                'gris_total': float(linha_coleta_processada['gris'] + transferencia['gris']),
                                'seguro': float(linha_coleta_processada.get('seguro', 0))  # INCLUIR SEGURO NO DETALHAMENTO
                            },
                            'alertas_peso': {
                                'tem_alerta': not validacao_coleta['valido'],
                                'alertas': [validacao_coleta.get('alerta')] if validacao_coleta.get('alerta') else []
                            }
                        }
                        
                        # Salvar a melhor rota para esta combinação
                        melhores_rotas_coleta[chave_combinacao] = rota_parcial
                        print(f"[AGENTES] ✅ Melhor rota: Coleta {agente_col.get('Fornecedor')} + Transfer {transferencia['fornecedor']} = R$ {total_rota:.2f}")
                        
                    except Exception as e:
                        print(f"[AGENTES] Erro ao processar rota parcial: {e}")
                        continue
            
            # Adicionar apenas as melhores rotas encontradas
            for rota in melhores_rotas_coleta.values():
                rotas_encontradas.append(rota)
        
        # 3.4 FALLBACK - APENAS TRANSFERÊNCIAS DIRETAS
        elif agentes_coleta.empty and agentes_entrega.empty:
            print(f"[AGENTES] ⚠️ Sem agentes de coleta nem entrega")
            print(f"[AGENTES] 🔄 Considerando apenas transferências diretas")
            
            # Buscar transferências diretas da cidade origem para cidade destino
            origem_normalizada = normalizar_cidade(origem)
            destino_normalizado = normalizar_cidade(destino)
            
            # Carregar base de transferências se não estiver carregada
            if 'transferencias_base' not in locals():
                transferencias_base = carregar_base_completa()
            
            # Adicionar normalização se não existir
            if 'Origem_Normalizada' not in transferencias_base.columns:
                transferencias_base['Origem_Normalizada'] = transferencias_base['Origem'].apply(normalizar_cidade)
            if 'Destino_Normalizado' not in transferencias_base.columns:
                transferencias_base['Destino_Normalizado'] = transferencias_base['Destino'].apply(normalizar_cidade)
            
            transferencias_diretas = transferencias_base[
                (transferencias_base['Origem_Normalizada'] == origem_normalizada) &
                (transferencias_base['Destino_Normalizado'] == destino_normalizado)
            ]
            
            print(f"[AGENTES] 🚛 Transferências diretas {origem} → {destino}: {len(transferencias_diretas)}")
            
            # Se não há transferências diretas, buscar para cidades próximas
            if transferencias_diretas.empty:
                print(f"[AGENTES] 🔍 Buscando transferências para região próxima...")
                
                # Mapeamento de cidades para regiões próximas
                cidades_proximas = {
                    'CARLOS BARBOSA': ['CAXIAS DO SUL', 'PORTO ALEGRE', 'GRAMADO', 'CANELA'],
                    'CAXIAS DO SUL': ['CARLOS BARBOSA', 'PORTO ALEGRE', 'BENTO GONCALVES'],
                    'GRAMADO': ['CANELA', 'CAXIAS DO SUL', 'PORTO ALEGRE'],
                    'CANELA': ['GRAMADO', 'CAXIAS DO SUL', 'PORTO ALEGRE']
                }
                
                destino_norm = normalizar_cidade(destino)
                proximas = cidades_proximas.get(destino_norm, [])
                
                for cidade_proxima in proximas:
                    transferencias_proximas = transferencias_base[
                        (transferencias_base['Origem_Normalizada'] == origem_normalizada) &
                        (transferencias_base['Destino_Normalizado'] == normalizar_cidade(cidade_proxima))
                    ]
                    
                    if not transferencias_proximas.empty:
                        print(f"[AGENTES] 🎯 Encontradas {len(transferencias_proximas)} transferências para {cidade_proxima}")
                        transferencias_diretas = transferencias_proximas
                        break
            
            for _, linha_direta in transferencias_diretas.iterrows():
                try:
                    linha_processada = processar_linha_transferencia(linha_direta, maior_peso, valor_nf)
                    if linha_processada:
                        total_rota_direta = (linha_processada['custo'] + linha_processada['pedagio'] + linha_processada['gris'])
                        
                        rota_direta = {
                            'tipo_rota': 'transferencia_direta',
                            'fornecedor_transferencia': linha_processada['fornecedor'],
                            'agente_coleta': {
                                'fornecedor': 'N/A - Sem agente coleta',
                                'custo': 0,
                                'pedagio': 0,
                                'gris': 0,
                                'observacao': 'Cliente entrega na origem'
                            },
                            'transferencia': {
                                'origem': linha_direta.get('Origem', origem),
                                'destino': linha_direta.get('Destino', destino),
                                'custo': float(linha_processada['custo']),
                                'pedagio': float(linha_processada['pedagio']),
                                'gris': float(linha_processada['gris']),
                                'fornecedor': linha_processada['fornecedor'],
                                'prazo': linha_processada['prazo'],
                                'frete': float(linha_processada['custo']) - float(linha_processada['pedagio']) - float(linha_processada['gris']),
                                'base_origem': linha_direta.get('Origem', origem),
                                'base_destino': linha_direta.get('Destino', destino),
                                'rota_bases': f"{linha_direta.get('Origem', origem)} → {linha_direta.get('Destino', destino)}"
                            },
                            'agente_entrega': {
                                'fornecedor': 'N/A - Sem agente entrega',
                                'custo': 0,
                                'pedagio': 0,
                                'gris': 0,
                                'observacao': 'Cliente retira no destino'
                            },
                            'total': float(total_rota_direta),
                            'prazo_total': int(linha_processada['prazo']),
                            'peso_real': float(peso_real),
                            'peso_cubado': float(peso_cubado_fracionado),
                            'maior_peso': float(maior_peso),
                            'peso_usado': 'Cubado' if maior_peso == peso_cubado_fracionado else 'Real',
                            'base_origem': linha_direta.get('Origem', origem),
                            'base_destino_transferencia': linha_direta.get('Destino', destino),
                            'resumo': f"Transferência {linha_processada['fornecedor']}",
                            'observacoes': f"⚠️ Apenas transferência - Cliente entrega na origem e retira no destino",
                            'detalhamento_custos': {
                                'coleta': 0,
                                'transferencia': float(linha_processada['custo']),
                                'entrega': 0,
                                'pedagio': float(linha_processada['pedagio']),
                                'gris_total': float(linha_processada['gris'])
                            },
                            'alertas_peso': {
                                'tem_alerta': False,
                                'alertas': []
                            }
                        }
                        rotas_encontradas.append(rota_direta)
                        print(f"[AGENTES] ✅ Transferência: {linha_processada['fornecedor']} - R$ {rota_direta['total']:.2f}")
                except Exception as e:
                    print(f"[AGENTES] Erro ao processar transferência direta: {e}")
                    continue
        
        # Ordenar por custo total
        rotas_encontradas = sorted(rotas_encontradas, key=lambda x: x.get('total', float('inf')))
        
        print(f"[AGENTES] ✅ {len(rotas_encontradas)} rotas com agentes calculadas")
        
        return {
            'rotas': rotas_encontradas,
            'cotacoes_ranking': rotas_encontradas,  # Adicionar este campo para compatibilidade
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
        
        # Verificar se é um agente (Tipo == 'Agente' ou 'Direto')
        tipo = linha_dict.get('Tipo', '')
        is_agente = tipo in ['Agente', 'Direto']
        
        if is_agente:
            # LÓGICA PARA AGENTES DIRETOS (CORRIGIDA PARA REUNIDAS E GRITSCH)
            if tipo == 'Direto':
                fornecedor = linha_dict.get('Fornecedor', '').upper()
                valor_minimo = float(linha_dict.get('VALOR MÍNIMO ATÉ 10', 0) or 0)
                valor_excedente = float(linha_dict.get('EXCEDENTE', 0) or 0)
                
                # REGRAS ESPECÍFICAS POR FORNECEDOR
                if 'REUNIDAS' in fornecedor:
                    # REUNIDAS: Até 300kg usa faixas, acima de 300kg usa excedente
                    if peso <= 10:
                        valor_base = valor_minimo
                        faixa_peso_usada = "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_minimo / 10 if valor_minimo > 0 else 0
                    elif peso <= 300:
                        # Usar faixa de peso correspondente
                        if peso <= 20:
                            valor_base = float(linha_dict.get(20, 0) or 0)
                            faixa_peso_usada = "20kg"
                        elif peso <= 30:
                            valor_base = float(linha_dict.get(30, 0) or 0)
                            faixa_peso_usada = "30kg"
                        elif peso <= 50:
                            valor_base = float(linha_dict.get(50, 0) or 0)
                            faixa_peso_usada = "50kg"
                        elif peso <= 70:
                            valor_base = float(linha_dict.get(70, 0) or 0)
                            faixa_peso_usada = "70kg"
                        elif peso <= 100:
                            valor_base = float(linha_dict.get(100, 0) or 0)
                            faixa_peso_usada = "100kg"
                        elif peso <= 150:
                            valor_base = float(linha_dict.get(150, 0) or 0)
                            faixa_peso_usada = "150kg"
                        elif peso <= 200:
                            valor_base = float(linha_dict.get(200, 0) or 0)
                            faixa_peso_usada = "200kg"
                        else:  # peso <= 300
                            valor_base = float(linha_dict.get(300, 0) or 0)
                            faixa_peso_usada = "300kg"
                        
                        valor_kg_usado = valor_base / peso if valor_base > 0 and peso > 0 else 0
                    else:
                        # ACIMA DE 300KG: usar excedente (peso × valor_excedente)
                        valor_base = peso * valor_excedente
                        faixa_peso_usada = f"Excedente (>{peso:.0f}kg)"
                        valor_kg_usado = valor_excedente
                        
                elif 'GRITSCH' in fornecedor:
                    # GRITSCH: Até 10kg usa valor mínimo, acima usa valor mínimo + excedente
                    if peso <= 10:
                        valor_base = valor_minimo
                        faixa_peso_usada = "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_minimo / 10 if valor_minimo > 0 else 0
                    else:
                        # ACIMA DE 10KG: valor mínimo + (peso_excedente × valor_excedente)
                        peso_excedente = peso - 10
                        valor_base = valor_minimo + (peso_excedente * valor_excedente)
                        faixa_peso_usada = f"Valor Mínimo + Excedente (>{peso:.0f}kg)"
                        valor_kg_usado = valor_excedente
                        
                else:
                    # OUTROS AGENTES DIRETOS: usar lógica de faixas padrão
                    if peso <= 10:
                        valor_base = valor_minimo
                        faixa_peso_usada = "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_minimo / 10 if valor_minimo > 0 else 0
                    elif peso <= 20:
                        valor_kg = float(linha_dict.get(20, 0) or 0)
                        valor_base = valor_kg if valor_kg > 0 else valor_minimo
                        faixa_peso_usada = "20kg" if valor_kg > 0 else "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_kg / peso if valor_kg > 0 and peso > 0 else valor_minimo / 10
                    elif peso <= 30:
                        valor_kg = float(linha_dict.get(30, 0) or 0)
                        valor_base = valor_kg if valor_kg > 0 else valor_minimo
                        faixa_peso_usada = "30kg" if valor_kg > 0 else "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_kg / peso if valor_kg > 0 and peso > 0 else valor_minimo / 10
                    elif peso <= 50:
                        valor_kg = float(linha_dict.get(50, 0) or 0)
                        valor_base = valor_kg if valor_kg > 0 else valor_minimo
                        faixa_peso_usada = "50kg" if valor_kg > 0 else "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_kg / peso if valor_kg > 0 and peso > 0 else valor_minimo / 10
                    elif peso <= 70:
                        valor_kg = float(linha_dict.get(70, 0) or 0)
                        valor_base = valor_kg if valor_kg > 0 else valor_minimo
                        faixa_peso_usada = "70kg" if valor_kg > 0 else "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_kg / peso if valor_kg > 0 and peso > 0 else valor_minimo / 10
                    elif peso <= 100:
                        valor_kg = float(linha_dict.get(100, 0) or 0)
                        valor_base = valor_kg if valor_kg > 0 else valor_minimo
                        faixa_peso_usada = "100kg" if valor_kg > 0 else "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_kg / peso if valor_kg > 0 and peso > 0 else valor_minimo / 10
                    elif peso <= 150:
                        valor_kg = float(linha_dict.get(150, 0) or 0)
                        valor_base = valor_kg if valor_kg > 0 else valor_minimo
                        faixa_peso_usada = "150kg" if valor_kg > 0 else "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_kg / peso if valor_kg > 0 and peso > 0 else valor_minimo / 10
                    elif peso <= 200:
                        valor_kg = float(linha_dict.get(200, 0) or 0)
                        valor_base = valor_kg if valor_kg > 0 else valor_minimo
                        faixa_peso_usada = "200kg" if valor_kg > 0 else "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_kg / peso if valor_kg > 0 and peso > 0 else valor_minimo / 10
                    elif peso <= 300:
                        valor_kg = float(linha_dict.get(300, 0) or 0)
                        valor_base = valor_kg if valor_kg > 0 else valor_minimo
                        faixa_peso_usada = "300kg" if valor_kg > 0 else "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_kg / peso if valor_kg > 0 and peso > 0 else valor_minimo / 10
                    elif peso <= 500:
                        valor_kg = float(linha_dict.get(500, 0) or 0)
                        valor_base = valor_kg if valor_kg > 0 else valor_minimo
                        faixa_peso_usada = "500kg" if valor_kg > 0 else "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_kg / peso if valor_kg > 0 and peso > 0 else valor_minimo / 10
                    else:
                        valor_kg = float(linha_dict.get('Acima 500', 0) or 0)
                        valor_base = valor_kg if valor_kg > 0 else valor_minimo
                        faixa_peso_usada = "Acima 500kg" if valor_kg > 0 else "VALOR MÍNIMO ATÉ 10"
                        valor_kg_usado = valor_kg / peso if valor_kg > 0 and peso > 0 else valor_minimo / 10
            else:
                # Para outros tipos de agentes (não diretos), manter lógica original com EXCEDENTE
                valor_minimo = float(linha_dict.get('VALOR MÍNIMO ATÉ 10', 0) or 0)
                valor_excedente = float(linha_dict.get('EXCEDENTE', 0) or 0)
                
                if peso <= 10:
                    valor_base = valor_minimo
                    faixa_peso_usada = "Valor Mínimo (≤10kg)"
                    valor_kg_usado = valor_minimo / 10 if valor_minimo > 0 else 0
                else:
                    peso_excedente = peso - 10
                    valor_base = valor_minimo + (peso_excedente * valor_excedente)
                    faixa_peso_usada = f"Valor Mínimo + Excedente (>{peso:.1f}kg)"
                    valor_kg_usado = valor_excedente
        else:
            # LÓGICA PARA TRANSFERÊNCIAS (corrigida)
            if peso <= 10:
                # Para peso ≤ 10kg: usar VALOR MÍNIMO ATÉ 10 (valor fixo)
                valor_base = float(linha_dict.get('VALOR MÍNIMO ATÉ 10', 0) or 0)
                faixa_peso_usada = 'VALOR MÍNIMO ATÉ 10'
                valor_kg_usado = valor_base / 10 if valor_base > 0 else 0  # Para referência
            else:
                # Para peso > 10kg: usar faixa correspondente multiplicada pelo peso
                # MAS SEMPRE GARANTIR QUE SEJA NO MÍNIMO O VALOR MÍNIMO ATÉ 10
                valor_minimo = float(linha_dict.get('VALOR MÍNIMO ATÉ 10', 0) or 0)
                
                if peso <= 20:
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
                        valor_kg_usado = float(linha_dict.get('VALOR MÍNIMO ATÉ 10', 0) or 0) / 10
                except (ValueError, TypeError):
                    valor_kg_usado = 0
                
                # Calcular valor base para transferências
                valor_calculado = peso * valor_kg_usado
                # GARANTIR que nunca seja menor que o valor mínimo
                valor_base = max(valor_minimo, valor_calculado)
                
                # Atualizar faixa usada se valor mínimo foi aplicado
                if valor_base == valor_minimo:
                    faixa_peso_usada = f"Valor Mínimo (>{peso:.1f}kg)"
        
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
                    # CORREÇÃO: Gris Exc na planilha sempre está em formato percentual
                    # Exemplo: 0.1 = 0.1%, 0.17 = 0.17%, 3.5 = 3.5%
                    gris_percentual = gris_exc / 100
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
        
        # Calcular TDA (Taxa de Despacho Aduaneiro) - NOVO PARA DIRETOS
        tda = 0.0
        try:
            if is_agente and tipo == 'Direto':  # Apenas para agentes diretos
                valor_tda = linha_dict.get('Tda', 0)
                if valor_tda is not None and not pd.isna(valor_tda):
                    tda = float(valor_tda)
                    if tda < 0:  # Garantir que não seja negativo
                        tda = 0.0
        except (ValueError, TypeError):
            tda = 0.0
        
        # Calcular Seguro - CORRIGIDO PARA CALCULAR PERCENTUAL SOBRE VALOR NF
        seguro = 0.0
        try:
            if is_agente and tipo == 'Direto' and valor_nf and valor_nf > 0:
                # CORREÇÃO: Verificar primeiro se o fornecedor tem seguro na base
                seguro_base = linha_dict.get('Seguro', None)
                
                if seguro_base is not None and not pd.isna(seguro_base):
                    seguro_base = float(seguro_base)
                    # CORREÇÃO: Se valor na base é muito baixo (< 0.01%), considerar como zero
                    if seguro_base < 0.01:
                        # Valores irrisórios como 0.003 = sem seguro
                        seguro = 0.0
                    else:
                        # CORREÇÃO: Usar valor da base como percentual sobre valor da NF
                        # Ex: se seguro_base = 0.3, então 0.3% do valor da NF
                        seguro = valor_nf * (seguro_base / 100)
                        # REMOVIDO: Valor mínimo - seguro deve ser exatamente o percentual calculado
                else:
                    # Se não tem valor na base, não calcular seguro
                    seguro = 0.0
        except (ValueError, TypeError):
            seguro = 0.0
        
        # Obter informações do fornecedor
        fornecedor = linha_dict.get('Fornecedor', 'N/A')
        
        # Garantir que nenhum valor seja NaN
        valor_base = 0.0 if pd.isna(valor_base) or math.isnan(valor_base) else valor_base
        pedagio = 0.0 if pd.isna(pedagio) or math.isnan(pedagio) else pedagio
        gris = 0.0 if pd.isna(gris) or math.isnan(gris) else gris
        tda = 0.0 if pd.isna(tda) or math.isnan(tda) else tda
        valor_kg_usado = 0.0 if pd.isna(valor_kg_usado) or math.isnan(valor_kg_usado) else valor_kg_usado
        
        # TOTAL INCLUI TDA PARA DIRETOS
        total = valor_base + pedagio + gris + tda + seguro
        total = 0.0 if pd.isna(total) or math.isnan(total) else total
        
        # Retornar resultado formatado
        return {
            'custo': round(valor_base, 2),
            'pedagio': round(pedagio, 2),
            'gris': round(gris, 2),
            'tda': round(tda, 2),  # NOVO CAMPO TDA
            'seguro': round(seguro, 2),  # NOVO CAMPO SEGURO
            'total': round(total, 2),
            'prazo': prazo,
            'faixa_peso': faixa_peso_usada,
            'valor_kg': round(valor_kg_usado, 4),
            'fornecedor': fornecedor,
            'is_agente': is_agente,
            'tipo': tipo  # NOVO CAMPO TIPO
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

def _gerar_alerta_peso_html(validacao_peso):
    """
    Gera HTML para alertas de peso máximo excedido
    """
    if not validacao_peso or validacao_peso.get('valido', True):
        return ""
    
    alerta = validacao_peso.get('alerta', {})
    if not alerta:
        return ""
    
    return f"""
    <div class="alerta-peso-excedido" style="
        background: linear-gradient(135deg, #ff6b6b, #ee5a52);
        color: white;
        padding: 12px;
        border-radius: 8px;
        margin: 8px 0;
        border-left: 5px solid #c92a2a;
        animation: pulseAlert 2s infinite;
        box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3);
    ">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1.2em;">⚠️</span>
            <div>
                <strong>{alerta.get('titulo', 'Peso Excedido')}</strong><br>
                <small>{alerta.get('mensagem', '')}</small><br>
                <div style="margin-top: 8px; font-weight: bold; background: rgba(255,255,255,0.2); padding: 6px; border-radius: 4px;">
                    📞 {alerta.get('acao_requerida', 'Cotar com o agente')}<br>
                    ✅ {alerta.get('validacao_cliente', 'Valide com o cliente')}
                </div>
            </div>
        </div>
    </div>
    """

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
            
            <!-- Botão para Ocultar/Mostrar Seções Técnicas -->
            <div class="analise-item" style="text-align: center; margin-top: 15px;">
                <button id="toggleTechnicalSections" onclick="
                    var sections = document.getElementById('technicalSections');
                    var button = document.getElementById('toggleTechnicalSections');
                    if (sections.style.display === 'none' || sections.style.display === '') {{
                        sections.style.display = 'block';
                        button.innerHTML = '📊 Ocultar Informações Técnicas';
                        button.style.background = '#6c757d';
                    }} else {{
                        sections.style.display = 'none';
                        button.innerHTML = '📊 Mostrar Informações Técnicas';
                        button.style.background = '#17a2b8';
                    }}
                " style="
                    background: #17a2b8; 
                    color: white; 
                    border: none; 
                    padding: 8px 16px; 
                    border-radius: 5px; 
                    font-size: 0.9rem; 
                    cursor: pointer;
                    transition: all 0.3s ease;
                " onmouseover="this.style.background='#138496'" onmouseout="this.style.background='#17a2b8'">
                    📊 Mostrar Informações Técnicas
                </button>
            </div>
        </div>

        <!-- Container das Seções Técnicas (inicialmente oculto) -->
        <div id="technicalSections" style="display: none;">
        <!-- Filtros de Qualidade Aplicados -->
        <div class="analise-container">
            <div class="analise-title">
                🔍 Filtros de Qualidade Aplicados
                <button class="btn-secondary" onclick="toggleDetails('detalhes_filtros')" style="float: right; margin-left: 10px; font-size: 0.8rem; padding: 4px 8px; background: #17a2b8;">
                    Ver Detalhes
                </button>
            </div>
            <div class="analise-item"><strong>Critérios Obrigatórios:</strong> {criterios_qualidade}</div>
            <div class="analise-item"><strong>Cotações Aceitas:</strong> 
                <span style="color: #27ae60; font-weight: bold;">{resultado.get('total_opcoes', 0)}</span>
            </div>
            <div class="analise-item"><strong>Cotações Rejeitadas:</strong> 
                <span style="color: #e74c3c; font-weight: bold;">{cotacoes_rejeitadas}</span>
            </div>
            
            <!-- Detalhes dos Filtros -->
            <div id="detalhes_filtros" style="display: none; margin-top: 15px; padding: 15px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px;">
                <strong style="color: #17a2b8;">🔍 Detalhamento dos Filtros de Qualidade:</strong><br><br>
                <div style="margin-bottom: 10px;">
                    <strong>✅ Critérios Aplicados:</strong><br>
                    • <strong>Peso Máximo:</strong> Verificação se agentes suportam o peso solicitado<br>
                    • <strong>Bases Válidas:</strong> Apenas rotas com bases operacionais ativas<br>
                    • <strong>Fornecedores Ativos:</strong> Somente parceiros com status ativo<br>
                    • <strong>Cálculos Precisos:</strong> Validação de custos, prazos e capacidades<br>
                    • <strong>Rotas Viáveis:</strong> Eliminação de combinações impossíveis
                </div>
                <div style="margin-bottom: 10px;">
                    <strong>📊 Processo de Seleção:</strong><br>
                    • Sistema analisa <strong>todas as combinações possíveis</strong> de agentes<br>
                    • Aplica filtros de qualidade para garantir viabilidade<br>
                    • Ordena por <strong>melhor custo-benefício</strong><br>
                    • Apresenta apenas opções <strong>executáveis</strong>
                </div>
                <div>
                    <strong>🎯 Resultado:</strong> 
                    <span style="color: #27ae60; font-weight: bold;">{resultado.get('total_opcoes', 0)} rotas aprovadas</span> 
                    de um total analisado, garantindo <strong>100% de confiabilidade</strong> nas cotações apresentadas.
                </div>
            </div>
        </div>

        <!-- Informações da Rota -->
        <div class="analise-container">
            <div class="analise-title">
                📍 Informações da Rota
                <button class="btn-secondary" onclick="toggleDetails('detalhes_rota')" style="float: right; margin-left: 10px; font-size: 0.8rem; padding: 4px 8px; background: #6f42c1;">
                    Ver Detalhes
                </button>
            </div>
            <div class="analise-item"><strong>Origem:</strong> {resultado.get('origem', 'N/A')} - {resultado.get('uf_origem', 'N/A')}</div>
            <div class="analise-item"><strong>Destino:</strong> {resultado.get('destino', 'N/A')} - {resultado.get('uf_destino', 'N/A')}</div>
            <div class="analise-item"><strong>Peso Real:</strong> {resultado.get('peso', 0)} kg</div>
            <div class="analise-item"><strong>Peso Cubado:</strong> {resultado.get('peso_cubado', 0):.2f} kg</div>
            <div class="analise-item"><strong>Cubagem:</strong> {resultado.get('cubagem', 0):.4f} m³</div>
            {f'<div class="analise-item"><strong>Valor da NF:</strong> R$ {resultado.get("valor_nf", 0):,.2f}</div>' if resultado.get('valor_nf') else '<div class="analise-item"><strong>Valor da NF:</strong> <span style="color: #f39c12;">Não informado</span></div>'}
            
            <!-- Detalhes da Rota -->
            <div id="detalhes_rota" style="display: none; margin-top: 15px; padding: 15px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px;">
                <strong style="color: #6f42c1;">📍 Detalhamento Técnico da Rota:</strong><br><br>
                <div style="margin-bottom: 10px;">
                    <strong>📦 Características da Carga:</strong><br>
                    • <strong>Peso Real:</strong> {resultado.get('peso', 0)} kg (peso físico da mercadoria)<br>
                    • <strong>Peso Cubado:</strong> {resultado.get('peso_cubado', 0):.2f} kg (peso volumétrico calculado)<br>
                    • <strong>Cubagem:</strong> {resultado.get('cubagem', 0):.4f} m³ (volume total ocupado)<br>
                    • <strong>Peso Tarifado:</strong> <span style="color: #e67e22; font-weight: bold;">Maior entre peso real e cubado</span><br>
                    {f'• <strong>Valor Declarado:</strong> R$ {resultado.get("valor_nf", 0):,.2f} (base para seguro)' if resultado.get('valor_nf') else '• <strong>Valor Declarado:</strong> <span style="color: #f39c12;">Não informado - pode afetar cálculo do seguro</span>'}
                </div>
                <div style="margin-bottom: 10px;">
                    <strong>🗺️ Informações Geográficas:</strong><br>
                    • <strong>Origem:</strong> {resultado.get('origem', 'N/A')}/{resultado.get('uf_origem', 'N/A')}<br>
                    • <strong>Destino:</strong> {resultado.get('destino', 'N/A')}/{resultado.get('uf_destino', 'N/A')}<br>
                    • <strong>Tipo de Rota:</strong> {'Interestadual' if resultado.get('uf_origem') != resultado.get('uf_destino') else 'Intraestadual'}<br>
                    • <strong>Complexidade:</strong> Análise automática de agentes e transferências disponíveis
                </div>
                <div>
                    <strong>⚙️ Processamento:</strong><br>
                    • Sistema analisou <strong>bases operacionais</strong> nas duas pontas<br>
                    • Identificou <strong>agentes de coleta e entrega</strong> disponíveis<br>
                    • Calculou <strong>transferências inter-bases</strong> necessárias<br>
                    • Aplicou <strong>tarifas específicas</strong> por peso e distância
                </div>
            </div>
        </div>
        </div>

        <!-- Alerta de Valor Alto -->
        
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
            
            # Verificar se é agente direto, tradicional ou rota parcial
            tipo_rota = opcao.get('tipo_rota', 'tradicional')
            
            if tipo_rota == 'direta':
                # AGENTE DIRETO
                agente_direto = opcao.get('agente_direto', {})
                
                html += f"""
                        <tr style="{row_style}">
                            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; font-size: 1.1em;">{posicao_icon}</td>
                            <td style="padding: 12px; border: 1px solid #dee2e6;">
                                <strong style="color: #28a745;">🚀 {opcao.get('resumo', 'N/A')}</strong><br>
                                <small style="color: #6c757d;">
                                    Serviço DIRETO porta-a-porta • {agente_direto.get('fornecedor', 'N/A')}
                                </small>
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: bold; color: #28a745; font-size: 1.1em;">
                                R$ {opcao.get('total', 0):,.2f}
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                                {opcao.get('prazo_total', 'N/A')} dias
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                                <button class="btn-secondary" onclick="toggleDetails('detalhes_direto_{i}')" style="margin: 2px; font-size: 0.8rem; padding: 4px 8px; background: #28a745;">
                                    Ver Detalhes
                                </button>
                            </td>
                        </tr>
                        
                        <!-- Detalhes do Agente Direto -->
                        <tr id="detalhes_direto_{i}" style="display: none;">
                            <td colspan="5" style="padding: 15px; background: #e8f5e8; border: 1px solid #dee2e6;">
                                <strong style="color: #28a745;">🚀 Agente DIRETO (Porta-a-Porta):</strong><br>
                                • <strong>Fornecedor:</strong> {agente_direto.get('fornecedor', 'N/A')}<br>
                                • <strong>Origem:</strong> {agente_direto.get('origem', 'N/A')}<br>
                                • <strong>Destino:</strong> {agente_direto.get('destino', 'N/A')}<br>
                                • <strong>Base Operacional:</strong> {agente_direto.get('base_origem', 'N/A')}<br>
                                • <strong>Custo do Serviço:</strong> R$ {agente_direto.get('custo', 0):.2f}<br>
                                • <strong>Pedágio:</strong> R$ {agente_direto.get('pedagio', 0):.2f}<br>
                                • <strong>GRIS:</strong> R$ {agente_direto.get('gris', 0):.2f}<br>
                                • <strong>TDA:</strong> R$ {agente_direto.get('tda', 0):.2f}<br>
                                • <strong>Seguro:</strong> R$ {agente_direto.get('seguro', 0):.2f}<br>
                                • <strong>Prazo:</strong> {agente_direto.get('prazo', 'N/A')} dias<br>
                                • <strong>Peso Máximo:</strong> {agente_direto.get('peso_maximo', 'N/A')} kg<br>
                                • <strong>Vantagem:</strong> <span style="color: #28a745;">✅ SEM transferência - porta-a-porta</span><br>
                                {_gerar_alerta_peso_html(agente_direto.get('validacao_peso', {}))}
                            </td>
                        </tr>
                """
            elif tipo_rota == 'transferencia_entrega':
                # ROTA PARCIAL: APENAS TRANSFERÊNCIA + ENTREGA
                transferencia = opcao.get('transferencia', {})
                agente_entrega = opcao.get('agente_entrega', {})
                
                html += f"""
                        <tr style="{row_style}">
                            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; font-size: 1.1em;">{posicao_icon}</td>
                            <td style="padding: 12px; border: 1px solid #dee2e6;">
                                <strong style="color: #fd7e14;">⚠️ {opcao.get('resumo', 'N/A')}</strong><br>
                                <small style="color: #6c757d;">
                                    Transfer: {transferencia.get('fornecedor', 'N/A')} + Entrega: {agente_entrega.get('fornecedor', 'N/A')}<br>
                                    <span style="color: #e74c3c;">⚠️ {opcao.get('observacoes', 'Cliente deve levar carga até base')}</span>
                                </small>
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: bold; color: #fd7e14; font-size: 1.1em;">
                                R$ {opcao.get('total', 0):,.2f}
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                                {opcao.get('prazo_total', 'N/A')} dias
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                                <button class="btn-secondary" onclick="toggleDetails('detalhes_transfer_{i}')" style="margin: 2px; font-size: 0.8rem; padding: 4px 8px; background: #fd7e14;">
                                    Ver Transfer
                                </button><br>
                                <button class="btn-secondary" onclick="toggleDetails('detalhes_entrega_{i}')" style="margin: 2px; font-size: 0.8rem; padding: 4px 8px; background: #28a745;">
                                    Ver Entrega
                                </button>
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
                                • <strong>Pedágio:</strong> R$ {agente_entrega.get('pedagio', 0):.2f}<br>
                                • <strong>GRIS:</strong> R$ {agente_entrega.get('gris', 0):.2f}<br>
                                • <strong>Prazo:</strong> {agente_entrega.get('prazo', 'N/A')} dias<br>
                                • <strong>Peso Máximo:</strong> {agente_entrega.get('peso_maximo', 'N/A')} kg<br>
                                {_gerar_alerta_peso_html(agente_entrega.get('validacao_peso', {}))}
                            </td>
                        </tr>
                """
            elif tipo_rota == 'coleta_transferencia':
                # ROTA PARCIAL: COLETA + TRANSFERÊNCIA APENAS
                agente_coleta = opcao.get('agente_coleta', {})
                transferencia = opcao.get('transferencia', {})
                
                html += f"""
                        <tr style="{row_style}">
                            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; font-size: 1.1em;">{posicao_icon}</td>
                            <td style="padding: 12px; border: 1px solid #dee2e6;">
                                <strong style="color: #007bff;">⚠️ {opcao.get('resumo', 'N/A')}</strong><br>
                                <small style="color: #6c757d;">
                                    Coleta: {agente_coleta.get('fornecedor', 'N/A')} + Transfer: {transferencia.get('fornecedor', 'N/A')}<br>
                                    <span style="color: #e74c3c;">⚠️ {opcao.get('observacoes', 'Cliente deve retirar carga na base')}</span>
                                </small>
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: bold; color: #007bff; font-size: 1.1em;">
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
                                • <strong>Pedágio:</strong> R$ {agente_coleta.get('pedagio', 0):.2f}<br>
                                • <strong>GRIS:</strong> R$ {agente_coleta.get('gris', 0):.2f}<br>
                                • <strong>Prazo:</strong> {agente_coleta.get('prazo', 'N/A')} dias<br>
                                • <strong>Peso Máximo:</strong> {agente_coleta.get('peso_maximo', 'N/A')} kg<br>
                                {_gerar_alerta_peso_html(agente_coleta.get('validacao_peso', {}))}
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
                                • <strong>Prazo:</strong> {transferencia.get('prazo', 'N/A')} dias<br>
                                • <strong>Observação:</strong> <span style="color: #e74c3c;">Cliente deve retirar carga na base {transferencia.get('destino', 'destino')}</span>
                            </td>
                        </tr>
                """
            elif tipo_rota == 'transferencia_direta':
                # ROTA PARCIAL: APENAS TRANSFERÊNCIA DIRETA
                transferencia = opcao.get('transferencia', {})
                
                html += f"""
                        <tr style="{row_style}">
                            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; font-size: 1.1em;">{posicao_icon}</td>
                            <td style="padding: 12px; border: 1px solid #dee2e6;">
                                <strong style="color: #6c757d;">⚠️ {opcao.get('resumo', 'N/A')}</strong><br>
                                <small style="color: #6c757d;">
                                    Apenas Transferência: {transferencia.get('fornecedor', 'N/A')}<br>
                                    <span style="color: #e74c3c;">⚠️ {opcao.get('observacoes', 'Cliente entrega e retira')}</span>
                                </small>
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: bold; color: #6c757d; font-size: 1.1em;">
                                R$ {opcao.get('total', 0):,.2f}
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                                {opcao.get('prazo_total', 'N/A')} dias
                            </td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                                <button class="btn-secondary" onclick="toggleDetails('detalhes_transfer_{i}')" style="margin: 2px; font-size: 0.8rem; padding: 4px 8px; background: #6c757d;">
                                    Ver Detalhes
                                </button>
                            </td>
                        </tr>
                """
            else:
                # AGENTE TRADICIONAL (com transferência)
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
                                • <strong>Pedágio:</strong> R$ {agente_coleta.get('pedagio', 0):.2f}<br>
                                • <strong>GRIS:</strong> R$ {agente_coleta.get('gris', 0):.2f}<br>
                                • <strong>Prazo:</strong> {agente_coleta.get('prazo', 'N/A')} dias<br>
                                • <strong>Peso Máximo:</strong> {agente_coleta.get('peso_maximo', 'N/A')} kg<br>
                                {_gerar_alerta_peso_html(agente_coleta.get('validacao_peso', {}))}
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
                                • <strong>Prazo:</strong> {transferencia.get('prazo', 'N/A')} dias<br>
                                • <strong>Observação:</strong> <span style="color: #e74c3c;">Cliente deve retirar carga na base {transferencia.get('destino', 'destino')}</span>
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
                                • <strong>Pedágio:</strong> R$ {agente_entrega.get('pedagio', 0):.2f}<br>
                                • <strong>GRIS:</strong> R$ {agente_entrega.get('gris', 0):.2f}<br>
                                • <strong>TDA:</strong> R$ {agente_entrega.get('tda', 0):.2f}<br>
                                • <strong>Seguro:</strong> R$ {agente_entrega.get('seguro', 0):.2f}<br>
                                • <strong>Prazo:</strong> {agente_entrega.get('prazo', 'N/A')} dias<br>
                                {_gerar_alerta_peso_html(agente_entrega.get('validacao_peso', {}))}
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
    
    <style>
    @keyframes pulseAlert {
        0% { 
            transform: scale(1); 
            box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3); 
        }
        50% { 
            transform: scale(1.02); 
            box-shadow: 0 6px 20px rgba(255, 107, 107, 0.5); 
        }
        100% { 
            transform: scale(1); 
            box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3); 
        }
    }
    
    .alerta-peso-excedido {
        position: relative;
        overflow: hidden;
    }
    
    .alerta-peso-excedido::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
        animation: shimmer 3s infinite;
    }
    
    @keyframes shimmer {
        0% { left: -100%; }
        100% { left: 100%; }
    }
    
    @keyframes pulseGold {
        0% { 
            transform: scale(1); 
            box-shadow: 0 6px 20px rgba(255, 167, 38, 0.4); 
        }
        50% { 
            transform: scale(1.02); 
            box-shadow: 0 8px 25px rgba(255, 167, 38, 0.6); 
        }
        100% { 
            transform: scale(1); 
            box-shadow: 0 6px 20px rgba(255, 167, 38, 0.4); 
        }
    }
    
    @keyframes shine {
        0% { left: -100%; }
        100% { left: 100%; }
    }
    </style>
    
    <script>
    function toggleDetails(elementId) {
        var element = document.getElementById(elementId);
        if (element.style.display === "none") {
            element.style.display = "block";
        } else {
            element.style.display = "none";
        }
    }
    
    // Adicionar notificação toast quando há alertas de peso
    document.addEventListener('DOMContentLoaded', function() {
        const alertas = document.querySelectorAll('.alerta-peso-excedido');
        if (alertas.length > 0) {
            // Criar notificação toast
            const toast = document.createElement('div');
            toast.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: linear-gradient(135deg, #ff6b6b, #ee5a52);
                color: white;
                padding: 15px 20px;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                z-index: 10000;
                animation: slideInRight 0.5s ease-out;
                max-width: 350px;
                font-family: Arial, sans-serif;
            `;
            toast.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 1.5em;">⚠️</span>
                    <div>
                        <strong>Atenção: Peso Máximo Excedido!</strong><br>
                        <small>Encontrados ${alertas.length} agente(s) com peso excedido. Verifique os detalhes.</small>
                    </div>
                </div>
            `;
            
            document.body.appendChild(toast);
            
            // Remover toast após 8 segundos
            setTimeout(() => {
                toast.style.animation = 'slideOutRight 0.5s ease-out';
                setTimeout(() => document.body.removeChild(toast), 500);
            }, 8000);
        }
    });
    </script>
    
    <style>
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    </style>
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
    
    # Botões de exportação removidos - são adicionados pelo JavaScript
    
    return html

def validar_peso_maximo_agente(agente, peso_usado, tipo_agente=""):
    """
    Valida se o peso usado ultrapassa o peso máximo do agente
    Retorna dict com status da validação e mensagem de alerta se necessário
    """
    try:
        peso_maximo_str = agente.get('PESO MÁXIMO TRANSPORTADO', '')
        if not peso_maximo_str or peso_maximo_str in ['N/A', '', 'nan']:
            return {
                'valido': True,
                'peso_maximo': 'N/A',
                'alerta': None,
                'status': 'sem_limite'
            }
        
        # Converter peso máximo para número
        peso_maximo = float(str(peso_maximo_str).replace(',', '.'))
        peso_usado_num = float(peso_usado)
        
        if peso_usado_num > peso_maximo:
            return {
                'valido': False,
                'peso_maximo': peso_maximo,
                'peso_usado': peso_usado_num,
                'excesso': peso_usado_num - peso_maximo,
                'alerta': {
                    'tipo': 'peso_excedido',
                    'titulo': f'⚠️ Peso Excedido - {tipo_agente}',
                    'mensagem': f'Peso usado ({peso_usado_num:.0f}kg) excede o limite do agente ({peso_maximo:.0f}kg)',
                    'acao_requerida': 'Cotar com o agente',
                    'validacao_cliente': 'Valide com o cliente, ultrapassou o peso máximo'
                },
                'status': 'excedido'
            }
        else:
            return {
                'valido': True,
                'peso_maximo': peso_maximo,
                'peso_usado': peso_usado_num,
                'margem': peso_maximo - peso_usado_num,
                'alerta': None,
                'status': 'dentro_limite'
            }
            
    except (ValueError, TypeError) as e:
        log_debug(f"[PESO_VALIDACAO] Erro ao validar peso do agente: {e}")
        return {
            'valido': True,
            'peso_maximo': 'N/A',
            'alerta': None,
            'status': 'erro_validacao'
        }

def validar_valor_nf_alto(valor_nf, limite=400000):
    """
    Valida se o valor da NF é alto e sugere frete dedicado
    """
    if not valor_nf:
        return {
            'valor_alto': False,
            'alerta': None
        }
    
    try:
        # Garantir que o valor_nf seja um número
        if isinstance(valor_nf, str):
            valor_nf = valor_nf.replace('.', '').replace(',', '.')
        valor_num = float(valor_nf)
        
        if valor_num >= limite:
            return {
                'valor_alto': True,
                'valor_nf': valor_num,
                'limite': limite,
                'alerta': {
                    'tipo': 'valor_nf_alto',
                    'titulo': '💰 Carga de Alto Valor Detectada',
                    'mensagem': f'Valor da NF (R$ {valor_num:,.2f}) ≥ R$ {limite:,.2f}',
                    'recomendacao': 'Considere usar Frete Dedicado para maior segurança'
                }
            }
        else:
            return {
                'valor_alto': False,
                'valor_nf': valor_num,
                'limite': limite,
                'alerta': None
            }
    except (ValueError, TypeError, AttributeError):
        return {
            'valor_alto': False,
            'alerta': None
        }

def _gerar_alerta_valor_alto_html(validacao_valor):
    """
    Gera HTML para alerta de valor da NF alto sugerindo frete dedicado
    """
    if not validacao_valor or not validacao_valor.get('valor_alto', False):
        return ""
    
    alerta = validacao_valor.get('alerta', {})
    if not alerta:
        return ""
    
    return f"""
    <div class="alerta-valor-alto" style="
        background: linear-gradient(135deg, #ffa726, #ff8a50);
        color: white;
        padding: 16px;
        border-radius: 12px;
        margin: 16px 0;
        border-left: 5px solid #f57c00;
        animation: pulseGold 3s infinite;
        box-shadow: 0 6px 20px rgba(255, 167, 38, 0.4);
        position: relative;
        overflow: hidden;
    ">
        <div style="display: flex; align-items: center; gap: 12px; position: relative; z-index: 2;">
            <span style="font-size: 1.8em;">💰</span>
            <div style="flex: 1;">
                <strong style="font-size: 1.1em; display: block; margin-bottom: 8px;">
                    {alerta.get('titulo', 'Carga de Alto Valor')}
                </strong>
                <div style="font-size: 0.95em; margin-bottom: 12px; opacity: 0.95;">
                    {alerta.get('mensagem', '')}
                </div>
                <div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 8px; margin-bottom: 12px;">
                    <strong>💡 {alerta.get('recomendacao', 'Recomendação')}</strong>
                </div>
                <div style="text-align: center;">
                    <button 
                        onclick="window.open('/?tab=dedicado', '_blank')" 
                        style="
                            background: linear-gradient(135deg, #4caf50, #45a049);
                            color: white;
                            border: none;
                            padding: 12px 24px;
                            border-radius: 8px;
                            font-weight: bold;
                            font-size: 1em;
                            cursor: pointer;
                            box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3);
                            transition: all 0.3s ease;
                        "
                        onmouseover="this.style.transform='scale(1.05)'"
                        onmouseout="this.style.transform='scale(1)'"
                    >
                        🚛 {alerta.get('botao_acao', 'Calcular Frete Dedicado')}
                    </button>
                </div>
            </div>
        </div>
        <div class="shine-effect" style="
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            animation: shine 4s infinite;
        "></div>
    </div>
    """

@app.route("/calcular_frete_fracionado", methods=["POST"])
def calcular_frete_fracionado():
    global ultimoResultadoFracionado, CONTADOR_FRACIONADO
    ip_cliente = obter_ip_cliente()
    usuario = session.get('usuario_logado', 'DESCONHECIDO')
    
    try:
        # Extrair e validar dados do JSON
        data = request.get_json()
        uf_origem = data.get("uf_origem") or data.get("estado_origem")
        cidade_origem = data.get("municipio_origem")
        uf_destino = data.get("uf_destino") or data.get("estado_destino")
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
        
        # Função para calcular peso cubado baseado no tipo de serviço
        def calcular_peso_cubado_por_tipo(cubagem_m3, tipo_servico='fracionado'):
            if not cubagem_m3 or cubagem_m3 <= 0:
                return peso_real * 0.17  # Fallback padrão
            
            if tipo_servico == 'direto':
                return float(cubagem_m3) * 250  # 250 kg/m³ para diretos
            else:
                return float(cubagem_m3) * 166  # 166 kg/m³ para fracionado
        
        # Para esta função, usar peso cubado fracionado como base (será recalculado para diretos)
        peso_cubado_fracionado = calcular_peso_cubado_por_tipo(cubagem, 'fracionado')
        peso_cubado_direto = calcular_peso_cubado_por_tipo(cubagem, 'direto')
        
        # Usar peso cubado fracionado para transferências e agentes tradicionais
        maior_peso_fracionado = max(peso_real, peso_cubado_fracionado)
        # Usar peso cubado direto para agentes diretos
        maior_peso_direto = max(peso_real, peso_cubado_direto)
        
        log_debug(f"[AGENTES] Peso real: {peso_real}kg")
        log_debug(f"[AGENTES] Peso cubado fracionado (166): {peso_cubado_fracionado:.2f}kg")
        log_debug(f"[AGENTES] Peso cubado direto (250): {peso_cubado_direto:.2f}kg")
        log_debug(f"[AGENTES] Maior peso fracionado: {maior_peso_fracionado:.2f}kg")
        log_debug(f"[AGENTES] Maior peso direto: {maior_peso_direto:.2f}kg")

        # VALIDAR SE VALOR DA NF É ALTO E SUGERIR FRETE DEDICADO
        validacao_valor = validar_valor_nf_alto(valor_nf)

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
        maior_peso_usado = melhor_opcao.get('maior_peso', max(peso_real, peso_cubado_fracionado))
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
            "peso_cubado": peso_cubado_fracionado,
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

        # Adicionar validação de valor alto ao resultado
        resultado_final["validacao_valor"] = validacao_valor

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
            'peso_cubado': peso_cubado_fracionado,
            'cubagem': cubagem,
            'valor_nf': valor_nf,
            'estrategia_busca': "AGENTES_REAL_APENAS",
            # Dados de rotas com agentes
            'rotas_agentes': rotas_agentes,
            # Validação de valor alto
            'validacao_valor': validacao_valor
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
        log_debug(f"Erro ao calcular frete fracionado: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erro ao calcular frete fracionado: {str(e)}"})

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
