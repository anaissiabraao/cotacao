import pandas as pd
import datetime
import math
import requests
import polyline
import time
import fpdf
from fpdf import FPDF
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash
import io
import os
import re
import unicodedata
import json
import uuid
import urllib.parse
from dotenv import load_dotenv
import tempfile
from functools import lru_cache, wraps

# Funções auxiliares para formatação e cálculos
def formatar_nome_agente(nome_completo):
    """
    Remove parênteses dos nomes dos agentes, mantendo apenas o nome principal
    Ex: "PTX (Coleta)" -> "PTX"
    """
    if not nome_completo or nome_completo == 'N/A':
        return 'N/A'
    
    # Remover parênteses e seu conteúdo
    nome_limpo = re.sub(r'\s*\([^)]*\)', '', nome_completo).strip()
    return nome_limpo if nome_limpo else nome_completo

def calcular_prazo_total_agentes(opcao, tipo_rota):
    """
    Calcula o prazo total somando os prazos de todos os agentes da rota
    """
    try:
        detalhes = opcao.get('detalhes', {})
        prazo_total = 0
        
        if tipo_rota == 'transferencia_direta':
            # Para transferência direta, usar prazo da transferência
            transferencia = opcao.get('transferencia', {})
            prazo_total = transferencia.get('prazo', 3)
            
        elif tipo_rota == 'agente_direto':
            # Para agente direto, usar prazo do agente
            agente_direto = opcao.get('agente_direto', {})
            prazo_total = agente_direto.get('prazo', 3)
            
        elif tipo_rota == 'coleta_transferencia':
            # Somar prazo da coleta + transferência
            agente_coleta = opcao.get('agente_coleta', {})
            transferencia = opcao.get('transferencia', {})
            prazo_total = (agente_coleta.get('prazo', 1) + transferencia.get('prazo', 2))
            
        elif tipo_rota == 'transferencia_entrega':
            # Somar prazo da transferência + entrega
            transferencia = opcao.get('transferencia', {})
            agente_entrega = opcao.get('agente_entrega', {})
            prazo_total = (transferencia.get('prazo', 2) + agente_entrega.get('prazo', 1))
            
        elif tipo_rota == 'coleta_transferencia_entrega':
            # Somar prazo da coleta + transferência + entrega
            agente_coleta = opcao.get('agente_coleta', {})
            transferencia = opcao.get('transferencia', {})
            agente_entrega = opcao.get('agente_entrega', {})
            prazo_total = (agente_coleta.get('prazo', 1) + transferencia.get('prazo', 2) + agente_entrega.get('prazo', 1))
            
        else:
            # Fallback para outros tipos de rota
            prazo_total = opcao.get('prazo_total', 3)
        
        return max(prazo_total, 1)  # Mínimo de 1 dia
        
    except Exception as e:
        print(f"[PRAZO] Erro ao calcular prazo total: {e}")
        return 3  # Fallback

def obter_bases_rota(opcao, tipo_rota):
    """
    Extrai as bases de origem e destino da rota
    """
    try:
        detalhes = opcao.get('detalhes', {})
        base_origem = 'N/A'
        base_destino = 'N/A'
        
        if tipo_rota == 'transferencia_direta':
            transferencia = opcao.get('transferencia', {})
            base_origem = transferencia.get('origem', transferencia.get('base_origem', 'N/A'))
            base_destino = transferencia.get('destino', transferencia.get('base_destino', 'N/A'))
            
        elif tipo_rota == 'agente_direto':
            agente_direto = opcao.get('agente_direto', {})
            base_origem = agente_direto.get('origem', agente_direto.get('base_origem', 'N/A'))
            base_destino = agente_direto.get('destino', agente_direto.get('base_destino', 'N/A'))
            
        elif tipo_rota == 'coleta_transferencia':
            agente_coleta = opcao.get('agente_coleta', {})
            transferencia = opcao.get('transferencia', {})
            base_origem = agente_coleta.get('base_destino', agente_coleta.get('destino', 'N/A'))
            base_destino = transferencia.get('destino', transferencia.get('base_destino', 'N/A'))
            
        elif tipo_rota == 'transferencia_entrega':
            transferencia = opcao.get('transferencia', {})
            agente_entrega = opcao.get('agente_entrega', {})
            base_origem = transferencia.get('origem', transferencia.get('base_origem', 'N/A'))
            base_destino = agente_entrega.get('base_origem', agente_entrega.get('origem', 'N/A'))
            
        elif tipo_rota == 'coleta_transferencia_entrega':
            agente_coleta = opcao.get('agente_coleta', {})
            transferencia = opcao.get('transferencia', {})
            agente_entrega = opcao.get('agente_entrega', {})
            base_origem = transferencia.get('base_origem', transferencia.get('origem', 'N/A'))
            base_destino = transferencia.get('base_destino', transferencia.get('destino', 'N/A'))
            
        return base_origem, base_destino
        
    except Exception as e:
        print(f"[BASES] Erro ao extrair bases: {e}")
        return 'N/A', 'N/A'

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

# Cache global para base unificada (evitar redefinição)
if '_BASE_UNIFICADA_CACHE' not in globals():
    _BASE_UNIFICADA_CACHE = None
if '_ULTIMO_CARREGAMENTO_BASE' not in globals():
    _ULTIMO_CARREGAMENTO_BASE = 0
if '_CACHE_VALIDADE_BASE' not in globals():
    _CACHE_VALIDADE_BASE = 900  # 15 minutos
# Índices e recortes pré-processados para acelerar filtros
if '_BASE_INDICES_PRONTOS' not in globals():
    _BASE_INDICES_PRONTOS = False
if '_DF_DIRETOS' not in globals():
    _DF_DIRETOS = None
if '_DF_AGENTES' not in globals():
    _DF_AGENTES = None
if '_DF_TRANSFERENCIAS' not in globals():
    _DF_TRANSFERENCIAS = None

# Cache de cálculos por rota
if '_CACHE_ROTAS' not in globals():
    _CACHE_ROTAS = {}
if '_CACHE_ROTAS_TTL' not in globals():
    _CACHE_ROTAS_TTL = 900  # 15 minutos

# Cache global para agentes
_BASE_AGENTES_CACHE = None
_ULTIMO_CARREGAMENTO = 0
_CACHE_VALIDADE = 300  # 5 minutos

# Configuração do token do Melhor Envio
MELHOR_ENVIO_TOKEN = os.getenv('MELHOR_ENVIO_TOKEN')
MELHOR_ENVIO_API_BASE = os.getenv('MELHOR_ENVIO_API_BASE', 'https://api.melhorenvio.com.br')
MELHOR_ENVIO_AUTH_BASE = os.getenv('MELHOR_ENVIO_AUTH_BASE', 'https://melhorenvio.com.br')
MELHOR_ENVIO_CLIENT_ID = os.getenv('MELHOR_ENVIO_CLIENT_ID')
MELHOR_ENVIO_CLIENT_SECRET = os.getenv('MELHOR_ENVIO_CLIENT_SECRET')
MELHOR_ENVIO_SCOPE = os.getenv('MELHOR_ENVIO_SCOPE', '')

# Cache de token Melhor Envio obtido via OAuth
if '_MELHOR_ENVIO_TOKEN_CACHE' not in globals():
    _MELHOR_ENVIO_TOKEN_CACHE = {'token': None, 'exp_ts': 0}

