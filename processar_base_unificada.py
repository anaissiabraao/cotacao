import pandas as pd
import numpy as np
import json
import os
from flask import jsonify

# Mapeamento de códigos de base para nomes de cidades
MAPEAMENTO_BASES = {
    # São Paulo
    "SPO": "São Paulo",
    "RAO": "Ribeirão Preto",
    "CPQ": "Campinas",
    "SJK": "São José dos Campos",
    "RPO": "São José do Rio Preto",
    "BAU": "Bauru",
    # Rio de Janeiro
    "RIO": "Rio de Janeiro",
    "CAW": "Campos dos Goytacazes",
    # Minas Gerais
    "BHZ": "Belo Horizonte",
    "UDI": "Uberlândia",
    "JDF": "Juiz de Fora",
    # Paraná
    "CWB": "Curitiba",
    "LDB": "Londrina",
    "MGF": "Maringá",
    # Santa Catarina
    "FLN": "Florianópolis",
    "JOI": "Joinville",
    "CFC": "Chapecó",
    "ITJ": "Itajaí",
    # Rio Grande do Sul
    "POA": "Porto Alegre",
    "CXJ": "Caxias do Sul",
    # Espírito Santo
    "VIX": "Vitória",
    # Bahia
    "SSA": "Salvador",
    # Pernambuco
    "REC": "Recife",
    # Ceará
    "FOR": "Fortaleza",
    # Goiás
    "GYN": "Goiânia",
    # Distrito Federal
    "BSB": "Brasília",
    # Mato Grosso
    "CGB": "Cuiabá",
    # Mato Grosso do Sul
    "CGR": "Campo Grande",
    # Pará
    "BEL": "Belém",
    # Amazonas
    "MAO": "Manaus",
    # Filial
    "FILIAL": "Filial Local"
}

def obter_nome_base(codigo):
    """
    Converte o código da base para o nome da cidade
    
    Args:
        codigo (str): Código da base (ex: RAO)
        
    Returns:
        str: Nome da cidade correspondente ou o próprio código se não encontrado
    """
    return MAPEAMENTO_BASES.get(str(codigo).strip().upper(), codigo)

def filtrar_por_tipo(df, tipo=None):
    """
    Filtra a base de dados por tipo
    
    Args:
        df (DataFrame): DataFrame com os dados da base unificada
        tipo (str, opcional): Tipo para filtrar ('Agente' ou 'Transferência')
        
    Returns:
        DataFrame: DataFrame filtrado
    """
    if tipo and tipo in df['Tipo'].unique():
        return df[df['Tipo'] == tipo]
    return df

def calcular_rota_direta(df, origem, destino, peso):
    """
    Calcula o custo da rota direta
    
    Args:
        df (DataFrame): DataFrame com os dados da base unificada
        origem (str): Código da base de origem
        destino (str): Código da base de destino
        peso (float): Peso da carga em kg
        
    Returns:
        dict: Dicionário com os resultados da rota direta
    """
    # Filtrar apenas transferências diretas entre origem e destino
    df_direto = df[(df['Tipo'] == 'Transferência') & 
                  (df['Base Origem'] == origem) & 
                  (df['Base Destino'] == destino)]
    
    resultados = []
    
    if df_direto.empty:
        return {
            "tipo": "Direto",
            "disponivel": False,
            "mensagem": f"Não há rota direta disponível entre {obter_nome_base(origem)} e {obter_nome_base(destino)}"
        }
    
    for _, linha in df_direto.iterrows():
        # Determinar faixa de peso
        faixa_peso = None
        for coluna in [10, 20, 30, 50, 70, 100, 300, 500]:
            if peso <= coluna:
                faixa_peso = coluna
                break
        
        if faixa_peso is None:
            faixa_peso = 'Acima 500'
        
        # Calcular valor base
        if isinstance(faixa_peso, str):
            valor_base_kg = float(linha.get(faixa_peso, 0))
        else:
            valor_base_kg = float(linha.get(faixa_peso, 0))
            
        valor_base = peso * valor_base_kg if faixa_peso != 10 else float(linha.get('VALOR MÍNIMO ATÉ 10', 0))
        
        # Calcular pedágio
        valor_pedagio = float(linha.get('Pedagio (100 Kg)', 0))
        pedagio = np.ceil(peso / 100) * valor_pedagio if valor_pedagio and peso > 0 else 0.0
        
        # Prazo
        prazo = int(linha.get('Prazo', 0))
        
        # Resultado
        resultados.append({
            "fornecedor": linha.get('Fornecedor', 'Não especificado'),
            "valor_base": round(valor_base, 2),
            "pedagio": round(pedagio, 2),
            "valor_total": round(valor_base + pedagio, 2),
            "prazo": prazo
        })
    
    # Ordenar por valor total
    resultados = sorted(resultados, key=lambda x: x["valor_total"])
    
    return {
        "tipo": "Direto",
        "disponivel": True,
        "origem": obter_nome_base(origem),
        "destino": obter_nome_base(destino),
        "resultados": resultados
    }

