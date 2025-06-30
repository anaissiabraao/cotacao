#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Arquivo principal da aplicação de cotação de fretes
"""

import os
from flask import Flask
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

try:
    # Importar a aplicação principal
    from improved_chico_automate_fpdf import app
    
    # Configurar variáveis de ambiente importantes
    if not app.secret_key and os.environ.get('SECRET_KEY'):
        app.secret_key = os.environ.get('SECRET_KEY')
    
    if os.environ.get('FLASK_ENV') == 'production':
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
    
except Exception as e:
    # Em caso de erro, criar uma aplicação básica para diagnóstico
    app = Flask(__name__)
    
    @app.route('/')
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