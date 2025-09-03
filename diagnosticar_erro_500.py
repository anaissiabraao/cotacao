#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para diagnosticar erro 500 na API de teste
Execute: python diagnosticar_erro_500.py
"""

import requests
import json

# Configuração da API
API_BASE_URL = 'https://cotacao-portoex.com.br'

def diagnosticar_erro_500():
    """Diagnosticar erro 500 na API de teste"""
    try:
        print("🔍 Diagnosticando erro 500...")
        
        # Teste 1: Health check detalhado
        print("\n1️⃣ Health check detalhado...")
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=10)
            print(f"📄 Status: {response.status_code}")
            print(f"📄 Resposta: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"📊 Database: {data.get('services', {}).get('database', 'N/A')}")
                print(f"📊 PostgreSQL: {data.get('services', {}).get('postgresql_available', 'N/A')}")
                print(f"📊 Records: {data.get('services', {}).get('records', 'N/A')}")
            else:
                print(f"❌ Health check falhou: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro no health check: {e}")
        
        # Teste 2: Teste de conexão com detalhes do erro
        print("\n2️⃣ Teste de conexão com detalhes...")
        try:
            response = requests.post(f"{API_BASE_URL}/api/admin/configuracoes/teste-conexao", timeout=15)
            print(f"📄 Status: {response.status_code}")
            print(f"📄 Headers: {dict(response.headers)}")
            
            if response.status_code == 500:
                print("❌ Erro 500 detectado!")
                try:
                    error_data = response.json()
                    print(f"📄 Erro JSON: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"📄 Resposta texto: {response.text[:500]}")
            elif response.status_code == 200:
                data = response.json()
                print(f"✅ Sucesso: {data.get('sucesso', False)}")
                if not data.get('sucesso'):
                    print(f"📄 Erro: {data.get('error', 'Desconhecido')}")
            else:
                print(f"📄 Resposta: {response.text[:200]}")
                
        except Exception as e:
            print(f"❌ Erro ao testar conexão: {e}")
        
        # Teste 3: Verificar se a rota existe
        print("\n3️⃣ Verificando se a rota existe...")
        try:
            response = requests.get(f"{API_BASE_URL}/api/admin/configuracoes/teste-conexao", timeout=5)
            print(f"📄 GET Status: {response.status_code}")
            if response.status_code == 405:
                print("✅ Rota existe (método GET não permitido)")
            else:
                print(f"📄 Resposta GET: {response.text[:100]}")
        except Exception as e:
            print(f"❌ Erro ao verificar rota: {e}")
        
        # Teste 4: Testar outras rotas admin
        print("\n4️⃣ Testando outras rotas admin...")
        rotas_teste = [
            '/api/admin/base-dados',
            '/api/admin/configuracoes/teste-permissoes',
            '/admin/configuracoes'
        ]
        
        for rota in rotas_teste:
            try:
                response = requests.get(f"{API_BASE_URL}{rota}", timeout=5)
                print(f"📄 {rota}: {response.status_code}")
            except Exception as e:
                print(f"❌ {rota}: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro durante diagnóstico: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Diagnosticando erro 500...")
    print("🌐 API: https://cotacao-portoex.com.br")
    print("-" * 50)
    
    diagnosticar_erro_500()
    
    print("-" * 50)
    print("💡 Verifique os logs do Render para mais detalhes")
