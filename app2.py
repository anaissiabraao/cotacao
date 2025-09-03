#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pandas as pd
import datetime
import math
import requests
import polyline
import time
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash
import io
import os
import re
import json
import uuid
from dotenv import load_dotenv
from functools import lru_cache
from sqlalchemy import text

# Carregar variáveis de ambiente
load_dotenv()

# Configuração do Flask
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv("SECRET_KEY", "chave_secreta_portoex_2025")

# Configuração do banco de dados
database_url = os.environ.get('DATABASE_URL', '')

# Limpar a URL se tiver aspas
if database_url:
    database_url = database_url.strip().strip("'").strip('"')
    
    # Verificar se é uma URL válida do Neon
    if (database_url.startswith('postgresql://') and 
        'neon.tech' in database_url and 
        not database_url.startswith('postgresql://localhost')):
        
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        print(f"[CONFIG] ✅ Produção usando DATABASE_URL: {database_url[:50]}...")
    else:
        # URL inválida ou localhost
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portoex.db'
        print(f"[CONFIG] ⚠️ DATABASE_URL inválido: {database_url[:50]}..., usando SQLite")
else:
    # Sem DATABASE_URL
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portoex.db'
    print("[CONFIG] ⚠️ DATABASE_URL não encontrado, usando SQLite")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_BINDS'] = {}
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_timeout': 20,
    'max_overflow': 0
}

# Inicializar banco de dados
POSTGRESQL_AVAILABLE = False

try:
    print("[DATABASE] 🔄 Inicializando banco de dados...")
    from models import db, Usuario, BaseUnificada, AgenteTransportadora, MemoriaCalculoAgente, Agente, TipoCalculoFrete, FormulaCalculoFrete, ConfiguracaoAgente, HistoricoCalculo, LogSistema
    
    # Inicializar o banco
    db.init_app(app)
    print("[DATABASE] ✅ SQLAlchemy inicializado")
    
    # Criar contexto da aplicação
    with app.app_context():
        print("[DATABASE] 🔄 Criando tabelas...")
        db.create_all()
        print("[DATABASE] ✅ Tabelas criadas")
        
        # Criar usuário admin padrão
        print("[DATABASE] 🔄 Criando usuário admin...")
        Usuario.criar_usuario_admin_default()
        print("[DATABASE] ✅ Usuário admin criado")
        
        print("[DATABASE] ✅ Sistema inicializado com sucesso")
        
    POSTGRESQL_AVAILABLE = True
    print("[DATABASE] ✅ PostgreSQL disponível")
    
except Exception as e:
    print(f"[DATABASE] ❌ Erro na inicialização: {e}")
    POSTGRESQL_AVAILABLE = False
    print("[DATABASE] ⚠️ Usando SQLite como fallback")

# Configurações de sessão
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=7)

# Cache para municípios
MUNICIPIOS_CACHE = {}

# ===== FUNÇÕES AUXILIARES LIMPAS =====

def normalizar_cidade_nome(cidade):
    """Normaliza nome da cidade"""
    if not cidade:
        return ""
    return re.sub(r'[^\w\s-]', '', str(cidade).strip().title())

def normalizar_uf(uf):
    """Normaliza UF"""
    if not uf:
        return ""
    return str(uf).strip().upper()[:2]

def obter_ip_cliente():
    """Obtém IP do cliente"""
    return request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', '127.0.0.1'))

def log_acesso(usuario, acao, ip, detalhes=""):
    """Log de acesso simplificado"""
    try:
        if POSTGRESQL_AVAILABLE:
            LogSistema.log('INFO', acao, usuario, ip, detalhes)
        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        print(f"[LOG] {timestamp} - {usuario} - {acao} - IP: {ip}")
    except Exception as e:
        print(f"[LOG] Erro: {e}")

# ===== CONSTANTES PARA CÁLCULO DEDICADO =====

def determinar_faixa(distancia):
    """Determina a faixa de distância para cálculo de custos"""
    faixas = [
        (0, 20), (20, 50), (50, 100), (100, 150), (150, 200),
        (200, 250), (250, 300), (300, 400), (400, 600), (600, 800),
        (800, 1000), (1000, 1500), (1500, 2000), (2000, 2500),
        (2500, 3000), (3000, 3500), (3500, 4000), (4000, 4500),
        (4500, 6000)
    ]
    for min_val, max_val in faixas:
        if min_val < distancia <= max_val:
            return f"{min_val}-{max_val}"
    return None

# Tabela fixa de custos para frete dedicado por faixa de distância e tipo de veículo
TABELA_CUSTOS_DEDICADO = {
    "0-20": {"FIORINO": 150.0, "VAN": 200.0, "3/4": 250.0, "TOCO": 300.0, "TRUCK": 350.0, "CARRETA": 500.0},
    "20-50": {"FIORINO": 200.0, "VAN": 250.0, "3/4": 300.0, "TOCO": 400.0, "TRUCK": 500.0, "CARRETA": 700.0},
    "50-100": {"FIORINO": 300.0, "VAN": 400.0, "3/4": 500.0, "TOCO": 600.0, "TRUCK": 700.0, "CARRETA": 1000.0},
    "100-150": {"FIORINO": 400.0, "VAN": 500.0, "3/4": 600.0, "TOCO": 800.0, "TRUCK": 1000.0, "CARRETA": 1500.0},
    "150-200": {"FIORINO": 500.0, "VAN": 600.0, "3/4": 800.0, "TOCO": 1000.0, "TRUCK": 1200.0, "CARRETA": 1800.0},
    "200-250": {"FIORINO": 600.0, "VAN": 800.0, "3/4": 1000.0, "TOCO": 1200.0, "TRUCK": 1500.0, "CARRETA": 2200.0},
    "250-300": {"FIORINO": 700.0, "VAN": 900.0, "3/4": 1200.0, "TOCO": 1500.0, "TRUCK": 1800.0, "CARRETA": 2500.0},
    "300-400": {"FIORINO": 900.0, "VAN": 1200.0, "3/4": 1500.0, "TOCO": 1800.0, "TRUCK": 2200.0, "CARRETA": 3000.0},
    "400-600": {"FIORINO": 1200.0, "VAN": 1600.0, "3/4": 2000.0, "TOCO": 2500.0, "TRUCK": 3000.0, "CARRETA": 4000.0}
}

# Valores por km acima de 600km
DEDICADO_KM_ACIMA_600 = {
    "FIORINO": 3.0,
    "VAN": 4.0,
    "3/4": 4.5,
    "TOCO": 5.0,
    "TRUCK": 5.5,
    "CARRETA": 8.0
}

# ===== SISTEMA DE CÁLCULO RESTAURADO =====

def carregar_base_unificada():
    """Carrega base unificada do PostgreSQL"""
    try:
        if not POSTGRESQL_AVAILABLE:
            print("[BASE] ⚠️ PostgreSQL não disponível")
            return None
            
        registros = BaseUnificada.query.all()
        
        # Converter para formato pandas-like para compatibilidade
        dados = []
        for r in registros:
            dados.append({
                'Tipo': r.tipo,
                'Fornecedor': r.fornecedor,
                'Base Origem': r.base_origem,
                'Origem': r.origem,
                'Base Destino': r.base_destino,
                'Destino': r.destino,
                'VALOR MÍNIMO ATÉ 10': r.valor_minimo_10,
                '20': r.peso_20,
                '30': r.peso_30,
                '50': r.peso_50,
                '70': r.peso_70,
                '100': r.peso_100,
                '150': r.peso_150,
                '200': r.peso_200,
                '300': r.peso_300,
                '500': r.peso_500,
                'Acima 500': r.acima_500,
                'Pedagio (100 Kg)': r.pedagio_100kg,
                'EXCEDENTE': r.excedente,
                'Seguro': r.seguro,
                'PESO MÁXIMO TRANSPORTADO': r.peso_maximo,
                'Gris Min': r.gris_min,
                'Gris Exc': r.gris_exc,
                'TAS': r.tas,
                'DESPACHO': r.despacho
            })
        
        import pandas as pd
        df = pd.DataFrame(dados)
        print(f"[BASE] ✅ PostgreSQL carregado: {len(df)} registros")
        return df
        
    except Exception as e:
        print(f"[BASE] ❌ Erro ao carregar PostgreSQL: {e}")
        return None

def popular_banco_com_memorias_originais():
    """Popula o banco de dados com as memórias de cálculo originais - EXECUTAR UMA VEZ"""
    try:
        # Verificar se já existem agentes
        if AgenteTransportadora.query.count() > 0:
            print("[SETUP] ✅ Agentes já existem no banco - não sobrescrever")
            return
        
        print("[SETUP] 🔧 Populando banco com memórias de cálculo originais...")
        
        # 1. Criar tipos de cálculo
        tipos_calculo = [
            {'nome': 'FRACIONADO_DIRETO', 'descricao': 'Frete fracionado direto porta-a-porta', 'categoria': 'FRACIONADO'},
            {'nome': 'FRACIONADO_TRANSFERENCIA', 'descricao': 'Frete fracionado com transferência', 'categoria': 'FRACIONADO'},
            {'nome': 'FRACIONADO_AGENTE_COLETA', 'descricao': 'Frete fracionado com agente de coleta', 'categoria': 'FRACIONADO'},
            {'nome': 'FRACIONADO_AGENTE_ENTREGA', 'descricao': 'Frete fracionado com agente de entrega', 'categoria': 'FRACIONADO'},
            {'nome': 'FRACIONADO_ROTA_COMPLETA', 'descricao': 'Frete fracionado com agente + transferência + agente', 'categoria': 'FRACIONADO'}
        ]
        
        tipos_ids = {}
        for tipo_data in tipos_calculo:
            tipo = TipoCalculoFrete(
                nome=tipo_data['nome'],
                descricao=tipo_data['descricao'],
                categoria=tipo_data['categoria']
            )
            db.session.add(tipo)
            db.session.flush()  # Para obter o ID
            tipos_ids[tipo_data['nome']] = tipo.id
        
        # 2. Criar fórmulas de cálculo baseadas no código original
        formulas_originais = [
            {
                'nome': 'JEM_DFI_TRANSFERENCIA',
                'tipo': 'FRACIONADO_TRANSFERENCIA',
                'formula': '''
# Lógica original JEM/DFI - transferência padrão
peso_calculo = float(peso_usado)
valor_minimo = linha_base.get('VALOR MÍNIMO ATÉ 10')
if peso_calculo <= 10 and valor_minimo and float(valor_minimo) > 0:
    resultado = float(valor_minimo)
else:
    faixas_kg = [20, 30, 50, 70, 100, 150, 200, 300, 500]
    for faixa in faixas_kg:
        if peso_calculo <= float(faixa):
            valor_faixa = linha_base.get(str(faixa), 0)
            if valor_faixa and float(valor_faixa) > 0:
                resultado = peso_calculo * float(valor_faixa)
                break
''',
                'condicoes': 'fornecedor.contains("JEM") or fornecedor.contains("DFI")',
                'prioridade': 1
            },
            {
                'nome': 'REUNIDAS_VALOR_FIXO',
                'tipo': 'FRACIONADO_DIRETO',
                'formula': '''
# Lógica original REUNIDAS - valor fixo faixa 200kg
valor_200 = linha_base.get('200', 0)
if valor_200 and float(valor_200) > 0:
    resultado = float(valor_200)  # Valor fixo, não multiplicado
else:
    for faixa in [100, 150, 300, 500]:
        valor_faixa = linha_base.get(str(faixa), 0)
        if valor_faixa and float(valor_faixa) > 0:
            resultado = float(valor_faixa)
            break
''',
                'condicoes': 'fornecedor.contains("REUNIDAS")',
                'prioridade': 1
            },
            {
                'nome': 'PTX_MULTIPLICADO',
                'tipo': 'FRACIONADO_DIRETO',
                'formula': '''
# Lógica original PTX - valor multiplicado pelo peso
peso_calculo = float(peso_usado)
valor_por_kg = 0.0
for key in ['20', '10', '30', '50', '70', '100']:
    valor_key = linha_base.get(key, 0)
    if valor_key and float(valor_key) > 0:
        valor_por_kg = float(valor_key)
        break
resultado = peso_calculo * valor_por_kg
''',
                'condicoes': 'fornecedor.contains("PTX")',
                'prioridade': 1
            },
            {
                'nome': 'GRITSCH_DIRETO',
                'tipo': 'FRACIONADO_DIRETO',
                'formula': '''
# Lógica original Gritsch - direto porta-a-porta
peso_calculo = float(peso_usado)
valor_minimo = linha_base.get('VALOR MÍNIMO ATÉ 10')
if peso_calculo <= 10 and valor_minimo and float(valor_minimo) > 0:
    resultado = float(valor_minimo)
else:
    faixas_kg = [20, 30, 50, 70, 100, 150, 200, 300, 500]
    for faixa in faixas_kg:
        if peso_calculo <= float(faixa):
            valor_faixa = linha_base.get(str(faixa), 0)
            if valor_faixa and float(valor_faixa) > 0:
                resultado = peso_calculo * float(valor_faixa)
                break
''',
                'condicoes': 'fornecedor.contains("GRITSCH")',
                'prioridade': 1
            },
            {
                'nome': 'ROTA_COMPLETA_AUTOMATICA',
                'tipo': 'FRACIONADO_ROTA_COMPLETA',
                'formula': '''
# Sistema automático de combinação de agentes
# Busca automaticamente: agente_coleta + transferencia + agente_entrega
# Soma os custos totais de cada etapa
resultado = custo_coleta_total + custo_transferencia_total + custo_entrega_total
''',
                'condicoes': 'peso_cubado <= 1000',
                'prioridade': 1
            }
        ]
        
        formulas_ids = {}
        for formula_data in formulas_originais:
            formula = FormulaCalculoFrete(
                nome=formula_data['nome'],
                tipo_calculo_id=tipos_ids[formula_data['tipo']],
                formula=formula_data['formula'],
                condicoes=formula_data['condicoes'],
                prioridade=formula_data['prioridade']
            )
            db.session.add(formula)
            db.session.flush()
            formulas_ids[formula_data['nome']] = formula.id
        
        # 3. Criar apenas configurações de sistema, sem agentes hardcoded
        print("[SETUP] ✅ Tipos de cálculo e fórmulas configurados")
        
        db.session.commit()
        print(f"[SETUP] ✅ Sistema de tipos e fórmulas configurado")
        
        print(f"[SETUP] ✅ Sistema base configurado com {len(tipos_calculo)} tipos e {len(formulas_originais)} fórmulas")
        print("[SETUP] 📝 Use a interface admin para cadastrar agentes e configurações específicas")
        
    except Exception as e:
        print(f"[SETUP] ❌ Erro ao popular banco: {e}")
        db.session.rollback()



def carregar_agentes_e_memorias():
    """Carrega agentes e memórias do banco de dados - VERSÃO LIMPA"""
    try:
        if not POSTGRESQL_AVAILABLE:
            print("[AGENTES] ⚠️ PostgreSQL não disponível")
            return {}
            
        # Filtrar apenas os agentes que configuramos especificamente
        agentes_configurados = ['PTX', 'Jem/Dfl', 'SOL', 'FILIAL SP', 'GLI']
        
        # Carregar agentes do banco
        agentes = AgenteTransportadora.query.filter(
            AgenteTransportadora.nome.in_(agentes_configurados),
            AgenteTransportadora.ativo == True
        ).all()
        agentes_dict = {}
        
        for agente in agentes:
            # Carregar parâmetros de cálculo
            parametros = agente.get_parametros_calculo()
            
            agentes_dict[agente.nome] = {
                'id': agente.id,
                'nome': agente.nome,
                'tipo': agente.tipo_agente,
                'logica_calculo': agente.logica_calculo,
                'gris_percentual': agente.gris_percentual,
                'gris_minimo': agente.gris_minimo,
                'pedagio_por_bloco': agente.pedagio_por_bloco,
                'parametros': parametros,
                'descricao': agente.descricao_logica,
                'memorias': []
            }
            
            # Carregar memórias específicas
            memorias = MemoriaCalculoAgente.query.filter_by(agente_id=agente.id).all()
            for memoria in memorias:
                try:
                    config = json.loads(memoria.configuracao_memoria) if memoria.configuracao_memoria else {}
                    agentes_dict[agente.nome]['memorias'].append({
                        'id': memoria.id,
                        'tipo_memoria': memoria.tipo_memoria,
                        'nome_memoria': memoria.nome_memoria,
                        'condicoes': memoria.condicoes_aplicacao,
                        'configuracao': config,
                        'prioridade': memoria.prioridade if hasattr(memoria, 'prioridade') else 1
                    })
                except Exception as e:
                    print(f"[MEMORIA] ⚠️ Erro ao carregar memória {memoria.id}: {e}")
        
        print(f"[AGENTES] ✅ {len(agentes_dict)} agentes configurados carregados do banco")
        return agentes_dict
        
    except Exception as e:
        print(f"[AGENTES] ❌ Erro ao carregar do banco: {e}")
        return {}

