#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para corrigir estrutura do banco Neon
Execute: python corrigir_banco_neon.py
"""

import psycopg2
import os

# Configuração do Neon
DATABASE_URL = 'postgresql://neondb_owner:npg_P8uAds7tHvUF@ep-bold-poetry-adeue94a-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

def corrigir_banco_neon():
    """Corrigir estrutura do banco Neon"""
    try:
        print("🔧 Corrigindo estrutura do banco Neon...")
        
        # Conectar ao banco
        print("🔌 Conectando ao Neon...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print("✅ Conectado ao Neon")
        
        # Verificar estrutura atual
        print("🔍 Verificando estrutura atual...")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'usuarios' 
            ORDER BY ordinal_position
        """)
        colunas_atuais = [row[0] for row in cursor.fetchall()]
        print(f"📋 Colunas atuais: {colunas_atuais}")
        
        # Verificar se falta a coluna tipo_usuario
        if 'tipo_usuario' not in colunas_atuais:
            print("➕ Adicionando coluna tipo_usuario...")
            cursor.execute("""
                ALTER TABLE usuarios 
                ADD COLUMN tipo_usuario VARCHAR(50) DEFAULT 'usuario'
            """)
            print("✅ Coluna tipo_usuario adicionada")
        
        # Verificar outras colunas necessárias
        colunas_necessarias = [
            'pode_calcular_fretes', 'pode_ver_admin', 'pode_editar_base',
            'pode_gerenciar_usuarios', 'pode_importar_dados', 'ultimo_login',
            'ip_ultimo_login', 'tentativas_login', 'bloqueado_ate',
            'criado_em', 'criado_por', 'atualizado_em'
        ]
        
        for coluna in colunas_necessarias:
            if coluna not in colunas_atuais:
                print(f"➕ Adicionando coluna {coluna}...")
                if coluna in ['pode_calcular_fretes', 'pode_ver_admin', 'pode_editar_base', 'pode_gerenciar_usuarios', 'pode_importar_dados']:
                    cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {coluna} BOOLEAN DEFAULT FALSE")
                elif coluna in ['tentativas_login']:
                    cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {coluna} INTEGER DEFAULT 0")
                elif coluna in ['ultimo_login', 'criado_em', 'atualizado_em', 'bloqueado_ate']:
                    cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {coluna} TIMESTAMP")
                elif coluna in ['ip_ultimo_login', 'criado_por']:
                    cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {coluna} VARCHAR(255)")
                print(f"✅ Coluna {coluna} adicionada")
        
        # Verificar tabela base_unificada
        print("🔍 Verificando tabela base_unificada...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'base_unificada' 
            ORDER BY ordinal_position
        """)
        colunas_base = [row[0] for row in cursor.fetchall()]
        print(f"📋 Colunas base_unificada: {colunas_base}")
        
        # Verificar se a tabela base_unificada existe e tem estrutura correta
        if not colunas_base:
            print("❌ Tabela base_unificada não existe ou está vazia")
            print("💡 Execute o script de migração completo primeiro")
        else:
            print("✅ Tabela base_unificada existe")
        
        # Commit das alterações
        conn.commit()
        print("💾 Alterações salvas")
        
        # Verificar estrutura final
        print("🔍 Verificando estrutura final...")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'usuarios' 
            ORDER BY ordinal_position
        """)
        colunas_finais = [row[0] for row in cursor.fetchall()]
        print(f"📋 Colunas finais: {colunas_finais}")
        
        # Fechar conexão
        cursor.close()
        conn.close()
        print("🔌 Conexão fechada")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Corrigindo estrutura do banco Neon...")
    print("🗄️ Banco: Neon PostgreSQL")
    print("-" * 50)
    
    sucesso = corrigir_banco_neon()
    
    if sucesso:
        print("-" * 50)
        print("🎉 Estrutura corrigida!")
        print("💡 Agora teste novamente a conexão")
    else:
        print("-" * 50)
        print("❌ Erro ao corrigir estrutura!")
        print("💡 Verifique os logs acima")
