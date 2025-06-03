#!/usr/bin/env python
# -*- coding: utf-8 -*-
try:
    import pandas as pd
    import datetime
    import math
    import requests
    import polyline
    from fpdf import FPDF
    from flask import Flask, render_template_string, request, jsonify, send_file
    import io
    import os
    import re
    import unicodedata
    import json
    import time
    from dotenv import load_dotenv
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    from functools import lru_cache
    import sqlite3
    from markupsafe import escape
except ImportError as e:
    print(f"Erro: Uma dependência está faltando. Execute 'pip install pandas requests fpdf flask python-dotenv tenacity markupsafe'.\nDetalhes: {e}")
    exit(1)

# Carregar variáveis de ambiente
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)

# Configurações
BASE_DIR = r"C:\Users\Usuário\OneDrive\Desktop\SQL data\Chico automate\Chico Automate Project V2"
EXCEL_FILE = os.getenv('EXCEL_FILE', os.path.join(BASE_DIR, 'corrected_data.xlsx'))
HISTORY_DB = os.getenv('HISTORY_DB', os.path.join(BASE_DIR, 'historico.db'))
HTML_TEMPLATE_PATH = os.getenv('HTML_TEMPLATE_PATH', os.path.join(BASE_DIR, 'template.html'))
NOMINATIM_URL = os.getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org/search')
OSRM_URL = os.getenv('OSRM_URL', 'http://router.project-osrm.org/route/v1/driving')
IBGE_URL = os.getenv('IBGE_URL', 'https://servicodados.ibge.gov.br/api/v1/localidades')

# Estados fallback
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

# Tabela de custos para frete dedicado
TABELA_CUSTOS_DEDICADO = {
    "0-20": {"VAN": 250, "3/4": 350, "TOCO": 450, "TRUCK": 550, "CARRETA": 1000},
    "20-50": {"VAN": 350, "3/4": 450, "TOCO": 550, "TRUCK": 700, "CARRETA": 1500},
    "50-100": {"VAN": 600, "3/4": 900, "TOCO": 1200, "TRUCK": 1500, "CARRETA": 2100},
    "100-150": {"VAN": 800, "3/4": 1100, "TOCO": 1500, "TRUCK": 1800, "CARRETA": 2600},
    "150-200": {"VAN": 1000, "3/4": 1500, "TOCO": 1800, "TRUCK": 2100, "CARRETA": 3000},
    "200-250": {"VAN": 1300, "3/4": 1800, "TOCO": 2100, "TRUCK": 2500, "CARRETA": 3300},
    "250-300": {"VAN": 1500, "3/4": 2100, "TOCO": 2500, "TRUCK": 2800, "CARRETA": 3800},
    "300-400": {"VAN": 1800, "3/4": 2500, "TOCO": 2800, "TRUCK": 3300, "CARRETA": 4300},
    "400-600": {"VAN": 2100, "3/4": 2900, "TOCO": 3500, "TRUCK": 3800, "CARRETA": 4800},
    "600-800": {"VAN": 2500, "3/4": 3300, "TOCO": 4000, "TRUCK": 4500, "CARRETA": 5500},
    "800-1000": {"VAN": 2900, "3/4": 3700, "TOCO": 4500, "TRUCK": 5200, "CARRETA": 6200},
    "1000-1500": {"VAN": 3500, "3/4": 4500, "TOCO": 5500, "TRUCK": 6500, "CARRETA": 8000},
    "1500-2000": {"VAN": 4500, "3/4": 5800, "TOCO": 7000, "TRUCK": 8500, "CARRETA": 10500},
    "2000-2500": {"VAN": 5500, "3/4": 7100, "TOCO": 8500, "TRUCK": 10500, "CARRETA": 13000},
    "2500-3000": {"VAN": 6500, "3/4": 8400, "TOCO": 10000, "TRUCK": 12500, "CARRETA": 15500},
    "3000-3500": {"VAN": 7500, "3/4": 9700, "TOCO": 11500, "TRUCK": 14500, "CARRETA": 18000},
    "3500-4000": {"VAN": 8500, "3/4": 11000, "TOCO": 13000, "TRUCK": 16500, "CARRETA": 20500},
    "4000-4500": {"VAN": 9500, "3/4": 12300, "TOCO": 14500, "TRUCK": 18500, "CARRETA": 23000},
    "4500-6000": {"VAN": 11000, "3/4": 14000, "TOCO": 17000, "TRUCK": 21000, "CARRETA": 27000},
}

