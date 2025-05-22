from flask import Flask, render_template_string, request, jsonify, send_file, send_from_directory
import requests
import math
import os
import datetime
import sqlite3
import csv
import polyline
from fpdf import FPDF
import io

app = Flask(__name__)

BASE_PATH = r"C:\Users\Usuário\OneDrive\Desktop\SQL data\Chico automate"
DATABASE = os.path.join(BASE_PATH, "fretes.db")
CSV_CONCEPT = os.path.join(BASE_PATH, "Concept.csv")
CSV_JEM_DFL = os.path.join(BASE_PATH, "JEM_DFL.csv")

# Fallback local de estados (sigla e nome)
ESTADOS_FALLBACK = [
    {"id": "AC", "text": "Acre"},
    {"id": "AL", "text": "Alagoas"},
    {"id": "AP", "text": "Amapá"},
    {"id": "AM", "text": "Amazonas"},
    {"id": "BA", "text": "Bahia"},
    {"id": "CE", "text": "Ceará"},
    {"id": "DF", "text": "Distrito Federal"},
    {"id": "ES", "text": "Espírito Santo"},
    {"id": "GO", "text": "Goiás"},
    {"id": "MA", "text": "Maranhão"},
    {"id": "MT", "text": "Mato Grosso"},
    {"id": "MS", "text": "Mato Grosso do Sul"},
    {"id": "MG", "text": "Minas Gerais"},
    {"id": "PA", "text": "Pará"},
    {"id": "PB", "text": "Paraíba"},
    {"id": "PR", "text": "Paraná"},
    {"id": "PE", "text": "Pernambuco"},
    {"id": "PI", "text": "Piauí"},
    {"id": "RJ", "text": "Rio de Janeiro"},
    {"id": "RN", "text": "Rio Grande do Norte"},
    {"id": "RS", "text": "Rio Grande do Sul"},
    {"id": "RO", "text": "Rondônia"},
    {"id": "RR", "text": "Roraima"},
    {"id": "SC", "text": "Santa Catarina"},
    {"id": "SP", "text": "São Paulo"},
    {"id": "SE", "text": "Sergipe"},
    {"id": "TO", "text": "Tocantins"}
]

# Tabela de custos expandida
TABELA_CUSTOS = {
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
}

# Histórico de pesquisas
HISTORICO_PESQUISAS = []

def get_db():
    try:
        if not os.path.exists(BASE_PATH):
            os.makedirs(BASE_PATH, exist_ok=True)  # Create directory if it doesn't exist
        if not os.access(BASE_PATH, os.W_OK):
            raise PermissionError(f"No write permissions for directory: {BASE_PATH}")
        return sqlite3.connect(DATABASE)
    except PermissionError as e:
        print(f"Permission Error: {e}")
        raise
    except Exception as e:
        print(f"Error accessing database at {DATABASE}: {e}")
        raise

