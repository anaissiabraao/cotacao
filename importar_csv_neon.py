#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para importar dados de tarifa do CSV para o banco Neon via API
Execute: python importar_csv_neon.py
"""

import csv
import requests
import os
from decimal import Decimal

# Configuração da API
API_BASE_URL = 'https://cotacao-portoex.com.br'

def limpar_valor(valor):
    """Limpar e converter valor para Decimal"""
    if not valor or valor.strip() == '':
        return None
    try:
        # Remove caracteres especiais e converte para Decimal
        valor_limpo = valor.strip().replace('R$', '').replace(',', '.').replace(' ', '')
        return float(valor_limpo)
    except:
        return None

def importar_csv():
    """Importar dados do CSV para o banco via API"""
    csv_path = r'C:\Users\Usuário\OneDrive\Documentos\GitHub\cotacao\data\Base_Unificada.csv'
    
    if not os.path.exists(csv_path):
        print(f"❌ Arquivo não encontrado: {csv_path}")
        return False
    
    try:
        # Ler CSV
        dados_para_inserir = []
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                # Preparar dados
                dados = {
                    'tipo': row.get('Tipo', ''),
                    'fornecedor': row.get('Fornecedor', ''),
                    'base_origem': row.get('Base Origem', ''),
                    'origem': row.get('Origem', ''),
                    'base_destino': row.get('Base Destino', ''),
                    'destino': row.get('Destino', ''),
                    'valor_minimo_ate_10': limpar_valor(row.get('VALOR MÍNIMO ATÉ 10', '')),
                    'valor_20': limpar_valor(row.get('20', '')),
                    'valor_30': limpar_valor(row.get('30', '')),
                    'valor_50': limpar_valor(row.get('50', '')),
                    'valor_70': limpar_valor(row.get('70', '')),
                    'valor_100': limpar_valor(row.get('100', '')),
                    'valor_150': limpar_valor(row.get('150', '')),
                    'valor_200': limpar_valor(row.get('200', '')),
                    'valor_300': limpar_valor(row.get('300', '')),
                    'valor_500': limpar_valor(row.get('500', '')),
                    'valor_acima_500': limpar_valor(row.get('Acima 500', '')),
                    'pedagio_100_kg': limpar_valor(row.get('Pedagio (100 Kg)', '')),
                    'excedente': limpar_valor(row.get('EXCEDENTE', '')),
                    'seguro': limpar_valor(row.get('Seguro', '')),
                    'peso_maximo_transportado': limpar_valor(row.get('PESO MÁXIMO TRANSPORTADO', '')),
                    'gris_min': limpar_valor(row.get('Gris Min', '')),
                    'gris_exc': limpar_valor(row.get('Gris Exc', '')),
                    'prazo': int(row.get('Prazo', '0')) if row.get('Prazo', '').isdigit() else None,
                    'tda': row.get('TDA', ''),
                    'uf': row.get('UF', ''),
                    'tas': limpar_valor(row.get('TAS', '')),
                    'despacho': limpar_valor(row.get('DESPACHO', ''))
                }
                
                dados_para_inserir.append(dados)
                print(f"📋 Preparado: {dados['fornecedor']} - {dados['origem']} -> {dados['destino']}")
        
        print(f"📊 Total de registros preparados: {len(dados_para_inserir)}")
        
        # Enviar dados via API
        url = f"{API_BASE_URL}/api/admin/base-dados/inserir-automatico"
        headers = {'Content-Type': 'application/json'}
        
        print("🚀 Enviando dados via API...")
        response = requests.post(url, json=dados_para_inserir, headers=headers)
        
        if response.status_code == 200:
            resultado = response.json()
            print("✅ Dados importados com sucesso!")
            print(f"📊 {resultado.get('message', '')}")
            print(f"📈 Registros inseridos: {resultado.get('registros_inseridos', 0)}")
            return True
        else:
            print(f"❌ Erro na API: {response.status_code}")
            print(f"Resposta: {response.text}")
            return False
        
    except Exception as e:
        print(f"❌ Erro durante importação: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando importação de dados de tarifa...")
    print("📁 Arquivo: Base_Unificada.csv")
    print("🌐 API: https://cotacao-portoex.com.br")
    print("🗄️ Banco: Neon PostgreSQL via API")
    print("-" * 50)
    
    sucesso = importar_csv()
    
    if sucesso:
        print("-" * 50)
        print("🎉 Importação concluída com sucesso!")
        print("💡 Use o painel administrativo para verificar os dados")
    else:
        print("-" * 50)
        print("❌ Importação falhou!")
        print("💡 Verifique o arquivo CSV e a conexão com a API")
