import requests

url = "http://127.0.0.1:5000/calcular"
data = {
    "uf_origem": "SP",
    "municipio_origem": "São Paulo",
    "uf_destino": "RJ",
    "municipio_destino": "Rio de Janeiro",
    "peso": 1000,
    "cubagem": 10,
    "distancia": 430
}

response = requests.post(url, json=data)
print(response.status_code)
print(response.text)