def obter_token_melhor_envio() -> str:
    """Obtém um token válido para a API Melhor Envio.
    1) Usa MELHOR_ENVIO_TOKEN se definido (token manual).
    2) Se não houver, tenta fluxo client_credentials com CLIENT_ID/SECRET.
    3) Mantém cache em memória até expirar.
    """
    global _MELHOR_ENVIO_TOKEN_CACHE, MELHOR_ENVIO_TOKEN
    try:
        agora = time.time()
        # Preferir token manual por variável de ambiente
        if MELHOR_ENVIO_TOKEN:
            return MELHOR_ENVIO_TOKEN
        # Usar token em cache se válido
        if _MELHOR_ENVIO_TOKEN_CACHE.get('token') and _MELHOR_ENVIO_TOKEN_CACHE.get('exp_ts', 0) - 60 > agora:
            return _MELHOR_ENVIO_TOKEN_CACHE['token']
        # Tentar client credentials
        if not (MELHOR_ENVIO_CLIENT_ID and MELHOR_ENVIO_CLIENT_SECRET):
            return None
        token_url = f"{MELHOR_ENVIO_AUTH_BASE.rstrip('/')}/oauth/token"
        # 1) Tentar client_secret_basic (Authorization: Basic base64(id:secret))
        import base64 as _b64
        basic = _b64.b64encode(f"{MELHOR_ENVIO_CLIENT_ID}:{MELHOR_ENVIO_CLIENT_SECRET}".encode('utf-8')).decode('utf-8')
        form_headers = {'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': f'Basic {basic}'}
        form_payload = {'grant_type': 'client_credentials'}
        if MELHOR_ENVIO_SCOPE:
            form_payload['scope'] = MELHOR_ENVIO_SCOPE
        resp = requests.post(token_url, data=form_payload, headers=form_headers, timeout=20)
        # 2) Fallback: client_secret_post (id/secret no body, sem Basic)
        if resp.status_code >= 400:
            headers2 = {'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
            payload2 = {
                'grant_type': 'client_credentials',
                'client_id': MELHOR_ENVIO_CLIENT_ID,
                'client_secret': MELHOR_ENVIO_CLIENT_SECRET,
            }
            if MELHOR_ENVIO_SCOPE:
                payload2['scope'] = MELHOR_ENVIO_SCOPE
            resp = requests.post(token_url, data=payload2, headers=headers2, timeout=20)
        # 3) Último fallback em JSON
        if resp.status_code >= 400:
            headers3 = {'Accept':'application/json','Content-Type':'application/json'}
            payload3 = {
                'grant_type': 'client_credentials',
                'client_id': MELHOR_ENVIO_CLIENT_ID,
                'client_secret': MELHOR_ENVIO_CLIENT_SECRET,
            }
            if MELHOR_ENVIO_SCOPE:
                payload3['scope'] = MELHOR_ENVIO_SCOPE
            resp = requests.post(token_url, json=payload3, headers=headers3, timeout=20)
        resp.raise_for_status()
        data = resp.json() or {}
        access_token = data.get('access_token') or data.get('token')
        expires_in = int(data.get('expires_in', 3600))
        if not access_token:
            return None
        _MELHOR_ENVIO_TOKEN_CACHE['token'] = access_token
        _MELHOR_ENVIO_TOKEN_CACHE['exp_ts'] = agora + max(60, expires_in)
        return access_token
    except Exception as e:
        try:
            err_txt = resp.text if 'resp' in locals() else str(e)
            status = resp.status_code if 'resp' in locals() else 'N/A'
            print(f"[MelhorEnvio] Falha ao obter token ({status}): {err_txt}")
        except Exception:
            print(f"[MelhorEnvio] Falha ao obter token: {e}")
        return None

def _melhor_envio_headers():
    """Monta headers com Bearer token válido da Melhor Envio (manual ou OAuth)."""
    token = obter_token_melhor_envio()
    if not token:
        return None
    return {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'User-Agent': 'PortoExCotacao/1.0'
    }

# SISTEMA DE USUÁRIOS E CONTROLE DE ACESSO
# Evitar redefinições posteriores: se já existir, não sobrescrever
if 'USUARIOS_SISTEMA' not in globals():
    USUARIOS_SISTEMA = {}

# Usuários base
USUARIOS_SISTEMA.update({
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
})

# Usuários solicitados (senha padrão 1234)
USUARIOS_SISTEMA.update({
    'tiago.comercial': {
        'senha': '1234', 'tipo': 'comercial', 'nome': 'Tiago (Comercial)',
        'permissoes': ['calcular', 'historico', 'exportar']
    },
    'sabrina.comercial': {
        'senha': '1234', 'tipo': 'comercial', 'nome': 'Sabrina (Comercial)',
        'permissoes': ['calcular', 'historico', 'exportar']
    },
    'uriel.comercial': {
        'senha': '1234', 'tipo': 'comercial', 'nome': 'Uriel (Comercial)',
        'permissoes': ['calcular', 'historico', 'exportar']
    },
    'caio.comercial': {
        'senha': '1234', 'tipo': 'comercial', 'nome': 'Caio (Comercial)',
        'permissoes': ['calcular', 'historico', 'exportar']
    },
    'stefany.comercial': {
        'senha': '1234', 'tipo': 'comercial', 'nome': 'Stefany (Comercial)',
        'permissoes': ['calcular', 'historico', 'exportar']
    },
    'gabriel.controladoria': {
        'senha': '1234', 'tipo': 'controladoria', 'nome': 'Gabriel (Controladoria)',
        'permissoes': ['calcular', 'historico', 'exportar', 'admin']
    },
    'leo.controladoria': {
        'senha': '1234', 'tipo': 'controladoria', 'nome': 'Leo (Controladoria)',
        'permissoes': ['calcular', 'historico', 'exportar']
    },
    'chico.controladoria': {
        'senha': '1234', 'tipo': 'controladoria', 'nome': 'Chico (Controladoria)',
        'permissoes': ['calcular', 'historico', 'exportar']
    }
})

# Controle de logs de acesso (evitar redefinição)
if 'LOGS_SISTEMA' not in globals():
    LOGS_SISTEMA = []
if 'HISTORICO_DETALHADO' not in globals():
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
        "SALVADOR": "SALVADOR",
        "SSA": "SALVADOR",
        "NAVEGANTES": "NAVEGANTES",
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

@lru_cache(maxsize=1000)
def normalizar_cidade_nome(cidade):
    """
    Normaliza o nome da cidade, removendo a parte após o hífen.
    Com cache para melhorar performance
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

# Configuração OAuth Google - Produção
app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '1003471136320-kgbh8cgr04qk18fcgc7pqe20np5a7shq.apps.googleusercontent.com')
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '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')

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
    global _CACHE_ROTAS, _BASE_UNIFICADA_CACHE, _BASE_INDICES_PRONTOS
    _CACHE_ROTAS = {}
    _BASE_UNIFICADA_CACHE = None
    _BASE_INDICES_PRONTOS = False
    return jsonify({"ok": True, "message": "Cache limpo"})
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
        # Normalizar entradas
        usuario = (usuario or '').strip().lower()
        senha = (senha or '').strip()
        
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

# Login com Google OAuth
@app.route('/login/google')
def login_google():
    try:
        client_id = app.config.get('GOOGLE_OAUTH_CLIENT_ID')
        redirect_uri = url_for('google_auth_callback', _external=True)
        state = uuid.uuid4().hex
        session['oauth_state'] = state
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'access_type': 'offline',
            'prompt': 'select_account'
        }
        auth_url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)
        return redirect(auth_url)
    except Exception as e:
        print(f"[OAUTH] Erro ao iniciar login Google: {e}")
        flash('Erro ao iniciar login com Google.', 'error')
        return redirect(url_for('login'))

@app.route('/auth/google/callback')
def google_auth_callback():
    try:
        code = request.args.get('code')
        state = request.args.get('state')
        if not code or not state or state != session.get('oauth_state'):
            flash('Requisição inválida de login Google.', 'error')
            return redirect(url_for('login'))

        token_url = 'https://oauth2.googleapis.com/token'
        redirect_uri = url_for('google_auth_callback', _external=True)
        data = {
            'code': code,
            'client_id': app.config.get('GOOGLE_OAUTH_CLIENT_ID'),
            'client_secret': app.config.get('GOOGLE_OAUTH_CLIENT_SECRET'),
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        token_resp = requests.post(token_url, data=data, timeout=10)
        token_json = token_resp.json()
        access_token = token_json.get('access_token')
        if not access_token:
            print(f"[OAUTH] Token response: {token_json}")
            flash('Não foi possível autenticar com o Google.', 'error')
            return redirect(url_for('login'))

        userinfo_resp = requests.get(
            'https://openidconnect.googleapis.com/v1/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        userinfo = userinfo_resp.json()
        email = (userinfo.get('email') or '').lower().strip()
        nome = userinfo.get('name') or email
        if not email:
            flash('Conta Google sem e-mail disponível.', 'error')
            return redirect(url_for('login'))

        # Estratégia de vinculação: parte antes do @ deve existir como usuário do sistema
        username = email.split('@')[0]
        if username in USUARIOS_SISTEMA:
            # Efetivar login
            session.clear()
            session['usuario_logado'] = username
            session['tipo_usuario'] = USUARIOS_SISTEMA[username]['tipo']
            session['nome_usuario'] = USUARIOS_SISTEMA[username]['nome']
            session.permanent = True

            ip_cliente = obter_ip_cliente()
            log_acesso(username, 'LOGIN_GOOGLE_SUCESSO', ip_cliente, f"Login via Google: {email}")
            flash(f'Bem-vindo, {USUARIOS_SISTEMA[username]["nome"]}!', 'success')
            return redirect(url_for('index'))

        # Alternativa: procurar por campo 'email' cadastrado no usuário
        for user, dados in USUARIOS_SISTEMA.items():
            if str(dados.get('email', '')).lower().strip() == email:
                session.clear()
                session['usuario_logado'] = user
                session['tipo_usuario'] = dados['tipo']
                session['nome_usuario'] = dados['nome']
                session.permanent = True
                ip_cliente = obter_ip_cliente()
                log_acesso(user, 'LOGIN_GOOGLE_SUCESSO', ip_cliente, f"Login via Google: {email}")
                flash(f'Bem-vindo, {dados["nome"]}!', 'success')
                return redirect(url_for('index'))

        flash('Sua conta Google não está vinculada a um usuário do sistema.', 'error')
        return redirect(url_for('login'))
    except Exception as e:
        print(f"[OAUTH] Erro no callback do Google: {e}")
        flash('Erro ao autenticar com o Google.', 'error')
        return redirect(url_for('login'))

# Health check endpoint para Render
@app.route("/health")
def health_check():
    """Endpoint de health check para verificar se a aplicação está funcionando."""
    try:
        # Verificar se a aplicação está funcionando
        base_df = carregar_base_unificada()
        total_registros = len(base_df) if base_df is not None else 0
        status = {
            "status": "healthy",
            "timestamp": pd.Timestamp.now().isoformat(),
            "version": "1.0.0",
            "services": {
                "database": "online" if total_registros > 0 else "offline",
                "records": total_registros
            }
        }
        return jsonify(status), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy", 
            "error": str(e),
            "timestamp": pd.Timestamp.now().isoformat()
        }), 503

HISTORICO_PESQUISAS = []
CONTADOR_DEDICADO = 1
CONTADOR_FRACIONADO = 1
ultimoResultadoDedicado = None
ultimoResultadoFracionado = None
app.config["UPLOAD_FOLDER"] = "static"

"""
Removido suporte a Excel no boot (bloco duplicado). Startup não faz mais I/O de Excel
e não exibe logs relacionados ao arquivo. A base é carregada sob demanda do PostgreSQL.
"""
df_unificado = pd.DataFrame()

def geocode(municipio, uf):
    try:
        # Normalizar cidade e UF
        cidade_norm = normalizar_cidade(municipio)
        uf_norm = normalizar_uf(uf)
        
        # Primeiro, tentar obter do cache de coordenadas
        from utils.coords_cache import COORDS_CACHE
        chave_cache = f"{cidade_norm}-{uf_norm}"
        
        if chave_cache in COORDS_CACHE:
            coords = COORDS_CACHE[chave_cache]
            return coords
        
        # Se não encontrou no cache, tentar a API do OpenStreetMap
        
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
            return coords
        
        # 5. Fallback final: Brasília
        coords = [-15.7801, -47.9292]
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
            # Calcular pedágios usando estimativa simples
            pedagio_real = rota_info["distancia"] * 0.05  # R$ 0,05 por km
            pedagio_detalhes = {"fonte": "Estimativa baseada na distância", "valor_por_km": 0.05}
    
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

def gerar_pedagios_estimados_mapa(rota_info, veiculo, pedagio_real, distancia_km):
    """
    Gera estrutura de pedágios para exibição no mapa (placeholder leve).
    - Retorna None se não houver pedágio real.
    - Caso exista, distribui o total em marcadores ao longo da rota.
    """
    try:
        if not rota_info or not isinstance(rota_info, dict):
            return None
        if not pedagio_real or pedagio_real <= 0:
            return None
        pontos = rota_info.get("rota_pontos") or []
        if not pontos or len(pontos) < 2:
            return None

        # Distribuir em até 3 marcadores ao longo da rota
        num_marcos = min(3, max(1, len(pontos) // max(1, len(pontos) // 3)))
        interval = max(1, len(pontos) // (num_marcos + 1))
        marcadores = []
        for i in range(1, num_marcos + 1):
            idx = min(len(pontos) - 1, i * interval)
            latlon = pontos[idx]
            marcadores.append({
                "pos": latlon,
                "valor": round(pedagio_real / num_marcos, 2)
            })

        return {
            "total": round(pedagio_real, 2),
            "marcadores": marcadores,
            "veiculo": veiculo,
            "distancia_km": distancia_km
        }
    except Exception:
        return None

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

def carregar_base_unificada_db_only():
    """
    Carrega a Base Unificada do PostgreSQL (schema public, tabela base_unificada) com cache.
    Sem fallback para Excel.
    """
    global _BASE_UNIFICADA_CACHE, _ULTIMO_CARREGAMENTO_BASE, _BASE_INDICES_PRONTOS, _DF_DIRETOS, _DF_AGENTES, _DF_TRANSFERENCIAS
    
    tempo_atual = time.time()
    if (
        _BASE_UNIFICADA_CACHE is not None
        and (tempo_atual - _ULTIMO_CARREGAMENTO_BASE) < _CACHE_VALIDADE_BASE
    ):
        # Garantir que recortes estejam prontos mesmo no retorno por cache
        try:
            df_cached = _BASE_UNIFICADA_CACHE
            needs_rebuild = (
                not _BASE_INDICES_PRONTOS or
                _DF_DIRETOS is None or len(_DF_DIRETOS) == 0 or
                _DF_AGENTES is None or len(_DF_AGENTES) == 0 or
                _DF_TRANSFERENCIAS is None or len(_DF_TRANSFERENCIAS) == 0
            )
            if needs_rebuild and df_cached is not None:
                # Padronizar nomes de colunas do cache
                try:
                    df_cached.columns = df_cached.columns.astype(str).str.strip()
                except Exception:
                    pass
                # Criar colunas auxiliares se ausentes
                if 'origem_norm' not in df_cached.columns and 'Origem' in df_cached.columns:
                    df_cached['origem_norm'] = (
                        df_cached['Origem'].astype(str)
                        .str.upper().str.normalize('NFKD').str.encode('ascii', 'ignore').str.decode('ascii').str.strip()
                    )
                if 'destino_norm' not in df_cached.columns and 'Destino' in df_cached.columns:
                    df_cached['destino_norm'] = (
                        df_cached['Destino'].astype(str)
                        .str.upper().str.normalize('NFKD').str.encode('ascii', 'ignore').str.decode('ascii').str.strip()
                    )
                if 'fornecedor_upper' not in df_cached.columns and 'Fornecedor' in df_cached.columns:
                    df_cached['fornecedor_upper'] = df_cached['Fornecedor'].astype(str).str.upper()
                if 'tipo_norm' not in df_cached.columns and 'Tipo' in df_cached.columns:
                    df_cached['tipo_norm'] = (
                        df_cached['Tipo'].astype(str)
                        .str.upper().str.normalize('NFKD').str.encode('ascii', 'ignore').str.decode('ascii').str.strip()
                    )
                if 'uf_upper' not in df_cached.columns and 'UF' in df_cached.columns:
                    df_cached['uf_upper'] = df_cached['UF'].astype(str).str.upper()

                # Recalcular recortes
                if 'tipo_norm' in df_cached.columns:
                    _DF_DIRETOS = df_cached[df_cached['tipo_norm'] == 'DIRETO'].copy()
                    _DF_AGENTES = df_cached[df_cached['tipo_norm'] == 'AGENTE'].copy()
                    _DF_TRANSFERENCIAS = df_cached[df_cached['tipo_norm'] == 'TRANSFERENCIA'].copy()
                elif 'Tipo' in df_cached.columns:
                    _DF_DIRETOS = df_cached[df_cached['Tipo'] == 'Direto'].copy()
                    _DF_AGENTES = df_cached[df_cached['Tipo'] == 'Agente'].copy()
                    _DF_TRANSFERENCIAS = df_cached[df_cached['Tipo'] == 'Transferência'].copy()
                else:
                    _DF_DIRETOS = df_cached.iloc[0:0]
                    _DF_AGENTES = df_cached.iloc[0:0]
                    _DF_TRANSFERENCIAS = df_cached.iloc[0:0]
                _BASE_INDICES_PRONTOS = True
                print(f"[BASE] 🔁 Rebuild recortes via cache | diretos={len(_DF_DIRETOS)} agentes={len(_DF_AGENTES)} transf={len(_DF_TRANSFERENCIAS)}")
        except Exception as _cache_rebuild_err:
            print(f"[BASE] ⚠️ Falha ao reconstruir recortes do cache: {_cache_rebuild_err}")
        return _BASE_UNIFICADA_CACHE
        
    # Tentar PostgreSQL primeiro (a menos que desabilitado nas configurações)
    try:
        try:
            if 'ADMIN_CONFIG' in globals() and not ADMIN_CONFIG.get('use_db', True):
                raise RuntimeError('PostgreSQL desabilitado via configurações do Admin')
        except Exception:
            pass
        import psycopg2
        db_url = (
            os.getenv("DATABASE_URL")
            or os.getenv("POSTGRES_URL")
            or os.getenv("DATABASE_URL_INTERNAL")
            or os.getenv("DATABASE_URI")
            or None
        )
        if db_url:
            # Garantir sslmode=require se não presente (Render e outros providers)
            if "sslmode=" not in db_url:
                sep = "&" if "?" in db_url else "?"
                db_url = f"{db_url}{sep}sslmode=require"
            conn = psycopg2.connect(db_url)
        else:
            db_name = os.getenv("DB_NAME", "base_unificada")
            db_user = os.getenv("DB_USER", "postgres")
            db_password = os.getenv("DB_PASSWORD", "KIzUlYo78kowk6QkF2Y3F26SJpQPgYHp")
            db_host = os.getenv("DB_HOST", "dpg-d2d2o524d50c738435jg-a.oregon-postgres.render.com")
            db_port = os.getenv("DB_PORT", "5432")
            # Garantir SSL para provedores gerenciados (ex.: Render)
            db_sslmode = os.getenv("DB_SSLMODE") or ("require" if "render.com" in str(db_host) else "prefer")
            conn = psycopg2.connect(
                dbname=db_name,
                user=db_user,
                password=db_password,
                host=db_host,
                port=db_port,
                sslmode=db_sslmode,
            )
        cur = conn.cursor()
        cur.execute("SELECT * FROM public.base_unificada")
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        cur.close()
        conn.close()

        df_base = pd.DataFrame(rows, columns=colnames)
        # Garantir nomes de colunas sem espaços/BOM/artefatos
        try:
            df_base.columns = (
                df_base.columns.astype(str)
                .str.replace('\ufeff', '', regex=False)
                .str.strip()
            )
        except Exception:
            pass
        # Se o banco retornou vazio, forçar fallback CSV
        if df_base is None or len(df_base) == 0:
            raise RuntimeError("DB retornou 0 linhas para base_unificada")
        # Pré-processar: normalizar textos frequentes e criar recortes por tipo
        for col in [
            'Fornecedor', 'Tipo', 'Origem', 'Destino', 'Base Origem', 'Base Destino', 'UF'
        ]:
            if col in df_base.columns:
                df_base[col] = df_base[col].astype(str).str.strip()

        # Colunas normalizadas (vetorizadas) para filtros rápidos
        def _norm_series(s):
            return (
                s.astype(str)
                 .str.upper()
                 .str.normalize('NFKD')
                 .str.encode('ascii', 'ignore')
                 .str.decode('ascii')
                 .str.strip()
            )

        if 'Origem' in df_base.columns:
            df_base['origem_norm'] = _norm_series(df_base['Origem'])
        if 'Destino' in df_base.columns:
            df_base['destino_norm'] = _norm_series(df_base['Destino'])
        if 'Base Origem' in df_base.columns:
            df_base['base_origem_norm'] = _norm_series(df_base['Base Origem'])
        if 'Base Destino' in df_base.columns:
            df_base['base_destino_norm'] = _norm_series(df_base['Base Destino'])
        if 'Fornecedor' in df_base.columns:
            df_base['fornecedor_upper'] = df_base['Fornecedor'].astype(str).str.upper()
        if 'Tipo' in df_base.columns:
            df_base['tipo_upper'] = df_base['Tipo'].astype(str).str.upper()
            # Normalização robusta do tipo (sem acento, upper)
            try:
                df_base['tipo_norm'] = (
                    df_base['Tipo'].astype(str)
                    .str.upper()
                    .str.normalize('NFKD')
                    .str.encode('ascii', 'ignore')
                    .str.decode('ascii')
                    .str.strip()
                )
            except Exception:
                import unicodedata as _ud
                df_base['tipo_norm'] = df_base['Tipo'].astype(str).apply(
                    lambda x: _ud.normalize('NFKD', x).encode('ascii', 'ignore').decode('ascii')
                ).str.upper().str.strip()
        if 'UF' in df_base.columns:
            df_base['uf_upper'] = df_base['UF'].astype(str).str.upper()

        # Conversão de colunas numéricas que podem vir como string com vírgula decimal
        try:
            numeric_cols = [
                'VALOR MÍNIMO ATÉ 10', '20', '30', '50', '70', '100', '150', '200', '300', '500',
                'Acima 500', 'Acima 1000', 'Acima 2000', 'Pedagio (100 Kg)', 'EXCEDENTE', 'Seguro',
                'Gris Min', 'Gris Exc', 'TDA', 'TAS', 'DESPACHO'
            ]
            for col in [c for c in numeric_cols if c in df_base.columns]:
                with pd.option_context('mode.chained_assignment', None):
                    df_base[col] = pd.to_numeric(
                        df_base[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
                        errors='coerce'
                    ).fillna(0)
        except Exception:
            pass

        # Recortes
        if 'tipo_norm' in df_base.columns:
            # Tentar match exato e, se vazio, usar contains
            _DF_DIRETOS = df_base[df_base['tipo_norm'] == 'DIRETO'].copy()
            if len(_DF_DIRETOS) == 0:
                _DF_DIRETOS = df_base[df_base['tipo_norm'].str.contains('DIRETO', na=False)].copy()
            _DF_AGENTES = df_base[df_base['tipo_norm'] == 'AGENTE'].copy()
            if len(_DF_AGENTES) == 0:
                _DF_AGENTES = df_base[df_base['tipo_norm'].str.contains('AGENTE', na=False)].copy()
            _DF_TRANSFERENCIAS = df_base[df_base['tipo_norm'] == 'TRANSFERENCIA'].copy()
            if len(_DF_TRANSFERENCIAS) == 0:
                _DF_TRANSFERENCIAS = df_base[df_base['tipo_norm'].str.contains('TRANSFER', na=False)].copy()
        elif 'Tipo' in df_base.columns:
            _DF_DIRETOS = df_base[df_base['Tipo'] == 'Direto'].copy()
            _DF_AGENTES = df_base[df_base['Tipo'] == 'Agente'].copy()
            _DF_TRANSFERENCIAS = df_base[df_base['Tipo'] == 'Transferência'].copy()
        else:
            _DF_DIRETOS = df_base.iloc[0:0]
            _DF_AGENTES = df_base.iloc[0:0]
            _DF_TRANSFERENCIAS = df_base.iloc[0:0]
        _BASE_INDICES_PRONTOS = True
        try:
            tipos_info = (
                df_base['tipo_norm'].value_counts(dropna=False).to_dict() if 'tipo_norm' in df_base.columns
                else (df_base['Tipo'].astype(str).value_counts(dropna=False).to_dict() if 'Tipo' in df_base.columns else {})
            )
            print(f"[BASE] 📊 Tipos (DB): {tipos_info} | diretos={len(_DF_DIRETOS)} agentes={len(_DF_AGENTES)} transf={len(_DF_TRANSFERENCIAS)}")
        except Exception:
            pass

        _BASE_UNIFICADA_CACHE = df_base
        _ULTIMO_CARREGAMENTO_BASE = tempo_atual
        print("[BASE] ✅ Base Unificada carregada do PostgreSQL")
        return df_base
    except Exception as db_err:
        print(f"[BASE] ⚠️ Falha ao carregar do PostgreSQL: {db_err}")
        
    # Fallback: tentar CSV local para não interromper o sistema
    try:
        csv_candidates = [
            os.path.join(os.path.dirname(__file__), 'data', 'Base_Unificada.csv'),
            os.path.join('cotacao', 'data', 'Base_Unificada.csv'),
            os.path.join('data', 'Base_Unificada.csv')
        ]
        csv_path = next((p for p in csv_candidates if os.path.exists(p)), None)
        if csv_path:
            print(f"[BASE] ⚠️ Usando fallback CSV: {csv_path}")
            # Tentar automaticamente separadores e codificações comuns
            df_base = None
            sep_candidates = [',', ';', '\t', None]
            enc_candidates = ['utf-8', 'utf-8-sig', 'latin-1']
            for _sep in sep_candidates:
                for _enc in enc_candidates:
                    try:
                        df_try = pd.read_csv(
                            csv_path,
                            dtype=str,
                            keep_default_na=False,
                            sep=_sep,
                            encoding=_enc,
                            engine='python' if _sep is None else 'c'
                        )
                        # Considerar válido se tiver colunas chaves
                        cols = set(df_try.columns.str.strip())
                        if {'Fornecedor', 'Tipo', 'Origem', 'Destino'}.issubset(cols) or len(cols) > 6:
                            df_base = df_try
                            # Padronizar nomes de colunas imediatamente após a leitura
                            try:
                                df_base.columns = (
                                    df_base.columns.astype(str)
                                    .str.replace('\ufeff', '', regex=False)
                                    .str.strip()
                                )
                            except Exception:
                                pass
                            print(f"[BASE] ✅ CSV lido com sep='{_sep}' encoding='{_enc}' colunas={len(cols)}")
                            break
                    except Exception:
                        continue
                if df_base is not None:
                    break
            if df_base is None:
                # Última tentativa simples
                df_base = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
            # Garantir nomes de colunas sem espaços/BOM/artefatos
            try:
                df_base.columns = (
                    df_base.columns.astype(str)
                    .str.replace('\ufeff', '', regex=False)
                    .str.strip()
                )
            except Exception:
                pass
            # Ajustar tipos numéricos comuns após leitura como texto quando aplicável
            for col in ['Prazo']:
                if col in df_base.columns:
                    with pd.option_context('mode.chained_assignment', None):
                        df_base[col] = pd.to_numeric(df_base[col], errors='coerce').fillna(0).astype(int)

            # Normalizações e colunas auxiliares
            for col in [
                'Fornecedor', 'Tipo', 'Origem', 'Destino', 'Base Origem', 'Base Destino', 'UF'
            ]:
                if col in df_base.columns:
                    df_base[col] = df_base[col].astype(str).str.strip()

            def _norm_series(s):
                return (
                    s.astype(str)
                     .str.upper()
                     .str.normalize('NFKD')
                     .str.encode('ascii', 'ignore')
                     .str.decode('ascii')
                     .str.strip()
                )

            if 'Origem' in df_base.columns:
                df_base['origem_norm'] = _norm_series(df_base['Origem'])
            if 'Destino' in df_base.columns:
                df_base['destino_norm'] = _norm_series(df_base['Destino'])
            if 'Base Origem' in df_base.columns:
                df_base['base_origem_norm'] = _norm_series(df_base['Base Origem'])
            if 'Base Destino' in df_base.columns:
                df_base['base_destino_norm'] = _norm_series(df_base['Base Destino'])
            if 'Fornecedor' in df_base.columns:
                df_base['fornecedor_upper'] = df_base['Fornecedor'].astype(str).str.upper()
            if 'Tipo' in df_base.columns:
                df_base['tipo_upper'] = df_base['Tipo'].astype(str).str.upper()
                try:
                    df_base['tipo_norm'] = (
                        df_base['Tipo'].astype(str)
                        .str.upper()
                        .str.normalize('NFKD')
                        .str.encode('ascii', 'ignore')
                        .str.decode('ascii')
                        .str.strip()
                    )
                except Exception:
                    df_base['tipo_norm'] = df_base['tipo_upper']
            if 'UF' in df_base.columns:
                df_base['uf_upper'] = df_base['UF'].astype(str).str.upper()

            # Conversão de colunas numéricas que podem vir como string com vírgula decimal (CSV)
            try:
                numeric_cols = [
                    'VALOR MÍNIMO ATÉ 10', '20', '30', '50', '70', '100', '150', '200', '300', '500',
                    'Acima 500', 'Acima 1000', 'Acima 2000', 'Pedagio (100 Kg)', 'EXCEDENTE', 'Seguro',
                    'Gris Min', 'Gris Exc', 'TDA', 'TAS', 'DESPACHO'
                ]
                for col in [c for c in numeric_cols if c in df_base.columns]:
                    with pd.option_context('mode.chained_assignment', None):
                        df_base[col] = pd.to_numeric(
                            df_base[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
                            errors='coerce'
                        ).fillna(0)
            except Exception:
                pass

            # Recortes
            if 'tipo_norm' in df_base.columns:
                _DF_DIRETOS = df_base[df_base['tipo_norm'] == 'DIRETO'].copy()
                _DF_AGENTES = df_base[df_base['tipo_norm'] == 'AGENTE'].copy()
                _DF_TRANSFERENCIAS = df_base[df_base['tipo_norm'] == 'TRANSFERENCIA'].copy()
            elif 'Tipo' in df_base.columns:
                _DF_DIRETOS = df_base[df_base.get('Tipo', '').astype(str) == 'Direto'].copy()
                _DF_AGENTES = df_base[df_base.get('Tipo', '').astype(str) == 'Agente'].copy()
                _DF_TRANSFERENCIAS = df_base[df_base.get('Tipo', '').astype(str) == 'Transferência'].copy()
            else:
                _DF_DIRETOS = df_base.iloc[0:0]
                _DF_AGENTES = df_base.iloc[0:0]
                _DF_TRANSFERENCIAS = df_base.iloc[0:0]
            _BASE_INDICES_PRONTOS = True
            try:
                tipos_info = (
                    df_base['tipo_norm'].value_counts(dropna=False).to_dict() if 'tipo_norm' in df_base.columns
                    else (df_base['Tipo'].astype(str).value_counts(dropna=False).to_dict() if 'Tipo' in df_base.columns else {})
                )
                print(f"[BASE] 📊 Tipos (CSV): {tipos_info} | diretos={len(_DF_DIRETOS)} agentes={len(_DF_AGENTES)} transf={len(_DF_TRANSFERENCIAS)}")
            except Exception:
                pass

            _BASE_UNIFICADA_CACHE = df_base
            _ULTIMO_CARREGAMENTO_BASE = time.time()
            return df_base
    except Exception as csv_err:
        print(f"[BASE] ❌ Fallback CSV falhou: {csv_err}")

    print("[BASE] ❌ Banco e CSV indisponíveis para carregar base_unificada")
    return None

# Substituir o DataFrame carregado do Excel por dados do PostgreSQL, se disponível
try:
    _df_db_boot = carregar_base_unificada()
    if _df_db_boot is not None and len(_df_db_boot) > 0:
        df_unificado = _df_db_boot
        print("[BASE] 🔄 df_unificado substituído pelos dados do PostgreSQL no boot")
except Exception as _boot_e:
    print(f"[BASE] ⚠️ Não foi possível substituir df_unificado pelo DB no boot: {_boot_e}")


def calcular_frete_fracionado_multiplas_bases(origem, uf_origem, destino, uf_destino, peso, cubagem, valor_nf=None, bases_intermediarias=None):
    """
    Calcular frete fracionado usando múltiplas bases intermediárias
    Permite ao usuário escolher bases para compor a viagem (ex: SAO -> ITJ -> SSZ -> SJP)
    """
    try:
        tempo_inicio = time.time()
        todas_opcoes = []
        
        # Carregar base unificada
        df_base = carregar_base_unificada()
        if df_base is None:
            return {
                'error': 'É necessário fornecer exatamente 1 base intermediária para compor a viagem (ex: SAO)',
                'sem_opcoes': True
            }
        
        # Normalizar cidades
        origem_norm = normalizar_cidade_nome(origem)
        destino_norm = normalizar_cidade_nome(destino)
        uf_origem_norm = normalizar_uf(uf_origem)
        uf_destino_norm = normalizar_uf(uf_destino)
        
        print(f"[FRACIONADO] 🔍 Buscando serviços para: {origem_norm}/{uf_origem_norm} → {destino_norm}/{uf_destino_norm}")
        
        return {
            'opcoes': todas_opcoes,
            'total_opcoes': len(todas_opcoes),
            'tempo_processamento': time.time() - tempo_inicio,
            'origem': origem_norm,
            'destino': destino_norm,
            'uf_origem': uf_origem_norm,
            'uf_destino': uf_destino_norm
        }
        
    except Exception as e:
        print(f"[FRACIONADO] ❌ Erro geral: {e}")
        return {
            'sem_opcoes': True,
            'mensagem': 'Erro interno no processamento',
            'detalhes': str(e)
        }

def calcular_prazo_total_agentes(opcao, tipo_rota):
    """
    Calcula o prazo total somando os prazos de todos os agentes da rota
    """
    try:
        detalhes = opcao.get('detalhes', {})
        prazo_total = 0
        
        if tipo_rota == 'transferencia_direta':
            # Para transferência direta, usar prazo da transferência
            transferencia = opcao.get('transferencia', {})
            prazo_total = transferencia.get('prazo', 3)
            
        elif tipo_rota == 'agente_direto':
            # Para agente direto, usar prazo do agente
            agente_direto = opcao.get('agente_direto', {})
            prazo_total = agente_direto.get('prazo', 3)
            
        elif tipo_rota == 'coleta_transferencia':
            # Somar prazo da coleta + transferência
            agente_coleta = opcao.get('agente_coleta', {})
            transferencia = opcao.get('transferencia', {})
            prazo_total = (agente_coleta.get('prazo', 1) + transferencia.get('prazo', 2))
            
        elif tipo_rota == 'transferencia_entrega':
            # Somar prazo da transferência + entrega
            transferencia = opcao.get('transferencia', {})
            agente_entrega = opcao.get('agente_entrega', {})
            prazo_total = (transferencia.get('prazo', 2) + agente_entrega.get('prazo', 1))
            
        elif tipo_rota == 'coleta_transferencia_entrega':
            # Somar prazo da coleta + transferência + entrega
            agente_coleta = opcao.get('agente_coleta', {})
            transferencia = opcao.get('transferencia', {})
            agente_entrega = opcao.get('agente_entrega', {})
            prazo_total = (agente_coleta.get('prazo', 1) + transferencia.get('prazo', 2) + agente_entrega.get('prazo', 1))
            
        else:
            # Fallback para outros tipos de rota
            prazo_total = opcao.get('prazo_total', 3)
        
        return max(prazo_total, 1)  # Mínimo de 1 dia
        
    except Exception as e:
        print(f"[PRAZO] Erro ao calcular prazo total: {e}")
        return 3  # Fallback

def obter_bases_rota(opcao, tipo_rota):
    """
    Extrai as bases de origem e destino da rota
    """
    try:
        detalhes = opcao.get('detalhes', {})
        base_origem = 'N/A'
        base_destino = 'N/A'
        
        if tipo_rota == 'transferencia_direta':
            transferencia = opcao.get('transferencia', {})
            base_origem = transferencia.get('origem', transferencia.get('base_origem', 'N/A'))
            base_destino = transferencia.get('destino', transferencia.get('base_destino', 'N/A'))
            
        elif tipo_rota == 'agente_direto':
            agente_direto = opcao.get('agente_direto', {})
            base_origem = agente_direto.get('origem', agente_direto.get('base_origem', 'N/A'))
            base_destino = agente_direto.get('destino', agente_direto.get('base_destino', 'N/A'))
            
        elif tipo_rota == 'coleta_transferencia':
            agente_coleta = opcao.get('agente_coleta', {})
            transferencia = opcao.get('transferencia', {})
            base_origem = agente_coleta.get('base_destino', agente_coleta.get('destino', 'N/A'))
            base_destino = transferencia.get('destino', transferencia.get('base_destino', 'N/A'))
            
        elif tipo_rota == 'transferencia_entrega':
            transferencia = opcao.get('transferencia', {})
            agente_entrega = opcao.get('agente_entrega', {})
            base_origem = transferencia.get('origem', transferencia.get('base_origem', 'N/A'))
            base_destino = agente_entrega.get('base_origem', agente_entrega.get('origem', 'N/A'))
            
        elif tipo_rota == 'coleta_transferencia_entrega':
            agente_coleta = opcao.get('agente_coleta', {})
            transferencia = opcao.get('transferencia', {})
            agente_entrega = opcao.get('agente_entrega', {})
            base_origem = transferencia.get('base_origem', transferencia.get('origem', 'N/A'))
            base_destino = transferencia.get('base_destino', transferencia.get('destino', 'N/A'))
            
        return base_origem, base_destino
        
    except Exception as e:
        print(f"[BASES] Erro ao extrair bases: {e}")
        return 'N/A', 'N/A'

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

# Cache global para base unificada
_BASE_UNIFICADA_CACHE = None
_ULTIMO_CARREGAMENTO_BASE = 0
_CACHE_VALIDADE_BASE = 300  # 5 minutos

# Cache global para agentes
_BASE_AGENTES_CACHE = None
_ULTIMO_CARREGAMENTO = 0
_CACHE_VALIDADE = 300  # 5 minutos

# Removido bloco duplicado de definição de USUARIOS_SISTEMA e reinicialização de logs

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

# Configurações administrativas editáveis em tempo de execução
if 'ADMIN_CONFIG' not in globals():
    try:
        ADMIN_CONFIG = {
            'use_db': True,  # Tentar PostgreSQL antes do CSV
            'cache_rotas_ttl': _CACHE_ROTAS_TTL,
            'cache_base_ttl': _CACHE_VALIDADE_BASE,
            'verbose_logs': False,
        }
    except NameError:
        ADMIN_CONFIG = {
            'use_db': True,
            'cache_rotas_ttl': 900,
            'cache_base_ttl': 300,
            'verbose_logs': False,
        }

# Último diagnóstico de conexão com o banco
if '_ULTIMO_TESTE_DB' not in globals():
    _ULTIMO_TESTE_DB = None

def diagnosticar_conexao_db():
    """Tenta conectar no PostgreSQL diretamente e retorna diagnóstico sem fallback para CSV."""
    resultado = {
        'ok': False,
        'rows': 0,
        'error': '',
        'params': {},
    }
    try:
        import psycopg2
        db_url = (
            os.getenv("DATABASE_URL")
            or os.getenv("POSTGRES_URL")
            or os.getenv("DATABASE_URL_INTERNAL")
            or os.getenv("DATABASE_URI")
            or None
        )
        conn = None
        conn_params = {}
        if db_url:
            if "sslmode=" not in db_url:
                sep = "&" if "?" in db_url else "?"
                db_url = f"{db_url}{sep}sslmode=require"
            conn = psycopg2.connect(db_url)
            conn_params = {'via_url': True}
        else:
            db_name = os.getenv("DB_NAME", "base_unificada")
            db_user = os.getenv("DB_USER", "postgres")
            db_password = os.getenv("DB_PASSWORD", "")
            db_host = os.getenv("DB_HOST", "localhost")
            db_port = os.getenv("DB_PORT", "5432")
            db_sslmode = os.getenv("DB_SSLMODE") or ("require" if "render.com" in str(db_host) else "prefer")
            conn_params = {
                'dbname': db_name,
                'user': db_user,
                'host': db_host,
                'port': db_port,
                'sslmode': db_sslmode,
            }
            conn = psycopg2.connect(
                dbname=db_name,
                user=db_user,
                password=db_password,
                host=db_host,
                port=db_port,
                sslmode=db_sslmode,
            )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM public.base_unificada")
        count = cur.fetchone()[0] or 0
        resultado['ok'] = True
        resultado['rows'] = int(count)
        resultado['params'] = conn_params
        cur.close()
        conn.close()
    except Exception as e:
        resultado['error'] = str(e)
    finally:
        try:
            import datetime as _dt
            resultado['timestamp'] = _dt.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            pass
        globals()['_ULTIMO_TESTE_DB'] = resultado
    return resultado

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
        "SALVADOR": "SALVADOR",
        "SSA": "SALVADOR",
        "NAVEGANTES": "NAVEGANTES",
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

@lru_cache(maxsize=1000)
def normalizar_cidade_nome(cidade):
    """
    Normaliza o nome da cidade, removendo a parte após o hífen.
    Com cache para melhorar performance
    """
    if not cidade:
        return ""
    
    cidade = str(cidade)
    partes = cidade.split("-")
    cidade_sem_uf = partes[0].strip()
    
    return normalizar_cidade(cidade_sem_uf)

def geocode(municipio, uf):
    try:
        # Normalizar cidade e UF
        cidade_norm = normalizar_cidade(municipio)
        uf_norm = normalizar_uf(uf)
        
        # Primeiro, tentar obter do cache de coordenadas
        from utils.coords_cache import COORDS_CACHE
        chave_cache = f"{cidade_norm}-{uf_norm}"
        
        if chave_cache in COORDS_CACHE:
            coords = COORDS_CACHE[chave_cache]
            return coords
        
        # Se não encontrou no cache, tentar a API do OpenStreetMap
        
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
            return coords
        
        # 5. Fallback final: Brasília
        coords = [-15.7801, -47.9292]
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
            # Calcular pedágios usando estimativa simples
            pedagio_real = rota_info["distancia"] * 0.05  # R$ 0,05 por km
            pedagio_detalhes = {"fonte": "Estimativa baseada na distância", "valor_por_km": 0.05}
    
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
    Carrega a Base Unificada com cache: tenta DB e, se necessário, usa CSV automaticamente.
    """
    return carregar_base_unificada_db_only()
def calcular_frete_fracionado_multiplas_bases(origem, uf_origem, destino, uf_destino, peso, cubagem, valor_nf=None, bases_intermediarias=None):
    """
    Calcular frete fracionado usando múltiplas bases intermediárias
    Permite ao usuário escolher bases para compor a viagem (ex: SAO -> ITJ -> SSZ -> SJP)
    """
    try:
        tempo_inicio = time.time()
        
        # Carregar base unificada
        df_base = carregar_base_unificada()
        if df_base is None:
            return None
        
        # Normalizar cidades
        origem_norm = normalizar_cidade_nome(origem)
        destino_norm = normalizar_cidade_nome(destino)
        uf_origem_norm = normalizar_uf(uf_origem)
        uf_destino_norm = normalizar_uf(uf_destino)
        
        # Mapeamento de códigos de base para nomes
        mapeamento_bases = {
            # Bases principais (já existentes)
            "SAO": "São Paulo", "ITJ": "Itajaí", "SSZ": "Salvador", "SJP": "São José dos Pinhais",
            "SPO": "São Paulo", "RAO": "Ribeirão Preto", "CPQ": "Campinas", "SJK": "São José dos Campos",
            "RIO": "Rio de Janeiro", "BHZ": "Belo Horizonte", "VIX": "Vitória", "CWB": "Curitiba",
            "POA": "Porto Alegre", "BSB": "Brasília", "GYN": "Goiânia", "CGB": "Cuiabá",
            "CGR": "Campo Grande", "FOR": "Fortaleza", "REC": "Recife", "SSA": "Salvador",
            "NAT": "Natal", "JPA": "João Pessoa", "MCZ": "Maceió", "AJU": "Aracaju",
            "SLZ": "São Luís", "TER": "Teresina", "MAO": "Manaus", "MAB": "Marabá",
            "PMW": "Palmas", "FILIAL": "Filial Local",
            
            # Bases adicionais com maior frequência de uso
            "LDB": "Londrina", "CXJ": "Caxias do Sul", "EXP": "Exportação", "RSI": "Rio de Janeiro",
            "PRI": "Primavera", "RDZ": "Rondonópolis", "MGF": "Maringá", "SCI": "Santa Catarina",
            "JOI": "Joinville", "FLN": "Florianópolis", "GIG": "Rio de Janeiro", "GOD": "Goiânia",
            "GPB": "Guarapuava", "IGU": "Foz do Iguaçu", "IMP": "Imperatriz", "JDF": "Juiz de Fora",
            "JDO": "Juazeiro do Norte", "LAJ": "Lages", "LAR": "Laranjeiras", "LEC": "Leme",
            "MCP": "Macapá", "MOC": "Montes Claros", "NVT": "Navegantes", "PEL": "Pelotas",
            "PFB": "Passo Fundo", "PGO": "Ponta Grossa", "PGZ": "Ponta Grossa", "PLU": "Palhoça",
            "PNZ": "Parnaíba", "POO": "Poços de Caldas", "PPB": "Ponta Porã", "PPY": "Ponta Porã",
            "PTO": "Pato Branco", "PVH": "Porto Velho", "QVR": "Quatro Barras", "RBR": "Rio Branco",
            "RDZ": "Rondonópolis", "RIA": "Ribeirão Preto", "ROO": "Rondonópolis", "RSF": "Rio de Janeiro",
            "RSP": "Rio de Janeiro", "RSR": "Rio de Janeiro", "RVD": "Rio Verde", "SDU": "Rio de Janeiro",
            "SOD": "Sorocaba", "SPI": "São Paulo", "SPP": "São Paulo", "SPR": "São Paulo",
            "STM": "Santos", "SÃO": "São Paulo", "TER": "Teresina", "TUB": "Tubarão",
            "UBA": "Uberaba", "UDI": "Uberlândia", "VAG": "Varginha", "VDC": "Vitória da Conquista",
            "XAP": "Chapecó"
        }
        
        # Se não foi fornecida base intermediária, retornar erro
        if not bases_intermediarias or len(bases_intermediarias) != 1:
            return {
                'error': 'É necessário fornecer exatamente 1 base intermediária para compor a viagem (ex: SAO)',
                'sem_opcoes': True
            }
        
        # Construir rota completa: Origem -> Base Intermediária -> Destino
        # Converter códigos de base para nomes de cidades
        base_intermediaria = bases_intermediarias[0]  # Pegar a única base
        nome_base = mapeamento_bases.get(base_intermediaria.upper(), base_intermediaria)
        
        # Usar nomes normalizados para busca na base de dados
        rota_completa = [origem_norm, nome_base, destino_norm]
        
        print(f"[MULTIPLAS_BASES] 🛣️ Rota completa: {' -> '.join(rota_completa)}")
        
        # Calcular custos para cada trecho da rota
        trechos_custos = []
        custo_total = 0
        prazo_total = 0
        fornecedores_utilizados = []
        
        # Calcular cada trecho da rota
        for i in range(len(rota_completa) - 1):
            origem_trecho = rota_completa[i]
            destino_trecho = rota_completa[i + 1]
            indice = i + 1
            # Evitar usar Transferência nas pontas (coleta inicial e entrega final)
            is_primeiro_trecho = (i == 0)
            is_ultimo_trecho = (i == len(rota_completa) - 2)
            
            print(f"[MULTIPLAS_BASES] 🔍 Calculando trecho {indice}: {origem_trecho} -> {destino_trecho}")
            
            # Buscar serviços porta-porta (agentes diretos) - removendo transferências
            print(f"[MULTIPLAS_BASES] 🔍 Buscando serviços porta-porta para: {origem_trecho} -> {destino_trecho}")
            
            # Estratégia 1: Busca específica para agentes, diretos e transferências (prioridade)
            print(f"[MULTIPLAS_BASES] 🔍 Buscando serviços para: {origem_trecho} -> {destino_trecho}")
            servicos_agentes = df_base[
                (df_base['Tipo'].isin(['Agente', 'Direto', 'Transferência'])) &
                (df_base['Origem'].str.contains(origem_trecho[:4], case=False, na=False)) &
                (df_base['Destino'].str.contains(destino_trecho[:4], case=False, na=False))
            ]
            
            # Estratégia 2: Busca exata para agentes, diretos e transferências
            if servicos_agentes.empty:
                servicos_agentes = df_base[
                    (df_base['Tipo'].isin(['Agente', 'Direto', 'Transferência'])) &
                    (df_base['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_trecho)) &
                    (df_base['Destino'].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_trecho))
                ]
            
            # Estratégia 3: Busca por Base Origem/Destino para agentes, diretos e transferências
            if servicos_agentes.empty:
                servicos_agentes = df_base[
                    (df_base['Tipo'].isin(['Agente', 'Direto', 'Transferência'])) &
                    (df_base['Base Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_trecho)) &
                    (df_base['Base Destino'].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_trecho))
                ]
            
            # Estratégia 4: Busca flexível para agentes, diretos e transferências
            if servicos_agentes.empty:
                servicos_agentes = df_base[
                    (df_base['Tipo'].isin(['Agente', 'Direto', 'Transferência'])) &
                    (df_base['Origem'].str.contains(origem_trecho, case=False, na=False)) &
                    (df_base['Destino'].str.contains(destino_trecho, case=False, na=False))
                ]
            
            # Estratégia 5: Busca com normalização aplicada aos dados da base
            if servicos_agentes.empty:
                servicos_agentes = df_base[
                    (df_base['Tipo'].isin(['Agente', 'Direto', 'Transferência'])) &
                    (df_base['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_trecho)) &
                    (df_base['Destino'].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_trecho))
                ]
            
            # Usar todos os serviços encontrados (agentes, diretos e transferências)
            servicos_trecho = servicos_agentes
            
            if not servicos_agentes.empty:
                print(f"[MULTIPLAS_BASES] 📊 Encontrados {len(servicos_agentes)} serviços (agentes/diretos/transferências)")
            else:
                print(f"[MULTIPLAS_BASES] ⚠️ Nenhum serviço encontrado")
            
            print(f"[MULTIPLAS_BASES] 📊 Encontrados {len(servicos_trecho)} serviços para o trecho")
            print(f"[MULTIPLAS_BASES] 🔍 Processando serviços...")
            
            if servicos_trecho.empty:
                return {
                    'error': f'Não há serviços disponíveis para o trecho {origem_trecho} -> {destino_trecho}',
                    'sem_opcoes': True
                }
            
            # Encontrar o melhor serviço para este trecho
            melhor_servico = None
            menor_custo = float('inf')
            
            # Contador para evitar logs duplicados
            servicos_processados = 0
            
            for _, servico in servicos_trecho.iterrows():
                try:
                    # Pular serviços de Transferência nas pontas (coleta e entrega)
                    tipo_atual = str(servico.get('Tipo', '')).upper()
                    if (is_primeiro_trecho or is_ultimo_trecho) and (tipo_atual == 'TRANSFERÊNCIA' or 'TRANSFERENCIA' in tipo_atual):
                        # Ex.: evita selecionar Concept para entrega final em áreas sem cobertura direta
                        continue

                    # Calcular custo para este serviço baseado no tipo
                    peso_cubado = max(float(peso), float(cubagem) * 300) if cubagem else float(peso)
                    tipo_servico = servico.get('Tipo', 'FRACIONADO')
                    fornecedor = servico.get('Fornecedor', 'N/A')
                    
                    # Lógica específica para PTX
                    if str(fornecedor).strip().upper() == 'PTX':
                        # Usar valores da tabela da base de dados multiplicados pelo peso
                        # Preferir chaves string para evitar acesso posicional do pandas
                        valor_por_kg = 0.0
                        for key in ['20', 20]:
                            try:
                                v = servico.get(key, 0)
                                if v:
                                    valor_por_kg = float(v)
                                    break
                            except Exception:
                                continue
                        if valor_por_kg == 0:
                            # Se não tiver valor na coluna 20, tentar outras colunas
                            for coluna in ['10', 10, '30', 30, '50', 50, '70', 70, '100', 100]:
                                try:
                                    v = servico.get(coluna, 0)
                                    if v:
                                        valor_por_kg = float(v)
                                        break
                                except Exception:
                                    continue
                        
                        custo_base = float(peso_cubado) * valor_por_kg
                        print(f"[CUSTO-PTX] {peso_cubado}kg × R$ {valor_por_kg:.4f} = R$ {custo_base:.2f}")
                        custo_servico = {
                            'custo_total': custo_base,
                            'total': custo_base,
                            'valor': custo_base,
                            'prazo': servico.get('Prazo', 2),
                            'detalhes': {
                                'base': custo_base,
                                'peso_maximo': peso_cubado,
                                'valor_por_kg': valor_por_kg,
                                'formula': f'{peso_cubado}kg × R$ {valor_por_kg:.4f}'
                            }
                        }
                    elif tipo_servico in ['Agente', 'Direto', 'Transferência']:
                        # Usar lógica específica para agentes, diretos e transferências
                        custo_servico = calcular_custo_agente(servico, peso_cubado, valor_nf)
                    else:
                        # Usar lógica padrão para outros tipos
                        custo_servico = processar_linha_fracionado(servico, peso_cubado, valor_nf, tipo_servico)
                    
                    # Verificar se o custo é válido
                    if custo_servico:
                        custo_total_servico = custo_servico.get('custo_total', 0)
                        if custo_total_servico == 0:
                            # Tentar outras chaves possíveis
                            custo_total_servico = custo_servico.get('total', 0)
                            if custo_total_servico == 0:
                                custo_total_servico = custo_servico.get('valor', 0)
                        
                        if custo_total_servico > 0 and custo_total_servico < menor_custo:
                            menor_custo = custo_total_servico
                            melhor_servico = {
                                'servico': servico,
                                'custo': custo_servico,
                                'origem': origem_trecho,
                                'destino': destino_trecho,
                                'tipo': tipo_servico
                            }
                            print(f"[MULTIPLAS_BASES] ✅ Melhor serviço: {fornecedor} ({tipo_servico}) - R$ {menor_custo:.2f}")
                    
                    servicos_processados += 1
                    
                except Exception as e:
                    print(f"[MULTIPLAS_BASES] ⚠️ Erro ao processar serviço {fornecedor}: {e}")
                    continue
            
            print(f"[MULTIPLAS_BASES] 📊 Processados {servicos_processados} serviços para o trecho")
            
            # Se não encontrou nenhum serviço válido, retornar erro
            if not melhor_servico:
                print(f"[MULTIPLAS_BASES] ❌ Nenhum serviço válido encontrado")
                return {
                    'error': f'Não há serviços disponíveis para o trecho {origem_trecho} -> {destino_trecho}',
                    'sem_opcoes': True
                }
            
            # Adicionar custo do trecho ao total
            custo_trecho = melhor_servico['custo'].get('custo_total', 0)
            if custo_trecho == 0:
                # Tentar outras chaves possíveis
                custo_trecho = melhor_servico['custo'].get('total', 0)
                if custo_trecho == 0:
                    custo_trecho = melhor_servico['custo'].get('valor', 0)
            
            custo_total += custo_trecho
            prazo_total += melhor_servico['custo'].get('prazo', 0)
            fornecedores_utilizados.append(melhor_servico['servico'].get('Fornecedor', 'N/A'))
            
            trechos_custos.append({
                'trecho': f"{origem_trecho} -> {destino_trecho}",
                'custo': custo_trecho,
                'fornecedor': melhor_servico['servico'].get('Fornecedor', 'N/A'),
                'tipo_servico': melhor_servico.get('tipo', 'FRACIONADO'),
                'prazo': melhor_servico['custo'].get('prazo', 0),
                'detalhes': melhor_servico['custo']
            })
            
            print(f"[MULTIPLAS_BASES] 💰 Trecho {indice}: {origem_trecho} -> {destino_trecho} = R$ {custo_trecho:.2f} ({melhor_servico.get('tipo', 'FRACIONADO')})")
        
        # Calcular custos adicionais (GRIS, seguro, etc.)
        peso_cubado = max(float(peso), float(cubagem) * 300) if cubagem else float(peso)
        
        # GRIS (se valor_nf fornecido)
        gris_total = 0
        if valor_nf:
            gris_total = float(valor_nf) * 0.01  # 1% do valor da NF
        
        # Seguro (se aplicável)
        seguro_total = peso_cubado * 0.50  # R$ 0,50 por kg
        
        custo_total += gris_total + seguro_total
        
        # Preparar resultado
        resultado = {
            'tipo': 'Fracionado Multiplas Bases',
            'origem': f"{origem}/{uf_origem}",
            'destino': f"{destino}/{uf_destino}",
            'bases_intermediarias': bases_intermediarias,
            'rota_completa': rota_completa,
            'trechos': trechos_custos,
            'custo_total': custo_total,
            'prazo_total': prazo_total,
            'fornecedores_utilizados': fornecedores_utilizados,
            'peso_cubado': peso_cubado,
            'gris': gris_total,
            'seguro': seguro_total,
            'tempo_calculo': time.time() - tempo_inicio
        }
        
        print(f"[MULTIPLAS_BASES] ✅ Cálculo concluído: R$ {custo_total:.2f} em {prazo_total} dias")
        return resultado
        
    except Exception as e:
        print(f"[MULTIPLAS_BASES] ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return None
def calcular_frete_fracionado_base_unificada(origem, uf_origem, destino, uf_destino, peso, cubagem, valor_nf=None):
    """
    Calcular frete fracionado usando a Base Unificada - APENAS dados reais da base
    """
    try:
        tempo_inicio = time.time()
        todas_opcoes = []
        
        # Carregar base unificada
        df_base = carregar_base_unificada()
        if df_base is None:
            return {
                'sem_opcoes': True,
                'mensagem': 'Erro ao carregar base de dados',
                'detalhes': 'Base unificada não disponível'
            }
        
        # Normalizar cidades
        origem_norm = normalizar_cidade_nome(origem)
        destino_norm = normalizar_cidade_nome(destino)
        uf_origem_norm = normalizar_uf(uf_origem)
        uf_destino_norm = normalizar_uf(uf_destino)
        
        print(f"[FRACIONADO] 🔍 Buscando serviços para: {origem_norm}/{uf_origem_norm} → {destino_norm}/{uf_destino_norm}")
        
        # 1. BUSCAR SERVIÇOS DIRETOS - APENAS CORRESPONDÊNCIA EXATA (vetorizado)
        df_diretos = _DF_DIRETOS if _BASE_INDICES_PRONTOS else (
            df_base[df_base['tipo_norm'] == 'DIRETO'] if 'tipo_norm' in df_base.columns else df_base[df_base['Tipo'] == 'Direto']
        )
        col_on = 'origem_norm' if 'origem_norm' in df_diretos.columns else 'Origem'
        coldn = 'destino_norm' if 'destino_norm' in df_diretos.columns else 'Destino'
        val_on = origem_norm if col_on == 'origem_norm' else origem_norm
        val_dn = destino_norm if coldn == 'destino_norm' else destino_norm
        servicos_diretos = df_diretos[
            (df_diretos[col_on] == val_on) &
            (df_diretos[coldn] == val_dn)
        ]
        
        print(f"[FRACIONADO] 📊 Serviços diretos encontrados: {len(servicos_diretos)}")
        
        # 2. BUSCAR ML, GRITSCH E EXPRESSO S. MIGUEL - APENAS CORRESPONDÊNCIA EXATA (vetorizado)
        base_for = _DF_DIRETOS if _BASE_INDICES_PRONTOS else df_base
        col_for = 'fornecedor_upper' if 'fornecedor_upper' in base_for.columns else 'Fornecedor'
        df_ml_gritsch = base_for[
            base_for[col_for].str.contains(r'ML|GRITSCH|EXPRESSO S\. MIGUEL', case=False, na=False)
        ]
        col_on_m = 'origem_norm' if 'origem_norm' in df_ml_gritsch.columns else 'Origem'
        coldn_m = 'destino_norm' if 'destino_norm' in df_ml_gritsch.columns else 'Destino'
        ml_gritsch_services = df_ml_gritsch[
            (df_ml_gritsch[col_on_m] == origem_norm) &
            (df_ml_gritsch[coldn_m] == destino_norm)
        ]
        
        print(f"[FRACIONADO] 📊 ML/GRITSCH/EXPRESSO encontrados: {len(ml_gritsch_services)}")
        
        # Combinar serviços diretos
        servicos_diretos_completos = pd.concat([servicos_diretos, ml_gritsch_services]).drop_duplicates()
        
        # Processar serviços diretos válidos
        for _, servico in servicos_diretos_completos.iterrows():
            try:
                peso_real = float(peso)
                peso_cubado = calcular_peso_cubado_por_tipo(peso_real, cubagem, 'Direto', servico.get('Fornecedor'))
                opcao = processar_linha_fracionado(servico, peso_cubado, valor_nf, "DIRETO PORTA-A-PORTA")
                
                if opcao:
                    opcao_formatada = {
                        'fornecedor': opcao['fornecedor'],
                        'origem': origem,
                        'destino': destino,
                        'total': opcao['total'],
                        'prazo': opcao['prazo'],
                        'peso_cubado': peso_cubado,
                        'peso_usado': peso_cubado,
                        'modalidade': 'DIRETO',
                        'tipo': 'direto_porta_porta',
                        'tipo_rota': 'direto_porta_porta',
                        'resumo': f"{opcao['fornecedor']} - Serviço Direto Porta-a-Porta",
                        'detalhes': opcao,
                        'custo_base': opcao['custo_base'],
                        'gris': opcao['gris'],
                        'pedagio': opcao['pedagio'],
                        'seguro': opcao.get('seguro', 0),
                        'servico_direto': True,
                        'peso_maximo_transportado': servico.get('PESO MÁXIMO TRANSPORTADO', 'N/A'),
                        'prazo_real': servico.get('Prazo', 'N/A')
                    }
                    todas_opcoes.append(opcao_formatada)
            except Exception as e:
                print(f"[FRACIONADO] ❌ Erro ao processar serviço direto: {e}")
                continue
        
        # 3. BUSCAR ROTAS COM AGENTES - APENAS SE HÁ AGENTES EXATOS
        rotas_agentes = calcular_frete_com_agentes(
            origem, uf_origem,
            destino, uf_destino,
            peso, valor_nf, cubagem
        )
        
        # Adicionar rotas com agentes se existirem
        if rotas_agentes and rotas_agentes.get('rotas'):
            for rota in rotas_agentes['rotas']:
                todas_opcoes.append(rota)
        
        # 🆕 ORDENAR OPÇÕES POR PREÇO (menor para maior)
        todas_opcoes.sort(key=lambda x: x.get('total', float('inf')))
        
        # 4. VERIFICAR SE HÁ OPÇÕES VÁLIDAS
        if len(todas_opcoes) == 0:
            print(f"[FRACIONADO] ❌ Nenhuma opção válida encontrada na base de dados")
            return {
                'sem_opcoes': True,
                'mensagem': 'Não há nenhuma opção para a rota solicitada',
                'detalhes': f'Não há serviços disponíveis para {origem_norm} → {destino_norm}'
            }
        
        # 5. RETORNAR RESULTADO
        tempo_total = time.time() - tempo_inicio
        print(f"[FRACIONADO] ✅ Processamento concluído em {tempo_total:.2f}s - {len(todas_opcoes)} opções encontradas")
        
        return {
            'opcoes': todas_opcoes,
            'total_opcoes': len(todas_opcoes),
            'tempo_processamento': tempo_total,
            'origem': origem_norm,
            'destino': destino_norm,
            'uf_origem': uf_origem_norm,
            'uf_destino': uf_destino_norm
        }
        
    except Exception as e:
        print(f"[FRACIONADO] ❌ Erro geral: {e}")
        return {
            'sem_opcoes': True,
            'mensagem': 'Erro interno no processamento',
            'detalhes': str(e)
        }

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

        # Separar tipos - ML, GRITSCH e EXPRESSO S. MIGUEL tratados como agentes diretos porta-porta
        # Usar recortes pré-processados
        base_agentes = _DF_AGENTES if _BASE_INDICES_PRONTOS else df_base[df_base['Tipo'] == 'Agente']
        df_agentes = base_agentes[
            ~base_agentes['Fornecedor'].str.contains(r'ML|GRITSCH|EXPRESSO S\. MIGUEL', case=False, na=False)
        ].copy()

        base_transf = _DF_TRANSFERENCIAS if _BASE_INDICES_PRONTOS else df_base[df_base['Tipo'] == 'Transferência']
        # Não excluir EXPRESSO S. MIGUEL das transferências; necessário para rotas por bases
        df_transferencias = base_transf.copy()

        # Logs de diagnóstico (contagens)
        try:
            print(f"[AGENTES] 🔎 Totais: agentes={len(df_agentes)}, transferencias={len(df_transferencias)}")
        except Exception:
            pass

        # Mapeamentos cidade <-> código de base a partir das transferências (para conectar agentes)
        try:
            def _norm(s):
                return str(s).upper().strip()
            if {'Base Origem', 'Origem'}.issubset(df_transferencias.columns):
                cidade_to_cod_origem = dict(
                    df_transferencias[['Origem', 'Base Origem']]
                    .dropna()
                    .apply(lambda r: (_norm(r['Origem']), _norm(r['Base Origem'])), axis=1)
                    .drop_duplicates()
                    .tolist()
                )
            else:
                cidade_to_cod_origem = {}
            if {'Base Destino', 'Destino'}.issubset(df_transferencias.columns):
                cidade_to_cod_destino = dict(
                    df_transferencias[['Destino', 'Base Destino']]
                    .dropna()
                    .apply(lambda r: (_norm(r['Destino']), _norm(r['Base Destino'])), axis=1)
                    .drop_duplicates()
                    .tolist()
                )
            else:
                cidade_to_cod_destino = {}
        except Exception:
            cidade_to_cod_origem, cidade_to_cod_destino = {}, {}

        df_diretos = _DF_DIRETOS.copy() if _BASE_INDICES_PRONTOS else df_base[df_base['Tipo'] == 'Direto'].copy()
        

        
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
        MAX_ROTAS = 30  # Reduzido para melhorar performance
        MAX_ITERACOES = 1000  # Limite para evitar loops infinitos
        contador_iteracoes = 0
        
        def gerar_chave_rota(agente_col_forn, transf_forn, agente_ent_forn):
            """Gera chave única para controle de duplicatas"""
            return f"{agente_col_forn}+{transf_forn}+{agente_ent_forn}"
        
        # Verificar se existem agentes na origem/destino exatos (vetorizado + UF)
        uf_origem_upper = uf_origem
        uf_destino_upper = uf_destino
        col_uf = 'uf_upper' if 'uf_upper' in df_agentes.columns else 'UF'
        col_on_norm = 'origem_norm' if 'origem_norm' in df_agentes.columns else 'Origem'
        df_agentes_origem_uf = df_agentes[df_agentes[col_uf] == uf_origem_upper]
        df_agentes_destino_uf = df_agentes[df_agentes[col_uf] == uf_destino_upper]

        origem_norm_str = normalizar_cidade_nome(str(origem))
        destino_norm_str = normalizar_cidade_nome(str(destino))

        agentes_origem = df_agentes_origem_uf[
            df_agentes_origem_uf[col_on_norm] == origem_norm_str
        ]
        agentes_destino = df_agentes_destino_uf[
            df_agentes_destino_uf[col_on_norm] == destino_norm_str
        ]

        # Fallback: se não houver agentes de entrega exatos no mesmo UF,
        # relaxar o filtro de UF e procurar por cidade exata em toda a base de agentes
        if agentes_destino.empty:
            try:
                agentes_destino = df_agentes[
                    df_agentes[col_on_norm] == destino_norm_str
                ]
                if not agentes_destino.empty:
                    print(f"[AGENTES] 🔎 Fallback: encontrados {len(agentes_destino)} agentes de entrega por cidade (ignorando UF)")
            except Exception:
                pass
        
        # 🔧 CORREÇÃO: Se origem e destino são do mesmo estado, filtrar agentes apenas do estado correto
        if uf_origem == uf_destino:
            agentes_destino = agentes_destino[agentes_destino['UF'] == uf_destino]
        
        # 🔧 CORREÇÃO: Verificar se faltam agentes exatos - SER CONSERVADOR
        if agentes_origem.empty:
            agentes_faltando['origem'] = True
            avisos.append(f"Não há agente de coleta em {origem_norm}")
        
        if agentes_destino.empty:
            agentes_faltando['destino'] = True
            avisos.append(f"Não há agente de entrega em {destino_norm}")
        
        # REMOVIDO: Serviços diretos - já são processados em calcular_frete_fracionado_base_unificada
        # para evitar duplicação
        servicos_diretos = pd.DataFrame()  # DataFrame vazio
        
        # CÓDIGO ORIGINAL COMENTADO:
        # servicos_diretos = df_diretos[
        #     (df_diretos['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_norm)) &
        #     (df_diretos['Destino'].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_norm))
        # ]
        
        # Agentes de coleta - BUSCA GLOBAL E INTELIGENTE
        agentes_coleta = df_agentes[
            df_agentes['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_norm)
        ]
        
        # Se não encontrar agentes na cidade exata, manter vazio para rotas parciais
        if agentes_coleta.empty:
            # Manter vazio para permitir rotas parciais
            pass
        
        # Agentes de entrega - BUSCA GLOBAL E INTELIGENTE
        agentes_entrega = df_agentes[
            df_agentes['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_norm)
        ]
        
        # Se não encontrar agentes na cidade exata, manter vazio para rotas parciais
        if agentes_entrega.empty:
            # Manter vazio para permitir rotas parciais
            pass

        # 🆕 NOVA LÓGICA: Transferências com agentes nas pontas
        # Buscar agentes de coleta na origem
        agentes_coleta = df_agentes[
            df_agentes['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_norm)
        ]
        
        # Buscar agentes de entrega no destino
        agentes_entrega = df_agentes[
            df_agentes['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_norm)
        ]
        
        print(f"[AGENTES] 📊 Agentes de coleta encontrados: {len(agentes_coleta)}")
        print(f"[AGENTES] 📊 Agentes de entrega encontrados: {len(agentes_entrega)}")
        try:
            print(f"[AGENTES] 📊 Transferências totais: {len(df_transferencias)} | diretas O→D: {len(transferencias_origem_destino)}")
        except Exception:
            pass
        
        # Buscar transferências entre bases (usar conjunto completo; filtros ocorrerão por conexão de base)
        transferencias_bases = df_transferencias.copy()
        
        # Buscar transferências diretas também
        transferencias_origem_destino = df_transferencias[
            (df_transferencias['Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) == origem_norm)) &
            (df_transferencias['Destino'].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_norm))
        ]
        
        print(f"[AGENTES] 📊 Transferências diretas encontradas: {len(transferencias_origem_destino)}")
        
        rotas_encontradas = []
        
        # 🆕 CENÁRIO 1: Agente de coleta + Transferência + Agente de entrega (rota completa com conexão flexível)
        if not agentes_coleta.empty and not agentes_entrega.empty and not transferencias_bases.empty:
            print(f"[AGENTES] 🔄 Conectando agentes com transferências (rota completa)...")
            # Usar apenas colunas de BASE para conectar transferências entre bases
            orig_cols = [c for c in ['base_origem_norm'] if c in transferencias_bases.columns]
            if not orig_cols and 'Base Origem' in transferencias_bases.columns:
                orig_cols = ['Base Origem']
            dest_cols = [c for c in ['base_destino_norm'] if c in transferencias_bases.columns]
            if not dest_cols and 'Base Destino' in transferencias_bases.columns:
                dest_cols = ['Base Destino']
            for _, agente_col in agentes_coleta.iterrows():
                start_candidates = set()
                for key in ['base_destino_norm', 'base_origem_norm']:
                    if key in agente_col and agente_col.get(key):
                        start_candidates.add(agente_col.get(key))
                start_candidates.update([
                    normalizar_cidade_nome(str(agente_col.get('Base Origem', ''))),
                    normalizar_cidade_nome(str(agente_col.get('Base Destino', ''))),
                    (agente_col.get('origem_norm') if 'origem_norm' in agente_col else normalizar_cidade_nome(str(agente_col.get('Origem', ''))))
                ])
                start_candidates = {s for s in start_candidates if s}
                for _, agente_ent in agentes_entrega.iterrows():
                    end_candidates = set()
                    for key in ['base_origem_norm', 'base_destino_norm']:
                        if key in agente_ent and agente_ent.get(key):
                            end_candidates.add(agente_ent.get(key))
                    end_candidates.update([
                        normalizar_cidade_nome(str(agente_ent.get('Base Origem', ''))),
                        normalizar_cidade_nome(str(agente_ent.get('Base Destino', ''))),
                        (agente_ent.get('origem_norm') if 'origem_norm' in agente_ent else normalizar_cidade_nome(str(agente_ent.get('Origem', ''))))
                    ])
                    end_candidates = {e for e in end_candidates if e}
                    if not start_candidates or not end_candidates:
                        continue
                    mask_o = False
                    for col in orig_cols:
                        mask_o = mask_o | transferencias_bases[col].isin(start_candidates)
                    mask_d = False
                    for col in dest_cols:
                        mask_d = mask_d | transferencias_bases[col].isin(end_candidates)
                    transf_candidatas = transferencias_bases[mask_o & mask_d]
                    print(f"[AGENTES] 🔎 Candidatas completas: {len(transf_candidatas)}")
                    for _, transferencia in transf_candidatas.iterrows():
                        chave_rota = gerar_chave_rota(
                            agente_col.get('Fornecedor', 'N/A'),
                            transferencia.get('Fornecedor', 'N/A'),
                            agente_ent.get('Fornecedor', 'N/A')
                        )
                        if chave_rota in rotas_processadas:
                            continue
                        rotas_processadas.add(chave_rota)
                        peso_cubado_col = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_col.get('Tipo', 'Agente'), agente_col.get('Fornecedor'))
                        peso_cubado_transf = calcular_peso_cubado_por_tipo(peso_real, cubagem, transferencia.get('Tipo', 'Transferência'), transferencia.get('Fornecedor'))
                        peso_cubado_ent = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_ent.get('Tipo', 'Agente'), agente_ent.get('Fornecedor'))
                        custo_coleta = calcular_custo_agente(agente_col, peso_cubado_col, valor_nf)
                        custo_transferencia = calcular_custo_agente(transferencia, peso_cubado_transf, valor_nf)
                        custo_entrega = calcular_custo_agente(agente_ent, peso_cubado_ent, valor_nf)
                        if custo_coleta and custo_transferencia and custo_entrega:
                            total = custo_coleta['total'] + custo_transferencia['total'] + custo_entrega['total']
                            prazo_total = max(custo_coleta.get('prazo', 1), custo_transferencia.get('prazo', 1), custo_entrega.get('prazo', 1))
                            rota = {
                                'tipo_rota': 'agente_transferencia_agente_completa',
                                'resumo': f"{formatar_nome_agente(agente_col.get('Fornecedor'))} (Coleta) + {formatar_nome_agente(transferencia.get('Fornecedor'))} (Transferência) + {formatar_nome_agente(agente_ent.get('Fornecedor'))} (Entrega)",
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
                                'observacoes': f"Rota completa: {origem} → {transferencia.get('Origem')} → {transferencia.get('Destino')} → {destino}",
                                'status_rota': 'COMPLETA',
                                'agente_coleta': custo_coleta,
                                'transferencia': custo_transferencia,
                                'agente_entrega': custo_entrega,
                                'chave_unica': chave_rota
                            }
                            rotas_encontradas.append(rota)
                            if len(rotas_encontradas) >= MAX_ROTAS:
                                break
                    if len(rotas_encontradas) >= MAX_ROTAS:
                        break
                if len(rotas_encontradas) >= MAX_ROTAS:
                    break
        
        # 🆕 CENÁRIO 2: Coleta + Transferência + Entrega (rota completa conectando bases)
        elif not agentes_coleta.empty and not agentes_entrega.empty and not transferencias_bases.empty:
            print(f"[AGENTES] 🔄 Conectando agentes com transferências (rota completa)...")
            # Colunas de BASE disponíveis nas transferências (evitar casar por cidade)
            orig_cols = [c for c in ['base_origem_norm'] if c in transferencias_bases.columns]
            if not orig_cols and 'Base Origem' in transferencias_bases.columns:
                orig_cols = ['Base Origem']
            dest_cols = [c for c in ['base_destino_norm'] if c in transferencias_bases.columns]
            if not dest_cols and 'Base Destino' in transferencias_bases.columns:
                dest_cols = ['Base Destino']

            for _, agente_col in agentes_coleta.iterrows():
                # Conjunto de bases possíveis de saída após coleta
                base_dest_coleta = agente_col.get('base_destino_norm') if 'base_destino_norm' in agente_col else None
                base_origem_coleta = agente_col.get('base_origem_norm') if 'base_origem_norm' in agente_col else None
                fallback_coleta_bo = normalizar_cidade_nome(str(agente_col.get('Base Origem', '')))
                fallback_coleta_bd = normalizar_cidade_nome(str(agente_col.get('Base Destino', '')))
                # Também permitir conectar pela cidade do agente de coleta
                agente_coleta_cidade = agente_col.get('origem_norm') if 'origem_norm' in agente_col else normalizar_cidade_nome(str(agente_col.get('Origem', '')))
                # Mapear cidade do agente para possíveis códigos de base pelas transferências
                possiveis_cod_start = set()
                if agente_coleta_cidade:
                    cod1 = cidade_to_cod_origem.get(agente_coleta_cidade)
                    cod2 = cidade_to_cod_destino.get(agente_coleta_cidade)
                    if cod1: possiveis_cod_start.add(cod1)
                    if cod2: possiveis_cod_start.add(cod2)
                start_bases = {b for b in [base_dest_coleta, base_origem_coleta, fallback_coleta_bd, fallback_coleta_bo, agente_coleta_cidade] if b}
                start_bases |= possiveis_cod_start
                if not start_bases:
                    continue
                for _, agente_ent in agentes_entrega.iterrows():
                    # Conjunto de bases possíveis de entrada antes da entrega
                    base_origem_entrega = agente_ent.get('base_origem_norm') if 'base_origem_norm' in agente_ent else None
                    base_destino_entrega = agente_ent.get('base_destino_norm') if 'base_destino_norm' in agente_ent else None
                    fallback_ent_bo = normalizar_cidade_nome(str(agente_ent.get('Base Origem', '')))
                    fallback_ent_bd = normalizar_cidade_nome(str(agente_ent.get('Base Destino', '')))
                    # Também permitir conectar pela cidade do agente de entrega
                    agente_entrega_cidade = agente_ent.get('origem_norm') if 'origem_norm' in agente_ent else normalizar_cidade_nome(str(agente_ent.get('Origem', '')))
                    possiveis_cod_end = set()
                    if agente_entrega_cidade:
                        cod1 = cidade_to_cod_origem.get(agente_entrega_cidade)
                        cod2 = cidade_to_cod_destino.get(agente_entrega_cidade)
                        if cod1: possiveis_cod_end.add(cod1)
                        if cod2: possiveis_cod_end.add(cod2)
                    end_bases = {b for b in [base_origem_entrega, base_destino_entrega, fallback_ent_bo, fallback_ent_bd, agente_entrega_cidade] if b}
                    end_bases |= possiveis_cod_end
                    if not end_bases:
                        continue

                    # Máscaras de correspondência nas transferências considerando apenas colunas de BASE
                    mask_orig = False
                    for col in orig_cols:
                        mask_orig = mask_orig | transferencias_bases[col].isin(start_bases)
                    mask_dest = False
                    for col in dest_cols:
                        mask_dest = mask_dest | transferencias_bases[col].isin(end_bases)
                    transf_candidatas = transferencias_bases[mask_orig & mask_dest]
                    print(f"[AGENTES] 🔎 Candidatas entre {len(transferencias_bases)} transferências: {len(transf_candidatas)} (start={list(start_bases)[:2]}..., end={list(end_bases)[:2]}...)")
                    if transf_candidatas.empty:
                        continue
                    for _, transferencia in transf_candidatas.iterrows():
                        chave_rota = gerar_chave_rota(
                            agente_col.get('Fornecedor', 'N/A'),
                            transferencia.get('Fornecedor', 'N/A'),
                            agente_ent.get('Fornecedor', 'N/A')
                        )
                        if chave_rota in rotas_processadas:
                            continue
                        rotas_processadas.add(chave_rota)
                        # custos
                        peso_cubado_col = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_col.get('Tipo', 'Agente'), agente_col.get('Fornecedor'))
                        peso_cubado_transf = calcular_peso_cubado_por_tipo(peso_real, cubagem, transferencia.get('Tipo', 'Transferência'), transferencia.get('Fornecedor'))
                        peso_cubado_ent = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_ent.get('Tipo', 'Agente'), agente_ent.get('Fornecedor'))
                        custo_coleta = calcular_custo_agente(agente_col, peso_cubado_col, valor_nf)
                        custo_transferencia = calcular_custo_agente(transferencia, peso_cubado_transf, valor_nf)
                        custo_entrega = calcular_custo_agente(agente_ent, peso_cubado_ent, valor_nf)
                        if custo_coleta and custo_transferencia and custo_entrega:
                            total = custo_coleta['total'] + custo_transferencia['total'] + custo_entrega['total']
                            prazo_total = max(
                                custo_coleta.get('prazo', 1),
                                custo_transferencia.get('prazo', 1),
                                custo_entrega.get('prazo', 1)
                            )
                            rota = {
                                'tipo_rota': 'agente_transferencia_agente_completa',
                                'resumo': f"{formatar_nome_agente(agente_col.get('Fornecedor'))} (Coleta) + {formatar_nome_agente(transferencia.get('Fornecedor'))} (Transferência) + {formatar_nome_agente(agente_ent.get('Fornecedor'))} (Entrega)",
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
                                'observacoes': f"Rota completa: {origem} → {transferencia.get('Origem')} → {transferencia.get('Destino')} → {destino}",
                                'status_rota': 'COMPLETA',
                                'agente_coleta': custo_coleta,
                                'transferencia': custo_transferencia,
                                'agente_entrega': custo_entrega,
                                'chave_unica': chave_rota
                            }
                            rotas_encontradas.append(rota)
                            if len(rotas_encontradas) >= MAX_ROTAS:
                                break
                    if len(rotas_encontradas) >= MAX_ROTAS:
                        break
                if len(rotas_encontradas) >= MAX_ROTAS:
                    break
        
        # 🆕 CENÁRIO 3: Apenas transferência + agente de entrega (rota parcial)
        elif not agentes_entrega.empty and not transferencias_bases.empty:
            print(f"[AGENTES] 🔄 Criando rotas parciais (apenas transferência + entrega)...")
            
            # Preparar conjuntos de bases de origem possíveis vinculadas à cidade de origem
            possiveis_start_bases = set()
            try:
                origem_key = normalizar_cidade_nome(origem_norm) if origem_norm else None
                if origem_key:
                    cod_origem = cidade_to_cod_origem.get(origem_key.upper()) if 'cidade_to_cod_origem' in locals() else None
                    if cod_origem:
                        possiveis_start_bases.add(cod_origem)
            except Exception:
                pass
            
            for _, agente_ent in agentes_entrega.iterrows():
                # Determinar bases de entrada válidas para o agente de entrega (base de origem do agente de entrega)
                end_bases = set()
                try:
                    if 'base_origem_norm' in agente_ent and agente_ent.get('base_origem_norm'):
                        end_bases.add(agente_ent.get('base_origem_norm'))
                    if 'base_destino_norm' in agente_ent and agente_ent.get('base_destino_norm'):
                        end_bases.add(agente_ent.get('base_destino_norm'))
                    # Fallbacks por nomes crus das colunas
                    end_bases.update([
                        normalizar_cidade_nome(str(agente_ent.get('Base Origem', ''))),
                        normalizar_cidade_nome(str(agente_ent.get('Base Destino', '')))
                    ])
                    # Considerar cidade do agente de entrega para mapear possíveis códigos
                    agente_entrega_cidade = agente_ent.get('origem_norm') if 'origem_norm' in agente_ent else normalizar_cidade_nome(str(agente_ent.get('Origem', '')))
                    if agente_entrega_cidade and 'cidade_to_cod_destino' in locals():
                        cod1 = cidade_to_cod_destino.get(agente_entrega_cidade.upper())
                        if cod1:
                            end_bases.add(cod1)
                    end_bases = {e for e in end_bases if e}
                except Exception:
                    end_bases = set()
                
                # Filtrar transferências que cheguem a uma das end_bases
                if end_bases:
                    mask_dest = False
                    if 'base_destino_norm' in transferencias_bases.columns:
                        mask_dest = transferencias_bases['base_destino_norm'].isin(end_bases)
                    elif 'Base Destino' in transferencias_bases.columns:
                        mask_dest = transferencias_bases['Base Destino'].apply(lambda x: normalizar_cidade_nome(str(x)) in end_bases)
                    else:
                        # Sem colunas de base destino, pular
                        continue
                    transf_filtradas = transferencias_bases[mask_dest]
                else:
                    transf_filtradas = transferencias_bases
                
                # Opcional: filtrar por base de origem próxima à cidade de origem
                if possiveis_start_bases:
                    if 'base_origem_norm' in transf_filtradas.columns:
                        transf_filtradas = transf_filtradas[transf_filtradas['base_origem_norm'].isin(possiveis_start_bases)]
                    elif 'Base Origem' in transf_filtradas.columns:
                        transf_filtradas = transf_filtradas[transf_filtradas['Base Origem'].apply(lambda x: normalizar_cidade_nome(str(x)) in possiveis_start_bases)]
                
                for _, transferencia in transf_filtradas.iterrows():
                    # Validar que a transferência aproxima a UF de destino (quando possível)
                    try:
                        transf_dest = transferencia.get('destino_norm') if 'destino_norm' in transferencia else normalizar_cidade_nome(str(transferencia.get('Destino', '')))
                        if uf_destino_upper and isinstance(uf_destino_upper, str):
                            # Se transferência leva para cidade do mesmo UF do destino final, priorizar
                            pass
                    except Exception:
                        pass
                    
                    chave_rota = gerar_chave_rota(
                        "SEM_COLETA",
                        transferencia.get('Fornecedor', 'N/A'),
                        agente_ent.get('Fornecedor', 'N/A')
                    )
                    
                    if chave_rota in rotas_processadas:
                        continue
                    rotas_processadas.add(chave_rota)
                    
                    peso_cubado_transf = calcular_peso_cubado_por_tipo(peso_real, cubagem, transferencia.get('Tipo', 'Transferência'), transferencia.get('Fornecedor'))
                    peso_cubado_ent = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_ent.get('Tipo', 'Agente'), agente_ent.get('Fornecedor'))
                    
                    custo_transferencia = calcular_custo_agente(transferencia, peso_cubado_transf, valor_nf)
                    custo_entrega = calcular_custo_agente(agente_ent, peso_cubado_ent, valor_nf)
                    
                    if custo_transferencia and custo_entrega:
                        total = custo_transferencia['total'] + custo_entrega['total']
                        prazo_total = max(custo_transferencia.get('prazo', 1), custo_entrega.get('prazo', 1))
                        
                        rota = {
                            'tipo_rota': 'transferencia_agente_parcial',
                            'resumo': f"{formatar_nome_agente(transferencia.get('Fornecedor'))} (Transferência) + {formatar_nome_agente(agente_ent.get('Fornecedor'))} (Entrega) - SEM AGENTE DE COLETA",
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
                            'observacoes': f"Rota parcial: {transferencia.get('Origem')} → {transferencia.get('Destino')} → {destino} (sem agente de coleta)",
                            'status_rota': 'PARCIAL_SEM_COLETA',
                            'agente_coleta': None,
                            'transferencia': custo_transferencia,
                            'agente_entrega': custo_entrega,
                            'chave_unica': chave_rota
                        }
                        rotas_encontradas.append(rota)
                        
                        if len(rotas_encontradas) >= MAX_ROTAS:
                            break
                
                if len(rotas_encontradas) >= MAX_ROTAS:
                    break
        
        # 🆕 CENÁRIO 4: Apenas transferência direta (sem agentes)
        elif not transferencias_origem_destino.empty:
            print(f"[AGENTES] 🔄 Criando rotas apenas com transferência direta...")
            
            for _, transferencia in transferencias_origem_destino.iterrows():
                try:
                    custo_transferencia = processar_linha_fracionado(transferencia, peso_cubado, valor_nf, "TRANSFERÊNCIA")
                    
                    if custo_transferencia:
                        rota = {
                            'fornecedor': transferencia['Fornecedor'],
                            'origem': origem,
                            'destino': destino,
                            'total': custo_transferencia['total'],
                            'prazo': custo_transferencia['prazo'],
                            'peso_cubado': peso_cubado,
                            'peso_usado': peso_cubado,
                            'modalidade': 'TRANSFERÊNCIA',
                            'tipo': 'transferencia_direta',
                            'tipo_rota': 'transferencia_direta',
                            'resumo': f"{transferencia['Fornecedor']} - Transferência Direta",
                            'detalhes': custo_transferencia,
                            'custo_base': custo_transferencia['custo_base'],
                            'gris': custo_transferencia['gris'],
                            'pedagio': custo_transferencia['pedagio'],
                            'seguro': custo_transferencia.get('seguro', 0),
                            'servico_direto': False
                        }
                        rotas_encontradas.append(rota)
                except Exception as e:
                    print(f"[AGENTES] ❌ Erro ao processar transferência: {e}")
                    continue

        # 🆕 CENÁRIO 5: Rota parcial por bases do estado (sem coleta e sem agente de entrega)
        # Cliente retira em uma base do estado de destino
        elif agentes_entrega.empty and not transferencias_bases.empty:
            try:
                # Selecionar transferências que aproximem do destino: mesma UF do destino
                transf_destino_uf = df_transferencias.copy()
                if 'uf_upper' in df_transferencias.columns:
                    transf_destino_uf = transf_destino_uf[transf_destino_uf['uf_upper'] == uf_destino_upper]
                # E/ou cidade de destino igual (destino_norm)
                dest_cols = [c for c in ['destino_norm', 'Destino'] if c in df_transferencias.columns]
                if dest_cols:
                    mask_dest = False
                    for c in dest_cols:
                        if c == 'destino_norm':
                            mask_dest = mask_dest | (transf_destino_uf[c] == destino_norm)
                        else:
                            mask_dest = mask_dest | (transf_destino_uf[c].apply(lambda x: normalizar_cidade_nome(str(x)) == destino_norm))
                    transf_destino_uf = transf_destino_uf[mask_dest | (transf_destino_uf['uf_upper'] == uf_destino_upper) if 'uf_upper' in transf_destino_uf.columns else mask_dest]
                print(f"[AGENTES] 🔄 Criando rotas parciais por bases do estado: {len(transf_destino_uf)} transferências no UF de destino")
                LIMITE_ROTAS_PARCIAIS = 20
                count_adicionadas = 0
                for _, transferencia in transf_destino_uf.iterrows():
                    try:
                        peso_cubado_transf = calcular_peso_cubado_por_tipo(
                            peso_real, cubagem,
                            transferencia.get('Tipo', 'Transferência'),
                            transferencia.get('Fornecedor')
                        )
                        custo_transferencia = calcular_custo_agente(transferencia, peso_cubado_transf, valor_nf)
                        if not custo_transferencia:
                            continue
                        rota = {
                            'tipo_rota': 'transferencia_sem_entrega',
                            'resumo': f"{formatar_nome_agente(transferencia.get('Fornecedor'))} (Transferência) + Retirada pelo cliente em {transferencia.get('Destino')}",
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
                            'observacoes': f"Rota parcial por bases: cliente retira em {transferencia.get('Destino')} ({uf_destino})",
                            'status_rota': 'PARCIAL_SEM_ENTREGA',
                            'agente_coleta': None,
                            'transferencia': custo_transferencia,
                            'agente_entrega': None,
                            'chave_unica': gerar_chave_rota('SEM_COLETA', transferencia.get('Fornecedor', 'N/A'), 'SEM_ENTREGA')
                        }
                        rotas_encontradas.append(rota)
                        count_adicionadas += 1
                        if count_adicionadas >= LIMITE_ROTAS_PARCIAIS:
                            break
                    except Exception as e:
                        print(f"[AGENTES] ❌ Erro ao processar rota parcial por bases: {e}")
                        continue
            except Exception as e:
                print(f"[AGENTES] ❌ Erro no cenário de bases do estado: {e}")

        # Retornar resultados encontrados
        rotas_encontradas.sort(key=lambda x: x['total'])
        return {
            'rotas': rotas_encontradas,
            'total_opcoes': len(rotas_encontradas),
            'origem': origem_norm,
            'destino': destino_norm,
            'agentes_faltando': agentes_faltando,
            'avisos': avisos
        }

        # Se há agentes de coleta mas não há transferências diretas, tentar via bases
        if not agentes_coleta.empty and transferencias_origem_destino.empty:
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
                                'resumo': f"{formatar_nome_agente(fornecedor_col)} (Coleta) + {formatar_nome_agente(fornecedor_transf)} (Transferência) + {formatar_nome_agente(fornecedor_ent)} (Entrega via {base_destino})",
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
        if agentes_coleta.empty and transferencias_para_bases:
            print(f"[ROTAS] 🔄 Criando rotas parciais via bases (sem agente de coleta)...")
            for item in transferencias_para_bases:
                transf = item['transferencia']
                agente_ent = item['agente_entrega']
                base_destino = item['base_destino']
                
                fornecedor_transf = transf.get('Fornecedor', 'N/A')
                fornecedor_ent = agente_ent.get('Fornecedor', 'N/A')
                
                # Controle de duplicatas para rota via base
                chave_rota = gerar_chave_rota("SEM_COLETA", fornecedor_transf, fornecedor_ent)
                if chave_rota in rotas_processadas:
                    continue
                rotas_processadas.add(chave_rota)
                
                peso_cubado_transf = calcular_peso_cubado_por_tipo(peso_real, cubagem, transf.get('Tipo', 'Transferência'), transf.get('Fornecedor'))
                peso_cubado_ent = calcular_peso_cubado_por_tipo(peso_real, cubagem, agente_ent.get('Tipo', 'Agente'), agente_ent.get('Fornecedor'))
                custo_transferencia = calcular_custo_agente(transf, peso_cubado_transf, valor_nf)
                custo_entrega = calcular_custo_agente(agente_ent, peso_cubado_ent, valor_nf)
                
                if custo_transferencia and custo_entrega:
                    total = custo_transferencia['total'] + custo_entrega['total']
                    prazo_total = max(custo_transferencia.get('prazo', 1), custo_entrega.get('prazo', 1))
                    
                    rota_bases = f"{transf.get('Origem')} → {transf.get('Destino')} → {destino}"
                    
                    rota = {
                        'tipo_rota': 'transferencia_entrega_via_base',
                        'resumo': f"{formatar_nome_agente(fornecedor_transf)} (Transferência) + {formatar_nome_agente(fornecedor_ent)} (Entrega via {base_destino})",
                        'total': total,
                        'prazo_total': prazo_total,
                        'maior_peso': peso_cubado,
                        'peso_usado': 'Real' if peso_real >= peso_cubado else 'Cubado',
                        'rota_bases': rota_bases,
                        'detalhamento_custos': {
                            'coleta': 0,  # Sem agente de coleta
                            'transferencia': custo_transferencia['total'],
                            'entrega': custo_entrega['total'],
                            'pedagio': custo_transferencia.get('pedagio', 0) + custo_entrega.get('pedagio', 0),
                            'gris_total': custo_transferencia.get('gris', 0) + custo_entrega.get('gris', 0)
                        },
                        'observacoes': f"Rota via base: Cliente entrega em {origem}, transferência para {base_destino}, entrega em {destino}",
                        'status_rota': 'PARCIAL_SEM_COLETA',
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
                    print(f"[ROTAS] ✅ Rota via base criada: {rota_bases} - R$ {total:.2f}")

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
                                'tipo_rota': 'transferencia_entrega',
                                'resumo': f"{formatar_nome_agente(fornecedor_transf)} (Transferência) + {formatar_nome_agente(fornecedor_ent)} (Entrega)",
                                'total': total,
                                'prazo_total': prazo_total,
                                'maior_peso': peso_cubado,
                                'peso_usado': 'Real' if peso_real >= peso_cubado else 'Cubado',
                                'rota_bases': rota_bases,  # ✅ CORREÇÃO: Mostra rota real das cidades
                                'detalhamento_custos': {
                                    'coleta': 0,  # Sem agente de coleta
                                    'transferencia': custo_transferencia['total'],
                                    'entrega': custo_entrega['total'],
                                    'pedagio': custo_transferencia.get('pedagio', 0) + custo_entrega.get('pedagio', 0),
                                    'gris_total': custo_transferencia.get('gris', 0) + custo_entrega.get('gris', 0)
                                },
                                'observacoes': f"Sem agente de coleta em {origem}",
                                'status_rota': 'PARCIAL_SEM_COLETA',
                                'agente_coleta': {
                                    'fornecedor': 'SEM AGENTE',
                                    'custo': 0,
                                    'total': 0,
                                    'pedagio': 0,
                                    'gris': 0,
                                    'seguro': 0,
                                    'prazo': 0,
                                    'sem_agente': True,
                                    'observacao': ''
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

        # Se não há agentes de coleta mas há transferências diretas - NÃO criar rotas duplicadas aqui
        # As rotas já foram criadas em PRIORIDADE MÁXIMA acima

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
                                'resumo': f"{formatar_nome_agente(fornecedor_col)} (Coleta) + {formatar_nome_agente(fornecedor_transf)} (Transferência) - Cliente retira no destino",
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

        # REMOVIDO: Seção 4 - estava duplicando as rotas já criadas em PRIORIDADE MÁXIMA

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
                            'resumo': f"{formatar_nome_agente(fornecedor_transf)} - Transferência Direta (Cliente entrega e retira)",
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
        # Função inline para validar e corrigir rotas
        def validar_e_corrigir_rota_fracionada(rota):
            """Valida e corrige campos de uma rota para garantir consistência"""
            if not isinstance(rota, dict):
                return rota
                
            # Garantir que campos essenciais existam
            if 'tipo_rota' not in rota:
                rota['tipo_rota'] = 'transferencia_direta'
            
            # Garantir detalhamento_custos
            if 'detalhamento_custos' not in rota or not isinstance(rota.get('detalhamento_custos'), dict):
                rota['detalhamento_custos'] = {
                    'coleta': 0,
                    'transferencia': 0,
                    'entrega': 0,
                    'gris_total': 0,
                    'pedagio': 0,
                    'total': rota.get('total', 0)
                }
            
            return rota
        
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
        # Retornar estrutura vazia ao invés de None
        return {
            'rotas': [],
            'total_opcoes': 0,
            'origem': f"{origem}/{uf_origem}",
            'destino': f"{destino}/{uf_destino}",
            'estatisticas': {
                'rotas_completas': 0,
                'rotas_parciais': 0,
                'fornecedores_unicos': 0
            },
            'avisos': [f"Erro ao calcular rotas: {str(e)}"],
            'agentes_faltando': {'origem': False, 'destino': False}
        }
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
        def _get(d, key, default=0):
            try:
                if key in d:
                    return d.get(key)
                return d.get(str(key), default)
            except Exception:
                try:
                    return d.get(str(key), default)
                except Exception:
                    return default
        def _parse_decimal(v):
            try:
                if v is None:
                    return 0.0
                if isinstance(v, (int, float)):
                    return float(v)
                s = str(v).strip().replace('%', '')
                s = s.replace('.', '').replace(',', '.')
                return float(s)
            except Exception:
                return 0.0
        # Validar peso_cubado
        if peso_cubado is None:
            print(f"[CUSTO] ❌ Erro: peso_cubado é None")
            return None
            
        # Garantir que peso_cubado é float
        try:
            peso_cubado = float(peso_cubado)
        except (ValueError, TypeError):
            print(f"[CUSTO] ❌ Erro: peso_cubado inválido: {peso_cubado}")
            return None
            
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
        # Função auxiliar: cálculo básico de transferência (mesma regra para todos)
        def _calc_transfer_like():
            peso_calculo_local = float(peso_cubado)
            # 1) Valor mínimo até 10kg
            valor_minimo_local = None
            if 'VALOR MÍNIMO ATÉ 10' in linha and pd.notna(linha.get('VALOR MÍNIMO ATÉ 10')):
                try:
                    valor_minimo_local = float(linha.get('VALOR MÍNIMO ATÉ 10', 0))
                except (ValueError, TypeError):
                    valor_minimo_local = None

            if peso_calculo_local <= 10 and valor_minimo_local is not None and valor_minimo_local > 0:
                return valor_minimo_local

            # 2) Seleção de faixa por peso (10–∞)
            faixas_kg = [20, 30, 50, 70, 100, 150, 200, 300, 500]
            valor_por_kg_local = 0.0

            # Encontrar a menor faixa >= peso
            for faixa in faixas_kg:
                if peso_calculo_local <= float(faixa):
                    try:
                        valor_por_kg_local = float(linha.get(faixa, 0) or 0)
                    except (ValueError, TypeError):
                        valor_por_kg_local = 0.0
                    if valor_por_kg_local > 0:
                        return peso_calculo_local * valor_por_kg_local
                    # Se a coluna da faixa estiver vazia, continua procurando próxima

            # 3) Acima de 500kg: tentar colunas "Acima 500"/"Acima 1000"/"Acima 2000"
            for col_acima in ['Acima 500', 'Acima 1000', 'Acima 2000']:
                if col_acima in linha and pd.notna(linha.get(col_acima)):
                    try:
                        valor_por_kg_local = float(linha.get(col_acima, 0) or 0)
                    except (ValueError, TypeError):
                        valor_por_kg_local = 0.0
                    if valor_por_kg_local > 0:
                        return peso_calculo_local * valor_por_kg_local

            # 4) Fallbacks: usar a maior faixa disponível com valor > 0
            for faixa in reversed(faixas_kg):
                try:
                    v = float(linha.get(faixa, 0) or 0)
                except (ValueError, TypeError):
                    v = 0.0
                if v > 0:
                    return peso_calculo_local * v

            # 5) Se nada encontrado e há valor mínimo, retorna valor mínimo como último recurso
            if valor_minimo_local and valor_minimo_local > 0:
                return valor_minimo_local

            return 0.0

        # 🔧 LÓGICA ESPECÍFICA PARA TRANSFERÊNCIAS
        fornecedor_upper = str(fornecedor).upper()
        tipo_servico = str(linha.get('Tipo', '')).upper()
        
        if tipo_servico == 'TRANSFERÊNCIA' or 'TRANSFERENCIA' in tipo_servico:
            print(f"[CUSTO-TRANSF] 🔧 Aplicando lógica para transferência: {fornecedor}")
            custo_base = _calc_transfer_like()
            
        # 🔧 LÓGICA ESPECÍFICA PARA REUNIDAS - VALOR FIXO POR FAIXA
        elif 'REUNIDAS' in fornecedor_upper:
            print(f"[CUSTO-REUNIDAS] 🔧 Aplicando lógica de faixas de peso para REUNIDAS: {fornecedor}")
            
            # REUNIDAS usa valores fixos por faixa (não multiplica pelo peso)
            peso_calculo = peso_cubado  # Já é o máximo entre peso real e cubado
            
            # Validar peso_calculo
            if peso_calculo is None or peso_calculo <= 0:
                print(f"[CUSTO-REUNIDAS] ❌ Peso inválido: {peso_calculo}")
                return None
                
            # 1. Verificar valor mínimo para até 10kg
            if 'VALOR MÍNIMO ATÉ 10' in linha and pd.notna(linha.get('VALOR MÍNIMO ATÉ 10')):
                valor_minimo = float(linha.get('VALOR MÍNIMO ATÉ 10', 0))
                
                # Se peso for até 10kg, usar valor mínimo
                if peso_calculo <= 10:
                    valor_base = valor_minimo
                    print(f"[CUSTO-REUNIDAS] ✅ Peso ≤ 10kg: Valor mínimo R$ {valor_base:.2f}")
                    custo_base = valor_base
                else:
                    # Para pesos acima de 10kg, buscar faixa apropriada
                    if peso_calculo > 200:
                        # REUNIDAS: Acima de 200kg usa lógica de EXCEDENTE
                        try:
                            valor_200 = float(linha.get('200', linha.get(200, 0)))  # Valor base até 200kg
                        except Exception:
                            valor_200 = 0.0
                        excedente_por_kg = float(linha.get('EXCEDENTE', 0))  # Valor por kg excedente
                        
                        if excedente_por_kg > 0:
                            peso_excedente = peso_calculo - 200
                            valor_excedente = peso_excedente * excedente_por_kg
                            valor_base = valor_200 + valor_excedente
                            print(f"[CUSTO-REUNIDAS] ✅ Peso >200kg: Base 200kg (R$ {valor_200:.2f}) + Excedente {peso_excedente:.1f}kg × R$ {excedente_por_kg:.4f} = R$ {valor_base:.2f}")
                        else:
                            # Se não tiver excedente definido, usar faixa mais próxima
                            if peso_calculo > 500:
                                try:
                                    valor_base = float(linha.get('Acima 500', linha.get('500', linha.get(500, 0))))
                                except Exception:
                                    valor_base = 0.0
                                print(f"[CUSTO-REUNIDAS] ⚠️ Sem excedente definido, usando faixa >500kg: R$ {valor_base:.2f}")
                            elif peso_calculo > 300:
                                try:
                                    valor_base = float(linha.get('500', linha.get(500, 0)))
                                except Exception:
                                    valor_base = 0.0
                                print(f"[CUSTO-REUNIDAS] ⚠️ Sem excedente definido, usando faixa 500kg: R$ {valor_base:.2f}")
                            else:
                                try:
                                    valor_base = float(linha.get('300', linha.get(300, 0)))
                                except Exception:
                                    valor_base = 0.0
                                print(f"[CUSTO-REUNIDAS] ⚠️ Sem excedente definido, usando faixa 300kg: R$ {valor_base:.2f}")
                    else:
                        # Para pesos entre 10kg e 200kg, usar valor fixo da faixa
                        faixas_peso = [20, 30, 50, 70, 100, 150, 200]
                        
                        # Encontrar a menor faixa que seja maior ou igual ao peso
                        valor_base = 0
                        faixa_usada = None
                        for faixa in faixas_peso:
                            if peso_calculo <= faixa:
                                try:
                                    valor_faixa = float(linha.get(str(faixa), 0))
                                except Exception:
                                    try:
                                        valor_faixa = float(linha.get(faixa, 0))
                                    except Exception:
                                        valor_faixa = 0.0
                                if valor_faixa > 0:  # Só usar se tiver valor
                                    valor_base = valor_faixa  # REUNIDAS usa valor fixo da faixa
                                    faixa_usada = faixa
                                    print(f"[CUSTO-REUNIDAS] ✅ Peso {peso_calculo}kg na faixa até {faixa}kg: Valor fixo R$ {valor_base:.2f}")
                                    break
                        
                        if not faixa_usada:
                            # Se não encontrou faixa válida, usar a última disponível
                            try:
                                valor_base = float(linha.get('200', linha.get(200, 0)))
                            except Exception:
                                valor_base = 0.0
                            print(f"[CUSTO-REUNIDAS] ⚠️ Usando faixa 200kg (padrão): Valor fixo R$ {valor_base:.2f}")
                    
                    custo_base = valor_base
            else:
                # Se não tiver valor mínimo, começar direto com as faixas
                print(f"[CUSTO-REUNIDAS] ⚠️ Sem valor mínimo definido, usando faixas direto")
                custo_base = 0
                
        # 🔧 LÓGICA ESPECÍFICA PARA JEM/DFL - CORREÇÃO DO CÁLCULO
        elif 'JEM' in fornecedor_upper or 'DFL' in fornecedor_upper:
            # Tratar JEM/DFL exatamente como transferência padrão (exceto colunas M-N já ignoradas)
            print(f"[CUSTO-JEM] 🔧 Aplicando regra padrão de transferência para JEM/DFL: {fornecedor}")
            custo_base = _calc_transfer_like()
        
        # 🔧 LÓGICA ESPECÍFICA PARA PTX - VALOR DA BASE × PESO
        elif 'PTX' in fornecedor_upper:
            print(f"[CUSTO-PTX] 🔧 Aplicando lógica específica para PTX: {fornecedor}")
            
            # PTX usa valores da tabela da base de dados multiplicados pelo peso
            # Preferir chaves string para evitar acesso posicional do pandas
            valor_por_kg = 0.0
            for key in ['20', 20]:
                try:
                    v = linha.get(key, 0)
                    if v:
                        valor_por_kg = float(v)
                        break
                except Exception:
                    continue
            if valor_por_kg == 0:
                # Se não tiver valor na coluna 20, tentar outras colunas
                for coluna in ['10', 10, '30', 30, '50', 50, '70', 70, '100', 100]:
                    try:
                        v = linha.get(coluna, 0)
                        if v:
                            valor_por_kg = float(v)
                            break
                    except Exception:
                        continue
            
            custo_base = float(peso_cubado) * valor_por_kg
            print(f"[CUSTO-PTX] {peso_cubado}kg × R$ {valor_por_kg:.4f} = R$ {custo_base:.2f}")
        
        # 🔧 LÓGICA ESPECÍFICA PARA EXPRESSO S. MIGUEL - COLUNAS G, P, Q, S
        elif 'EXPRESSO S. MIGUEL' in fornecedor_upper:
            print(f"[CUSTO-EXPRESSO] 🔧 Aplicando lógica específica para EXPRESSO S. MIGUEL: {fornecedor}")
            
            # EXPRESSO S. MIGUEL usa colunas específicas:
            # - Coluna G: Valor mínimo (VALOR MÍNIMO ATÉ 10)
            # - Coluna P: Excedente até 500kg
            # - Coluna Q: Excedente 500-1000kg
            # - Coluna S: Excedente acima de 1000kg
            
            valor_base = 0
            
            # 1. Verificar valor mínimo (Coluna G)
            valor_minimo = linha.get('VALOR MÍNIMO ATÉ 10', 0)
            if pd.notna(valor_minimo):
                valor_minimo = float(valor_minimo)
                
                # 2. Determinar qual coluna usar baseado no peso
                if peso_cubado <= 10:
                    # Usar apenas valor mínimo
                    valor_base = valor_minimo
                    print(f"[CUSTO-EXPRESSO] ✅ Peso ≤ 10kg: Valor mínimo (Coluna G) R$ {valor_base:.2f}")
                
                elif peso_cubado <= 500:
                    # Calcular excedente: peso_total × valor_por_kg (Coluna P)
                    valor_por_kg = linha.get('Acima 500', 0)  # Coluna P
                    if pd.notna(valor_por_kg):
                        valor_por_kg = float(valor_por_kg)
                        valor_calculado = peso_cubado * valor_por_kg
                        
                        # Se o valor calculado for menor que o mínimo, usar o mínimo
                        if valor_calculado < valor_minimo:
                            valor_base = valor_minimo
                            print(f"[CUSTO-EXPRESSO] ✅ Peso {peso_cubado}kg (≤500kg): {peso_cubado}kg × R$ {valor_por_kg:.4f} = R$ {valor_calculado:.2f} < mínimo R$ {valor_minimo:.2f} → Usar mínimo R$ {valor_base:.2f}")
                        else:
                            valor_base = valor_calculado
                            print(f"[CUSTO-EXPRESSO] ✅ Peso {peso_cubado}kg (≤500kg): {peso_cubado}kg × R$ {valor_por_kg:.4f} = R$ {valor_base:.2f}")
                
                elif peso_cubado <= 1000:
                    # Calcular excedente: peso_total × valor_por_kg (Coluna Q)
                    valor_por_kg = linha.get('Acima 1000', 0)  # Coluna Q
                    if pd.notna(valor_por_kg):
                        valor_por_kg = float(valor_por_kg)
                        valor_calculado = peso_cubado * valor_por_kg
                        
                        # Se o valor calculado for menor que o mínimo, usar o mínimo
                        if valor_calculado < valor_minimo:
                            valor_base = valor_minimo
                            print(f"[CUSTO-EXPRESSO] ✅ Peso {peso_cubado}kg (500-1000kg): {peso_cubado}kg × R$ {valor_por_kg:.4f} = R$ {valor_calculado:.2f} < mínimo R$ {valor_minimo:.2f} → Usar mínimo R$ {valor_base:.2f}")
                        else:
                            valor_base = valor_calculado
                            print(f"[CUSTO-EXPRESSO] ✅ Peso {peso_cubado}kg (500-1000kg): {peso_cubado}kg × R$ {valor_por_kg:.4f} = R$ {valor_base:.2f}")
                
                else:
                    # Calcular excedente: peso_total × valor_por_kg (Coluna S)
                    valor_por_kg = linha.get('Acima 2000', 0)  # Coluna S
                    if pd.notna(valor_por_kg):
                        valor_por_kg = float(valor_por_kg)
                        valor_calculado = peso_cubado * valor_por_kg
                        
                        # Se o valor calculado for menor que o mínimo, usar o mínimo
                        if valor_calculado < valor_minimo:
                            valor_base = valor_minimo
                            print(f"[CUSTO-EXPRESSO] ✅ Peso {peso_cubado}kg (>1000kg): {peso_cubado}kg × R$ {valor_por_kg:.4f} = R$ {valor_calculado:.2f} < mínimo R$ {valor_minimo:.2f} → Usar mínimo R$ {valor_base:.2f}")
                        else:
                            valor_base = valor_calculado
                            print(f"[CUSTO-EXPRESSO] ✅ Peso {peso_cubado}kg (>1000kg): {peso_cubado}kg × R$ {valor_por_kg:.4f} = R$ {valor_base:.2f}")
            
            print(f"[CUSTO-EXPRESSO] Fornecedor: {fornecedor}, Peso: {peso_cubado}kg, Base: R$ {valor_base:.2f}")
            custo_base = valor_base
        
        else:
            # LÓGICA PADRÃO PARA OUTROS FORNECEDORES
            # Validar peso_cubado
            if peso_cubado is None or peso_cubado <= 0:
                print(f"[CUSTO] ❌ Peso inválido para {fornecedor}: {peso_cubado}")
                return None
                
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
        
        # 🔧 GARANTIR QUE custo_base ESTEJA DEFINIDO PARA TODOS OS FORNECEDORES
        if 'custo_base' not in locals():
            print(f"[CUSTO] ⚠️ custo_base não definido para {fornecedor}, usando valor padrão")
            custo_base = valor_base if 'valor_base' in locals() else 0.0
        
        # 🔧 CALCULAR PEDÁGIO (APLICADO PARA TRANSFERÊNCIAS TAMBÉM)
        pedagio = 0.0
        try:
            valor_pedagio = float(linha.get('Pedagio (100 Kg)', 0) or 0)
            if valor_pedagio > 0 and peso_cubado > 0:
                blocos_pedagio = math.ceil(peso_cubado / 100)
                pedagio = blocos_pedagio * valor_pedagio
                print(f"[PEDAGIO] {fornecedor}: {blocos_pedagio} blocos × R$ {valor_pedagio:.2f} = R$ {pedagio:.2f}")
        except (ValueError, TypeError):
            pedagio = 0.0
        
        # 🔧 CALCULAR GRIS (APLICADO PARA TRANSFERÊNCIAS TAMBÉM)
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
                    
                    # 🔧 VERIFICAÇÃO ESPECÍFICA PARA JEM/DFL
                    if 'JEM' in fornecedor_upper or 'DFL' in fornecedor_upper:
                        print(f"[GRIS-JEM] {fornecedor}: {gris_exc:.1f}% de R$ {valor_nf:,.2f} = R$ {gris_valor:.2f} (mín: R$ {gris_min:.2f})")
                    else:
                        print(f"[GRIS] {fornecedor}: {gris_exc:.1f}% de R$ {valor_nf:,.2f} = R$ {gris_valor:.2f} (mín: R$ {gris_min:.2f})")
        except (ValueError, TypeError) as e:
            print(f"[GRIS] ❌ Erro ao calcular GRIS para {fornecedor}: {e}")
            gris_valor = 0.0
        
        # Calcular total
        total = custo_base + pedagio + gris_valor
        
        # 🔧 CALCULAR SEGURO SE DISPONÍVEL
        seguro = 0
        # EXCEÇÃO: ML e GRITSCH não calculam seguro, apenas GRIS
        # EXPRESSO S. MIGUEL CALCULA SEGURO normalmente
        if 'ML' not in fornecedor_upper and 'GRITSCH' not in fornecedor_upper:
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
        else:
            print(f"[SEGURO] {fornecedor}: Não calcula seguro (apenas GRIS)")
        
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
        
        # 🔧 VERIFICAÇÃO ESPECÍFICA PARA JEM/DFL
        if 'JEM' in fornecedor_upper or 'DFL' in fornecedor_upper:
            print(f"[CUSTO-JEM] 🔍 VERIFICAÇÃO FINAL: {fornecedor}")
            print(f"[CUSTO-JEM] 📊 Base: R$ {custo_base:.2f}")
            print(f"[CUSTO-JEM] 📊 GRIS: R$ {gris_valor:.2f}")
            print(f"[CUSTO-JEM] 📊 Pedágio: R$ {pedagio:.2f}")
            print(f"[CUSTO-JEM] 📊 Seguro: R$ {seguro:.2f}")
            print(f"[CUSTO-JEM] 📊 TOTAL: R$ {total:.2f}")
        
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
        
        # TRATAMENTO ESPECIAL PARA ML, GRITSCH E EXPRESSO S. MIGUEL - forçar como DIRETO
        if 'ML' in fornecedor.upper() or 'GRITSCH' in fornecedor.upper() or 'EXPRESSO S. MIGUEL' in fornecedor.upper():
            tipo_servico = "DIRETO PORTA-A-PORTA"
            # Forçar tipo como Direto para processamento correto
            linha_temp = linha.copy() if hasattr(linha, 'copy') else dict(linha)
            linha_temp['Tipo'] = 'Direto'
            linha = linha_temp
        
        # Calcular custo usando a função existente
        custo_resultado = calcular_custo_agente(linha, peso_cubado, valor_nf)
        
        if not custo_resultado:
            return None
        
        # Retornar dados formatados
        resultado_processado = {
            'fornecedor': fornecedor,
            'origem': linha.get('Origem', ''),
            'destino': linha.get('Destino', ''),
            'custo_base': custo_resultado['custo_base'],
            'pedagio': custo_resultado['pedagio'],
            'gris': custo_resultado['gris'],
            'seguro': custo_resultado.get('seguro', 0),  # Adicionar seguro no retorno
            'total': custo_resultado['total'],
            'prazo': custo_resultado['prazo'],
            'peso_usado': peso_cubado,
            'tipo_servico': tipo_servico,
            'peso_maximo': custo_resultado.get('peso_maximo'),
            'alerta_peso': custo_resultado.get('alerta_peso'),
            'excede_peso': custo_resultado.get('excede_peso', False)
        }
        
        # 🔧 VERIFICAÇÃO ESPECÍFICA PARA JEM/DFL
        if 'JEM' in fornecedor.upper() or 'DFL' in fornecedor.upper():
            print(f"[PROCESSAR-JEM] 🔍 VERIFICAÇÃO FINAL PROCESSADA: {fornecedor}")
            print(f"[PROCESSAR-JEM] 📊 Base: R$ {resultado_processado['custo_base']:.2f}")
            print(f"[PROCESSAR-JEM] 📊 GRIS: R$ {resultado_processado['gris']:.2f}")
            print(f"[PROCESSAR-JEM] 📊 Pedágio: R$ {resultado_processado['pedagio']:.2f}")
            print(f"[PROCESSAR-JEM] 📊 Seguro: R$ {resultado_processado['seguro']:.2f}")
            print(f"[PROCESSAR-JEM] 📊 TOTAL: R$ {resultado_processado['total']:.2f}")
        
        return resultado_processado
        
    except Exception as e:
        print(f"[PROCESSAR] ❌ Erro ao processar linha {fornecedor}: {e}")
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
        elif tipo_linha == 'Transferência' and fornecedor and ('JEM' in str(fornecedor).upper() or 'CONCEPT' in str(fornecedor).upper() or 'SOL' in str(fornecedor).upper()):
            fator_cubagem = 166  # kg/m³ para JEM, Concept e SOL
            tipo_calculo = f"Transferência {fornecedor} (166kg/m³)"
        else:
            # Padrão para outros tipos
            fator_cubagem = 250  # kg/m³ padrão
            tipo_calculo = f"{tipo_linha} (250kg/m³)"
            
        peso_cubado = cubagem * fator_cubagem
        peso_final = max(peso_real, peso_cubado)
        
        print(f"[PESO_CUBADO] {tipo_calculo}: {peso_real}kg vs {peso_cubado}kg = {peso_final}kg")
        return peso_final
        
    except Exception as e:
        print(f"[PESO_CUBADO] Erro no cálculo: {e}")
        return float(peso_real) if peso_real else 0

def calcular_frete_aereo_base_unificada(origem, uf_origem, destino, uf_destino, peso, valor_nf=None):
    """
    Calcula frete aéreo usando a Base Unificada
    """
    try:
        print(f"[AÉREO] 📦 Iniciando cálculo: {origem}/{uf_origem} → {destino}/{uf_destino}")
        print(f"[AÉREO] Peso: {peso}kg, Valor NF: R$ {valor_nf:,}" if valor_nf else f"[AÉREO] Peso: {peso}kg")
        
        # Carregar base unificada
        df_base = carregar_base_unificada()
        if df_base is None:
            print("[AÉREO] ❌ Erro: Base unificada não disponível")
            return []
            
        # Filtrar apenas serviços aéreos
        df_aereo = df_base[df_base['Tipo'] == 'Aéreo'].copy()
        
        if df_aereo.empty:
            print("[AÉREO] ❌ Nenhum serviço aéreo encontrado na base")
            return []
            
        # Normalizar cidades
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
            return []
        
        # Ordenar por menor custo
        opcoes_aereas.sort(key=lambda x: x['total'])
        
        print(f"[AÉREO] ✅ {len(opcoes_aereas)} opções aéreas encontradas")
        return opcoes_aereas
        
    except Exception as e:
        print(f"[AÉREO] ❌ Erro no cálculo aéreo: {e}")
        return []

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
        elif tipo_rota == 'transferencia_agente_parcial':
            # Rota parcial: SEM agente de coleta
            transferencia = opcao.get('transferencia', detalhes.get('transferencia', {}))
            agente_entrega = opcao.get('agente_entrega', detalhes.get('agente_entrega', {}))
            info['agente_coleta'] = 'SEM AGENTE DE COLETA'
            info['transferencia'] = transferencia.get('fornecedor', transferencia.get('Fornecedor', 'N/A'))
            info['agente_entrega'] = agente_entrega.get('fornecedor', agente_entrega.get('Fornecedor', 'N/A'))
            info['fornecedor_principal'] = info['transferencia']
            # Bases coerentes com a rota parcial
            info['base_origem'] = transferencia.get('origem', transferencia.get('base_origem', 'ORIGEM'))
            info['base_destino'] = agente_entrega.get('base_origem', agente_entrega.get('origem', transferencia.get('destino', transferencia.get('base_destino', 'DESTINO'))))
        elif tipo_rota == 'transferencia_sem_entrega':
            # Rota parcial onde cliente retira na base: SEM coleta e SEM agente de entrega
            transferencia = opcao.get('transferencia', detalhes.get('transferencia', {}))
            info['agente_coleta'] = 'SEM AGENTE DE COLETA'
            info['agente_entrega'] = 'SEM AGENTE DE ENTREGA'
            info['transferencia'] = transferencia.get('fornecedor', transferencia.get('Fornecedor', 'N/A'))
            info['fornecedor_principal'] = info['transferencia']
            info['base_origem'] = transferencia.get('origem', transferencia.get('base_origem', 'ORIGEM'))
            info['base_destino'] = transferencia.get('destino', transferencia.get('base_destino', 'DESTINO'))
            
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

def gerar_ranking_dedicado(custos, analise, rota_info, peso=0, cubagem=0, valor_nf=None):
    """
    Gera ranking das opções de frete dedicado no formato "all in"
    """
    try:
        # Preparar ranking das opcoes baseado nos custos
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

def extrair_detalhamento_custos(opcao, peso_cubado, valor_nf):
    """
    Extrai detalhamento completo de custos de uma opção
    """
    try:
        # Validar entrada
        if not isinstance(opcao, dict):
            print(f"[CUSTOS] ⚠️ Opção não é um dicionário: {type(opcao)}")
            return {
                'custo_base_frete': 0,
                'pedagio': 0,
                'gris': 0,
                'seguro': 0,
                'tda': 0,
                'outros': 0,
                'total_custos': 0
            }
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
                if not agente_data or not isinstance(agente_data, dict):
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
                if not agente_data or not isinstance(agente_data, dict):
                    return 0
                return (
                    agente_data.get('pedagio', 0) or
                    agente_data.get('toll', 0) or
                    0
                )
            
            def extrair_gris_agente(agente_data):
                if not agente_data or not isinstance(agente_data, dict):
                    return 0
                return (
                    agente_data.get('gris', 0) or
                    agente_data.get('gris_value', 0) or
                    0
                )
            
            def extrair_seguro_agente(agente_data):
                if not agente_data or not isinstance(agente_data, dict):
                    return 0
                return (
                    agente_data.get('seguro', 0) or
                    agente_data.get('insurance', 0) or
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
                elif tipo_rota == 'transferencia_entrega' or tipo_rota == 'transferencia_direta_entrega' or tipo_rota == 'cliente_entrega_transferencia_agente_entrega' or tipo_rota == 'PARCIAL_SEM_COLETA':
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
            
            # Debug: verificar se os dados dos agentes estão sendo extraídos corretamente
            print(f"[RANKING] Opção {i} - agentes_info: {agentes_info}")
            
            # Determinar tipo de serviço para mostrar no ranking
            if tipo_rota == 'transferencia_direta':
                # Para transferência direta, mostrar o nome do fornecedor
                fornecedor_nome = agentes_info['fornecedor_principal']
                tipo_servico = f"TRANSFERÊNCIA - {fornecedor_nome}"
                descricao = f"Transferência direta via {fornecedor_nome}"
                capacidade_info = {
                    'peso_max': 'Ilimitado',
                    'volume_max': 'Ilimitado',
                    'descricao': 'Transferência rodoviária direta'
                }
            elif tipo_rota == 'direto_porta_porta':
                # Para serviço direto, mostrar o nome do fornecedor
                fornecedor_nome = agentes_info['fornecedor_principal']
                tipo_servico = f"DIRETO - {fornecedor_nome}"
                rota_bases = opcao.get('rota_bases', f"{origem} → {destino} (Direto)")
                descricao = f"ROTA: {rota_bases}<br/>Coleta e entrega incluídas no serviço"
                
                # Usar capacidades reais do fornecedor da base de dados
                detalhes_opcao = opcao.get('detalhes', {})
                peso_maximo = detalhes_opcao.get('peso_maximo_transportado', 'N/A')
                prazo_real = detalhes_opcao.get('prazo', 'N/A')
                
                # Converter peso máximo para formato legível
                if peso_maximo and peso_maximo != 'N/A':
                    try:
                        peso_max_kg = float(peso_maximo)
                        if peso_max_kg >= 1000:
                            peso_max_str = f"{peso_max_kg/1000:.1f} ton"
                        else:
                            peso_max_str = f"{peso_max_kg:.0f}kg"
                    except:
                        peso_max_str = f"{peso_maximo}kg"
                else:
                    peso_max_str = "500kg"  # Default
                
                # Calcular volume máximo baseado no peso (aproximação: 1m³ = 300kg)
                if peso_maximo and peso_maximo != 'N/A':
                    try:
                        volume_max_m3 = float(peso_maximo) / 300
                        volume_max_str = f"{volume_max_m3:.1f}m³"
                    except:
                        volume_max_str = "15m³"  # Default
                else:
                    volume_max_str = "15m³"  # Default
                
                capacidade_info = {
                    'peso_max': peso_max_str,
                    'volume_max': volume_max_str,
                    'descricao': f'Serviço porta-a-porta - Prazo: {prazo_real} dias'
                }
            elif tipo_rota == 'agente_direto':
                # Para agente direto, mostrar o nome do agente
                agente_nome = agentes_info['fornecedor_principal']
                tipo_servico = f"AGENTE - {agente_nome}"
                descricao = f"Porta-a-porta direto via {agente_nome}"
                
                # Usar capacidades reais do agente
                detalhes_opcao = opcao.get('detalhes', {})
                peso_maximo = detalhes_opcao.get('peso_maximo_transportado', 'N/A')
                prazo_real = detalhes_opcao.get('prazo', 'N/A')
                
                # Converter peso máximo para formato legível
                if peso_maximo and peso_maximo != 'N/A':
                    try:
                        peso_max_kg = float(peso_maximo)
                        if peso_max_kg >= 1000:
                            peso_max_str = f"{peso_max_kg/1000:.1f} ton"
                        else:
                            peso_max_str = f"{peso_max_kg:.0f}kg"
                    except:
                        peso_max_str = f"{peso_maximo}kg"
                else:
                    peso_max_str = "500kg"  # Default
                
                # Calcular volume máximo baseado no peso
                if peso_maximo and peso_maximo != 'N/A':
                    try:
                        volume_max_m3 = float(peso_maximo) / 300
                        volume_max_str = f"{volume_max_m3:.1f}m³"
                    except:
                        volume_max_str = "15m³"  # Default
                else:
                    volume_max_str = "15m³"  # Default
                
                capacidade_info = {
                    'peso_max': peso_max_str,
                    'volume_max': volume_max_str,
                    'descricao': f'Agente direto - Prazo: {prazo_real} dias'
                }
            else:
                # Para outros tipos de rota (transferência + entrega, etc.)
                # Criar nome descritivo com os agentes envolvidos
                agentes_nomes = []
                
                if agentes_info['agente_coleta'] and agentes_info['agente_coleta'] != 'N/A':
                    agentes_nomes.append(agentes_info['agente_coleta'])
                
                if agentes_info['transferencia'] and agentes_info['transferencia'] != 'N/A':
                    agentes_nomes.append(agentes_info['transferencia'])
                
                if agentes_info['agente_entrega'] and agentes_info['agente_entrega'] != 'N/A':
                    agentes_nomes.append(agentes_info['agente_entrega'])
                
                # Se não conseguiu extrair nomes específicos, usar fornecedor principal
                if not agentes_nomes:
                    agentes_nomes = [agentes_info['fornecedor_principal']]
                
                # Criar nome da rota com os agentes
                if len(agentes_nomes) == 1:
                    tipo_servico = f"{agentes_nomes[0]}"
                else:
                    tipo_servico = f"{' + '.join(agentes_nomes)}"
                
                descricao = f"{agentes_info['fornecedor_principal']}"
                capacidade_info = {
                    'peso_max': 'Variável',
                    'volume_max': 'Variável',
                    'descricao': 'Rota com agentes e transferências'
                }
            
            # Determinar ícone da posição
            if i == 1:
                icone_posicao = "🥇"
            elif i == 2:
                icone_posicao = "🥈"
            elif i == 3:
                icone_posicao = "🥉"
            else:
                icone_posicao = f"{i}º"
            
            # Calcular prazo estimado baseado na distância ou usar prazo real
            prazo_estimado = calcular_prazo_total_agentes(opcao, tipo_rota)
            
            # Extrair detalhamento de custos
            detalhamento_custos = extrair_detalhamento_custos(opcao, peso_cubado, valor_nf)
            
            # Calcular o maior peso máximo entre os agentes da rota
            peso_maximos = []
            for etapa in ['agente_coleta', 'transferencia', 'agente_entrega']:
                etapa_data = detalhes_opcao.get(etapa, {})
                if etapa_data and etapa_data.get('peso_maximo'):
                    try:
                        peso_maximos.append(float(etapa_data['peso_maximo']))
                    except Exception:
                        pass
            
            # Se não encontrou peso máximo nos detalhes, tentar extrair do peso_maximo_transportado
            if not peso_maximos and detalhes_opcao.get('peso_maximo_transportado'):
                try:
                    peso_maximos.append(float(detalhes_opcao['peso_maximo_transportado']))
                except Exception:
                    pass
            
            # Converter para formato legível
            if peso_maximos:
                peso_max_kg = max(peso_maximos)
                if peso_max_kg >= 1000:
                    peso_maximo_agente = f"{peso_max_kg/1000:.1f} ton"
                else:
                    peso_maximo_agente = f"{peso_max_kg:.0f}kg"
            else:
                peso_maximo_agente = None
            
            opcao_ranking = {
                'posicao': i,
                'icone': f"{icone_posicao} 📦",
                'tipo_servico': tipo_servico,
                'fornecedor': agentes_info['fornecedor_principal'],
                'descricao': descricao,
                'custo_total': opcao.get('total', 0),
                'prazo': prazo_estimado,
                'peso_usado': f"{peso}kg" if peso else "Não informado",
                'capacidade': capacidade_info,
                'peso_maximo_agente': peso_maximo_agente,  # Novo campo
                'eh_melhor_opcao': (i == 1),
                
                # Detalhes expandidos
                'detalhes_expandidos': {
                    'custos_detalhados': detalhamento_custos,
                    'agentes_info': agentes_info,  # 🔧 CORREÇÃO: Mover para o nível correto
                    'rota_info': {
                        'origem': origem,
                        'destino': destino,
                        'tipo_rota': tipo_rota,
                        'observacoes': opcao.get('observacoes', ''),
                        'status_rota': opcao.get('status_rota', 'N/A'),
                        'peso_cubado': peso_cubado,
                        'peso_real': peso_real,
                        'cubagem': cubagem,
                        'tipo_peso_usado': 'Real' if peso_real >= peso_cubado else 'Cubado'
                    },
                    'dados_agentes': detalhes_opcao,  # Adicionar dados completos dos agentes
                    'servico_info': {
                        'tipo': tipo_rota,
                        'capacidade_peso': capacidade_info['peso_max'],
                        'capacidade_volume': capacidade_info['volume_max'],
                        'descricao': capacidade_info['descricao']
                    }
                }
            }
            
            ranking_opcoes.append(opcao_ranking)
        
        # Informações consolidadas da cotação
        melhor_opcao = ranking_opcoes[0] if ranking_opcoes else None
        
        # Gerar ID único para o cálculo
        import datetime
        id_calculo = f"#Frac{len(ranking_opcoes):03d}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        resultado_formatado = {
            'id_calculo': id_calculo,
            'tipo_frete': 'Fracionado',
            'origem': origem,
            'destino': destino,
            'peso': peso,
            'cubagem': cubagem,
            'valor_nf': valor_nf,
            'peso_cubado': peso_cubado,
            'peso_usado_tipo': 'Real' if peso_real >= peso_cubado else 'Cubado',
            'melhor_opcao': melhor_opcao,
            'ranking_opcoes': ranking_opcoes,
            'total_opcoes': len(ranking_opcoes),
            'data_calculo': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            'distancia': 0,  # Não calculado para fracionado
            'tempo_estimado': 'Variável'
        }
        
        return resultado_formatado
    except Exception as e:
        print(f"[RANKING FRACIONADO] Erro ao gerar ranking: {e}")
        import traceback
        traceback.print_exc()
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

# Rotas administrativas
@app.route("/admin")
@middleware_admin
def admin_dashboard():
    try:
        from collections import Counter
        usuario_dados = usuario_logado()
        ip_cliente = obter_ip_cliente()
        log_acesso(session.get('usuario_logado', 'DESCONHECIDO'), 'ADMIN_ACESSO_DASHBOARD', ip_cliente, 'Acesso ao painel admin')

        total_logs = len(LOGS_SISTEMA)
        total_pesquisas = len(HISTORICO_PESQUISAS)
        usuarios_unicos = len({log['usuario'] for log in LOGS_SISTEMA}) if LOGS_SISTEMA else 0
        ips_unicos = len({log['ip'] for log in LOGS_SISTEMA}) if LOGS_SISTEMA else 0
        ultimas_atividades = LOGS_SISTEMA[-10:] if LOGS_SISTEMA else []
        acoes_mais_comuns = []
        if LOGS_SISTEMA:
            contador_acoes = Counter([log.get('acao', 'N/A') for log in LOGS_SISTEMA])
            acoes_mais_comuns = list(contador_acoes.most_common(6))

        estatisticas = {
            'total_logs': total_logs,
            'total_pesquisas': total_pesquisas,
            'usuarios_unicos': usuarios_unicos,
            'ips_unicos': ips_unicos,
            'ultimas_atividades': ultimas_atividades,
            'acoes_mais_comuns': acoes_mais_comuns
        }

        return render_template("admin.html", usuario=usuario_dados, estatisticas=estatisticas)
    except Exception as e:
        print(f"[ADMIN] Erro no dashboard: {e}")
        return redirect(url_for('index'))

@app.route("/admin/logs")
@middleware_admin
def admin_logs():
    try:
        ip_cliente = obter_ip_cliente()
        log_acesso(session.get('usuario_logado', 'DESCONHECIDO'), 'ADMIN_ACESSO_LOGS', ip_cliente, 'Acesso aos logs do sistema')

        # Filtros
        filtro_usuario = request.args.get('usuario', '').strip()
        filtro_acao = request.args.get('acao', '').strip()
        filtro_data = request.args.get('data', '').strip()  # Formato esperado: DD/MM/YYYY
        page = int(request.args.get('page', 1) or 1)
        page_size = 25

        logs_filtrados = LOGS_SISTEMA[:]

        if filtro_usuario:
            logs_filtrados = [l for l in logs_filtrados if str(l.get('usuario', '')).strip() == filtro_usuario]
        if filtro_acao:
            logs_filtrados = [l for l in logs_filtrados if str(l.get('acao', '')).strip() == filtro_acao]
        if filtro_data:
            logs_filtrados = [l for l in logs_filtrados if str(l.get('data_hora', '')).startswith(filtro_data)]

        total_logs = len(logs_filtrados)
        start = (page - 1) * page_size
        end = start + page_size
        logs_paginados = logs_filtrados[start:end]

        usuarios_unicos = sorted({l.get('usuario', '') for l in LOGS_SISTEMA if l.get('usuario')})
        acoes_unicas = sorted({l.get('acao', '') for l in LOGS_SISTEMA if l.get('acao')})

        filtros = {
            'usuario': filtro_usuario,
            'acao': filtro_acao,
            'data': filtro_data
        }

        has_prev = page > 1
        has_next = end < total_logs

        return render_template(
            "admin_logs.html",
            total_logs=total_logs,
            logs=logs_paginados,
            usuarios_unicos=usuarios_unicos,
            acoes_unicas=acoes_unicas,
            filtros=filtros,
            page=page,
            has_prev=has_prev,
            has_next=has_next
        )
    except Exception as e:
        print(f"[ADMIN] Erro em /admin/logs: {e}")
        return redirect(url_for('admin_dashboard'))

@app.route("/admin/historico-detalhado")
@middleware_admin
def admin_historico_detalhado():
    try:
        ip_cliente = obter_ip_cliente()
        log_acesso(session.get('usuario_logado', 'DESCONHECIDO'), 'ADMIN_ACESSO_HISTORICO', ip_cliente, 'Acesso ao histórico detalhado')

        historico_view = []
        for item in HISTORICO_PESQUISAS:
            if isinstance(item, dict):
                historico_view.append({
                    'tipo': item.get('tipo', 'Cálculo'),
                    'id': item.get('id_historico') or item.get('id_calculo') or 'N/A',
                    'data_hora': item.get('data_hora') or item.get('data_calculo') or 'N/A',
                    'detalhes': f"Origem: {item.get('origem', 'N/A')} -> Destino: {item.get('destino', 'N/A')} | Distância: {round(item.get('distancia', 0), 2) if isinstance(item.get('distancia', 0), (int, float)) else item.get('distancia', 'N/A')} | Provedor: {item.get('provider', 'N/A')}"
                })

        # Ordenar por data se possível (strings no formato DD/MM/YYYY HH:MM:SS)
        try:
            from datetime import datetime
            historico_view.sort(key=lambda x: datetime.strptime(x['data_hora'], "%d/%m/%Y %H:%M:%S"), reverse=True)
        except Exception:
            pass

        return render_template("admin_historico.html", historico=historico_view)
    except Exception as e:
        print(f"[ADMIN] Erro em /admin/historico-detalhado: {e}")
        return redirect(url_for('admin_dashboard'))

@app.route("/admin/setup")
@middleware_admin
def admin_setup():
    try:
        import sys
        # Tentar carregar a base para obter métricas
        df_base = None
        try:
            df_base = carregar_base_unificada()
        except Exception as e:
            print(f"[ADMIN] Falha ao carregar base na tela de setup: {e}")

        total_registros = int(len(df_base)) if df_base is not None else 0
        colunas_planilha = list(df_base.columns) if df_base is not None else []

        arquivo_excel = os.path.abspath('Base_Unificada.xlsx') if os.path.exists('Base_Unificada.xlsx') else ''
        base_unificada = os.path.abspath(os.path.join('data', 'Base_Unificada.csv')) if os.path.exists(os.path.join('data', 'Base_Unificada.csv')) else ''

        info_sistema = {
            'versao_python': sys.version,
            'usuarios_sistema': len(USUARIOS_SISTEMA),
            'logs_em_memoria': len(LOGS_SISTEMA),
            'historico_pesquisas': len(HISTORICO_PESQUISAS),
            'arquivo_excel': arquivo_excel,
            'base_unificada': base_unificada,
            'total_registros': total_registros,
            'colunas_planilha': colunas_planilha,
        }

        ip_cliente = obter_ip_cliente()
        log_acesso(session.get('usuario_logado', 'DESCONHECIDO'), 'ADMIN_ACESSO_SETUP', ip_cliente, 'Acesso às configurações')

        # Enriquecer admin_config com status de token do Melhor Envio
        ADMIN_CONFIG['melhor_envio_token_ok'] = bool(os.getenv('MELHOR_ENVIO_TOKEN'))

        try:
            return render_template("admin_setup.html", info_sistema=info_sistema, admin_config=ADMIN_CONFIG, _ULTIMO_TESTE_DB=_ULTIMO_TESTE_DB)
        except UnicodeDecodeError as e:
            # Fallback em caso de problema de encoding do template
            print(f"[ADMIN] Template admin_setup.html com encoding inválido: {e}")
            html = f"""
            <html><head><meta charset='utf-8'><title>Configurações - Fallback</title></head>
            <body style='font-family:Segoe UI, Arial, sans-serif; padding:20px;'>
            <h2>Configurações do Sistema (Fallback)</h2>
            <p>O template admin_setup.html apresentou problema de codificação. Exibindo visão simplificada.</p>
            <h3>Status</h3>
            <ul>
                <li>Python: {info_sistema.get('versao_python','')}</li>
                <li>Usuários: {info_sistema.get('usuarios_sistema',0)}</li>
                <li>Logs: {info_sistema.get('logs_em_memoria',0)}</li>
                <li>Histórico: {info_sistema.get('historico_pesquisas',0)}</li>
                <li>Registros base: {info_sistema.get('total_registros',0)}</li>
            </ul>
            <h3>Preferências</h3>
            <ul>
                <li>Usar DB: {ADMIN_CONFIG.get('use_db', True)}</li>
                <li>TTL rotas: {ADMIN_CONFIG.get('cache_rotas_ttl', 900)}s</li>
                <li>TTL base: {ADMIN_CONFIG.get('cache_base_ttl', 300)}s</li>
                <li>Logs verbosos: {ADMIN_CONFIG.get('verbose_logs', False)}</li>
            </ul>
            <p><a href='/admin'>Voltar</a></p>
            </body></html>
            """
            return html
    except Exception as e:
        print(f"[ADMIN] Erro em /admin/setup: {e}")
        return redirect(url_for('admin_dashboard'))

@app.route("/admin/setup/salvar", methods=["POST"])
@middleware_admin
def admin_setup_salvar():
    try:
        global _CACHE_ROTAS_TTL, _CACHE_VALIDADE_BASE
        use_db = request.form.get('use_db') == 'on'
        cache_rotas_ttl = int(request.form.get('cache_rotas_ttl') or _CACHE_ROTAS_TTL)
        cache_base_ttl = int(request.form.get('cache_base_ttl') or _CACHE_VALIDADE_BASE)
        verbose_logs = request.form.get('verbose_logs') == 'on'
        # Permitir salvar credenciais da Melhor Envio (opcional durante a sessão)
        client_id = request.form.get('melhor_envio_client_id')
        client_secret = request.form.get('melhor_envio_client_secret')

        ADMIN_CONFIG['use_db'] = use_db
        ADMIN_CONFIG['cache_rotas_ttl'] = cache_rotas_ttl
        ADMIN_CONFIG['cache_base_ttl'] = cache_base_ttl
        ADMIN_CONFIG['verbose_logs'] = verbose_logs
        if client_id:
            globals()['MELHOR_ENVIO_CLIENT_ID'] = client_id
        if client_secret:
            globals()['MELHOR_ENVIO_CLIENT_SECRET'] = client_secret
        # Limpar cache de token para forçar novo
        if '_MELHOR_ENVIO_TOKEN_CACHE' in globals():
            globals()['_MELHOR_ENVIO_TOKEN_CACHE'] = {'token': None, 'exp_ts': 0}

        _CACHE_ROTAS_TTL = cache_rotas_ttl
        _CACHE_VALIDADE_BASE = cache_base_ttl

        flash('Configurações salvas com sucesso.', 'success')
    except Exception as e:
        print(f"[ADMIN] Erro ao salvar configurações: {e}")
        flash('Erro ao salvar configurações.', 'error')
    return redirect(url_for('admin_setup'))

@app.route("/admin/setup/testar-db", methods=["POST"])
@middleware_admin
def admin_setup_testar_db():
    try:
        diag = diagnosticar_conexao_db()
        if diag.get('ok'):
            flash(f"Conexão OK. Registros na tabela: {diag.get('rows',0):,}", 'success')
        else:
            flash(f"Falha na conexão com o DB: {diag.get('error','desconhecido')}", 'error')
    except Exception as e:
        print(f"[ADMIN] Erro ao testar DB: {e}")
        flash('Erro inesperado ao testar DB.', 'error')
    return redirect(url_for('admin_setup'))

@app.route("/admin/setup/testar-melhor-envio", methods=["POST"])
@middleware_admin
def admin_setup_testar_melhor_envio():
    try:
        token = obter_token_melhor_envio()
        if not token:
            flash('Não foi possível obter token da Melhor Envio. Configure MELHOR_ENVIO_TOKEN ou CLIENT_ID/SECRET.', 'error')
            return redirect(url_for('admin_setup'))
        headers = _melhor_envio_headers()
        url = f"{MELHOR_ENVIO_API_BASE.rstrip('/')}/v2/companies"
        resp = requests.get(url, headers=headers, timeout=20)
        try:
            data = resp.json()
        except Exception:
            data = []
        if resp.status_code >= 400:
            detalhe = data if isinstance(data, dict) else {'status': resp.status_code}
            flash(f"Falha ao consultar transportadoras: {detalhe}", 'error')
        else:
            total = len(data or [])
            flash(f"Autenticação OK. Transportadoras retornadas: {total}", 'success')
    except Exception as e:
        print(f"[ADMIN] Erro ao testar Melhor Envio: {e}")
        flash('Erro inesperado ao testar Melhor Envio.', 'error')
    return redirect(url_for('admin_setup'))

@app.route("/admin/setup/recarregar-base", methods=["POST"])
@middleware_admin
def admin_setup_recarregar_base():
    try:
        global _BASE_UNIFICADA_CACHE, _ULTIMO_CARREGAMENTO_BASE, _BASE_INDICES_PRONTOS
        _BASE_UNIFICADA_CACHE = None
        _ULTIMO_CARREGAMENTO_BASE = 0
        _BASE_INDICES_PRONTOS = False
        df = carregar_base_unificada()
        if df is not None:
            flash(f"Base recarregada: {len(df):,} registros.", 'success')
        else:
            flash("Falha ao recarregar a base.", 'error')
    except Exception as e:
        print(f"[ADMIN] Erro ao recarregar base: {e}")
        flash('Erro inesperado ao recarregar base.', 'error')
    return redirect(url_for('admin_setup'))

@app.route("/admin/limpar-logs", methods=["POST"])
@middleware_admin
def admin_limpar_logs():
    try:
        LOGS_SISTEMA.clear()
        flash('Logs limpos com sucesso.', 'success')
    except Exception as e:
        print(f"[ADMIN] Erro ao limpar logs: {e}")
        flash('Erro ao limpar logs.', 'error')
    return redirect(url_for('admin_logs'))

@app.route("/admin/exportar-logs")
@middleware_admin
def admin_exportar_logs():
    try:
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['data_hora', 'usuario', 'acao', 'ip', 'detalhes', 'user_agent'])
        for l in LOGS_SISTEMA:
            writer.writerow([
                l.get('data_hora', ''),
                l.get('usuario', ''),
                l.get('acao', ''),
                l.get('ip', ''),
                l.get('detalhes', ''),
                l.get('user_agent', ''),
            ])
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue().encode('utf-8')), as_attachment=True, download_name='logs.csv', mimetype='text/csv')
    except Exception as e:
        print(f"[ADMIN] Erro ao exportar logs: {e}")
        return redirect(url_for('admin_logs'))
@app.route("/api/bases-disponiveis")
def api_bases_disponiveis():
    """API endpoint para fornecer lista de bases disponíveis para frete fracionado"""
    try:
        # Mapeamento de códigos de base para nomes de cidades
        bases_disponiveis = [
            {"codigo": "SAO", "nome": "São Paulo", "regiao": "Sudeste"},
            {"codigo": "ITJ", "nome": "Itajaí", "regiao": "Sul"},
            {"codigo": "SSZ", "nome": "Salvador", "regiao": "Nordeste"},
            {"codigo": "SJP", "nome": "São José dos Pinhais", "regiao": "Sul"},
            {"codigo": "SPO", "nome": "São Paulo", "regiao": "Sudeste"},
            {"codigo": "RAO", "nome": "Ribeirão Preto", "regiao": "Sudeste"},
            {"codigo": "CPQ", "nome": "Campinas", "regiao": "Sudeste"},
            {"codigo": "SJK", "nome": "São José dos Campos", "regiao": "Sudeste"},
            {"codigo": "RIO", "nome": "Rio de Janeiro", "regiao": "Sudeste"},
            {"codigo": "BHZ", "nome": "Belo Horizonte", "regiao": "Sudeste"},
            {"codigo": "VIX", "nome": "Vitória", "regiao": "Sudeste"},
            {"codigo": "CWB", "nome": "Curitiba", "regiao": "Sul"},
            {"codigo": "POA", "nome": "Porto Alegre", "regiao": "Sul"},
            {"codigo": "BSB", "nome": "Brasília", "regiao": "Centro-Oeste"},
            {"codigo": "GYN", "nome": "Goiânia", "regiao": "Centro-Oeste"},
            {"codigo": "CGB", "nome": "Cuiabá", "regiao": "Centro-Oeste"},
            {"codigo": "CGR", "nome": "Campo Grande", "regiao": "Centro-Oeste"},
            {"codigo": "FOR", "nome": "Fortaleza", "regiao": "Nordeste"},
            {"codigo": "REC", "nome": "Recife", "regiao": "Nordeste"},
            {"codigo": "SSA", "nome": "Salvador", "regiao": "Nordeste"},
            {"codigo": "NAT", "nome": "Natal", "regiao": "Nordeste"},
            {"codigo": "JPA", "nome": "João Pessoa", "regiao": "Nordeste"},
            {"codigo": "MCZ", "nome": "Maceió", "regiao": "Nordeste"},
            {"codigo": "AJU", "nome": "Aracaju", "regiao": "Nordeste"},
            {"codigo": "SLZ", "nome": "São Luís", "regiao": "Nordeste"},
            {"codigo": "TER", "nome": "Teresina", "regiao": "Nordeste"},
            {"codigo": "MAO", "nome": "Manaus", "regiao": "Norte"},
            {"codigo": "MAB", "nome": "Marabá", "regiao": "Norte"},
            {"codigo": "PMW", "nome": "Palmas", "regiao": "Norte"},
            {"codigo": "FILIAL", "nome": "Filial Local", "regiao": "Local"}
        ]
        
        return jsonify({
            "bases": bases_disponiveis,
            "total": len(bases_disponiveis)
        })
        
    except Exception as e:
        print(f"[API] Erro ao carregar bases disponíveis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": f"Erro interno: {str(e)}",
            "bases": []
        })
@app.route("/api/base-agentes")
def api_base_agentes():
    """API endpoint para fornecer dados da Base Unificada para o mapa de agentes"""
    try:
        # Carregar base unificada
        df_base = carregar_base_unificada()
        if df_base is None:
            return jsonify({
                "error": "Base de dados não disponível",
                "agentes": []
            })
        
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

@app.route("/api/melhor-envio/transportadoras", methods=["GET"])
@middleware_auth
def melhor_envio_transportadoras():
    """Lista transportadoras disponíveis via API do Melhor Envio."""
    try:
        headers = _melhor_envio_headers()
        if headers is None:
            return jsonify({
                "error": "Token do Melhor Envio não configurado. Defina a variável de ambiente MELHOR_ENVIO_TOKEN.",
                "codigo": "TOKEN_NAO_CONFIGURADO"
            }), 400

        # Endpoint público de empresas (transportadoras)
        # Documentação: app.melhorenvio.com.br (requere token com escopos de leitura)
        url = f"{MELHOR_ENVIO_API_BASE.rstrip('/')}/v2/companies"
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        # Normalizar campos essenciais
        transportadoras = []
        for item in (data or []):
            transportadoras.append({
                "id": item.get("id"),
                "nome": item.get("name"),
                "document": item.get("document"),
                "status": item.get("status"),
                "picture": item.get("picture"),
                "alias": item.get("alias"),
            })

        return jsonify({
            "total": len(transportadoras),
            "transportadoras": transportadoras
        })
    except requests.exceptions.HTTPError as e:
        # Se for 401/403, limpar cache de token e tentar uma vez
        status = resp.status_code if 'resp' in locals() else 0
        if status in (401, 403):
            if '_MELHOR_ENVIO_TOKEN_CACHE' in globals():
                globals()['_MELHOR_ENVIO_TOKEN_CACHE'] = {'token': None, 'exp_ts': 0}
            headers = _melhor_envio_headers()
            if headers is not None:
                try:
                    resp2 = requests.get(url, headers=headers, timeout=20)
                    resp2.raise_for_status()
                    data2 = resp2.json()
                    transportadoras = [{
                        "id": item.get("id"),
                        "nome": item.get("name"),
                        "document": item.get("document"),
                        "status": item.get("status"),
                        "picture": item.get("picture"),
                        "alias": item.get("alias"),
                    } for item in (data2 or [])]
                    return jsonify({"total": len(transportadoras), "transportadoras": transportadoras})
                except Exception:
                    pass
        try:
            payload = resp.json()
        except Exception:
            payload = {"message": str(e)}
        return jsonify({"error": "Falha na API do Melhor Envio", "detalhes": payload}), resp.status_code if 'resp' in locals() else 502
    except requests.exceptions.Timeout:
        return jsonify({"error": "Timeout ao consultar a API do Melhor Envio"}), 504
    except Exception as e:
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500
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
        if not coord_origem or not coord_destino:
            return jsonify({"error": "Não foi possível geocodificar origem ou destino"})
        rota_info = calcular_distancia_osrm(coord_origem, coord_destino) or \
                    calcular_distancia_openroute(coord_origem, coord_destino) or \
                    calcular_distancia_reta(coord_origem, coord_destino)
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
        
        if resultado_aereo and isinstance(resultado_aereo, list) and len(resultado_aereo) > 0:
            # Usar dados da base unificada
            for opcao in resultado_aereo:
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

@app.route("/calcular_frete_fracionado_multiplas_bases", methods=["POST"])
@middleware_auth
def calcular_frete_fracionado_multiplas_bases_route():
    """Rota para calcular frete fracionado com múltiplas bases intermediárias"""
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
        bases_intermediarias = data.get("bases_intermediarias", [])

        log_acesso(usuario, 'CALCULO_FRACIONADO_MULTIPLAS_BASES', ip_cliente, 
                  f"Cálculo Fracionado Multiplas Bases: {municipio_origem}/{uf_origem} -> {bases_intermediarias} -> {municipio_destino}/{uf_destino}, Peso: {peso}kg, Cubagem: {cubagem}m³")

        if not all([uf_origem, municipio_origem, uf_destino, municipio_destino]):
            return jsonify({"error": "Origem e destino são obrigatórios"})

        if not bases_intermediarias or len(bases_intermediarias) != 1:
            return jsonify({"error": "É necessário fornecer exatamente 1 base intermediária para compor a viagem (ex: SAO)"})

        # Calcular frete fracionado com múltiplas bases
        resultado = calcular_frete_fracionado_multiplas_bases(
            municipio_origem, uf_origem,
            municipio_destino, uf_destino,
            peso, cubagem, valor_nf, bases_intermediarias
        )
        
        if not resultado:
            return jsonify({
                "error": "Erro ao calcular frete fracionado com múltiplas bases",
                "tipo": "Fracionado Multiplas Bases"
            })
        
        if resultado.get('error'):
            return jsonify({
                "error": resultado.get('error'),
                "tipo": "Fracionado Multiplas Bases",
                "sem_opcoes": resultado.get('sem_opcoes', False)
            })
        
        # Preparar resposta
        resposta = {
            "tipo": "Fracionado Multiplas Bases",
            "origem": resultado['origem'],
            "destino": resultado['destino'],
            "bases_intermediarias": resultado['bases_intermediarias'],
            "rota_completa": resultado['rota_completa'],
            "trechos": resultado['trechos'],
            "custo_total": resultado['custo_total'],
            "prazo_total": resultado['prazo_total'],
            "fornecedores_utilizados": resultado['fornecedores_utilizados'],
            "peso_cubado": resultado['peso_cubado'],
            "gris": resultado['gris'],
            "seguro": resultado['seguro'],
            "tempo_calculo": resultado['tempo_calculo']
        }
        
        # Armazenar resultado para exportação
        ultimoResultadoFracionado = resposta
        
        # Registrar no histórico
        HISTORICO_PESQUISAS.append(resposta)
        if len(HISTORICO_PESQUISAS) > 15:
            HISTORICO_PESQUISAS.pop(0)
        
        # Sanitizar JSON
        resposta_sanitizada = sanitizar_json(resposta)
        return jsonify(resposta_sanitizada)
    
    except Exception as e:
        log_acesso(usuario, 'ERRO_CALCULO_FRACIONADO_MULTIPLAS_BASES', ip_cliente, f"Erro: {str(e)}")
        print(f"Erro ao calcular frete fracionado com múltiplas bases: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erro ao calcular frete fracionado com múltiplas bases: {str(e)}"})

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

        # Cache por chave de rota
        chave_cache = (
            f"{normalizar_cidade_nome(municipio_origem)}|{normalizar_uf(uf_origem)}|"
            f"{normalizar_cidade_nome(municipio_destino)}|{normalizar_uf(uf_destino)}|{float(peso)}|{float(cubagem or 0)}|{float(valor_nf or 0)}"
        )
        agora = time.time()
        item_cache = _CACHE_ROTAS.get(chave_cache)
        if item_cache and (agora - item_cache['ts'] < _CACHE_ROTAS_TTL):
            resultado_fracionado = item_cache['resultado']
        else:
        # Buscar dados fracionados da Base Unificada
            resultado_fracionado = calcular_frete_fracionado_base_unificada(
            municipio_origem, uf_origem,
            municipio_destino, uf_destino,
            peso, cubagem, valor_nf
        )
            if resultado_fracionado:
                _CACHE_ROTAS[chave_cache] = { 'ts': agora, 'resultado': resultado_fracionado }
        
        # Verificar se há avisos especiais (sem agente de entrega)
        if resultado_fracionado and resultado_fracionado.get('tipo_aviso') == 'SEM_AGENTE_ENTREGA':
            return jsonify({
                "error": f"⚠️ {resultado_fracionado.get('aviso')}",
                "ranking_fracionado": None,
                "tipo": "Fracionado",
                "aviso_tipo": "SEM_AGENTE_ENTREGA",
                "detalhes": "Não há agentes de entrega disponíveis na cidade de destino. Verifique se há cobertura na região."
            })
        
        if not resultado_fracionado:
            return jsonify({
                "error": "Erro ao calcular frete fracionado",
                "ranking_fracionado": None,
                "tipo": "Fracionado"
            })
        
        # Verificar se há mensagem específica quando não há opções
        if resultado_fracionado.get('sem_opcoes'):
            return jsonify({
                "error": resultado_fracionado.get('mensagem', 'Não há nenhuma opção para a rota solicitada'),
                "ranking_fracionado": None,
                "tipo": "Fracionado",
                "sem_opcoes": True
            })
        
        if not resultado_fracionado.get('opcoes'):
            return jsonify({
                "error": "Não há nenhuma opção para a rota solicitada",
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
            "distancia": 0,  # Sem cálculo de distância
            "duracao": 0,  # Sem estimativa
            "custos": custos_fracionado,  # Para compatibilidade
            "rota_pontos": [],  # Sem coordenadas
            "analise": {
                "id_historico": ranking_fracionado['id_calculo'],
                "tipo": "Fracionado",
                "origem": ranking_fracionado['origem'],
                "destino": ranking_fracionado['destino'],
                "distancia": 0,  # Sem cálculo de distância
                "tempo_estimado": ranking_fracionado['tempo_estimado'],
                "consumo_estimado": 0,  # Sem estimativa
                "emissao_co2": 0,  # Sem cálculo
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
                resumo = (
                    cotacao.get('resumo')
                    or cotacao.get('tipo_servico')
                    or cotacao.get('descricao')
                    or 'N/A'
                )
                total = cotacao.get('total', cotacao.get('custo_total', 0))
                prazo = cotacao.get('prazo_total', cotacao.get('prazo', 'N/A'))

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
                    detalhes_expandidos = rota.get('detalhes_expandidos', {}) or {}
                    dados_agentes = detalhes_expandidos.get('dados_agentes', {}) or {}
                    custos_detalhados = detalhes_expandidos.get('custos_detalhados', {}) or {}

                    agente_coleta = (
                        rota.get('agente_coleta')
                        or dados_agentes.get('agente_coleta', {})
                        or {}
                    )
                    transferencia = (
                        rota.get('transferencia')
                        or dados_agentes.get('transferencia', {})
                        or {}
                    )
                    agente_entrega = (
                        rota.get('agente_entrega')
                        or dados_agentes.get('agente_entrega', {})
                        or {}
                    )

                    dados_rota = dados_basicos.copy()
                    dados_rota.update({
                        "Posição Ranking": i,
                        "Rota Resumo": rota.get('resumo') or rota.get('tipo_servico') or rota.get('descricao', 'N/A'),
                        "Custo Total (R$)": rota.get('total', rota.get('custo_total', 0)),
                        "Prazo Total (dias)": rota.get('prazo_total', rota.get('prazo', 'N/A')),

                        # Agente de Coleta
                        "Agente Coleta": agente_coleta.get('fornecedor', 'N/A'),
                        "Coleta Origem": agente_coleta.get('origem', agente_coleta.get('base_origem', 'N/A')),
                        "Coleta Base Destino": agente_coleta.get('base_destino', agente_coleta.get('destino', 'N/A')),
                        "Coleta Custo (R$)": agente_coleta.get('custo', 0),
                        "Coleta Prazo (dias)": agente_coleta.get('prazo', 'N/A'),
                        "Coleta Peso Máximo (kg)": agente_coleta.get('peso_maximo', 'N/A'),

                        # Transferência
                        "Transferência Fornecedor": transferencia.get('fornecedor', 'N/A'),
                        "Transferência Origem": transferencia.get('origem', transferencia.get('base_origem', 'N/A')),
                        "Transferência Destino": transferencia.get('destino', transferencia.get('base_destino', 'N/A')),
                        "Transferência Custo (R$)": transferencia.get('custo', custos_detalhados.get('custo_base_frete', 0)),
                        "Transferência Pedágio (R$)": transferencia.get('pedagio', custos_detalhados.get('pedagio', 0)),
                        "Transferência GRIS (R$)": transferencia.get('gris', custos_detalhados.get('gris', 0)),
                        "Transferência Prazo (dias)": transferencia.get('prazo', 'N/A'),

                        # Agente de Entrega
                        "Agente Entrega": agente_entrega.get('fornecedor', 'N/A'),
                        "Entrega Base Origem": agente_entrega.get('base_origem', agente_entrega.get('origem', 'N/A')),
                        "Entrega Destino": agente_entrega.get('destino', agente_entrega.get('base_destino', 'N/A')),
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


def extrair_detalhamento_custos(opcao, peso_cubado, valor_nf):
    """
    Extrai detalhamento completo de custos de uma opção
    """
    try:
        # Validar entrada
        if not isinstance(opcao, dict):
            print(f"[CUSTOS] ⚠️ Opção não é um dicionário: {type(opcao)}")
            return {
                'custo_base_frete': 0,
                'pedagio': 0,
                'gris': 0,
                'seguro': 0,
                'tda': 0,
                'outros': 0,
                'total_custos': 0
            }
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
                if not agente_data or not isinstance(agente_data, dict):
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
                if not agente_data or not isinstance(agente_data, dict):
                    return 0
                return (
                    agente_data.get('pedagio', 0) or
                    agente_data.get('toll', 0) or
                    0
                )
            
            def extrair_gris_agente(agente_data):
                if not agente_data or not isinstance(agente_data, dict):
                    return 0
                return (
                    agente_data.get('gris', 0) or
                    agente_data.get('gris_value', 0) or
                    0
                )
            
            def extrair_seguro_agente(agente_data):
                if not agente_data or not isinstance(agente_data, dict):
                    return 0
                return (
                    agente_data.get('seguro', 0) or
                    agente_data.get('insurance', 0) or
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
                elif tipo_rota == 'transferencia_entrega' or tipo_rota == 'transferencia_direta_entrega' or tipo_rota == 'cliente_entrega_transferencia_agente_entrega' or tipo_rota == 'PARCIAL_SEM_COLETA':
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)