#!/usr/bin/env python3
"""
Script para migrar dados reais para o Render
"""

import requests
import json
import time

def migrar_dados_reais():
    """Migra dados reais para o Render"""
    
    base_url = "https://cotacao-portoex.com.br"
    
    # Dados reais de exemplo (substitua pelos seus dados reais)
    dados_reais = [
        {
            'tipo': 'FRACIONADO',
            'fornecedor': 'JEM',
            'base_origem': 'SP',
            'origem': 'São Paulo',
            'base_destino': 'RJ',
            'destino': 'Rio de Janeiro',
            'valor_minimo_10': '25.50',
            'peso_20': '1.20',
            'peso_30': '1.15',
            'peso_50': '1.10',
            'peso_70': '1.05',
            'peso_100': '1.00',
            'peso_150': '0.95',
            'peso_200': '0.90',
            'peso_300': '0.85',
            'peso_500': '0.80',
            'acima_500': '0.75',
            'pedagio_100kg': '15.00',
            'excedente': '2.50',
            'seguro': '0.50',
            'peso_maximo': '1000',
            'gris_min': '5.00',
            'gris_exc': '0.30',
            'tas': '0.20',
            'despacho': '10.00'
        },
        {
            'tipo': 'DEDICADO',
            'fornecedor': 'TRANSPORTADORA_A',
            'base_origem': 'SP',
            'origem': 'São Paulo',
            'base_destino': 'MG',
            'destino': 'Belo Horizonte',
            'valor_minimo_10': '150.00',
            'peso_20': '8.50',
            'peso_30': '8.00',
            'peso_50': '7.50',
            'peso_70': '7.00',
            'peso_100': '6.50',
            'peso_150': '6.00',
            'peso_200': '5.50',
            'peso_300': '5.00',
            'peso_500': '4.50',
            'acima_500': '4.00',
            'pedagio_100kg': '25.00',
            'excedente': '3.50',
            'seguro': '0.80',
            'peso_maximo': '2000',
            'gris_min': '8.00',
            'gris_exc': '0.45',
            'tas': '0.35',
            'despacho': '20.00'
        }
    ]
    
    print("🚀 Migrando dados reais para o Render...")
    
    # Primeiro, fazer login
    session = requests.Session()
    
    try:
        # Login
        login_data = {
            'usuario': 'admin',
            'senha': 'admin123'
        }
        
        print("🔐 Fazendo login...")
        response = session.post(f"{base_url}/login", data=login_data)
        
        if response.status_code != 200:
            print(f"❌ Erro no login: {response.status_code}")
            print(f"Resposta: {response.text[:200]}")
            return False
        
        print("✅ Login realizado com sucesso")
        
        # Verificar permissões
        print("🔍 Verificando permissões...")
        response = session.get(f"{base_url}/api/admin/configuracoes/teste-permissoes")
        
        if response.status_code == 200:
            permissoes = response.json()
            print(f"✅ Permissões verificadas: {permissoes.get('message', 'OK')}")
            if permissoes.get('sucesso'):
                usuario = permissoes.get('usuario', {})
                print(f"👤 Usuário: {usuario.get('nome_usuario')}")
                print(f"🔑 Pode editar base: {usuario.get('pode_editar_base')}")
        else:
            print(f"⚠️ Não foi possível verificar permissões: {response.status_code}")
        
        # Inserir dados via API
        for i, dados in enumerate(dados_reais):
            print(f"📝 Inserindo registro {i+1}/{len(dados_reais)}: {dados['fornecedor']}")
            
            response = session.post(
                f"{base_url}/api/admin/base-dados",
                json=dados,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print(f"✅ Registro {dados['fornecedor']} inserido com sucesso")
            else:
                print(f"❌ Erro ao inserir {dados['fornecedor']}: {response.status_code}")
                print(f"Resposta: {response.text[:200]}")
        
        print("\n🎉 Migração concluída!")
        return True
        
    except Exception as e:
        print(f"❌ Erro na migração: {e}")
        return False

if __name__ == "__main__":
    migrar_dados_reais()
