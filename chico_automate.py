from flask import Flask, render_template_string, request, jsonify
import requests
import math

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

def geocode(municipio, uf):
    """Obtém coordenadas usando OpenStreetMap"""
    url = "https://nominatim.openstreetmap.org/search"
    params = {'q': f'{municipio}, {uf}, Brasil', 'format': 'json', 'limit': 1}
    headers = {'User-Agent': 'TransportCostCalculator/1.0'}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        return (float(data[0]['lat']), float(data[0]['lon'])) if data else None
    except:
        return None

def calcular_distancia_rota(origem, destino):
    """Calcula distância de rota via OSRM"""
    try:
        url = f"<http://router.project-osrm.org/route/v1/driving/{origem>[1]},{origem[0]};{destino[1]},{destino[0]}"
        response = requests.get(url, params={'overview': 'false'}, timeout=10)
        data = response.json()
        if data['code'] == 'Ok' and data['routes']:
            return data['routes'][0]['distance'] / 1000  # km
        return None
    except:
        return None

def calcular_distancia_reta(origem, destino):
    """Distância em linha reta (Haversine)"""
    lat1, lon1 = origem
    lat2, lon2 = destino
    R = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def determinar_faixa(distancia):
    faixas = [
        (0, 20), (20, 50), (50, 100), (100, 150), (150, 200),
        (200, 250), (250, 300), (300, 400), (400, 600), (600, 800),
        (800, 1000), (1000, 1500), (1500, 2000), (2000, 2500),
        (2500, 3000), (3000, 3500), (3500, 4000), (4000, 4500)
    ]
    for min, max in faixas:
        if min < distancia <= max:
            return f"{min}-{max}"
    return None

