import os
from datetime import timedelta

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # PostgreSQL Database
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    # Configuração local de desenvolvimento com fallback para SQLite
    if not DATABASE_URL:
        # Primeiro tentar PostgreSQL local com suas credenciais
        DATABASE_URL = os.environ.get('POSTGRESQL_URL') or \
                      'postgresql://cotacao:1234@localhost:5432/base_unificada'
        
        # Se PostgreSQL não estiver disponível, usar SQLite como fallback
        try:
            import psycopg2
            # Testar conexão
            import sqlalchemy
            engine = sqlalchemy.create_engine(DATABASE_URL)
            engine.connect()
            print("[CONFIG] ✅ PostgreSQL disponível")
        except Exception as e:
            print(f"[CONFIG] ⚠️ PostgreSQL não disponível ({e}), usando SQLite como fallback")
            DATABASE_URL = 'sqlite:///cotacao.db'
    
    # Para Render, garantir que DATABASE_URL seja usado se disponível
    if os.environ.get('DATABASE_URL'):
        DATABASE_URL = os.environ.get('DATABASE_URL')
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        print(f"[CONFIG] ✅ Usando DATABASE_URL do Render: {DATABASE_URL[:50]}...")
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_timeout': 20,
        'pool_recycle': -1,
        'pool_pre_ping': True
    }
    
    # Cache configuration
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

class DevelopmentConfig(Config):
    DEBUG = True
    
    # Configuração específica de desenvolvimento
    dev_db_url = os.environ.get('DEV_DATABASE_URL')
    if not dev_db_url:
        # Tentar PostgreSQL primeiro, depois SQLite
        try:
            import psycopg2
            import sqlalchemy
            dev_db_url = 'postgresql://cotacao:1234@localhost:5432/base_unificada'
            engine = sqlalchemy.create_engine(dev_db_url)
            engine.connect()
            print("[CONFIG] ✅ PostgreSQL de desenvolvimento disponível")
        except Exception as e:
            print(f"[CONFIG] ⚠️ PostgreSQL dev não disponível ({e}), usando SQLite")
            dev_db_url = 'sqlite:///cotacao_dev.db'
    
    SQLALCHEMY_DATABASE_URI = dev_db_url

class ProductionConfig(Config):
    DEBUG = False
    
    # Para produção no Render, garantir que DATABASE_URL seja usado
    if os.environ.get('DATABASE_URL'):
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
        if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
        print(f"[CONFIG] ✅ Produção usando DATABASE_URL: {SQLALCHEMY_DATABASE_URI[:50]}...")
    
class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

class SQLiteConfig(Config):
    """Configuração específica para SQLite"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///cotacao.db'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_timeout': 20,
        'pool_recycle': -1,
        'pool_pre_ping': True
    }

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'sqlite': SQLiteConfig,
    'default': DevelopmentConfig
} 