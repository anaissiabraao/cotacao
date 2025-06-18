import pandas as pd
import os

print("Criando novas rotas...")
novas_rotas = pd.DataFrame({
    'Tipo': ['Transferência', 'Transferência'],
    'Fornecedor': ['Braspress', 'Jamef'],
    'Base Origem': ['RIB', 'RIB'],
    'Origem': ['Ribeirão Preto - SP', 'Ribeirão Preto - SP'],
    'Base Destino': ['RIO', 'RIO'],
    'Destino': ['Rio de Janeiro - RJ', 'Rio de Janeiro - RJ'],
    'VALOR MÍNIMO ATÉ 10': [45.0, 48.0],
    20: [55.0, 58.0],
    30: [65.0, 68.0],
    50: [85.0, 88.0],
    70: [105.0, 108.0],
    100: [135.0, 138.0],
    300: [335.0, 338.0],
    500: [535.0, 538.0],
    'Acima 500': [0.94, 0.99],
    'Pedagio (100 Kg)': [17.0, 20.0],
    'EXCEDENTE': [0.54, 0.59],
    'PESO MÁXIMO TRANSPORTADO': [5000, 5000],
    'Gris Min': [5.4, 5.9],
    'Gris Exc': [0.17, 0.20],
    'Prazo': [4, 4]
})

print("Carregando base existente...")
df = pd.read_excel('Base_Unificada.xlsx')
print(f"Base carregada com {len(df)} registros")

print("Combinando dados...")
df_combinado = pd.concat([df, novas_rotas], ignore_index=True)
df_combinado = df_combinado.drop_duplicates(subset=['Fornecedor', 'Origem', 'Destino'])

print("Salvando arquivo atualizado...")
df_combinado.to_excel('Base_Unificada.xlsx', index=False)
print(f"Arquivo salvo com {len(df_combinado)} registros") 