# Funções auxiliares
@lru_cache(maxsize=1000)
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), 
       retry=retry_if_exception_type(requests.exceptions.RequestException))
def geocode(municipio, uf):
    if municipio is None or uf is None:
        return None
    municipio_norm = normalizar_cidade(municipio)
    url = NOMINATIM_URL
    params = {"q": f"{municipio_norm}, {uf}, Brasil", "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "PortoExTransportCalculator/1.1"}
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    if data and uf.upper() in data[0].get('display_name', '').upper():
        return (float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", ""))
    return None

@lru_cache(maxsize=1000)
def calcular_distancia_osrm(origem, destino):
    if not origem or not destino:
        return None
    url = OSRM_URL + f"/{origem[1]},{origem[0]};{destino[1]},{destino[0]}"
    response = requests.get(url, params={"overview": "full"}, timeout=15)
    response.raise_for_status()
    data = response.json()
    if data.get("code") == "Ok" and data.get("routes"):
        route = data["routes"][0]
        return {"distance": route["distance"] / 1000, "duration": route["duration"] / 60, 
                "route_points": polyline.decode(route.get("geometry", "")), "provider": "OSRM"}
    return None

def calcular_distancia_reta(origem, destino):
    if not origem or not destino:
        return None
    lat1, lon1 = origem[0], origem[1]
    lat2, lon2 = destino[0], destino[1]
    R = 6371
    phi1, phi2 = map(math.radians, [lat1, lat2])
    dphi, dlambda = map(math.radians, [lat2 - lat1, lon2 - lon1])
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    duration = (distance / 80) * 60
    return {"distance": distance, "duration": duration, "route_points": [[lat1, lon1], [lat2, lon2]], "provider": "Linha Reta"}

def determinar_faixa(distancia):
    faixas = [(0, 20), (20, 50), (50, 100), (100, 150), (150, 200), (200, 250), (250, 300), 
              (300, 400), (400, 600), (600, 800), (800, 1000), (1000, 1500), (1500, 2000), 
              (2000, 2500), (2500, 3000), (3000, 3500), (3500, 4000), (4000, 4500), (4500, 6000)]
    for min_val, max_val in faixas:
        if min_val < distancia <= max_val:
            return f"{min_val}-{max_val}"
    return "6000+" if distancia > 6000 else "0-20" if distancia <= 0 else None

def normalizar_cidade(cidade):
    if cidade is None:
        return ""
    if not isinstance(cidade, str):
        cidade = str(cidade)
    cidade = ''.join(c for c in unicodedata.normalize('NFD', cidade) if unicodedata.category(c) != 'Mn')
    cidade = re.sub(r'[^a-zA-Z0-9\s]', '', cidade).strip().upper()
    return re.sub(r'\s+', ' ', cidade)

def calcular_valor_fracionado(peso, cubagem, transportadora_data):
    peso_cubado = max(float(peso), float(cubagem) * 300)
    if peso_cubado > transportadora_data["peso_maximo"]:
        return None
    custo_base = transportadora_data["10kg"] if peso_cubado <= 10 else transportadora_data["10kg"] + (peso_cubado - 10) * transportadora_data["excedente"]
    custo_gris = custo_base * transportadora_data["gris"] if isinstance(transportadora_data["gris"], (int, float)) else 0.0
    return round(custo_base + custo_gris, 2)

def gerar_analise_trajeto(origem_info, destino_info, rota_info, tipo_frete, detalhes_calculo):
    search_id = int(time.time() * 1000)
    analise = {
        "search_id": search_id, "tipo_frete": tipo_frete, "data_hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "origem_uf": detalhes_calculo.get("uf_origem", "N/A"), "origem_municipio": detalhes_calculo.get("municipio_origem", "N/A"),
        "origem_geocode": origem_info[2] if origem_info and len(origem_info) > 2 else "Origem Desconhecida",
        "destino_uf": detalhes_calculo.get("uf_destino", "N/A"), "destino_municipio": detalhes_calculo.get("municipio_destino", "N/A"),
        "destino_geocode": destino_info[2] if destino_info and len(destino_info) > 2 else "Destino Desconhecido",
        "peso_kg": detalhes_calculo.get("peso", 0), "cubagem_m3": detalhes_calculo.get("cubagem", 0),
        "distancia_km": round(rota_info["distance"], 2) if rota_info else None,
        "duracao_min": round(rota_info["duration"], 2) if rota_info else None,
        "rota_provider": rota_info["provider"] if rota_info else None,
        "rota_pontos": rota_info["route_points"] if rota_info else [],
        "resultado": detalhes_calculo.get("custos_dedicado", {}) if tipo_frete == "dedicado" else detalhes_calculo.get("ranking_fracionado", [])
    }
    save_history(analise)
    return analise

def get_municipios_uf(uf):
    try:
        response = requests.get(f"{IBGE_URL}/estados/{uf}/municipios", timeout=10)
        response.raise_for_status()
        data = response.json()
        return {normalizar_cidade(m["nome"]): m["nome"].title() for m in data}
    except Exception:
        if uf in TABELA_CUSTOS:
            return {cid: cid for cid in TABELA_CUSTOS[uf].keys()}
        return {}

# Banco de dados
def init_db():
    conn = sqlite3.connect(HISTORY_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS historico
                 (search_id INTEGER PRIMARY KEY, tipo_frete TEXT, data_hora TEXT,
                  origem_uf TEXT, origem_municipio TEXT, destino_uf TEXT, destino_municipio TEXT,
                  peso_kg REAL, cubagem_m3 REAL, distancia_km REAL, duracao_min REAL,
                  rota_provider TEXT, resultado TEXT)''')
    conn.commit()
    conn.close()

def save_history(analise):
    conn = sqlite3.connect(HISTORY_DB)
    c = conn.cursor()
    c.execute('''INSERT INTO historico (search_id, tipo_frete, data_hora, origem_uf, origem_municipio,
                 destino_uf, destino_municipio, peso_kg, cubagem_m3, distancia_km, duracao_min,
                 rota_provider, resultado)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (analise['search_id'], analise['tipo_frete'], analise['data_hora'],
                  analise['origem_uf'], analise['origem_municipio'],
                  analise['destino_uf'], analise['destino_municipio'],
                  analise['peso_kg'], analise['cubagem_m3'],
                  analise['distancia_km'], analise['duracao_min'],
                  analise['rota_provider'], json.dumps(analise['resultado'])))
    c.execute('DELETE FROM historico WHERE search_id NOT IN (SELECT search_id FROM historico ORDER BY search_id DESC LIMIT 100)')
    conn.commit()
    conn.close()

def load_history():
    conn = sqlite3.connect(HISTORY_DB)
    c = conn.cursor()
    c.execute('SELECT * FROM historico ORDER BY search_id DESC')
    rows = c.fetchall()
    conn.close()
    return [{
        'search_id': row[0], 'tipo_frete': row[1], 'data_hora': row[2],
        'origem_uf': row[3], 'origem_municipio': row[4],
        'destino_uf': row[5], 'destino_municipio': row[6],
        'peso_kg': row[7], 'cubagem_m3': row[8],
        'distancia_km': row[9], 'duracao_min': row[10],
        'rota_provider': row[11], 'resultado': json.loads(row[12])
    } for row in rows]

# Carregar planilha
required_columns = ["UF Origem", "Cidade Origem", "UF Destino", "Cidade Destino",
                   "Fornecedor", "Valor Mínimo (até 10kg)", "Excedente (por kg adicional)",
                   "Peso Máximo Transportado", "Prazo Econômico", "Prazo Expresso", "Gris", "STATUS"]
TABELA_CUSTOS = {}
try:
    df_cidades = pd.read_excel(EXCEL_FILE)
    missing_cols = [col for col in required_columns if col not in df_cidades.columns]
    if missing_cols:
        raise ValueError(f"Colunas faltantes na planilha: {', '.join(missing_cols)}")
    for _, row in df_cidades[df_cidades["STATUS"].str.upper() == "ATIVO"].iterrows():
        if pd.isna(row["Fornecedor"]) or row["Fornecedor"] == "N/A":
            continue
        uf_origem = str(row["UF Origem"]).strip().upper()
        cidade_origem = normalizar_cidade(row["Cidade Origem"])
        uf_destino = str(row["UF Destino"]).strip().upper()
        cidade_destino = normalizar_cidade(row["Cidade Destino"])
        if not all([uf_origem, cidade_origem, uf_destino, cidade_destino]):
            continue
        TABELA_CUSTOS.setdefault(uf_origem, {}).setdefault(cidade_origem, {}).setdefault(uf_destino, {}).setdefault(cidade_destino, []).append({
            "fornecedor": str(row["Fornecedor"]),
            "10kg": float(row["Valor Mínimo (até 10kg)"]) if pd.notna(row["Valor Mínimo (até 10kg)"]) else 0,
            "excedente": float(row["Excedente (por kg adicional)"]) if pd.notna(row["Excedente (por kg adicional)"]) else 0,
            "peso_maximo": float(row["Peso Máximo Transportado"]) if pd.notna(row["Peso Máximo Transportado"]) else float('inf'),
            "prazo_econ": int(row["Prazo Econômico"]) if pd.notna(row["Prazo Econômico"]) else 99,
            "prazo_expresso": int(row["Prazo Expresso"]) if pd.notna(row["Prazo Expresso"]) else 99,
            "gris": float(row["Gris"]) if pd.notna(row["Gris"]) else 0.0,
            "zona_parceiro": "Interior",
            "nova_zona": "Interior",
            "dfl": "Sim"
        })
except FileNotFoundError:
    print(f"Erro: Arquivo '{EXCEL_FILE}' não encontrado.")
    exit()
except ValueError as e:
    print(f"Erro na estrutura da planilha: {e}")
    exit()
except Exception as e:
    print(f"Erro inesperado ao carregar a planilha: {e}")
    exit()

# Classe PDF
class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 15)
        self.cell(0, 10, "PortoEx - Relatorio de Cotacao", 0, 1, "C")  # Using ASCII for compatibility
        self.set_font("Arial", "", 10)
        self.cell(0, 5, f"Gerado em: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 0, 1, "C")
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", 0, 0, "C")
    
    def chapter_title(self, title):
        self.set_font("Arial", "B", 12)
        self.cell(0, 6, title, 0, 1, "L", True)
        self.ln(4)
    
    def chapter_body(self, body):
        self.set_font("Arial", "", 10)
        self.multi_cell(0, 5, body)
        self.ln()
    
    def print_table(self, header, data):
        if not data:
            self.cell(0, 10, "Nenhum dado disponível.", 0, 1)
            return
        self.set_font("Arial", "B", 9)
        col_widths = [40, 30, 20, 20, 30, 30]  # Adjusted to match the number of columns (6)
        for i, h in enumerate(header):
            self.cell(col_widths[i], 7, h, 1, 0, "C")
        self.ln()
        self.set_font("Arial", "", 8)
        for row in data:
            custo_str = f"R$ {row['custo']:.2f}".replace('.', ',') if isinstance(row.get('custo'), (int, float)) else str(row.get('custo', 'N/A'))
            prazo_str = str(row.get('prazo', 'N/A'))
            gris_str = f"{row['gris']*100:.2f}%".replace('.', ',') if isinstance(row.get('gris'), (int, float)) else str(row.get('gris', 'N/A'))
            peso_max_str = str(row.get('peso_maximo', 'N/A'))
            exced_str = f"R$ {row['excedente']:.2f}".replace('.', ',') if isinstance(row.get('excedente'), (int, float)) else str(row.get('excedente', 'N/A'))
            self.cell(col_widths[0], 6, str(row.get('fornecedor', 'N/A')), 1)
            self.cell(col_widths[1], 6, custo_str, 1, 0, "R")
            self.cell(col_widths[2], 6, prazo_str, 1, 0, "C")
            self.cell(col_widths[3], 6, gris_str, 1, 0, "C")
            self.cell(col_widths[4], 6, peso_max_str, 1, 0, "C")
            self.cell(col_widths[5], 6, exced_str, 1, 0, "R")
            self.ln()

# Carregar template HTML
try:
    with open(HTML_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        HTML_TEMPLATE = f.read()
except FileNotFoundError:
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Cálculo de Frete</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            .loading { display: none; }
            #map { height: 400px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container mt-5">
            <h1 class="mb-4">Cálculo de Frete Fracionado</h1>
            {% if erro %}
            <div class="alert alert-danger">{{ erro | e }}</div>
            {% endif %}
            <form method="post" action="/calcular_frete_fracionado" class="mb-4">
                <div class="row g-3">
                    <div class="col-md-6">
                        <label for="estado_origem" class="form-label">Estado Origem</label>
                        <select id="estado_origem" name="estado_origem" class="form-select" required></select>
                    </div>
                    <div class="col-md-6">
                        <label for="municipio_origem" class="form-label">Município Origem</label>
                        <select id="municipio_origem" name="municipio_origem" class="form-select" required></select>
                    </div>
                    <div class="col-md-6">
                        <label for="estado_destino" class="form-label">Estado Destino</label>
                        <select id="estado_destino" name="estado_destino" class="form-select" required></select>
                    </div>
                    <div class="col-md-6">
                        <label for="municipio_destino" class="form-label">Município Destino</label>
                        <select id="municipio_destino" name="municipio_destino" class="form-select" required></select>
                    </div>
                    <div class="col-md-6">
                        <label for="peso" class="form-label">Peso (kg)</label>
                        <input type="number" id="peso" name="peso" class="form-control" step="0.01" required>
                    </div>
                    <div class="col-md-6">
                        <label for="cubagem" class="form-label">Cubagem (m³)</label>
                        <input type="number" id="cubagem" name="cubagem" class="form-control" step="0.001" required>
                    </div>
                    <div class="col-md-6">
                        <label for="tipo_prazo" class="form-label">Tipo de Prazo</label>
                        <select id="tipo_prazo" name="tipo_prazo" class="form-select">
                            <option value="econ">Econômico</option>
                            <option value="expresso">Expresso</option>
                        </select>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary mt-3">Calcular Frete</button>
            </form>

            {% if resultado %}
            <h2>Resultados da Cotação</h2>
            <div class="card mb-4">
                <div class="card-body">
                    <p><strong>Origem:</strong> {{ resultado.cidades_origem | e }}, {{ resultado.uf_origem | e }}</p>
                    <p><strong>Destino:</strong> {{ resultado.cidades_destino | e }}, {{ resultado.uf_destino | e }}</p>
                    <p><strong>Peso:</strong> {{ resultado.peso | e }} kg | <strong>Cubagem:</strong> {{ resultado.cubagem | e }} m³</p>
                    {% if resultado.distancia %}
                    <p><strong>Distância Estimada:</strong> {{ "%.2f"|format(resultado.distancia) }} km</p>
                    {% endif %}
                    <form method="post" action="/gerar_pdf">
                        <input type="hidden" name="resultado_json" value="{{ resultado | tojson | safe }}">
                        <button type="submit" class="btn btn-success">Gerar PDF</button>
                    </form>
                </div>
            </div>
            <table class="table table-striped">
                <thead>
                    <tr>
                        <th>Fornecedor</th>
                        <th>Custo (R$)</th>
                        <th>Prazo (dias)</th>
                        <th>GRIS (%)</th>
                        <th>Peso Máx (kg)</th>
                        <th>Excedente (R$/kg)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in resultado.ranking %}
                    <tr>
                        <td>{{ item.fornecedor | e }}</td>
                        <td>{{ "%.2f"|format(item.custo) }}</td>
                        <td>{{ item.prazo | e }}</td>
                        <td>{{ "%.2f"|format(item.gris * 100) }}%</td>
                        <td>{{ item.peso_maximo | e }}</td>
                        <td>{{ "%.2f"|format(item.excedente) }}</td>
                    </tr>
                    {% else %}
                    <tr><td colspan="6" class="text-center">Nenhuma transportadora encontrada.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
            {% if resultado.route_points %}
            <div id="map"></div>
            {% endif %}
            {% endif %}

            <h2>Histórico de Pesquisas</h2>
            <div id="history-container" class="list-group">
                <div class="loading">Carregando...</div>
            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script src="https://unpkg.com/leaflet@1.9.3/dist/leaflet.js"></script>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.3/dist/leaflet.css"/>
        <script>
            const estadoOrigemSelect = document.getElementById('estado_origem');
            const municipioOrigemSelect = document.getElementById('municipio_origem');
            const estadoDestinoSelect = document.getElementById('estado_destino');
            const municipioDestinoSelect = document.getElementById('municipio_destino');
            const historyContainer = document.getElementById('history-container');

            function loadEstados(selectElement) {
                fetch('/estados')
                    .then(response => response.json())
                    .then(data => {
                        selectElement.innerHTML = '<option value="">Selecione...</option>';
                        data.forEach(estado => {
                            const option = document.createElement('option');
                            option.value = estado.id;
                            option.textContent = estado.text;
                            selectElement.appendChild(option);
                        });
                    });
            }

            function loadMunicipios(uf, selectElement) {
                fetch(`/municipios/${uf}`)
                    .then(response => response.json())
                    .then(data => {
                        selectElement.innerHTML = '<option value="">Selecione...</option>';
                        data.forEach(municipio => {
                            const option = document.createElement('option');
                            option.value = municipio.id;
                            option.textContent = municipio.text;
                            selectElement.appendChild(option);
                        });
                    });
            }

            function loadHistory() {
                document.querySelector('.loading').style.display = 'block';
                fetch('/historico')
                    .then(response => response.json())
                    .then(data => {
                        historyContainer.innerHTML = '';
                        if (data && data.length > 0) {
                            data.slice().reverse().forEach(item => {
                                const itemDiv = document.createElement('div');
                                itemDiv.className = 'list-group-item';
                                itemDiv.innerHTML = `<strong>ID: ${item.search_id}</strong> - ${item.data_hora} - ${item.tipo_frete}: 
                                    ${item.origem_municipio}/${item.origem_uf} -> ${item.destino_municipio}/${item.destino_uf}
                                    (Peso: ${item.peso_kg}kg, Cubagem: ${item.cubagem_m3}m³)`;
                                historyContainer.appendChild(itemDiv);
                            });
                        } else {
                            historyContainer.innerHTML = '<div class="list-group-item">Nenhuma pesquisa no histórico.</div>';
                        }
                        document.querySelector('.loading').style.display = 'none';
                    })
                    .catch(error => {
                        console.error('Erro ao carregar histórico:', error);
                        historyContainer.innerHTML = '<div class="list-group-item text-danger">Erro ao carregar histórico.</div>';
                        document.querySelector('.loading').style.display = 'none';
                    });
            }

            estadoOrigemSelect.addEventListener('change', () => {
                if (estadoOrigemSelect.value) loadMunicipios(estadoOrigemSelect.value, municipioOrigemSelect);
                else municipioOrigemSelect.innerHTML = '<option value="">Selecione o estado primeiro</option>';
            });
            estadoDestinoSelect.addEventListener('change', () => {
                if (estadoDestinoSelect.value) loadMunicipios(estadoDestinoSelect.value, municipioDestinoSelect);
                else municipioDestinoSelect.innerHTML = '<option value="">Selecione o estado primeiro</option>';
            });

            loadEstados(estadoOrigemSelect);
            loadEstados(estadoDestinoSelect);
            loadHistory();

            {% if resultado and resultado.route_points %}
            var map = L.map('map').setView([0, 0], 4);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            }).addTo(map);
            var routePoints = {{ resultado.route_points | tojson | safe }};
            if (routePoints.length > 0) {
                L.polyline(routePoints, {color: 'blue'}).addTo(map);
                map.fitBounds(L.polyline(routePoints).getBounds());
            }
            {% endif %}
        </script>
    </body>
    </html>
    """

# Endpoints
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/estados')
def estados():
    try:
        response = requests.get(f"{IBGE_URL}/estados", timeout=10)
        response.raise_for_status()
        data = response.json()
        estados_ibge = [{"id": e["sigla"], "text": e["nome"]} for e in sorted(data, key=lambda x: x["nome"])]
        return jsonify(estados_ibge)
    except Exception:
        ufs_disponiveis = list(TABELA_CUSTOS.keys())
        estados_fallback_filtrado = [e for e in ESTADOS_FALLBACK if e['id'] in ufs_disponiveis]
        return jsonify(sorted(estados_fallback_filtrado, key=lambda x: x['text']))

@app.route('/municipios/<uf>')
def municipios(uf):
    municipios_dict = get_municipios_uf(uf)
    municipios_list = [{"id": norm, "text": orig} for norm, orig in municipios_dict.items()]
    return jsonify(sorted(municipios_list, key=lambda x: x['text']))

@app.route('/calcular', methods=['POST'])
def calcular():
    data = request.json
    municipio_origem = data.get("municipio_origem")
    uf_origem = data.get("uf_origem")
    municipio_destino = data.get("municipio_destino")
    uf_destino = data.get("uf_destino")
    if not all([municipio_origem, uf_origem, municipio_destino, uf_destino]):
        return jsonify({"error": "Dados de origem/destino incompletos"}), 400
    coord_origem = geocode(municipio_origem, uf_origem)
    coord_destino = geocode(municipio_destino, uf_destino)
    if not coord_origem or not coord_destino:
        return jsonify({"error": "Não foi possível geocodificar os locais."}), 400
    rota_info = calcular_distancia_osrm(coord_origem, coord_destino) or calcular_distancia_reta(coord_origem, coord_destino)
    if not rota_info:
        return jsonify({"error": "Não foi possível calcular a distância/rota."}), 500
    distancia = rota_info["distance"]
    faixa = determinar_faixa(distancia)
    custos_dedicado = TABELA_CUSTOS_DEDICADO.get(faixa, {}) if faixa and faixa != "6000+" else {"error": "Cotação indisponível para esta distância."}
    detalhes_calculo = {"municipio_origem": municipio_origem, "uf_origem": uf_origem, "municipio_destino": municipio_destino,
                        "uf_destino": uf_destino, "peso": data.get("peso", 0), "cubagem": data.get("cubagem", 0),
                        "custos_dedicado": custos_dedicado}
    analise = gerar_analise_trajeto(coord_origem, coord_destino, rota_info, "dedicado", detalhes_calculo)
    return jsonify({"distancia_km": round(distancia, 2), "duracao_min": round(rota_info["duration"], 2),
                    "rota_provider": rota_info["provider"], "custos_dedicado": custos_dedicado,
                    "rota_pontos": rota_info["route_points"], "analise_historico": analise})

@app.route('/calcular_frete_fracionado', methods=['POST'])
def calcular_frete_fracionado():
    estado_origem = request.form.get('estado_origem', '').strip().upper()
    municipio_origem_norm = normalizar_cidade(request.form.get('municipio_origem', ''))
    estado_destino = request.form.get('estado_destino', '').strip().upper()
    municipio_destino_norm = normalizar_cidade(request.form.get('municipio_destino', ''))
    peso_str = request.form.get('peso', '0')
    cubagem_str = request.form.get('cubagem', '0')
    tipo_prazo = request.form.get('tipo_prazo', 'econ')
    ufs_validas = [e['id'] for e in ESTADOS_FALLBACK]
    if estado_origem not in ufs_validas or estado_destino not in ufs_validas:
        return render_template_string(HTML_TEMPLATE, erro="UF inválida. Selecione um estado válido.")
    if estado_origem not in TABELA_CUSTOS or municipio_origem_norm not in TABELA_CUSTOS.get(estado_origem, {}):
        return render_template_string(HTML_TEMPLATE, erro=f"Município de origem {municipio_origem_norm} não encontrado.")
    try:
        peso = float(peso_str)
        cubagem = float(cubagem_str)
        if peso <= 0 or peso > 10000 or cubagem < 0 or cubagem > 100:
            return render_template_string(HTML_TEMPLATE, erro="Valores inválidos para peso ou cubagem.")
    except ValueError:
        return render_template_string(HTML_TEMPLATE, erro="Peso e cubagem devem ser numéricos.")
    municipios_origem_dict = get_municipios_uf(estado_origem)
    municipios_destino_dict = get_municipios_uf(estado_destino)
    municipio_origem_display = municipios_origem_dict.get(municipio_origem_norm, municipio_origem_norm)
    municipio_destino_display = municipios_destino_dict.get(municipio_destino_norm, municipio_destino_norm)
    transportadoras_rota = TABELA_CUSTOS.get(estado_origem, {}).get(municipio_origem_norm, {}).get(estado_destino, {}).get(municipio_destino_norm, [])
    ranking = []
    if transportadoras_rota:
        for transportadora_data in transportadoras_rota:
            custo = calcular_valor_fracionado(peso, cubagem, transportadora_data)
            if custo is not None:
                prazo_key = 'prazo_expresso' if tipo_prazo == 'expresso' else 'prazo_econ'
                ranking.append({
                    "fornecedor": transportadora_data["fornecedor"],
                    "custo": custo,
                    "prazo": transportadora_data[prazo_key],
                    "gris": transportadora_data["gris"],
                    "peso_maximo": transportadora_data["peso_maximo"],
                    "excedente": transportadora_data["excedente"]
                })
        ranking.sort(key=lambda x: (x["custo"], x["prazo"]))
    coord_origem = geocode(municipio_origem_display, estado_origem)
    coord_destino = geocode(municipio_destino_display, estado_destino)
    rota_info = calcular_distancia_osrm(coord_origem, coord_destino) if coord_origem and coord_destino else None
    resultado_final = {
        "ranking": ranking,
        "uf_origem": estado_origem,
        "cidades_origem": municipio_origem_display,
        "uf_destino": estado_destino,
        "cidades_destino": municipio_destino_display,
        "peso": peso,
        "cubagem": cubagem,
        "distancia": rota_info["distance"] if rota_info else None,
        "route_points": rota_info["route_points"] if rota_info else []
    }
    detalhes_calculo = {"uf_origem": estado_origem, "municipio_origem": municipio_origem_display,
                        "uf_destino": estado_destino, "municipio_destino": municipio_destino_display,
                        "peso": peso, "cubagem": cubagem, "ranking_fracionado": ranking}
    analise = gerar_analise_trajeto(coord_origem, coord_destino, rota_info, "fracionado", detalhes_calculo)
    resultado_final["search_id"] = analise["search_id"]
    return render_template_string(HTML_TEMPLATE, resultado=resultado_final)

@app.route('/gerar_pdf', methods=['POST'])
def gerar_pdf():
    resultado_json = request.form.get('resultado_json')
    if not resultado_json:
        return "Erro: Dados do resultado não encontrados.", 400
    try:
        resultado = json.loads(resultado_json)
    except json.JSONDecodeError:
        return "Erro: Formato inválido dos dados do resultado.", 400
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.alias_nb_pages()
    pdf.chapter_title("Detalhes da Cotacao")
    pdf.cell(40, 5, "Origem:", 0, 0)
    pdf.cell(0, 5, f"{resultado.get('cidades_origem', 'N/A')}, {resultado.get('uf_origem', 'N/A')}", 0, 1)
    pdf.cell(40, 5, "Destino:", 0, 0)
    pdf.cell(0, 5, f"{resultado.get('cidades_destino', 'N/A')}, {resultado.get('uf_destino', 'N/A')}", 0, 1)
    pdf.cell(40, 5, "Peso:", 0, 0)
    pdf.cell(0, 5, f"{resultado.get('peso', 'N/A')} kg", 0, 1)
    pdf.cell(40, 5, "Cubagem:", 0, 0)
    pdf.cell(0, 5, f"{resultado.get('cubagem', 'N/A')} m³", 0, 1)
    if resultado.get('distancia'):
        pdf.cell(40, 5, "Distância Estimada:", 0, 0)
        pdf.cell(0, 5, f"{resultado['distancia']:.2f} km", 0, 1)
    pdf.ln(5)
    pdf.chapter_title("Ranking de Transportadoras (Frete Fracionado)")
    header = ["Fornecedor", "Custo (R$)", "Prazo", "GRIS (%)", "Peso Max", "Exced (R$)"]
    data_table = resultado.get('ranking', [])
    pdf.print_table(header, data_table)
    pdf_output = pdf.output(dest='S')
    return send_file(
        io.BytesIO(pdf_output),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"cotacao_{resultado.get('uf_origem', '')}_{resultado.get('uf_destino', '')}.pdf"
    )

@app.route('/historico', methods=['GET'])
def get_historico():
    uf_filter = request.args.get('uf', '').strip().upper()
    historico = load_history()
    if uf_filter:
        historico = [h for h in historico if h['origem_uf'] == uf_filter or h['destino_uf'] == uf_filter]
    return jsonify(historico)

if __name__ == '__main__':
    init_db()
    os.makedirs(BASE_DIR, exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=False)