def calcular_rota_agentes(df, origem, destino, peso):
    """
    Calcula o custo da rota com agentes (origem + destino)
    
    Args:
        df (DataFrame): DataFrame com os dados da base unificada
        origem (str): Código da base de origem
        destino (str): Código da base de destino
        peso (float): Peso da carga em kg
        
    Returns:
        dict: Dicionário com os resultados da rota com agentes
    """
    # Filtrar agentes na origem e no destino
    df_agente_origem = df[(df['Tipo'] == 'Agente') & (df['Base Origem'] == origem)]
    df_agente_destino = df[(df['Tipo'] == 'Agente') & (df['Base Origem'] == destino)]
    
    if df_agente_origem.empty or df_agente_destino.empty:
        return {
            "tipo": "Agentes",
            "disponivel": False,
            "mensagem": f"Não há agentes disponíveis em ambas as localidades: {obter_nome_base(origem)} e {obter_nome_base(destino)}"
        }
    
    resultados = []
    
    for _, agente_origem in df_agente_origem.iterrows():
        for _, agente_destino in df_agente_destino.iterrows():
            # Verificar se são do mesmo fornecedor para melhor integração
            mesmo_fornecedor = agente_origem.get('Fornecedor') == agente_destino.get('Fornecedor')
            
            # Calcular custos para origem
            valor_origem = calcular_custo_agente(agente_origem, peso)
            
            # Calcular custos para destino
            valor_destino = calcular_custo_agente(agente_destino, peso)
            
            # Calcular prazo total (soma dos prazos)
            prazo_origem = int(agente_origem.get('Prazo', 0))
            prazo_destino = int(agente_destino.get('Prazo', 0))
            prazo_total = prazo_origem + prazo_destino
            
            # Bonificação se for o mesmo fornecedor (melhor integração)
            fator_integracao = 0.95 if mesmo_fornecedor else 1.0
            
            valor_total = (valor_origem['total'] + valor_destino['total']) * fator_integracao
            
            resultados.append({
                "fornecedor_origem": agente_origem.get('Fornecedor', 'Não especificado'),
                "fornecedor_destino": agente_destino.get('Fornecedor', 'Não especificado'),
                "mesmo_fornecedor": mesmo_fornecedor,
                "valor_origem": round(valor_origem['total'], 2),
                "valor_destino": round(valor_destino['total'], 2),
                "valor_total": round(valor_total, 2),
                "prazo": prazo_total
            })
    
    # Ordenar por valor total
    resultados = sorted(resultados, key=lambda x: x["valor_total"])
    
    return {
        "tipo": "Agentes",
        "disponivel": True,
        "origem": obter_nome_base(origem),
        "destino": obter_nome_base(destino),
        "resultados": resultados[:5]  # Limitar aos 5 melhores resultados
    }

def calcular_rota_completa(df, origem, destino, peso):
    """
    Calcula o custo da rota completa (agente + transferência + agente)
    
    Args:
        df (DataFrame): DataFrame com os dados da base unificada
        origem (str): Código da base de origem
        destino (str): Código da base de destino
        peso (float): Peso da carga em kg
        
    Returns:
        dict: Dicionário com os resultados da rota completa
    """
    # Filtrar agentes na origem e no destino
    df_agente_origem = df[(df['Tipo'] == 'Agente') & (df['Base Origem'] == origem)]
    df_agente_destino = df[(df['Tipo'] == 'Agente') & (df['Base Origem'] == destino)]
    
    # Filtrar transferências disponíveis
    df_transferencia = df[df['Tipo'] == 'Transferência']
    
    if df_agente_origem.empty or df_agente_destino.empty or df_transferencia.empty:
        return {
            "tipo": "Completa",
            "disponivel": False,
            "mensagem": f"Não há rotas completas disponíveis entre {obter_nome_base(origem)} e {obter_nome_base(destino)}"
        }
    
    resultados = []
    
    # Para cada combinação de agentes, buscar transferências disponíveis
    for _, agente_origem in df_agente_origem.iterrows():
        for _, agente_destino in df_agente_destino.iterrows():
            # Verificar se são do mesmo fornecedor
            mesmo_fornecedor = agente_origem.get('Fornecedor') == agente_destino.get('Fornecedor')
            
            # Buscar transferências que conectam as filiais dos agentes
            for _, transferencia in df_transferencia.iterrows():
                if transferencia['Base Origem'] == 'FILIAL' and transferencia['Base Destino'] == 'FILIAL':
                    # Calcular custos para origem
                    valor_origem = calcular_custo_agente(agente_origem, peso)
                    
                    # Calcular custos para transferência
                    valor_transferencia = calcular_custo_transferencia(transferencia, peso)
                    
                    # Calcular custos para destino
                    valor_destino = calcular_custo_agente(agente_destino, peso)
                    
                    # Calcular prazo total
                    prazo_origem = int(agente_origem.get('Prazo', 0))
                    prazo_transferencia = int(transferencia.get('Prazo', 0))
                    prazo_destino = int(agente_destino.get('Prazo', 0))
                    prazo_total = prazo_origem + prazo_transferencia + prazo_destino
                    
                    # Bonificação se for o mesmo fornecedor
                    fator_integracao = 0.95 if mesmo_fornecedor else 1.0
                    
                    valor_total = (valor_origem['total'] + valor_transferencia['total'] + valor_destino['total']) * fator_integracao
                    
                    resultados.append({
                        "fornecedor_origem": agente_origem.get('Fornecedor', 'Não especificado'),
                        "fornecedor_transferencia": transferencia.get('Fornecedor', 'Não especificado'),
                        "fornecedor_destino": agente_destino.get('Fornecedor', 'Não especificado'),
                        "mesmo_fornecedor": mesmo_fornecedor,
                        "valor_origem": round(valor_origem['total'], 2),
                        "valor_transferencia": round(valor_transferencia['total'], 2),
                        "valor_destino": round(valor_destino['total'], 2),
                        "valor_total": round(valor_total, 2),
                        "prazo": prazo_total
                    })
    
    # Ordenar por valor total
    resultados = sorted(resultados, key=lambda x: x["valor_total"])
    
    return {
        "tipo": "Completa",
        "disponivel": len(resultados) > 0,
        "origem": obter_nome_base(origem),
        "destino": obter_nome_base(destino),
        "resultados": resultados[:5] if resultados else []  # Limitar aos 5 melhores resultados
    }

