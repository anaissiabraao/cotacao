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
import uuid

def normalizar_cidade(cidade):
    # Remove acentos e caracteres especiais, converte para maiúsculas e normaliza espaços
    cidade = ''.join(c for c in unicodedata.normalize('NFD', cidade) if unicodedata.category(c) != 'Mn')
    cidade = re.sub(r'[^a-zA-Z0-9\s]', '', cidade).strip().upper()
    return re.sub(r'\s+', ' ', cidade)

app = Flask(__name__)

# Caminho do Excel
EXCEL_FILE = r"C:\Users\Usuário\OneDrive\Desktop\SQL data\Chico automate\consolidated_data.xlsx"  # Atualizar conforme o update do Seu Francisco

# Carregar transportadoras e cidades
xl = pd.ExcelFile(EXCEL_FILE)
df_transp = pd.read_excel(xl, nrows=5971, dtype=str)
print("Colunas do df_transp:", df_transp.columns.tolist())  # Depuração
transportadoras_ativas = df_transp[df_transp["STATUS"].isin(["SIM-OK", "ATIVO"])]

df_cidades = pd.read_excel(xl, skiprows=114, header=None)
df_cidades.columns = [
    'UF Origem', 'Cidade Origem', 'UF Destino', 'Cidade Destino', 'Fornecedor',
    'Valor Mínimo (até 10kg)', 'Excedente (por kg adicional)', 'Peso Máximo Transportado',
    'Prazo Econômico', 'Prazo Expresso', 'Gris', 'Pedágio', 'STATUS'
]
df_cidades.columns = df_cidades.columns.astype(str).str.strip()
print("Colunas do df_cidades:", df_cidades.columns.tolist())  # Depuração
print("Primeiras linhas do df_cidades:\n", df_cidades.head())  # Depuração

# Estrutura para TABELA_CUSTOS com normalização
TABELA_CUSTOS = {}
for _, row in df_cidades.iterrows():
    uf_origem = str(row["UF Origem"]).strip().upper() if pd.notna(row["UF Origem"]) else "DESCONHECIDO"
    cidade_origem = normalizar_cidade(str(row["Cidade Origem"]) if pd.notna(row["Cidade Origem"]) else "")
    uf_destino = str(row["UF Destino"]).strip().upper() if pd.notna(row["UF Destino"]) else "DESCONHECIDO"
    cidade_destino = normalizar_cidade(str(row["Cidade Destino"]) if pd.notna(row["Cidade Destino"]) else "")
    
    if not uf_origem or not cidade_origem or not uf_destino or not cidade_destino:
        continue
    
    if uf_origem not in TABELA_CUSTOS:
        TABELA_CUSTOS[uf_origem] = {}
    if cidade_origem not in TABELA_CUSTOS[uf_origem]:
        TABELA_CUSTOS[uf_origem][cidade_origem] = {}
    if uf_destino not in TABELA_CUSTOS[uf_origem][cidade_origem]:
        TABELA_CUSTOS[uf_origem][cidade_origem][uf_destino] = {}
    if cidade_destino not in TABELA_CUSTOS[uf_origem][cidade_origem][uf_destino]:
        TABELA_CUSTOS[uf_origem][cidade_origem][uf_destino][cidade_destino] = []
    
    fornecedor = str(row["Fornecedor"]) if pd.notna(row["Fornecedor"]) else "N/A"
    valor_min_10kg = float(row["Valor Mínimo (até 10kg)"]) if pd.notna(row["Valor Mínimo (até 10kg)"]) else 36.58
    excedente = float(row["Excedente (por kg adicional)"]) if pd.notna(row["Excedente (por kg adicional)"]) else 0.65
    peso_maximo = float(row["Peso Máximo Transportado"]) if pd.notna(row["Peso Máximo Transportado"]) else 2500
    prazo_econ = int(row["Prazo Econômico"]) if pd.notna(row["Prazo Econômico"]) else 5
    prazo_expresso = int(row["Prazo Expresso"]) if pd.notna(row["Prazo Expresso"]) else 2
    gris = float(row["Gris"]) if pd.notna(row["Gris"]) else 0.001
    
    TABELA_CUSTOS[uf_origem][cidade_origem][uf_destino][cidade_destino].append({
        "fornecedor": fornecedor,
        "10kg": valor_min_10kg,
        "excedente": excedente,
        "peso_maximo": peso_maximo,
        "prazo_econ": prazo_econ,
        "prazo_expresso": prazo_expresso,
        "gris": gris,
        "zona_parceiro": "Interior",
        "nova_zona": "Interior",
        "dfl": "Sim"
    })

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

# Contadores para histórico de pesquisas
CONTADOR_FRACIONADO = 1
CONTADOR_DEDICADO = 1

# Histórico de pesquisas
HISTORICO_PESQUISAS = []

# Funções auxiliares
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
            route_points = polyline.decode(geometry) if geometry else []
            return {"distance": distance, "duration": duration, "route_points": route_points, "provider": "OSRM"}
        return None
    except Exception as e:
        print(f"Erro ao calcular rota OSRM: {e}")
        return None

def calcular_distancia_openroute(origem, destino):
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {"Accept": "application/json"}
        params = {"start": f"{origem[1]},{origem[0]}", "end": f"{destino[1]},{destino[0]}"}
        response = requests.get(url, headers=headers, params=params, timeout=15)
        data = response.json()
        if "features" in data and data["features"]:
            route = data["features"][0]
            segments = route.get("properties", {}).get("segments", [{}])[0]
            distance = segments.get("distance", 0) / 1000
            duration = segments.get("duration", 0) / 60
            geometry = route.get("geometry", {})
            route_points = [[coord[1], coord[0]] for coord in geometry.get("coordinates", [])]
            return {"distance": distance, "duration": duration, "route_points": route_points, "provider": "OpenRouteService"}
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

def calcular_valor_fracionado(peso, cubagem, transportadora_data):
    peso_cubado = max(peso, cubagem * 300)
    if peso_cubado <= 10:
        custo_base = transportadora_data["10kg"]
    else:
        custo_base = transportadora_data["10kg"] + (peso_cubado - 10) * transportadora_data["excedente"]
    return custo_base

