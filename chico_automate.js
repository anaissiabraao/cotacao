import webbrowser
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse

# Tabela de custos conforme fornecido
cost_table = {
    "0-20": {"VAN": 250, "3/4": 350, "TOCO": 450, "TRUCK": 550, "CARRETA": 1000},
    "20-50": {"VAN": 350, "3/4": 450, "TOCO": 550, "TRUCK": 700, "CARRETA": 1500},
    "50-100": {"VAN": 600, "3/4": 900, "TOCO": 1200, "TRUCK": 1500, "CARRETA": 2100},
    "100-150": {"VAN": 800, "3/4": 1100, "TOCO": 1500, "TRUCK": 1800, "CARRETA": 2600},
    "150-200": {"VAN": 1000, "3/4": 1500, "TOCO": 1800, "TRUCK": 2100, "CARRETA": 3000},
    "200-250": {"VAN": 1300, "3/4": 1800, "TOCO": 2100, "TRUCK": 2500, "CARRETA": 3300},
    "250-300": {"VAN": 1500, "3/4": 2100, "TOCO": 2500, "TRUCK": 2800, "CARRETA": 3800},
    "300-400": {"VAN": 1800, "3/4": 2500, "TOCO": 2800, "TRUCK": 3300, "CARRETA": 4300},
    "400-600": {"VAN": 2100, "3/4": 2900, "TOCO": 3500, "TRUCK": 3800, "CARRETA": 4800},
}

def get_costs_for_distance(distance_km):
    if distance_km <= 20:
        range_key = "0-20"
    elif distance_km <= 50:
        range_key = "20-50"
    elif distance_km <= 100:
        range_key = "50-100"
    elif distance_km <= 150:
        range_key = "100-150"
    elif distance_km <= 200:
        range_key = "150-200"
    elif distance_km <= 250:
        range_key = "200-250"
    elif distance_km <= 300:
        range_key = "250-300"
    elif distance_km <= 400:
        range_key = "300-400"
    elif distance_km <= 600:
        range_key = "400-600"
    else:
        return None
    
    return cost_table[range_key]

# HTML para interface com mapa do Google embutido
html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Calculadora de Custos de Transporte</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        #map {
            height: 400px;
            width: 100%;
            margin-bottom: 20px;
            border: 1px solid #ddd;
        }
        #results {
            display: none;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
    </style>
</head>
<body>
    <h1>Calculadora de Custos de Transporte</h1>
    
    <div>
        <div>
            <label for="origin">Origem:</label>
            <input type="text" id="origin" value="Itajaí, SC, Brazil">
            
            <label for="destination">Destino:</label>
            <input type="text" id="destination" placeholder="Digite o destino">
            
            <button onclick="calculateRoute()">Calcular Rota</button>
        </div>
        
        <div id="map"></div>
        
        <div>
            <label for="manual-distance">Ou digite a distância manualmente (km):</label>
            <input type="number" id="manual-distance" min="0" step="0.1">
            <button onclick="calculateManual()">Calcular</button>
        </div>
        
        <div id="results">
            <h2>Resultados</h2>
            <p id="distance-text"></p>
            <h3>Custos de Transporte</h3>
            <table>
                <thead>
                    <tr>
                        <th>Tipo de Veículo</th>
                        <th>Custo (R$)</th>
                    </tr>
                </thead>
                <tbody id="costs-table">
                </tbody>
            </table>
        </div>
    </div>

    <script>
        let map;
        let directionsService;
        let directionsRenderer;

        function initMap() {
            map = new google.maps.Map(document.getElementById("map"), {
                center: { lat: -27.0974, lng: -48.9177 }, // Coordenadas de Itajaí
                zoom: 8
            });
            
            directionsService = new google.maps.DirectionsService();
            directionsRenderer = new google.maps.DirectionsRenderer();
            directionsRenderer.setMap(map);
            
            const originInput = document.getElementById("origin");
            const destinationInput = document.getElementById("destination");
            const originAutocomplete = new google.maps.places.Autocomplete(originInput);
            const destinationAutocomplete = new google.maps.places.Autocomplete(destinationInput);
        }

        function calculateRoute() {
            const origin = document.getElementById("origin").value;
            const destination = document.getElementById("destination").value;
            
            if (!origin || !destination) {
                alert("Por favor, digite origem e destino");
                return;
            }
            
            const request = {
                origin: origin,
                destination: destination,
                travelMode: google.maps.TravelMode.DRIVING
            };
            
            directionsService.route(request, function(result, status) {
                if (status == google.maps.DirectionsStatus.OK) {
                    directionsRenderer.setDirections(result);
                    
                    let distance = 0;
                    const route = result.routes[0];
                    
                    for (let i = 0; i < route.legs.length; i++) {
                        distance += route.legs[i].distance.value;
                    }
                    
                    distance = distance / 1000; // Converter metros para quilômetros
                    
                    document.getElementById("distance-text").textContent = `Distância: ${distance.toFixed(2)} km`;
                    calculateCosts(distance);
                    document.getElementById("results").style.display = "block";
                } else {
                    alert("Não foi possível calcular a rota: " + status);
                }
            });
        }

        function calculateManual() {
            const distanceInput = document.getElementById("manual-distance");
            const distance = parseFloat(distanceInput.value);
            
            if (isNaN(distance) || distance < 0) {
                alert("Por favor, digite uma distância válida");
                return;
            }
            
            document.getElementById("distance-text").textContent = `Distância: ${distance.toFixed(2)} km`;
            calculateCosts(distance);
            document.getElementById("results").style.display = "block";
        }

        function calculateCosts(distance) {
            fetch(`/calculate?distance=${distance}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        return;
                    }
                    
                    const costsTable = document.getElementById("costs-table");
                    costsTable.innerHTML = "";
                    
                    for (const [vehicleType, cost] of Object.entries(data.costs)) {
                        const row = costsTable.insertRow();
                        const cell1 = row.insertCell(0);
                        const cell2 = row.insertCell(1);
                        
                        cell1.textContent = vehicleType;
                        cell2.textContent = `R$ ${cost.toFixed(2)}`;
                    }
                })
                .catch(error => {
                    console.error('Erro:', error);
                    alert("Ocorreu um erro ao calcular os custos");
                });
        }
    </script>
    <script src="https://maps.googleapis.com/maps/api/js?libraries=places&callback=initMap" async defer></script>
</body>
</html>
"""

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        elif self.path.startswith("/calculate"):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            distance_str = params.get("distance", ["0"])[0]
            
            try:
                distance = float(distance_str)
                costs = get_costs_for_distance(distance)
                
                if costs is None:
                    response = {"error": "Distância excede as faixas fornecidas (máx 600 km)"}
                else:
                    response = {"costs": costs}
                    
                self.wfile.write(json.dumps(response).encode("utf-8"))
            except ValueError:
                self.wfile.write(json.dumps({"error": "Distância inválida"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    server_address = ("", 8000)
    httpd = HTTPServer(server_address, RequestHandler)
    print("Iniciando servidor em http://localhost:8000")
    print("Pressione Ctrl+C para sair")
    try:
        webbrowser.open("http://localhost:8000")
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Servidor parado")

if __name__ == "__main__":
    run_server()