def calcular_rotas_automaticas_banco(origem, uf_origem, destino, uf_destino, peso_cubado, valor_nf, df_base):
    """Calcula rotas combinadas automaticamente baseado na base de dados (como no código original)"""
    try:
        # Normalizar nomes como no código original
        origem_norm = origem.strip().title()
        destino_norm = destino.strip().title()
        
        # Separar tipos da base como no código original
        df_agentes = df_base[df_base['Tipo'] == 'Agente'].copy()
        df_transferencias = df_base[df_base['Tipo'] == 'Transferência'].copy()
        
        # Buscar agentes de coleta na origem (como no código original)
        agentes_coleta = df_agentes[
            df_agentes['Origem'].str.contains(origem_norm, case=False, na=False)
        ]
        
        # Buscar agentes de entrega no destino (como no código original)
        # Como os agentes têm Destino=None, vamos buscar agentes que atendem a região do destino
        agentes_entrega = df_agentes[
            (df_agentes['Origem'].str.contains(destino_norm, case=False, na=False)) |
            (df_agentes['Base Destino'].str.contains(destino_norm, case=False, na=False))
        ]
        
        # Buscar agentes por estado também (para melhor cobertura)
        agentes_coleta_estado = df_agentes[
            df_agentes['Base Origem'].str.contains(uf_origem, case=False, na=False)
        ]
        agentes_entrega_estado = df_agentes[
            df_agentes['Base Destino'].str.contains(uf_destino, case=False, na=False)
        ]
        
        # Combinar resultados e REMOVER DUPLICATAS por fornecedor
        agentes_coleta = pd.concat([agentes_coleta, agentes_coleta_estado]).drop_duplicates(subset=['Fornecedor'])
        agentes_entrega = pd.concat([agentes_entrega, agentes_entrega_estado]).drop_duplicates(subset=['Fornecedor'])
        
        # Buscar transferências diretas
        transferencias_diretas = df_transferencias[
            (df_transferencias['Origem'].str.contains(origem_norm, case=False, na=False)) &
            (df_transferencias['Destino'].str.contains(destino_norm, case=False, na=False))
        ]
        
        print(f"[ROTAS_AUTO] 🔍 Encontrados na base - Coleta: {len(agentes_coleta)}, Transferência: {len(df_transferencias)}, Entrega: {len(agentes_entrega)}, Diretas: {len(transferencias_diretas)}")
        
        # Listar agentes encontrados
        if not agentes_coleta.empty:
            print(f"[ROTAS_AUTO] 📦 Agentes de coleta: {list(agentes_coleta['Fornecedor'].values)}")
        if not agentes_entrega.empty:
            print(f"[ROTAS_AUTO] 🚚 Agentes de entrega: {list(agentes_entrega['Fornecedor'].values)}")
        
        rotas_combinadas = []
        
        # 1. Rotas diretas (identificação automática pela base) - APENAS AGENTES QUE ATENDEM ORIGEM E DESTINO
        agentes_diretos = df_agentes[
            (df_agentes['Origem'].str.contains(origem_norm, case=False, na=False)) &
            (df_agentes['Destino'].str.contains(destino_norm, case=False, na=False))
        ]
        
        for _, agente in agentes_diretos.iterrows():
            rota = criar_rota_direta_original(agente, origem, destino, peso_cubado, valor_nf)
            if rota:
                rotas_combinadas.append(rota)
        
        # 2. Transferências diretas (como no original)
        for _, transferencia in transferencias_diretas.iterrows():
            rota = criar_rota_transferencia_direta_original(transferencia, origem, destino, peso_cubado, valor_nf)
            if rota:
                rotas_combinadas.append(rota)
        
        # 3. Rotas combinadas (agente + transferência + agente) - COMO NO ORIGINAL
        if not agentes_coleta.empty and not agentes_entrega.empty and not df_transferencias.empty:
            print(f"[ROTAS_AUTO] 🔗 Criando rotas combinadas (coleta + transferência + entrega)...")
            
            # Limitar para performance (como no original)
            for _, agente_col in agentes_coleta.head(2).iterrows():
                for _, transferencia in df_transferencias.head(3).iterrows():
                    for _, agente_ent in agentes_entrega.head(2).iterrows():
                        
                        rota = criar_rota_combinada_original(agente_col, transferencia, agente_ent, origem, destino, peso_cubado, valor_nf)
                        if rota:
                            # Adicionar prefixo para identificar como rota combinada
                            rota['tipo_servico'] = f"COMBINADA: {rota['tipo_servico']}"
                            rota['descricao'] = f"Rota completa com 3 agentes especializados"
                            rotas_combinadas.append(rota)
                            print(f"[ROTAS_AUTO] ✅ Rota combinada criada: {agente_col.get('Fornecedor')} + {transferencia.get('Fornecedor')} + {agente_ent.get('Fornecedor')} = R$ {rota.get('custo_total', 0):.2f}")
                        else:
                            print(f"[ROTAS_AUTO] ❌ Falha ao criar rota combinada: {agente_col.get('Fornecedor')} + {transferencia.get('Fornecedor')} + {agente_ent.get('Fornecedor')}")
        
        # 4. ROTAS PARCIAIS - Quando falta agente de coleta ou entrega
        print(f"[ROTAS_AUTO] 🔗 Criando rotas parciais...")
        
        # Rota parcial: Transferência + Entrega (sem coleta)
        if agentes_coleta.empty and not agentes_entrega.empty and not df_transferencias.empty:
            print(f"[ROTAS_AUTO] ⚠️ Criando rota parcial: Transferência + Entrega (sem agente de coleta)")
            for _, transferencia in df_transferencias.head(2).iterrows():
                for _, agente_ent in agentes_entrega.head(2).iterrows():
                    rota = criar_rota_parcial_transferencia_entrega(transferencia, agente_ent, origem, destino, peso_cubado, valor_nf)
                    if rota:
                        rotas_combinadas.append(rota)
        
        # Rota parcial: Coleta + Transferência (sem entrega)
        if not agentes_coleta.empty and agentes_entrega.empty and not df_transferencias.empty:
            print(f"[ROTAS_AUTO] ⚠️ Criando rota parcial: Coleta + Transferência (sem agente de entrega)")
            for _, agente_col in agentes_coleta.head(2).iterrows():
                for _, transferencia in df_transferencias.head(2).iterrows():
                    rota = criar_rota_parcial_coleta_transferencia(agente_col, transferencia, origem, destino, peso_cubado, valor_nf)
                    if rota:
                        rotas_combinadas.append(rota)
        
        # Ordenar por custo total (como no original)
        rotas_combinadas.sort(key=lambda x: x.get('custo_total', float('inf')))
        
        print(f"[ROTAS_AUTO] ✅ {len(rotas_combinadas)} rotas automáticas calculadas")
        return rotas_combinadas[:10]  # Retornar as 10 melhores
        
    except Exception as e:
        print(f"[ROTAS_AUTO] ❌ Erro: {e}")
        return []

def calcular_rota_direta_banco(agente_nome, origem, uf_origem, destino, uf_destino, peso_cubado, valor_nf, df_base):
    """Calcula rota direta usando configuração do banco"""
    try:
        # Buscar linha do agente na base
        linhas_agente = df_base[df_base['Fornecedor'].str.contains(agente_nome, case=False, na=False)]
        if linhas_agente.empty:
            return None
        
        linha = linhas_agente.iloc[0]
        
        # Buscar configuração do agente
        config = ConfiguracaoAgente.query.filter_by(agente_nome=agente_nome, ativa=True).first()
        if not config:
            return None
        
        valores = config.get_valores_customizados()
        formulas = config.get_formulas_customizadas()
        
        # Calcular usando fórmula do banco
        if formulas.get('formula_id'):
            formula = FormulaCalculoFrete.query.get(formulas['formula_id'])
            if formula:
                # Executar fórmula
                exec_globals = {
                    'peso_usado': peso_cubado,
                    'valor_nf': valor_nf,
                    'linha_base': linha.to_dict(),
                    'resultado': 0
                }
                exec(formula.formula, exec_globals)
                valor_base = exec_globals.get('resultado', 0)
                
                # Calcular custos adicionais
                gris = 0
                if valor_nf and not valores.get('sem_gris', False):
                    gris = max((valor_nf * valores.get('gris_percentual', 0) / 100), valores.get('gris_minimo', 0))
                
                pedagio = 0
                if not valores.get('sem_pedagio', False):
                    pedagio = (peso_cubado / 100) * valores.get('pedagio_100kg', 0)
                
                seguro = 0
                if valor_nf and not valores.get('sem_seguro', False):
                    seguro = valor_nf * (valores.get('seguro_percentual', 0) / 100)
                
                total = valor_base + gris + pedagio + seguro
                
                return {
                    'tipo_servico': f"{agente_nome} - Direto",
                    'fornecedor': agente_nome,
                    'custo_total': total,
                    'prazo': 3,
                    'peso_maximo_agente': valores.get('peso_maximo', 'N/A'),
                    'descricao': f"Serviço direto porta-a-porta",
                    'detalhes_expandidos': {
                        'agentes_info': {
                            'agente_coleta': 'N/A',
                            'transferencia': 'N/A',
                            'agente_entrega': 'N/A'
                        },
                        'rota_info': {
                            'origem': origem,
                            'destino': destino,
                            'peso_cubado': peso_cubado,
                            'tipo_peso_usado': 'Cubado'
                        },
                        'custos_detalhados': {
                            'custo_base_frete': valor_base,
                            'custo_coleta': 0,
                            'custo_transferencia': 0,
                            'custo_entrega': 0,
                            'pedagio': pedagio,
                            'gris': gris,
                            'seguro': seguro,
                            'icms': 0,
                            'outros': 0
                        },
                        'observacoes': f"Rota direta calculada usando fórmula {formula.nome}"
                    }
                }
        
        return None
        
    except Exception as e:
        print(f"[ROTA_DIRETA] ❌ Erro para {agente_nome}: {e}")
        return None

def calcular_rota_combinada_banco(agente_coleta, agente_transferencia, agente_entrega, origem, uf_origem, destino, uf_destino, peso_cubado, valor_nf, df_base):
    """Calcula rota combinada (agente + transferência + agente) usando banco"""
    try:
        # Calcular cada etapa separadamente
        custo_coleta = calcular_rota_direta_banco(agente_coleta, origem, uf_origem, "Base Intermediária", "BI", peso_cubado, valor_nf, df_base)
        custo_transferencia = calcular_rota_direta_banco(agente_transferencia, "Base Origem", "BO", "Base Destino", "BD", peso_cubado, valor_nf, df_base)
        custo_entrega = calcular_rota_direta_banco(agente_entrega, "Base Intermediária", "BI", destino, uf_destino, peso_cubado, valor_nf, df_base)
        
        if not all([custo_coleta, custo_transferencia, custo_entrega]):
            return None
        
        # Somar custos totais
        custo_total_rota = custo_coleta['custo_total'] + custo_transferencia['custo_total'] + custo_entrega['custo_total']
        
        return {
            'tipo_servico': f"{agente_coleta} (Coleta) + {agente_transferencia} (Transferência) + {agente_entrega} (Entrega)",
            'fornecedor': f"{agente_transferencia}",  # Fornecedor principal
            'custo_total': custo_total_rota,
            'prazo': 3,
            'peso_maximo_agente': min(
                custo_coleta.get('peso_maximo_agente', 1000),
                custo_transferencia.get('peso_maximo_agente', 1000),
                custo_entrega.get('peso_maximo_agente', 1000)
            ),
            'descricao': f"Rota completa com 3 agentes especializados",
            'detalhes_expandidos': {
                'agentes_info': {
                    'agente_coleta': agente_coleta,
                    'transferencia': agente_transferencia,
                    'agente_entrega': agente_entrega,
                    'base_origem': transferencia.get('Base Origem', 'Base de Origem'),
                    'base_destino': transferencia.get('Base Destino', 'Base de Destino')
                },
                'rota_info': {
                    'origem': origem,
                    'destino': destino,
                    'peso_real': peso_cubado / 300 if peso_cubado > 300 else peso_cubado,
                    'cubagem': peso_cubado / 300 if peso_cubado > 300 else 0,
                    'peso_cubado': peso_cubado,
                    'tipo_peso_usado': 'Cubado'
                },
                'custos_detalhados': {
                    'custo_base_frete': custo_coleta['custo_total'] + custo_transferencia['custo_total'] + custo_entrega['custo_total'],
                    'custo_coleta': custo_coleta['custo_total'],
                    'custo_transferencia': custo_transferencia['custo_total'],
                    'custo_entrega': custo_entrega['custo_total'],
                    'pedagio': 0,
                    'gris': 0,
                    'seguro': 0,
                    'icms': 0,
                    'outros': 0
                },
                'observacoes': f"Rota combinada automática: {agente_coleta} → {agente_transferencia} → {agente_entrega}. Peso: {peso_cubado}kg"
            }
        }
        
    except Exception as e:
        print(f"[ROTA_COMBINADA] ❌ Erro: {e}")
        return None

def criar_rota_direta_original(agente_linha, origem, destino, peso_cubado, valor_nf):
    """Cria rota direta como no código original"""
    try:
        fornecedor = agente_linha.get('Fornecedor', 'N/A')
        
        # Calcular custo usando lógica original do calcular_custo_agente
        custo_resultado = calcular_custo_agente_original(agente_linha, peso_cubado, valor_nf)
        
        if not custo_resultado:
            return None
        
        return {
            'tipo_servico': f"{fornecedor} - Direto",
            'fornecedor': fornecedor,
            'custo_total': custo_resultado['total'],
            'prazo': custo_resultado.get('prazo', 3),
            'peso_maximo_agente': custo_resultado.get('peso_maximo', 'N/A'),
            'descricao': f"Serviço direto porta-a-porta",
            'detalhes_expandidos': {
                'agentes_info': {
                    'agente_coleta': 'N/A',
                    'transferencia': 'N/A',
                    'agente_entrega': 'N/A'
                },
                'rota_info': {
                    'origem': origem,
                    'destino': destino,
                    'peso_cubado': peso_cubado,
                    'tipo_peso_usado': 'Cubado'
                },
                'custos_detalhados': {
                    'custo_base_frete': custo_resultado['custo_base'],
                    'custo_coleta': 0,
                    'custo_transferencia': 0,
                    'custo_entrega': 0,
                    'pedagio': custo_resultado['pedagio'],
                    'gris': custo_resultado['gris'],
                    'seguro': custo_resultado.get('seguro', 0),
                    'icms': 0,
                    'outros': 0
                },
                'observacoes': f"Rota direta original: {fornecedor}"
            }
        }
        
    except Exception as e:
        print(f"[ROTA_DIRETA_ORIG] ❌ Erro: {e}")
        return None

def criar_rota_transferencia_direta_original(transferencia_linha, origem, destino, peso_cubado, valor_nf):
    """Cria rota de transferência direta como no código original"""
    try:
        fornecedor = transferencia_linha.get('Fornecedor', 'N/A')
        
        # Calcular custo usando lógica original
        custo_resultado = calcular_custo_agente_original(transferencia_linha, peso_cubado, valor_nf)
        
        if not custo_resultado:
            return None
        
        return {
            'tipo_servico': f"{fornecedor} - Transferência",
            'fornecedor': fornecedor,
            'custo_total': custo_resultado['total'],
            'prazo': custo_resultado.get('prazo', 3),
            'peso_maximo_agente': custo_resultado.get('peso_maximo', 'N/A'),
            'descricao': f"Transferência direta",
            'detalhes_expandidos': {
                'agentes_info': {
                    'agente_coleta': 'N/A',
                    'transferencia': fornecedor,
                    'agente_entrega': 'N/A',
                    'base_origem': transferencia_linha.get('Base Origem', 'Base de Origem'),
                    'base_destino': transferencia_linha.get('Base Destino', 'Base de Destino')
                },
                'rota_info': {
                    'origem': origem,
                    'destino': destino,
                    'peso_cubado': peso_cubado,
                    'tipo_peso_usado': 'Cubado'
                },
                'custos_detalhados': {
                    'custo_base_frete': custo_resultado['custo_base'],
                    'custo_coleta': 0,
                    'custo_transferencia': custo_resultado['total'],
                    'custo_entrega': 0,
                    'pedagio': custo_resultado['pedagio'],
                    'gris': custo_resultado['gris'],
                    'seguro': custo_resultado.get('seguro', 0),
                    'icms': 0,
                    'outros': 0
                },
                'observacoes': f"Transferência direta original: {fornecedor}"
            }
        }
        
    except Exception as e:
        print(f"[TRANSFERENCIA_ORIG] ❌ Erro: {e}")
        return None