def inicializar_banco():
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Verificar e criar a tabela 'concept'
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='concept'")
        if c.fetchone() is None:
            c.execute('''CREATE TABLE concept (
                            uf_origem TEXT,
                            origem TEXT,
                            uf_destino TEXT,
                            destino TEXT,
                            faixa10 REAL,
                            faixa20 REAL,
                            faixa35 REAL,
                            faixa50 REAL,
                            faixa70 REAL,
                            faixa100 REAL,
                            faixa300 REAL,
                            faixa500 REAL,
                            faixa500plus REAL,
                            pedagio REAL,
                            gris_min REAL
                        )''')
            if not os.path.exists(CSV_CONCEPT):
                raise FileNotFoundError(f"CSV file not found: {CSV_CONCEPT}")
            with open(CSV_CONCEPT, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Pular o cabeçalho
                for row in reader:
                    if len(row) != 15:
                        print(f"Warning: Invalid row in {CSV_CONCEPT}: {row}")
                        continue
                    c.execute('INSERT INTO concept VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', row)
        
        # Verificar e criar a tabela 'jem_dfl'
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jem_dfl'")
        if c.fetchone() is None:
            c.execute('''CREATE TABLE jem_dfl (
                            uf_origem TEXT,
                            origem TEXT,
                            uf_destino TEXT,
                            destino TEXT,
                            faixa10 REAL,
                            faixa20 REAL,
                            faixa35 REAL,
                            faixa50 REAL,
                            faixa70 REAL,
                            faixa100 REAL,
                            faixa300 REAL,
                            faixa500 REAL,
                            faixa500plus REAL,
                            pedagio REAL,
                            gris_min REAL
                        )''')
            if not os.path.exists(CSV_JEM_DFL):
                raise FileNotFoundError(f"CSV file not found: {CSV_JEM_DFL}")
            with open(CSV_JEM_DFL, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Pular o cabeçalho
                for row in reader:
                    if len(row) != 15:
                        print(f"Warning: Invalid row in {CSV_JEM_DFL}: {row}")
                        continue
                    c.execute('INSERT INTO jem_dfl VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', row)
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

# --- Cálculo Fracionado (exemplo simplificado) ---
def calcular_valor_fracionado(row, peso):
    limites = [10, 20, 35, 50, 70, 100, 300, 500, 99999]
    precos = [row['faixa10'], row['faixa20'], row['faixa35'], row['faixa50'], row['faixa70'], row['faixa100'], row['faixa300'], row['faixa500'], row['faixa500plus']]
    valor = 0
    restante = peso
    for i, limite in enumerate(limites):
        if restante <= 0:
            break
        if i == 0:
            if restante <= limite:
                valor += precos[i]
                restante = 0
            else:
                valor += precos[i]
                restante -= limite
        else:
            if restante > 0:
                faixa_peso = min(restante, limite - limites[i-1])
                valor += faixa_peso * precos[i]
                restante -= faixa_peso
    valor += row['pedagio']
    valor += row['gris_min']
    return valor

@app.route('/calcular_fracionado', methods=['POST'])
def calcular_fracionado():
    data = request.json
    uf_origem = data["uf_origem"]
    origem = data["origem"].strip().upper()
    uf_destino = data["uf_destino"]
    destino = data["destino"].strip().upper()
    peso = float(data["peso"])
    cubagem = float(data["cubagem"])
    peso_cubado = max(peso, cubagem * 300)

    resultados = []
    conn = get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    for tabela, nome_agente in [("concept", "Concept"), ("jem_dfl", "JEM/DFL")]:
        c.execute(f"""SELECT * FROM {tabela} 
                      WHERE uf_origem=? AND origem=? AND uf_destino=? AND destino=?""",
                  (uf_origem, origem, uf_destino, destino))
        for row in c.fetchall():
            valor = calcular_valor_fracionado(row, peso_cubado)
            resultados.append({
                'agente': nome_agente,
                'valor': valor
            })
    conn.close()
    resultados = [r for r in resultados if r['valor'] > 0]
    resultados.sort(key=lambda x: x['valor'])
    return jsonify({
        "principal": resultados[0] if resultados else None,
        "todos": resultados
    })

def geocode(municipio, uf):
    """Obtém coordenadas usando OpenStreetMap"""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": f"{municipio}, {uf}, Brasil", "format": "json", "limit": 1}
    headers = {"User-Agent": "TransportCostCalculator/1.0"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        if data:
            return (float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", ""))
        return None
    except Exception as e:
        print(f"Erro ao geocodificar: {e}")
        return None

def calcular_distancia_osrm(origem, destino):
    """Calcula distância de rota via OSRM"""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{origem[1]},{origem[0]};{destino[1]},{destino[0]}"
        response = requests.get(url, params={"overview": "full"}, timeout=15)
        data = response.json()
        if data.get("code") == "Ok" and data.get("routes"):
            route = data["routes"][0]
            distance = route["distance"] / 1000  # km
            duration = route["duration"] / 60  # minutos
            geometry = route.get("geometry", "")
            
            route_points = []
            if geometry:
                try:
                    route_points = polyline.decode(geometry)
                except Exception as e:
                    print(f"Erro ao decodificar geometria: {e}")
            
            return {
                "distance": distance,
                "duration": duration,
                "route_points": route_points,
                "provider": "OSRM"
            }
        return None
    except Exception as e:
        print(f"Erro ao calcular rota OSRM: {e}")
        return None

def calcular_distancia_openroute(origem, destino):
    """Calcula distância de rota via OpenRouteService como backup"""
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {"Accept": "application/json"}
        params = {
            "start": f"{origem[1]},{origem[0]}",
            "end": f"{destino[1]},{destino[0]}"
        }
        response = requests.get(url, headers=headers, params=params, timeout=15)
        data = response.json()
        
        if "features" in data and data["features"]:
            route = data["features"][0]
            properties = route.get("properties", {})
            segments = properties.get("segments", [{}])[0]
            
            distance = segments.get("distance", 0) / 1000  # km
            duration = segments.get("duration", 0) / 60  # minutos
            
            geometry = route.get("geometry", {})
            route_points = []
            if geometry and "coordinates" in geometry:
                route_points = [[coord[1], coord[0]] for coord in geometry["coordinates"]]
            
            return {
                "distance": distance,
                "duration": duration,
                "route_points": route_points,
                "provider": "OpenRouteService"
            }
        return None
    except Exception as e:
        print(f"Erro ao calcular rota OpenRouteService: {e}")
        return None

def calcular_distancia_reta(origem, destino):
    """Distância em linha reta (Haversine)"""
    try:
        lat1, lon1 = origem[0], origem[1]
        lat2, lon2 = destino[0], destino[1]
        R = 6371
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        duration = (distance / 80) * 60
        route_points = [[lat1, lon1], [lat2, lon2]]
        return {"distance": distance, "duration": duration, "route_points": route_points, "provider": "Linha Reta"}
    except Exception as e:
        print(f"Erro ao calcular distância em linha reta: {e}")
        return None

def determinar_faixa(distancia):
    faixas = [
        (0, 20), (20, 50), (50, 100), (100, 150), (150, 200),
        (200, 250), (250, 300), (300, 400), (400, 600), (600, 800),
        (800, 1000), (1000, 1500), (1500, 2000), (2000, 2500),
        (2500, 3000), (3000, 3500), (3500, 4000), (4000, 4500)
    ]
    for min_val, max_val in faixas:
        if min_val < distancia <= max_val:
            return f"{min_val}-{max_val}"
    return None

def gerar_analise_trajeto(origem_info, destino_info, rota_info, custos):
    origem_nome = origem_info[2] if len(origem_info) > 2 else "Origem"
    destino_nome = destino_info[2] if len(destino_info) > 2 else "Destino"
    horas = int(rota_info["duration"] // 60)
    minutos = int(rota_info["duration"] % 60)
    tempo_estimado = f"{horas}h {minutos}min" if horas > 0 else f"{minutos}min"
    consumo_combustivel = rota_info["distance"] / 10
    emissao_co2 = consumo_combustivel * 2.3
    pedagio_estimado = rota_info["distance"] * 0.15
    analise = {
        "origem": origem_nome, "destino": destino_nome,
        "distancia": round(rota_info["distance"], 2),
        "tempo_estimado": tempo_estimado,
        "duracao_minutos": round(rota_info["duration"], 2),
        "consumo_combustivel": round(consumo_combustivel, 2),
        "emissao_co2": round(emissao_co2, 2),
        "pedagio_estimado": round(pedagio_estimado, 2),
        "provider": rota_info["provider"], "custos": custos,
        "data_hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "rota_pontos": rota_info["route_points"]
    }
    return analise

class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 15)
        self.cell(0, 10, "📦 PortoEx - Relatório de Transporte", 0, 1, "C")
        self.line(10, 20, 200, 20)
        self.ln(10)
        
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", 0, 0, "C")
        self.cell(0, 10, f"© {datetime.datetime.now().year} PortoEx - Todos os direitos reservados", 0, 0, "R")

# ----------- ENDPOINTS FRACIONADO - FILTROS -----------
@app.route("/estados_fracionado")
def estados_fracionado():
    conn = get_db()
    c = conn.cursor()
    estados = set()
    for tabela in ["concept", "jem_dfl"]:
        c.execute(f"SELECT DISTINCT uf_origem FROM {tabela}")
        estados.update([row[0] for row in c.fetchall()])
    conn.close()
    estados = sorted(estados)
    return jsonify([{"id": uf, "text": uf} for uf in estados])

@app.route("/municipios_fracionado/<uf>")
def municipios_fracionado(uf):
    conn = get_db()
    c = conn.cursor()
    municipios = set()
    for tabela in ["concept", "jem_dfl"]:
        c.execute(f"SELECT DISTINCT origem FROM {tabela} WHERE uf_origem=?", (uf,))
        municipios.update([row[0] for row in c.fetchall()])
    conn.close()
    municipios = sorted(municipios)
    return jsonify([{"id": m, "text": m.title()} for m in municipios])

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/estados")
def estados():
    try:
        response = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome", timeout=3)
        response.raise_for_status() 
        estados_data = response.json()
        print("Estados carregados da API IBGE.")
        return jsonify([{"id": e["sigla"], "text": e["nome"]} for e in estados_data])
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar estados da API do IBGE: {e}. Usando fallback.")
        return jsonify(ESTADOS_FALLBACK)

@app.route("/municipios/<uf>")
def municipios(uf):
    try:
        response = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios", timeout=5)
        response.raise_for_status()
        return jsonify([{"id": m["nome"], "text": m["nome"]} for m in response.json()])
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar municípios da API do IBGE para {uf}: {e}. Retornando lista vazia.")
        return jsonify([]) 

@app.route("/calcular", methods=["POST"])
def calcular():
    data = request.json
    municipio_origem = data["municipio_origem"]
    uf_origem = data["uf_origem"]
    municipio_destino = data["municipio_destino"]
    uf_destino = data["uf_destino"]
    coord_origem = geocode(municipio_origem, uf_origem)
    coord_destino = geocode(municipio_destino, uf_destino)
    if not coord_origem or not coord_destino:
        return jsonify({"error": "Não foi possível identificar os locais"}), 400
    rota_info = calcular_distancia_osrm(coord_origem, coord_destino)
    if not rota_info:
        rota_info = calcular_distancia_openroute(coord_origem, coord_destino)
    if not rota_info:
        rota_info = calcular_distancia_reta(coord_origem, coord_destino)
        if not rota_info:
            return jsonify({"error": "Não foi possível calcular a distância"}), 500
    distancia = rota_info["distance"]
    faixa = determinar_faixa(distancia)
    if not faixa:
        return jsonify({"error": "Distância fora da faixa suportada (acima de 4500 km)"}), 400
    custos = TABELA_CUSTOS[faixa]
    analise = gerar_analise_trajeto(coord_origem, coord_destino, rota_info, custos)
    HISTORICO_PESQUISAS.append(analise)
    if len(HISTORICO_PESQUISAS) > 50:
        HISTORICO_PESQUISAS.pop(0)
    return jsonify({
        "distancia": round(distancia, 2),
        "duracao": round(rota_info["duration"], 2),
        "tipo_distancia": rota_info["provider"],
        "custos": custos,
        "rota_pontos": rota_info["route_points"],
        "analise": analise
    })

@app.route("/historico")
def historico():
    return jsonify(HISTORICO_PESQUISAS)

@app.route("/gerar-pdf", methods=["POST"])
def gerar_pdf():
    data = request.json
    analise = data.get("analise")
    if not analise:
        return jsonify({"error": "Dados de análise não fornecidos"}), 400
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Análise de Trajeto", 0, 1, "L")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 10, f"Data: {analise['data_hora']}", 0, 1, "L")
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Rota", 0, 1, "L")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, f"Origem: {analise['origem']}", 0, 1, "L")
    pdf.cell(0, 8, f"Destino: {analise['destino']}", 0, 1, "L")
    pdf.cell(0, 8, f"Método de cálculo: {analise['provider']}", 0, 1, "L")
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Estatísticas", 0, 1, "L")
    pdf.set_font("Arial", "", 10)
    stats = [
        ["Distância total", f"{analise['distancia']} km"],
        ["Tempo estimado", f"{analise['tempo_estimado']}"],
        ["Consumo estimado", f"{analise['consumo_combustivel']} L"],
        ["Emissão de CO₂", f"{analise['emissao_co2']} kg"]
    ]
    for stat in stats:
        pdf.set_font("Arial", "B", 10)
        pdf.cell(80, 8, stat[0], 1, 0, "L")
        pdf.set_font("Arial", "", 10)
        pdf.cell(80, 8, stat[1], 1, 1, "L")
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Custos por Tipo de Veículo", 0, 1, "L")
    pdf.set_font("Arial", "B", 10)
    pdf.cell(80, 8, "Tipo de Veículo", 1, 0, "C")
    pdf.cell(80, 8, "Custo (R$)", 1, 1, "C")
    pdf.set_font("Arial", "", 10)
    for veiculo, valor in analise["custos"].items():
        pdf.cell(80, 8, veiculo, 1, 0, "L")
        pdf.cell(80, 8, f"R$ {valor:.2f}", 1, 1, "R")
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Informações Adicionais", 0, 1, "L")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, f"Pedágio estimado: R$ {analise['pedagio_estimado']:.2f}", 0, 1, "L")
    pdf.ln(5)
    pdf.multi_cell(0, 8, "Observações: Os valores apresentados são estimativas baseadas em cálculos aproximados e podem variar de acordo com condições específicas da rota, clima, tráfego e outros fatores.", 0, "L")
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return send_file(
        pdf_output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f'relatorio_transporte_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <title>PortoEx - Cotação Controladoria</title>
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <!-- Frameworks e Libs -->
  <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet"/>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css"/>
  <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {
      --primary: #1976d2;
      --accent: #e53935;
      --bg: #f7f9fa;
      --bg-dark: #181c23;
      --card: #fff;
      --card-dark: #23272f;
      --text: #23272f;
      --text-dark: #f7f9fa;
      --shadow: 0 2px 24px 0 rgba(25, 118, 210, 0.08);
      --radius: 18px;
      --transition: .18s cubic-bezier(.4,0,.2,1);
    }
    html, body {
      margin: 0; padding: 0;
      font-family: 'Inter', Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      transition: background .2s, color .2s;
    }
    body.dark {
      background: var(--bg-dark);
      color: var(--text-dark);
    }
    .container {
      max-width: 1100px;
      margin: 32px auto;
      padding: 24px;
      background: var(--card);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      transition: background .2s;
    }
    body.dark .container {
      background: var(--card-dark);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 24px;
    }
    header h1 {
      font-size: 2.1rem;
      font-weight: 800;
      letter-spacing: -1.5px;
      margin: 0;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .theme-btn {
      border: none;
      background: none;
      font-size: 1.5rem;
      color: var(--primary);
      cursor: pointer;
      transition: color .2s;
    }
    .theme-btn:hover { color: var(--accent); }
    .consulta-btn {
      text-decoration: none;
      color: var(--primary);
      font-weight: 600;
      font-size: 1.02rem;
      padding: 4px 12px;
      border-radius: 8px;
      background: rgba(25,118,210,0.08);
      transition: background .2s;
      margin-right: 8px;
    }
    .consulta-btn:hover { background: rgba(25,118,210,0.18);}
    .pbi-btn {
      background: var(--primary);
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 8px 18px;
      font-size: 1rem;
      font-weight: 600;
      margin-bottom: 18px;
      cursor: pointer;
      transition: background .2s;
      box-shadow: 0 2px 8px 0 rgba(25, 118, 210, 0.09);
    }
    .pbi-btn:hover { background: var(--accent);}
    /* Tabs */
    .tabs {
      display: flex;
      margin-bottom: 24px;
      border-bottom: 2px solid #e3e8ee;
    }
    .tab-btn {
      flex: 1;
      background: none;
      border: none;
      padding: 14px 0;
      font-size: 1.1em;
      cursor: pointer;
      color: var(--text);
      font-weight: 600;
      border-bottom: 3px solid transparent;
      transition: color .2s, border-bottom .2s;
    }
    .tab-btn.active {
      color: var(--primary);
      border-bottom: 3px solid var(--primary);
      background: rgba(25,118,210,0.04);
    }
    body.dark .tab-btn { color: var(--text-dark);}
    body.dark .tab-btn.active { color: var(--accent); border-bottom: 3px solid var(--accent);}
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    /* Formulários */
    .form-container {
      margin-bottom: 32px;
    }
    .row {
      display: flex;
      gap: 32px;
      flex-wrap: wrap;
    }
    .col { flex: 1; min-width: 270px; }
    .form-group { margin-bottom: 18px; }
    label { font-weight: 600; margin-bottom: 6px; display: block;}
    input, select, .select2-container--classic .select2-selection--single {
      width: 100%;
      padding: 10px 12px;
      border-radius: 8px;
      border: 1.5px solid #d1d5db;
      font-size: 1rem;
      background: #f7f9fa;
      transition: border .2s;
      margin-top: 3px;
    }
    body.dark input, body.dark select, body.dark .select2-container--classic .select2-selection--single {
      background: #23272f;
      color: #f7f9fa;
      border-color: #3a3f4b;
    }
    .btn-calcular {
      background: var(--accent);
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 10px 22px;
      font-size: 1.1rem;
      font-weight: 700;
      cursor: pointer;
      margin-top: 12px;
      transition: background .2s;
      box-shadow: 0 2px 8px 0 rgba(229, 57, 53, 0.08);
    }
    .btn-calcular:hover { background: #b71c1c;}
    /* Resultados */
    #resultados, #fracionado-resultado {
      margin-top: 32px;
      animation: fadeIn .7s;
    }
    @keyframes fadeIn { from { opacity: 0;} to { opacity: 1; } }
    table {
      border-collapse: collapse;
      width: 100%;
      margin-top: 18px;
      background: #f7f9fa;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 2px 8px 0 rgba(25, 118, 210, 0.06);
    }
    body.dark table { background: #23272f;}
    th, td {
      border: none;
      padding: 12px 10px;
      text-align: left;
      font-size: 1rem;
    }
    th {
      background: var(--primary);
      color: #fff;
      font-weight: 700;
      letter-spacing: .5px;
    }
    tr:nth-child(even) { background: #f1f5fa;}
    body.dark tr:nth-child(even) { background: #252a34;}
    .resultado-info p { margin: 8px 0; font-size: 1.08rem;}
    /* Mapa */
    #map { width: 100%; height: 320px; border-radius: 12px; margin-top: 22px; }
    /* Power BI Modal */
    .pbi-modal-bg {
      display: none; position: fixed; top:0; left:0; width:100vw; height:100vh;
      background: rgba(36,37,38,0.75); z-index: 9999; align-items: center; justify-content: center;
    }
    .pbi-modal-bg.active { display: flex;}
    .pbi-modal {
      background: #fff; padding: 0; border-radius: 18px; max-width: 900px; width: 98vw; box-shadow: var(--shadow);
      position: relative; animation: fadeIn .5s;
    }
    .pbi-modal-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 12px 24px; background: var(--primary); color: #fff; border-radius: 18px 18px 0 0;
    }
    .pbi-modal-body { padding: 0 0 18px 0;}
    .pbi-modal iframe { width: 100%; height: 440px; border: none; border-radius: 0 0 18px 18px;}
    .close-btn {
      background: none; border: none; font-size: 1.3rem; color: #fff; cursor: pointer;
    }
    /* Loading */
    .loading { display: flex; align-items: center; gap: 18px; margin-top: 18px;}
    .spinner {
      width: 28px; height: 28px; border: 4px solid #e3e8ee; border-top: 4px solid var(--primary);
      border-radius: 50%; animation: spin 1s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    /* Fracionado extra */
    #fracionado-form input, #fracionado-form select { width: 100%; padding: 8px; }
    #fracionado-resultado h3 { margin-top: 0; color: var(--primary);}
    /* Responsivo */
    @media (max-width: 800px) {
      .container { padding: 12px;}
      .row { flex-direction: column; gap: 0;}
      header { flex-direction: column; gap: 8px;}
      .pbi-modal { max-width: 98vw;}
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1><i class="fa-solid fa-truck-fast"></i> PortoEx - Cotação Controladoria</h1>
      <button id="theme-toggle" class="theme-btn" title="Alternar tema">
        <i class="fa-solid fa-moon" id="theme-icon"></i>
      </button>
      <a href="https://onedrive.live.com/?id=7D2F1EE6EAD699A1%21s3c277927e98244b3a012f3122abe84a5&cid=7D2F1EE6EAD699A1&sb=name&sd=1" target="_blank" class="consulta-btn">
        <i class="fa-solid fa-table-list"></i> Consultar Tabela de Agentes
      </a>
    </header>
    <button class="pbi-btn" id="abrir-pbi">📊 Target BI</button>
    <!-- Abas -->
    <div class="tabs">
      <button class="tab-btn active" data-tab="rota">Dedicado</button>
      <button class="tab-btn" data-tab="fracionado">Fracionado</button>
    </div>
    <!-- Cálculo de Rota -->
    <main class="form-container tab-content active" id="tab-rota">
      <div class="row">
        <div class="col">
          <div class="form-group">
            <label for="uf_origem">Estado de Origem</label>
            <select id="uf_origem" class="select2-enable" data-placeholder="Selecione o estado"></select>
          </div>
          <div class="form-group">
            <label for="municipio_origem">Município de Origem</label>
            <select id="municipio_origem" class="select2-enable" data-placeholder="Selecione o município" disabled></select>
          </div>
        </div>
        <div class="col">
          <div class="form-group">
            <label for="uf_destino">Estado de Destino</label>
            <select id="uf_destino" class="select2-enable" data-placeholder="Selecione o estado"></select>
          </div>
          <div class="form-group">
            <label for="municipio_destino">Município de Destino</label>
            <select id="municipio_destino" class="select2-enable" data-placeholder="Selecione o município" disabled></select>
          </div>
        </div>
      </div>
      <button id="btn_calcular" class="btn-calcular">
        <i class="fa-solid fa-calculator"></i> Calcular Custos
      </button>
      <div id="loading" class="loading" style="display:none;">
        <div class="spinner"></div>
        <p>Calculando rota e custos...</p>
      </div>
      <div id="resultados" style="display: none">
        <div id="map"></div>
        <table>
          <thead>
            <tr>
              <th>Tipo de Veículo</th>
              <th>Custo (R$)</th>
            </tr>
          </thead>
          <tbody id="tabela-resultado"></tbody>
        </table>
        <div class="resultado-info">
          <p><strong>Rota:</strong> <span id="res-origem"></span> → <span id="res-destino"></span></p>
          <p><strong>Distância:</strong> <span id="res-distancia"></span> km</p>
          <p><strong>Tempo estimado:</strong> <span id="res-tempo"></span></p>
          <p><strong>Consumo estimado:</strong> <span id="res-consumo"></span> L</p>
          <p><strong>Emissão de CO₂:</strong> <span id="res-co2"></span> kg</p>
          <p><strong>Pedágio estimado:</strong> R$ <span id="res-pedagio"></span></p>
        </div>
        <button id="btn_gerar_pdf" class="btn-calcular" style="background: #1976d2;">
          <i class="fa-solid fa-file-pdf"></i> Salvar Relatório em PDF
        </button>
      </div>
    </main>
    <!-- Fracionado -->
    <main class="form-container tab-content" id="tab-fracionado">
      <form id="fracionado-form" onsubmit="return false;">
        <div class="row">
          <div class="col">
            <div class="form-group">
              <label for="uf_origem_frac">Estado de Origem</label>
              <select id="uf_origem_frac" class="select2-enable"></select>
            </div>
            <div class="form-group">
              <label for="municipio_origem_frac">Município de Origem</label>
              <select id="municipio_origem_frac" class="select2-enable" disabled></select>
            </div>
          </div>
          <div class="col">
            <div class="form-group">
              <label for="uf_destino_frac">Estado de Destino</label>
              <select id="uf_destino_frac" class="select2-enable"></select>
            </div>
            <div class="form-group">
              <label for="municipio_destino_frac">Município de Destino</label>
              <select id="municipio_destino_frac" class="select2-enable" disabled></select>
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col">
            <div class="form-group">
              <label for="peso-frac">Peso (kg)</label>
              <input type="number" id="peso-frac" value="10" min="0.01" step="0.01" required>
            </div>
          </div>
          <div class="col">
            <div class="form-group">
              <label for="cubagem-frac">Cubagem (m³)</label>
              <input type="number" id="cubagem-frac" value="0.05" min="0" step="0.01" required>
            </div>
          </div>
        </div>
        <button id="btn-fracionado" class="btn-calcular">
          <i class="fa-solid fa-calculator"></i> Calcular Frete Fracionado
        </button>
      </form>
      <div id="fracionado-resultado"></div>
    </main>
  </div>
  <!-- Power BI Modal -->
  <div class="pbi-modal-bg" id="pbi-modal-bg">
    <div class="pbi-modal">
      <div class="pbi-modal-header">
        <span>Dashboard</span>
        <button class="close-btn" id="fechar-pbi" title="Fechar">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="pbi-modal-body">
        <iframe src="https://app.powerbi.com/view?r=eyJrIjoiYWUzODBiYmUtMWI1OC00NGVjLWFjNDYtYzYyMDQ3MzQ0MTQ0IiwidCI6IjM4MjViNTlkLTY1ZGMtNDM1Zi04N2M4LTkyM2QzMzkxYzMyOCJ9" allowfullscreen="true"></iframe>
      </div>
    </div>
  </div>
  <script>
    // Abas
    $(".tab-btn").on("click", function() {
      $(".tab-btn").removeClass("active");
      $(this).addClass("active");
      $(".tab-content").removeClass("active");
      $("#tab-" + $(this).data("tab")).addClass("active");
    });
    // Tema claro/escuro
    function setTheme(mode) {
      if (mode === "dark") {
        document.body.classList.add("dark");
        document.getElementById("theme-icon").classList.replace("fa-moon", "fa-sun");
      } else {
        document.body.classList.remove("dark");
        document.getElementById("theme-icon").classList.replace("fa-sun", "fa-moon");
      }
      localStorage.setItem("theme", mode);
    }
    $(document).ready(function () {
      // Tema
      const savedTheme = localStorage.getItem("theme") || "light";
      setTheme(savedTheme);
      $("#theme-toggle").on("click", function () {
        const currentTheme = document.body.classList.contains("dark") ? "dark" : "light";
        setTheme(currentTheme === "dark" ? "light" : "dark");
      });
      // Power BI Modal
      $("#abrir-pbi").on("click", function () {
        $("#pbi-modal-bg").addClass("active");
      });
      $("#fechar-pbi, #pbi-modal-bg").on("click", function (e) {
        if (e.target === this) {
          $("#pbi-modal-bg").removeClass("active");
        }
      });
      // Select2 AJAX para estados e municípios (Rota)
      $("#uf_origem, #uf_destino").select2({
        placeholder: "Selecione o estado",
        allowClear: true,
        theme: "classic",
        ajax: {
          url: "/estados",
          dataType: "json",
          delay: 250,
          processResults: function (data) {
            return { results: data };
          },
          cache: true,
        },
      });
      $("#uf_origem").on("change", function () {
        var uf = $(this).val();
        $("#municipio_origem").val(null).trigger("change");
        $("#municipio_origem").prop("disabled", !uf);
        if (uf) {
          $("#municipio_origem").select2({
            placeholder: "Selecione o município",
            allowClear: true,
            theme: "classic",
            ajax: {
              url: "/municipios/" + uf,
              dataType: "json",
              delay: 250,
              processResults: function (data) {
                return { results: data };
              },
              cache: true,
            },
          });
        } else {
          $("#municipio_origem").select2("destroy");
        }
      });
      $("#uf_destino").on("change", function () {
        var uf = $(this).val();
        $("#municipio_destino").val(null).trigger("change");
        $("#municipio_destino").prop("disabled", !uf);
        if (uf) {
          $("#municipio_destino").select2({
            placeholder: "Selecione o município",
            allowClear: true,
            theme: "classic",
            ajax: {
              url: "/municipios/" + uf,
              dataType: "json",
              delay: 250,
              processResults: function (data) {
                return { results: data };
              },
              cache: true,
            },
          });
        } else {
          $("#municipio_destino").select2("destroy");
        }
      });
      // Botão calcular rota
      $("#btn_calcular").on("click", function () {
        const ufOrigem = $("#uf_origem").val();
        const munOrigem = $("#municipio_origem").val();
        const ufDestino = $("#uf_destino").val();
        const munDestino = $("#municipio_destino").val();
        if (!ufOrigem || !munOrigem || !ufDestino || !munDestino) {
          alert("Por favor, selecione origem e destino completos.");
          return;
        }
        $("#loading").show();
        $("#resultados").hide();
        $.ajax({
          url: "/calcular",
          method: "POST",
          contentType: "application/json",
          data: JSON.stringify({
            uf_origem: ufOrigem,
            municipio_origem: munOrigem,
            uf_destino: ufDestino,
            municipio_destino: munDestino,
          }),
          success: function (resp) {
            $("#loading").hide();
            $("#res-origem").text(resp.analise.origem);
            $("#res-destino").text(resp.analise.destino);
            $("#res-distancia").text(resp.analise.distancia);
            $("#res-tempo").text(resp.analise.tempo_estimado);
            $("#res-consumo").text(resp.analise.consumo_combustivel);
            $("#res-co2").text(resp.analise.emissao_co2);
            $("#res-pedagio").text(resp.analise.pedagio_estimado);
            let htmlTabela = "";
            for (let tipo in resp.custos) {
              htmlTabela += `<tr>
                <td>${tipo}</td>
                <td>R$ ${resp.custos[tipo].toLocaleString("pt-BR", {minimumFractionDigits: 2})}</td>
              </tr>`;
            }
            $("#tabela-resultado").html(htmlTabela);
            $("#resultados").show();
            if (resp.rota_pontos && resp.rota_pontos.length > 1) {
              // Chame a função do mapa se necessário
            } else {
              $("#map").hide();
            }
          },
          error: function (xhr) {
            $("#loading").hide();
            alert("Erro ao calcular rota: " + xhr.responseText);
          },
        });
      });

      // Fracionado Select2 Estados/Municípios
      $("#uf_origem_frac").select2({
        placeholder: "Selecione o estado",
        ajax: {
          url: "/estados_fracionado",
          dataType: "json",
          processResults: function (data) { return { results: data }; },
          cache: true,
        }
      });
      $("#uf_origem_frac").on("change", function () {
        let uf = $(this).val();
        $("#municipio_origem_frac").val(null).trigger("change").prop("disabled", !uf);
        if (uf) {
          $("#municipio_origem_frac").select2({
            placeholder: "Selecione o município",
            ajax: {
              url: "/municipios_fracionado/" + uf,
              dataType: "json",
              processResults: function (data) { return { results: data }; },
              cache: true,
            }
          });
        } else {
          $("#municipio_origem_frac").select2("destroy");
        }
      });
      $("#uf_destino_frac").select2({
        placeholder: "Selecione o estado",
        ajax: {
          url: "/estados_fracionado",
          dataType: "json",
          processResults: function (data) { return { results: data }; },
          cache: true,
        }
      });
      $("#uf_destino_frac").on("change", function () {
        let uf = $(this).val();
        $("#municipio_destino_frac").val(null).trigger("change").prop("disabled", !uf);
        if (uf) {
          $("#municipio_destino_frac").select2({
            placeholder: "Selecione o município",
            ajax: {
              url: "/municipios_fracionado/" + uf,
              dataType: "json",
              processResults: function (data) { return { results: data }; },
              cache: true,
            }
          });
        } else {
          $("#municipio_destino_frac").select2("destroy");
        }
      });

      // Envio do formulário fracionado
      $("#btn-fracionado").on("click", function () {
        const uf_origem = $("#uf_origem_frac").val();
        const origem = $("#municipio_origem_frac").val();
        const uf_destino = $("#uf_destino_frac").val();
        const destino = $("#municipio_destino_frac").val();
        const peso = $("#peso-frac").val();
        const cubagem = $("#cubagem-frac").val();
        if (!uf_origem || !origem || !uf_destino || !destino || !peso || !cubagem) {
          alert("Preencha todos os campos!");
          return;
        }
        $("#fracionado-resultado").html("<div class='loading'><div class='spinner'></div>Calculando...</div>");
        fetch('/calcular_fracionado', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({uf_origem, origem, uf_destino, destino, peso, cubagem})
        })
        .then(res => res.json())
        .then(data => {
          let html = '';
          if (data.principal) {
            html += `<h3>Melhor transportador: ${data.principal.agente} - R$ ${data.principal.valor.toFixed(2)}</h3>`;
          } else {
            html += `<h3>Nenhum frete encontrado para esse trecho.</h3>`;
          }
          if (data.todos && data.todos.length > 0) {
            html += `<table><thead><tr><th>Agente</th><th>Valor (R$)</th></tr></thead><tbody>`;
            data.todos.forEach(r => {
              html += `<tr><td>${r.agente}</td><td>${r.valor.toFixed(2)}</td></tr>`;
            });
            html += `</tbody></table>`;
          }
          $("#fracionado-resultado").html(html);
        }).catch(() => {
          $("#fracionado-resultado").html("<p>Erro ao calcular frete fracionado.</p>");
        });
      });
    });
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    try:
        if not os.path.exists(os.path.join(BASE_PATH, "db_initialized")):
            inicializar_banco()
            with open(os.path.join(BASE_PATH, "db_initialized"), 'w') as f:
                f.write("Banco de dados inicializado")
        app.run(debug=True, host="0.0.0.0", port=5006)
    except Exception as e:
        print(f"Failed to start application: {e}")