@app.route('/')
def index():
    return render_template_string(HTML)

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

    coord_origem = geocode(municipio_origem, uf_origem)
    coord_destino = geocode(municipio_destino, uf_destino)

    if not coord_origem or not coord_destino:
        return jsonify(error="Não foi possível identificar os locais"), 400

    distancia = calcular_distancia_rota(coord_origem, coord_destino)
    tipo_distancia = "rota viária"
    if not distancia:
        distancia = calcular_distancia_reta(coord_origem, coord_destino)
        tipo_distancia = "linha reta"
        if not distancia:
            return jsonify(error="Não foi possível calcular a distância"), 500

    faixa = determinar_faixa(distancia)
    if not faixa:
        return jsonify(error="Distância fora da faixa suportada (acima de 4500 km)"), 400

    return jsonify({
        "distancia": round(distancia, 2),
        "tipo_distancia": tipo_distancia,
        "custos": TABELA_CUSTOS[faixa]
    })

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Calculadora de Transporte</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        :root { 
            --cor-primaria: #2c3e50; 
            --cor-secundaria: #3498db; 
            --cor-whatsapp: #25D366;
        }
        body { 
            font-family: 'Segoe UI', sans-serif; 
            margin: 0; 
            padding: 20px; 
            background: #f5f6fa; 
        }
        .container { 
            max-width: 800px; 
            margin: 0 auto; 
        }
        .card { 
            background: white; 
            border-radius: 10px; 
            padding: 25px; 
            box-shadow: 0 2px 15px rgba(0,0,0,0.1); 
            margin: 20px 0; 
        }
        h1 { 
            color: var(--cor-primaria); 
            text-align: center; 
            margin-bottom: 30px; 
        }
        .select2-container--default .select2-selection--single { 
            border: 2px solid #ddd!important; 
            border-radius: 5px!important; 
            height: 45px!important; 
        }
        .select2-container--default .select2-selection__rendered { 
            line-height: 45px!important; 
        }
        button { 
            background: var(--cor-secundaria)!important; 
            color: white!important; 
            border: none!important; 
            padding: 12px 25px!important; 
            border-radius: 5px!important; 
            cursor: pointer!important; 
            width: 100%; 
            font-size: 16px; 
            transition: opacity 0.3s; 
        }
        button:hover { 
            opacity: 0.9; 
        }
        table { 
            width: 100%; 
            margin-top: 20px; 
            border-collapse: collapse; 
        }
        th, td { 
            padding: 12px; 
            text-align: left; 
            border-bottom: 1px solid #ddd; 
        }
        th { 
            background: var(--cor-primaria); 
            color: white; 
        }
        .resultado { 
            margin-top: 20px; 
            padding: 15px; 
            background: #e8f4fd; 
            border-radius: 5px; 
        }
        .erro { 
            color: #e74c3c; 
            background: #fde8e8; 
            padding: 15px; 
            border-radius: 5px; 
        }
        .whatsapp-buttons { 
            margin-top: 20px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
        }
        .whatsapp-btn {
            background: var(--cor-whatsapp)!important;
            display: flex;
            align-items: center;
            gap: 8px;
            justify-content: center;
        }
        .pdf-section {
            margin: 20px 0;
            border-top: 2px solid #eee;
            padding-top: 20px;
        }
        .instrucoes {
            color: #666; 
            margin-top: 15px; 
            font-size: 0.9em;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📦 Calculadora de Custos de Transporte PortoEx</h1>
        
        <div class="card">
            <div class="seletores">
                <div>
                    <h3>Origem</h3>
                    <select id="estado-origem" class="js-example-basic-single">
                        <option value="">Selecione o estado</option>
                    </select>
                    <select id="municipio-origem" class="js-example-basic-single" disabled>
                        <option value="">Selecione o município</option>
                    </select>
                </div>
                <div>
                    <h3>Destino</h3>
                    <select id="estado-destino" class="js-example-basic-single">
                        <option value="">Selecione o estado</option>
                    </select>
                    <select id="municipio-destino" class="js-example-basic-single" disabled>
                        <option value="">Selecione o município</option>
                    </select>
                </div>
            </div>
            <button onclick="calcular()">CALCULAR CUSTOS</button>
        </div>

        <div id="resultado"></div>

        <div class="pdf-section">
            <button id="downloadPDF" class="pdf-btn">📥 Baixar PDF</button>
            
            <div class="whatsapp-buttons">
                <!-- Lista de contatos do WhatsApp -->
                <a href="https://wa.me/5547997863038?text=Segue%20o%20formul%C3%A1rio%20de%20custo%20de%20transporte%20em%20PDF.%20Por%20favor%20verifique%20o%20anexo." target="_blank">
                    <button class="whatsapp-btn">📎 Biel (Controladoria)</button>
                </a>
                <a href="https://wa.me/554796727002?text=Segue%20o%20formul%C3%A1rio%20de%20custo%20de%20transporte%20em%20PDF.%20Por%20favor%20verifique%20o%20anexo." target="_blank">
                    <button class="whatsapp-btn">📎 Léo (Controladoria)</button>
                </a>
                <a href="https://wa.me/5547984210621?text=Segue%20o%20formul%C3%A1rio%20de%20custo%20de%20transporte%20em%20PDF.%20Por%20favor%20verifique%20o%20anexo." target="_blank">
                    <button class="whatsapp-btn">📎 Chico (Controladoria)</button>
                </a>
                <a href="https://wa.me/5547984997020?text=Segue%20o%20formul%C3%A1rio%20de%20custo%20de%20transporte%20em%20PDF.%20Por%20favor%20verifique%20o%20anexo." target="_blank">
                    <button class="whatsapp-btn">📎 Tiago (Comercial)</button>
                </a>
                <a href="https://wa.me/5547997244552?text=Segue%20o%20formul%C3%A1rio%20de%20custo%20de%20transporte%20em%20PDF.%20Por%20favor%20verifique%20o%20anexo." target="_blank">
                    <button class="whatsapp-btn">📎 Sabrina (Comercial)</button>
                </a>
                <a href="https://wa.me/5547996410944?text=Segue%20o%20formul%C3%A1rio%20de%20custo%20de%20transporte%20em%20PDF.%20Por%20favor%20verifique%20o%20anexo." target="_blank">
                    <button class="whatsapp-btn">📎 Caio (Comercial)</button>
                </a>
                <a href="https://wa.me/5511996996282?text=Segue%20o%20formul%C3%A1rio%20de%20custo%20de%20transporte%20em%20PDF.%20Por%20favor%20verifique%20o%20anexo." target="_blank">
                    <button class="whatsapp-btn">📎 Marcela (Comercial)</button>
                </a>
            </div>

            <div class="instrucoes">
                📌 Instruções: 
                <ol>
                    <li>Após calcular, clique em "Baixar PDF" para gerar o arquivo</li>
                    <li>Escolha o contato desejado nos botões acima</li>
                    <li>Anexe manualmente o PDF na conversa do WhatsApp que será aberta</li>
                </ol>
            </div>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
    <script>
        $(document).ready(function() {
            $('.js-example-basic-single').select2({
                placeholder: "Digite para buscar...",
                minimumInputLength: 2,
                width: '100%'
            });

            fetch('/estados')
                .then(r => r.json())
                .then(estados => {
                    $('#estado-origem, #estado-destino').select2({
                        data: estados.map(e => ({id: e.sigla, text: e.nome}))
                    });
                });

            $('#estado-origem').on('select2:select', function(e) {
                const uf = e.params.data.id;
                fetch(`/municipios/${uf}`)
                    .then(r => r.json())
                    .then(municipios => {
                        $('#municipio-origem').select2({
                            data: municipios.map(m => ({id: m.nome, text: m.nome}))
                        }).prop('disabled', false);
                    });
            });

            $('#estado-destino').on('select2:select', function(e) {
                const uf = e.params.data.id;
                fetch(`/municipios/${uf}`)
                    .then(r => r.json())
                    .then(municipios => {
                        $('#municipio-destino').select2({
                            data: municipios.map(m => ({id: m.nome, text: m.nome}))
                        }).prop('disabled', false);
                    });
            });
        });

        function calcular() {
            const municipio_origem = $('#municipio-origem').val();
            const uf_origem = $('#estado-origem').val();
            const municipio_destino = $('#municipio-destino').val();
            const uf_destino = $('#estado-destino').val();
            
            if(!municipio_origem || !uf_origem || !municipio_destino || !uf_destino) {
                mostrarResultado('<div class="erro">⚠️ Selecione origem e destino!</div>');
                return;
            }

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
                if(data.error) {
                    mostrarResultado(`<div class="erro">⛔ ${data.error}</div>`);
                } else {
                    let html = `
                        <div class="resultado">
                            <h3>🚚 Resultado para ${municipio_origem}/${uf_origem} → ${municipio_destino}/${uf_destino}</h3>
                            <p>📏 Distância calculada: <strong>${data.distancia} km</strong> (${data.tipo_distancia})</p>
                            <table>
                                <tr><th>Modal</th><th>Custo (R$)</th></tr>
                                ${Object.entries(data.custos).map(([modal, valor]) => `
                                    <tr><td>${modal}</td><td>R$ ${valor.toFixed(2)}</td></tr>
                                `).join('')}
                            </table>
                        </div>
                    `;
                    mostrarResultado(html);
                }
            });
        }

        function mostrarResultado(conteudo) {
            $('#resultado').html(conteudo);
        }

        // Gerar PDF
        document.getElementById('downloadPDF').onclick = function() {
            const element = document.getElementById('resultado');
            const options = {
                margin:       10,
                filename:     `Custo_Transporte_${new Date().toLocaleDateString()}.pdf`,
                image:        { type: 'jpeg', quality: 0.98 },
                html2canvas:  { scale: 2 },
                jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
            };
            
            html2pdf().set(options).from(element).save();
        };
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=True)
