from flask import Flask, render_template_string, request, jsonify, send_file
import requests
import math
import os
import datetime
import json
from fpdf2 import FPDF
import io
import polyline

app = Flask(__name__)

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

def geocode(municipio, uf):
    """Obtém coordenadas usando OpenStreetMap"""
    url = "https://nominatim.openstreetmap.org/search"
    params = {'q': f'{municipio}, {uf}, Brasil', 'format': 'json', 'limit': 1}
    headers = {'User-Agent': 'TransportCostCalculator/1.0'}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        if data:
            return (float(data[0]['lat']), float(data[0]['lon']), data[0].get('display_name', ''))
        return None
    except Exception as e:
        print(f"Erro ao geocodificar: {e}")
        return None

def calcular_distancia_osrm(origem, destino):
    """Calcula distância de rota via OSRM"""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{origem[1]},{origem[0]};{destino[1]},{destino[0]}"
        response = requests.get(url, params={'overview': 'full'}, timeout=15)
        data = response.json()
        if data.get('code') == 'Ok' and data.get('routes'):
            route = data['routes'][0]
            distance = route['distance'] / 1000  # km
            duration = route['duration'] / 60  # minutos
            geometry = route.get('geometry', '')
            
            # Decodificar a geometria da rota (formato polyline)
            route_points = []
            if geometry:
                try:
                    route_points = polyline.decode(geometry)
                except Exception as e:
                    print(f"Erro ao decodificar geometria: {e}")
            
            return {
                'distance': distance,
                'duration': duration,
                'route_points': route_points,
                'provider': 'OSRM'
            }
        return None
    except Exception as e:
        print(f"Erro ao calcular rota OSRM: {e}")
        return None