def criar_rota_combinada_original(agente_col, transferencia, agente_ent, origem, destino, peso_cubado, valor_nf):
    """Cria rota combinada como no código original"""
    try:
        # Calcular cada etapa usando lógica original
        custo_coleta = calcular_custo_agente_original(agente_col, peso_cubado, valor_nf)
        custo_transferencia = calcular_custo_agente_original(transferencia, peso_cubado, valor_nf)
        custo_entrega = calcular_custo_agente_original(agente_ent, peso_cubado, valor_nf)
        
        if not all([custo_coleta, custo_transferencia, custo_entrega]):
            return None
        
        # Somar custos totais (como no original)
        total = custo_coleta['total'] + custo_transferencia['total'] + custo_entrega['total']
        prazo_total = max(custo_coleta.get('prazo', 1), custo_transferencia.get('prazo', 1), custo_entrega.get('prazo', 1))
        
        fornecedor_col = agente_col.get('Fornecedor', 'N/A')
        fornecedor_transf = transferencia.get('Fornecedor', 'N/A')
        fornecedor_ent = agente_ent.get('Fornecedor', 'N/A')
        
        return {
            'tipo_servico': f"{fornecedor_col} (Coleta) + {fornecedor_transf} (Transferência) + {fornecedor_ent} (Entrega)",
            'fornecedor': f"{fornecedor_transf}",  # Fornecedor principal
            'custo_total': total,
            'prazo': prazo_total,
            'peso_maximo_agente': min(
                custo_coleta.get('peso_maximo', 1000) or 1000,
                custo_transferencia.get('peso_maximo', 1000) or 1000,
                custo_entrega.get('peso_maximo', 1000) or 1000
            ),
            'descricao': f"Rota completa com 3 agentes especializados",
            'detalhes_expandidos': {
                'agentes_info': {
                    'agente_coleta': fornecedor_col,
                    'transferencia': fornecedor_transf,
                    'agente_entrega': fornecedor_ent,
                    'base_origem': transferencia.get('Base Origem', 'Osasco/SP'),
                    'base_destino': transferencia.get('Base Destino', 'Amparo/SP')
                },
                'rota_info': {
                    'origem': origem,
                    'destino': destino,
                    'peso_real': peso_cubado / 300 if peso_cubado > 300 else peso_cubado,
                    'cubagem': peso_cubado / 300 if peso_cubado > 300 else 0,
                    'peso_cubado': peso_cubado,
                    'tipo_peso_usado': 'Cubado'
                },
                'custos_detalhados': {
                    'custo_base_frete': custo_coleta['custo_base'] + custo_transferencia['custo_base'] + custo_entrega['custo_base'],
                    'custo_coleta': custo_coleta['total'],
                    'custo_transferencia': custo_transferencia['total'],
                    'custo_entrega': custo_entrega['total'],
                    'pedagio': custo_coleta['pedagio'] + custo_transferencia['pedagio'] + custo_entrega['pedagio'],
                    'gris': custo_coleta['gris'] + custo_transferencia['gris'] + custo_entrega['gris'],
                    'seguro': custo_coleta.get('seguro', 0) + custo_transferencia.get('seguro', 0) + custo_entrega.get('seguro', 0),
                    'icms': 0,
                    'outros': 0
                },
                'observacoes': f"Rota combinada original: {fornecedor_col} → {fornecedor_transf} → {fornecedor_ent}. Peso: {peso_cubado}kg"
            }
        }
        
    except Exception as e:
        print(f"[ROTA_COMBINADA_ORIG] ❌ Erro: {e}")
        return None

def calcular_custo_agente_original(linha, peso_cubado, valor_nf):
    """Calcula custo baseado apenas nos dados da base unificada - SEM LÓGICAS HARDCODED"""
    try:
        fornecedor = linha.get('Fornecedor', 'N/A')
        prazo_raw = linha.get('Prazo', 1)
        prazo = int(prazo_raw) if prazo_raw and str(prazo_raw).isdigit() else 1
        
        # Peso máximo
        peso_maximo = None
        if 'PESO MÁXIMO TRANSPORTADO' in linha and pd.notna(linha.get('PESO MÁXIMO TRANSPORTADO')):
            try:
                peso_maximo = float(linha.get('PESO MÁXIMO TRANSPORTADO', 0))
            except:
                pass
        
        # Usar apenas lógica de transferência padrão baseada nos dados da base
        custo_base = calcular_transferencia_padrao(linha, peso_cubado)
        
        if custo_base <= 0:
            return None
        
        # Calcular custos adicionais baseados apenas nos dados da base
        gris = 0
        if valor_nf and linha.get('Gris Exc'):
            gris_perc = float(linha.get('Gris Exc', 0))
            gris_min = float(linha.get('Gris Min', 0))
            gris = max((valor_nf * gris_perc / 100), gris_min)
        
        pedagio = 0
        if linha.get('Pedagio (100 Kg)'):
            pedagio = (peso_cubado / 100) * float(linha.get('Pedagio (100 Kg)', 0))
        
        seguro = 0
        if valor_nf and linha.get('Seguro'):
            seguro = valor_nf * (float(linha.get('Seguro', 0)) / 100)
        
        total = custo_base + gris + pedagio + seguro
        
        return {
            'fornecedor': fornecedor,
            'custo_base': custo_base,
            'gris': gris,
            'pedagio': pedagio,
            'seguro': seguro,
            'total': total,
            'prazo': prazo,
            'peso_maximo': peso_maximo
        }
        
    except Exception as e:
        print(f"[CUSTO_BASE] ❌ Erro para {linha.get('Fornecedor', 'N/A')}: {e}")
        return None

def calcular_transferencia_padrao(linha, peso_cubado):
    """Implementa a lógica de transferência padrão do código original"""
    try:
        peso_calculo = float(peso_cubado)
        
        # 1) Valor mínimo até 10kg
        valor_minimo = linha.get('VALOR MÍNIMO ATÉ 10')
        if peso_calculo <= 10 and valor_minimo and float(valor_minimo) > 0:
            return float(valor_minimo)
        
        # 2) Seleção de faixa por peso
        faixas_kg = [20, 30, 50, 70, 100, 150, 200, 300, 500]
        
        for faixa in faixas_kg:
            if peso_calculo <= float(faixa):
                valor_faixa = linha.get(str(faixa), 0)
                if valor_faixa and float(valor_faixa) > 0:
                    return peso_calculo * float(valor_faixa)
        
        # 3) Acima de 500kg
        for col_acima in ['Acima 500', 'Acima 1000', 'Acima 2000']:
            valor_acima = linha.get(col_acima)
            if valor_acima and float(valor_acima) > 0:
                return peso_calculo * float(valor_acima)
        
        # 4) Fallback: usar valor mínimo se disponível
        if valor_minimo and float(valor_minimo) > 0:
            return float(valor_minimo)
        
        return 0.0
        
    except Exception as e:
        print(f"[TRANSF_PADRAO] ❌ Erro: {e}")
        return 0.0

def calcular_com_configuracao_banco(agente_nome, linha_base, peso_cubado, valor_nf):
    """Calcula usando configurações do banco de dados - SEM LÓGICA HARDCODED"""
    try:
        # Buscar agente no banco
        agente = AgenteTransportadora.query.filter_by(nome=agente_nome, ativo=True).first()
        if not agente:
            print(f"[AGENTE] ❌ Agente {agente_nome} não encontrado no banco")
            return None
        
        # Buscar memória de cálculo ativa para este agente
        memoria = MemoriaCalculoAgente.query.filter_by(
            agente_id=agente.id, 
            ativo=True
        ).order_by(MemoriaCalculoAgente.prioridade.desc()).first()
        
        if not memoria:
            print(f"[AGENTE] ⚠️ Nenhuma memória de cálculo encontrada para {agente_nome}")
            return None
        
        # Aplicar lógica baseada no tipo de memória
        config = memoria.get_configuracao_memoria()
        tipo_memoria = memoria.tipo_memoria
        
        valor_base = 0.0
        
        if tipo_memoria == 'valor_fixo_faixa':
            # Lógica: usar valor fixo de uma faixa específica
            faixa_especifica = config.get('faixa_especifica', '50')
            valor_base = float(linha_base.get(faixa_especifica, 0))
            
        elif tipo_memoria == 'valor_por_kg':
            # Lógica: multiplicar peso por valor por kg
            valor_por_kg = config.get('valor_por_kg', 0)
            valor_base = peso_cubado * valor_por_kg
            
        elif tipo_memoria == 'tabela_especifica':
            # Lógica: usar tabela de faixas como no código original
            valor_base = calcular_com_tabela_faixas(linha_base, peso_cubado, config)
            
        elif tipo_memoria == 'formula_customizada':
            # Lógica: usar fórmula customizada
            formula = config.get('formula', '')
            valor_base = executar_formula_customizada(formula, linha_base, peso_cubado, valor_nf)
            
        else:
            # Fallback: usar valor mínimo se disponível
            valor_minimo = linha_base.get('VALOR MÍNIMO ATÉ 10', 0)
            if valor_minimo and float(valor_minimo) > 0:
                valor_base = float(valor_minimo)
        
        if valor_base <= 0:
            print(f"[AGENTE] ❌ Valor base zero para {agente_nome}")
            return None
        
        # Calcular custos adicionais baseados na configuração do agente
        gris = 0
        if agente.gris_percentual > 0 and valor_nf:
            gris = max((valor_nf * agente.gris_percentual / 100), agente.gris_minimo)
        
        pedagio = 0
        if agente.calcula_pedagio and agente.pedagio_por_bloco > 0:
            pedagio = agente.pedagio_por_bloco
        
        seguro = 0
        if agente.calcula_seguro and valor_nf:
            seguro = valor_nf * 0.002  # 0.2% padrão
        
        total = valor_base + gris + pedagio + seguro
        
        return {
            'agente': agente_nome,
            'tipo_agente': agente.tipo_agente,
            'valor_base': valor_base,
            'gris': gris,
            'pedagio': pedagio,
            'seguro': seguro,
            'total': total,
            'peso_maximo': agente.get_parametros_calculo().get('peso_maximo', 1000),
            'volume_maximo': agente.get_parametros_calculo().get('volume_maximo', 100),
            'memoria_usada': memoria.nome_memoria
        }
        
    except Exception as e:
        print(f"[AGENTE] ❌ Erro no cálculo com configuração para {agente_nome}: {e}")
        return None

def calcular_com_tabela_faixas(linha_base, peso_cubado, config):
    """Calcula usando tabela de faixas baseada na configuração"""
    try:
        peso_calculo = float(peso_cubado)
        
        # Verificar se deve usar valor mínimo
        usar_valor_minimo = config.get('usar_valor_minimo', True)
        if usar_valor_minimo:
            valor_minimo = linha_base.get('VALOR MÍNIMO ATÉ 10')
            if peso_calculo <= 10 and valor_minimo and float(valor_minimo) > 0:
                return float(valor_minimo)
        
        # Usar faixas configuradas ou padrão
        faixas_config = config.get('faixas', [20, 30, 50, 70, 100, 150, 200, 300, 500])
        
        for faixa in faixas_config:
            if peso_calculo <= float(faixa):
                valor_faixa = linha_base.get(str(faixa), 0)
                if valor_faixa and float(valor_faixa) > 0:
                    return peso_calculo * float(valor_faixa)
        
        # Fallback: usar valor mínimo se disponível
        valor_minimo = linha_base.get('VALOR MÍNIMO ATÉ 10')
        if valor_minimo and float(valor_minimo) > 0:
            return float(valor_minimo)
        
        return 0.0
        
    except Exception as e:
        print(f"[TABELA_FAIXAS] ❌ Erro: {e}")
        return 0.0

def executar_formula_customizada(formula, linha_base, peso_cubado, valor_nf):
    """Executa fórmula customizada"""
    try:
        # Variáveis disponíveis para a fórmula
        exec_globals = {
            'peso_cubado': peso_cubado,
            'valor_nf': valor_nf or 0,
            'linha_base': linha_base,
            'resultado': 0
        }
        
        exec(formula, exec_globals)
        return exec_globals.get('resultado', 0)
        
    except Exception as e:
        print(f"[FORMULA] ❌ Erro executando fórmula: {e}")
        return 0.0



