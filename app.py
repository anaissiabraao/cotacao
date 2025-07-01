#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Arquivo principal da aplicação de cotação de fretes
"""

import os
import sys
from flask import Flask, request, jsonify
from flask_caching import Cache
from dotenv import load_dotenv
import gzip
import functools
from flask_migrate import Migrate

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

# Variáveis globais para controle
main_app = None
cache = None
POSTGRESQL_AVAILABLE = False

try:
    # Tentar importar os modelos do PostgreSQL
    from models import db, HistoricoCalculo, LogSistema
    from config import config
    POSTGRESQL_AVAILABLE = True
    print("[PostgreSQL] ✅ Modelos importados com sucesso")
except ImportError as import_error:
    POSTGRESQL_AVAILABLE = False
    print(f"[PostgreSQL] ⚠️ PostgreSQL não disponível: {import_error}")
    print("[PostgreSQL] Usando fallback para logs em arquivo")

try:
    # Importar a aplicação principal
    from improved_chico_automate_fpdf import app as imported_app
    main_app = imported_app
    
    # Configurar cache
    cache = Cache()
    cache.init_app(main_app, config=cache_config)
    
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
    
    print("[APP] ✅ Aplicação principal carregada com sucesso")

except Exception as main_error:
    # Em caso de erro, criar uma aplicação básica para diagnóstico
    print(f"[APP] ⚠️ Erro ao carregar aplicação principal: {main_error}")
    main_app = Flask(__name__)
    
    try:
        cache = Cache()
        cache.init_app(main_app, config=cache_config)
    except Exception as cache_error:
        print(f"[CACHE] ⚠️ Erro ao configurar cache: {cache_error}")
        cache = None
    
    @main_app.route('/')
    def diagnose():
        try:
            return jsonify({
                'status': 'error',
                'message': str(main_error),
                'python_version': sys.version,
                'environment': os.environ.get('FLASK_ENV', 'not set'),
                'working_directory': os.getcwd(),
                'files_in_directory': os.listdir('.'),
                'postgresql_available': POSTGRESQL_AVAILABLE,
                'cache_available': cache is not None
            })
        except Exception as diag_error:
            return jsonify({
                'status': 'critical_error',
                'message': f'Erro no diagnóstico: {str(diag_error)}',
                'original_error': str(main_error)
            })

def create_app(config_name=None):
    """Factory function para criar a aplicação Flask com PostgreSQL"""
    
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    
    # Configurar apenas se PostgreSQL estiver disponível
    if POSTGRESQL_AVAILABLE:
        try:
            app.config.from_object(config[config_name])
            
            # Inicializar extensões
            db.init_app(app)
            migrate = Migrate(app, db)
            
            # Criar tabelas se não existirem
            with app.app_context():
                try:
                    db.create_all()
                    print("[PostgreSQL] ✅ Tabelas criadas/verificadas com sucesso")
                except Exception as db_error:
                    print(f"[PostgreSQL] ⚠️ Erro ao criar tabelas: {db_error}")
                    print("[PostgreSQL] Continuando com fallback para logs em arquivo...")
            
            # Adicionar contexto de shell para debug
            @app.shell_context_processor
            def make_shell_context():
                return {
                    'db': db,
                    'HistoricoCalculo': HistoricoCalculo,
                    'LogSistema': LogSistema
                }
        except Exception as pg_error:
            print(f"[PostgreSQL] ⚠️ Erro na configuração PostgreSQL: {pg_error}")
            print("[PostgreSQL] Continuando sem banco de dados...")
    else:
        print("[PostgreSQL] ⚠️ PostgreSQL não disponível, usando configuração básica")
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    
    # Copiar rotas do arquivo principal se disponível
    if main_app and hasattr(main_app, 'url_map'):
        for rule in main_app.url_map.iter_rules():
            if rule.endpoint != 'static':
                try:
                    app.add_url_rule(
                        rule.rule,
                        endpoint=rule.endpoint,
                        view_func=main_app.view_functions[rule.endpoint],
                        methods=rule.methods
                    )
                except Exception as route_error:
                    print(f"[ROUTES] ⚠️ Erro ao copiar rota {rule.endpoint}: {route_error}")
    
    # Copiar configurações do app principal se disponível
    if main_app:
        if hasattr(main_app, 'secret_key') and main_app.secret_key:
            app.secret_key = main_app.secret_key
        if hasattr(main_app, 'jinja_env'):
            app.jinja_env.globals.update(main_app.jinja_env.globals)
    
    return app

if __name__ == '__main__':
    try:
        app = create_app()
        port = int(os.environ.get('PORT', 5000))
        print(f"[SERVER] 🚀 Iniciando servidor na porta {port}")
        app.run(host='0.0.0.0', port=port, debug=True)
    except Exception as server_error:
        print(f"[SERVER] ❌ Erro ao iniciar servidor: {server_error}")
        # Tentar usar apenas a aplicação principal
        if main_app:
            port = int(os.environ.get('PORT', 5000))
            print(f"[SERVER] 🔄 Tentando usar aplicação principal na porta {port}")
            main_app.run(host='0.0.0.0', port=port, debug=True)
        else:
            print("[SERVER] ❌ Não foi possível iniciar o servidor")
            sys.exit(1) 