def calcular_custo_agente(linha, peso):
    """
    Calcula o custo de um agente
    
    Args:
        linha (Series): Linha do DataFrame com os dados do agente
        peso (float): Peso da carga em kg
        
    Returns:
        dict: Dicionário com os custos calculados
    """
    # Determinar faixa de peso
    faixa_peso = None
    for coluna in [10, 20, 30, 50, 70, 100, 300, 500]:
        if peso <= coluna:
            faixa_peso = coluna
            break
    
    if faixa_peso is None:
        faixa_peso = 'Acima 500'
    
    # Calcular valor base
    if isinstance(faixa_peso, str):
        valor_base_kg = float(linha.get(faixa_peso, 0))
    else:
        valor_base_kg = float(linha.get(faixa_peso, 0))
        
    valor_base = peso * valor_base_kg if faixa_peso != 10 else float(linha.get('VALOR MÍNIMO ATÉ 10', 0))
    
    # Calcular pedágio
    valor_pedagio = float(linha.get('Pedagio (100 Kg)', 0))
    pedagio = np.ceil(peso / 100) * valor_pedagio if valor_pedagio and peso > 0 else 0.0
    
    return {
        "base": valor_base,
        "pedagio": pedagio,
        "total": valor_base + pedagio
    }

def calcular_custo_transferencia(linha, peso):
    """
    Calcula o custo de uma transferência
    
    Args:
        linha (Series): Linha do DataFrame com os dados da transferência
        peso (float): Peso da carga em kg
        
    Returns:
        dict: Dicionário com os custos calculados
    """
    # Determinar faixa de peso
    faixa_peso = None
    for coluna in [10, 20, 30, 50, 70, 100, 300, 500]:
        if peso <= coluna:
            faixa_peso = coluna
            break
    
    if faixa_peso is None:
        faixa_peso = 'Acima 500'
    
    # Calcular valor base
    if isinstance(faixa_peso, str):
        valor_base_kg = float(linha.get(faixa_peso, 0))
    else:
        valor_base_kg = float(linha.get(faixa_peso, 0))
        
    valor_base = peso * valor_base_kg if faixa_peso != 10 else float(linha.get('VALOR MÍNIMO ATÉ 10', 0))
    
    # Calcular pedágio
    valor_pedagio = float(linha.get('Pedagio (100 Kg)', 0))
    pedagio = np.ceil(peso / 100) * valor_pedagio if valor_pedagio and peso > 0 else 0.0
    
    return {
        "base": valor_base,
        "pedagio": pedagio,
        "total": valor_base + pedagio
    }

def gerar_ranking_precos(resultados_direto, resultados_agentes, resultados_completa):
    """
    Gera um ranking de preços considerando todas as modalidades de rota
    
    Args:
        resultados_direto (dict): Resultados da rota direta
        resultados_agentes (dict): Resultados da rota com agentes
        resultados_completa (dict): Resultados da rota completa
        
    Returns:
        list: Lista com o ranking de preços
    """
    ranking = []
    
    # Adicionar resultados da rota direta
    if resultados_direto.get("disponivel", False):
        for resultado in resultados_direto.get("resultados", []):
            ranking.append({
                "tipo": "Direto",
                "fornecedor": resultado.get("fornecedor"),
                "valor_total": resultado.get("valor_total"),
                "prazo": resultado.get("prazo"),
                "detalhes": resultado
            })
    
    # Adicionar resultados da rota com agentes
    if resultados_agentes.get("disponivel", False):
        for resultado in resultados_agentes.get("resultados", []):
            ranking.append({
                "tipo": "Agentes",
                "fornecedor": f"{resultado.get('fornecedor_origem')} / {resultado.get('fornecedor_destino')}",
                "valor_total": resultado.get("valor_total"),
                "prazo": resultado.get("prazo"),
                "detalhes": resultado
            })
    
    # Adicionar resultados da rota completa
    if resultados_completa.get("disponivel", False):
        for resultado in resultados_completa.get("resultados", []):
            ranking.append({
                "tipo": "Completa",
                "fornecedor": f"{resultado.get('fornecedor_origem')} / {resultado.get('fornecedor_transferencia')} / {resultado.get('fornecedor_destino')}",
                "valor_total": resultado.get("valor_total"),
                "prazo": resultado.get("prazo"),
                "detalhes": resultado
            })
    
    # Ordenar por valor total
    ranking = sorted(ranking, key=lambda x: x["valor_total"])
    
    return ranking

