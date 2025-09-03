#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para recriar usuário admin com senha correta
Execute: python recriar_admin_senha.py
"""

import psycopg2
import os
from werkzeug.security import generate_password_hash

# Configuração do Neon
DATABASE_URL = 'postgresql://neondb_owner:npg_P8uAds7tHvUF@ep-bold-poetry-adeue94a-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

def recriar_admin_senha():
    """Recriar usuário admin com senha correta"""
    try:
        print("🔧 Recriando usuário admin com senha correta...")
        
        # Conectar ao banco
        print("🔌 Conectando ao Neon...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print("✅ Conectado ao Neon")
        
        # Gerar hash da senha
        senha = 'admin123'
        senha_hash = generate_password_hash(senha)
        print(f"🔐 Senha: {senha}")
        print(f"🔐 Hash: {senha_hash[:50]}...")
        
        # Verificar se o usuário admin existe
        print("🔍 Verificando usuário admin...")
        cursor.execute("SELECT id, nome_usuario, senha_hash FROM usuarios WHERE nome_usuario = 'admin'")
        admin_existe = cursor.fetchone()
        
        if admin_existe:
            print(f"✅ Usuário admin existe (ID: {admin_existe[0]})")
            print(f"📄 Hash atual: {admin_existe[2][:50]}...")
            
            # Atualizar senha
            print("🔄 Atualizando senha do admin...")
            cursor.execute("""
                UPDATE usuarios 
                SET senha_hash = %s,
                    tipo_usuario = 'admin',
                    pode_calcular_fretes = TRUE,
                    pode_ver_admin = TRUE,
                    pode_editar_base = TRUE,
                    pode_gerenciar_usuarios = TRUE,
                    pode_importar_dados = TRUE,
                    ativo = TRUE,
                    tentativas_login = 0,
                    bloqueado_ate = NULL,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE nome_usuario = 'admin'
            """, (senha_hash,))
            print("✅ Senha atualizada")
            
        else:
            print("➕ Criando usuário admin...")
            cursor.execute("""
                INSERT INTO usuarios (
                    nome_usuario, nome_completo, email, senha_hash, tipo_usuario,
                    pode_calcular_fretes, pode_ver_admin, pode_editar_base,
                    pode_gerenciar_usuarios, pode_importar_dados, ativo, criado_por
                ) VALUES (
                    'admin', 'Administrador do Sistema', 'admin@portoex.com', %s, 'admin',
                    TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, 'sistema'
                )
            """, (senha_hash,))
            print("✅ Usuário admin criado")
        
        # Verificar resultado
        print("🔍 Verificando resultado...")
        cursor.execute("""
            SELECT id, nome_usuario, tipo_usuario, ativo, senha_hash 
            FROM usuarios 
            WHERE nome_usuario = 'admin'
        """)
        admin = cursor.fetchone()
        
        if admin:
            print(f"✅ Admin verificado:")
            print(f"   📋 ID: {admin[0]}")
            print(f"   📋 Nome: {admin[1]}")
            print(f"   📋 Tipo: {admin[2]}")
            print(f"   📋 Ativo: {admin[3]}")
            print(f"   📋 Hash: {admin[4][:50]}...")
            
            # Testar senha
            print("🔐 Testando senha...")
            from werkzeug.security import check_password_hash
            senha_valida = check_password_hash(admin[4], 'admin123')
            print(f"   ✅ Senha válida: {senha_valida}")
            
        else:
            print("❌ Usuário admin não encontrado após criação")
        
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
    print("🚀 Recriando usuário admin com senha correta...")
    print("🗄️ Banco: Neon PostgreSQL")
    print("👤 Credenciais: admin / admin123")
    print("-" * 50)
    
    sucesso = recriar_admin_senha()
    
    if sucesso:
        print("-" * 50)
        print("🎉 Usuário admin recriado!")
        print("💡 Agora teste o login: admin / admin123")
    else:
        print("-" * 50)
        print("❌ Erro ao recriar admin!")
        print("💡 Verifique os logs acima")