def gerar_analise_trajeto(origem_info, destino_info, rota_info, custos, tipo="Dedicado"):
    global CONTADOR_DEDICADO
    
    origem_nome = origem_info[2] if len(origem_info) > 2 else "Origem"
    destino_nome = destino_info[2] if len(destino_info) > 2 else "Destino"
    horas = int(rota_info["duration"] // 60)
    minutos = int(rota_info["duration"] % 60)
    tempo_estimado = f"{horas}h {minutos}min" if horas > 0 else f"{minutos}min"
    consumo_combustivel = rota_info["distance"] / 10
    emissao_co2 = consumo_combustivel * 2.3
    pedagio_estimado = rota_info["distance"] * 0.15
    
    # Gerar ID de histórico
    id_historico = f"#{tipo}{CONTADOR_DEDICADO:03d}"
    if tipo == "Dedicado":
        CONTADOR_DEDICADO += 1
    
    analise = {
        "id_historico": id_historico,
        "tipo": tipo,
        "origem": origem_nome, 
        "destino": destino_nome,
        "distancia": round(rota_info["distance"], 2),
        "tempo_estimado": tempo_estimado,
        "duracao_minutos": round(rota_info["duration"], 2),
        "consumo_combustivel": round(consumo_combustivel, 2),
        "emissao_co2": round(emissao_co2, 2),
        "pedagio_estimado": round(pedagio_estimado, 2),
        "provider": rota_info["provider"], 
        "custos": custos,
        "data_hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "rota_pontos": rota_info["route_points"]
    }
    return analise

def get_municipios_uf(uf):
    try:
        response = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios", timeout=10)
        response.raise_for_status()
        data = response.json()
        return {normalizar_cidade(m["nome"]): m["nome"].title() for m in data}
    except Exception as e:
        print(f"Erro ao carregar municípios do IBGE para UF {uf}: {e}")
        return {}

# Função para filtrar por fornecedor sem repetição
def filtrar_por_fornecedor(transportadoras):
    fornecedores_unicos = {}
    for t in transportadoras:
        fornecedor = t["fornecedor"]
        # Se o fornecedor ainda não existe ou se o custo é menor que o já registrado
        if fornecedor not in fornecedores_unicos or t["custo"] < fornecedores_unicos[fornecedor]["custo"]:
            fornecedores_unicos[fornecedor] = t
    return list(fornecedores_unicos.values())

# Função para registrar pesquisa fracionada no histórico
def registrar_pesquisa_fracionada(dados):
    global CONTADOR_FRACIONADO, HISTORICO_PESQUISAS
    
    id_historico = f"#Fracionado{CONTADOR_FRACIONADO:03d}"
    CONTADOR_FRACIONADO += 1
    
    # Criar registro de histórico
    registro = {
        "id_historico": id_historico,
        "tipo": "Fracionado",
        "origem": f"{dados['cidades_origem']} - {dados['uf_origem']}",
        "destino": f"{dados['cidades_destino']} - {dados['uf_destino']}",
        "peso": dados["peso"],
        "cubagem": dados["cubagem"],
        "distancia": dados.get("distancia"),
        "data_hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "melhor_preco": dados.get("melhor_preco"),
        "melhor_prazo": dados.get("melhor_prazo"),
        "fornecedores": dados.get("todos_agentes", []),
        "route_points": dados.get("route_points"),
        "ranking": dados.get("ranking", []),
        "ranking_completo": dados.get("ranking_completo", [])
    }
    
    # Adicionar ao histórico
    HISTORICO_PESQUISAS.append(registro)
    
    # Limitar tamanho do histórico
    if len(HISTORICO_PESQUISAS) > 50:
        HISTORICO_PESQUISAS.pop(0)
    
    return id_historico

class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def header(self):
        # Usar fonte padrão
        self.set_font("helvetica", "B", 15)
        # Usar parâmetros modernos em vez de ln=1
        self.cell(0, 10, "PortoEx - Relatório de Transporte", 0, new_x="LMARGIN", new_y="NEXT", align="C")
        self.line(10, 20, 200, 20)
        self.ln(10)
        
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", 0, 0, "C")
        self.cell(0, 10, f"© {datetime.datetime.now().year} PortoEx - Todos os direitos reservados", 0, 0, "R")

# Endpoints
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/estados")
def estados():
    try:
        response = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados", timeout=10)
        response.raise_for_status()
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
        municipios = [{"id": normalizar_cidade(m["nome"]), "text": m["nome"].title()} for m in sorted(data, key=lambda x: x["nome"])]
        return jsonify(municipios)
    except Exception as e:
        print(f"Erro ao carregar municípios para UF {uf}: {e}")
        return jsonify([])

@app.route("/historico")
def historico():
    return jsonify(HISTORICO_PESQUISAS)

@app.route("/calcular", methods=["POST"])
def calcular():
    data = request.json
    municipio_origem = data["municipio_origem"]
    uf_origem = data["uf_origem"]
    municipio_destino = data["municipio_destino"]
    uf_destino = data["uf_destino"]
    peso = float(data.get("peso", 0))
    cubagem = float(data.get("cubagem", 0))
    coord_origem = geocode(municipio_origem, uf_origem)
    coord_destino = geocode(municipio_destino, uf_destino)
    if not coord_origem or not coord_destino:
        return jsonify({"error": "Não foi possível identificar os locais"}), 400
    rota_info = calcular_distancia_osrm(coord_origem, coord_destino) or \
                calcular_distancia_openroute(coord_origem, coord_destino) or \
                calcular_distancia_reta(coord_origem, coord_destino)
    if not rota_info:
        return jsonify({"error": "Não foi possível calcular a distância"}), 500
    distancia = rota_info["distance"]
    faixa = determinar_faixa(distancia)
    if not faixa:
        return jsonify({"error": "Distância fora da faixa suportada (acima de 6000 km)"}), 400
    custos = TABELA_CUSTOS_DEDICADO[faixa]
    analise = gerar_analise_trajeto(coord_origem, coord_destino, rota_info, custos, "Dedicado")
    HISTORICO_PESQUISAS.append(analise)
    if len(HISTORICO_PESQUISAS) > 50:
        HISTORICO_PESQUISAS.pop(0)
    return jsonify({
        "id_historico": analise["id_historico"],
        "distancia": round(distancia, 2),
        "duracao": round(rota_info["duration"], 2),
        "custos": custos,
        "peso": peso,
        "cubagem": cubagem,
        "rota_pontos": rota_info["route_points"],
        "analise": analise
    })

@app.route("/calcular_frete_fracionado", methods=["POST"])
def calcular_frete_fracionado():
    try:
        uf_origem = request.form.get("estado_origem")
        cidade_origem = normalizar_cidade(request.form.get("municipio_origem"))
        uf_destino = request.form.get("estado_destino")
        cidade_destino = normalizar_cidade(request.form.get("municipio_destino"))
        peso = float(request.form.get("peso", 10))
        cubagem = float(request.form.get("cubagem", 0.05))
        
        if not all([uf_origem, cidade_origem, uf_destino, cidade_destino]):
            return render_template_string(HTML_TEMPLATE, erro="Todos os campos são obrigatórios.")
        
        # Verificar se a rota existe
        if (uf_origem not in TABELA_CUSTOS or 
            cidade_origem not in TABELA_CUSTOS[uf_origem] or 
            uf_destino not in TABELA_CUSTOS[uf_origem][cidade_origem] or 
            cidade_destino not in TABELA_CUSTOS[uf_origem][cidade_origem][uf_destino]):
            return render_template_string(HTML_TEMPLATE, erro="Rota não encontrada na base de dados.")
        
        transportadoras = TABELA_CUSTOS[uf_origem][cidade_origem][uf_destino][cidade_destino]
        if not transportadoras:
            return render_template_string(HTML_TEMPLATE, erro="Nenhuma transportadora disponível para esta rota.")
        
        # Calcular custos para cada transportadora
        ranking = []
        for t in transportadoras:
            if peso <= t["peso_maximo"]:
                custo = calcular_valor_fracionado(peso, cubagem, t)
                gris_valor = custo * t["gris"]
                ranking.append({
                    "fornecedor": t["fornecedor"],
                    "custo": custo,
                    "prazo": t["prazo_econ"],
                    "gris": t["gris"],
                    "zona_parceiro": t["zona_parceiro"],
                    "nova_zona": t["nova_zona"],
                    "dfl": t["dfl"],
                    "peso_maximo": t["peso_maximo"],
                    "excedente": t["excedente"]
                })
        
        # Ordenar por custo (menor primeiro)
        ranking.sort(key=lambda x: x["custo"])
        
        # Obter coordenadas para o mapa
        coord_origem = geocode(cidade_origem, uf_origem)
        coord_destino = geocode(cidade_destino, uf_destino)
        route_points = None
        distancia = None
        
        if coord_origem and coord_destino:
            rota_info = calcular_distancia_osrm(coord_origem, coord_destino) or \
                        calcular_distancia_openroute(coord_origem, coord_destino) or \
                        calcular_distancia_reta(coord_origem, coord_destino)
            if rota_info:
                route_points = rota_info["route_points"]
                distancia = rota_info["distance"]
        
        # Categorizar por melhor preço e melhor prazo
        melhor_preco = min(ranking, key=lambda x: x["custo"]) if ranking else None
        melhor_prazo = min(ranking, key=lambda x: x["prazo"]) if ranking else None
        
        # Identificar o pior agente (maior preço)
        pior_preco = max(ranking, key=lambda x: x["custo"]) if ranking else None
        
        # Calcular a diferença entre o melhor e o pior preço
        diferenca_valor = None
        diferenca_percentual = None
        if melhor_preco and pior_preco:
            diferenca_valor = pior_preco["custo"] - melhor_preco["custo"]
            diferenca_percentual = (diferenca_valor / melhor_preco["custo"]) * 100 if melhor_preco["custo"] > 0 else 0
        
        # Listar todos os agentes que atuam na rota (sem filtrar)
        todos_agentes = []
        fornecedores_vistos = set()
        for t in ranking:
            if t["fornecedor"] not in fornecedores_vistos:
                todos_agentes.append(t["fornecedor"])
                fornecedores_vistos.add(t["fornecedor"])
        
        # Aplicar filtro por fornecedor para evitar repetição
        ranking_filtrado = filtrar_por_fornecedor(ranking)
        
        # Ordenar novamente após filtragem
        ranking_filtrado.sort(key=lambda x: x["custo"])
        
        # Preparar resultado para o template
        municipios_origem = get_municipios_uf(uf_origem)
        municipios_destino = get_municipios_uf(uf_destino)
        
        cidade_origem_formatada = municipios_origem.get(cidade_origem, cidade_origem)
        cidade_destino_formatada = municipios_destino.get(cidade_destino, cidade_destino)
        
        resultado = {
            "cidades_origem": cidade_origem_formatada,
            "uf_origem": uf_origem,
            "cidades_destino": cidade_destino_formatada,
            "uf_destino": uf_destino,
            "peso": peso,
            "cubagem": cubagem,
            "ranking": ranking_filtrado,
            "ranking_completo": ranking,  # Ranking sem filtro por fornecedor
            "route_points": route_points,
            "distancia": distancia,
            "melhor_preco": melhor_preco,
            "melhor_prazo": melhor_prazo,
            "pior_preco": pior_preco,
            "diferenca_valor": diferenca_valor,
            "diferenca_percentual": diferenca_percentual,
            "todos_agentes": todos_agentes
        }
        
        # Registrar no histórico
        id_historico = registrar_pesquisa_fracionada(resultado)
        resultado["id_historico"] = id_historico
        
        return render_template_string(HTML_TEMPLATE, resultado=resultado, historico=HISTORICO_PESQUISAS)
    
    except Exception as e:
        print(f"Erro ao calcular frete fracionado: {e}")
        return render_template_string(HTML_TEMPLATE, erro=f"Erro ao processar: {str(e)}")

@app.route("/gerar-pdf", methods=["POST"])
def gerar_pdf():
    try:
        data = request.json
        analise = data.get("analise", {})
        tipo = analise.get("tipo", "Dedicado")
        
        pdf = PDF()
        pdf.add_page()
        
        # Título
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 10, "Relatório de Análise de Transporte", 0, new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(5)
        
        # ID do Histórico
        if "id_historico" in analise:
            pdf.set_font("helvetica", "B", 12)
            pdf.cell(0, 8, f"ID: {analise.get('id_historico', 'N/A')}", 0, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        
        # Informações da rota
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, f"Rota: {analise.get('origem', 'N/A')} → {analise.get('destino', 'N/A')}", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        
        # Detalhes
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 8, f"Data/Hora: {analise.get('data_hora', 'N/A')}", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Distância: {analise.get('distancia', 'N/A')} km", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Tempo estimado: {analise.get('tempo_estimado', 'N/A')}", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Consumo estimado: {analise.get('consumo_combustivel', 'N/A')} L", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Emissão de CO₂: {analise.get('emissao_co2', 'N/A')} kg", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Pedágio estimado: R$ {analise.get('pedagio_estimado', 'N/A')}", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        
        if tipo == "Dedicado":
            # Tabela de custos para Dedicado
            pdf.set_font("helvetica", "B", 12)
            pdf.cell(0, 10, "Custos por Tipo de Veículo", 0, new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(60, 8, "Tipo de Veículo", 1, 0, "C")
            pdf.cell(60, 8, "Custo (R$)", 1, new_x="LMARGIN", new_y="NEXT", align="C")
            
            pdf.set_font("helvetica", "", 10)
            for tipo_veiculo, custo in analise.get("custos", {}).items():
                pdf.cell(60, 8, tipo_veiculo, 1, 0)
                pdf.cell(60, 8, f"R$ {custo:.2f}", 1, new_x="LMARGIN", new_y="NEXT", align="R")
        else:
            # Tabela de fornecedores para Fracionado
            pdf.set_font("helvetica", "B", 12)
            pdf.cell(0, 10, "Ranking de Fornecedores", 0, new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(40, 8, "Fornecedor", 1, 0, "C")
            pdf.cell(30, 8, "Custo (R$)", 1, 0, "C")
            pdf.cell(30, 8, "Prazo (dias)", 1, new_x="LMARGIN", new_y="NEXT", align="C")
            
            pdf.set_font("helvetica", "", 10)
            for item in analise.get("ranking", []):
                pdf.cell(40, 8, item.get("fornecedor", "N/A"), 1, 0)
                pdf.cell(30, 8, f"R$ {item.get('custo', 0):.2f}", 1, 0, "R")
                pdf.cell(30, 8, str(item.get("prazo", "N/A")), 1, new_x="LMARGIN", new_y="NEXT", align="C")
            
            # Melhor e pior preço
            if "melhor_preco" in analise and "pior_preco" in analise:
                pdf.ln(5)
                pdf.set_font("helvetica", "B", 12)
                pdf.cell(0, 10, "Comparação de Preços", 0, new_x="LMARGIN", new_y="NEXT")
                
                melhor = analise.get("melhor_preco", {})
                pior = analise.get("pior_preco", {})
                
                pdf.set_font("helvetica", "B", 10)
                pdf.cell(0, 8, "Melhor Preço:", 0, new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("helvetica", "", 10)
                pdf.cell(0, 6, f"Fornecedor: {melhor.get('fornecedor', 'N/A')}", 0, new_x="LMARGIN", new_y="NEXT")
                pdf.cell(0, 6, f"Custo: R$ {melhor.get('custo', 0):.2f}", 0, new_x="LMARGIN", new_y="NEXT")
                pdf.cell(0, 6, f"Prazo: {melhor.get('prazo', 'N/A')} dias", 0, new_x="LMARGIN", new_y="NEXT")
                
                pdf.ln(3)
                pdf.set_font("helvetica", "B", 10)
                pdf.cell(0, 8, "Pior Preço:", 0, new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("helvetica", "", 10)
                pdf.cell(0, 6, f"Fornecedor: {pior.get('fornecedor', 'N/A')}", 0, new_x="LMARGIN", new_y="NEXT")
                pdf.cell(0, 6, f"Custo: R$ {pior.get('custo', 0):.2f}", 0, new_x="LMARGIN", new_y="NEXT")
                pdf.cell(0, 6, f"Prazo: {pior.get('prazo', 'N/A')} dias", 0, new_x="LMARGIN", new_y="NEXT")
                
                if "diferenca_valor" in analise and "diferenca_percentual" in analise:
                    pdf.ln(3)
                    pdf.set_font("helvetica", "B", 10)
                    pdf.cell(0, 8, "Diferença:", 0, new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("helvetica", "", 10)
                    pdf.cell(0, 6, f"Valor: R$ {analise.get('diferenca_valor', 0):.2f}", 0, new_x="LMARGIN", new_y="NEXT")
                    pdf.cell(0, 6, f"Percentual: {analise.get('diferenca_percentual', 0):.2f}%", 0, new_x="LMARGIN", new_y="NEXT")
        
        # Rodapé
        pdf.ln(10)
        pdf.set_font("helvetica", "I", 8)
        pdf.cell(0, 8, "Este relatório é gerado automaticamente pelo sistema PortoEx.", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, "Os valores apresentados são estimativas e podem variar conforme condições específicas.", 0, new_x="LMARGIN", new_y="NEXT")
        
        # Gerar PDF
        pdf_output = io.BytesIO()
        pdf.output(pdf_output)
        pdf_output.seek(0)
        
        return send_file(
            pdf_output,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"relatorio_{tipo.lower()}.pdf"
        )
    
    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/exportar-excel", methods=["POST"])
def exportar_excel():
    try:
        data = request.json
        tipo = data.get("tipo", "Dedicado")
        dados = data.get("dados", {})
        
        output = io.BytesIO()
        
        if tipo == "Dedicado":
            # Criar DataFrame para dados de frete dedicado
            df = pd.DataFrame({
                "Tipo de Veículo": list(dados.get("custos", {}).keys()),
                "Custo (R$)": list(dados.get("custos", {}).values())
            })
            
            # Adicionar informações adicionais
            info = {
                "ID": [dados.get("id_historico", "N/A")],
                "Origem": [dados.get("origem", "N/A")],
                "Destino": [dados.get("destino", "N/A")],
                "Distância (km)": [dados.get("distancia", "N/A")],
                "Tempo Estimado": [dados.get("tempo_estimado", "N/A")],
                "Data/Hora": [dados.get("data_hora", "N/A")]
            }
            df_info = pd.DataFrame(info)
            
            # Salvar em Excel
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_info.to_excel(writer, sheet_name='Informações', index=False)
                df.to_excel(writer, sheet_name='Custos por Veículo', index=False)
        
        else:  # Fracionado
            # Criar DataFrame para ranking de fornecedores
            ranking = dados.get("ranking", [])
            if ranking:
                df_ranking = pd.DataFrame(ranking)
                
                # Criar DataFrame para informações gerais
                info = {
                    "ID": [dados.get("id_historico", "N/A")],
                    "Origem": [f"{dados.get('cidades_origem', 'N/A')} - {dados.get('uf_origem', 'N/A')}"],
                    "Destino": [f"{dados.get('cidades_destino', 'N/A')} - {dados.get('uf_destino', 'N/A')}"],
                    "Peso (kg)": [dados.get("peso", "N/A")],
                    "Cubagem (m³)": [dados.get("cubagem", "N/A")],
                    "Distância (km)": [dados.get("distancia", "N/A")],
                    "Data/Hora": [dados.get("data_hora", "N/A")]
                }
                df_info = pd.DataFrame(info)
                
                # Criar DataFrame para melhor e pior preço
                melhor_pior = {
                    "Categoria": ["Melhor Preço", "Melhor Prazo", "Pior Preço"],
                    "Fornecedor": [
                        dados.get("melhor_preco", {}).get("fornecedor", "N/A"),
                        dados.get("melhor_prazo", {}).get("fornecedor", "N/A"),
                        dados.get("pior_preco", {}).get("fornecedor", "N/A")
                    ],
                    "Custo (R$)": [
                        dados.get("melhor_preco", {}).get("custo", "N/A"),
                        dados.get("melhor_prazo", {}).get("custo", "N/A"),
                        dados.get("pior_preco", {}).get("custo", "N/A")
                    ],
                    "Prazo (dias)": [
                        dados.get("melhor_preco", {}).get("prazo", "N/A"),
                        dados.get("melhor_prazo", {}).get("prazo", "N/A"),
                        dados.get("pior_preco", {}).get("prazo", "N/A")
                    ]
                }
                df_melhor_pior = pd.DataFrame(melhor_pior)
                
                # Salvar em Excel
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_info.to_excel(writer, sheet_name='Informações', index=False)
                    df_ranking.to_excel(writer, sheet_name='Ranking de Fornecedores', index=False)
                    df_melhor_pior.to_excel(writer, sheet_name='Melhor e Pior', index=False)
                    
                    # Se houver ranking completo, adicionar também
                    ranking_completo = dados.get("ranking_completo", [])
                    if ranking_completo:
                        df_completo = pd.DataFrame(ranking_completo)
                        df_completo.to_excel(writer, sheet_name='Ranking Completo', index=False)
            else:
                # Se não houver dados de ranking, criar um Excel simples com informações básicas
                info = {
                    "ID": [dados.get("id_historico", "N/A")],
                    "Origem": [f"{dados.get('cidades_origem', 'N/A')} - {dados.get('uf_origem', 'N/A')}"],
                    "Destino": [f"{dados.get('cidades_destino', 'N/A')} - {dados.get('uf_destino', 'N/A')}"],
                    "Peso (kg)": [dados.get("peso", "N/A")],
                    "Cubagem (m³)": [dados.get("cubagem", "N/A")],
                    "Distância (km)": [dados.get("distancia", "N/A")],
                    "Data/Hora": [dados.get("data_hora", "N/A")]
                }
                df_info = pd.DataFrame(info)
                
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_info.to_excel(writer, sheet_name='Informações', index=False)
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"dados_{tipo.lower()}.xlsx"
        )
    
    except Exception as e:
        print(f"Erro ao exportar Excel: {e}")
        return jsonify({"error": str(e)}), 500

# Template HTML
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PortoEx - Calculadora de Frete</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.3/dist/leaflet.css">
  <script src="https://code.jquery.com/jquery-3.6.3.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://unpkg.com/leaflet@1.9.3/dist/leaflet.js"></script>
  <style>
    body { padding: 20px; }
    .select2-container { width: 100% !important; }
    #map { height: 400px; width: 100%; margin-top: 20px; }
    .tab-content { padding-top: 20px; }
    .resultado-info { background-color: #f8f9fa; padding: 15px; border-radius: 5px; }
    .pbi-container { width: 100%; height: 600px; }
    .comparacao-card { margin-top: 20px; padding: 15px; border-radius: 5px; background-color: #f0f8ff; }
    .agentes-list { margin-top: 10px; }
    .agentes-list span { display: inline-block; margin-right: 10px; margin-bottom: 5px; padding: 5px 10px; background-color: #e9ecef; border-radius: 15px; }
    .historico-item { cursor: pointer; transition: background-color 0.3s; }
    .historico-item:hover { background-color: #f5f5f5; }
    .historico-badge { font-size: 0.8em; padding: 3px 8px; margin-right: 5px; }
    .chart-container { height: 300px; margin-bottom: 20px; }
    .btn-group-export { margin-top: 15px; margin-bottom: 20px; }
  </style>
</head>
<body>
  <div class="container">
    <h1 class="mb-4">📦 PortoEx - Calculadora de Frete</h1>
    <ul class="nav nav-tabs" id="myTab" role="tablist">
      <li class="nav-item">
        <a class="nav-link active" data-bs-toggle="tab" href="#tab-fracionado">Fracionado</a>
      </li>
      <li class="nav-item">
        <a class="nav-link" data-bs-toggle="tab" href="#tab-dedicado">Dedicado</a>
      </li>
      <li class="nav-item">
        <a class="nav-link" data-bs-toggle="tab" href="#tab-historico">Histórico</a>
      </li>
      <li class="nav-item">
        <a class="nav-link" data-bs-toggle="tab" href="#tab-dashboard">Target</a>
      </li>
    </ul>
    <div class="tab-content">
      <!-- Dedicado -->
      <div class="tab-pane fade" id="tab-dedicado">
        <form id="form-dedicado" class="row g-3">
          <div class="col-md-6">
            <label for="uf_origem" class="form-label">Estado de Origem</label>
            <select id="uf_origem" class="form-select select2-enable"></select>
          </div>
          <div class="col-md-6">
            <label for="uf_destino" class="form-label">Estado de Destino</label>
            <select id="uf_destino" class="form-select select2-enable"></select>
          </div>
          <div class="col-md-6">
            <label for="municipio_origem" class="form-label">Município de Origem</label>
            <select id="municipio_origem" class="form-select select2-enable" disabled></select>
          </div>
          <div class="col-md-6">
            <label for="municipio_destino" class="form-label">Município de Destino</label>
            <select id="municipio_destino" class="form-select select2-enable" disabled></select>
          </div>
          <div class="col-md-6">
            <label for="peso" class="form-label">Peso (kg) - Opcional</label>
            <input type="number" id="peso" class="form-control" min="0" step="0.01">
          </div>
          <div class="col-md-6">
            <label for="cubagem" class="form-label">Cubagem (m³) - Opcional</label>
            <input type="number" id="cubagem" class="form-control" min="0" step="0.01">
          </div>
          <div class="col-12">
            <button type="button" id="btn_calcular" class="btn btn-primary">Calcular Custos</button>
          </div>
        </form>
        <div id="resultados" style="display: none;">
          <h3 class="mt-4" id="id-historico-dedicado"></h3>
          <div id="map"></div>
          <h3 class="mt-4">Resultados</h3>
          
          <div class="btn-group-export">
            <button id="btn_gerar_pdf" class="btn btn-secondary">Salvar Relatório em PDF</button>
            <button id="btn_exportar_excel" class="btn btn-success ms-2">Exportar para Excel</button>
          </div>
          
          <div class="row mt-4">
            <div class="col-md-6">
              <div class="chart-container">
                <h4>Custos por Veículo</h4>
                <canvas id="custoChart"></canvas>
              </div>
            </div>
            <div class="col-md-6">
              <table class="table table-striped mt-4">
                <thead>
                  <tr>
                    <th>Tipo de Veículo</th>
                    <th>Custo (R$)</th>
                  </tr>
                </thead>
                <tbody id="tabela-resultado"></tbody>
              </table>
            </div>
          </div>
          <div class="resultado-info mt-4">
            <p><strong>Rota:</strong> <span id="res-origem"></span> → <span id="res-destino"></span></p>
            <p><strong>Distância:</strong> <span id="res-distancia"></span> km</p>
            <p><strong>Tempo estimado:</strong> <span id="res-tempo"></span></p>
            <p><strong>Consumo estimado:</strong> <span id="res-consumo"></span> L</p>
            <p><strong>Emissão de CO₂:</strong> <span id="res-co2"></span> kg</p>
            <p><strong>Pedágio estimado:</strong> R$ <span id="res-pedagio"></span></p>
            <p><strong>Peso informado:</strong> <span id="res-peso"></span></p>
            <p><strong>Cubagem informada:</strong> <span id="res-cubagem"></span></p>
          </div>
        </div>
      </div>
      <!-- Fracionado -->
      <div class="tab-pane fade show active" id="tab-fracionado">
        <form method="POST" action="/calcular_frete_fracionado" class="row g-3">
          <div class="col-md-6">
            <label for="uf_origem_frac" class="form-label">Estado de Origem</label>
            <select name="estado_origem" id="uf_origem_frac" class="form-select select2-enable"></select>
          </div>
          <div class="col-md-6">
            <label for="uf_destino_frac" class="form-label">Estado de Destino</label>
            <select name="estado_destino" id="uf_destino_frac" class="form-select select2-enable"></select>
          </div>
          <div class="col-md-6">
            <label for="municipio_origem_frac" class="form-label">Município de Origem</label>
            <select name="municipio_origem" id="municipio_origem_frac" class="form-select select2-enable" disabled></select>
          </div>
          <div class="col-md-6">
            <label for="municipio_destino_frac" class="form-label">Município de Destino</label>
            <select name="municipio_destino" id="municipio_destino_frac" class="form-select select2-enable" disabled></select>
          </div>
          <div class="col-md-6">
            <label for="peso-frac" class="form-label">Peso (kg)</label>
            <input type="number" name="peso" id="peso-frac" value="10" min="0" step="0.01" class="form-control">
          </div>
          <div class="col-md-6">
            <label for="cubagem-frac" class="form-label">Cubagem (m³)</label>
            <input type="number" name="cubagem" id="cubagem-frac" value="0.05" min="0" step="0.01" class="form-control">
          </div>
          <div class="col-12">
            <button type="submit" class="btn btn-primary">Calcular Lista de Agentes</button>
          </div>
        </form>
        {% if erro %}
          <div class="alert alert-danger mt-3">{{ erro }}</div>
        {% endif %}
        {% if resultado %}
          <h3 class="mt-4">{{ resultado.id_historico }} - Cotação: {{ resultado.cidades_origem }} - {{ resultado.uf_origem }} → {{ resultado.cidades_destino }} - {{ resultado.uf_destino }}</h3>
          <p><strong>Peso:</strong> {{ resultado.peso }} kg | <strong>Cubagem:</strong> {{ resultado.cubagem }} m³</p>
          {% if resultado.distancia %}
            <p><strong>Distância:</strong> {{ resultado.distancia | round(2) }} km</p>
          {% endif %}
          
          <!-- Botões de exportação -->
          <div class="btn-group-export">
            <button id="btn_gerar_pdf_fracionado" class="btn btn-secondary">Salvar Relatório em PDF</button>
            <button id="btn_exportar_excel_fracionado" class="btn btn-success ms-2">Exportar para Excel</button>
          </div>
          
          <!-- Gráfico de custo por agente -->
          <div class="row mt-4">
            <div class="col-md-12">
              <div class="chart-container">
                <h4>Custos por Agente</h4>
                <canvas id="custoAgentesChart"></canvas>
              </div>
            </div>
          </div>
          
          <!-- Lista de todos os agentes que atuam na rota -->
          <div class="card mt-4">
            <div class="card-header bg-info text-white">
              <h5 class="mb-0">Agentes que atuam nesta rota</h5>
            </div>
            <div class="card-body">
              <div class="agentes-list">
                {% for agente in resultado.todos_agentes %}
                  <span class="badge bg-secondary">{{ agente }}</span>
                {% endfor %}
              </div>
            </div>
          </div>
          
          <!-- Comparação entre melhor e pior agente -->
          {% if resultado.melhor_preco and resultado.pior_preco %}
            <div class="card mt-4">
              <div class="card-header bg-warning text-dark">
                <h5 class="mb-0">Comparação entre Melhor e Pior Agente</h5>
              </div>
              <div class="card-body">
                <div class="row">
                  <div class="col-md-6">
                    <h6>Melhor Agente (Menor Preço)</h6>
                    <p><strong>Fornecedor:</strong> {{ resultado.melhor_preco.fornecedor }}</p>
                    <p><strong>Custo:</strong> R$ {{ resultado.melhor_preco.custo | round(2) }}</p>
                    <p><strong>Prazo:</strong> {{ resultado.melhor_preco.prazo }} dias</p>
                  </div>
                  <div class="col-md-6">
                    <h6>Pior Agente (Maior Preço)</h6>
                    <p><strong>Fornecedor:</strong> {{ resultado.pior_preco.fornecedor }}</p>
                    <p><strong>Custo:</strong> R$ {{ resultado.pior_preco.custo | round(2) }}</p>
                    <p><strong>Prazo:</strong> {{ resultado.pior_preco.prazo }} dias</p>
                  </div>
                </div>
                <div class="alert alert-info mt-3">
                  <p><strong>Diferença de valor:</strong> R$ {{ resultado.diferenca_valor | round(2) }}</p>
                  <p><strong>Diferença percentual:</strong> {{ resultado.diferenca_percentual | round(2) }}%</p>
                </div>
              </div>
            </div>
          {% endif %}
          
          <!-- Categorização por melhor preço e prazo -->
          <div class="row mt-4">
            <div class="col-md-6">
              <div class="card">
                <div class="card-header bg-success text-white">
                  <h5 class="mb-0">Melhor Preço</h5>
                </div>
                <div class="card-body">
                  {% if resultado.melhor_preco %}
                    <p><strong>Fornecedor:</strong> {{ resultado.melhor_preco.fornecedor }}</p>
                    <p><strong>Custo:</strong> R$ {{ resultado.melhor_preco.custo | round(2) }}</p>
                    <p><strong>Prazo:</strong> {{ resultado.melhor_preco.prazo }} dias</p>
                  {% else %}
                    <p>Nenhum fornecedor disponível</p>
                  {% endif %}
                </div>
              </div>
            </div>
            <div class="col-md-6">
              <div class="card">
                <div class="card-header bg-primary text-white">
                  <h5 class="mb-0">Melhor Prazo</h5>
                </div>
                <div class="card-body">
                  {% if resultado.melhor_prazo %}
                    <p><strong>Fornecedor:</strong> {{ resultado.melhor_prazo.fornecedor }}</p>
                    <p><strong>Custo:</strong> R$ {{ resultado.melhor_prazo.custo | round(2) }}</p>
                    <p><strong>Prazo:</strong> {{ resultado.melhor_prazo.prazo }} dias</p>
                  {% else %}
                    <p>Nenhum fornecedor disponível</p>
                  {% endif %}
                </div>
              </div>
            </div>
          </div>
          
          <!-- Ranking de transportadoras filtrado (sem repetição) -->
          <div class="row mt-4">
            <div class="col-md-12">
              <h4>Ranking de Transportadoras (Filtrado por Fornecedor)</h4>
              <table class="table table-striped">
                <thead>
                  <tr>
                    <th>Posição</th>
                    <th>Fornecedor</th>
                    <th>Custo (R$)</th>
                    <th>Prazo (dias)</th>
                    <th>Gris</th>
                    <th>Zona Parceiro</th>
                    <th>Nova Zona</th>
                    <th>DFL</th>
                    <th>Peso Máximo (kg)</th>
                    <th>Excedente (R$/kg)</th>
                  </tr>
                </thead>
                <tbody>
                  {% for item in resultado.ranking %}
                    <tr>
                      <td>{{ loop.index }}</td>
                      <td>{{ item.fornecedor }}</td>
                      <td>{{ item.custo | round(2) }}</td>
                      <td>{{ item.prazo }}</td>
                      <td>{{ item.gris }}</td>
                      <td>{{ item.zona_parceiro }}</td>
                      <td>{{ item.nova_zona }}</td>
                      <td>{{ item.dfl }}</td>
                      <td>{{ item.peso_maximo }}</td>
                      <td>{{ item.excedente | round(2) }}</td>
                    </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
          </div>
          
          <!-- Ranking completo de transportadoras (com todas as opções) -->
          <div class="row mt-4">
            <div class="col-md-12">
              <h4>Ranking Completo de Transportadoras (Todas as Opções)</h4>
              <table class="table table-striped">
                <thead>
                  <tr>
                    <th>Posição</th>
                    <th>Fornecedor</th>
                    <th>Custo (R$)</th>
                    <th>Prazo (dias)</th>
                    <th>Gris</th>
                    <th>Zona Parceiro</th>
                    <th>Nova Zona</th>
                    <th>DFL</th>
                    <th>Peso Máximo (kg)</th>
                    <th>Excedente (R$/kg)</th>
                  </tr>
                </thead>
                <tbody>
                  {% for item in resultado.ranking_completo %}
                    <tr>
                      <td>{{ loop.index }}</td>
                      <td>{{ item.fornecedor }}</td>
                      <td>{{ item.custo | round(2) }}</td>
                      <td>{{ item.prazo }}</td>
                      <td>{{ item.gris }}</td>
                      <td>{{ item.zona_parceiro }}</td>
                      <td>{{ item.nova_zona }}</td>
                      <td>{{ item.dfl }}</td>
                      <td>{{ item.peso_maximo }}</td>
                      <td>{{ item.excedente | round(2) }}</td>
                    </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
          </div>
        {% endif %}
      </div>
      
      <!-- Histórico -->
      <div class="tab-pane fade" id="tab-historico">
        <h3 class="mt-4">Histórico de Pesquisas</h3>
        <div class="table-responsive">
          <table class="table table-hover">
            <thead>
              <tr>
                <th>ID</th>
                <th>Tipo</th>
                <th>Origem</th>
                <th>Destino</th>
                <th>Data/Hora</th>
                <th>Detalhes</th>
              </tr>
            </thead>
            <tbody id="historico-tbody">
              <!-- Será preenchido via JavaScript -->
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- Dashboard -->
      <div class="tab-pane fade" id="tab-dashboard">
        <div class="pbi-container">
          <iframe src="https://app.powerbi.com/view?r=eyJrIjoiYWUzODBiYmUtMWI1OC00NGVjLWFjNDYtYzYyMDQ3MzQ0MTQ0IiwidCI6IjM4MjViNTlkLTY1ZGMtNDM1Zi04N2M4LTkyM2QzMzkxYzMyOCJ9" allowfullscreen="true" style="width: 100%; height: 600px;"></iframe>
        </div>
      </div>
    </div>
  </div>

  <script>
    let map;
    let custoAgentesChart;
    let resultadoFracionado = null;
    let resultadoDedicado = null;
    
    function initMap(points) {
      if (!map) {
        map = L.map('map').setView([-15.77972, -47.92972], 5);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© OpenStreetMap contributors'
        }).addTo(map);
      }
      
      if (points && points.length > 1) {
        // Limpar rotas e marcadores anteriores
        map.eachLayer(function(layer) {
          if (layer instanceof L.Polyline || layer instanceof L.Marker) {
            map.removeLayer(layer);
          }
        });
        
        let route = L.polyline(points, {color: 'blue'}).addTo(map);
        map.fitBounds(route.getBounds());
        L.marker(points[0]).addTo(map).bindPopup('Origem');
        L.marker(points[points.length - 1]).addTo(map).bindPopup('Destino');
      }
    }
    
    function carregarHistorico() {
      $.get('/historico', function(data) {
        let html = '';
        data.forEach(function(item) {
          let badgeClass = item.tipo === 'Fracionado' ? 'bg-primary' : 'bg-success';
          html += `<tr class="historico-item" data-id="${item.id_historico}">
            <td><span class="badge ${badgeClass} historico-badge">${item.id_historico}</span></td>
            <td>${item.tipo}</td>
            <td>${item.origem}</td>
            <td>${item.destino}</td>
            <td>${item.data_hora}</td>
            <td><button class="btn btn-sm btn-info">Ver Detalhes</button></td>
          </tr>`;
        });
        $('#historico-tbody').html(html);
      });
    }
    
    function criarGraficoAgentes(ranking) {
      if (custoAgentesChart) {
        custoAgentesChart.destroy();
      }
      
      const ctx = document.getElementById('custoAgentesChart').getContext('2d');
      
      // Extrair dados para o gráfico
      const labels = ranking.map(item => item.fornecedor);
      const data = ranking.map(item => item.custo);
      const backgroundColors = [
        'rgba(54, 162, 235, 0.5)',
        'rgba(255, 99, 132, 0.5)',
        'rgba(255, 206, 86, 0.5)',
        'rgba(75, 192, 192, 0.5)',
        'rgba(153, 102, 255, 0.5)',
        'rgba(255, 159, 64, 0.5)',
        'rgba(199, 199, 199, 0.5)'
      ];
      
      custoAgentesChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Custo (R$)',
            data: data,
            backgroundColor: backgroundColors.slice(0, labels.length),
            borderColor: backgroundColors.map(color => color.replace('0.5', '1')),
            borderWidth: 1
          }]
        },
        options: {
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: 'Custo (R$)'
              }
            },
            x: {
              title: {
                display: true,
                text: 'Fornecedor'
              }
            }
          },
          plugins: {
            title: {
              display: true,
              text: 'Comparação de Custos por Fornecedor'
            }
          }
        }
      });
    }

    $(document).ready(function() {
      $('.select2-enable').select2();
      
      // Carregar histórico
      carregarHistorico();
      
      // Atualizar histórico quando a aba for selecionada
      $('a[data-bs-toggle="tab"]').on('shown.bs.tab', function(e) {
        if ($(e.target).attr('href') === '#tab-historico') {
          carregarHistorico();
        }
      });

      // Carregar estados
      $.get('/estados', function(data) {
        ['#uf_origem', '#uf_destino', '#uf_origem_frac', '#uf_destino_frac'].forEach(function(id) {
          $(id).append('<option value="">Selecione</option>');
          data.forEach(function(estado) {
            $(id).append(`<option value="${estado.id}">${estado.text}</option>`);
          });
        });
      });

      // Carregar municípios
      ['#uf_origem', '#uf_destino', '#uf_origem_frac', '#uf_destino_frac'].forEach(function(id, index) {
        $(id).change(function() {
          let uf = $(this).val();
          let target = ['#municipio_origem', '#municipio_destino', '#municipio_origem_frac', '#municipio_destino_frac'][index];
          $(target).prop('disabled', true).empty().append('<option value="">Selecione</option>');
          if (uf) {
            $.get(`/municipios/${uf}`, function(data) {
              data.forEach(function(municipio) {
                $(target).append(`<option value="${municipio.id}">${municipio.text}</option>`);
              });
              $(target).prop('disabled', false);
            });
          }
        });
      });

      // Calcular frete dedicado
      $('#btn_calcular').click(function() {
        let data = {
          uf_origem: $('#uf_origem').val(),
          municipio_origem: $('#municipio_origem').val(),
          uf_destino: $('#uf_destino').val(),
          municipio_destino: $('#municipio_destino').val(),
          peso: $('#peso').val() || 0,
          cubagem: $('#cubagem').val() || 0
        };
        if (!data.uf_origem || !data.municipio_origem || !data.uf_destino || !data.municipio_destino) {
          alert('Preencha todos os campos obrigatórios.');
          return;
        }
        $.ajax({
          url: '/calcular',
          type: 'POST',
          contentType: 'application/json',
          data: JSON.stringify(data),
          success: function(response) {
            resultadoDedicado = response;
            
            $('#id-historico-dedicado').text(response.id_historico);
            $('#res-origem').text(`${data.municipio_origem} - ${data.uf_origem}`);
            $('#res-destino').text(`${data.municipio_destino} - ${data.uf_destino}`);
            $('#res-distancia').text(response.distancia);
            let horas = Math.floor(response.duracao / 60);
            let minutos = Math.round(response.duracao % 60);
            $('#res-tempo').text(`${horas}h ${minutos}min`);
            $('#res-consumo').text((response.distancia / 10).toFixed(2));
            $('#res-co2').text(((response.distancia / 10) * 2.3).toFixed(2));
            $('#res-pedagio').text((response.distancia * 0.15).toFixed(2));
            $('#res-peso').text(response.peso > 0 ? `${response.peso} kg` : 'Não informado');
            $('#res-cubagem').text(response.cubagem > 0 ? `${response.cubagem} m³` : 'Não informado');

            let html = '';
            for (let tipo in response.custos) {
              html += `<tr><td>${tipo}</td><td>R$ ${response.custos[tipo].toFixed(2)}</td></tr>`;
            }
            $('#tabela-resultado').html(html);
            $('#resultados').show();

            initMap(response.rota_pontos);

            let ctx = document.getElementById('custoChart').getContext('2d');
            new Chart(ctx, {
              type: 'bar',
              data: {
                labels: Object.keys(response.custos),
                datasets: [{
                  label: 'Custo (R$)',
                  data: Object.values(response.custos),
                  backgroundColor: 'rgba(54, 162, 235, 0.5)',
                  borderColor: 'rgba(54, 162, 235, 1)',
                  borderWidth: 1
                }]
              },
              options: { 
                maintainAspectRatio: false,
                scales: { 
                  y: { 
                    beginAtZero: true,
                    title: {
                      display: true,
                      text: 'Custo (R$)'
                    }
                  },
                  x: {
                    title: {
                      display: true,
                      text: 'Tipo de Veículo'
                    }
                  }
                },
                plugins: {
                  title: {
                    display: true,
                    text: 'Custos por Tipo de Veículo'
                  }
                }
              }
            });
            
            // Atualizar histórico
            carregarHistorico();
          }
        });
      });

      // Gerar PDF para Dedicado
      $('#btn_gerar_pdf').click(function() {
        if (!resultadoDedicado || !resultadoDedicado.analise) {
          alert('Nenhum resultado disponível para gerar PDF.');
          return;
        }
        
        $.ajax({
          url: '/gerar-pdf',
          type: 'POST',
          contentType: 'application/json',
          data: JSON.stringify({ analise: resultadoDedicado.analise }),
          success: function(response, status, xhr) {
            // Criar um blob a partir da resposta
            var blob = new Blob([response], { type: xhr.getResponseHeader('content-type') });
            var link = document.createElement('a');
            link.href = window.URL.createObjectURL(blob);
            link.download = 'relatorio_dedicado.pdf';
            link.click();
          },
          error: function(xhr, status, error) {
            alert('Erro ao gerar PDF: ' + error);
          }
        });
      });
      
      // Exportar Excel para Dedicado
      $('#btn_exportar_excel').click(function() {
        if (!resultadoDedicado || !resultadoDedicado.analise) {
          alert('Nenhum resultado disponível para exportar.');
          return;
        }
        
        $.ajax({
          url: '/exportar-excel',
          type: 'POST',
          contentType: 'application/json',
          data: JSON.stringify({ 
            tipo: 'Dedicado', 
            dados: resultadoDedicado.analise 
          }),
          success: function(response, status, xhr) {
            // Criar um blob a partir da resposta
            var blob = new Blob([response], { type: xhr.getResponseHeader('content-type') });
            var link = document.createElement('a');
            link.href = window.URL.createObjectURL(blob);
            link.download = 'dados_dedicado.xlsx';
            link.click();
          },
          error: function(xhr, status, error) {
            alert('Erro ao exportar Excel: ' + error);
          }
        });
      });
      
      // Gerar PDF para Fracionado
      $('#btn_gerar_pdf_fracionado').click(function() {
        // Obter dados do resultado atual
        let resultado = {{ resultado | tojson if resultado else 'null' }};
        
        if (!resultado) {
          alert('Nenhum resultado disponível para gerar PDF.');
          return;
        }
        
        // Preparar dados para o PDF
        let analise = {
          id_historico: resultado.id_historico,
          tipo: 'Fracionado',
          origem: resultado.cidades_origem + ' - ' + resultado.uf_origem,
          destino: resultado.cidades_destino + ' - ' + resultado.uf_destino,
          distancia: resultado.distancia,
          data_hora: new Date().toLocaleString(),
          ranking: resultado.ranking,
          melhor_preco: resultado.melhor_preco,
          melhor_prazo: resultado.melhor_prazo,
          pior_preco: resultado.pior_preco,
          diferenca_valor: resultado.diferenca_valor,
          diferenca_percentual: resultado.diferenca_percentual
        };
        
        $.ajax({
          url: '/gerar-pdf',
          type: 'POST',
          contentType: 'application/json',
          data: JSON.stringify({ analise: analise }),
          success: function(response, status, xhr) {
            // Criar um blob a partir da resposta
            var blob = new Blob([response], { type: xhr.getResponseHeader('content-type') });
            var link = document.createElement('a');
            link.href = window.URL.createObjectURL(blob);
            link.download = 'relatorio_fracionado.pdf';
            link.click();
          },
          error: function(xhr, status, error) {
            alert('Erro ao gerar PDF: ' + error);
          }
        });
      });
      
      // Exportar Excel para Fracionado
      $('#btn_exportar_excel_fracionado').click(function() {
        // Obter dados do resultado atual
        let resultado = {{ resultado | tojson if resultado else 'null' }};
        
        if (!resultado) {
          alert('Nenhum resultado disponível para exportar.');
          return;
        }
        
        $.ajax({
          url: '/exportar-excel',
          type: 'POST',
          contentType: 'application/json',
          data: JSON.stringify({ 
            tipo: 'Fracionado', 
            dados: resultado 
          }),
          success: function(response, status, xhr) {
            // Criar um blob a partir da resposta
            var blob = new Blob([response], { type: xhr.getResponseHeader('content-type') });
            var link = document.createElement('a');
            link.href = window.URL.createObjectURL(blob);
            link.download = 'dados_fracionado.xlsx';
            link.click();
          },
          error: function(xhr, status, error) {
            alert('Erro ao exportar Excel: ' + error);
          }
        });
      });

      // Criar gráfico de custos por agente
      {% if resultado and resultado.ranking %}
        $(document).ready(function() {
          // Criar gráfico de custos por agente
          criarGraficoAgentes({{ resultado.ranking | tojson }});
        });
      {% endif %}
    });
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5006)
