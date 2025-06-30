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
    from improved_chico_automate_fpdf import app
    
    # Configurar cache
    cache = Cache(app, config=cache_config)
    
    # Configurar variáveis de ambiente importantes
    if not app.secret_key and os.environ.get('SECRET_KEY'):
        app.secret_key = os.environ.get('SECRET_KEY')
    
    if os.environ.get('FLASK_ENV') == 'production':
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 ano
        app.config['TEMPLATES_AUTO_RELOAD'] = False
        app.config['PROPAGATE_EXCEPTIONS'] = True
    
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
        if endpoint in app.view_functions:
            app.view_functions[endpoint] = gzipped(app.view_functions[endpoint])
    
except Exception as e:
    # Em caso de erro, criar uma aplicação básica para diagnóstico
    app = Flask(__name__)
    cache = Cache(app, config=cache_config)
    
    @app.route('/')
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

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port, debug=False) 