#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PortoEx - Sistema de Gestão de Fretes
Aplicação principal Flask

Este é o ponto de entrada da aplicação.
O código principal está em improved_chico_automate_fpdf.py
"""

from improved_chico_automate_fpdf import app
from leitor_dados2_0 import ler_gollog_aereo

@app.route("/aereo", methods=["GET"])
def aereo():
    df_aereo = ler_gollog_aereo()
    if df_aereo is not None:
        # Ordenar (por exemplo, por custo_base) e converter para dict (ou list) para JSON
        df_aereo = df_aereo.sort_values(by="custo_base", ascending=True)
        dados = df_aereo.to_dict(orient="records")
        return jsonify(dados)
    else:
        return jsonify({"error": "Erro ao ler modal aéreo (GOLLOG)"}), 500

if __name__ == "__main__":
    app.run() 