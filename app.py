#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PortoEx - Sistema de Gestão de Fretes
Aplicação principal Flask

Este é o ponto de entrada da aplicação.
O código principal está em improved_chico_automate_fpdf.py
"""

import os
from improved_chico_automate_fpdf import app

# Configuração para produção com Gunicorn
if __name__ == "__main__":
    # Para desenvolvimento local
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
else:
    # Para produção com Gunicorn
    # Configurações específicas para Render
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "fallback-secret-key"),
        DEBUG=False,
        TESTING=False
    ) 