def processar_base_unificada(origem, destino, peso, valor_nf=0):
    """
    Processa a base unificada e retorna os resultados das diferentes modalidades de rota
    
    Args:
        origem (str): Código da base de origem
        destino (str): Código da base de destino
        peso (float): Peso da carga em kg
        valor_nf (float, opcional): Valor da nota fiscal
        
    Returns:
        dict: Dicionário com os resultados das diferentes modalidades de rota
    """
    try:
        # Carregar a base unificada
        df = pd.read_excel('Base_Unificada.xlsx')
        
        # Calcular as diferentes modalidades de rota
        resultados_direto = calcular_rota_direta(df, origem, destino, peso)
        resultados_agentes = calcular_rota_agentes(df, origem, destino, peso)
        resultados_completa = calcular_rota_completa(df, origem, destino, peso)
        
        # Gerar ranking de preços
        ranking = gerar_ranking_precos(resultados_direto, resultados_agentes, resultados_completa)
        
        return {
            "origem": obter_nome_base(origem),
            "destino": obter_nome_base(destino),
            "peso": peso,
            "valor_nf": valor_nf,
            "resultados": {
                "direto": resultados_direto,
                "agentes": resultados_agentes,
                "completa": resultados_completa
            },
            "ranking": ranking[:10]  # Limitar aos 10 melhores resultados
        }
    except Exception as e:
        return {
            "erro": str(e),
            "mensagem": "Erro ao processar a base unificada"
        }

def processar_modalidades_avancadas(origem, destino, peso, valor_nf=0, tipo_filtro=None):
    """
    Processa todas as modalidades avançadas de rota com sistema aprimorado:
    1. Filtra por tipo (Coluna A da planilha)
    2. Relaciona Base Origem (Coluna C) com nomenclaturas de bases
    3. Calcula diferentes modalidades: transferência direta, agente + transferência + agente
    4. Cria ranking completo de preços com todas as opções
    
    Args:
        origem (str): Código da base de origem (ex: RAO, SAO, RIO)
        destino (str): Código da base de destino
        peso (float): Peso da carga em kg
        valor_nf (float, opcional): Valor da nota fiscal
        tipo_filtro (str, opcional): Filtro por tipo ('Agente' ou 'Transferência')
        
    Returns:
        dict: Dicionário completo com todas as modalidades e ranking
    """
    try:
        # Carregar a base unificada
        df = pd.read_excel('Base_Unificada.xlsx')
        print(f"Base carregada com {len(df)} registros")
        print(f"Colunas disponíveis: {df.columns.tolist()}")
        
        # Verificar se as colunas necessárias existem
        colunas_necessarias = ['Tipo', 'Base Origem', 'Fornecedor']
        colunas_faltando = [col for col in colunas_necessarias if col not in df.columns]
        
        if colunas_faltando:
            print(f"ERRO: Colunas faltando: {colunas_faltando}")
            return {
                "erro": f"Colunas necessárias não encontradas: {', '.join(colunas_faltando)}",
                "colunas_disponeis": df.columns.tolist()
            }
        
        # 1. FILTRAR POR TIPO (Coluna A)
        df_filtrado = aplicar_filtro_tipo(df, tipo_filtro)
        print(f"Após filtro por tipo '{tipo_filtro}': {len(df_filtrado)} registros")
        
        # 2. RELACIONAR BASE ORIGEM COM NOMENCLATURAS
        mapeamento_bases = obter_mapeamento_bases_completo()
        
        # 3. CALCULAR DIFERENTES MODALIDADES
        modalidades = {
            "transferencia_direta": calcular_transferencia_direta_avancada(df_filtrado, origem, destino, peso, mapeamento_bases),
            "agente_transferencia_agente": calcular_rota_agente_completa(df_filtrado, origem, destino, peso, mapeamento_bases),
            "transferencia_simples": calcular_transferencia_simples(df_filtrado, origem, destino, peso, mapeamento_bases),
            "rota_mista": calcular_rota_mista(df_filtrado, origem, destino, peso, mapeamento_bases)
        }
        
        # 4. CRIAR RANKING COMPLETO DE PREÇOS
        ranking_completo = gerar_ranking_completo_avancado(modalidades, origem, destino, peso, valor_nf)
        
        # Estatísticas gerais
        estatisticas = gerar_estatisticas_modalidades(modalidades, df_filtrado)
        
        return {
            "origem": {
                "codigo": origem,
                "nome": mapeamento_bases.get(origem, origem),
            },
            "destino": {
                "codigo": destino, 
                "nome": mapeamento_bases.get(destino, destino),
            },
            "parametros": {
                "peso": peso,
                "valor_nf": valor_nf,
                "tipo_filtro": tipo_filtro
            },
            "modalidades": modalidades,
            "ranking_completo": ranking_completo,
            "estatisticas": estatisticas,
            "mapeamento_bases": mapeamento_bases,
            "total_opcoes": len(ranking_completo),
            "sucesso": True
        }
        
    except Exception as e:
        print(f"Erro ao processar modalidades avançadas: {str(e)}")
        return {
            "erro": str(e),
            "sucesso": False
        }