def calcular_frete_fracionado_base_unificada(origem, uf_origem, destino, uf_destino, peso, cubagem, valor_nf=None):
    """Função restaurada que estava funcionando - INTEGRADA COM BANCO"""
    try:
        print(f"[FRACIONADO] 📦 Calculando: {origem}/{uf_origem} → {destino}/{uf_destino}")
        print(f"[FRACIONADO] Peso: {peso}kg, Cubagem: {cubagem}m³")
        
        # Carregar base unificada
        df_base = carregar_base_unificada()
        if df_base is None or df_base.empty:
            return {'sem_opcoes': True, 'erro': 'Base de dados não disponível'}
        
        # Carregar agentes e memórias do banco
        agentes_dict = carregar_agentes_e_memorias()
        
        # Normalizar nomes
        origem_norm = origem.strip().title()
        destino_norm = destino.strip().title()
        
        # Filtrar dados da base
        df_filtrado = df_base[
            (df_base['Origem'].str.contains(origem_norm, case=False, na=False)) &
            (df_base['Destino'].str.contains(destino_norm, case=False, na=False))
        ]
        
        if df_filtrado.empty:
            return {'sem_opcoes': True, 'erro': 'Nenhuma rota encontrada'}
        
        # Calcular peso cubado
        peso_cubado = max(peso, cubagem * 250) if cubagem else peso
        
        resultados = []
        resultados_detalhados = []  # Para o ranking com detalhes
        
        # Verificar se há agentes no banco
        if not agentes_dict:
            print(f"[FRACIONADO] ⚠️ Nenhum agente no banco - use /admin/calculadoras para configurar")
            return {'sem_opcoes': True, 'erro': 'Sistema não configurado. Execute o setup na interface admin.'}
        
        # Calcular rotas automáticas baseadas nas configurações do banco
        rotas_automaticas = calcular_rotas_automaticas_banco(origem, uf_origem, destino, uf_destino, peso_cubado, valor_nf, df_base)
        if rotas_automaticas:
            resultados_detalhados.extend(rotas_automaticas)
            print(f"[FRACIONADO] 🤖 {len(rotas_automaticas)} rotas automáticas do banco adicionadas")
        
        print(f"[FRACIONADO] 🔗 Processando rotas com {len(agentes_dict)} agentes do banco")
        
        # Processar cada linha para rotas diretas - EVITAR DUPLICATAS
        fornecedores_processados = set()  # Para evitar duplicatas
        
        for idx, linha in df_filtrado.iterrows():
            try:
                fornecedor = linha.get('Fornecedor', 'N/A')
                
                # Evitar duplicatas
                if fornecedor in fornecedores_processados:
                    continue
                fornecedores_processados.add(fornecedor)
                
                # Verificar se o fornecedor é um agente no banco de dados
                if fornecedor in agentes_dict:
                    print(f"[FRACIONADO] 🎯 Usando agente do banco: {fornecedor}")
                    calculo_agente = calcular_com_configuracao_banco(fornecedor, linha, peso_cubado, valor_nf)
                    
                    if calculo_agente:
                        # Resultado para compatibilidade
                        resultado = {
                            'fornecedor': fornecedor,
                            'tipo_servico': f"{calculo_agente['tipo_agente']} - {fornecedor}",
                            'custo_base': calculo_agente['valor_base'],
                            'gris': calculo_agente['gris'],
                            'pedagio': calculo_agente['pedagio'],
                            'seguro': calculo_agente['seguro'],
                            'total': calculo_agente['total'],
                            'peso_usado': f"{peso_cubado}kg",
                            'prazo': 3,
                            'eh_melhor_opcao': False
                        }
                        resultados.append(resultado)
                        
                        # Resultado detalhado para ranking
                        resultado_detalhado = {
                            'tipo_servico': f"{calculo_agente['tipo_agente']} - {fornecedor}",
                            'fornecedor': fornecedor,
                            'custo_total': calculo_agente['total'],
                            'prazo': 3,
                            'peso_maximo_agente': calculo_agente['peso_maximo'],
                            'descricao': f"Serviço {calculo_agente['tipo_agente']} com memória de cálculo: {calculo_agente['memoria_usada']}",
                            'detalhes_expandidos': {
                                'agentes_info': {
                                    'agente_coleta': fornecedor if calculo_agente['tipo_agente'] == 'agente_coleta' else 'N/A',
                                    'transferencia': fornecedor if calculo_agente['tipo_agente'] == 'transferencia' else 'N/A',
                                    'agente_entrega': fornecedor if calculo_agente['tipo_agente'] == 'agente_entrega' else 'N/A',
                                    'base_origem': linha.get('Base Origem', 'Base de Origem'),
                                    'base_destino': linha.get('Base Destino', 'Base de Destino')
                                },
                                'rota_info': {
                                    'origem': origem,
                                    'destino': destino,
                                    'peso_real': peso,
                                    'cubagem': cubagem,
                                    'peso_cubado': peso_cubado,
                                    'tipo_peso_usado': 'Cubado' if peso_cubado > peso else 'Real'
                                },
                                'custos_detalhados': {
                                    'custo_base_frete': calculo_agente['valor_base'],
                                    'custo_coleta': calculo_agente['valor_base'] * 0.3 if calculo_agente['tipo_agente'] == 'agente_coleta' else 0,
                                    'custo_transferencia': calculo_agente['valor_base'] * 0.5 if calculo_agente['tipo_agente'] == 'transferencia' else 0,
                                    'custo_entrega': calculo_agente['valor_base'] * 0.2 if calculo_agente['tipo_agente'] == 'agente_entrega' else 0,
                                    'pedagio': calculo_agente['pedagio'],
                                    'gris': calculo_agente['gris'],
                                    'seguro': calculo_agente['seguro'],
                                    'icms': 0,
                                    'outros': 0
                                },
                                'observacoes': f"Cálculo usando memória de agente do banco de dados: {calculo_agente['memoria_usada']}. Peso máximo: {calculo_agente['peso_maximo']}kg"
                            }
                        }
                        resultados_detalhados.append(resultado_detalhado)
                        continue
                
                # Fallback para cálculo tradicional se não estiver no banco
                print(f"[FRACIONADO] 📊 Cálculo tradicional para: {fornecedor}")
                
                # Obter valor por peso (cálculo tradicional)
                valor_base = None
                if peso_cubado <= 10 and linha.get('VALOR MÍNIMO ATÉ 10'):
                    valor_base = float(linha.get('VALOR MÍNIMO ATÉ 10', 0))
                elif peso_cubado <= 20 and linha.get('20'):
                    valor_base = float(linha.get('20', 0)) * peso_cubado
                elif peso_cubado <= 30 and linha.get('30'):
                    valor_base = float(linha.get('30', 0)) * peso_cubado
                elif peso_cubado <= 50 and linha.get('50'):
                    valor_base = float(linha.get('50', 0)) * peso_cubado
                elif peso_cubado <= 70 and linha.get('70'):
                    valor_base = float(linha.get('70', 0)) * peso_cubado
                elif peso_cubado <= 100 and linha.get('100'):
                    valor_base = float(linha.get('100', 0)) * peso_cubado
                elif peso_cubado <= 150 and linha.get('150'):
                    valor_base = float(linha.get('150', 0)) * peso_cubado
                elif peso_cubado <= 200 and linha.get('200'):
                    valor_base = float(linha.get('200', 0)) * peso_cubado
                elif peso_cubado <= 300 and linha.get('300'):
                    valor_base = float(linha.get('300', 0)) * peso_cubado
                elif peso_cubado <= 500 and linha.get('500'):
                    valor_base = float(linha.get('500', 0)) * peso_cubado
                else:
                    valor_base = float(linha.get('Acima 500', 0)) * peso_cubado
                
                if not valor_base or valor_base <= 0:
                    continue
                
                # Calcular custos adicionais
                gris = 0
                if valor_nf and linha.get('Gris Exc'):
                    gris_perc = float(linha.get('Gris Exc', 0))
                    gris_min = float(linha.get('Gris Min', 0))
                    gris = max((valor_nf * gris_perc / 100), gris_min)
                
                pedagio = 0
                if linha.get('Pedagio (100 Kg)'):
                    pedagio = (peso_cubado / 100) * float(linha.get('Pedagio (100 Kg)', 0))
                
                seguro = 0
                if valor_nf and linha.get('Seguro'):
                    seguro = valor_nf * (float(linha.get('Seguro', 0)) / 100)
                
                total = valor_base + gris + pedagio + seguro
                
                resultado = {
                    'fornecedor': fornecedor,
                    'tipo_servico': f"{linha.get('Tipo', 'Fracionado')} - {fornecedor}",
                    'custo_base': valor_base,
                    'gris': gris,
                    'pedagio': pedagio,
                    'seguro': seguro,
                    'total': total,
                    'peso_usado': f"{peso_cubado}kg",
                    'prazo': 3,
                    'eh_melhor_opcao': False
                }
                
                resultados.append(resultado)
                
            except Exception as e:
                print(f"[FRACIONADO] Erro processando {linha.get('Fornecedor', 'N/A')}: {e}")
                continue
        
        # Ordenar por preço
        resultados.sort(key=lambda x: x.get('total', float('inf')))
        
        # Marcar melhor opção
        if resultados:
            resultados[0]['eh_melhor_opcao'] = True
        
        print(f"[FRACIONADO] ✅ {len(resultados)} opções encontradas")
        
        # Criar estrutura de ranking detalhada como o JavaScript original espera
        ranking_data = {
            'id_calculo': f"FRAC_{origem}_{destino}_{int(time.time())}",
            'origem': f"{origem}/{uf_origem}",
            'destino': f"{destino}/{uf_destino}",
            'peso': peso,
            'cubagem': cubagem,
            'peso_cubado': f"{peso_cubado}kg",
            'peso_usado_tipo': 'Cubado' if peso_cubado > peso else 'Real',
            'valor_nf': valor_nf,
            'melhor_opcao': resultados[0] if resultados else None,
            'ranking_opcoes': []
        }
        
        # Usar resultados detalhados se disponíveis, senão converter resultados básicos
        if resultados_detalhados:
            # Ordenar todos os resultados detalhados por custo total
            resultados_detalhados.sort(key=lambda x: x.get('custo_total', float('inf')))
            ranking_data['ranking_opcoes'] = resultados_detalhados
            print(f"[FRACIONADO] 🎯 Usando {len(resultados_detalhados)} resultados detalhados do banco (incluindo rotas combinadas)")
        else:
            # Converter resultados tradicionais para formato de ranking
            for idx, resultado in enumerate(resultados):
                opcao_ranking = {
                    'tipo_servico': resultado['tipo_servico'],
                    'fornecedor': resultado['fornecedor'],
                    'custo_total': resultado['total'],
                    'prazo': resultado.get('prazo', 3),
                    'peso_maximo_agente': 'N/A',
                    'descricao': f"Serviço {resultado['tipo_servico']}",
                    'detalhes_expandidos': {
                        'agentes_info': {
                            'agente_coleta': 'N/A',
                            'transferencia': resultado['fornecedor'],
                            'agente_entrega': 'N/A',
                            'base_origem': 'Base de Origem',
                            'base_destino': 'Base de Destino'
                        },
                        'rota_info': {
                            'origem': origem,
                            'destino': destino,
                            'peso_real': peso,
                            'cubagem': cubagem,
                            'peso_cubado': peso_cubado,
                            'tipo_peso_usado': 'Cubado' if peso_cubado > peso else 'Real'
                        },
                        'custos_detalhados': {
                            'custo_base_frete': resultado['custo_base'],
                            'custo_coleta': resultado['custo_base'] * 0.3,
                            'custo_transferencia': resultado['custo_base'] * 0.5,
                            'custo_entrega': resultado['custo_base'] * 0.2,
                            'pedagio': resultado['pedagio'],
                            'gris': resultado['gris'],
                            'seguro': resultado['seguro'],
                            'icms': 0,
                            'outros': 0
                        },
                        'observacoes': f"Cálculo baseado em peso cubado de {peso_cubado}kg"
                    }
                }
                ranking_data['ranking_opcoes'].append(opcao_ranking)
            print(f"[FRACIONADO] 📊 Usando {len(resultados)} resultados tradicionais")
        
        return {
            'sem_opcoes': len(resultados) == 0,
            'opcoes': resultados,  # Manter para compatibilidade
            'ranking_fracionado': ranking_data,  # Novo formato detalhado
            'total_opcoes': len(resultados),
            'origem': origem,
            'destino': destino
        }
        
    except Exception as e:
        print(f"[FRACIONADO] ❌ Erro: {e}")
        return {'sem_opcoes': True, 'erro': str(e)}

def calcular_com_agente_banco(agente, linha_base, peso_usado, valor_nf):
    """Calcula usando configurações do banco"""
    try:
        # Buscar memória ativa
        memoria = MemoriaCalculoAgente.query.filter_by(
            agente_id=agente.id, 
            ativo=True
        ).first()
        
        if not memoria:
            return calcular_generico_base(linha_base, peso_usado, valor_nf)
        
        # Aplicar memória
        dados = {
            'peso_usado': peso_usado,
            'valor_nf': valor_nf or 0,
            'fornecedor': agente.nome
        }
        
        resultado_memoria = memoria.aplicar_memoria_calculo(dados)
        if not resultado_memoria:
            return calcular_generico_base(linha_base, peso_usado, valor_nf)
        
        valor_base = resultado_memoria.get('valor_base', 0)
        
        # Calcular custos usando configurações do agente
        gris = 0
        if agente.gris_percentual > 0 and valor_nf:
            gris = max((valor_nf * agente.gris_percentual / 100), agente.gris_minimo)
        
        pedagio = agente.pedagio_por_bloco if agente.calcula_pedagio else 0
        seguro = (valor_nf * 0.002) if agente.calcula_seguro and valor_nf else 0
        
        total = valor_base + gris + pedagio + seguro
        
        return {
            'fornecedor': agente.nome,
            'tipo_servico': f"{linha_base.tipo} - {agente.nome}",
            'custo_base': valor_base,
            'gris': gris,
            'pedagio': pedagio,
            'seguro': seguro,
            'total': total,
            'peso_usado': f"{peso_usado}kg",
            'prazo': 3,
            'eh_melhor_opcao': False,
            'sistema': 'banco_configurado'
        }
        
    except Exception as e:
        print(f"[AGENTE BANCO] Erro: {e}")
        return None

def calcular_generico_base(linha_base, peso_usado, valor_nf):
    """Cálculo genérico usando valores da base"""
    try:
        valor_base = linha_base.get_valor_por_peso(peso_usado)
        if not valor_base:
            return None
        
        # Custos genéricos
        gris = float(linha_base.gris_exc or 0) if linha_base.gris_exc else 0
        pedagio = float(linha_base.pedagio_100kg or 0) if linha_base.pedagio_100kg else 0
        seguro = (valor_nf * 0.002) if valor_nf else 0
        
        total = valor_base + gris + pedagio + seguro
        
        return {
            'fornecedor': linha_base.fornecedor,
            'tipo_servico': f"{linha_base.tipo} - Genérico",
            'custo_base': valor_base,
            'gris': gris,
            'pedagio': pedagio,
            'seguro': seguro,
            'total': total,
            'peso_usado': f"{peso_usado}kg",
            'prazo': 3,
            'eh_melhor_opcao': False,
            'sistema': 'generico_base'
        }
        
    except Exception as e:
        print(f"[GENERICO] Erro: {e}")
        return None

# ===== ROTAS PRINCIPAIS LIMPAS =====

