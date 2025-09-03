#!/usr/bin/env python3
"""
Script para popular o banco SQLite local com dados de exemplo
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Importar modelos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from models import db, Usuario, BaseUnificada, AgenteTransportadora

def criar_banco_local():
    """Cria e popula o banco SQLite local"""
    try:
        # Configurar banco SQLite
        engine = create_engine('sqlite:///portoex.db')
        
        # Criar tabelas usando Flask-SQLAlchemy
        from flask import Flask
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portoex.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        db.init_app(app)
        
        with app.app_context():
            db.create_all()
        
        print("✅ Banco SQLite criado com sucesso")
        
        # Criar sessão usando Flask-SQLAlchemy
        with app.app_context():
            # Criar usuário admin
            admin = Usuario(
                nome_usuario='admin',
                nome_completo='Administrador',
                email='admin@portoex.com',
                tipo_usuario='admin',
                pode_editar_base=True,
                pode_gerenciar_usuarios=True,
                pode_ver_admin=True,
                pode_importar_dados=True
            )
            admin.set_senha('admin123')
            db.session.add(admin)
        
        # Criar dados de exemplo para BaseUnificada
        dados_exemplo = [
            {
                'tipo': 'Fracionado',
                'fornecedor': 'PTX',
                'base_origem': 'SP',
                'origem': 'São Paulo',
                'base_destino': 'RJ',
                'destino': 'Rio de Janeiro',
                'valor_minimo_10': 'R$ 25,50',
                'peso_20': 'R$ 30,00',
                'peso_30': 'R$ 35,00',
                'peso_50': 'R$ 45,00',
                'peso_70': 'R$ 55,00',
                'peso_100': 'R$ 70,00',
                'peso_150': 'R$ 95,00',
                'peso_200': 'R$ 120,00',
                'peso_300': 'R$ 170,00',
                'peso_500': 'R$ 250,00',
                'acima_500': 'R$ 0,50/kg',
                'pedagio_100kg': 'R$ 15,00',
                'excedente': 'R$ 0,80/kg',
                'seguro': '0,5%',
                'peso_maximo': '1000',
                'gris_min': 'R$ 5,00',
                'gris_exc': '0,25%',
                'tas': 'R$ 10,00',
                'despacho': 'R$ 8,00'
            },
            {
                'tipo': 'Dedicado',
                'fornecedor': 'SOL',
                'base_origem': 'MG',
                'origem': 'Belo Horizonte',
                'base_destino': 'SP',
                'destino': 'Campinas',
                'valor_minimo_10': 'R$ 35,00',
                'peso_20': 'R$ 42,00',
                'peso_30': 'R$ 48,00',
                'peso_50': 'R$ 60,00',
                'peso_70': 'R$ 72,00',
                'peso_100': 'R$ 90,00',
                'peso_150': 'R$ 120,00',
                'peso_200': 'R$ 150,00',
                'peso_300': 'R$ 210,00',
                'peso_500': 'R$ 320,00',
                'acima_500': 'R$ 0,65/kg',
                'pedagio_100kg': 'R$ 20,00',
                'excedente': 'R$ 1,00/kg',
                'seguro': '0,6%',
                'peso_maximo': '1500',
                'gris_min': 'R$ 8,00',
                'gris_exc': '0,3%',
                'tas': 'R$ 15,00',
                'despacho': 'R$ 12,00'
            }
        ]
        
        for dados in dados_exemplo:
            registro = BaseUnificada(**dados)
            db.session.add(registro)
        
        # Criar agentes de transportadora
        agentes = [
            {
                'nome': 'PTX - Porto Express',
                'nome_normalizado': 'PTX - PORTO EXPRESS',
                'tipo_agente': 'transportadora',
                'ativo': True,
                'logica_calculo': 'valor_fixo_faixa',
                'gris_percentual': 0.25,
                'gris_minimo': 5.00,
                'calcula_seguro': True,
                'calcula_pedagio': True,
                'pedagio_por_bloco': 15.00,
                'parametros_calculo': '{"faixas": {"0-10": 25.50, "10-20": 30.00, "20-30": 35.00}}',
                'descricao_logica': 'Cálculo por faixas de peso com GRIS e pedágio',
                'observacoes': 'Transportadora principal'
            },
            {
                'nome': 'SOL - Soluções Logísticas',
                'nome_normalizado': 'SOL - SOLUCOES LOGISTICAS',
                'tipo_agente': 'transportadora',
                'ativo': True,
                'logica_calculo': 'valor_por_kg',
                'gris_percentual': 0.30,
                'gris_minimo': 8.00,
                'calcula_seguro': True,
                'calcula_pedagio': True,
                'pedagio_por_bloco': 20.00,
                'parametros_calculo': '{"valor_por_kg": 0.65, "peso_minimo": 100}',
                'descricao_logica': 'Cálculo por kg com valor mínimo',
                'observacoes': 'Especializada em cargas dedicadas'
            },
            {
                'nome': 'JEM - JEM Transportes',
                'nome_normalizado': 'JEM - JEM TRANSPORTES',
                'tipo_agente': 'agente_coleta',
                'ativo': True,
                'logica_calculo': 'valor_fixo_faixa',
                'gris_percentual': 0.20,
                'gris_minimo': 3.00,
                'calcula_seguro': False,
                'calcula_pedagio': True,
                'pedagio_por_bloco': 12.00,
                'parametros_calculo': '{"faixas": {"0-50": 40.00, "50-100": 60.00}}',
                'descricao_logica': 'Agente de coleta com valores fixos',
                'observacoes': 'Especializado em coleta'
            },
            {
                'nome': 'DFL - DFL Logística',
                'nome_normalizado': 'DFL - DFL LOGISTICA',
                'tipo_agente': 'agente_entrega',
                'ativo': True,
                'logica_calculo': 'valor_por_kg',
                'gris_percentual': 0.15,
                'gris_minimo': 4.00,
                'calcula_seguro': True,
                'calcula_pedagio': False,
                'pedagio_por_bloco': 0.00,
                'parametros_calculo': '{"valor_por_kg": 0.45, "peso_minimo": 50}',
                'descricao_logica': 'Agente de entrega por kg',
                'observacoes': 'Especializado em entrega final'
            }
        ]
        
        for agente_data in agentes:
            agente = AgenteTransportadora(**agente_data)
            db.session.add(agente)
        
        # Commit das alterações
        db.session.commit()
        
        print("✅ Dados de exemplo inseridos com sucesso")
        print("📊 Resumo:")
        print("   👤 Usuário admin criado")
        print("   📦 4 registros na BaseUnificada")
        print("   🚚 4 agentes de transportadora")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar banco local: {e}")
        return False

def verificar_banco_local():
    """Verifica dados no banco local"""
    try:
        engine = create_engine('sqlite:///portoex.db')
        
        with engine.connect() as conn:
            # Verificar BaseUnificada
            result = conn.execute(text("SELECT COUNT(*) FROM base_unificada"))
            count_base = result.fetchone()[0]
            print(f"📊 BaseUnificada: {count_base} registros")
            
            # Verificar Usuario
            result = conn.execute(text("SELECT COUNT(*) FROM usuario"))
            count_user = result.fetchone()[0]
            print(f"📊 Usuario: {count_user} registros")
            
            # Verificar AgenteTransportadora
            result = conn.execute(text("SELECT COUNT(*) FROM agente_transportadora"))
            count_agente = result.fetchone()[0]
            print(f"📊 AgenteTransportadora: {count_agente} registros")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao verificar banco local: {e}")
        return False

def main():
    """Função principal"""
    print("🚀 Criando banco SQLite local com dados de exemplo")
    print("=" * 60)
    
    if criar_banco_local():
        print("\n🔍 Verificando dados criados...")
        verificar_banco_local()
        print("\n✅ Banco local pronto para migração!")
        print("💡 Execute 'python migrar_para_neon.py' para migrar para o Neon")
    else:
        print("\n❌ Falha ao criar banco local")

if __name__ == "__main__":
    main()