def aplicar_filtro_tipo(df, tipo_filtro):
    """
    Aplica filtro por tipo na coluna A da planilha
    """
    if not tipo_filtro:
        return df
    
    tipos_validos = df['Tipo'].unique()
    print(f"Tipos disponíveis na base: {tipos_validos}")
    
    if tipo_filtro not in tipos_validos:
        print(f"Aviso: Tipo '{tipo_filtro}' não encontrado. Tipos válidos: {tipos_validos}")
        return df
    
    df_filtrado = df[df['Tipo'] == tipo_filtro]
    print(f"Filtrado por tipo '{tipo_filtro}': {len(df_filtrado)} registros de {len(df)} totais")
    
    return df_filtrado

def obter_mapeamento_bases_completo():
    """
    Retorna mapeamento completo de códigos de bases para nomes de cidades
    Baseado na coluna C (Base Origem) da planilha
    """
    mapeamento_expandido = {
        # Principais bases
        "SPO": "São Paulo",
        "RIO": "Rio de Janeiro", 
        "RAO": "Ribeirão Preto",
        "BHZ": "Belo Horizonte",
        "CWB": "Curitiba",
        "POA": "Porto Alegre",
        "BSB": "Brasília",
        "GYN": "Goiânia",
        "CPQ": "Campinas",
        "AJU": "Aracaju",
        "FLN": "Florianópolis",
        "VIX": "Vitória",
        "FOR": "Fortaleza",
        "BEL": "Belém",
        "MAN": "Manaus",
        "REC": "Recife",
        "SSA": "Salvador",
        "FILIAL": "Filial Local",
        
        # Bases secundárias
        "SJK": "São José dos Campos",
        "RPO": "São José do Rio Preto", 
        "BAU": "Bauru",
        "CAW": "Campos dos Goytacazes",
        "UDI": "Uberlândia",
        "JDF": "Juiz de Fora",
        "LDB": "Londrina",
        "MGF": "Maringá",
        "JOI": "Joinville",
        "CFC": "Chapecó",
        "CXJ": "Caxias do Sul",
        "CGB": "Cuiabá",
        "CGR": "Campo Grande",
        "MAO": "Manaus",
        "ITJ": "Itajaí"
    }
    
    return mapeamento_expandido

def calcular_transferencia_direta_avancada(df, origem, destino, peso, mapeamento_bases):
    """
    Calcula transferência direta com informações avançadas de bases
    """
    df_transferencias = df[df['Tipo'] == 'Transferência']
    df_rota = df_transferencias[
        (df_transferencias['Base Origem'] == origem) & 
        (df_transferencias['Base Destino'] == destino)
    ]
    
    if df_rota.empty:
        return {
            "disponivel": False,
            "origem_base": {"codigo": origem, "nome": mapeamento_bases.get(origem, origem)},
            "destino_base": {"codigo": destino, "nome": mapeamento_bases.get(destino, destino)},
            "mensagem": f"Não há transferência direta entre {mapeamento_bases.get(origem, origem)} e {mapeamento_bases.get(destino, destino)}",
            "opcoes": []
        }
    
    opcoes = []
    for _, linha in df_rota.iterrows():
        custo_detalhado = calcular_custo_detalhado_avancado(linha, peso)
        
        opcao = {
            "fornecedor": linha.get('Fornecedor', 'N/A'),
            "origem_base": {"codigo": origem, "nome": mapeamento_bases.get(origem, origem)},
            "destino_base": {"codigo": destino, "nome": mapeamento_bases.get(destino, destino)},
            "modalidade": "Transferência Direta",
            "custos": custo_detalhado,
            "prazo": int(linha.get('Prazo', 0)),
            "observacoes": f"Rota direta {mapeamento_bases.get(origem, origem)} → {mapeamento_bases.get(destino, destino)}"
        }
        opcoes.append(opcao)
    
    # Ordenar por custo total
    opcoes.sort(key=lambda x: x['custos']['total'])
    
    return {
        "disponivel": True,
        "origem_base": {"codigo": origem, "nome": mapeamento_bases.get(origem, origem)},
        "destino_base": {"codigo": destino, "nome": mapeamento_bases.get(destino, destino)},
        "total_opcoes": len(opcoes),
        "opcoes": opcoes
    }

