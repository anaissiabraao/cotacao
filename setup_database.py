#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para configurar o banco de dados da aplicação de cotação
Detecta automaticamente se PostgreSQL está disponível e configura SQLite como fallback
"""

import os
import sys
import subprocess
import platform

def check_postgresql_available():
    """Verifica se PostgreSQL está disponível e rodando"""
    try:
        import psycopg2
        import sqlalchemy
        
        # Tentar conectar ao PostgreSQL
        database_url = 'postgresql://postgres:postgres@localhost:5432/postgres'
        engine = sqlalchemy.create_engine(database_url)
        
        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"[PostgreSQL] ✅ Conectado com sucesso: {version}")
            return True
            
    except ImportError:
        print("[PostgreSQL] ❌ Biblioteca psycopg2 não instalada")
        return False
    except Exception as e:
        print(f"[PostgreSQL] ❌ Erro de conexão: {e}")
        return False

def install_postgresql_windows():
    """Instruções para instalar PostgreSQL no Windows"""
    print("\n=== INSTALAÇÃO POSTGRESQL WINDOWS ===")
    print("1. Baixe o PostgreSQL de: https://www.postgresql.org/download/windows/")
    print("2. Execute o instalador e siga as instruções")
    print("3. Durante a instalação:")
    print("   - Defina a senha do usuário 'postgres' como 'postgres'")
    print("   - Use a porta padrão 5432")
    print("   - Marque a opção para inicializar o banco de dados")
    print("4. Após a instalação, o PostgreSQL deve iniciar automaticamente")
    print("\nPara instalar via chocolatey (se disponível):")
    print("   choco install postgresql")

def install_postgresql_linux():
    """Instruções para instalar PostgreSQL no Linux"""
    print("\n=== INSTALAÇÃO POSTGRESQL LINUX ===")
    print("Ubuntu/Debian:")
    print("   sudo apt update")
    print("   sudo apt install postgresql postgresql-contrib")
    print("   sudo systemctl start postgresql")
    print("   sudo systemctl enable postgresql")
    print("\nCentOS/RHEL:")
    print("   sudo yum install postgresql postgresql-server")
    print("   sudo postgresql-setup initdb")
    print("   sudo systemctl start postgresql")

def setup_postgresql_database():
    """Configura o banco de dados PostgreSQL"""
    try:
        import psycopg2
        import sqlalchemy
        
        # Conectar como postgres
        admin_url = 'postgresql://postgres:postgres@localhost:5432/postgres'
        engine = sqlalchemy.create_engine(admin_url)
        
        with engine.connect() as conn:
            # Verificar se o banco cotacao_db existe
            result = conn.execute(sqlalchemy.text(
                "SELECT 1 FROM pg_database WHERE datname = 'cotacao_db'"
            ))
            
            if not result.fetchone():
                # Criar o banco de dados
                conn.execute(sqlalchemy.text("COMMIT"))  # Fechar transação atual
                conn.execute(sqlalchemy.text("CREATE DATABASE cotacao_db"))
                print("[PostgreSQL] ✅ Banco de dados 'cotacao_db' criado")
            else:
                print("[PostgreSQL] ✅ Banco de dados 'cotacao_db' já existe")
                
        return True
        
    except Exception as e:
        print(f"[PostgreSQL] ❌ Erro ao configurar banco: {e}")
        return False

def setup_sqlite_fallback():
    """Configura SQLite como fallback"""
    try:
        import sqlite3
        
        # Criar arquivo de banco SQLite
        db_path = os.path.join(os.getcwd(), 'cotacao.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Criar uma tabela de teste
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        print(f"[SQLite] ✅ Banco SQLite configurado em: {db_path}")
        return True
        
    except Exception as e:
        print(f"[SQLite] ❌ Erro ao configurar SQLite: {e}")
        return False

def install_dependencies():
    """Instala dependências necessárias"""
    print("\n=== INSTALANDO DEPENDÊNCIAS ===")
    
    dependencies = [
        'flask',
        'flask-sqlalchemy',
        'flask-caching',
        'flask-migrate',
        'python-dotenv'
    ]
    
    # Tentar instalar psycopg2 para PostgreSQL
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'psycopg2-binary'])
        print("[DEPS] ✅ psycopg2-binary instalado")
        dependencies.extend(['psycopg2-binary'])
    except Exception as e:
        print(f"[DEPS] ⚠️ Erro ao instalar psycopg2: {e}")
        print("[DEPS] Continuando sem PostgreSQL...")
    
    # Instalar outras dependências
    for dep in dependencies:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', dep])
            print(f"[DEPS] ✅ {dep} instalado")
        except Exception as e:
            print(f"[DEPS] ⚠️ Erro ao instalar {dep}: {e}")

def create_env_file():
    """Cria arquivo .env com configurações"""
    env_content = """# Configurações da aplicação de cotação
SECRET_KEY=dev-secret-key-change-in-production
FLASK_ENV=development

# PostgreSQL (se disponível)
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cotacao_db

# SQLite (fallback)
# DATABASE_URL=sqlite:///cotacao.db

# Cache
CACHE_TYPE=SimpleCache

# Configurações de sessão
SESSION_PERMANENT=True
"""
    
    env_path = os.path.join(os.getcwd(), '.env')
    
    if not os.path.exists(env_path):
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
        print(f"[ENV] ✅ Arquivo .env criado em: {env_path}")
    else:
        print("[ENV] ✅ Arquivo .env já existe")

def main():
    """Função principal"""
    print("=== CONFIGURAÇÃO DO BANCO DE DADOS ===")
    print(f"Sistema operacional: {platform.system()}")
    print(f"Python: {sys.version}")
    print(f"Diretório atual: {os.getcwd()}")
    
    # Instalar dependências
    install_dependencies()
    
    # Criar arquivo .env
    create_env_file()
    
    # Verificar PostgreSQL
    postgres_available = check_postgresql_available()
    
    if postgres_available:
        print("\n[PostgreSQL] ✅ PostgreSQL está disponível!")
        if setup_postgresql_database():
            print("[PostgreSQL] ✅ Configuração completa!")
            print("\nVocê pode executar a aplicação com:")
            print("python app.py")
        else:
            print("[PostgreSQL] ⚠️ Erro na configuração, usando SQLite como fallback")
            setup_sqlite_fallback()
    else:
        print("\n[PostgreSQL] ❌ PostgreSQL não disponível")
        
        if platform.system() == "Windows":
            install_postgresql_windows()
        else:
            install_postgresql_linux()
        
        print("\n[FALLBACK] Configurando SQLite como alternativa...")
        if setup_sqlite_fallback():
            print("[SQLite] ✅ SQLite configurado com sucesso!")
            print("\nVocê pode executar a aplicação com:")
            print("python app.py")
            print("\nPara usar PostgreSQL depois, instale-o e execute este script novamente.")
    
    print("\n=== CONFIGURAÇÃO CONCLUÍDA ===")

if __name__ == '__main__':
    main() 