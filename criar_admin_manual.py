#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para criar usuário admin manualmente
Execute: python criar_admin_manual.py
"""

import os
import sys

def criar_admin_manual():
    """Criar usuário admin manualmente"""
    try:
        print("🔧 Criando usuário admin manualmente...")
        
        # Verificar se estamos no diretório correto
        if not os.path.exists('app2.py'):
            print("❌ Arquivo app2.py não encontrado!")
            print("💡 Execute este script no diretório do projeto")
            return False
        
        # Importar módulos
        print("📦 Importando módulos...")
        try:
            from app2 import app, db
            from models import Usuario
            print("✅ Módulos importados com sucesso")
        except Exception as e:
            print(f"❌ Erro ao importar módulos: {e}")
            return False
        
        # Criar contexto da aplicação
        print("🔧 Criando contexto da aplicação...")
        with app.app_context():
            try:
                # Criar tabelas
                print("📋 Criando tabelas...")
                db.create_all()
                print("✅ Tabelas criadas")
                
                # Verificar se admin já existe
                admin_existente = Usuario.query.filter_by(nome_usuario='admin').first()
                if admin_existente:
                    print("⚠️ Usuário admin já existe")
                    print(f"📋 Nome: {admin_existente.nome_usuario}")
                    print(f"📋 Tipo: {admin_existente.tipo_usuario}")
                    print(f"📋 Ativo: {admin_existente.ativo}")
                    
                    # Resetar senha
                    admin_existente.set_senha('admin123')
                    db.session.commit()
                    print("✅ Senha do admin resetada para: admin123")
                else:
                    # Criar admin
                    print("👤 Criando usuário admin...")
                    admin = Usuario(
                        nome_usuario='admin',
                        nome_completo='Administrador do Sistema',
                        email='admin@portoex.com',
                        tipo_usuario='admin',
                        pode_calcular_fretes=True,
                        pode_ver_admin=True,
                        pode_editar_base=True,
                        pode_gerenciar_usuarios=True,
                        pode_importar_dados=True,
                        criado_por='sistema'
                    )
                    admin.set_senha('admin123')
                    
                    db.session.add(admin)
                    db.session.commit()
                    print("✅ Usuário admin criado com sucesso!")
                
                # Verificar total de usuários
                total_usuarios = Usuario.query.count()
                print(f"📊 Total de usuários no banco: {total_usuarios}")
                
                # Listar usuários
                usuarios = Usuario.query.all()
                print("\n📋 Usuários cadastrados:")
                for usuario in usuarios:
                    print(f"  - {usuario.nome_usuario} ({usuario.tipo_usuario}) - Ativo: {usuario.ativo}")
                
                return True
                
            except Exception as e:
                print(f"❌ Erro durante criação: {e}")
                db.session.rollback()
                return False
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Criando usuário admin manualmente...")
    print("👤 Usuário: admin")
    print("🔑 Senha: admin123")
    print("-" * 50)
    
    sucesso = criar_admin_manual()
    
    if sucesso:
        print("-" * 50)
        print("🎉 Usuário admin criado com sucesso!")
        print("💡 Acesse: http://192.168.1.246:8000/login")
        print("💡 Use: admin / admin123")
    else:
        print("-" * 50)
        print("❌ Erro ao criar usuário admin!")
        print("💡 Verifique os logs acima")
