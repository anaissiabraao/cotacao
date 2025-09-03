#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de setup completo para ambiente local
Execute: python setup_local.py
"""

import os
import sys

def setup_local():
    """Setup completo para ambiente local"""
    try:
        print("🔧 Setup completo para ambiente local...")
        
        # Verificar se estamos no diretório correto
        if not os.path.exists('app2.py'):
            print("❌ Arquivo app2.py não encontrado!")
            print("💡 Execute este script no diretório do projeto")
            return False
        
        # Configurar variáveis de ambiente
        os.environ['DATABASE_URL'] = 'sqlite:///portoex_local.db'
        os.environ['FLASK_ENV'] = 'development'
        os.environ['SECRET_KEY'] = 'chave_secreta_local_2025'
        print("⚙️ Variáveis de ambiente configuradas")
        
        # Importar módulos
        print("📦 Importando módulos...")
        try:
            from app2 import app, db
            from models import Usuario, BaseUnificada, AgenteTransportadora
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
                
                # Criar usuário admin
                print("👤 Criando usuário admin...")
                admin_existente = Usuario.query.filter_by(nome_usuario='admin').first()
                if admin_existente:
                    print("⚠️ Usuário admin já existe - resetando senha")
                    admin_existente.set_senha('admin123')
                    db.session.commit()
                else:
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
                    print("✅ Usuário admin criado")
                
                # Verificar dados
                total_usuarios = Usuario.query.count()
                total_registros = BaseUnificada.query.count()
                total_agentes = AgenteTransportadora.query.count()
                
                print(f"📊 Estatísticas:")
                print(f"  - Usuários: {total_usuarios}")
                print(f"  - Registros na base: {total_registros}")
                print(f"  - Agentes: {total_agentes}")
                
                return True
                
            except Exception as e:
                print(f"❌ Erro durante setup: {e}")
                db.session.rollback()
                return False
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        return False

def mostrar_instrucoes():
    """Mostrar instruções de uso"""
    print("\n🎉 Setup concluído com sucesso!")
    print("\n📋 Próximos passos:")
    print("1️⃣ Inicie o servidor:")
    print("   python iniciar_servidor_local.py")
    print("\n2️⃣ Acesse o sistema:")
    print("   http://192.168.1.246:8000")
    print("\n3️⃣ Faça login:")
    print("   Usuário: admin")
    print("   Senha: admin123")
    print("\n4️⃣ Acesse o painel admin:")
    print("   http://192.168.1.246:8000/admin")
    print("\n💡 Para parar o servidor: Ctrl+C")

if __name__ == "__main__":
    print("🚀 Setup completo para ambiente local...")
    print("🗄️ Banco: SQLite local")
    print("🌐 IP: 192.168.1.246")
    print("🔌 Porta: 8000")
    print("-" * 50)
    
    sucesso = setup_local()
    
    if sucesso:
        mostrar_instrucoes()
    else:
        print("-" * 50)
        print("❌ Erro durante setup!")
        print("💡 Verifique os logs acima")