def calcular_rota_agente_completa(df, origem, destino, peso, mapeamento_bases):
    """
    Calcula rota completa: Agente Coleta + Transferência + Agente Entrega
    """
    df_agentes = df[df['Tipo'] == 'Agente'] 
    df_transferencias = df[df['Tipo'] == 'Transferência']
    
    # Encontrar agentes na origem
    agentes_origem = df_agentes[df_agentes['Base Origem'] == origem]
    
    # Encontrar agentes no destino
    agentes_destino = df_agentes[df_agentes['Base Origem'] == destino]
    
    if agentes_origem.empty and agentes_destino.empty:
        return {
            "disponivel": False,
            "mensagem": f"Não há agentes disponíveis em {mapeamento_bases.get(origem, origem)} ou {mapeamento_bases.get(destino, destino)}",
            "opcoes": []
        }
    
    rotas_completas = []
    
    # Combinar agentes de origem com transferências e agentes de destino
    for _, agente_orig in agentes_origem.iterrows():
        for _, transferencia in df_transferencias.iterrows():
            for _, agente_dest in agentes_destino.iterrows():
                
                # Verificar compatibilidade de bases na rota
                if (transferencia['Base Origem'] == origem and 
                    transferencia['Base Destino'] == destino):
                    
                    custo_coleta = calcular_custo_detalhado_avancado(agente_orig, peso)
                    custo_transferencia = calcular_custo_detalhado_avancado(transferencia, peso)
                    custo_entrega = calcular_custo_detalhado_avancado(agente_dest, peso)
                    
                    custo_total = (custo_coleta['total'] + 
                                 custo_transferencia['total'] + 
                                 custo_entrega['total'])
                    
                    prazo_total = (int(agente_orig.get('Prazo', 0)) + 
                                 int(transferencia.get('Prazo', 0)) + 
                                 int(agente_dest.get('Prazo', 0)))
                    
                    rota = {
                        "fornecedor_completo": f"{agente_orig.get('Fornecedor')}/{transferencia.get('Fornecedor')}/{agente_dest.get('Fornecedor')}",
                        "modalidade": "Agente + Transferência + Agente",
                        "etapas": {
                            "coleta": {
                                "fornecedor": agente_orig.get('Fornecedor'),
                                "base": {"codigo": origem, "nome": mapeamento_bases.get(origem, origem)},
                                "custos": custo_coleta,
                                "prazo": int(agente_orig.get('Prazo', 0))
                            },
                            "transferencia": {
                                "fornecedor": transferencia.get('Fornecedor'),
                                "origem_base": {"codigo": origem, "nome": mapeamento_bases.get(origem, origem)},
                                "destino_base": {"codigo": destino, "nome": mapeamento_bases.get(destino, destino)},
                                "custos": custo_transferencia,
                                "prazo": int(transferencia.get('Prazo', 0))
                            },
                            "entrega": {
                                "fornecedor": agente_dest.get('Fornecedor'),
                                "base": {"codigo": destino, "nome": mapeamento_bases.get(destino, destino)},
                                "custos": custo_entrega,
                                "prazo": int(agente_dest.get('Prazo', 0))
                            }
                        },
                        "custos_totais": {
                            "valor_base": custo_coleta['valor_base'] + custo_transferencia['valor_base'] + custo_entrega['valor_base'],
                            "pedagio": custo_coleta['pedagio'] + custo_transferencia['pedagio'] + custo_entrega['pedagio'],
                            "gris": custo_coleta['gris'] + custo_transferencia['gris'] + custo_entrega['gris'],
                            "total": custo_total
                        },
                        "prazo_total": prazo_total,
                        "observacoes": f"Rota completa: {mapeamento_bases.get(origem, origem)} (Coleta) → {mapeamento_bases.get(destino, destino)} (Entrega)"
                    }
                    
                    rotas_completas.append(rota)
    
    # Ordenar por custo total
    rotas_completas.sort(key=lambda x: x['custos_totais']['total'])
    
    return {
        "disponivel": len(rotas_completas) > 0,
        "total_opcoes": len(rotas_completas),
        "opcoes": rotas_completas[:10]  # Limitar aos 10 melhores
    }

def calcular_transferencia_simples(df, origem, destino, peso, mapeamento_bases):
    """
    Calcula apenas transferências simples (sem agentes)
    """
    df_transferencias = df[df['Tipo'] == 'Transferência']
    
    # Buscar todas as transferências possíveis
    opcoes_simples = []
    
    for _, linha in df_transferencias.iterrows():
        if (linha['Base Origem'] == origem and linha['Base Destino'] == destino):
            custo = calcular_custo_detalhado_avancado(linha, peso)
            
            opcao = {
                "fornecedor": linha.get('Fornecedor'),
                "modalidade": "Transferência Simples",
                "origem_base": {"codigo": origem, "nome": mapeamento_bases.get(origem, origem)},
                "destino_base": {"codigo": destino, "nome": mapeamento_bases.get(destino, destino)},
                "custos": custo,
                "prazo": int(linha.get('Prazo', 0))
            }
            opcoes_simples.append(opcao)
    
    opcoes_simples.sort(key=lambda x: x['custos']['total'])
    
    return {
        "disponivel": len(opcoes_simples) > 0,
        "total_opcoes": len(opcoes_simples),
        "opcoes": opcoes_simples
    }