@app.route('/')
def index():
    """Página principal"""
    usuario_logado = session.get('usuario_logado')
    
    if usuario_logado:
        try:
            # Buscar dados completos do usuário no banco
            usuario_db = Usuario.query.filter_by(nome_usuario=usuario_logado, ativo=True).first()
            
            if usuario_db:
                usuario_dados = {
                    'nome': usuario_db.nome_completo,
                    'nome_usuario': usuario_db.nome_usuario,
                    'tipo': usuario_db.tipo_usuario,
                    'logado': True,
                    'pode_ver_admin': usuario_db.pode_ver_admin or usuario_db.is_admin(),
                    'permissoes': session.get('usuario_permissoes', {})
                }
            else:
                # Usuário não encontrado no banco, limpar sessão
                session.clear()
                usuario_dados = {
                    'nome': 'Visitante',
                    'tipo': 'visitante',
                    'logado': False
                }
            
            log_acesso(usuario_logado, 'ACESSO_HOME', obter_ip_cliente())
        except Exception as e:
            print(f"[INDEX] Erro ao buscar usuário: {e}")
            usuario_dados = {
                'nome': usuario_logado,
                'tipo': 'operador',
                'logado': True,
                'pode_ver_admin': True  # Fallback
            }
    else:
        usuario_dados = {
            'nome': 'Visitante',
            'tipo': 'visitante',
            'logado': False
        }
    
    return render_template('index.html', usuario=usuario_dados)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Sistema de login com banco de dados"""
    if request.method == 'POST':
        nome_usuario = request.form.get('usuario', '').strip()
        senha = request.form.get('senha', '').strip()
        ip_cliente = obter_ip_cliente()
        
        if not nome_usuario or not senha:
            flash('Usuário e senha são obrigatórios')
            return render_template('login.html')
        
        try:
            # Buscar usuário no banco
            usuario = Usuario.query.filter_by(nome_usuario=nome_usuario).first()
            
            if not usuario:
                log_acesso(nome_usuario, 'LOGIN_FALHA_USUARIO_INEXISTENTE', ip_cliente)
                flash('Usuário não encontrado')
                return render_template('login.html')
            
            # Verificar se usuário está bloqueado
            if usuario.is_blocked():
                log_acesso(nome_usuario, 'LOGIN_FALHA_USUARIO_BLOQUEADO', ip_cliente)
                flash('Usuário temporariamente bloqueado. Tente novamente em 30 minutos.')
                return render_template('login.html')
            
            # Verificar se usuário está ativo
            if not usuario.ativo:
                log_acesso(nome_usuario, 'LOGIN_FALHA_USUARIO_INATIVO', ip_cliente)
                flash('Usuário inativo. Contate o administrador.')
                return render_template('login.html')
            
            # Verificar senha
            if usuario.verificar_senha(senha):
                # Login bem-sucedido
                usuario.resetar_tentativas_login()
                usuario.ip_ultimo_login = ip_cliente
                db.session.commit()
                
                # Criar sessão
                session['usuario_logado'] = usuario.nome_usuario
                session['usuario_id'] = usuario.id
                session['usuario_tipo'] = usuario.tipo_usuario
                session['usuario_nome_completo'] = usuario.nome_completo
                session['usuario_permissoes'] = {
                    'pode_calcular_fretes': usuario.pode_calcular_fretes,
                    'pode_ver_admin': usuario.pode_ver_admin,
                    'pode_editar_base': usuario.pode_editar_base,
                    'pode_gerenciar_usuarios': usuario.pode_gerenciar_usuarios,
                    'pode_importar_dados': usuario.pode_importar_dados
                }
                
                log_acesso(nome_usuario, 'LOGIN_SUCESSO', ip_cliente, f'Tipo: {usuario.tipo_usuario}')
                flash(f'Bem-vindo, {usuario.nome_completo}!', 'success')
                return redirect(url_for('index'))
            else:
                # Senha incorreta
                usuario.incrementar_tentativas_login()
                db.session.commit()
                
                log_acesso(nome_usuario, 'LOGIN_FALHA_SENHA_INCORRETA', ip_cliente)
                flash(f'Senha incorreta. Tentativas restantes: {5 - usuario.tentativas_login}')
                return render_template('login.html')
                
        except Exception as e:
            print(f"[LOGIN] Erro: {e}")
            log_acesso(nome_usuario, 'LOGIN_ERRO_SISTEMA', ip_cliente, str(e))
            flash('Erro interno do sistema. Tente novamente.')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    usuario = session.get('usuario_logado', 'DESCONHECIDO')
    session.clear()
    log_acesso(usuario, 'LOGOUT', obter_ip_cliente())
    return redirect(url_for('login'))

# ===== MIDDLEWARES =====

def middleware_admin(f):
    """Middleware específico para administradores"""
    def decorated_function(*args, **kwargs):
        if 'usuario_logado' not in session:
            return redirect(url_for('login'))

        usuario_permissoes = session.get('usuario_permissoes', {})
        if not (usuario_permissoes.get('pode_ver_admin', False) or 
               session.get('usuario_tipo') == 'admin'):
            flash('Acesso negado. Você não tem permissão para acessar esta área.', 'danger')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# ===== ROTA DE SETUP =====

@app.route("/admin/setup-memorias", methods=["POST"])
@middleware_admin
def admin_setup_memorias():
    """Rota para popular banco com memórias de cálculo originais"""
    try:
        popular_banco_com_memorias_originais()
        return jsonify({
            'sucesso': True,
            'mensagem': 'Memórias de cálculo originais salvas no banco com sucesso'
        })
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'mensagem': f'Erro ao salvar memórias: {str(e)}'
        }), 500

@app.route("/admin/setup-base-unificada", methods=["POST"])
@middleware_admin
def admin_setup_base_unificada():
    """Rota para verificar conexão com PostgreSQL"""
    try:
        resultado = conectar_base_postgresql()
        
        if resultado:
            return jsonify({
                'sucesso': True,
                'mensagem': 'Conexão com PostgreSQL estabelecida com sucesso'
            })
        else:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Erro na conexão com PostgreSQL'
            }), 500
            
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'mensagem': f'Erro interno do servidor: {str(e)}'
        }), 500

# ===== ROTAS DE CÁLCULO LIMPAS =====

@app.route("/calcular_frete_fracionado", methods=["POST"])
def calcular_frete_fracionado():
    """Cálculo de frete fracionado restaurado"""
    try:
        data = request.get_json()
        usuario = session.get('usuario_logado', 'DESCONHECIDO')
        
        origem = data.get("municipio_origem")
        uf_origem = data.get("uf_origem")
        destino = data.get("municipio_destino")
        uf_destino = data.get("uf_destino")
        peso = float(data.get("peso", 1))
        cubagem = float(data.get("cubagem", 0.01))
        valor_nf = float(data.get("valor_nf", 0)) if data.get("valor_nf") else None
        
        log_acesso(usuario, 'CALCULO_FRACIONADO', obter_ip_cliente(), 
                  f"{origem}/{uf_origem} → {destino}/{uf_destino}, {peso}kg")
        
        if not all([origem, uf_origem, destino, uf_destino]):
            return jsonify({"error": "Origem e destino são obrigatórios"})
        
        # Usar função restaurada que funcionava
        resultado = calcular_frete_fracionado_base_unificada(origem, uf_origem, destino, uf_destino, 
                                                           peso, cubagem, valor_nf)
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"[FRACIONADO] Erro: {e}")
        return jsonify({"error": str(e)})

@app.route("/calcular", methods=["POST"])
def calcular():
    """Rota principal de cálculo - redireciona para dedicado"""
    print("[CALCULO] Função calcular() iniciada")
    try:
        data = request.get_json()
        print(f"[CALCULO] Dados recebidos: {data}")
        
        if not data:
            print("[CALCULO] ❌ Dados JSON não recebidos")
            return jsonify({"error": "Dados JSON não recebidos"}), 400
        
        usuario = session.get('usuario_logado', 'DESCONHECIDO')
        
        origem = data.get("municipio_origem")
        uf_origem = data.get("uf_origem")
        destino = data.get("municipio_destino")
        uf_destino = data.get("uf_destino")
        peso = float(data.get("peso", 1))
        cubagem = float(data.get("cubagem", 0))
        valor_nf = data.get("valor_nf")
        
        print(f"[CALCULO] Parâmetros extraídos: origem={origem}, uf_origem={uf_origem}, destino={destino}, uf_destino={uf_destino}")
        
        log_acesso(usuario, 'CALCULO_PRINCIPAL', obter_ip_cliente(), 
                  f"Cálculo: {origem}/{uf_origem} -> {destino}/{uf_destino}, Peso: {peso}kg")
        
        if not all([origem, uf_origem, destino, uf_destino]):
            print("[CALCULO] ❌ Parâmetros obrigatórios ausentes")
            return jsonify({"error": "Origem e destino são obrigatórios"}), 400
        
        print("[CALCULO] ✅ Parâmetros válidos, iniciando geocodificação...")
        
        # Geocodificação
        coord_origem = geocode(origem, uf_origem)
        coord_destino = geocode(destino, uf_destino)
        
        print(f"[CALCULO] Coordenadas obtidas: origem={coord_origem}, destino={coord_destino}")
        
        if not coord_origem or not coord_destino:
            print("[CALCULO] ❌ Falha na geocodificação")
            return jsonify({"error": "Não foi possível geocodificar origem ou destino"}), 400
        
        print("[CALCULO] ✅ Geocodificação bem-sucedida, calculando rota...")
        
        # Calcular rota
        rota_info = calcular_distancia_osrm(coord_origem, coord_destino) or \
                    calcular_distancia_reta(coord_origem, coord_destino)
        
        print(f"[CALCULO] Informações da rota: {rota_info}")
        
        if not rota_info:
            print("[CALCULO] ❌ Falha no cálculo da rota")
            return jsonify({"error": "Não foi possível calcular a rota"}), 400
        
        print("[CALCULO] ✅ Rota calculada, calculando custos...")
        
        # Calcular pedágio real
        analise_preliminar = gerar_analise_trajeto(coord_origem, coord_destino, rota_info, {}, "Dedicado", origem, uf_origem, destino, uf_destino)
        pedagio_real = analise_preliminar.get('pedagio_real', 0)
        
        # Calcular custos
        custos = calcular_custos_dedicado(uf_origem, origem, uf_destino, destino, rota_info["distancia"], pedagio_real)
        
        print(f"[CALCULO] Custos calculados: {custos}")
        
        # Gerar análise final
        analise = gerar_analise_trajeto(coord_origem, coord_destino, rota_info, custos, "Dedicado", origem, uf_origem, destino, uf_destino)
        
        # Gerar ranking
        ranking_dedicado = gerar_ranking_dedicado(custos, analise, rota_info, peso, cubagem, valor_nf)
        
        print(f"[CALCULO] Ranking gerado: {ranking_dedicado}")
        
        # Preparar rota para mapa
        rota_pontos = rota_info.get("rota_pontos", [])
        if not isinstance(rota_pontos, list) or len(rota_pontos) == 0:
            rota_pontos = [coord_origem, coord_destino]
        
        for i, pt in enumerate(rota_pontos):
            if not isinstance(pt, list) or len(pt) < 2:
                rota_pontos[i] = [0, 0]
        
        # Resposta completa
        resposta = {
            "tipo": "Dedicado",
            "distancia": rota_info["distancia"],
            "duracao": rota_info["duracao"],
            "custos": custos,
            "rota_pontos": rota_pontos,
            "analise": {
                "tempo_estimado": analise["tempo_estimado"],
                "consumo_combustivel": analise["consumo_combustivel"],
                "emissao_co2": analise["emissao_co2"],
                "pedagio_estimado": analise["pedagio_estimado"],
                "pedagio_real": analise.get("pedagio_real", 0),
                "pedagio_detalhes": analise.get("pedagio_detalhes"),
                "origem": analise["origem"],
                "destino": analise["destino"],
                "distancia": analise["distancia"],
                "duracao_minutos": analise["duracao_minutos"],
                "provider": analise["provider"],
                "data_hora": analise["data_hora"],
                "rota_pontos": rota_pontos,
                "id_historico": analise["id_historico"],
                "tipo": "Dedicado",
                "custos": custos
            },
            "ranking_dedicado": ranking_dedicado,
            "melhor_opcao": ranking_dedicado['melhor_opcao'] if ranking_dedicado else None,
            "total_opcoes": ranking_dedicado['total_opcoes'] if ranking_dedicado else len(custos)
        }
        
        print(f"[CALCULO] ✅ Resposta preparada: {resposta}")
        return jsonify(resposta)
        
    except Exception as e:
        print(f"[CALCULO] ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erro ao calcular frete dedicado: {str(e)}"}), 500

def geocode(municipio, uf):
    """Geocodifica município e UF para coordenadas"""
    try:
        if not municipio or not uf:
            print(f"[GEOCODE] Dados inválidos: municipio='{municipio}', uf='{uf}'")
            return None
            
        query = f"{municipio}, {uf}, Brasil"
        url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1"
        
        print(f"[GEOCODE] Buscando: {query}")
        print(f"[GEOCODE] URL: {url}")
        
        response = requests.get(url, timeout=10)
        print(f"[GEOCODE] Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"[GEOCODE] Resposta: {data}")
            
            if data and len(data) > 0:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                resultado = [lat, lon, f"{municipio} - {uf}"]
                print(f"[GEOCODE] Sucesso: {resultado}")
                return resultado
            else:
                print(f"[GEOCODE] Nenhum resultado encontrado para: {query}")
        else:
            print(f"[GEOCODE] Erro HTTP: {response.status_code}")
            
        # Fallback: coordenadas aproximadas dos estados brasileiros
        coordenadas_estados = {
            'AC': [-8.77, -70.55], 'AL': [-9.71, -35.73], 'AP': [0.90, -52.00], 'AM': [-3.42, -65.73],
            'BA': [-12.97, -38.50], 'CE': [-3.72, -38.54], 'DF': [-15.78, -47.92], 'ES': [-20.31, -40.31],
            'GO': [-16.64, -49.25], 'MA': [-2.53, -44.30], 'MT': [-15.60, -56.10], 'MS': [-20.44, -54.64],
            'MG': [-19.92, -43.93], 'PA': [-1.45, -48.50], 'PB': [-7.12, -34.88], 'PR': [-25.42, -49.27],
            'PE': [-8.05, -34.88], 'PI': [-5.09, -42.80], 'RJ': [-22.91, -43.20], 'RN': [-5.79, -35.21],
            'RS': [-30.03, -51.23], 'RO': [-8.76, -63.90], 'RR': [2.82, -60.67], 'SC': [-27.59, -48.55],
            'SP': [-23.55, -46.64], 'SE': [-10.90, -37.07], 'TO': [-10.17, -48.33]
        }
        
        if uf in coordenadas_estados:
            lat, lon = coordenadas_estados[uf]
            resultado = [lat, lon, f"{municipio} - {uf}"]
            print(f"[GEOCODE] Fallback para {uf}: {resultado}")
            return resultado
            
        return None
    except Exception as e:
        print(f"[GEOCODE] Erro: {e}")
        import traceback
        traceback.print_exc()
        return None

def calcular_distancia_osrm(origem, destino):
    """Calcula distância usando OSRM"""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{origem[1]},{origem[0]};{destino[1]},{destino[0]}?overview=false"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['routes']:
                route = data['routes'][0]
                return {
                    "distancia": route['distance'] / 1000,
                    "duracao": route['duration'] / 60,
                    "rota_pontos": [],
                    "provider": "OSRM"
                }
        return None
    except Exception as e:
        print(f"[OSRM] Erro: {e}")
        return None

def calcular_distancia_reta(origem, destino):
    """Calcula distância em linha reta (fallback)"""
    try:
        from math import radians, cos, sin, asin, sqrt
        
        lat1, lon1 = origem[0], origem[1]
        lat2, lon2 = destino[0], destino[1]
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371
        
        distancia = c * r
        duracao = distancia * 1.5
        
        return {
            "distancia": distancia,
            "duracao": duracao,
            "rota_pontos": [],
            "provider": "Distância Reta"
        }
    except Exception as e:
        print(f"[DISTANCIA_RETA] Erro: {e}")
        return None

def calcular_custos_dedicado(uf_origem, municipio_origem, uf_destino, municipio_destino, distancia, pedagio_real=0):
    """Calcula custos para frete dedicado baseado na distância"""
    try:
        custos = {}
        
        pedagio_real = float(pedagio_real) if pedagio_real is not None else 0.0
        distancia = float(distancia) if distancia is not None else 0.0
        
        faixa = determinar_faixa(distancia)
        
        if faixa and faixa in TABELA_CUSTOS_DEDICADO:
            tabela = TABELA_CUSTOS_DEDICADO[faixa]
            for tipo_veiculo, valor in tabela.items():
                custo_total = float(valor) + pedagio_real
                custos[tipo_veiculo] = round(custo_total, 2)
                
        elif distancia > 600:
            for tipo_veiculo, valor_km in DEDICADO_KM_ACIMA_600.items():
                custo_total = (distancia * float(valor_km)) + pedagio_real
                custos[tipo_veiculo] = round(custo_total, 2)
        else:
            custos_base = {
                "FIORINO": 150.0, "VAN": 200.0, "3/4": 250.0, 
                "TOCO": 300.0, "TRUCK": 350.0, "CARRETA": 500.0
            }
            for tipo_veiculo, valor in custos_base.items():
                custo_total = float(valor) + pedagio_real
                custos[tipo_veiculo] = round(custo_total, 2)
        
        for tipo_veiculo in list(custos.keys()):
            if not isinstance(custos[tipo_veiculo], (int, float)) or custos[tipo_veiculo] < 0:
                custos[tipo_veiculo] = 0.0
        
        return custos
        
    except Exception as e:
        print(f"[ERRO] Erro ao calcular custos dedicado: {e}")
        return {
            "FIORINO": 150.0, "VAN": 200.0, "3/4": 250.0, 
            "TOCO": 300.0, "TRUCK": 350.0, "CARRETA": 500.0
        }

def gerar_analise_trajeto(origem_info, destino_info, rota_info, custos, tipo="Dedicado", municipio_origem=None, uf_origem=None, municipio_destino=None, uf_destino=None):
    """Gera análise completa do trajeto"""
    if municipio_origem and uf_origem:
        origem_nome = f"{municipio_origem} - {uf_origem}"
    else:
        origem_nome = origem_info[2] if len(origem_info) > 2 else "Origem"
    
    if municipio_destino and uf_destino:
        destino_nome = f"{municipio_destino} - {uf_destino}"
    else:
        destino_nome = destino_info[2] if len(destino_info) > 2 else "Destino"
    
    horas = int(rota_info["duracao"] / 60)
    minutos = int(rota_info["duracao"] % 60)
    tempo_estimado = f"{horas}h {minutos}min"
    
    consumo_combustivel = rota_info["distancia"] * 0.12
    emissao_co2 = consumo_combustivel * 2.3
    pedagio_real = rota_info["distancia"] * 0.05
    pedagio_detalhes = {"fonte": "Estimativa baseada na distância", "valor_por_km": 0.05}
    
    import uuid
    id_historico = f"#Ded{uuid.uuid4().hex[:6].upper()}"
    
    return {
        "id_historico": id_historico,
        "tipo": tipo,
        "origem": origem_nome,
        "destino": destino_nome,
        "distancia": rota_info["distancia"],
        "duracao_minutos": rota_info["duracao"],
        "tempo_estimado": tempo_estimado,
        "consumo_combustivel": round(consumo_combustivel, 2),
        "emissao_co2": round(emissao_co2, 2),
        "pedagio_estimado": round(pedagio_real, 2),
        "pedagio_real": round(pedagio_real, 2),
        "pedagio_detalhes": pedagio_detalhes,
        "provider": rota_info["provider"],
        "data_hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "custos": custos
    }

def gerar_ranking_dedicado(custos, analise, rota_info, peso=0, cubagem=0, valor_nf=None):
    """Gera ranking das opções de frete dedicado"""
    try:
        ranking_opcoes = []
        custos_ordenados = sorted(custos.items(), key=lambda x: x[1])
        
        for i, (tipo_veiculo, custo) in enumerate(custos_ordenados, 1):
            if tipo_veiculo == "VAN":
                capacidade_info = {'peso_max': '1.500kg', 'volume_max': '8m³', 'descricao': 'Veículo compacto para cargas leves'}
                icone_veiculo = "🚐"
            elif tipo_veiculo == "TRUCK":
                capacidade_info = {'peso_max': '8.000kg', 'volume_max': '25m³', 'descricao': 'Caminhão médio para cargas variadas'}
                icone_veiculo = "🚛"
            elif tipo_veiculo == "CARRETA":
                capacidade_info = {'peso_max': '27.000kg', 'volume_max': '90m³', 'descricao': 'Carreta para cargas pesadas'}
                icone_veiculo = "🚛"
            else:
                capacidade_info = {'peso_max': 'Variável', 'volume_max': 'Variável', 'descricao': 'Veículo dedicado'}
                icone_veiculo = "🚛"
            
            if i == 1:
                icone_posicao = "🥇"
            elif i == 2:
                icone_posicao = "🥈"
            elif i == 3:
                icone_posicao = "🥉"
            else:
                icone_posicao = f"{i}º"
            
            distancia = analise.get('distancia', 500)
            prazo_estimado = max(1, int(distancia / 500))
            
            custo_base = custo * 0.70
            combustivel = custo * 0.20
            pedagio = analise.get('pedagio_real', custo * 0.10)
            
            opcao_ranking = {
                'posicao': i,
                'icone': f"{icone_posicao} {icone_veiculo}",
                'tipo_servico': f"FRETE DEDICADO - {tipo_veiculo}",
                'fornecedor': 'Porto Express',
                'descricao': f"Frete dedicado com {tipo_veiculo.lower()} exclusivo",
                'custo_total': custo,
                'prazo': prazo_estimado,
                'peso_usado': f"{peso}kg" if peso else "Não informado",
                'capacidade': capacidade_info,
                'eh_melhor_opcao': (i == 1),
                'detalhes_expandidos': {
                    'custos_detalhados': {
                        'custo_base': round(custo_base, 2),
                        'combustivel': round(combustivel, 2),
                        'pedagio': round(pedagio, 2),
                        'outros': round(custo - custo_base - combustivel - pedagio, 2),
                        'total': custo
                    },
                    'rota_info': {
                        'origem': analise.get('origem', ''),
                        'destino': analise.get('destino', ''),
                        'distancia': analise.get('distancia', 0),
                        'tempo_viagem': analise.get('tempo_estimado', ''),
                        'pedagio_real': analise.get('pedagio_real', 0),
                        'consumo_estimado': analise.get('consumo_combustivel', 0),
                        'emissao_co2': analise.get('emissao_co2', 0)
                    },
                    'veiculo_info': {
                        'tipo': tipo_veiculo,
                        'capacidade_peso': capacidade_info['peso_max'],
                        'capacidade_volume': capacidade_info['volume_max'],
                        'descricao': capacidade_info['descricao']
                    }
                }
            }
            
            ranking_opcoes.append(opcao_ranking)
        
        melhor_opcao = ranking_opcoes[0] if ranking_opcoes else None
        
        return {
            'id_calculo': analise.get('id_historico', f"#Ded{len(ranking_opcoes):03d}"),
            'tipo_frete': 'Dedicado',
            'origem': analise.get('origem', ''),
            'destino': analise.get('destino', ''),
            'peso': peso,
            'cubagem': cubagem,
            'valor_nf': valor_nf,
            'distancia': analise.get('distancia', 0),
            'tempo_estimado': analise.get('tempo_estimado', ''),
            'pedagio_real': analise.get('pedagio_real', 0),
            'opcoes': ranking_opcoes,
            'melhor_opcao': melhor_opcao,
            'total_opcoes': len(ranking_opcoes)
        }
        
    except Exception as e:
        print(f"[RANKING] Erro ao gerar ranking dedicado: {e}")
        return None

@app.route("/calcular_dedicado", methods=["POST"])
def calcular_dedicado():
    """Cálculo de frete dedicado - redireciona para /calcular"""
    try:
        data = request.get_json()
        # Redirecionar para a função calcular() que já faz o cálculo dedicado
        return calcular()
    except Exception as e:
        print(f"[DEDICADO] Erro: {e}")
        return jsonify({"error": f"Erro ao calcular frete dedicado: {str(e)}"})

@app.route("/calcular_aereo", methods=["POST"])
def calcular_aereo():
    """Cálculo de frete aéreo limpo"""
    try:
        data = request.get_json()
        usuario = session.get('usuario_logado', 'DESCONHECIDO')
        
        origem = data.get("municipio_origem")
        uf_origem = data.get("uf_origem")
        destino = data.get("municipio_destino")
        uf_destino = data.get("uf_destino")
        peso = float(data.get("peso", 5))
        cubagem = float(data.get("cubagem", 0.02))
        
        log_acesso(usuario, 'CALCULO_AEREO', obter_ip_cliente(), 
                  f"{origem}/{uf_origem} → {destino}/{uf_destino}, {peso}kg")
        
        if not all([origem, uf_origem, destino, uf_destino]):
            return jsonify({"error": "Origem e destino são obrigatórios"})
        
        # Sistema simplificado para aéreo
        resultado = {'sem_opcoes': True, 'erro': 'Cálculo aéreo em desenvolvimento'}
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"[AÉREO] Erro: {e}")
        return jsonify({"error": str(e)})

# ===== ROTAS DE ADMINISTRAÇÃO =====

@app.route('/admin')
def admin():
    """Painel administrativo"""
    usuario = session.get('usuario_logado', 'DESCONHECIDO')
    log_acesso(usuario, 'ADMIN_ACESSO', obter_ip_cliente())
    
    try:
        estatisticas = {
            'total_logs': LogSistema.query.count() if POSTGRESQL_AVAILABLE else 0,
            'total_pesquisas': HistoricoCalculo.query.count() if POSTGRESQL_AVAILABLE else 0,
            'usuarios_unicos': 1,
            'ips_unicos': 1,
            'ultimas_atividades': [],
            'acoes_mais_comuns': []
        }
        
        return render_template("admin_melhorado.html", estatisticas=estatisticas)
    except Exception as e:
        print(f"[ADMIN] Erro: {e}")
        return redirect(url_for('index'))

@app.route('/admin/calculadoras')
def admin_calculadoras():
    """Gerenciar calculadoras"""
    return render_template('admin_calculadoras.html')

@app.route('/admin/base-dados')
def admin_base_dados():
    """Gerenciar base de dados"""
    return render_template('admin_base_dados.html')

@app.route('/admin/agentes-memoria')
def admin_agentes_memoria():
    """Gerenciar memórias de cálculo"""
    return render_template('admin_agentes_memoria.html')

@app.route('/admin/usuarios')
def admin_usuarios():
    """Gerenciar usuários do sistema"""
    # Verificar se usuário tem permissão
    if not session.get('usuario_permissoes', {}).get('pode_gerenciar_usuarios', False):
        flash('Acesso negado. Você não tem permissão para gerenciar usuários.', 'danger')
        return redirect(url_for('admin'))
    
    return render_template('admin_usuarios.html')

# ===== APIs LIMPAS =====

@app.route('/api/admin/base-dados', methods=['GET'])
def api_get_base_dados():
    """API para listar dados da base"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        todos = request.args.get('todos', 'false').lower() == 'true'
        
        # Filtros
        query = BaseUnificada.query
        
        if request.args.get('tipo'):
            query = query.filter(BaseUnificada.tipo.ilike(f'%{request.args.get("tipo")}%'))
        if request.args.get('fornecedor'):
            query = query.filter(BaseUnificada.fornecedor.ilike(f'%{request.args.get("fornecedor")}%'))
        if request.args.get('origem'):
            query = query.filter(BaseUnificada.origem.ilike(f'%{request.args.get("origem")}%'))
        if request.args.get('destino'):
            query = query.filter(BaseUnificada.destino.ilike(f'%{request.args.get("destino")}%'))
        
        total = query.count()
        
        if todos:
            registros = query.all()
        else:
            registros = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Converter para dicionários
        dados = []
        for r in registros:
            dados.append({
                'id': f"{r.fornecedor}_{r.origem}_{r.destino}",
                'tipo': r.tipo,
                'fornecedor': r.fornecedor,
                'base_origem': r.base_origem,
                'origem': r.origem,
                'base_destino': r.base_destino,
                'destino': r.destino,
                'valor_minimo_10': r.valor_minimo_10,
                'peso_20': r.peso_20,
                'peso_30': r.peso_30,
                'peso_50': r.peso_50,
                'peso_70': r.peso_70,
                'peso_100': r.peso_100,
                'peso_150': r.peso_150,
                'peso_200': r.peso_200,
                'peso_300': r.peso_300,
                'peso_500': r.peso_500,
                'acima_500': r.acima_500,
                'pedagio_100kg': r.pedagio_100kg,
                'excedente': r.excedente,
                'seguro': r.seguro,
                'peso_maximo': r.peso_maximo,
                'gris_min': r.gris_min,
                'gris_exc': r.gris_exc,
                'tas': r.tas,
                'despacho': r.despacho
            })
        
        # Filtros disponíveis
        from sqlalchemy import distinct
        filtros = {
            'tipos': [r[0] for r in db.session.query(distinct(BaseUnificada.tipo)).filter(BaseUnificada.tipo.isnot(None)).all()],
            'fornecedores': [r[0] for r in db.session.query(distinct(BaseUnificada.fornecedor)).filter(BaseUnificada.fornecedor.isnot(None)).all()],
            'bases_origem': [r[0] for r in db.session.query(distinct(BaseUnificada.base_origem)).filter(BaseUnificada.base_origem.isnot(None)).all()]
        }
        
        return jsonify({
            'registros': dados,
            'total': total,
            'filtros': filtros
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== ROTAS DE EDIÇÃO DA BASE DE DADOS =====

@app.route('/api/admin/base-dados/editar', methods=['POST'])
def api_editar_campo_base_dados():
    """Editar campo específico da base de dados"""
    # Verificar permissão
    if not session.get('usuario_permissoes', {}).get('pode_editar_base', False):
        return jsonify({'error': 'Acesso negado. Você não tem permissão para editar a base de dados.'}), 403
    
    try:
        data = request.get_json()
        registro_id = data.get('id')
        campo = data.get('campo')
        valor = data.get('valor')
        
        if not all([registro_id, campo]):
            return jsonify({'error': 'ID e campo são obrigatórios'}), 400
        
        # Decodificar ID (formato: fornecedor_origem_destino)
        partes = registro_id.split('_', 2)
        if len(partes) < 3:
            return jsonify({'error': 'ID inválido'}), 400
        
        fornecedor = partes[0]
        origem = partes[1]
        destino = partes[2]
        
        # Buscar registro
        registro = BaseUnificada.query.filter_by(
            fornecedor=fornecedor,
            origem=origem,
            destino=destino
        ).first()
        
        if not registro:
            return jsonify({'error': 'Registro não encontrado'}), 404
        
        # Mapear campos do frontend para o modelo
        campo_mapping = {
            'tipo': 'tipo',
            'fornecedor': 'fornecedor',
            'base_origem': 'base_origem',
            'origem': 'origem',
            'base_destino': 'base_destino',
            'destino': 'destino',
            'valor_minimo_10': 'valor_minimo_10',
            'peso_20': 'peso_20',
            'peso_30': 'peso_30',
            'peso_50': 'peso_50',
            'peso_70': 'peso_70',
            'peso_100': 'peso_100',
            'peso_150': 'peso_150',
            'peso_200': 'peso_200',
            'peso_300': 'peso_300',
            'peso_500': 'peso_500',
            'acima_500': 'acima_500',
            'pedagio_100kg': 'pedagio_100kg',
            'excedente': 'excedente',
            'seguro': 'seguro',
            'peso_maximo': 'peso_maximo',
            'gris_min': 'gris_min',
            'gris_exc': 'gris_exc',
            'tas': 'tas',
            'despacho': 'despacho'
        }
        
        if campo not in campo_mapping:
            return jsonify({'error': f'Campo inválido: {campo}'}), 400
        
        # Atualizar campo
        setattr(registro, campo_mapping[campo], valor)
        db.session.commit()
        
        return jsonify({'sucesso': True, 'message': 'Campo atualizado com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/base-dados/inserir-automatico', methods=['POST'])
def api_inserir_dados_automatico():
    """Inserir dados automaticamente na base de dados"""
    try:
        # Permitir inserção automática sem verificação de permissão
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Dados não fornecidos'}), 400
        
        # Se for uma lista, inserir múltiplos registros
        if isinstance(data, list):
            registros_inseridos = 0
            for item in data:
                try:
                    # Criar novo registro
                    novo_registro = BaseUnificada(
                        tipo=item.get('tipo', ''),
                        fornecedor=item.get('fornecedor', ''),
                        base_origem=item.get('base_origem', ''),
                        origem=item.get('origem', ''),
                        base_destino=item.get('base_destino', ''),
                        destino=item.get('destino', ''),
                        valor_minimo_10=item.get('valor_minimo_ate_10'),
                        peso_20=item.get('valor_20'),
                        peso_30=item.get('valor_30'),
                        peso_50=item.get('valor_50'),
                        peso_70=item.get('valor_70'),
                        peso_100=item.get('valor_100'),
                        peso_150=item.get('valor_150'),
                        peso_200=item.get('valor_200'),
                        peso_300=item.get('valor_300'),
                        peso_500=item.get('valor_500'),
                        acima_500=item.get('valor_acima_500'),
                        pedagio_100kg=item.get('pedagio_100_kg'),
                        excedente=item.get('excedente'),
                        seguro=item.get('seguro'),
                        peso_maximo=item.get('peso_maximo_transportado'),
                        gris_min=item.get('gris_min'),
                        gris_exc=item.get('gris_exc'),
                        prazo=item.get('prazo'),
                        tda=item.get('tda', ''),
                        uf=item.get('uf', ''),
                        tas=item.get('tas'),
                        despacho=item.get('despacho')
                    )
                    
                    db.session.add(novo_registro)
                    registros_inseridos += 1
                    
                except Exception as e:
                    print(f"Erro ao inserir registro: {e}")
                    continue
            
            db.session.commit()
            return jsonify({
                'sucesso': True, 
                'message': f'{registros_inseridos} registros inseridos automaticamente',
                'registros_inseridos': registros_inseridos
            })
        
        else:
            # Inserir registro único
            novo_registro = BaseUnificada(
                tipo=data.get('tipo', ''),
                fornecedor=data.get('fornecedor', ''),
                base_origem=data.get('base_origem', ''),
                origem=data.get('origem', ''),
                base_destino=data.get('base_destino', ''),
                destino=data.get('destino', ''),
                valor_minimo_10=data.get('valor_minimo_ate_10'),
                peso_20=data.get('valor_20'),
                peso_30=data.get('valor_30'),
                peso_50=data.get('valor_50'),
                peso_70=data.get('valor_70'),
                peso_100=data.get('valor_100'),
                peso_150=data.get('valor_150'),
                peso_200=data.get('valor_200'),
                peso_300=data.get('valor_300'),
                peso_500=data.get('valor_500'),
                acima_500=data.get('valor_acima_500'),
                pedagio_100kg=data.get('pedagio_100_kg'),
                excedente=data.get('excedente'),
                seguro=data.get('seguro'),
                peso_maximo=data.get('peso_maximo_transportado'),
                gris_min=data.get('gris_min'),
                gris_exc=data.get('gris_exc'),
                prazo=data.get('prazo'),
                tda=data.get('tda', ''),
                uf=data.get('uf', ''),
                tas=data.get('tas'),
                despacho=data.get('despacho')
            )
            
            db.session.add(novo_registro)
            db.session.commit()
            
            return jsonify({
                'sucesso': True, 
                'message': 'Registro inserido automaticamente',
                'registro': {
                    'fornecedor': novo_registro.fornecedor,
                    'origem': novo_registro.origem,
                    'destino': novo_registro.destino
                }
            })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erro ao inserir dados: {str(e)}'}), 500

@app.route('/api/admin/base-dados', methods=['POST'])
def api_create_base_dados():
    """Criar novo registro na base de dados"""
    # Verificar permissão
    if not session.get('usuario_permissoes', {}).get('pode_editar_base', False):
        return jsonify({'error': 'Acesso negado. Você não tem permissão para editar a base de dados.'}), 403
    
    try:
        data = request.get_json()
        
        # Validar campos obrigatórios
        campos_obrigatorios = ['tipo', 'fornecedor', 'origem', 'destino']
        for campo in campos_obrigatorios:
            if not data.get(campo):
                return jsonify({'error': f'Campo obrigatório: {campo}'}), 400
        
        # Verificar se já existe
        existente = BaseUnificada.query.filter_by(
            fornecedor=data['fornecedor'],
            origem=data['origem'],
            destino=data['destino']
        ).first()
        
        if existente:
            return jsonify({'error': 'Registro já existe'}), 400
        
        # Criar novo registro
        novo_registro = BaseUnificada(
            tipo=data['tipo'],
            fornecedor=data['fornecedor'],
            base_origem=data.get('base_origem'),
            origem=data['origem'],
            base_destino=data.get('base_destino'),
            destino=data['destino'],
            valor_minimo_10=data.get('valor_minimo_10'),
            peso_20=data.get('peso_20'),
            peso_30=data.get('peso_30'),
            peso_50=data.get('peso_50'),
            peso_70=data.get('peso_70'),
            peso_100=data.get('peso_100'),
            peso_150=data.get('peso_150'),
            peso_200=data.get('peso_200'),
            peso_300=data.get('peso_300'),
            peso_500=data.get('peso_500'),
            acima_500=data.get('acima_500'),
            pedagio_100kg=data.get('pedagio_100kg'),
            excedente=data.get('excedente'),
            seguro=data.get('seguro'),
            peso_maximo=data.get('peso_maximo'),
            gris_min=data.get('gris_min'),
            gris_exc=data.get('gris_exc'),
            tas=data.get('tas'),
            despacho=data.get('despacho')
        )
        
        db.session.add(novo_registro)
        db.session.commit()
        
        return jsonify({'sucesso': True, 'message': 'Registro criado com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/base-dados/<registro_id>', methods=['DELETE'])
def api_delete_base_dados(registro_id):
    """Excluir registro da base de dados"""
    # Verificar permissão
    if not session.get('usuario_permissoes', {}).get('pode_editar_base', False):
        return jsonify({'error': 'Acesso negado. Você não tem permissão para editar a base de dados.'}), 403
    
    try:
        # Decodificar ID (formato: fornecedor_origem_destino)
        partes = registro_id.split('_', 2)
        if len(partes) < 3:
            return jsonify({'error': 'ID inválido'}), 400
        
        fornecedor = partes[0]
        origem = partes[1]
        destino = partes[2]
        
        # Buscar e excluir registro
        registro = BaseUnificada.query.filter_by(
            fornecedor=fornecedor,
            origem=origem,
            destino=destino
        ).first()
        
        if not registro:
            return jsonify({'error': 'Registro não encontrado'}), 404
        
        db.session.delete(registro)
        db.session.commit()
        
        return jsonify({'sucesso': True, 'message': 'Registro excluído com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ===== ROTA DE CONFIGURAÇÕES E TESTE DE CONEXÃO =====

@app.route('/admin/configuracoes')
def admin_configuracoes():
    """Painel de configurações do sistema"""
    return render_template('admin_configuracoes.html')

@app.route('/api/admin/configuracoes/importar-csv', methods=['POST'])
def api_importar_csv():
    """Importar dados CSV para o banco Neon"""
    try:
        # Verificar se arquivo foi enviado
        if 'arquivo_csv' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        arquivo = request.files['arquivo_csv']
        if arquivo.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        # Verificar extensão
        if not arquivo.filename.lower().endswith('.csv'):
            return jsonify({'error': 'Arquivo deve ser CSV'}), 400
        
        # Ler arquivo CSV
        import csv
        import io
        
        # Decodificar arquivo
        conteudo = arquivo.read().decode('utf-8')
        arquivo_csv = io.StringIO(conteudo)
        
        dados_para_inserir = []
        registros_processados = 0
        
        try:
            reader = csv.DictReader(arquivo_csv)
            
            for row in reader:
                registros_processados += 1
                
                # Função para limpar valores
                def limpar_valor(valor):
                    if not valor or valor.strip() == '':
                        return None
                    try:
                        valor_limpo = valor.strip().replace('R$', '').replace(',', '.').replace(' ', '')
                        return float(valor_limpo)
                    except:
                        return None
                
                # Preparar dados
                dados = {
                    'tipo': row.get('Tipo', ''),
                    'fornecedor': row.get('Fornecedor', ''),
                    'base_origem': row.get('Base Origem', ''),
                    'origem': row.get('Origem', ''),
                    'base_destino': row.get('Base Destino', ''),
                    'destino': row.get('Destino', ''),
                    'valor_minimo_ate_10': limpar_valor(row.get('VALOR MÍNIMO ATÉ 10', '')),
                    'valor_20': limpar_valor(row.get('20', '')),
                    'valor_30': limpar_valor(row.get('30', '')),
                    'valor_50': limpar_valor(row.get('50', '')),
                    'valor_70': limpar_valor(row.get('70', '')),
                    'valor_100': limpar_valor(row.get('100', '')),
                    'valor_150': limpar_valor(row.get('150', '')),
                    'valor_200': limpar_valor(row.get('200', '')),
                    'valor_300': limpar_valor(row.get('300', '')),
                    'valor_500': limpar_valor(row.get('500', '')),
                    'valor_acima_500': limpar_valor(row.get('Acima 500', '')),
                    'pedagio_100_kg': limpar_valor(row.get('Pedagio (100 Kg)', '')),
                    'excedente': limpar_valor(row.get('EXCEDENTE', '')),
                    'seguro': limpar_valor(row.get('Seguro', '')),
                    'peso_maximo_transportado': limpar_valor(row.get('PESO MÁXIMO TRANSPORTADO', '')),
                    'gris_min': limpar_valor(row.get('Gris Min', '')),
                    'gris_exc': limpar_valor(row.get('Gris Exc', '')),
                    'prazo': int(row.get('Prazo', '0')) if row.get('Prazo', '').isdigit() else None,
                    'tda': row.get('TDA', ''),
                    'uf': row.get('UF', ''),
                    'tas': limpar_valor(row.get('TAS', '')),
                    'despacho': limpar_valor(row.get('DESPACHO', ''))
                }
                
                dados_para_inserir.append(dados)
                
        except Exception as e:
            return jsonify({'error': f'Erro ao ler CSV: {str(e)}'}), 400
        
        if not dados_para_inserir:
            return jsonify({'error': 'Nenhum dado válido encontrado no CSV'}), 400
        
        # Inserir dados no banco
        registros_inseridos = 0
        for dados in dados_para_inserir:
            try:
                novo_registro = BaseUnificada(
                    tipo=dados['tipo'],
                    fornecedor=dados['fornecedor'],
                    base_origem=dados['base_origem'],
                    origem=dados['origem'],
                    base_destino=dados['base_destino'],
                    destino=dados['destino'],
                    valor_minimo_10=dados['valor_minimo_ate_10'],
                    peso_20=dados['valor_20'],
                    peso_30=dados['valor_30'],
                    peso_50=dados['valor_50'],
                    peso_70=dados['valor_70'],
                    peso_100=dados['valor_100'],
                    peso_150=dados['valor_150'],
                    peso_200=dados['valor_200'],
                    peso_300=dados['valor_300'],
                    peso_500=dados['valor_500'],
                    acima_500=dados['valor_acima_500'],
                    pedagio_100kg=dados['pedagio_100_kg'],
                    excedente=dados['excedente'],
                    seguro=dados['seguro'],
                    peso_maximo=dados['peso_maximo_transportado'],
                    gris_min=dados['gris_min'],
                    gris_exc=dados['gris_exc'],
                    prazo=dados['prazo'],
                    tda=dados['tda'],
                    uf=dados['uf'],
                    tas=dados['tas'],
                    despacho=dados['despacho']
                )
                
                db.session.add(novo_registro)
                registros_inseridos += 1
                
            except Exception as e:
                print(f"Erro ao inserir registro: {e}")
                continue
        
        db.session.commit()
        
        return jsonify({
            'sucesso': True,
            'message': f'Importação concluída! {registros_inseridos} de {registros_processados} registros inseridos',
            'registros_processados': registros_processados,
            'registros_inseridos': registros_inseridos,
            'arquivo': arquivo.filename
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erro durante importação: {str(e)}'}), 500

@app.route('/api/admin/configuracoes/teste-conexao', methods=['POST'])
def api_teste_conexao_banco():
    """Testar conexão com o banco de dados"""
    try:
        print("[TESTE] Iniciando teste de conexão...")
        
        # Testar conexão básica
        from sqlalchemy import text
        with app.app_context():
            print("[TESTE] Testando conexão básica...")
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            print("[TESTE] Conexão básica OK")
            
            # Testar consultas específicas
            print("[TESTE] Testando consultas...")
            estatisticas = {
                'total_registros': BaseUnificada.query.count(),
                'total_usuarios': Usuario.query.count(),
                'total_agentes': AgenteTransportadora.query.count(),
                'total_memorias': MemoriaCalculoAgente.query.count(),
                'total_tipos_calculo': TipoCalculoFrete.query.count(),
                'total_formulas': FormulaCalculoFrete.query.count()
            }
            print(f"[TESTE] Estatísticas: {estatisticas}")
            
            # Verificar configurações do banco
            config_info = {
                'database_url': app.config.get('SQLALCHEMY_DATABASE_URI', 'Não configurado')[:50] + '...' if app.config.get('SQLALCHEMY_DATABASE_URI') else 'Não configurado',
                'database_type': 'PostgreSQL' if 'postgresql' in app.config.get('SQLALCHEMY_DATABASE_URI', '').lower() else 'SQLite',
                'flask_env': os.environ.get('FLASK_ENV', 'development'),
                'debug_mode': app.config.get('DEBUG', False),
                'postgresql_available': POSTGRESQL_AVAILABLE
            }
            
            print("[TESTE] Teste concluído com sucesso")
            return jsonify({
                'sucesso': True,
                'conexao': 'OK',
                'estatisticas': estatisticas,
                'config_info': config_info,
                'message': 'Conexão com banco de dados funcionando corretamente'
            })
        
    except Exception as e:
        print(f"[TESTE] Erro: {e}")
        return jsonify({
            'sucesso': False,
            'error': str(e),
            'message': 'Erro na conexão com banco de dados'
        }), 500

@app.route('/api/admin/configuracoes/teste-permissoes', methods=['GET'])
def api_teste_permissoes():
    """Testar permissões do usuário logado"""
    try:
        if 'usuario_logado' not in session:
            return jsonify({
                'sucesso': False,
                'message': 'Usuário não está logado'
            }), 401
        
        usuario = Usuario.query.filter_by(nome_usuario=session.get('usuario_logado')).first()
        if not usuario:
            return jsonify({
                'sucesso': False,
                'message': 'Usuário não encontrado no banco'
            }), 404
        
        permissoes = {
            'nome_usuario': usuario.nome_usuario,
            'tipo_usuario': usuario.tipo_usuario,
            'ativo': usuario.ativo,
            'pode_calcular_fretes': usuario.pode_calcular_fretes,
            'pode_ver_admin': usuario.pode_ver_admin,
            'pode_editar_base': usuario.pode_editar_base,
            'pode_gerenciar_usuarios': usuario.pode_gerenciar_usuarios,
            'pode_importar_dados': usuario.pode_importar_dados
        }
        
        permissoes_sessao = session.get('usuario_permissoes', {})
        
        return jsonify({
            'sucesso': True,
            'usuario': permissoes,
            'permissoes_sessao': permissoes_sessao,
            'message': 'Permissões verificadas com sucesso'
        })
        
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'error': str(e),
            'message': 'Erro ao verificar permissões'
        }), 500

@app.route('/api/admin/agentes-memoria', methods=['GET'])
def api_get_agentes_memoria():
    """API para listar agentes e memórias"""
    try:
        agentes = AgenteTransportadora.query.filter_by(ativo=True).all()
        memorias = MemoriaCalculoAgente.query.filter_by(ativo=True).all()
        
        estatisticas = {
            'transportadoras': AgenteTransportadora.query.filter_by(tipo_agente='transportadora', ativo=True).count(),
            'transferencias': AgenteTransportadora.query.filter_by(tipo_agente='transferencia', ativo=True).count(),
            'agentes_ponta': AgenteTransportadora.query.filter(
                AgenteTransportadora.tipo_agente.in_(['agente_coleta', 'agente_entrega']),
                AgenteTransportadora.ativo == True
            ).count(),
            'memorias_ativas': MemoriaCalculoAgente.query.filter_by(ativo=True).count()
        }
        
        return jsonify({
            'agentes': [a.to_dict() for a in agentes],
            'memorias': [m.to_dict() for m in memorias],
            'estatisticas': estatisticas
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== APIs DE CALCULADORAS =====

@app.route('/api/admin/tipos-calculo', methods=['GET'])
def api_get_tipos_calculo():
    """Listar tipos de cálculo"""
    try:
        tipos = TipoCalculoFrete.query.filter_by(ativo=True).all()
        return jsonify([{
            'id': tipo.id,
            'nome': tipo.nome,
            'descricao': tipo.descricao,
            'categoria': tipo.categoria,
            'ativo': tipo.ativo
        } for tipo in tipos])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/tipos-calculo', methods=['POST'])
def api_create_tipo_calculo():
    """Criar novo tipo de cálculo"""
    try:
        data = request.get_json()
        tipo = TipoCalculoFrete(
            nome=data['nome'],
            descricao=data.get('descricao', ''),
            categoria=data.get('categoria', 'FRACIONADO')
        )
        db.session.add(tipo)
        db.session.commit()
        return jsonify({'sucesso': True, 'id': tipo.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/formulas-calculo', methods=['GET'])
def api_get_formulas_calculo():
    """Listar fórmulas de cálculo"""
    try:
        formulas = FormulaCalculoFrete.query.filter_by(ativa=True).all()
        return jsonify([{
            'id': formula.id,
            'nome': formula.nome,
            'tipo_id': formula.tipo_calculo_id,
            'formula': formula.formula,
            'condicoes': formula.condicoes,
            'prioridade': formula.prioridade,
            'ativa': formula.ativa
        } for formula in formulas])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/formulas-calculo', methods=['POST'])
def api_create_formula_calculo():
    """Criar nova fórmula de cálculo"""
    try:
        data = request.get_json()
        formula = FormulaCalculoFrete(
            nome=data['nome'],
            tipo_calculo_id=data['tipo_id'],
            formula=data['formula'],
            condicoes=data.get('condicoes', ''),
            prioridade=data.get('prioridade', 1)
        )
        db.session.add(formula)
        db.session.commit()
        return jsonify({'sucesso': True, 'id': formula.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/configuracoes-agente', methods=['GET'])
def api_get_configuracoes_agente():
    """Listar configurações de agentes"""
    try:
        configuracoes = ConfiguracaoAgente.query.filter_by(ativa=True).all()
        return jsonify([{
            'id': config.id,
            'agente_nome': config.agente_nome,
            'tipo_calculo_id': config.tipo_calculo_id,
            'ativa': config.ativa,
            'valores_customizados': config.get_valores_customizados(),
            'formulas_customizadas': config.get_formulas_customizadas()
        } for config in configuracoes])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/configuracoes-agente', methods=['POST'])
def api_create_configuracao_agente():
    """Criar nova configuração de agente"""
    try:
        data = request.get_json()
        config = ConfiguracaoAgente(
            agente_nome=data['agente_nome'],
            tipo_calculo_id=data['tipo_calculo_id'],
            valores_customizados=data.get('valores_customizados', '{}'),
            formulas_customizadas=data.get('formulas_customizadas', '{}')
        )
        db.session.add(config)
        db.session.commit()
        return jsonify({'sucesso': True, 'id': config.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ===== APIs DE USUÁRIOS =====

@app.route('/api/admin/usuarios', methods=['GET'])
def api_get_usuarios():
    """Listar usuários do sistema"""
    try:
        # Verificar permissão
        if not session.get('usuario_permissoes', {}).get('pode_gerenciar_usuarios', False):
            return jsonify({'error': 'Acesso negado'}), 403
        
        usuarios = Usuario.query.order_by(Usuario.nome_usuario).all()
        return jsonify([usuario.to_dict() for usuario in usuarios])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/usuarios', methods=['POST'])
def api_create_usuario():
    """Criar novo usuário"""
    try:
        # Verificar permissão
        if not session.get('usuario_permissoes', {}).get('pode_gerenciar_usuarios', False):
            return jsonify({'error': 'Acesso negado'}), 403
        
        data = request.get_json()
        
        # Validar dados obrigatórios
        if not data.get('nome_usuario') or not data.get('nome_completo') or not data.get('senha'):
            return jsonify({'error': 'Nome de usuário, nome completo e senha são obrigatórios'}), 400
        
        # Verificar se usuário já existe
        if Usuario.query.filter_by(nome_usuario=data['nome_usuario']).first():
            return jsonify({'error': 'Nome de usuário já existe'}), 400
        
        # Verificar email único se fornecido
        if data.get('email'):
            if Usuario.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email já está em uso'}), 400
        
        # Criar usuário
        usuario = Usuario(
            nome_usuario=data['nome_usuario'],
            nome_completo=data['nome_completo'],
            email=data.get('email'),
            tipo_usuario=data.get('tipo_usuario', 'operador'),
            pode_calcular_fretes=bool(data.get('pode_calcular_fretes', True)),
            pode_ver_admin=bool(data.get('pode_ver_admin', False)),
            pode_editar_base=bool(data.get('pode_editar_base', False)),
            pode_gerenciar_usuarios=bool(data.get('pode_gerenciar_usuarios', False)),
            pode_importar_dados=bool(data.get('pode_importar_dados', False)),
            ativo=bool(data.get('ativo', True)),
            criado_por=session.get('usuario_logado', 'sistema')
        )
        usuario.set_senha(data['senha'])
        
        db.session.add(usuario)
        db.session.commit()
        
        log_acesso(session.get('usuario_logado'), 'USUARIO_CRIADO', obter_ip_cliente(), 
                  f'Criado usuário: {usuario.nome_usuario}')
        
        return jsonify(usuario.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/usuarios/<int:usuario_id>', methods=['PUT'])
def api_update_usuario(usuario_id):
    """Atualizar usuário"""
    try:
        # Verificar permissão
        if not session.get('usuario_permissoes', {}).get('pode_gerenciar_usuarios', False):
            return jsonify({'error': 'Acesso negado'}), 403
        
        usuario = Usuario.query.get_or_404(usuario_id)
        data = request.get_json()
        
        # Verificar nome único (exceto o próprio)
        if data.get('nome_usuario') != usuario.nome_usuario:
            if Usuario.query.filter_by(nome_usuario=data['nome_usuario']).first():
                return jsonify({'error': 'Nome de usuário já existe'}), 400
        
        # Verificar email único (exceto o próprio)
        if data.get('email') and data.get('email') != usuario.email:
            if Usuario.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email já está em uso'}), 400
        
        # Atualizar dados
        usuario.nome_usuario = data.get('nome_usuario', usuario.nome_usuario)
        usuario.nome_completo = data.get('nome_completo', usuario.nome_completo)
        usuario.email = data.get('email', usuario.email)
        usuario.tipo_usuario = data.get('tipo_usuario', usuario.tipo_usuario)
        usuario.pode_calcular_fretes = bool(data.get('pode_calcular_fretes', usuario.pode_calcular_fretes))
        usuario.pode_ver_admin = bool(data.get('pode_ver_admin', usuario.pode_ver_admin))
        usuario.pode_editar_base = bool(data.get('pode_editar_base', usuario.pode_editar_base))
        usuario.pode_gerenciar_usuarios = bool(data.get('pode_gerenciar_usuarios', usuario.pode_gerenciar_usuarios))
        usuario.pode_importar_dados = bool(data.get('pode_importar_dados', usuario.pode_importar_dados))
        usuario.ativo = bool(data.get('ativo', usuario.ativo))
        
        # Atualizar senha se fornecida
        if data.get('senha') and data['senha'] != '******':
            usuario.set_senha(data['senha'])
        
        db.session.commit()
        
        log_acesso(session.get('usuario_logado'), 'USUARIO_ATUALIZADO', obter_ip_cliente(), 
                  f'Atualizado usuário: {usuario.nome_usuario}')
        
        return jsonify(usuario.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/usuarios/<int:usuario_id>/senha', methods=['PUT'])
def api_update_senha_usuario(usuario_id):
    """Alterar senha de usuário"""
    try:
        # Verificar permissão
        if not session.get('usuario_permissoes', {}).get('pode_gerenciar_usuarios', False):
            return jsonify({'error': 'Acesso negado'}), 403
        
        usuario = Usuario.query.get_or_404(usuario_id)
        data = request.get_json()
        
        nova_senha = data.get('nova_senha')
        if not nova_senha or len(nova_senha) < 6:
            return jsonify({'error': 'Senha deve ter pelo menos 6 caracteres'}), 400
        
        # Atualizar senha
        usuario.set_senha(nova_senha)
        usuario.tentativas_login = 0  # Resetar tentativas
        usuario.bloqueado_ate = None  # Desbloquear se estiver bloqueado
        
        db.session.commit()
        
        log_acesso(session.get('usuario_logado'), 'SENHA_ALTERADA', obter_ip_cliente(), 
                  f'Senha alterada para usuário: {usuario.nome_usuario}')
        
        return jsonify({'message': 'Senha alterada com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/usuarios/<int:usuario_id>', methods=['DELETE'])
def api_delete_usuario(usuario_id):
    """Excluir usuário"""
    try:
        # Verificar permissão
        if not session.get('usuario_permissoes', {}).get('pode_gerenciar_usuarios', False):
            return jsonify({'error': 'Acesso negado'}), 403
        
        usuario = Usuario.query.get_or_404(usuario_id)
        
        # Não permitir excluir admin padrão
        if usuario.nome_usuario == 'admin':
            return jsonify({'error': 'Não é possível excluir o usuário admin padrão'}), 400
        
        # Não permitir excluir o próprio usuário
        if usuario.id == session.get('usuario_id'):
            return jsonify({'error': 'Não é possível excluir seu próprio usuário'}), 400
        
        nome_usuario = usuario.nome_usuario
        db.session.delete(usuario)
        db.session.commit()
        
        log_acesso(session.get('usuario_logado'), 'USUARIO_EXCLUIDO', obter_ip_cliente(), 
                  f'Excluído usuário: {nome_usuario}')
        
        return jsonify({'message': 'Usuário excluído com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ===== ROTAS AUXILIARES =====

@app.route('/estados')
def estados():
    """Lista estados"""
    estados_brasil = [
        {"sigla": "AC", "nome": "Acre"},
        {"sigla": "AL", "nome": "Alagoas"},
        {"sigla": "AP", "nome": "Amapá"},
        {"sigla": "AM", "nome": "Amazonas"},
        {"sigla": "BA", "nome": "Bahia"},
        {"sigla": "CE", "nome": "Ceará"},
        {"sigla": "DF", "nome": "Distrito Federal"},
        {"sigla": "ES", "nome": "Espírito Santo"},
        {"sigla": "GO", "nome": "Goiás"},
        {"sigla": "MA", "nome": "Maranhão"},
        {"sigla": "MT", "nome": "Mato Grosso"},
        {"sigla": "MS", "nome": "Mato Grosso do Sul"},
        {"sigla": "MG", "nome": "Minas Gerais"},
        {"sigla": "PA", "nome": "Pará"},
        {"sigla": "PB", "nome": "Paraíba"},
        {"sigla": "PR", "nome": "Paraná"},
        {"sigla": "PE", "nome": "Pernambuco"},
        {"sigla": "PI", "nome": "Piauí"},
        {"sigla": "RJ", "nome": "Rio de Janeiro"},
        {"sigla": "RN", "nome": "Rio Grande do Norte"},
        {"sigla": "RS", "nome": "Rio Grande do Sul"},
        {"sigla": "RO", "nome": "Rondônia"},
        {"sigla": "RR", "nome": "Roraima"},
        {"sigla": "SC", "nome": "Santa Catarina"},
        {"sigla": "SP", "nome": "São Paulo"},
        {"sigla": "SE", "nome": "Sergipe"},
        {"sigla": "TO", "nome": "Tocantins"}
    ]
    return jsonify(estados_brasil)

@app.route('/municipios/<uf>')
def municipios(uf):
    """Lista municípios por UF"""
    try:
        # Cache simples
        if uf in MUNICIPIOS_CACHE:
            return jsonify(MUNICIPIOS_CACHE[uf])
        
        # Buscar via IBGE
        url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            municipios_data = response.json()
            municipios_nomes = [m['nome'] for m in municipios_data]
            MUNICIPIOS_CACHE[uf] = municipios_nomes
            return jsonify(municipios_nomes)
        else:
            return jsonify([])
            
    except Exception as e:
        print(f"[MUNICIPIOS] Erro para {uf}: {e}")
        return jsonify([])

@app.route('/historico')
def historico():
    """Histórico de consultas"""
    try:
        historicos = HistoricoCalculo.query.order_by(HistoricoCalculo.data_calculo.desc()).limit(50).all()
        return jsonify([h.to_dict() for h in historicos])
    except Exception:
        return jsonify([])

@app.route('/health')
def health_check():
    """Endpoint de health check para verificar se a aplicação está funcionando."""
    try:
        # Verificar se a aplicação está funcionando
        base_df = carregar_base_unificada()
        total_registros = len(base_df) if base_df is not None else 0
        status = {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "version": "1.0.0",
            "services": {
                "database": "online" if total_registros > 0 else "offline",
                "records": total_registros,
                "postgresql_available": POSTGRESQL_AVAILABLE
            }
        }
        return jsonify(status), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy", 
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 503

@app.route('/api/bases-disponiveis')
def api_bases_disponiveis():
    """API para listar bases disponíveis"""
    try:
        from sqlalchemy import distinct
        bases = db.session.query(distinct(BaseUnificada.base_origem)).filter(
            BaseUnificada.base_origem.isnot(None)
        ).all()
        
        bases_list = [base[0] for base in bases if base[0]]
        return jsonify(bases_list)
        
    except Exception as e:
        print(f"[BASES] Erro: {e}")
        return jsonify([])

# ===== MIDDLEWARE DE AUTENTICAÇÃO =====

def middleware_auth(f):
    """Middleware de autenticação com verificação de permissões"""
    def decorated_function(*args, **kwargs):
        if 'usuario_logado' not in session:
            return redirect(url_for('login'))
        
        # Verificar se usuário ainda existe e está ativo
        try:
            usuario = Usuario.query.filter_by(
                nome_usuario=session.get('usuario_logado'),
                ativo=True
            ).first()
            
            if not usuario:
                session.clear()
                flash('Sessão expirada. Faça login novamente.', 'warning')
                return redirect(url_for('login'))
                
        except Exception:
            pass  # Se erro no banco, continuar (fallback)
        
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Aplicar middleware nas rotas protegidas
calcular_frete_fracionado = middleware_auth(calcular_frete_fracionado)
calcular_dedicado = middleware_auth(calcular_dedicado)
calcular_aereo = middleware_auth(calcular_aereo)
admin = middleware_admin(admin)
admin_calculadoras = middleware_admin(admin_calculadoras)
admin_base_dados = middleware_admin(admin_base_dados)
admin_agentes_memoria = middleware_admin(admin_agentes_memoria)
admin_usuarios = middleware_admin(admin_usuarios)
admin_configuracoes = middleware_admin(admin_configuracoes)

def criar_rota_parcial_transferencia_entrega(transferencia_linha, agente_entrega, origem, destino, peso_cubado, valor_nf):
    """Cria rota parcial: Transferência + Entrega (sem agente de coleta)"""
    try:
        fornecedor_transf = transferencia_linha.get('Fornecedor', 'N/A')
        fornecedor_ent = agente_entrega.get('Fornecedor', 'N/A')
        
        # Calcular custos usando lógica original
        custo_transferencia = calcular_custo_agente_original(transferencia_linha, peso_cubado, valor_nf)
        custo_entrega = calcular_custo_agente_original(agente_entrega, peso_cubado, valor_nf)
        
        if not custo_transferencia or not custo_entrega:
            return None
        
        # Somar custos
        custo_total = custo_transferencia['total'] + custo_entrega['total']
        prazo_total = max(custo_transferencia.get('prazo', 1), custo_entrega.get('prazo', 1))
        
        return {
            'tipo_servico': f"{fornecedor_transf} (Transferência) + {fornecedor_ent} (Entrega) - Rota Parcial",
            'fornecedor': f"{fornecedor_transf}",
            'custo_total': custo_total,
            'prazo': prazo_total,
            'peso_maximo_agente': min(
                custo_transferencia.get('peso_maximo', 1000) or 1000,
                custo_entrega.get('peso_maximo', 1000) or 1000
            ),
            'descricao': f"Rota parcial: Transferência + Entrega (sem agente de coleta)",
            'detalhes_expandidos': {
                'agentes_info': {
                    'agente_coleta': 'N/A - Rota parcial',
                    'transferencia': fornecedor_transf,
                    'agente_entrega': fornecedor_ent,
                    'base_origem': transferencia_linha.get('Base Origem', 'Base de Origem'),
                    'base_destino': transferencia_linha.get('Base Destino', 'Base de Destino')
                },
                'rota_info': {
                    'origem': origem,
                    'destino': destino,
                    'peso_cubado': peso_cubado,
                    'tipo_peso_usado': 'Cubado'
                },
                'custos_detalhados': {
                    'custo_base_frete': custo_transferencia['custo_base'] + custo_entrega['custo_base'],
                    'custo_coleta': 0,
                    'custo_transferencia': custo_transferencia['total'],
                    'custo_entrega': custo_entrega['total'],
                    'pedagio': custo_transferencia['pedagio'] + custo_entrega['pedagio'],
                    'gris': custo_transferencia['gris'] + custo_entrega['gris'],
                    'seguro': custo_transferencia.get('seguro', 0) + custo_entrega.get('seguro', 0),
                    'icms': 0,
                    'outros': 0
                },
                'observacoes': f"Rota parcial: Transferência + Entrega. Agente de coleta não encontrado para {origem}. {fornecedor_transf} → {fornecedor_ent}"
            }
        }
        
    except Exception as e:
        print(f"[ROTA_PARCIAL_TE] ❌ Erro: {e}")
        return None

def criar_rota_parcial_coleta_transferencia(agente_coleta, transferencia_linha, origem, destino, peso_cubado, valor_nf):
    """Cria rota parcial: Coleta + Transferência (sem agente de entrega)"""
    try:
        fornecedor_col = agente_coleta.get('Fornecedor', 'N/A')
        fornecedor_transf = transferencia_linha.get('Fornecedor', 'N/A')
        
        # Calcular custos usando lógica original
        custo_coleta = calcular_custo_agente_original(agente_coleta, peso_cubado, valor_nf)
        custo_transferencia = calcular_custo_agente_original(transferencia_linha, peso_cubado, valor_nf)
        
        if not custo_coleta or not custo_transferencia:
            return None
        
        # Somar custos
        custo_total = custo_coleta['total'] + custo_transferencia['total']
        prazo_total = max(custo_coleta.get('prazo', 1), custo_transferencia.get('prazo', 1))
        
        return {
            'tipo_servico': f"{fornecedor_col} (Coleta) + {fornecedor_transf} (Transferência) - Rota Parcial",
            'fornecedor': f"{fornecedor_transf}",
            'custo_total': custo_total,
            'prazo': prazo_total,
            'peso_maximo_agente': min(
                custo_coleta.get('peso_maximo', 1000) or 1000,
                custo_transferencia.get('peso_maximo', 1000) or 1000
            ),
            'descricao': f"Rota parcial: Coleta + Transferência (sem agente de entrega)",
            'detalhes_expandidos': {
                'agentes_info': {
                    'agente_coleta': fornecedor_col,
                    'transferencia': fornecedor_transf,
                    'agente_entrega': 'N/A - Rota parcial',
                    'base_origem': transferencia_linha.get('Base Origem', 'Base de Origem'),
                    'base_destino': transferencia_linha.get('Base Destino', 'Base de Destino')
                },
                'rota_info': {
                    'origem': origem,
                    'destino': destino,
                    'peso_cubado': peso_cubado,
                    'tipo_peso_usado': 'Cubado'
                },
                'custos_detalhados': {
                    'custo_base_frete': custo_coleta['custo_base'] + custo_transferencia['custo_base'],
                    'custo_coleta': custo_coleta['total'],
                    'custo_transferencia': custo_transferencia['total'],
                    'custo_entrega': 0,
                    'pedagio': custo_coleta['pedagio'] + custo_transferencia['pedagio'],
                    'gris': custo_coleta['gris'] + custo_transferencia['gris'],
                    'seguro': custo_coleta.get('seguro', 0) + custo_transferencia.get('seguro', 0),
                    'icms': 0,
                    'outros': 0
                },
                'observacoes': f"Rota parcial: Coleta + Transferência. Agente de entrega não encontrado para {destino}. {fornecedor_col} → {fornecedor_transf}"
            }
        }
        
    except Exception as e:
        print(f"[ROTA_PARCIAL_CT] ❌ Erro: {e}")
        return None

def conectar_base_postgresql():
    """Conecta diretamente ao banco de dados configurado"""
    try:
        print("[DATABASE] 🔄 Conectando ao banco Neon...")
        
        # Verificar se banco está disponível
        if not POSTGRESQL_AVAILABLE:
            print("[DATABASE] ❌ Banco de dados não disponível")
            return False
        
        # Verificar conexão
        try:
            db.session.execute(text('SELECT 1'))
            print("[DATABASE] ✅ Conexão Neon estabelecida")
        except Exception as e:
            print(f"[DATABASE] ❌ Erro na conexão Neon: {e}")
            return False
        
        # Contar registros existentes
        total_registros = BaseUnificada.query.count()
        print(f"[DATABASE] 📊 Total de registros na base: {total_registros}")
        
        if total_registros == 0:
            print("[DATABASE] ⚠️ Base de dados vazia - operador deve inserir dados via painel admin")
        else:
            print("[DATABASE] ✅ Base de dados carregada com dados reais")
        
        return True
        
    except Exception as e:
        print(f"[DATABASE] ❌ Erro ao conectar: {e}")
        return False

# Conectar ao PostgreSQL na inicialização
with app.app_context():
    conectar_base_postgresql()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 PortoEx iniciando na porta {port}")
    print("✅ Sistema saneado e otimizado")
    app.run(host="0.0.0.0", port=port, debug=True)
