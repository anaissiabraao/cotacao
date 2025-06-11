# PortoEx API Documentation

## Visão Geral
API RESTful para cálculo de fretes e gestão logística.

## Autenticação

Todas as rotas (exceto `/login`) requerem autenticação via sessão.

### POST /login
Realizar login no sistema.

**Request:**
```json
{
  "usuario": "comercial.ptx",
  "senha": "ptx@123"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Login realizado com sucesso!",
  "usuario": "Usuário Comercial",
  "tipo": "comercial",
  "redirect": "/"
}
```

## Endpoints de Dados

### GET /estados
Lista todos os estados brasileiros.

**Response:**
```json
[
  {"id": "SP", "text": "São Paulo"},
  {"id": "RJ", "text": "Rio de Janeiro"}
]
```

### GET /municipios/{uf}
Lista municípios de um estado.

**Response:**
```json
[
  {"id": "São Paulo", "text": "São Paulo"},
  {"id": "Campinas", "text": "Campinas"}
]
```

## Cálculo de Fretes

### POST /calcular
Calcular frete dedicado.

**Request:**
```json
{
  "uf_origem": "SP",
  "municipio_origem": "São Paulo",
  "uf_destino": "RJ", 
  "municipio_destino": "Rio de Janeiro",
  "peso": 1000,
  "cubagem": 2.5
}
```

**Response:**
```json
{
  "distancia": 429.2,
  "duracao": 380.5,
  "custos": {
    "FIORINO": 900.0,
    "VAN": 1200.0,
    "CARRETA": 3000.0
  },
  "rota_pontos": [[lat, lng], ...],
  "analise": {
    "id_historico": "#Ded001",
    "tempo_estimado": "6h 20min",
    "consumo_combustivel": 51.5,
    "emissao_co2": 118.4,
    "pedagio_estimado": 21.46
  }
}
```

### POST /calcular_frete_fracionado
Calcular frete fracionado com dados reais.

**Request:**
```json
{
  "estado_origem": "SP",
  "municipio_origem": "São Paulo",
  "estado_destino": "SE",
  "municipio_destino": "Aracaju", 
  "peso": 50,
  "cubagem": 0.085,
  "valor_nf": 5000
}
```

**Response:**
```json
{
  "id_historico": "Fra001",
  "data_hora": "15/01/2025 14:30:00",
  "cotacoes_ranking": [
    {
      "modalidade": "Concept",
      "agente": "CWB",
      "total": 245.67,
      "prazo": 3,
      "valor_base": 200.00,
      "pedagio": 15.67,
      "gris": 30.00
    }
  ],
  "total_opcoes": 5,
  "fornecedores_count": 3,
  "html": "<div>...</div>"
}
```

### POST /calcular_aereo
Calcular frete aéreo.

**Request:**
```json
{
  "uf_origem": "SP",
  "municipio_origem": "São Paulo",
  "uf_destino": "AM",
  "municipio_destino": "Manaus",
  "peso": 5,
  "cubagem": 0.02
}
```

## Exportação

### POST /gerar-pdf
Exportar relatório em PDF.

**Request:**
```json
{
  "analise": {
    "id_historico": "#Fra001",
    "tipo": "Fracionado",
    "custos": {...}
  }
}
```

### POST /exportar-excel
Exportar dados para Excel.

## Administração

### GET /admin
Dashboard administrativo.

### GET /admin/logs
Visualizar logs do sistema.

**Query Parameters:**
- `usuario`: Filtrar por usuário
- `acao`: Filtrar por ação
- `data`: Filtrar por data
- `page`: Página (paginação)

### POST /admin/limpar-logs
Limpar logs do sistema.

### GET /admin/exportar-logs
Exportar logs para Excel.

## Códigos de Status

- `200`: Sucesso
- `400`: Dados inválidos
- `401`: Não autenticado
- `403`: Sem permissão
- `404`: Não encontrado
- `500`: Erro interno

## Tratamento de Erros

```json
{
  "error": "Mensagem de erro",
  "code": "ERROR_CODE",
  "details": "Detalhes adicionais"
}
```

## Rate Limiting

- Máximo 100 requests por minuto por IP
- Máximo 1000 requests por hora por usuário

## Logs

Todas as operações são registradas com:
- Timestamp
- Usuário
- Ação realizada
- IP de origem
- Detalhes da operação 