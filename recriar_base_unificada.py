#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para recriar tabela base_unificada com estrutura correta
Execute: python recriar_base_unificada.py
"""

import psycopg2
import os

# Configuração do Neon
DATABASE_URL = 'postgresql://neondb_owner:npg_P8uAds7tHvUF@ep-bold-poetry-adeue94a-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

def recriar_base_unificada():
    """Recriar tabela base_unificada com estrutura correta"""
    try:
        print("🔧 Recriando tabela base_unificada...")
        
        # Conectar ao banco
        print("🔌 Conectando ao Neon...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print("✅ Conectado ao Neon")
        
        # Verificar se a tabela existe
        print("🔍 Verificando tabela atual...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'base_unificada'
        """)
        tabela_existe = cursor.fetchone()
        
        if tabela_existe:
            print("🗑️ Removendo tabela existente...")
            cursor.execute("DROP TABLE base_unificada CASCADE")
            print("✅ Tabela removida")
        
        # Criar nova tabela com estrutura correta
        print("➕ Criando nova tabela...")
        cursor.execute("""
            CREATE TABLE base_unificada (
                "Tipo" TEXT,
                "Fornecedor" TEXT,
                "Base Origem" TEXT,
                "Origem" TEXT,
                "Base Destino" TEXT,
                "Destino" TEXT,
                "VALOR MÍNIMO ATÉ 10" TEXT,
                "20" TEXT,
                "30" TEXT,
                "50" TEXT,
                "70" TEXT,
                "100" TEXT,
                "150" TEXT,
                "200" TEXT,
                "300" TEXT,
                "500" TEXT,
                "Acima 500" TEXT,
                "Pedagio (100 Kg)" TEXT,
                "EXCEDENTE" TEXT,
                "Seguro" TEXT,
                "PESO MÁXIMO TRANSPORTADO" TEXT,
                "Gris Min" TEXT,
                "Gris Exc" TEXT,
                "Prazo" TEXT,
                "TDA" TEXT,
                "UF" TEXT,
                "TAS" TEXT,
                "DESPACHO" TEXT,
                id SERIAL PRIMARY KEY
            )
        """)
        print("✅ Tabela criada")
        
        # Inserir dados de exemplo
        print("📝 Inserindo dados de exemplo...")
        dados_exemplo = [
            ('Dedicado', 'PTX', 'São Paulo', 'São Paulo', 'Rio de Janeiro', 'Rio de Janeiro', '150.00', '200.00', '250.00', '300.00', '350.00', '400.00', '500.00', '600.00', '800.00', '1200.00', '1500.00', '50.00', '10.00', '5.00', '1000', '2.00', '1.50', '2', 'N', 'SP', '5.00', '10.00'),
            ('Fracionado', 'JEM', 'São Paulo', 'São Paulo', 'Belo Horizonte', 'Belo Horizonte', '100.00', '150.00', '200.00', '250.00', '300.00', '350.00', '450.00', '550.00', '750.00', '1100.00', '1400.00', '30.00', '8.00', '3.00', '500', '1.50', '1.00', '3', 'N', 'MG', '3.00', '8.00'),
            ('Dedicado', 'DFI', 'São Paulo', 'São Paulo', 'Brasília', 'Brasília', '200.00', '250.00', '300.00', '400.00', '500.00', '600.00', '800.00', '1000.00', '1200.00', '1800.00', '2200.00', '80.00', '15.00', '8.00', '1500', '3.00', '2.00', '4', 'N', 'DF', '8.00', '15.00')
        ]
        
        cursor.executemany("""
            INSERT INTO base_unificada (
                "Tipo", "Fornecedor", "Base Origem", "Origem", "Base Destino", "Destino",
                "VALOR MÍNIMO ATÉ 10", "20", "30", "50", "70", "100", "150", "200", "300", "500", "Acima 500",
                "Pedagio (100 Kg)", "EXCEDENTE", "Seguro", "PESO MÁXIMO TRANSPORTADO", "Gris Min", "Gris Exc", "Prazo", "TDA", "UF", "TAS", "DESPACHO"
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, dados_exemplo)
        print("✅ Dados de exemplo inseridos")
        
        # Verificar estrutura final
        print("🔍 Verificando estrutura final...")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'base_unificada' 
            ORDER BY ordinal_position
        """)
        colunas_finais = [row[0] for row in cursor.fetchall()]
        print(f"📋 Colunas finais: {colunas_finais}")
        
        # Verificar dados
        cursor.execute("SELECT COUNT(*) FROM base_unificada")
        total_registros = cursor.fetchone()[0]
        print(f"📊 Total de registros: {total_registros}")
        
        # Commit das alterações
        conn.commit()
        print("💾 Alterações salvas")
        
        # Fechar conexão
        cursor.close()
        conn.close()
        print("🔌 Conexão fechada")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Recriando tabela base_unificada...")
    print("🗄️ Banco: Neon PostgreSQL")
    print("-" * 50)
    
    sucesso = recriar_base_unificada()
    
    if sucesso:
        print("-" * 50)
        print("🎉 Tabela recriada com sucesso!")
        print("💡 Agora teste novamente a conexão")
    else:
        print("-" * 50)
        print("❌ Erro ao recriar tabela!")
        print("💡 Verifique os logs acima")
