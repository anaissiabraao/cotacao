from flask import Flask, render_template_string, request, jsonify, send_file
import requests
import math
import os
import datetime
import polyline
from fpdf import FPDF
import io
import pandas as pd

# Caminho do Excel
EXCEL_FILE = r"C:\Users\Usuário\OneDrive\Desktop\SQL data\Chico automate\fretes.db\Cidades por mesorregião_Com Transportadora.xlsx"

# Carregar transportadoras e cidades
xl = pd.ExcelFile(EXCEL_FILE)
df_transp = pd.read_excel(xl, nrows=5971, dtype=str)
transportadoras_ativas = df_transp[df_transp["STATUS"].isin(["SIM-OK", "ATIVO"])]

df_cidades = pd.read_excel(xl, skiprows=114)
df_cidades.columns = df_cidades.columns.astype(str).str.strip()

# Estrutura para TABELA_CUSTOS
TABELA_CUSTOS = {}
for _, row in df_cidades.iterrows():
    uf = row["UF"]
    municipio = row["Município"]
    if uf not in TABELA_CUSTOS:
        TABELA_CUSTOS[uf] = {}
    # Preencher com valores padrão se necessário
    valor = float(row["VALOR"]) if pd.notna(row["VALOR"]) else 36.58  # Valor padrão baseado no final do Excel
    excedente = float(row["EXCEDENTE"]) if pd.notna(row["EXCEDENTE"]) else 0.65
    peso_maximo = float(row["PESO MÁXIMO TRANSPORTADO"]) if pd.notna(row["PESO MÁXIMO TRANSPORTADO"]) else 2500
    prazo_eco = int(row["PRAZO ECO"]) if pd.notna(row["PRAZO ECO"]) else 5
    prazo_expresso = int(row["PRAZO EXPRESSO"]) if pd.notna(row["PRAZO EXPRESSO"]) else 2
    TABELA_CUSTOS[uf][municipio] = {
        "10kg": valor,
        "20kg": valor,
        "30kg": valor,
        "30kg": valor,  # Ajuste para 300kg
        "excedente": excedente,
        "peso_maximo": peso_maximo,
        "gris": 0.001,
        "prazo_econ": prazo_eco,
        "prazo_expresso": prazo_expresso,
        "fornecedor": "N/A",  # Será preenchido depois
        "zona_parceiro": row.get("ZONA PARCEIRO", "Interior"),
        "nova_zona": row.get("NOVA ZONA", "Interior"),
        "dfl": row.get("DFL", "Sim")
    }

# Associar transportadoras aos municípios
for uf, municipios in TABELA_CUSTOS.items():
    for municipio in municipios:
        # Encontrar transportadoras que atendem a UF
        transportadoras_uf = transportadoras_ativas[
            transportadoras_ativas["REF. CLIENTE"].str.contains(uf, na=False, case=False)
        ]
        if not transportadoras_uf.empty:
            TABELA_CUSTOS[uf][municipio]["fornecedor"] = transportadoras_uf.iloc[0]["TABELA"]
            
app = Flask(__name__)

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
    "4500-6000": {"VAN": 11000, "3/4": 14000, "TOCO": 17000, "TRUCK": 21000, "CARRETA": 27000},
}

# Histórico de pesquisas
HISTORICO_PESQUISAS = []

# --- Endpoints para Estados e Municípios (usando IBGE) ---
@app.route("/estados")
def estados():
    try:
        response = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados", timeout=10)
        response.raise_for_status()
        print("Estados carregados da API IBGE.")
        data = response.json()
        estados = [{"id": e["sigla"], "text": e["nome"]} for e in sorted(data, key=lambda x: x["nome"])]
        return jsonify(estados)
    except Exception as e:
        print(f"Erro ao carregar estados da API IBGE: {e}. Usando fallback.")
        return jsonify(ESTADOS_FALLBACK)

@app.route("/municipios/<uf>")
def municipios(uf):
    try:
        response = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios", timeout=10)
        response.raise_for_status()
        data = response.json()
        municipios = [{"id": m["nome"].upper(), "text": m["nome"].title()} for m in sorted(data, key=lambda x: x["nome"])]
        return jsonify(municipios)
    except Exception as e:
        print(f"Erro ao carregar municípios para UF {uf}: {e}")
        return jsonify([])

# --- Funções auxiliares para cálculo de distância (usadas por ambos os modos) ---
def geocode(municipio, uf):
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
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{origem[1]},{origem[0]};{destino[1]},{destino[0]}"
        response = requests.get(url, params={"overview": "full"}, timeout=15)
        data = response.json()
        if data.get("code") == "Ok" and data.get("routes"):
            route = data["routes"][0]
            distance = route["distance"] / 1000
            duration = route["duration"] / 60
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
            distance = segments.get("distance", 0) / 1000
            duration = segments.get("duration", 0) / 60
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
        (2500, 3000), (3000, 3500), (3500, 4000), (4000, 4500),
        (4500, 6000)
    ]
    for min_val, max_val in faixas:
        if min_val < distancia <= max_val:
            return f"{min_val}-{max_val}"
    return None

