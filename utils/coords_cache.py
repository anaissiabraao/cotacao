# -*- coding: utf-8 -*-
"""
Cache de coordenadas para geocodificação
"""

# Cache de coordenadas de cidades importantes
COORDS_CACHE = {
    "SAO PAULO-SP": [-23.5505, -46.6333],
    "RIO DE JANEIRO-RJ": [-22.9068, -43.1729],
    "BELO HORIZONTE-MG": [-19.9167, -43.9345],
    "BRASILIA-DF": [-15.7801, -47.9292],
    "SALVADOR-BA": [-12.9714, -38.5014],
    "FORTALEZA-CE": [-3.7319, -38.5267],
    "RECIFE-PE": [-8.0476, -34.8770],
    "CURITIBA-PR": [-25.4284, -49.2733],
    "PORTO ALEGRE-RS": [-30.0346, -51.2177],
    "MANAUS-AM": [-3.1190, -60.0217],
    "BELEM-PA": [-1.4558, -48.5044],
    "GOIANIA-GO": [-16.6869, -49.2648],
    "ARACAJU-SE": [-10.9472, -37.0731],
    "RIBEIRAO PRETO-SP": [-21.1775, -47.8106],
    "CAMPINAS-SP": [-22.9056, -47.0608],
    "SANTOS-SP": [-23.9618, -46.3322],
    "SOROCABA-SP": [-23.5015, -47.4526],
    "JOINVILLE-SC": [-26.3045, -48.8487],
    "FLORIANOPOLIS-SC": [-27.5954, -48.5480],
    "LONDRINA-PR": [-23.3045, -51.1696],
    "MARINGA-PR": [-23.4273, -51.9375],
    "CAMPO GRANDE-MS": [-20.4697, -54.6201],
    "CUIABA-MT": [-15.6014, -56.0979],
    "VITORIA-ES": [-20.3155, -40.3128],
    "NATAL-RN": [-5.7945, -35.2110],
    "JOAO PESSOA-PB": [-7.1195, -34.8450],
    "MACEIO-AL": [-9.6498, -35.7089],
    "TERESINA-PI": [-5.0892, -42.8019],
    "SAO LUIS-MA": [-2.5297, -44.3028],
    "PALMAS-TO": [-10.1689, -48.3317],
    "BOA VISTA-RR": [2.8235, -60.6758],
    "MACAPA-AP": [0.0389, -51.0664],
    "RIO BRANCO-AC": [-9.9754, -67.8249],
    "PORTO VELHO-RO": [-8.7612, -63.9004],
    "CAXIAS DO SUL-RS": [-29.1685, -51.1796],
    "JARAGUA DO SUL-SC": [-26.4851, -49.0668]
}

def get_coords_from_cache(cidade, uf):
    """Buscar coordenadas no cache"""
    key = f"{cidade.upper()}-{uf.upper()}"
    return COORDS_CACHE.get(key)

def add_to_cache(cidade, uf, coords):
    """Adicionar coordenadas ao cache"""
    key = f"{cidade.upper()}-{uf.upper()}"
    COORDS_CACHE[key] = coords 