def calcular_rota_mista(df, origem, destino, peso, mapeamento_bases):
    """
    Calcula rotas mistas (combinações de agentes e transferências)
    """
    df_agentes = df[df['Tipo'] == 'Agente']
    df_transferencias = df[df['Tipo'] == 'Transferência']
    
    rotas_mistas = []
    
    # Rota 1: Agente Origem + Transferência
    for _, agente in df_agentes.iterrows():
        if agente['Base Origem'] == origem:
            for _, transferencia in df_transferencias.iterrows():
                if transferencia['Base Origem'] == origem:
                    custo_agente = calcular_custo_detalhado_avancado(agente, peso)
                    custo_transferencia = calcular_custo_detalhado_avancado(transferencia, peso)
                    
                    rota = {
                        "modalidade": "Agente + Transferência",
                        "fornecedor_completo": f"{agente.get('Fornecedor')}/{transferencia.get('Fornecedor')}",
                        "etapas": {
                            "agente_origem": {
                                "fornecedor": agente.get('Fornecedor'),
                                "base": {"codigo": origem, "nome": mapeamento_bases.get(origem, origem)},
                                "custos": custo_agente
                            },
                            "transferencia": {
                                "fornecedor": transferencia.get('Fornecedor'),
                                "origem": {"codigo": origem, "nome": mapeamento_bases.get(origem, origem)},
                                "destino": {"codigo": destino, "nome": mapeamento_bases.get(destino, destino)},
                                "custos": custo_transferencia
                            }
                        },
                        "custos_totais": {
                            "total": custo_agente['total'] + custo_transferencia['total'],
                            "valor_base": custo_agente['valor_base'] + custo_transferencia['valor_base'],
                            "pedagio": custo_agente['pedagio'] + custo_transferencia['pedagio'],
                            "gris": custo_agente['gris'] + custo_transferencia['gris']
                        }
                    }
                    rotas_mistas.append(rota)
    
    # Rota 2: Transferência + Agente Destino
    for _, transferencia in df_transferencias.iterrows():
        if transferencia['Base Destino'] == destino:
            for _, agente in df_agentes.iterrows():
                if agente['Base Origem'] == destino:
                    custo_transferencia = calcular_custo_detalhado_avancado(transferencia, peso)
                    custo_agente = calcular_custo_detalhado_avancado(agente, peso)
                    
                    rota = {
                        "modalidade": "Transferência + Agente",
                        "fornecedor_completo": f"{transferencia.get('Fornecedor')}/{agente.get('Fornecedor')}",
                        "etapas": {
                            "transferencia": {
                                "fornecedor": transferencia.get('Fornecedor'),
                                "origem": {"codigo": origem, "nome": mapeamento_bases.get(origem, origem)},
                                "destino": {"codigo": destino, "nome": mapeamento_bases.get(destino, destino)},
                                "custos": custo_transferencia
                            },
                            "agente_destino": {
                                "fornecedor": agente.get('Fornecedor'),
                                "base": {"codigo": destino, "nome": mapeamento_bases.get(destino, destino)},
                                "custos": custo_agente
                            }
                        },
                        "custos_totais": {
                            "total": custo_transferencia['total'] + custo_agente['total'],
                            "valor_base": custo_transferencia['valor_base'] + custo_agente['valor_base'],
                            "pedagio": custo_transferencia['pedagio'] + custo_agente['pedagio'],
                            "gris": custo_transferencia['gris'] + custo_agente['gris']
                        }
                    }
                    rotas_mistas.append(rota)
    
    rotas_mistas.sort(key=lambda x: x['custos_totais']['total'])
    
    return {
        "disponivel": len(rotas_mistas) > 0,
        "total_opcoes": len(rotas_mistas),
        "opcoes": rotas_mistas[:10]
    }

def calcular_custo_detalhado_avancado(linha, peso):
    """
    Calcula custo detalhado para uma linha da planilha com tratamento de valores NaN
    """
    import pandas as pd
    import numpy as np
    
    def safe_float(value, default=0.0):
        """Converte valor para float tratando NaN e valores inválidos"""
        try:
            if pd.isna(value) or value is None:
                return default
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def safe_int(value, default=0):
        """Converte valor para int tratando NaN e valores inválidos"""
        try:
            if pd.isna(value) or value is None:
                return default
            return int(float(value))
        except (ValueError, TypeError):
            return default
    
    # Determinar faixa de peso
    faixa_peso = determinar_faixa_peso_avancada(peso)
    
    # Valor base com tratamento de NaN
    valor_base_raw = linha.get(faixa_peso, 0)
    valor_base_kg = safe_float(valor_base_raw, 0)
    
    if faixa_peso == 10:
        # Para peso até 10kg, usar valor mínimo se disponível
        valor_minimo_raw = linha.get('VALOR MÍNIMO ATÉ 10', valor_base_kg * peso)
        valor_base = safe_float(valor_minimo_raw, valor_base_kg * peso)
    else:
        valor_base = peso * valor_base_kg
    
    # Pedágio com tratamento de NaN
    valor_pedagio_raw = linha.get('Pedagio (100 Kg)', 0)
    valor_pedagio_100kg = safe_float(valor_pedagio_raw, 0)
    pedagio = np.ceil(peso / 100) * valor_pedagio_100kg if valor_pedagio_100kg > 0 else 0
    
    # GRIS com tratamento de NaN
    gris_min_raw = linha.get('Gris Min', 0)
    gris_excedente_raw = linha.get('Gris Exc', 0)
    gris_min = safe_float(gris_min_raw, 0)
    gris_excedente = safe_float(gris_excedente_raw, 0)
    gris = max(gris_min, valor_base * (gris_excedente / 100)) if gris_excedente > 0 else gris_min
    
    # Excedente com tratamento de NaN
    excedente_raw = linha.get('EXCEDENTE', 0)
    excedente = safe_float(excedente_raw, 0)
    
    # Prazo com tratamento de NaN
    prazo_raw = linha.get('Prazo', 1)
    prazo = safe_int(prazo_raw, 1)
    if prazo <= 0:
        prazo = 1
    
    total = valor_base + pedagio + gris + excedente
    
    return {
        "valor_base": round(valor_base, 2),
        "pedagio": round(pedagio, 2),
        "gris": round(gris, 2),
        "excedente": round(excedente, 2),
        "total": round(total, 2),
        "faixa_peso_usada": faixa_peso,
        "valor_kg": valor_base_kg,
        "prazo": prazo
    }