# --- Cálculo Fracionado usando TABELA_CUSTOS ---
def calcular_valor_fracionado(distancia, peso, cubagem):
    faixa = determinar_faixa(distancia)
    if not faixa:
        return None

    # Peso cubado (máximo entre peso real e cubagem * 300)
    peso_cubado = max(peso, cubagem * 300)

    # Escolher o veículo mais adequado com base no peso cubado
    if peso_cubado <= 500:
        veiculo = "VAN"
    elif peso_cubado <= 1000:
        veiculo = "3/4"
    elif peso_cubado <= 2000:
        veiculo = "TOCO"
    elif peso_cubado <= 4000:
        veiculo = "TRUCK"
    else:
        veiculo = "CARRETA"

    # Ajuste de custo com base no peso cubado (proporcional ao custo base do veículo)
    custo_base = TABELA_CUSTOS[faixa][veiculo]
    fator_peso = 1 + (peso_cubado / 1000) * 0.1  # Aumenta 10% a cada 1000 kg
    custo_final = custo_base * fator_peso

    return {
        "veiculo": veiculo,
        "custo": custo_final
    }

@app.route('/calcular_frete_fracionado', methods=['POST'])
def calcular_frete_fracionado():
    estado_origem = request.form.get('estado_origem')
    municipio_origem = request.form.get('municipio_origem')
    estado_destino = request.form.get('estado_destino')
    municipio_destino = request.form.get('municipio_destino')
    peso = float(request.form.get('peso'))
    cubagem = float(request.form.get('cubagem'))

    # Filtrar dados de origem e destino
    origem_data = TABELA_CUSTOS.get(estado_origem, {}).get(municipio_origem, {})
    destino_data = TABELA_CUSTOS.get(estado_destino, {}).get(municipio_destino, {})

    if not origem_data or not destino_data:
        return render_template('index.html', erro="Origem ou destino não encontrados na tabela de custos.")

    # Calcular custo baseado no peso
    if peso <= 10:
        custo_base = origem_data.get("10kg", 0) + destino_data.get("10kg", 0)
    elif peso <= 20:
        custo_base = origem_data.get("20kg", 0) + destino_data.get("20kg", 0)
    elif peso <= 30:
        custo_base = origem_data.get("30kg", 0) + destino_data.get("30kg", 0)
    elif peso <= 300:
        custo_base = origem_data.get("300kg", 0) + destino_data.get("300kg", 0)
    else:
        custo_base = origem_data.get("300kg", 0) + destino_data.get("300kg", 0)
        excedente_kg = max(0, peso - min(origem_data.get("peso_maximo", 2500), destino_data.get("peso_maximo", 2500)))
        custo_base += excedente_kg * (origem_data.get("excedente", 0) + destino_data.get("excedente", 0))

    # Ajustar por cubagem
    if cubagem > 0:
        custo_base += cubagem * 500  # Exemplo: custo adicional por m³

    # Resultado
    resultado = {
        "valor": round(custo_base, 2),
        "uf_origem": estado_origem,
        "fornecedor_origem": origem_data.get("fornecedor", "N/A"),
        "zona_parceiro_origem": origem_data.get("zona_parceiro", "N/A"),
        "nova_zona_origem": origem_data.get("nova_zona", "N/A"),
        "cidades_origem": municipio_origem,
        "valor_min_10kg_origem": origem_data.get("10kg", 0),
        "20kg_origem": origem_data.get("20kg", 0),
        "30kg_origem": origem_data.get("30kg", 0),
        "300kg_origem": origem_data.get("300kg", 0),
        "excedente_origem": origem_data.get("excedente", 0),
        "peso_maximo_origem": origem_data.get("peso_maximo", 0),
        "gris_origem": origem_data.get("gris", 0),
        "prazo_econ_origem": origem_data.get("prazo_econ", 0),
        "prazo_expresso_origem": origem_data.get("prazo_expresso", 0),
        "dfl_origem": origem_data.get("dfl", "N/A"),
        "uf_destino": estado_destino,
        "fornecedor_destino": destino_data.get("fornecedor", "N/A"),
        "zona_parceiro_destino": destino_data.get("zona_parceiro", "N/A"),
        "nova_zona_destino": destino_data.get("nova_zona", "N/A"),
        "cidades_destino": municipio_destino,
        "valor_min_10kg_destino": destino_data.get("10kg", 0),
        "20kg_destino": destino_data.get("20kg", 0),
        "30kg_destino": destino_data.get("30kg", 0),
        "300kg_destino": destino_data.get("300kg", 0),
        "excedente_destino": destino_data.get("excedente", 0),
        "peso_maximo_destino": destino_data.get("peso_maximo", 0),
        "gris_destino": destino_data.get("gris", 0),
        "prazo_econ_destino": destino_data.get("prazo_econ", 0),
        "prazo_expresso_destino": destino_data.get("prazo_expresso", 0),
        "dfl_destino": destino_data.get("dfl", "N/A"),
        "veiculo": "Carreta"
    }

    return render_template('index.html', resultado=resultado)

