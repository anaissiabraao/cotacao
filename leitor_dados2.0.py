import os
import pandas as pd
import numpy as np
import pdfplumber
import logging
from sqlalchemy import create_engine
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configurações
CAMINHO_BASE = Path(r"C:\Users\Usuário\OneDrive\Team Project\Data Base Controller\TABELA AGENTES")
SAIDA_DB = r"C:\Users\Usuário\OneDrive\Team Project\Data Base Controller\agentes.db"

def tratar_colunas_nulas(df):
    """Remove colunas totalmente nulas e linhas inválidas"""
    df = df.dropna(axis=1, how='all')
    df = df.dropna(how='all')
    return df.reset_index(drop=True)  # Resetar índice

def ler_pdf(caminho):
    """Lê PDFs com tratamento de erros e colunas nulas"""
    try:
        with pdfplumber.open(caminho) as pdf:
            tabelas = []
            for page in pdf.pages:
                try:
                    tbl = page.extract_table()
                    if tbl:
                        df = pd.DataFrame(tbl[1:], columns=tbl[0])
                        df = tratar_colunas_nulas(df)
                        tabelas.append(df)
                except Exception as e:
                    logging.warning(f"Erro na página {page.page_number}: {str(e)}")
                    continue
            if tabelas:
                return pd.concat(tabelas, ignore_index=True)  # Forçar índices únicos
            return None
    except Exception as e:
        logging.error(f"Falha ao ler PDF {caminho.name}: {str(e)}")
        return None

def processar_arquivo(caminho, agente):
    """Processa um único arquivo (PDF/Excel)"""
    if caminho.suffix.lower() == '.pdf':
        df = ler_pdf(caminho)
    elif caminho.suffix.lower() in ['.xls', '.xlsx']:
        try:
            df = pd.read_excel(caminho)
            df = tratar_colunas_nulas(df)
        except Exception as e:
            logging.error(f"Erro no Excel {caminho.name}: {str(e)}")
            return None
    else:
        return None
    
    if df is not None:
        # Padronização manual (ajuste conforme necessário)
        df = df.rename(columns={
            'Cidade': 'cidade',
            'Valor Total': 'preco',
            'Peso Inicial': 'peso_min',
            'Peso Final': 'peso_max',
            'Serviço': 'servico'
        })
        df['agente'] = agente
        return df.reset_index(drop=True)  # Garantir índice único
    return None

def processar_agente(pasta_agente):
    """Processa todos os arquivos de um agente com tratamento de erros"""
    dados = []
    for arquivo in os.listdir(pasta_agente):
        caminho = Path(pasta_agente) / arquivo
        if caminho.suffix.lower() in ['.pdf', '.xls', '.xlsx']:
            try:
                df = processar_arquivo(caminho, pasta_agente.name)
                if df is not None and not df.empty:
                    dados.append(df.reset_index(drop=True))  # Resetar índice
            except Exception as e:
                logging.error(f"Erro crítico em {arquivo}: {str(e)}")
                continue
    
    if dados:
        try:
            return pd.concat(dados, ignore_index=True)
        except Exception as e:
            logging.error(f"Falha ao concatenar dados de {pasta_agente.name}: {str(e)}")
            return None
    return None

def criar_base_unica():
    """Cria a base de dados SQLite consolidada"""
    engine = create_engine(f'sqlite:///{SAIDA_DB}')
    todos_dados = []
    
    for agente_dir in CAMINHO_BASE.iterdir():
        if agente_dir.is_dir():
            logging.info(f"Processando: {agente_dir.name}")
            df_agente = processar_agente(agente_dir)
            if df_agente is not None:
                todos_dados.append(df_agente)
              
                if __name__ == "__main__": criar_base_unica()
    # Diagnóstico rápido
    if os.path.exists(SAIDA_DB):
        print(f"Arquivo gerado: {SAIDA_DB}")
        try:
            import sqlite3
            conn = sqlite3.connect(SAIDA_DB)
            n = conn.execute("SELECT COUNT(*) FROM custos").fetchone()[0]
            print(f"Total de linhas na base: {n}")
            conn.close()
        except Exception as e:
            print("Não foi possível ler a base SQLite:", e)
    else:
        print("Arquivo de saída não foi criado!")
