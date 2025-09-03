#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para corrigir todas as tabelas do banco Neon
Execute: python corrigir_todas_tabelas.py
"""

import psycopg2
import os

# Configuração do Neon
DATABASE_URL = 'postgresql://neondb_owner:npg_P8uAds7tHvUF@ep-bold-poetry-adeue94a-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

def corrigir_todas_tabelas():
    """Corrigir todas as tabelas do banco Neon"""
    try:
        print("🔧 Corrigindo todas as tabelas...")
        
        # Conectar ao banco
        print("🔌 Conectando ao Neon...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print("✅ Conectado ao Neon")
        
        # Lista de tabelas para corrigir
        tabelas_para_corrigir = [
            'agentes_transportadora',
            'memorias_calculo_agente',
            'historico_calculos',
            'logs_sistema'
        ]
        
        for tabela in tabelas_para_corrigir:
            print(f"\n🔍 Verificando tabela {tabela}...")
            
            # Verificar se a tabela existe
            cursor.execute(f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name = '{tabela}'
            """)
            tabela_existe = cursor.fetchone()
            
            if tabela_existe:
                print(f"🗑️ Removendo tabela {tabela}...")
                cursor.execute(f"DROP TABLE {tabela} CASCADE")
                print(f"✅ Tabela {tabela} removida")
            
            # Criar tabela com estrutura correta baseada no modelo
            if tabela == 'agentes_transportadora':
                print(f"➕ Criando tabela {tabela}...")
                cursor.execute("""
                    CREATE TABLE agentes_transportadora (
                        id SERIAL PRIMARY KEY,
                        nome VARCHAR(255) NOT NULL,
                        nome_normalizado VARCHAR(255),
                        tipo_agente VARCHAR(50) DEFAULT 'transportadora',
                        ativo BOOLEAN DEFAULT TRUE,
                        logica_calculo VARCHAR(50) DEFAULT 'padrao',
                        gris_percentual DECIMAL(5,2) DEFAULT 0.00,
                        gris_minimo DECIMAL(10,2) DEFAULT 0.00,
                        calcula_seguro BOOLEAN DEFAULT FALSE,
                        calcula_pedagio BOOLEAN DEFAULT FALSE,
                        pedagio_por_bloco BOOLEAN DEFAULT FALSE,
                        parametros_calculo JSONB,
                        descricao_logica TEXT,
                        observacoes TEXT,
                        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Inserir dados de exemplo
                dados_exemplo = [
                    ('PTX', 'PTX', 'transportadora', True, 'dedicado', 2.5, 50.00, True, True, False, '{"fator": 1.2}', 'Lógica dedicada', 'Agente principal'),
                    ('JEM', 'JEM', 'transportadora', True, 'fracionado', 1.8, 30.00, False, False, False, '{"fator": 1.0}', 'Lógica fracionada', 'Agente secundário'),
                    ('DFI', 'DFI', 'transportadora', True, 'dedicado', 3.0, 75.00, True, True, True, '{"fator": 1.5}', 'Lógica dedicada premium', 'Agente premium')
                ]
                
                cursor.executemany("""
                    INSERT INTO agentes_transportadora (
                        nome, nome_normalizado, tipo_agente, ativo, logica_calculo, 
                        gris_percentual, gris_minimo, calcula_seguro, calcula_pedagio, 
                        pedagio_por_bloco, parametros_calculo, descricao_logica, observacoes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, dados_exemplo)
                
            elif tabela == 'memorias_calculo_agente':
                print(f"➕ Criando tabela {tabela}...")
                cursor.execute("""
                    CREATE TABLE memorias_calculo_agente (
                        id SERIAL PRIMARY KEY,
                        agente_id INTEGER REFERENCES agentes_transportadora(id),
                        origem VARCHAR(255),
                        destino VARCHAR(255),
                        tipo_calculo VARCHAR(50),
                        valor_base DECIMAL(10,2),
                        gris DECIMAL(10,2),
                        seguro DECIMAL(10,2),
                        pedagio DECIMAL(10,2),
                        valor_total DECIMAL(10,2),
                        peso_kg DECIMAL(8,2),
                        distancia_km DECIMAL(8,2),
                        prazo_entrega INTEGER,
                        observacoes TEXT,
                        ativo BOOLEAN DEFAULT TRUE,
                        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
            elif tabela == 'historico_calculos':
                print(f"➕ Criando tabela {tabela}...")
                cursor.execute("""
                    CREATE TABLE historico_calculos (
                        id SERIAL PRIMARY KEY,
                        usuario_id INTEGER REFERENCES usuarios(id),
                        origem VARCHAR(255),
                        destino VARCHAR(255),
                        peso_kg DECIMAL(8,2),
                        tipo_calculo VARCHAR(50),
                        resultado JSONB,
                        ip_cliente VARCHAR(45),
                        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
            elif tabela == 'logs_sistema':
                print(f"➕ Criando tabela {tabela}...")
                cursor.execute("""
                    CREATE TABLE logs_sistema (
                        id SERIAL PRIMARY KEY,
                        nivel VARCHAR(20),
                        acao VARCHAR(255),
                        usuario VARCHAR(100),
                        ip VARCHAR(45),
                        detalhes TEXT,
                        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            
            print(f"✅ Tabela {tabela} criada")
        
        # Commit das alterações
        conn.commit()
        print("\n💾 Alterações salvas")
        
        # Verificar estrutura final
        print("\n🔍 Verificando estrutura final...")
        for tabela in ['usuarios', 'base_unificada', 'agentes_transportadora', 'memorias_calculo_agente', 'historico_calculos', 'logs_sistema']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
                total = cursor.fetchone()[0]
                print(f"📊 {tabela}: {total} registros")
            except Exception as e:
                print(f"❌ {tabela}: Erro - {e}")
        
        # Fechar conexão
        cursor.close()
        conn.close()
        print("🔌 Conexão fechada")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Corrigindo todas as tabelas...")
    print("🗄️ Banco: Neon PostgreSQL")
    print("-" * 50)
    
    sucesso = corrigir_todas_tabelas()
    
    if sucesso:
        print("-" * 50)
        print("🎉 Todas as tabelas corrigidas!")
        print("💡 Agora teste novamente a conexão")
    else:
        print("-" * 50)
        print("❌ Erro ao corrigir tabelas!")
        print("💡 Verifique os logs acima")