# --- Funções para o cálculo Dedicado ---
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

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

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
        return jsonify({"error": "Distância fora da faixa suportada (acima de 6000 km)"}), 400
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
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PortoEx - Cotação Controladoria</title>
  <!-- Frameworks e Libs -->
  <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet"/>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css"/>
  <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
  <style>
    body {
      font-family: 'Roboto', sans-serif;
      margin: 0;
      padding: 0;
      background: linear-gradient(135deg, #f0f4f8 0%, #d9e6f2 100%);
      color: #333;
      min-height: 100vh;
      display: flex;
      justify-content: center;
      align-items: center;
      transition: background 0.3s ease;
    }
    body.dark {
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      color: #e0e0e0;
    }
    .container {
      max-width: 900px;
      background: rgba(255, 255, 255, 0.9);
      padding: 30px;
      border-radius: 10px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      border: 1px solid rgba(0, 123, 255, 0.1);
      margin: 20px;
      transition: background 0.3s ease, box-shadow 0.3s ease, border 0.3s ease;
    }
    body.dark .container {
      background: rgba(26, 26, 46, 0.9);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      border: 1px solid rgba(0, 123, 255, 0.2);
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }
    .header h2 {
      font-size: 24px;
      color: #007bff;
      transition: color 0.3s ease;
    }
    body.dark .header h2 {
      color: #007bff;
    }
    .header-buttons {
      display: flex;
      gap: 10px;
      align-items: center;
    }
    .theme-btn {
      background: transparent;
      border: none;
      color: #007bff;
      font-size: 1rem;
      cursor: pointer;
      transition: color 0.3s ease, transform 0.1s ease;
    }
    body.dark .theme-btn {
      color: #007bff;
    }
    .theme-btn:hover {
      color: #ff6200;
      transform: scale(1.1);
    }
    .consulta-btn {
      text-decoration: none;
      padding: 5px 10px;
      border-radius: 5px;
      background: rgba(0, 123, 255, 0.1);
      color: #007bff;
      transition: background 0.3s ease, color 0.3s ease, transform 0.1s ease;
    }
    body.dark .consulta-btn {
      background: rgba(0, 123, 255, 0.2);
      color: #007bff;
    }
    .consulta-btn:hover {
      background: rgba(0, 123, 255, 0.2);
      color: #ff6200;
      transform: scale(1.1);
    }
    .tabs {
      display: flex;
      border-bottom: 2px solid #007bff;
      margin-bottom: 20px;
      transition: border-bottom 0.3s ease;
    }
    body.dark .tabs {
      border-bottom: 2px solid #007bff;
    }
    .tab {
      padding: 10px 20px;
      cursor: pointer;
      background: rgba(0, 123, 255, 0.05);
      color: #333;
      transition: all 0.3s ease;
    }
    body.dark .tab {
      background: rgba(0, 123, 255, 0.1);
      color: #e0e0e0;
    }
    .tab.active {
      background: #007bff;
      color: #fff;
      box-shadow: 0 2px 4px rgba(0, 123, 255, 0.3);
      transform: translateY(-2px);
    }
    body.dark .tab.active {
      background: #007bff;
      color: #fff;
    }
    .tab-content {
      display: none;
    }
    .tab-content.active {
      display: block;
    }
    .section {
      margin: 20px 0;
    }
    .row {
      display: flex;
      gap: 20px;
      margin-bottom: 15px;
      flex-wrap: wrap;
    }
    .field {
      flex: 1;
      min-width: 200px;
    }
    label {
      display: block;
      margin-bottom: 5px;
      color: #555;
      font-size: 14px;
      transition: color 0.3s ease;
    }
    body.dark label {
      color: #b0bec5;
    }
    select, input {
      width: 100%;
      padding: 10px;
      border: 1px solid rgba(0, 123, 255, 0.2);
      border-radius: 5px;
      background: #fff;
      color: #333;
      transition: border 0.3s ease, box-shadow 0.3s ease;
    }
    body.dark select, body.dark input {
      background: #2a2a44;
      color: #e0e0e0;
      border: 1px solid rgba(0, 123, 255, 0.3);
    }
    select:focus, input:focus {
      border-color: #007bff;
      box-shadow: 0 0 5px rgba(0, 123, 255, 0.3);
      outline: none;
    }
    body.dark select:focus, body.dark input:focus {
      border-color: #007bff;
      box-shadow: 0 0 5px rgba(0, 123, 255, 0.5);
    }
    .select2-container--classic .select2-selection--single {
      background: #fff;
      border: 1px solid rgba(0, 123, 255, 0.2);
      color: #333;
      border-radius: 5px;
      height: 38px;
      padding: 5px;
      transition: border 0.3s ease, box-shadow 0.3s ease;
    }
    body.dark .select2-container--classic .select2-selection--single {
      background: #2a2a44;
      border: 1px solid rgba(0, 123, 255, 0.3);
      color: #e0e0e0;
    }
    .select2-container--classic .select2-selection--single:focus {
      border-color: #007bff;
      box-shadow: 0 0 5px rgba(0, 123, 255, 0.3);
    }
    body.dark .select2-container--classic .select2-selection--single:focus {
      border-color: #007bff;
      box-shadow: 0 0 5px rgba(0, 123, 255, 0.5);
    }
    .select2-container--classic .select2-selection__rendered {
      color: #333;
      line-height: 28px;
      transition: color 0.3s ease;
    }
    body.dark .select2-container--classic .select2-selection__rendered {
      color: #e0e0e0;
    }
    .select2-container--classic .select2-selection__arrow {
      background: transparent;
      border: none;
      height: 38px;
    }
    button {
      background: linear-gradient(90deg, #007bff, #ff6200);
      color: #fff;
      padding: 10px 20px;
      border: none;
      border-radius: 5px;
      cursor: pointer;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      position: relative;
      overflow: hidden;
    }
    button:hover {
      transform: scale(1.05);
      box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
    }
    button:active {
      transform: scale(0.95);
    }
    body.dark button {
      background: linear-gradient(90deg, #007bff, #ff6200);
    }
    .error {
      color: #dc3545;
      margin-top: 10px;
      font-size: 14px;
      transition: color 0.3s ease;
    }
    body.dark .error {
      color: #ff6b6b;
    }
    .modal {
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.5);
      justify-content: center;
      align-items: center;
      z-index: 1000;
      transition: background 0.3s ease;
    }
    body.dark .modal {
      background: rgba(0, 0, 0, 0.7);
    }
    .modal-content {
      background: #fff;
      padding: 20px;
      border-radius: 10px;
      width: 400px;
      text-align: center;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      transition: background 0.3s ease, box-shadow 0.3s ease;
    }
    body.dark .modal-content {
      background: #2a2a44;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    .modal-content h3 {
      color: #007bff;
      margin-bottom: 15px;
      transition: color 0.3s ease;
    }
    body.dark .modal-content h3 {
      color: #007bff;
    }
    .modal-content p {
      margin: 10px 0;
      color: #333;
      transition: color 0.3s ease;
    }
    body.dark .modal-content p {
      color: #e0e0e0;
    }
    .modal-content button {
      margin: 5px;
    }
    #map {
      width: 100%;
      height: 300px;
      border-radius: 10px;
      margin-top: 15px;
    }
    .pbi-container {
      background: #fff;
      padding: 20px;
      border-radius: 10px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      transition: background 0.3s ease, box-shadow 0.3s ease;
      max-width: 1400px;
      width: 100%;
      margin: 0 auto;
    }
    body.dark .pbi-container {
      background: #2a2a44;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    .pbi-container iframe {
      width: 100%;
      height: 1000px;
      border: none;
      border-radius: 10px;
    }
    .shortcuts {
      display: flex;
      justify-content: center;
      gap: 15px;
      margin-top: 20px;
      flex-wrap: wrap;
    }
    .shortcut-btn {
      background: linear-gradient(90deg, #007bff, #ff6200);
      color: #fff;
      padding: 10px 20px;
      border-radius: 5px;
      text-decoration: none;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .shortcut-btn:hover {
      transform: scale(1.05);
      box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
    }
    .shortcut-btn:active {
      transform: scale(0.95);
    }
    body.dark .shortcut-btn {
      background: linear-gradient(90deg, #007bff, #ff6200);
    }
    .footer {
      text-align: center;
      padding: 10px 0;
      margin-top: 20px;
      background: rgba(0, 123, 255, 0.05);
      border-radius: 5px;
      font-size: 14px;
      color: #555;
      transition: background 0.3s ease, color 0.3s ease;
    }
    body.dark .footer {
      background: rgba(0, 123, 255, 0.1);
      color: #b0bec5;
    }
    .resultado-info {
      margin-top: 15px;
    }
    .resultado-info p {
      margin: 5px 0;
      color: #333;
      transition: color 0.3s ease;
    }
    body.dark .resultado-info p {
      color: #e0e0e0;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 15px;
      background: rgba(0, 123, 255, 0.05);
      border-radius: 5px;
      overflow: hidden;
      transition: background 0.3s ease;
    }
    body.dark table {
      background: rgba(0, 123, 255, 0.1);
    }
    th, td {
      padding: 10px;
      text-align: left;
      color: #333;
      transition: color 0.3s ease;
    }
    body.dark th, body.dark td {
      color: #e0e0e0;
    }
    th {
      background: linear-gradient(90deg, #007bff, #ff6200);
      color: #fff;
    }
    body.dark th {
      background: linear-gradient(90deg, #007bff, #ff6200);
    }
    tr:nth-child(even) {
      background: rgba(0, 123, 255, 0.02);
      transition: background 0.3s ease;
    }
    body.dark tr:nth-child(even) {
      background: rgba(0, 123, 255, 0.03);
    }
    #fracionado-resultado h3 {
      color: #007bff;
      margin-top: 0;
      transition: color 0.3s ease;
    }
    body.dark #fracionado-resultado h3 {
      color: #007bff;
    }
    .spinner {
      display: none;
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 24px;
      color: #ff6200;
    }
    button:disabled .spinner {
      display: block;
    }
    button:disabled {
      opacity: 0.7;
      cursor: not-allowed;
    }
    .best-price {
      background: #d4edda;
      font-weight: bold;
    }
    body.dark .best-price {
      background: #155724;
      color: #fff;
    }
    .worst-price {
      background: #f8d7da;
      font-weight: bold;
    }
    body.dark .worst-price {
      background: #721c24;
      color: #fff;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h2><i class="fa-solid fa-truck-fast"></i> PortoEx - Cotação Controladoria</h2>
      <div class="header-buttons">
        <button id="theme-toggle" class="theme-btn" title="Alternar tema">
          <i class="fa-solid fa-moon" id="theme-icon"></i>
        </button>
        <a href="https://onedrive.live.com/?id=7D2F1EE6EAD699A1%21s3c277927e98244b3a012f3122abe84a5&cid=7D2F1EE6EAD699A1&sb=name&sd=1" target="_blank" class="consulta-btn">
          <i class="fa-solid fa-table-list"></i> Consultar Tabela de Agentes
        </a>
      </div>
    </div>
    <div class="tabs">
      <div class="tab active" data-tab="dedicado">Dedicado</div>
      <div class="tab" data-tab="fracionado">Fracionado</div>
      <div class="tab" data-tab="dashboard">Dashboard</div>
    </div>
    <!-- Dedicado -->
    <div class="section tab-content active" id="tab-dedicado">
      <div class="row">
        <div class="field">
          <label for="uf_origem">Estado de Origem</label>
          <select id="uf_origem" class="select2-enable"></select>
        </div>
        <div class="field">
          <label for="uf_destino">Estado de Destino</label>
          <select id="uf_destino" class="select2-enable"></select>
        </div>
      </div>
      <div class="row">
        <div class="field">
          <label for="municipio_origem">Município de Origem</label>
          <select id="municipio_origem" class="select2-enable" disabled></select>
        </div>
        <div class="field">
          <label for="municipio_destino">Município de Destino</label>
          <select id="municipio_destino" class="select2-enable" disabled></select>
        </div>
      </div>
      <div class="row">
        <div class="field">
          <label for="peso">Peso (kg) - Opcional</label>
          <input type="number" id="peso" value="" min="0" step="0.01" placeholder="Informe o peso (opcional)">
        </div>
        <div class="field">
          <label for="cubagem">Cubagem (m³) - Opcional</label>
          <input type="number" id="cubagem" value="" min="0" step="0.01" placeholder="Informe a cubagem (opcional)">
        </div>
      </div>
      <button id="btn_calcular">
        Calcular Custos
        <i class="fa-solid fa-spinner spinner" aria-hidden="true"></i>
      </button>
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
          <p><strong>Peso informado:</strong> <span id="res-peso"></span></p>
          <p><strong>Cubagem informada:</strong> <span id="res-cubagem"></span></p>
        </div>
        <button id="btn_gerar_pdf">Salvar Relatório em PDF</button>
      </div>
    </div>
    <!-- Fracionado -->
    <div class="section tab-content" id="tab-fracionado">
      <div class="row">
        <div class="field">
          <label for="uf_origem_frac">Estado de Origem</label>
          <select id="uf_origem_frac" class="select2-enable"></select>
        </div>
        <div class="field">
          <label for="uf_destino_frac">Estado de Destino</label>
          <select id="uf_destino_frac" class="select2-enable"></select>
        </div>
      </div>
      <div class="row">
        <div class="field">
          <label for="municipio_origem_frac">Município de Origem</label>
          <select id="municipio_origem_frac" class="select2-enable" disabled></select>
        </div>
        <div class="field">
          <label for="municipio_destino_frac">Município de Destino</label>
          <select id="municipio_destino_frac" class="select2-enable" disabled></select>
        </div>
      </div>
      <div class="row">
        <div class="field">
          <label for="peso-frac">Peso (kg)</label>
          <input type="number" id="peso-frac" value="10" min="0" step="0.01">
        </div>
        <div class="field">
          <label for="cubagem-frac">Cubagem (m³)</label>
          <input type="number" id="cubagem-frac" value="0.05" min="0" step="0.01">
        </div>
      </div>
      <button id="btn-fracionado">
        Calcular Lista de Agentes
        <i class="fa-solid fa-spinner spinner" aria-hidden="true"></i>
      </button>
      <div id="fracionado-resultado"></div>
    </div>
    <!-- Dashboard -->
    <div class="section tab-content" id="tab-dashboard">
      <div class="pbi-container">
        <iframe src="https://app.powerbi.com/view?r=eyJrIjoiYWUzODBiYmUtMWI1OC00NGVjLWFjNDYtYzYyMDQ3MzQ0MTQ0IiwidCI6IjM4MjViNTlkLTY1ZGMtNDM1Zi04N2M4LTkyM2QzMzkxYzMyOCJ9" allowfullscreen="true"></iframe>
      </div>
      <div class="shortcuts">
        <a href="#" onclick="window.scrollTo({top: 0, behavior: 'smooth'})" class="shortcut-btn">
          <i class="fa-solid fa-arrow-up"></i> Voltar ao Início
        </a>
        <a href="https://onedrive.live.com/?id=7D2F1EE6EAD699A1%21s3c277927e98244b3a012f3122abe84a5&cid=7D2F1EE6EAD699A1&sb=name&sd=1" target="_blank" class="shortcut-btn">
          <i class="fa-solid fa-table-list"></i> Consultar Tabela de Agentes
        </a>
        <a href="https://app.powerbi.com/view?r=eyJrIjoiYWUzODBiYmUtMWI1OC00NGVjLWFjNDYtYzYyMDQ3MzQ0MTQ0IiwidCI6IjM4MjViNTlkLTY1ZGMtNDM1Zi04N2M4LTkyM2QzMzkxYzMyOCJ9" target="_blank" class="shortcut-btn">
          <i class="fa-solid fa-chart-line"></i> Abrir Dashboard no Power BI
        </a>
      </div>
      <div class="footer">
        Desenvolvido por: Abraão Anaissi - PortoEx
      </div>
    </div>
  </div>

  <!-- Modal de Resultados (usado apenas para Fracionado) -->
  <div id="modal" class="modal">
    <div class="modal-content">
      <h3>Resultado da Cotação</h3>
      <p><strong>Origem:</strong> <span id="modalOrigem"></span></p>
      <p><strong>Destino:</strong> <span id="modalDestino"></span></p>
      <p><strong>Peso:</strong> <span id="modalPeso"></span> kg</p>
      <p><strong>Cubagem:</strong> <span id="modalCubagem"></span> m³</p>
      <p><strong>Transportadora:</strong> <span id="modalTransportadora"></span></p>
      <p><strong>Custo Total:</strong> R$ <span id="modalCusto"></span></p>
      <p><strong>Prazo:</strong> <span id="modalPrazo"></span></p>
      <button onclick="exportarPDF()">Exportar PDF</button>
      <button onclick="fecharModal()">Fechar</button>
    </div>
  </div>

  <script>
    let map;
    let routeLayer;

    // Tabela de custos (dedicado)
    const TABELA_CUSTOS = {
      "0-20": { "VAN": 250, "3/4": 350, "TOCO": 450, "TRUCK": 550, "CARRETA": 1000 },
      "20-50": { "VAN": 350, "3/4": 450, "TOCO": 550, "TRUCK": 700, "CARRETA": 1500 },
      "50-100": { "VAN": 600, "3/4": 900, "TOCO": 1200, "TRUCK": 1500, "CARRETA": 2100 },
      "100-150": { "VAN": 800, "3/4": 1100, "TOCO": 1500, "TRUCK": 1800, "CARRETA": 2600 },
      "150-200": { "VAN": 1000, "3/4": 1500, "TOCO": 1800, "TRUCK": 2100, "CARRETA": 3000 },
      "200-250": { "VAN": 1300, "3/4": 1800, "TOCO": 2100, "TRUCK": 2500, "CARRETA": 3300 },
      "250-300": { "VAN": 1500, "3/4": 2100, "TOCO": 2500, "TRUCK": 2800, "CARRETA": 3800 },
      "300-400": { "VAN": 1800, "3/4": 2500, "TOCO": 2800, "TRUCK": 3300, "CARRETA": 4300 },
      "400-600": { "VAN": 2100, "3/4": 2900, "TOCO": 3500, "TRUCK": 3800, "CARRETA": 4800 },
      "600-800": { "VAN": 2500, "3/4": 3300, "TOCO": 4000, "TRUCK": 4500, "CARRETA": 5500 },
      "800-1000": { "VAN": 2900, "3/4": 3700, "TOCO": 4500, "TRUCK": 5200, "CARRETA": 6200 },
      "1000-1500": { "VAN": 3500, "3/4": 4500, "TOCO": 5500, "TRUCK": 6500, "CARRETA": 8000 },
      "1500-2000": { "VAN": 4500, "3/4": 5800, "TOCO": 7000, "TRUCK": 8500, "CARRETA": 10500 },
      "2000-2500": { "VAN": 5500, "3/4": 7100, "TOCO": 8500, "TRUCK": 10500, "CARRETA": 13000 },
      "2500-3000": { "VAN": 6500, "3/4": 8400, "TOCO": 10000, "TRUCK": 12500, "CARRETA": 15500 },
      "3000-3500": { "VAN": 7500, "3/4": 9700, "TOCO": 11500, "TRUCK": 14500, "CARRETA": 18000 },
      "3500-4000": { "VAN": 8500, "3/4": 11000, "TOCO": 13000, "TRUCK": 16500, "CARRETA": 20500 },
      "4000-4500": { "VAN": 9500, "3/4": 12300, "TOCO": 14500, "TRUCK": 18500, "CARRETA": 23000 },
      "4500-6000": { "VAN": 11000, "3/4": 14000, "TOCO": 17000, "TRUCK": 21000, "CARRETA": 27000 },
    };

    // Função para determinar a faixa de distância
    function determinarFaixa(distancia) {
      const faixas = [
        [0, 20], [20, 50], [50, 100], [100, 150], [150, 200],
        [200, 250], [250, 300], [300, 400], [400, 600], [600, 800],
        [800, 1000], [1000, 1500], [1500, 2000], [2000, 2500],
        [2500, 3000], [3000, 3500], [3500, 4000], [4000, 4500],
        [4500, 6000]
      ];
      for (let i = 0; i < faixas.length; i++) {
        const [minVal, maxVal] = faixas[i];
        if (minVal < distancia && distancia <= maxVal) {
          return `${minVal}-${maxVal}`;
        }
      }
      return null;
    }

    // Dados mockados da planilha Base_Agentes
    const baseAgentes = [
      { UF: "SC", FORNECEDOR: "Transportadora A", ZONA_PARCEIRO: "Sul", NOVA_ZONA: "Sul", CIDADES: "Itajaí, Florianópolis", VALOR_MINIMO_ATE_10kg: 10.0, "20kg": 15.0, "30kg": 20.0, "300kg": 150.0, EXCEDENTE: 0.5, PESO_MAXIMO_TRANSPORTADO: 5000, GRIS: "Sim", PRAZO_ECON: "2 dias", PRAZO_EXPRESSO: "1 dia", DFL: "Não", STATUS: "Ativo" },
      { UF: "SC", FORNECEDOR: "Transportadora B", ZONA_PARCEIRO: "Sul", NOVA_ZONA: "Sul", CIDADES: "Itajaí, Blumenau", VALOR_MINIMO_ATE_10kg: 12.0, "20kg": 18.0, "30kg": 25.0, "300kg": 180.0, EXCEDENTE: 0.6, PESO_MAXIMO_TRANSPORTADO: 4000, GRIS: "Não", PRAZO_ECON: "3 dias", PRAZO_EXPRESSO: "2 dias", DFL: "Sim", STATUS: "Ativo" },
      { UF: "SP", FORNECEDOR: "Transportadora C", ZONA_PARCEIRO: "Sudeste", NOVA_ZONA: "Sudeste", CIDADES: "São Paulo, Campinas", VALOR_MINIMO_ATE_10kg: 15.0, "20kg": 22.0, "30kg": 30.0, "300kg": 200.0, EXCEDENTE: 0.7, PESO_MAXIMO_TRANSPORTADO: 6000, GRIS: "Sim", PRAZO_ECON: "2 dias", PRAZO_EXPRESSO: "1 dia", DFL: "Não", STATUS: "Ativo" },
      { UF: "RJ", FORNECEDOR: "Transportadora D", ZONA_PARCEIRO: "Sudeste", NOVA_ZONA: "Sudeste", CIDADES: "Rio de Janeiro, Niterói", VALOR_MINIMO_ATE_10kg: 14.0, "20kg": 20.0, "30kg": 28.0, "300kg": 190.0, EXCEDENTE: 0.65, PESO_MAXIMO_TRANSPORTADO: 5500, GRIS: "Sim", PRAZO_ECON: "2 dias", PRAZO_EXPRESSO: "1 dia", DFL: "Sim", STATUS: "Ativo" }
    ];

    // Inicializar o mapa
    function initMap() {
      map = L.map('map').setView([-15.77972, -47.92972], 5);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(map);
    }

    // Desenhar rota no mapa
    function drawRoute(points) {
      if (routeLayer) {
        map.removeLayer(routeLayer);
      }
      if (!points || points.length < 2) {
        $("#map").hide();
        return;
      }
      routeLayer = L.polyline(points, { color: '#007bff', weight: 5, opacity: 0.7 }).addTo(map);
      const origem = points[0];
      const destino = points[points.length - 1];
      L.marker(origem).addTo(map).bindPopup('Origem').openPopup();
      L.marker(destino).addTo(map).bindPopup('Destino');
      map.fitBounds(routeLayer.getBounds(), { padding: [50, 50] });
      $("#map").show();
    }

    // Tema claro/escuro
    function toggleTheme() {
      const isDark = document.body.classList.contains("dark");
      if (isDark) {
        document.body.classList.remove("dark");
        document.getElementById("theme-icon").classList.replace("fa-sun", "fa-moon");
        localStorage.setItem("theme", "light");
      } else {
        document.body.classList.add("dark");
        document.getElementById("theme-icon").classList.replace("fa-moon", "fa-sun");
        localStorage.setItem("theme", "dark");
      }
    }

    $(document).ready(function () {
      // Inicializar o mapa
      initMap();

      // Tema
      const savedTheme = localStorage.getItem("theme") || "light";
      if (savedTheme === "dark") {
        document.body.classList.add("dark");
        document.getElementById("theme-icon").classList.replace("fa-moon", "fa-sun");
      }
      $("#theme-toggle").on("click", toggleTheme);

      // Abas
      $(".tab").on("click", function() {
        $(".tab").removeClass("active");
        $(this).addClass("active");
        $(".tab-content").removeClass("active");
        $("#tab-" + $(this).data("tab")).addClass("active");
      });

      // Select2 para estados e municípios (Dedicado)
      $("#uf_origem").select2({
        placeholder: "Selecione o estado",
        allowClear: true,
        theme: "classic",
        ajax: {
          url: "/estados",
          dataType: "json",
          delay: 250,
          processResults: function (data) {
            return {
              results: data
            };
          },
          cache: true
        }
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
              url: `/municipios/${uf}`,
              dataType: "json",
              delay: 250,
              processResults: function (data) {
                return {
                  results: data
                };
              },
              cache: true
            }
          });
        } else {
          $("#municipio_origem").select2("destroy");
        }
      });

      $("#uf_destino").select2({
        placeholder: "Selecione o estado",
        allowClear: true,
        theme: "classic",
        ajax: {
          url: "/estados",
          dataType: "json",
          delay: 250,
          processResults: function (data) {
            return {
              results: data
            };
          },
          cache: true
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
              url: `/municipios/${uf}`,
              dataType: "json",
              delay: 250,
              processResults: function (data) {
                return {
                  results: data
                };
              },
              cache: true
            }
          });
        } else {
          $("#municipio_destino").select2("destroy");
        }
      });

      // Select2 para estados e municípios (Fracionado)
      $("#uf_origem_frac").select2({
        placeholder: "Selecione o estado",
        allowClear: true,
        theme: "classic",
        ajax: {
          url: "/estados",
          dataType: "json",
          delay: 250,
          processResults: function (data) {
            return {
              results: data
            };
          },
          cache: true
        }
      });
      $("#uf_origem_frac").on("change", function () {
        var uf = $(this).val();
        $("#municipio_origem_frac").val(null).trigger("change");
        $("#municipio_origem_frac").prop("disabled", !uf);
        if (uf) {
          $("#municipio_origem_frac").select2({
            placeholder: "Selecione o município",
            allowClear: true,
            theme: "classic",
            ajax: {
              url: `/municipios/${uf}`,
              dataType: "json",
              delay: 250,
              processResults: function (data) {
                return {
                  results: data
                };
              },
              cache: true
            }
          });
        } else {
          $("#municipio_origem_frac").select2("destroy");
        }
      });

      $("#uf_destino_frac").select2({
        placeholder: "Selecione o estado",
        allowClear: true,
        theme: "classic",
        ajax: {
          url: "/estados",
          dataType: "json",
          delay: 250,
          processResults: function (data) {
            return {
              results: data
            };
          },
          cache: true
        }
      });
      $("#uf_destino_frac").on("change", function () {
        var uf = $(this).val();
        $("#municipio_destino_frac").val(null).trigger("change");
        $("#municipio_destino_frac").prop("disabled", !uf);
        if (uf) {
          $("#municipio_destino_frac").select2({
            placeholder: "Selecione o município",
            allowClear: true,
            theme: "classic",
            ajax: {
              url: `/municipios/${uf}`,
              dataType: "json",
              delay: 250,
              processResults: function (data) {
                return {
                  results: data
                };
              },
              cache: true
            }
          });
        } else {
          $("#municipio_destino_frac").select2("destroy");
        }
      });

      // Botão calcular (Dedicado)
      $("#btn_calcular").on("click", function () {
        const button = $(this);
        button.prop("disabled", true);
        const ufOrigem = $("#uf_origem").val();
        const munOrigem = $("#municipio_origem").val();
        const ufDestino = $("#uf_destino").val();
        const munDestino = $("#municipio_destino").val();
        const peso = parseFloat($("#peso").val()) || 0;
        const cubagem = parseFloat($("#cubagem").val()) || 0;

        if (!ufOrigem || !munOrigem || !ufDestino || !munDestino) {
          alert("Por favor, selecione origem e destino.");
          button.prop("disabled", false);
          return;
        }

        $.ajax({
          url: "/calcular",
          method: "POST",
          contentType: "application/json",
          data: JSON.stringify({
            uf_origem: ufOrigem,
            municipio_origem: munOrigem,
            uf_destino: ufDestino,
            municipio_destino: munDestino,
            peso: peso,
            cubagem: cubagem
          }),
          success: function (data) {
            $("#res-origem").text(`${munOrigem} - ${ufOrigem}`);
            $("#res-destino").text(`${munDestino} - ${ufDestino}`);
            $("#res-distancia").text(data.distancia);
            $("#res-tempo").text(`${Math.floor(data.duracao / 60)}h ${Math.round(data.duracao % 60)}min`);
            $("#res-consumo").text((data.distancia / 10).toFixed(2));
            $("#res-co2").text(((data.distancia / 10) * 2.3).toFixed(2));
            $("#res-pedagio").text((data.distancia * 0.15).toFixed(2));
            $("#res-peso").text(peso > 0 ? `${peso.toFixed(2)} kg` : "Não informado");
            $("#res-cubagem").text(cubagem > 0 ? `${cubagem.toFixed(2)} m³` : "Não informado");

            let htmlTabela = "";
            for (let tipo in data.custos) {
              htmlTabela += `<tr><td>${tipo}</td><td>R$ ${data.custos[tipo].toLocaleString("pt-BR", {minimumFractionDigits: 2})}</td></tr>`;
            }
            $("#tabela-resultado").html(htmlTabela);
            $("#resultados").show();
            drawRoute(data.rota_pontos);
            button.prop("disabled", false);
          },
          error: function (xhr) {
            alert(xhr.responseJSON?.error || "Erro ao calcular.");
            button.prop("disabled", false);
          }
        });
      });

      // Botão gerar PDF (Dedicado)
      $("#btn_gerar_pdf").on("click", function () {
        $.ajax({
          url: "/gerar-pdf",
          method: "POST",
          contentType: "application/json",
          data: JSON.stringify({
            analise: {
              origem: $("#res-origem").text(),
              destino: $("#res-destino").text(),
              distancia: parseFloat($("#res-distancia").text()),
              tempo_estimado: $("#res-tempo").text(),
              consumo_combustivel: parseFloat($("#res-consumo").text()),
              emissao_co2: parseFloat($("#res-co2").text()),
              pedagio_estimado: parseFloat($("#res-pedagio").text()),
              custos: Object.fromEntries(
                $("#tabela-resultado tr").map((i, row) => [
                  $(row).find("td").eq(0).text(),
                  parseFloat($(row).find("td").eq(1).text().replace("R$ ", "").replace(".", "").replace(",", "."))
                ]).get()
              ),
              provider: "OSRM",
              data_hora: new Date().toLocaleString("pt-BR")
            }
          }),
          xhrFields: {
            responseType: 'blob'
          },
          success: function (data) {
            const url = window.URL.createObjectURL(new Blob([data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `relatorio_transporte_${new Date().toISOString().replace(/[:.]/g, "_")}.pdf`);
            document.body.appendChild(link);
            link.click();
            link.remove();
          },
          error: function (xhr) {
            alert("Erro ao gerar PDF.");
          }
        });
      });

      // Botão calcular (Fracionado)
      $("#btn-fracionado").on("click", function () {
        const button = $(this);
        button.prop("disabled", true);
        const formData = new FormData();
        formData.append("estado_origem", $("#uf_origem_frac").val());
        formData.append("municipio_origem", $("#municipio_origem_frac").val());
        formData.append("estado_destino", $("#uf_destino_frac").val());
        formData.append("municipio_destino", $("#municipio_destino_frac").val());
        formData.append("peso", parseFloat($("#peso-frac").val()) || 35);
        formData.append("cubagem", parseFloat($("#cubagem-frac").val()) || 0.05);

        $.ajax({
          url: "/calcular_frete_fracionado",
          method: "POST",
          data: formData,
          processData: false,
          contentType: false,
          success: function (data) {
            $("#fracionado-resultado").html($(data).find("#fracionado-resultado").html());
            button.prop("disabled", false);
          },
          error: function (xhr) {
            $("#fracionado-resultado").html("<p style='color: #dc3545;'>Erro ao calcular.</p>");
            button.prop("disabled", false);
          }
        });
      });
    });

    function fecharModal() {
      $("#modal").css("display", "none");
    }

    function exportarPDF() {
      const { jsPDF } = window.jspdf;
      const doc = new jsPDF();

      doc.setFontSize(16);
      doc.text("PortoEx - Cotação Fracionada", 20, 20);
      doc.setFontSize(12);
      doc.text(`Origem: ${$("#modalOrigem").text()}`, 20, 30);
      doc.text(`Destino: ${$("#modalDestino").text()}`, 20, 40);
      doc.text(`Peso: ${$("#modalPeso").text()} kg`, 20, 50);
      doc.text(`Cubagem: ${$("#modalCubagem").text()} m³`, 20, 60);
      doc.text(`Transportadora: ${$("#modalTransportadora").text()}`, 20, 70);
      doc.text(`Custo Total: R$ ${$("#modalCusto").text()}`, 20, 80);
      doc.text(`Prazo: ${$("#modalPrazo").text()}`, 20, 90);

      doc.save('cotacao_fracionado.pdf');
    }
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    try:
        print("Iniciando servidor Flask...")
        app.run(debug=True, host="0.0.0.0", port=5006)
    except Exception as e:
        print(f"Falha ao iniciar a aplicação: {e}")
        raise