def determinar_faixa_peso_avancada(peso):
    """
    Determina a faixa de peso para busca na planilha
    """
    if peso <= 10:
        return 10
    elif peso <= 20:
        return 20
    elif peso <= 30:
        return 30
    elif peso <= 50:
        return 50
    elif peso <= 70:
        return 70
    elif peso <= 100:
        return 100
    elif peso <= 300:
        return 300
    elif peso <= 500:
        return 500
    else:
        return 'Acima 500'

def gerar_ranking_completo_avancado(modalidades, origem, destino, peso, valor_nf):
    """
    Gera ranking completo unificado de todas as modalidades
    """
    todas_opcoes = []
    
    # Adicionar opções de todas as modalidades
    for modalidade_nome, modalidade_dados in modalidades.items():
        if modalidade_dados.get('disponivel', False):
            opcoes = modalidade_dados.get('opcoes', [])
            
            for opcao in opcoes:
                opcao_ranking = {
                    "modalidade_categoria": modalidade_nome,
                    "modalidade_tipo": opcao.get('modalidade', modalidade_nome),
                    "fornecedor": opcao.get('fornecedor', opcao.get('fornecedor_completo', 'N/A')),
                    "custos": opcao.get('custos', opcao.get('custos_totais', {})),
                    "prazo": opcao.get('prazo', opcao.get('prazo_total', 0)),
                    "origem": opcao.get('origem_base', {"codigo": origem, "nome": "N/A"}),
                    "destino": opcao.get('destino_base', {"codigo": destino, "nome": "N/A"}),
                    "observacoes": opcao.get('observacoes', ''),
                    "detalhes": opcao
                }
                todas_opcoes.append(opcao_ranking)
    
    # Ordenar por custo total (menor primeiro)
    todas_opcoes.sort(key=lambda x: x['custos'].get('total', float('inf')))
    
    # Adicionar posição no ranking
    for i, opcao in enumerate(todas_opcoes, 1):
        opcao['posicao_ranking'] = i
        opcao['peso_kg'] = peso
        opcao['valor_nf'] = valor_nf
    
    return todas_opcoes

def gerar_estatisticas_modalidades(modalidades, df_filtrado):
    """
    Gera estatísticas sobre as modalidades encontradas
    """
    total_opcoes = 0
    modalidades_disponiveis = 0
    fornecedores_unicos = set()
    
    for modalidade_nome, modalidade_dados in modalidades.items():
        if modalidade_dados.get('disponivel', False):
            modalidades_disponiveis += 1
            opcoes = modalidade_dados.get('opcoes', [])
            total_opcoes += len(opcoes)
            
            for opcao in opcoes:
                fornecedor = opcao.get('fornecedor', opcao.get('fornecedor_completo', ''))
                if fornecedor:
                    fornecedores_unicos.add(fornecedor)
    
    # Estatísticas da base
    tipos_disponiveis = df_filtrado['Tipo'].unique().tolist() if not df_filtrado.empty else []
    fornecedores_base = df_filtrado['Fornecedor'].unique().tolist() if not df_filtrado.empty else []
    bases_origem = df_filtrado['Base Origem'].unique().tolist() if not df_filtrado.empty else []
    
    return {
        "total_opcoes_encontradas": total_opcoes,
        "modalidades_disponiveis": modalidades_disponiveis,
        "total_modalidades_verificadas": len(modalidades),
        "fornecedores_unicos_utilizados": len(fornecedores_unicos),
        "fornecedores_utilizados": list(fornecedores_unicos),
        "base_dados": {
            "total_registros": len(df_filtrado),
            "tipos_disponiveis": tipos_disponiveis,
            "fornecedores_na_base": len(fornecedores_base),
            "bases_origem_disponiveis": bases_origem
        }
    }

# Função principal para uso direto
if __name__ == "__main__":
    # Exemplo de uso
    resultado = processar_modalidades_avancadas(
        origem="RAO",  # Ribeirão Preto
        destino="SAO", # São Paulo  
        peso=50,
        valor_nf=1000,
        tipo_filtro=None  # ou "Agente" ou "Transferência"
    )
    
    if resultado.get('sucesso'):
        print(f"\n=== RESULTADO DO PROCESSAMENTO ===")
        print(f"Origem: {resultado['origem']['nome']} ({resultado['origem']['codigo']})")
        print(f"Destino: {resultado['destino']['nome']} ({resultado['destino']['codigo']})")
        print(f"Total de opções encontradas: {resultado['total_opcoes']}")
        
        print(f"\n=== RANKING COMPLETO (TOP 5) ===")
        for i, opcao in enumerate(resultado['ranking_completo'][:5], 1):
            print(f"{i}. {opcao['fornecedor']} - R${opcao['custos']['total']:.2f} - {opcao['modalidade_tipo']}")
    else:
        print(f"Erro: {resultado.get('erro')}")