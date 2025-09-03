#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para iniciar servidor local
Execute: python iniciar_servidor_local.py
"""

import os
import subprocess
import sys

def iniciar_servidor_local():
    """Iniciar servidor local com SQLite"""
    try:
        print("🚀 Iniciando servidor local...")
        
        # Verificar se estamos no diretório correto
        if not os.path.exists('app2.py'):
            print("❌ Arquivo app2.py não encontrado!")
            print("💡 Execute este script no diretório do projeto")
            return False
        
        # Configurar para usar SQLite local
        os.environ['DATABASE_URL'] = 'sqlite:///portoex_local.db'
        os.environ['FLASK_ENV'] = 'development'
        print("🗄️ Configurado para usar SQLite local")
        print("🌐 Modo: desenvolvimento")
        
        # Verificar se o usuário admin existe
        print("🔍 Verificando usuário admin...")
        try:
            from app2 import app, db
            from models import Usuario
            
            with app.app_context():
                admin = Usuario.query.filter_by(nome_usuario='admin').first()
                if admin:
                    print("✅ Usuário admin encontrado")
                else:
                    print("⚠️ Usuário admin não encontrado")
                    print("💡 Execute primeiro: python criar_admin_local.py")
                    return False
        except Exception as e:
            print(f"❌ Erro ao verificar admin: {e}")
            return False
        
        # Iniciar servidor
        print("🌐 Iniciando servidor na porta 8000...")
        print("💡 Acesse: http://192.168.1.246:8000")
        print("💡 Login: admin / admin123")
        print("💡 Pressione Ctrl+C para parar")
        print("-" * 50)
        
        # Executar o servidor
        subprocess.run([sys.executable, 'app2.py'])
        
        return True
        
    except KeyboardInterrupt:
        print("\n🛑 Servidor parado pelo usuário")
        return True
    except Exception as e:
        print(f"❌ Erro ao iniciar servidor: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando servidor local...")
    print("🌐 IP: 192.168.1.246")
    print("🔌 Porta: 8000")
    print("🗄️ Banco: SQLite local")
    print("-" * 50)
    
    iniciar_servidor_local()