def calcular_distancia_openroute(origem, destino):
    """Calcula distância de rota via OpenRouteService como backup"""
    try:
        # Usando API pública sem chave (limitada, mas funcional para demonstração)
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {'Accept': 'application/json'}
        params = {
            'start': f"{origem[1]},{origem[0]}",
            'end': f"{destino[1]},{destino[0]}"
        }
        response = requests.get(url, headers=headers, params=params, timeout=15)
        data = response.json()
        
        if 'features' in data and data['features']:
            route = data['features'][0]
            properties = route.get('properties', {})
            segments = properties.get('segments', [{}])[0]
            
            distance = segments.get('distance', 0) / 1000  # km
            duration = segments.get('duration', 0) / 60  # minutos
            
            # Extrair pontos da rota
            geometry = route.get('geometry', {})
            route_points = []
            if geometry and 'coordinates' in geometry:
                # Converter [lon, lat] para [lat, lon]
                route_points = [[coord[1], coord[0]] for coord in geometry['coordinates']]
            
            return {
                'distance': distance,
                'duration': duration,
                'route_points': route_points,
                'provider': 'OpenRouteService'
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
        R = 6371  # Raio da Terra em km
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        
        # Estimar duração (velocidade média de 80 km/h)
        duration = (distance / 80) * 60
        
        # Criar pontos em linha reta para visualização
        route_points = [
            [lat1, lon1],
            [lat2, lon2]
        ]
        
        return {
            'distance': distance,
            'duration': duration,
            'route_points': route_points,
            'provider': 'Linha Reta'
        }
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
    """Gera análise detalhada do trajeto"""
    origem_nome = origem_info[2] if len(origem_info) > 2 else "Origem"
    destino_nome = destino_info[2] if len(destino_info) > 2 else "Destino"
    
    # Calcular tempo estimado em formato legível
    horas = int(rota_info['duration'] // 60)
    minutos = int(rota_info['duration'] % 60)
    tempo_estimado = f"{horas}h {minutos}min" if horas > 0 else f"{minutos}min"
    
    # Calcular consumo estimado de combustível (média de 10 km/l)
    consumo_combustivel = rota_info['distance'] / 10
    
    # Calcular emissão de CO2 (média de 2.3 kg CO2 por litro de diesel)
    emissao_co2 = consumo_combustivel * 2.3
    
    # Calcular custo de pedágio estimado (valor fictício baseado na distância)
    pedagio_estimado = rota_info['distance'] * 0.15
    
    analise = {
        "origem": origem_nome,
        "destino": destino_nome,
        "distancia": round(rota_info['distance'], 2),
        "tempo_estimado": tempo_estimado,
        "duracao_minutos": round(rota_info['duration'], 2),
        "consumo_combustivel": round(consumo_combustivel, 2),
        "emissao_co2": round(emissao_co2, 2),
        "pedagio_estimado": round(pedagio_estimado, 2),
        "provider": rota_info['provider'],
        "custos": custos,
        "data_hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "rota_pontos": rota_info['route_points']
    }
    
    return analise

class PDF(FPDF):
    def header(self):
        # Logo
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, '📦 PortoEx - Relatório de Transporte', 0, 1, 'C')
        self.line(10, 20, 200, 20)
        self.ln(10)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
        self.cell(0, 10, f'© {datetime.datetime.now().year} PortoEx - Todos os direitos reservados', 0, 0, 'R')

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/estados')
def estados():
    response = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome")
    return jsonify([{"sigla": e['sigla'], "nome": e['nome']} for e in response.json()])

@app.route('/municipios/<uf>')
def municipios(uf):
    response = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios")
    return jsonify([{"nome": m['nome']} for m in response.json()])

@app.route('/calcular', methods=['POST'])
def calcular():
    data = request.json
    municipio_origem = data['municipio_origem']
    uf_origem = data['uf_origem']
    municipio_destino = data['municipio_destino']
    uf_destino = data['uf_destino']

    # Geocodificar origem e destino
    coord_origem = geocode(municipio_origem, uf_origem)
    coord_destino = geocode(municipio_destino, uf_destino)

    if not coord_origem or not coord_destino:
        return jsonify({"error": "Não foi possível identificar os locais"}), 400

    # Tentar calcular rota usando OSRM
    rota_info = calcular_distancia_osrm(coord_origem, coord_destino)
    
    # Se OSRM falhar, tentar OpenRouteService
    if not rota_info:
        rota_info = calcular_distancia_openroute(coord_origem, coord_destino)
    
    # Se ambos falharem, usar linha reta como último recurso
    if not rota_info:
        rota_info = calcular_distancia_reta(coord_origem, coord_destino)
        if not rota_info:
            return jsonify({"error": "Não foi possível calcular a distância"}), 500

    distancia = rota_info['distance']
    faixa = determinar_faixa(distancia)
    
    if not faixa:
        return jsonify({"error": "Distância fora da faixa suportada (acima de 4500 km)"}), 400

    custos = TABELA_CUSTOS[faixa]
    
    # Gerar análise detalhada
    analise = gerar_analise_trajeto(coord_origem, coord_destino, rota_info, custos)
    
    # Adicionar ao histórico
    HISTORICO_PESQUISAS.append(analise)
    
    # Limitar histórico a 50 itens
    if len(HISTORICO_PESQUISAS) > 50:
        HISTORICO_PESQUISAS.pop(0)
    
    return jsonify({
        "distancia": round(distancia, 2),
        "duracao": round(rota_info['duration'], 2),
        "tipo_distancia": rota_info['provider'],
        "custos": custos,
        "rota_pontos": rota_info['route_points'],
        "analise": analise
    })

@app.route('/historico')
def historico():
    return jsonify(HISTORICO_PESQUISAS)

@app.route('/gerar-pdf', methods=['POST'])
def gerar_pdf():
    data = request.json
    analise = data.get('analise')
    
    if not analise:
        return jsonify({"error": "Dados de análise não fornecidos"}), 400
    
    # Criar PDF usando FPDF
    pdf = PDF()
    pdf.add_page()
    
    # Título e data
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Análise de Trajeto', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, f"Data: {analise['data_hora']}", 0, 1, 'L')
    pdf.ln(5)
    
    # Informações da rota
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Rota', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, f"Origem: {analise['origem']}", 0, 1, 'L')
    pdf.cell(0, 8, f"Destino: {analise['destino']}", 0, 1, 'L')
    pdf.cell(0, 8, f"Método de cálculo: {analise['provider']}", 0, 1, 'L')
    pdf.ln(5)
    
    # Estatísticas principais
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Estatísticas', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    
    # Criar tabela de estatísticas
    stats = [
        ["Distância total", f"{analise['distancia']} km"],
        ["Tempo estimado", f"{analise['tempo_estimado']}"],
        ["Consumo estimado", f"{analise['consumo_combustivel']} L"],
        ["Emissão de CO₂", f"{analise['emissao_co2']} kg"]
    ]
    
    for stat in stats:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(80, 8, stat[0], 1, 0, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(80, 8, stat[1], 1, 1, 'L')
    
    pdf.ln(5)
    
    # Custos por tipo de veículo
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Custos por Tipo de Veículo', 0, 1, 'L')
    
    # Cabeçalho da tabela
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(80, 8, "Tipo de Veículo", 1, 0, 'C')
    pdf.cell(80, 8, "Custo (R$)", 1, 1, 'C')
    
    # Dados da tabela
    pdf.set_font('Arial', '', 10)
    for veiculo, valor in analise['custos'].items():
        pdf.cell(80, 8, veiculo, 1, 0, 'L')
        pdf.cell(80, 8, f"R$ {valor:.2f}", 1, 1, 'R')
    
    pdf.ln(5)
    
    # Informações adicionais
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Informações Adicionais', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, f"Pedágio estimado: R$ {analise['pedagio_estimado']:.2f}", 0, 1, 'L')
    
    pdf.ln(5)
    pdf.multi_cell(0, 8, "Observações: Os valores apresentados são estimativas baseadas em cálculos aproximados e podem variar de acordo com condições específicas da rota, clima, tráfego e outros fatores.", 0, 'L')
    
    # Gerar PDF
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    
    # Retornar o PDF como resposta
    return send_file(
        pdf_output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"relatorio_transporte_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )

# Template HTML com design futurista e usabilidade aprimorada
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <title>PortoEx - Calculadora de Transporte Futurista</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css">
    <style>
        :root { 
            --cor-primaria: #1a2b45; 
            --cor-secundaria: #3498db; 
            --cor-terciaria: #2ecc71;
            --cor-destaque: #e74c3c;
            --cor-whatsapp: #25D366;
            --cor-fundo: #f0f2f5;
            --cor-card: #ffffff;
            --cor-texto: #333333;
            --cor-texto-claro: #ffffff;
            --sombra-padrao: 0 4px 20px rgba(0, 0, 0, 0.1);
            --borda-radius: 12px;
            --transicao: all 0.3s ease;
        }
        
        [data-theme="dark"] {
            --cor-primaria: #0f172a; 
            --cor-secundaria: #3b82f6; 
            --cor-terciaria: #22c55e;
            --cor-destaque: #ef4444;
            --cor-fundo: #1e293b;
            --cor-card: #334155;
            --cor-texto: #f1f5f9;
            --cor-texto-claro: #ffffff;
            --sombra-padrao: 0 4px 20px rgba(0, 0, 0, 0.3);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            transition: var(--transicao);
        }
        
        body { 
            font-family: 'Segoe UI', system-ui, sans-serif; 
            background: var(--cor-fundo); 
            color: var(--cor-texto);
            min-height: 100vh;
            padding: 0;
            margin: 0;
        }
        
        .container { 
            max-width: 1200px; 
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: var(--cor-primaria);
            color: var(--cor-texto-claro);
            padding: 20px 0;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: var(--sombra-padrao);
        }
        
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 24px;
            font-weight: bold;
        }
        
        .logo i {
            font-size: 28px;
            color: var(--cor-secundaria);
        }
        
        .theme-toggle {
            background: transparent;
            border: none;
            color: var(--cor-texto-claro);
            font-size: 20px;
            cursor: pointer;
            padding: 8px;
            border-radius: 50%;
            transition: background-color 0.3s;
        }
        
        .theme-toggle:hover {
            background-color: rgba(255, 255, 255, 0.1);
        }
        
        .card { 
            background: var(--cor-card); 
            border-radius: var(--borda-radius); 
            padding: 30px; 
            box-shadow: var(--sombra-padrao);
            margin: 20px 0; 
            transition: transform 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-5px);
        }
        
        h1 { 
            color: var(--cor-primaria); 
            text-align: center; 
            margin-bottom: 30px;
            font-size: 2.2rem;
            font-weight: 700;
        }
        
        h2 {
            color: var(--cor-secundaria);
            margin-bottom: 20px;
            font-size: 1.8rem;
            font-weight: 600;
        }
        
        h3 {
            color: var(--cor-primaria);
            margin: 15px 0;
            font-size: 1.4rem;
            font-weight: 600;
        }
        
        .seletores {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }
        
        @media (max-width: 768px) {
            .seletores {
                grid-template-columns: 1fr;
            }
        }
        
        .select2-container--default .select2-selection--single { 
            border: 2px solid #e2e8f0 !important; 
            border-radius: 10px !important; 
            height: 50px !important;
            background-color: var(--cor-card) !important;
            color: var(--cor-texto) !important;
        }
        
        .select2-container--default .select2-selection__rendered { 
            line-height: 50px !important;
            color: var(--cor-texto) !important;
            padding-left: 15px !important;
        }
        
        .select2-container--default .select2-selection__arrow {
            height: 48px !important;
        }
        
        .select2-dropdown {
            border-radius: 10px !important;
            border: 2px solid #e2e8f0 !important;
            background-color: var(--cor-card) !important;
        }
        
        .select2-results__option {
            padding: 10px 15px !important;
            color: var(--cor-texto) !important;
        }
        
        .select2-container--default .select2-results__option--highlighted[aria-selected] {
            background-color: var(--cor-secundaria) !important;
        }
        
        button { 
            background: var(--cor-secundaria) !important; 
            color: white !important; 
            border: none !important; 
            padding: 15px 25px !important; 
            border-radius: 10px !important; 
            cursor: pointer !important; 
            width: 100%; 
            font-size: 16px; 
            font-weight: 600;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }
        
        button:hover { 
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(52, 152, 219, 0.3);
        }
        
        button:active {
            transform: translateY(0);
        }
        
        .btn-primary {
            background: var(--cor-secundaria) !important;
        }
        
        .btn-success {
            background: var(--cor-terciaria) !important;
        }
        
        .btn-danger {
            background: var(--cor-destaque) !important;
        }
        
        .btn-whatsapp {
            background: var(--cor-whatsapp) !important;
        }
        
        table { 
            width: 100%; 
            margin-top: 20px; 
            border-collapse: collapse; 
            border-radius: var(--borda-radius);
            overflow: hidden;
        }
        
        th, td { 
            padding: 15px; 
            text-align: left; 
            border-bottom: 1px solid rgba(0,0,0,0.1); 
        }
        
        th { 
            background: var(--cor-primaria); 
            color: white; 
        }
        
        tr:nth-child(even) {
            background-color: rgba(0,0,0,0.02);
        }
        
        tr:hover {
            background-color: rgba(0,0,0,0.05);
        }
        
        .resultado { 
            margin-top: 20px; 
            padding: 20px; 
            background: rgba(52, 152, 219, 0.1); 
            border-radius: var(--borda-radius); 
            border-left: 5px solid var(--cor-secundaria);
        }
        
        .erro { 
            color: var(--cor-destaque); 
            background: rgba(231, 76, 60, 0.1); 
            padding: 15px; 
            border-radius: var(--borda-radius);
            border-left: 5px solid var(--cor-destaque);
            margin: 20px 0;
        }
        
        .whatsapp-buttons { 
            margin-top: 20px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .pdf-section {
            margin: 20px 0;
            border-top: 2px solid rgba(0,0,0,0.1);
            padding-top: 20px;
        }
        
        .instrucoes {
            color: var(--cor-texto); 
            margin-top: 15px; 
            font-size: 0.9em;
            padding: 15px;
            background: rgba(0,0,0,0.05);
            border-radius: var(--borda-radius);
        }
        
        .map-container {
            height: 400px;
            width: 100%;
            border-radius: var(--borda-radius);
            overflow: hidden;
            margin: 20px 0;
            box-shadow: var(--sombra-padrao);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        
        .stat-card {
            background: var(--cor-card);
            border-radius: var(--borda-radius);
            padding: 20px;
            box-shadow: var(--sombra-padrao);
            text-align: center;
            transition: transform 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: var(--cor-secundaria);
            margin: 10px 0;
        }
        
        .stat-label {
            font-size: 14px;
            color: var(--cor-texto);
            opacity: 0.8;
        }
        
        .stat-icon {
            font-size: 24px;
            color: var(--cor-secundaria);
            margin-bottom: 10px;
        }
        
        .tabs {
            display: flex;
            margin-bottom: 20px;
            border-bottom: 2px solid rgba(0,0,0,0.1);
        }
        
        .tab {
            padding: 15px 20px;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .tab.active {
            border-bottom: 3px solid var(--cor-secundaria);
            color: var(--cor-secundaria);
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .chart-container {
            height: 300px;
            margin: 20px 0;
        }
        
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100px;
        }
        
        .loading-spinner {
            border: 5px solid rgba(0,0,0,0.1);
            border-top: 5px solid var(--cor-secundaria);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .tooltip {
            position: relative;
            display: inline-block;
            cursor: help;
        }
        
        .tooltip .tooltiptext {
            visibility: hidden;
            width: 200px;
            background-color: var(--cor-primaria);
            color: var(--cor-texto-claro);
            text-align: center;
            border-radius: 6px;
            padding: 10px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            opacity: 0;
            transition: opacity 0.3s;
        }
        
        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
        
        .footer {
            background: var(--cor-primaria);
            color: var(--cor-texto-claro);
            padding: 30px 0;
            margin-top: 50px;
            text-align: center;
        }
        
        .footer-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
        }
        
        .footer-links {
            display: flex;
            gap: 20px;
        }
        
        .footer-links a {
            color: var(--cor-texto-claro);
            text-decoration: none;
        }
        
        .footer-links a:hover {
            color: var(--cor-secundaria);
        }
        
        .copyright {
            margin-top: 20px;
            font-size: 14px;
            opacity: 0.8;
        }
        
        /* Animações */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .animate-fade-in {
            animation: fadeIn 0.5s ease forwards;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        
        .pulse {
            animation: pulse 2s infinite;
        }
        
        /* Responsividade */
        @media (max-width: 992px) {
            .container {
                padding: 15px;
            }
            
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        
        @media (max-width: 768px) {
            .header-content {
                flex-direction: column;
                gap: 15px;
            }
            
            .seletores {
                grid-template-columns: 1fr;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .whatsapp-buttons {
                grid-template-columns: 1fr;
            }
            
            .card {
                padding: 20px;
            }
            
            h1 {
                font-size: 1.8rem;
            }
            
            h2 {
                font-size: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <div class="header-content">
                <div class="logo">
                    <i class="fas fa-truck-fast"></i>
                    <span>PortoEx</span>
                </div>
                <button id="theme-toggle" class="theme-toggle">
                    <i class="fas fa-moon"></i>
                </button>
            </div>
        </div>
    </div>

    <div class="container">
        <h1 class="animate-fade-in">Calculadora de Custos de Transporte</h1>
        
        <div class="tabs">
            <div class="tab active" data-tab="calculator">Calculadora</div>
            <div class="tab" data-tab="history">Histórico</div>
            <div class="tab" data-tab="about">Sobre</div>
        </div>
        
        <div id="calculator-tab" class="tab-content active">
            <div class="card animate-fade-in">
                <div class="seletores">
                    <div>
                        <h3><i class="fas fa-map-marker-alt"></i> Origem</h3>
                        <select id="estado-origem" class="js-example-basic-single">
                            <option value="">Selecione o estado</option>
                        </select>
                        <select id="municipio-origem" class="js-example-basic-single" disabled>
                            <option value="">Selecione o município</option>
                        </select>
                    </div>
                    <div>
                        <h3><i class="fas fa-flag-checkered"></i> Destino</h3>
                        <select id="estado-destino" class="js-example-basic-single">
                            <option value="">Selecione o estado</option>
                        </select>
                        <select id="municipio-destino" class="js-example-basic-single" disabled>
                            <option value="">Selecione o município</option>
                        </select>
                    </div>
                </div>
                <button onclick="calcular()" class="btn-primary">
                    <i class="fas fa-calculator"></i> CALCULAR CUSTOS
                </button>
            </div>
    
            <div id="loading" class="loading" style="display: none;">
                <div class="loading-spinner"></div>
            </div>
    
            <div id="resultado"></div>
            
            <div id="map-container" class="map-container" style="display: none;"></div>
            
            <div id="stats-container" class="stats-grid" style="display: none;"></div>
            
            <div id="chart-container" class="chart-container" style="display: none;">
                <canvas id="custos-chart"></canvas>
            </div>
    
            <div id="pdf-section" class="pdf-section" style="display: none;">
                <button id="downloadPDF" class="btn-success">
                    <i class="fas fa-file-pdf"></i> Baixar Relatório PDF
                </button>
                
                <div class="whatsapp-buttons">
                    <!-- Lista de contatos do WhatsApp -->
                    <button onclick="compartilharWhatsApp('5547997863038')" class="btn-whatsapp">
                        <i class="fab fa-whatsapp"></i> Biel (Controladoria)
                    </button>
                    <button onclick="compartilharWhatsApp('554796727002')" class="btn-whatsapp">
                        <i class="fab fa-whatsapp"></i> Léo (Controladoria)
                    </button>
                    <button onclick="compartilharWhatsApp('5547984210621')" class="btn-whatsapp">
                        <i class="fab fa-whatsapp"></i> Chico (Controladoria)
                    </button>
                    <button onclick="compartilharWhatsApp('5547984997020')" class="btn-whatsapp">
                        <i class="fab fa-whatsapp"></i> Tiago (Comercial)
                    </button>
                    <button onclick="compartilharWhatsApp('5547997244552')" class="btn-whatsapp">
                        <i class="fab fa-whatsapp"></i> Sabrina (Comercial)
                    </button>
                    <button onclick="compartilharWhatsApp('5547996410944')" class="btn-whatsapp">
                        <i class="fab fa-whatsapp"></i> Caio (Comercial)
                    </button>
                    <button onclick="compartilharWhatsApp('5511996996282')" class="btn-whatsapp">
                        <i class="fab fa-whatsapp"></i> Marcela (Comercial)
                    </button>
                </div>
    
                <div class="instrucoes">
                    <h3><i class="fas fa-info-circle"></i> Instruções</h3>
                    <ol>
                        <li>Após calcular, clique em "Baixar Relatório PDF" para gerar o arquivo</li>
                        <li>Escolha o contato desejado nos botões acima para compartilhar via WhatsApp</li>
                        <li>Anexe manualmente o PDF na conversa do WhatsApp que será aberta</li>
                    </ol>
                </div>
            </div>
        </div>
        
        <div id="history-tab" class="tab-content">
            <div class="card">
                <h2><i class="fas fa-history"></i> Histórico de Pesquisas</h2>
                <div id="historico-container">
                    <p>Carregando histórico...</p>
                </div>
            </div>
        </div>
        
        <div id="about-tab" class="tab-content">
            <div class="card">
                <h2><i class="fas fa-info-circle"></i> Sobre a Calculadora</h2>
                <p>A Calculadora de Custos de Transporte PortoEx é uma ferramenta avançada para estimar custos de transporte entre municípios brasileiros.</p>
                <p>Características principais:</p>
                <ul>
                    <li>Cálculo de rotas reais utilizando serviços de mapeamento</li>
                    <li>Estimativas de tempo, distância e custos por tipo de veículo</li>
                    <li>Análises detalhadas com consumo de combustível e emissão de CO₂</li>
                    <li>Geração de relatórios em PDF para compartilhamento</li>
                    <li>Visualização de rotas em mapa interativo</li>
                </ul>
                <p>Versão: 2.0 (2025)</p>
            </div>
        </div>
    </div>
    
    <div class="footer">
        <div class="container">
            <div class="footer-content">
                <div class="logo">
                    <i class="fas fa-truck-fast"></i>
                    <span>PortoEx</span>
                </div>
                <div class="footer-links">
                    <a href="#">Termos de Uso</a>
                    <a href="#">Política de Privacidade</a>
                    <a href="#">Contato</a>
                </div>
                <div class="copyright">
                    © 2025 PortoEx - Todos os direitos reservados
                </div>
            </div>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
    <script>
        // Variáveis globais
        let map;
        let routeLayer;
        let currentAnalise = null;
        let custoChart = null;
        
        // Inicialização
        $(document).ready(function() {
            // Inicializar Select2
            $('.js-example-basic-single').select2({
                placeholder: "Digite para buscar...",
                minimumInputLength: 2,
                width: '100%',
                language: {
                    inputTooShort: function() {
                        return "Digite pelo menos 2 caracteres para buscar...";
                    },
                    noResults: function() {
                        return "Nenhum resultado encontrado";
                    },
                    searching: function() {
                        return "Buscando...";
                    }
                }
            });

            // Carregar estados
            fetch('/estados')
                .then(r => r.json())
                .then(estados => {
                    $('#estado-origem, #estado-destino').empty().select2({
                        data: estados.map(e => ({id: e.sigla, text: `${e.nome} (${e.sigla})`}))
                    });
                });

            // Eventos de seleção de estados
            $('#estado-origem').on('select2:select', function(e) {
                const uf = e.params.data.id;
                carregarMunicipios(uf, '#municipio-origem');
            });

            $('#estado-destino').on('select2:select', function(e) {
                const uf = e.params.data.id;
                carregarMunicipios(uf, '#municipio-destino');
            });
            
            // Inicializar mapa
            inicializarMapa();
            
            // Configurar abas
            $('.tab').click(function() {
                const tabId = $(this).data('tab');
                
                // Ativar aba
                $('.tab').removeClass('active');
                $(this).addClass('active');
                
                // Mostrar conteúdo da aba
                $('.tab-content').removeClass('active');
                $(`#${tabId}-tab`).addClass('active');
                
                // Carregar dados específicos da aba
                if (tabId === 'history') {
                    carregarHistorico();
                }
            });
            
            // Configurar alternância de tema
            $('#theme-toggle').click(function() {
                if ($('body').attr('data-theme') === 'dark') {
                    $('body').removeAttr('data-theme');
                    $(this).html('<i class="fas fa-moon"></i>');
                } else {
                    $('body').attr('data-theme', 'dark');
                    $(this).html('<i class="fas fa-sun"></i>');
                }
            });
            
            // Configurar botão de PDF
            $('#downloadPDF').click(function() {
                if (currentAnalise) {
                    gerarPDF(currentAnalise);
                }
            });
        });
        
        // Função para carregar municípios
        function carregarMunicipios(uf, seletor) {
            fetch(`/municipios/${uf}`)
                .then(r => r.json())
                .then(municipios => {
                    $(seletor).empty().select2({
                        data: municipios.map(m => ({id: m.nome, text: m.nome}))
                    }).prop('disabled', false);
                });
        }
        
        // Função para inicializar o mapa
        function inicializarMapa() {
            map = L.map('map-container').setView([-15.77972, -47.92972], 5); // Centro no Brasil
            
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }).addTo(map);
        }
        
        // Função para calcular custos
        function calcular() {
            const municipio_origem = $('#municipio-origem').val();
            const uf_origem = $('#estado-origem').val();
            const municipio_destino = $('#municipio-destino').val();
            const uf_destino = $('#estado-destino').val();
            
            if(!municipio_origem || !uf_origem || !municipio_destino || !uf_destino) {
                mostrarResultado('<div class="erro"><i class="fas fa-exclamation-triangle"></i> Selecione origem e destino!</div>');
                return;
            }
            
            // Mostrar loading
            $('#loading').show();
            $('#resultado').hide();
            $('#map-container').hide();
            $('#stats-container').hide();
            $('#chart-container').hide();
            $('#pdf-section').hide();

            fetch('/calcular', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ 
                    municipio_origem, 
                    uf_origem, 
                    municipio_destino, 
                    uf_destino 
                })
            })
            .then(r => r.json())
            .then(data => {
                // Esconder loading
                $('#loading').hide();
                
                if(data.error) {
                    mostrarResultado(`<div class="erro"><i class="fas fa-exclamation-triangle"></i> ${data.error}</div>`);
                } else {
                    // Salvar análise atual
                    currentAnalise = data.analise;
                    
                    // Mostrar resultado
                    mostrarResultadoCompleto(data, municipio_origem, uf_origem, municipio_destino, uf_destino);
                    
                    // Mostrar mapa e desenhar rota
                    $('#map-container').show();
                    desenharRota(data.rota_pontos);
                    
                    // Mostrar estatísticas
                    mostrarEstatisticas(data);
                    
                    // Mostrar gráfico de custos
                    mostrarGraficoCustos(data.custos);
                    
                    // Mostrar seção de PDF
                    $('#pdf-section').show();
                }
            })
            .catch(error => {
                $('#loading').hide();
                console.error('Erro:', error);
                mostrarResultado('<div class="erro"><i class="fas fa-exclamation-triangle"></i> Ocorreu um erro ao processar sua solicitação. Tente novamente.</div>');
            });
        }
        
        // Função para mostrar resultado
        function mostrarResultado(html) {
            $('#resultado').html(html).show();
        }
        
        // Função para mostrar resultado completo
        function mostrarResultadoCompleto(data, municipio_origem, uf_origem, municipio_destino, uf_destino) {
            const tipoDistancia = data.tipo_distancia === 'Linha Reta' ? 
                '<span class="tooltip">linha reta<span class="tooltiptext">Cálculo aproximado em linha reta devido à indisponibilidade de rota viária</span></span>' : 
                'rota viária';
            
            let html = `
                <div class="resultado animate-fade-in">
                    <h2><i class="fas fa-route"></i> Resultado da Rota</h2>
                    <h3>🚚 ${municipio_origem}/${uf_origem} → ${municipio_destino}/${uf_destino}</h3>
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-icon"><i class="fas fa-road"></i></div>
                            <div class="stat-value">${data.distancia.toFixed(2)} km</div>
                            <div class="stat-label">Distância (${data.tipo_distancia})</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon"><i class="fas fa-clock"></i></div>
                            <div class="stat-value">${formatarTempo(data.duracao)}</div>
                            <div class="stat-label">Tempo estimado</div>
                        </div>
                    </div>
                    <h3>Custos por Tipo de Veículo</h3>
                    <table>
                        <tr>
                            <th>Tipo de Veículo</th>
                            <th>Custo (R$)</th>
                        </tr>
                        ${Object.entries(data.custos).map(([modal, valor]) => `
                            <tr>
                                <td>${formatarTipoVeiculo(modal)}</td>
                                <td>R$ ${valor.toFixed(2)}</td>
                            </tr>
                        `).join('')}
                    </table>
                </div>
            `;
            
            mostrarResultado(html);
        }
        
        // Função para desenhar rota no mapa
        function desenharRota(pontos) {
            // Limpar rota anterior
            if (routeLayer) {
                map.removeLayer(routeLayer);
            }
            
            if (!pontos || pontos.length < 2) {
                console.error('Pontos de rota insuficientes');
                return;
            }
            
            // Criar linha da rota
            routeLayer = L.polyline(pontos, {
                color: '#3498db',
                weight: 5,
                opacity: 0.7
            }).addTo(map);
            
            // Adicionar marcadores de origem e destino
            const origem = pontos[0];
            const destino = pontos[pontos.length - 1];
            
            L.marker(origem).addTo(map)
                .bindPopup('Origem')
                .openPopup();
                
            L.marker(destino).addTo(map)
                .bindPopup('Destino');
            
            // Ajustar visualização para mostrar toda a rota
            map.fitBounds(routeLayer.getBounds(), {
                padding: [50, 50]
            });
        }
        
        // Função para mostrar estatísticas
        function mostrarEstatisticas(data) {
            const analise = data.analise;
            
            const html = `
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-gas-pump"></i></div>
                    <div class="stat-value">${analise.consumo_combustivel.toFixed(2)} L</div>
                    <div class="stat-label">Consumo estimado</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-leaf"></i></div>
                    <div class="stat-value">${analise.emissao_co2.toFixed(2)} kg</div>
                    <div class="stat-label">Emissão de CO₂</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-ticket-alt"></i></div>
                    <div class="stat-value">R$ ${analise.pedagio_estimado.toFixed(2)}</div>
                    <div class="stat-label">Pedágio estimado</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-map"></i></div>
                    <div class="stat-value">${analise.provider}</div>
                    <div class="stat-label">Provedor de rota</div>
                </div>
            `;
            
            $('#stats-container').html(html).show();
        }
        
        // Função para mostrar gráfico de custos
        function mostrarGraficoCustos(custos) {
            $('#chart-container').show();
            
            // Destruir gráfico anterior se existir
            if (custoChart) {
                custoChart.destroy();
            }
            
            const ctx = document.getElementById('custos-chart').getContext('2d');
            
            // Preparar dados
            const labels = Object.keys(custos).map(k => formatarTipoVeiculo(k));
            const valores = Object.values(custos);
            
            // Criar gráfico
            custoChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Custo (R$)',
                        data: valores,
                        backgroundColor: [
                            'rgba(52, 152, 219, 0.7)',
                            'rgba(46, 204, 113, 0.7)',
                            'rgba(155, 89, 182, 0.7)',
                            'rgba(52, 73, 94, 0.7)',
                            'rgba(231, 76, 60, 0.7)'
                        ],
                        borderColor: [
                            'rgba(52, 152, 219, 1)',
                            'rgba(46, 204, 113, 1)',
                            'rgba(155, 89, 182, 1)',
                            'rgba(52, 73, 94, 1)',
                            'rgba(231, 76, 60, 1)'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return 'R$ ' + value;
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return 'R$ ' + context.raw.toFixed(2);
                                }
                            }
                        }
                    }
                }
            });
        }
        
        // Função para carregar histórico
        function carregarHistorico() {
            fetch('/historico')
                .then(r => r.json())
                .then(historico => {
                    if (historico.length === 0) {
                        $('#historico-container').html('<p>Nenhuma pesquisa realizada ainda.</p>');
                        return;
                    }
                    
                    let html = '<div class="animate-fade-in">';
                    
                    historico.reverse().forEach((item, index) => {
                        html += `
                            <div class="card">
                                <h3>${item.origem} → ${item.destino}</h3>
                                <p><strong>Data:</strong> ${item.data_hora}</p>
                                <p><strong>Distância:</strong> ${item.distancia.toFixed(2)} km (${item.provider})</p>
                                <p><strong>Tempo estimado:</strong> ${item.tempo_estimado}</p>
                                <button onclick="recarregarAnalise(${index})" class="btn-primary">
                                    <i class="fas fa-sync-alt"></i> Recarregar
                                </button>
                            </div>
                        `;
                    });
                    
                    html += '</div>';
                    
                    $('#historico-container').html(html);
                })
                .catch(error => {
                    console.error('Erro ao carregar histórico:', error);
                    $('#historico-container').html('<p>Erro ao carregar histórico.</p>');
                });
        }
        
        // Função para recarregar análise do histórico
        function recarregarAnalise(index) {
            fetch('/historico')
                .then(r => r.json())
                .then(historico => {
                    if (historico.length > index) {
                        const analise = historico.reverse()[index];
                        currentAnalise = analise;
                        
                        // Mudar para a aba de calculadora
                        $('.tab[data-tab="calculator"]').click();
                        
                        // Mostrar resultado
                        const origemPartes = analise.origem.split(', ');
                        const destinoPartes = analise.destino.split(', ');
                        
                        const data = {
                            distancia: analise.distancia,
                            duracao: analise.duracao_minutos,
                            tipo_distancia: analise.provider,
                            custos: analise.custos,
                            rota_pontos: analise.rota_pontos,
                            analise: analise
                        };
                        
                        mostrarResultadoCompleto(
                            data, 
                            origemPartes[0] || 'Origem', 
                            origemPartes[1] || 'UF', 
                            destinoPartes[0] || 'Destino', 
                            destinoPartes[1] || 'UF'
                        );
                        
                        // Mostrar mapa e desenhar rota
                        $('#map-container').show();
                        desenharRota(analise.rota_pontos);
                        
                        // Mostrar estatísticas
                        mostrarEstatisticas({analise: analise});
                        
                        // Mostrar gráfico de custos
                        mostrarGraficoCustos(analise.custos);
                        
                        // Mostrar seção de PDF
                        $('#pdf-section').show();
                    }
                });
        }
        
        // Função para gerar PDF
        function gerarPDF(analise) {
            fetch('/gerar-pdf', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({analise: analise})
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Erro ao gerar PDF');
                }
                return response.blob();
            })
            .then(blob => {
                // Criar URL para o blob
                const url = window.URL.createObjectURL(blob);
                
                // Criar link para download
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `relatorio_transporte_${new Date().toISOString().replace(/[:.]/g, '_')}.pdf`;
                
                // Adicionar à página e clicar
                document.body.appendChild(a);
                a.click();
                
                // Limpar
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            })
            .catch(error => {
                console.error('Erro ao gerar PDF:', error);
                alert('Erro ao gerar PDF. Tente novamente.');
            });
        }
        
        // Função para compartilhar via WhatsApp
        function compartilharWhatsApp(numero) {
            if (!currentAnalise) return;
            
            const texto = `Segue o formulário de custo de transporte em PDF. Por favor verifique o anexo.`;
            const url = `https://wa.me/${numero}?text=${encodeURIComponent(texto)}`;
            
            window.open(url, '_blank');
        }
        
        // Funções auxiliares
        function formatarTempo(minutos) {
            const horas = Math.floor(minutos / 60);
            const mins = Math.round(minutos % 60);
            
            if (horas > 0) {
                return `${horas}h ${mins}min`;
            } else {
                return `${mins} min`;
            }
        }
        
        function formatarTipoVeiculo(tipo) {
            const tipos = {
                'VAN': 'Van',
                '3/4': 'Caminhão 3/4',
                'TOCO': 'Caminhão Toco',
                'TRUCK': 'Caminhão Truck',
                'CARRETA': 'Carreta'
            };
            
            return tipos[tipo] || tipo;
        }
    </script>
</body>
</html>
'''

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5001)
