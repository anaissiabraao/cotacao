#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Arquivo principal da aplicação de cotação de fretes
"""

import os
from flask import Flask, request
from flask_caching import Cache
from dotenv import load_dotenv
import gzip
import functools
from flask_migrate import Migrate
from config import config
from models import db, HistoricoCalculo, LogSistema

# Carregar variáveis de ambiente
load_dotenv()

# Configuração do cache baseada no ambiente
if os.environ.get('FLASK_ENV') == 'production':
    cache_config = {
        'CACHE_TYPE': 'redis',
        'CACHE_REDIS_URL': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        'CACHE_DEFAULT_TIMEOUT': 300,  # 5 minutos
        'CACHE_KEY_PREFIX': 'portoex_'
    }
else:
    cache_config = {
        'CACHE_TYPE': 'SimpleCache',
        'CACHE_DEFAULT_TIMEOUT': 300,
        'CACHE_THRESHOLD': 1000
    }

try:
    # Importar a aplicação principal
    from improved_chico_automate_fpdf import app as main_app
    
    # Configurar cache
    cache = Cache(main_app, config=cache_config)
    
    # Configurar variáveis de ambiente importantes
    if not main_app.secret_key and os.environ.get('SECRET_KEY'):
        main_app.secret_key = os.environ.get('SECRET_KEY')
    
    if os.environ.get('FLASK_ENV') == 'production':
        main_app.config['DEBUG'] = False
        main_app.config['TESTING'] = False
        main_app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 ano
        main_app.config['TEMPLATES_AUTO_RELOAD'] = False
        main_app.config['PROPAGATE_EXCEPTIONS'] = True
    
    # Middleware para compressão gzip
    def gzipped(f):
        @functools.wraps(f)
        def view_func(*args, **kwargs):
            if not request.accept_encodings.get('gzip', False):
                return f(*args, **kwargs)

            response = f(*args, **kwargs)
            
            if response.status_code < 200 or response.status_code >= 300:
                return response
                
            gzip_buffer = gzip.compress(response.data)
            
            response.data = gzip_buffer
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Content-Length'] = len(response.data)
            response.headers['Vary'] = 'Accept-Encoding'
            
            return response
            
        return view_func
    
    # Aplicar compressão gzip nas rotas principais
    for endpoint in ['/', '/calcular_frete', '/calcular_frete_dedicado', '/calcular_frete_aereo']:
        if endpoint in main_app.view_functions:
            main_app.view_functions[endpoint] = gzipped(main_app.view_functions[endpoint])
    
except Exception as e:
    # Em caso de erro, criar uma aplicação básica para diagnóstico
    main_app = Flask(__name__)
    cache = Cache(main_app, config=cache_config)
    
    @main_app.route('/')
    @cache.cached(timeout=60)  # Cache de 1 minuto para diagnóstico
    def diagnose():
        return {
            'status': 'error',
            'message': str(e),
            'python_version': os.sys.version,
            'environment': os.environ.get('FLASK_ENV', 'not set'),
            'working_directory': os.getcwd(),
            'files_in_directory': os.listdir('.')
        }

def create_app(config_name=None):
    """Factory function para criar a aplicação Flask com PostgreSQL"""
    
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Inicializar extensões
    db.init_app(app)
    migrate = Migrate(app, db)
    
    # Copiar rotas do arquivo principal
    for rule in main_app.url_map.iter_rules():
        if rule.endpoint != 'static':
            app.add_url_rule(
                rule.rule,
                endpoint=rule.endpoint,
                view_func=main_app.view_functions[rule.endpoint],
                methods=rule.methods
            )
    
    # Copiar configurações do app principal
    app.secret_key = main_app.secret_key
    app.jinja_env.globals.update(main_app.jinja_env.globals)
    
    # Adicionar contexto de shell para debug
    @app.shell_context_processor
    def make_shell_context():
        return {
            'db': db,
            'HistoricoCalculo': HistoricoCalculo,
            'LogSistema': LogSistema
        }
    
    # Criar tabelas se não existirem
    with app.app_context():
        try:
            db.create_all()
            print("[PostgreSQL] ✅ Tabelas criadas/verificadas com sucesso")
        except Exception as e:
            print(f"[PostgreSQL] ⚠️ Erro ao criar tabelas: {e}")
            print("[PostgreSQL] Continuando com fallback para logs em arquivo...")
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True) 