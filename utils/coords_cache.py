"""
Cache de coordenadas para cidades brasileiras
"""

COORDS_CACHE = {
    'ITAJAI-SC': [-26.9087, -48.6626],
    'SAO JOSE DO RIO PRETO-SP': [-20.8113, -49.3758],
    'SAO PAULO-SP': [-23.5505, -46.6333],
    'RIO DE JANEIRO-RJ': [-22.9068, -43.1729],
    'BELO HORIZONTE-MG': [-19.9167, -43.9345],
    'CURITIBA-PR': [-25.4284, -49.2733],
    'PORTO ALEGRE-RS': [-30.0346, -51.2177],
    'SALVADOR-BA': [-12.9714, -38.5014],
    'RECIFE-PE': [-8.0476, -34.8770],
    'FORTALEZA-CE': [-3.7319, -38.5267],
    'MANAUS-AM': [-3.1190, -60.0217],
    'BRASILIA-DF': [-15.7801, -47.9292],
    'GOIANIA-GO': [-16.6869, -49.2648],
    'VITORIA-ES': [-20.2976, -40.2958],
    'FLORIANOPOLIS-SC': [-27.5945, -48.5477],
    'BELEM-PA': [-1.4558, -48.4902],
    'NATAL-RN': [-5.7945, -35.2120],
    'ARACAJU-SE': [-10.9472, -37.0731],
    'RIBEIRAO PRETO-SP': [-21.1704, -47.8103],
    'CAMPINAS-SP': [-22.9099, -47.0626]
}

def get_coords(cidade, uf):
    """
    Retorna as coordenadas de uma cidade
    """
    chave = f"{cidade}-{uf}"
    return COORDS_CACHE.get(chave, [-15.7801, -47.9292])  # Brasília como fallback 