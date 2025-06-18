#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Arquivo de compatibilidade - redireciona para o arquivo principal
"""

# Importar apenas o app do arquivo principal
from improved_chico_automate_fpdf import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False) 