#!/usr/bin/env python3
"""
Script para importar dados de Excel/CSV para o Render
"""

import pandas as pd
import requests
import json
import sys

def importar_dados_excel(arquivo_excel, sheet_name=0):
    """Importa dados de um arquivo Excel para o Render"""
    
    base_url = "https://cotacao-portoex.com.br"
    
    try:
        # Ler arquivo Excel
        print(f"📖 Lendo arquivo: {arquivo_excel}")
        df = pd.read_excel(arquivo_excel, sheet_name=sheet_name)
        
        print(f"✅ Arquivo lido: {len(df)} registros encontrados")
        print(f"📋 Colunas: {list(df.columns)}")
        
        # Converter para formato da API
        dados_api = []
        for index, row in df.iterrows():
            dados = {
                'tipo': row.get('tipo', 'FRACIONADO'),
                'fornecedor': row.get('fornecedor', ''),
                'base_origem': row.get('base_origem', ''),
                'origem': row.get('origem', ''),
                'base_destino': row.get('base_destino', ''),
                'destino': row.get('destino', ''),
                'valor_minimo_10': str(row.get('valor_minimo_10', '0')),
                'peso_20': str(row.get('peso_20', '0')),
                'peso_30': str(row.get('peso_30', '0')),
                'peso_50': str(row.get('peso_50', '0')),
                'peso_70': str(row.get('peso_70', '0')),
                'peso_100': str(row.get('peso_100', '0')),
                'peso_150': str(row.get('peso_150', '0')),
                'peso_200': str(row.get('peso_200', '0')),
                'peso_300': str(row.get('peso_300', '0')),
                'peso_500': str(row.get('peso_500', '0')),
                'acima_500': str(row.get('acima_500', '0')),
                'pedagio_100kg': str(row.get('pedagio_100kg', '0')),
                'excedente': str(row.get('excedente', '0')),
                'seguro': str(row.get('seguro', '0')),
                'peso_maximo': str(row.get('peso_maximo', '1000')),
                'gris_min': str(row.get('gris_min', '0')),
                'gris_exc': str(row.get('gris_exc', '0')),
                'tas': str(row.get('tas', '0')),
                'despacho': str(row.get('despacho', '0'))
            }
            dados_api.append(dados)
        
        # Fazer login
        session = requests.Session()
        login_data = {
            'username': 'admin',
            'password': 'admin123'
        }
        
        response = session.post(f"{base_url}/login", data=login_data)
        if response.status_code != 200:
            print("❌ Erro no login")
            return False
        
        print("✅ Login realizado com sucesso")
        
        # Inserir dados
        sucessos = 0
        erros = 0
        
        for i, dados in enumerate(dados_api):
            print(f"📝 Inserindo registro {i+1}/{len(dados_api)}: {dados['fornecedor']}")
            
            response = session.post(
                f"{base_url}/api/admin/base-dados",
                json=dados,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print(f"✅ Registro {dados['fornecedor']} inserido com sucesso")
                sucessos += 1
            else:
                print(f"❌ Erro ao inserir {dados['fornecedor']}: {response.status_code}")
                erros += 1
        
        print(f"\n🎉 Importação concluída!")
        print(f"✅ Sucessos: {sucessos}")
        print(f"❌ Erros: {erros}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na importação: {e}")
        return False

def importar_dados_csv(arquivo_csv):
    """Importa dados de um arquivo CSV para o Render"""
    
    try:
        # Ler arquivo CSV
        print(f"📖 Lendo arquivo: {arquivo_csv}")
        df = pd.read_csv(arquivo_csv)
        
        print(f"✅ Arquivo lido: {len(df)} registros encontrados")
        print(f"📋 Colunas: {list(df.columns)}")
        
        # Usar a mesma função de conversão
        return importar_dados_excel(arquivo_csv)
        
    except Exception as e:
        print(f"❌ Erro na leitura do CSV: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python importar_dados.py <arquivo.xlsx ou arquivo.csv>")
        print("Exemplo: python importar_dados.py dados_frete.xlsx")
        sys.exit(1)
    
    arquivo = sys.argv[1]
    
    if arquivo.endswith('.xlsx') or arquivo.endswith('.xls'):
        importar_dados_excel(arquivo)
    elif arquivo.endswith('.csv'):
        importar_dados_csv(arquivo)
    else:
        print("❌ Formato de arquivo não suportado. Use .xlsx, .xls ou .csv")
