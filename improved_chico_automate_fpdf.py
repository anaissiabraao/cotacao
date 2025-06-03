import pandas as pd
import datetime
import math
import requests
import polyline
from fpdf import FPDF
from flask import Flask, render_template_string, request, jsonify, send_file, redirect, url_for, session, flash
import io
import os
import re
import unicodedata
import json
import uuid
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Lista de estados como fallback
ESTADOS_FALLBACK = [
    {"id": "AC", "text": "Acre"}, {"id": "AL", "text": "Alagoas"}, {"id": "AP", "text": "Amapá"},
    {"id": "AM", "text": "Amazonas"}, {"id": "BA", "text": "Bahia"}, {"id": "CE", "text": "Ceará"},
    {"id": "DF", "text": "Distrito Federal"}, {"id": "ES", "text": "Espírito Santo"}, {"id": "GO", "text": "Goiás"},
    {"id": "MA", "text": "Maranhão"}, {"id": "MT", "text": "Mato Grosso"}, {"id": "MS", "text": "Mato Grosso do Sul"},
    {"id": "MG", "text": "Minas Gerais"}, {"id": "PA", "text": "Pará"}, {"id": "PB", "text": "Paraíba"},
    {"id": "PR", "text": "Paraná"}, {"id": "PE", "text": "Pernambuco"}, {"id": "PI", "text": "Piauí"},
    {"id": "RJ", "text": "Rio de Janeiro"}, {"id": "RN", "text": "Rio Grande do Norte"}, {"id": "RS", "text": "Rio Grande do Sul"},
    {"id": "RO", "text": "Rondônia"}, {"id": "RR", "text": "Roraima"}, {"id": "SC", "text": "Santa Catarina"},
    {"id": "SP", "text": "São Paulo"}, {"id": "SE", "text": "Sergipe"}, {"id": "TO", "text": "Tocantins"}
]

def normalizar_cidade(cidade):
    if not cidade:
        return ""
    # Converter para string e remover acentos
    cidade = str(cidade)
    cidade = ''.join(c for c in unicodedata.normalize('NFD', cidade) if unicodedata.category(c) != 'Mn')
    # Remover caracteres especiais e converter para maiúsculas
    cidade = re.sub(r'[^a-zA-Z0-9\s]', '', cidade).strip().upper()
    # Remover espaços extras
    cidade = re.sub(r'\s+', ' ', cidade)
    # Remover sufixos comuns
    cidade = re.sub(r'\s+(SP|RJ|MG|PR|SC|RS|BA|PE|CE|DF|GO|MT|MS|RO|AC|AP|AM|PA|PB|PI|MA|RN|SE|AL|ES|TO|RR)$', '', cidade)
    return cidade

def normalizar_uf(uf):
    # Trata abreviações e nomes completos
    if not uf:
        return ""
    uf = uf.strip().upper()
    # Exemplo: pode expandir para tratar mais casos se necessário
    if uf in ["SAO", "SÃO", "SAO PAULO", "SÃO PAULO", "SAO PAULO - SP", "SÃO PAULO - SP"]:
        return "SP"
    return uf[:2]  # Pega só a sigla se vier "SAO PAULO - SP"

def normalizar_cidade_nome(cidade):
    if not cidade:
        return ""
    # Primeiro remove tudo após o hífen
    cidade = str(cidade).split("-")[0].strip()
    # Depois normaliza
    return normalizar_cidade(cidade)

def buscar_valor_padrao(row, campo):
    nomes = [campo]
    if campo == "uf_origem":
        nomes = ["uf_origem", "UF ORIGEM"]
    elif campo == "cidade_origem":
        nomes = ["cidade_origem", "Origem"]
    elif campo == "uf_destino":
        nomes = ["uf_destino", "UF DESTINO"]
    elif campo == "cidade_destino":
        nomes = ["cidade_destino", "Destino"]
    for nome in nomes:
        if nome in row and pd.notnull(row[nome]):
            return row[nome]
    return None

def ler_linha_padronizada(row):
    return {
        "uf_origem": buscar_valor_padrao(row, "uf_origem"),
        "cidade_origem": buscar_valor_padrao(row, "cidade_origem"),
        "uf_destino": buscar_valor_padrao(row, "uf_destino"),
        "cidade_destino": buscar_valor_padrao(row, "cidade_destino"),
        "fornecedor": row.get("fornecedor", ""),
        "custo_base": row.get("custo_base", 0),
        "excedente": row.get("excedente", 0),
        "peso_max": row.get("peso_max", 0),
        "gris_min": row.get("gris_min", 0),
        "gris": row.get("gris", 0),
        "pedagio": row.get("pedagio", 0),
        "prazo_economico": row.get("prazo_economico", 0),
        "prazo_expresso": row.get("prazo_expresso", 0),
        "dfl": row.get("dfl", 0),
        "valor_min": row.get("custo_base", 0),
        "faixa_peso": row.get("faixa_peso", ""),
        "tipo": row.get("tipo", ""),
        "origem_dados": row.get("origem_dados", "")
    }

def buscar_opcao_unificada(df, uf_origem, cidade_origem, uf_destino, cidade_destino, peso, cubagem):
    uf_origem_norm = normalizar_uf(uf_origem)
    uf_destino_norm = normalizar_uf(uf_destino)
    cidade_origem_norm = normalizar_cidade_nome(cidade_origem)
    cidade_destino_norm = normalizar_cidade_nome(cidade_destino)
    resultados = []
    for _, row in df.iterrows():
        linha = ler_linha_padronizada(row)
        if (
            normalizar_uf(linha["uf_origem"]) == uf_origem_norm and
            normalizar_cidade_nome(linha["cidade_origem"]) == cidade_origem_norm and
            normalizar_uf(linha["uf_destino"]) == uf_destino_norm and
            normalizar_cidade_nome(linha["cidade_destino"]) == cidade_destino_norm
        ):
            try:
                custo_base = float(linha.get("custo_base") or 0)
                excedente = float(linha.get("excedente") or 0)
                peso_cubado = max(peso, cubagem * 300)
                if peso_cubado <= 10:
                    custo = custo_base
                else:
                    custo = custo_base + (peso_cubado - 10) * excedente
                resultados.append({
                    "fornecedor": linha.get("fornecedor", ""),
                    "custo": round(custo, 2),
                    "prazo": int(linha.get("prazo_economico") or 0),
                    "uf_origem": linha.get("uf_origem", ""),
                    "cidade_origem": linha.get("cidade_origem", ""),
                    "uf_destino": linha.get("uf_destino", ""),
                    "cidade_destino": linha.get("cidade_destino", ""),
                })
            except Exception as e:
                print(f"Erro ao calcular custo para linha: {e}")
    return resultados

# NOVAS FUNÇÕES PARA CÁLCULO FRACIONADO A+B+C+D+E

def validar_peso_cubagem(peso, cubagem):
    """
    Valida peso e cubagem, retornando valores normalizados
    Versão melhorada com validações mais rigorosas
    """
    try:
        # Converter para float
        peso = float(peso)
        cubagem = float(cubagem)
        
        # Validar peso
        if peso <= 0:
            raise ValueError("O peso deve ser maior que zero")
        if peso > 10000:  # Limite máximo de 10 toneladas
            raise ValueError("O peso não pode ser maior que 10.000 kg")
        
        # Validar cubagem
        if cubagem < 0:
            raise ValueError("A cubagem não pode ser negativa")
        if cubagem > 100:  # Limite máximo de 100m³
            raise ValueError("A cubagem não pode ser maior que 100m³")
        
        # Calcular peso cubado
        peso_cubado = max(peso, cubagem * 300)
        
        # Validar relação peso/cubagem
        if peso_cubado > 10000:
            raise ValueError(f"O peso cubado ({peso_cubado:.2f}kg) não pode ser maior que 10.000 kg")
        
        # Validar densidade mínima
        densidade = peso / cubagem if cubagem > 0 else float('inf')
        if densidade < 10:  # Densidade mínima de 10kg/m³
            raise ValueError(f"Densidade muito baixa: {densidade:.2f}kg/m³ (mínimo: 10kg/m³)")
        
        # Validar densidade máxima
        if densidade > 1000:  # Densidade máxima de 1000kg/m³
            raise ValueError(f"Densidade muito alta: {densidade:.2f}kg/m³ (máximo: 1000kg/m³)")
        
        return peso, cubagem
        
    except ValueError as ve:
        raise ValueError(f"Erro na validação de peso/cubagem: {str(ve)}")
    except Exception as e:
        raise ValueError(f"Erro ao processar peso/cubagem: {str(e)}")

def calcular_peso_cubado(peso, cubagem):
    """
    Calcula o peso cubado baseado no peso real e cubagem
    """
    peso, cubagem = validar_peso_cubagem(peso, cubagem)
    return max(peso, cubagem * 300)

# Listas ampliadas de colunas possíveis
COLUNAS_UF = ['UF', 'UF ORIGEM', 'uf_origem', 'Sigla Origem', 'unidade_origem', 'UF DESTINO', 'uf_destino', 'Sigla Destino']
COLUNAS_CIDADE = ['CIDADES', 'Origem', 'unidade_origem', 'CIDADE_PADRONIZADA', 'cidade_origem', 'Destino', 'cidade_destino']

def buscar_agentes_por_tipo(df, tipo, uf, cidade, peso, cubagem, etapa):
    """
    Busca agentes ou companhias de transferência por tipo, UF e cidade
    Agora busca em todas as colunas possíveis e aceita se qualquer uma bater.
    """
    try:
        uf = normalizar_uf(uf)
        cidade = normalizar_cidade(cidade)
        print(f"Buscando {tipo} para {cidade}-{uf} (etapa {etapa})")
        mask = pd.Series(True, index=df.index)
        # Filtrar por tipo/classificação
        if 'CLASSIFICACAO' in df.columns:
            mask &= df['CLASSIFICACAO'].str.upper() == tipo.upper()
        elif 'TIPO' in df.columns:
            mask &= df['TIPO'].str.upper() == tipo.upper()
        # Filtrar por UF (qualquer coluna)
        uf_mask = pd.Series(False, index=df.index)
        for col in COLUNAS_UF:
            if col in df.columns:
                uf_mask |= df[col].apply(lambda x: normalizar_uf(x) if pd.notna(x) else "") == uf
        mask &= uf_mask
        # Filtrar por cidade (qualquer coluna)
        cidade_mask = pd.Series(False, index=df.index)
        for col in COLUNAS_CIDADE:
            if col in df.columns:
                cidade_mask |= df[col].apply(lambda x: normalizar_cidade(str(x)) if pd.notna(x) else "") == cidade
        mask &= cidade_mask
        df_filtrado = df[mask].copy()
        if df_filtrado.empty:
            print(f"Nenhum {tipo} encontrado para {cidade}-{uf}")
            return []
        print(f"Encontrados {len(df_filtrado)} registros para {tipo} em {cidade}-{uf}")
        resultados = []
        for _, row in df_filtrado.iterrows():
            fornecedor = row.get('FORNECEDOR')
            custo_base = next((float(row[col]) for col in ['VALOR MÍNIMO ATÉ 10', 'Minima (Até 10 Kgs) Desconto', 'ATÉ 10'] if col in df.columns and pd.notna(row[col])), None)
            excedente = next((float(row[col]) for col in ['EXCEDENTE', 'Excedente (Até 20 kgs) Desconto', 'ACIMA 10 Kg'] if col in df.columns and pd.notna(row[col])), None)
            peso_max = next((float(row[col]) for col in ['PESO MÁXIMO TRANSPORTADO'] if col in df.columns and pd.notna(row[col])), None)
            gris = next((float(row[col]) for col in ['GRIS', 'Gris Min', 'GRIS MÍNIMO'] if col in df.columns and pd.notna(row[col])), 0.0)
            prazo = next((int(row[col]) for col in ['PRAZO ECON', 'PRAZO', 'prazo'] if col in df.columns and pd.notna(row[col])), None)
            if not all([fornecedor, custo_base is not None, excedente is not None, peso_max is not None]):
                continue
            peso_cubado = max(peso, cubagem * 300)
            if peso_cubado > peso_max:
                continue
            if peso_cubado <= 10:
                custo = custo_base
            else:
                custo = custo_base + (peso_cubado - 10) * excedente
            custo += custo * gris
            resultado = {
                "fornecedor": fornecedor,
                "custo": round(custo, 2),
                "prazo": prazo or 0,
                "etapa": etapa,
                "tipo": tipo,
                "peso_maximo": peso_max,
                "custo_base": custo_base,
                "excedente": excedente,
                "gris": gris,
                "uf": uf,
                "cidade": cidade
            }
            resultados.append(resultado)
        print(f"Retornando {len(resultados)} resultados válidos para {tipo} em {cidade}-{uf}")
        return resultados
    except Exception as e:
        print(f"Erro ao buscar {tipo}: {e}")
        return []

def calcular_fracionado_completo(df, uf_origem, cidade_origem, uf_destino, cidade_destino, peso, cubagem):
    """
    Calcula o frete fracionado completo com as 5 etapas A+B+C+D+E
    Versão melhorada com validações e tratamento de erros
    """
    try:
        # Validar entradas
        peso, cubagem = validar_peso_cubagem(peso, cubagem)
        peso_cubado = max(peso, cubagem * 300)
        
        # Log para debug
        print(f"Calculando frete fracionado:")
        print(f"Origem: {cidade_origem}-{uf_origem}")
        print(f"Destino: {cidade_destino}-{uf_destino}")
        print(f"Peso: {peso}kg, Cubagem: {cubagem}m³, Peso Cubado: {peso_cubado}kg")
        
        # Etapa A: Agente coleta origem
        agentes_origem = buscar_agentes_por_tipo(df, 'Agentes', uf_origem, cidade_origem, peso, cubagem, 'A')
        print(f"Agentes origem encontrados: {len(agentes_origem)}")
        
        # Etapa B: Cia de Transferência recebe da origem
        cias_origem = buscar_agentes_por_tipo(df, 'Cia de Transferência', uf_origem, cidade_origem, peso, cubagem, 'B')
        print(f"Cias origem encontradas: {len(cias_origem)}")
        
        # Etapa C: Cia de Transferência próxima ao destino
        cias_destino = buscar_agentes_por_tipo(df, 'Cia de Transferência', uf_destino, cidade_destino, peso, cubagem, 'C')
        print(f"Cias destino encontradas: {len(cias_destino)}")
        
        # Etapa D: Agente coleta da Cia de Transferência
        agentes_cia_destino = buscar_agentes_por_tipo(df, 'Agentes', uf_destino, cidade_destino, peso, cubagem, 'D')
        print(f"Agentes destino encontrados: {len(agentes_cia_destino)}")
        
        # Etapa E: Entrega final porta a porta
        agentes_entrega_final = buscar_agentes_por_tipo(df, 'Agentes', uf_destino, cidade_destino, peso, cubagem, 'E')
        print(f"Agentes entrega final encontrados: {len(agentes_entrega_final)}")
        
        # Verificar disponibilidade de etapas
        etapas_disponiveis = {
            "A_agentes_origem": len(agentes_origem),
            "B_cias_origem": len(cias_origem),
            "C_cias_destino": len(cias_destino),
            "D_agentes_cia_destino": len(agentes_cia_destino),
            "E_agentes_entrega_final": len(agentes_entrega_final)
        }
        
        # Verificar se há pelo menos uma opção para cada etapa
        etapas_obrigatorias = ['A_agentes_origem', 'E_agentes_entrega_final']
        etapas_faltantes = [etapa for etapa in etapas_obrigatorias if etapas_disponiveis[etapa] == 0]
        
        if etapas_faltantes:
            raise ValueError(f"Etapas obrigatórias não disponíveis: {', '.join(etapas_faltantes)}")
        
        # Calcular combinações possíveis
        combinacoes = []
        
        # Combinar agentes de origem com cias de transferência
        for agente_origem in agentes_origem:
            for cia_origem in cias_origem:
                # Combinar com cias de destino
                for cia_destino in cias_destino:
                    # Combinar com agentes de destino
                    for agente_destino in agentes_cia_destino:
                        # Combinar com agentes de entrega final
                        for agente_entrega in agentes_entrega_final:
                            # Calcular custo total
                            custo_total = (
                                agente_origem["custo"] +
                                cia_origem["custo"] +
                                cia_destino["custo"] +
                                agente_destino["custo"] +
                                agente_entrega["custo"]
                            )
                            
                            # Calcular prazo total (máximo entre as etapas)
                            prazo_total = max(
                                agente_origem["prazo"],
                                cia_origem["prazo"],
                                cia_destino["prazo"],
                                agente_destino["prazo"],
                                agente_entrega["prazo"]
                            )
                            
                            combinacao = {
                                "custo_total": round(custo_total, 2),
                                "prazo_total": prazo_total,
                                "etapas": {
                                    "A": agente_origem,
                                    "B": cia_origem,
                                    "C": cia_destino,
                                    "D": agente_destino,
                                    "E": agente_entrega
                                },
                                "fornecedores": [
                                    agente_origem["fornecedor"],
                                    cia_origem["fornecedor"],
                                    cia_destino["fornecedor"],
                                    agente_destino["fornecedor"],
                                    agente_entrega["fornecedor"]
                                ]
                            }
                            
                            combinacoes.append(combinacao)
        
        # Ordenar combinações por custo total
        combinacoes.sort(key=lambda x: x["custo_total"])
        
        print(f"Total de combinações encontradas: {len(combinacoes)}")
        
        return {
            "combinacoes": combinacoes,
            "melhor_opcao": combinacoes[0] if combinacoes else None,
            "total_combinacoes": len(combinacoes),
            "etapas_disponiveis": etapas_disponiveis,
            "peso_cubado": peso_cubado,
            "peso_original": peso,
            "cubagem_original": cubagem
        }
        
    except Exception as e:
        print(f"Erro no cálculo fracionado: {e}")
        raise ValueError(f"Erro no cálculo do frete fracionado: {str(e)}")

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')  # Usar variável de ambiente
app.config['SESSION_COOKIE_SECURE'] = True  # Forçar HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevenir acesso via JavaScript
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=24)  # Sessão de 24 horas

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Usuário fixo
USERS = {
    'portoex': {
        'password': 'portoex@123'
    }
}

class User(UserMixin):
    def __init__(self, username):
        self.id = username

    def get_id(self):
        return self.id

@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS:
        return User(user_id)
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USERS and USERS[username]['password'] == password:
            user = User(username)
            login_user(user)
            flash('Login realizado com sucesso!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso.', 'info')
    return redirect(url_for('login'))

# NOVA BASE DE DADOS
# Tentar diferentes caminhos possíveis para o arquivo Excel
import os

possible_paths = [
    "base_unificada_cidades_padronizadas.xlsx",  # Mesmo diretório do script
    "C:\\Users\\Usuário\\OneDrive\\Desktop\\SQL data\\Chico automate\\base_unificada_cidades_padronizadas.xlsx",
]

EXCEL_FILE = None
for path in possible_paths:
    if os.path.exists(path):
        EXCEL_FILE = path
        break

if EXCEL_FILE is None:
    print("ERRO: Arquivo Excel não encontrado. Coloque o arquivo 'base_unificada_cidades_padronizadas.xlsx' no mesmo diretório do script.")
    print("Caminhos testados:")
    for path in possible_paths:
        print(f"  - {path}")
    exit(1)

print(f"Carregando base de dados: {EXCEL_FILE}")

# Carregar a base unificada (apenas Sheet1)
df_unificado = pd.read_excel(EXCEL_FILE, sheet_name='Sheet1')

# --- Normalização automática robusta das colunas de UF e cidade (origem/destino) ---
# Mapeamento de possíveis nomes de colunas para origem e destino
colunas_uf_origem = [
    'uf_origem', 'UF ORIGEM', 'UF', 'Sigla Origem', 'unidade_origem'
]
colunas_cidade_origem = [
    'cidade_origem', 'Origem', 'CIDADES', 'unidade_origem'
]
colunas_uf_destino = [
    'uf_destino', 'UF DESTINO', 'Sigla Destino', 'UF'
]
colunas_cidade_destino = [
    'cidade_destino', 'Destino', 'CIDADES'
]

def buscar_primeira_coluna_existente(df, lista):
    for col in lista:
        if col in df.columns:
            return col
    return None

# Normalizar e criar colunas padronizadas
col_uf_origem = buscar_primeira_coluna_existente(df_unificado, colunas_uf_origem)
col_cidade_origem = buscar_primeira_coluna_existente(df_unificado, colunas_cidade_origem)
col_uf_destino = buscar_primeira_coluna_existente(df_unificado, colunas_uf_destino)
col_cidade_destino = buscar_primeira_coluna_existente(df_unificado, colunas_cidade_destino)

df_unificado['uf_origem'] = df_unificado[col_uf_origem].apply(lambda x: normalizar_uf(x) if pd.notnull(x) else "") if col_uf_origem else ""
df_unificado['cidade_origem'] = df_unificado[col_cidade_origem].apply(lambda x: normalizar_cidade_nome(x) if pd.notnull(x) else "") if col_cidade_origem else ""
df_unificado['uf_destino'] = df_unificado[col_uf_destino].apply(lambda x: normalizar_uf(x) if pd.notnull(x) else "") if col_uf_destino else ""
df_unificado['cidade_destino'] = df_unificado[col_cidade_destino].apply(lambda x: normalizar_cidade_nome(x) if pd.notnull(x) else "") if col_cidade_destino else ""
# --- Fim da normalização robusta ---

# Manter a base original para o novo cálculo fracionado A+B+C+D+E
# Criar uma versão filtrada para compatibilidade com o código existente
df_unificado_legacy = df_unificado.copy()

# Verificar se as colunas necessárias existem para o modo legacy
colunas_legacy = ["UF ORIGEM", "Origem", "UF DESTINO", "Destino", "FORNECEDOR", "VALOR MÍNIMO ATÉ 10", "EXCEDENTE", "PESO MÁXIMO TRANSPORTADO", "GRIS MÍNIMO", "GRIS", "PEDAGIO", "PRAZO ECON", "PRAZO EXPRESSO", "DFL", "Faixa", "TIPO", "ORIGEM_DADOS"]
colunas_existentes = [col for col in colunas_legacy if col in df_unificado_legacy.columns]

if len(colunas_existentes) > 0:
    df_unificado_legacy = df_unificado_legacy[colunas_existentes]
    # Renomear colunas para padronização (apenas para compatibilidade)
    rename_map = {
        "UF ORIGEM": "uf_origem", "Origem": "cidade_origem", "UF DESTINO": "uf_destino", "Destino": "cidade_destino",
        "FORNECEDOR": "fornecedor", "VALOR MÍNIMO ATÉ 10": "custo_base", "EXCEDENTE": "excedente",
        "PESO MÁXIMO TRANSPORTADO": "peso_max", "GRIS MÍNIMO": "gris_min", "GRIS": "gris",
        "PEDAGIO": "pedagio", "PRAZO ECON": "prazo_economico", "PRAZO EXPRESSO": "prazo_expresso", "DFL": "dfl",
        "Faixa": "faixa_peso", "TIPO": "tipo", "ORIGEM_DADOS": "origem_dados"
    }
    df_unificado_legacy.rename(columns=rename_map, inplace=True)

CONTADOR_FRACIONADO = 1
CONTADOR_DEDICADO = 1

HISTORICO_PESQUISAS = []

def geocode(municipio, uf):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": f"{municipio}, {uf}, Brasil", "format": "json", "limit": 1}
    headers = {"User-Agent": "TransportCostCalculator/1.0"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        if data:
            return (float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", ""))
        return None
    except Exception as e:
        print(f"Erro ao geocodificar: {e}")
        return None

def calcular_distancia_osrm(origem, destino):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{origem[1]},{origem[0]};{destino[1]},{destino[0]}"
        response = requests.get(url, params={"overview": "full"}, timeout=15)
        data = response.json()
        if data.get("code") == "Ok" and data.get("routes"):
            route = data["routes"][0]
            distance = route["distance"] / 1000
            duration = route["duration"] / 60
            geometry = route.get("geometry", "")
            route_points = polyline.decode(geometry) if geometry else []
            return {"distance": distance, "duration": duration, "route_points": route_points, "provider": "OSRM"}
        return None
    except Exception as e:
        print(f"Erro ao calcular rota OSRM: {e}")
        return None

def calcular_distancia_openroute(origem, destino):
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {"Accept": "application/json"}
        params = {"start": f"{origem[1]},{origem[0]}", "end": f"{destino[1]},{destino[0]}"}
        response = requests.get(url, headers=headers, params=params, timeout=15)
        data = response.json()
        if "features" in data and data["features"]:
            route = data["features"][0]
            segments = route.get("properties", {}).get("segments", [{}])[0]
            distance = segments.get("distance", 0) / 1000
            duration = segments.get("duration", 0) / 60
            geometry = route.get("geometry", {})
            route_points = [[coord[1], coord[0]] for coord in geometry.get("coordinates", [])]
            return {"distance": distance, "duration": duration, "route_points": route_points, "provider": "OpenRouteService"}
        return None
    except Exception as e:
        print(f"Erro ao calcular rota OpenRouteService: {e}")
        return None

def calcular_distancia_reta(origem, destino):
    try:
        lat1, lon1 = origem[0], origem[1]
        lat2, lon2 = destino[0], destino[1]
        R = 6371
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        duration = (distance / 80) * 60
        route_points = [[lat1, lon1], [lat2, lon2]]
        return {"distance": distance, "duration": duration, "route_points": route_points, "provider": "Linha Reta"}
    except Exception as e:
        print(f"Erro ao calcular distância em linha reta: {e}")
        return None

def determinar_faixa(distancia):
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

def calcular_valor_fracionado(peso, cubagem, transportadora_data):
    peso_cubado = max(peso, cubagem * 300)
    if peso_cubado <= 10:
        custo_base = transportadora_data["10kg"]
    else:
        custo_base = transportadora_data["10kg"] + (peso_cubado - 10) * transportadora_data["excedente"]
    return custo_base

# Tabela fixa de custos para frete dedicado por faixa de distância e tipo de veículo
TABELA_CUSTOS_DEDICADO = {
    "0-20": {"VAN": 250, "3/4": 350, "TOCO": 450, "TRUCK": 550, "CARRETA": 1000},
    "20-50": {"VAN": 350, "3/4": 450, "TOCO": 550, "TRUCK": 700, "CARRETA": 1500},
    "50-100": {"VAN": 600, "3/4": 900, "TOCO": 1200, "TRUCK": 1500, "CARRETA": 2100},
    "100-150": {"VAN": 800, "3/4": 1100, "TOCO": 1500, "TRUCK": 1800, "CARRETA": 2600},
    "150-200": {"VAN": 1000, "3/4": 1500, "TOCO": 1800, "TRUCK": 2100, "CARRETA": 3000},
    "200-250": {"VAN": 1300, "3/4": 1800, "TOCO": 2100, "TRUCK": 2500, "CARRETA": 3300},
    "250-300": {"VAN": 1500, "3/4": 2100, "TOCO": 2500, "TRUCK": 2800, "CARRETA": 3800},
    "300-400": {"VAN": 1800, "3/4": 2500, "TOCO": 2800, "TRUCK": 3300, "CARRETA": 4300},
    "400-600": {"VAN": 2100, "3/4": 2900, "TOCO": 3500, "TRUCK": 3800, "CARRETA": 4800},
    "600-800": {"VAN": 2500, "3/4": 3300, "TOCO": 4000, "TRUCK": 4500, "CARRETA": 5500},
    "800-1000": {"VAN": 2900, "3/4": 3700, "TOCO": 4500, "TRUCK": 5200, "CARRETA": 6200},
    "1000-1500": {"VAN": 3500, "3/4": 4500, "TOCO": 5500, "TRUCK": 6500, "CARRETA": 8000},
    "1500-2000": {"VAN": 4500, "3/4": 5800, "TOCO": 7000, "TRUCK": 8500, "CARRETA": 10500},
    "2000-2500": {"VAN": 5500, "3/4": 7100, "TOCO": 8500, "TRUCK": 10500, "CARRETA": 13000},
    "2500-3000": {"VAN": 6500, "3/4": 8400, "TOCO": 10000, "TRUCK": 12500, "CARRETA": 15500},
    "3000-3500": {"VAN": 7500, "3/4": 9700, "TOCO": 11500, "TRUCK": 14500, "CARRETA": 18000},
    "3500-4000": {"VAN": 8500, "3/4": 11000, "TOCO": 13000, "TRUCK": 16500, "CARRETA": 20500},
    "4000-4500": {"VAN": 9500, "3/4": 12300, "TOCO": 14500, "TRUCK": 18500, "CARRETA": 23000},
    "4500-6000": {"VAN": 11000, "3/4": 14000, "TOCO": 17000, "TRUCK": 21000, "CARRETA": 27000},
}

def calcular_custos_dedicado(df, uf_origem, municipio_origem, uf_destino, municipio_destino, distancia):
    """
    Calcula custos para diferentes tipos de veículos no frete dedicado
    baseado na distância entre origem e destino, usando tabela fixa
    """
    faixa = determinar_faixa(distancia)
    custos = {}
    if faixa and faixa in TABELA_CUSTOS_DEDICADO:
        tabela = TABELA_CUSTOS_DEDICADO[faixa]
        for tipo_veiculo, valor in tabela.items():
            custos[tipo_veiculo] = valor
    else:
        # Se não encontrar faixa, retorna vazio ou None
        custos = {"erro": "Faixa de distância não encontrada para o dedicado."}
    return custos

def gerar_analise_trajeto(origem_info, destino_info, rota_info, custos, tipo="Dedicado"):
    global CONTADOR_DEDICADO
    
    origem_nome = origem_info[2] if len(origem_info) > 2 else "Origem"
    destino_nome = destino_info[2] if len(destino_info) > 2 else "Destino"
    horas = int(rota_info["duration"] // 60)
    minutos = int(rota_info["duration"] % 60)
    tempo_estimado = f"{horas}h {minutos}min" if horas > 0 else f"{minutos}min"
    consumo_combustivel = rota_info["distance"] / 10
    emissao_co2 = consumo_combustivel * 2.3
    pedagio_estimado = rota_info["distance"] * 0.15
    
    id_historico = f"#{tipo}{CONTADOR_DEDICADO:03d}"
    if tipo == "Dedicado":
        CONTADOR_DEDICADO += 1
    
    analise = {
        "id_historico": id_historico,
        "tipo": tipo,
        "origem": origem_nome,
        "destino": destino_nome,
        "distancia": round(rota_info["distance"], 2),
        "tempo_estimado": tempo_estimado,
        "duracao_minutos": round(rota_info["duration"], 2),
        "consumo_combustivel": round(consumo_combustivel, 2),
        "emissao_co2": round(emissao_co2, 2),
        "pedagio_estimado": round(pedagio_estimado, 2),
        "provider": rota_info["provider"],
        "custos": custos,
        "data_hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "rota_pontos": rota_info["route_points"]
    }
    return analise

def get_municipios_uf(uf):
    try:
        response = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios", timeout=10)
        response.raise_for_status()
        data = response.json()
        return {normalizar_cidade(m["nome"]): m["nome"].title() for m in data}
    except Exception as e:
        print(f"Erro ao carregar municípios do IBGE para UF {uf}: {e}")
        return {}

def filtrar_por_fornecedor(transportadoras):
    fornecedores_unicos = {}
    for t in transportadoras:
        fornecedor = t["fornecedor"]
        if fornecedor not in fornecedores_unicos or t["custo"] < fornecedores_unicos[fornecedor]["custo"]:
            fornecedores_unicos[fornecedor] = t
    return list(fornecedores_unicos.values())

def registrar_pesquisa_fracionada(dados, calcular_dedicado=False):
    global CONTADOR_FRACIONADO, HISTORICO_PESQUISAS
    
    id_historico = f"#Fracionado{CONTADOR_FRACIONADO:03d}"
    CONTADOR_FRACIONADO += 1
    
    tipo_registro = "Fracionado"
    if calcular_dedicado:
        tipo_registro = "Fracionado + Dedicado"
    
    registro = {
        "id_historico": id_historico,
        "tipo": tipo_registro,
        "origem": f"{dados['cidades_origem']} - {dados['uf_origem']}",
        "destino": f"{dados['cidades_destino']} - {dados['uf_destino']}",
        "peso": dados["peso"],
        "cubagem": dados["cubagem"],
        "distancia": dados.get("distancia"),
        "data_hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "melhor_preco": dados.get("melhor_preco"),
        "melhor_prazo": dados.get("melhor_prazo"),
        "fornecedores": dados.get("todos_agentes", []),
        "route_points": dados.get("route_points"),
        "ranking": dados.get("ranking", []),
        "ranking_completo": dados.get("ranking_completo", []),
    }
    
    if calcular_dedicado and "dedicado_resultado" in dados:
        registro["dedicado"] = dados["dedicado_resultado"]
    
    HISTORICO_PESQUISAS.append(registro)
    
    if len(HISTORICO_PESQUISAS) > 50:
        HISTORICO_PESQUISAS.pop(0)
    
    return id_historico

class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def header(self):
        self.set_font("helvetica", "B", 15)
        self.cell(0, 10, "PortoEx - Relatório de Transporte", 0, new_x="LMARGIN", new_y="NEXT", align="C")
        self.line(10, 20, 200, 20)
        self.ln(10)
        
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", 0, 0, "C")
        self.cell(0, 10, f"© {datetime.datetime.now().year} PortoEx - Todos os direitos reservados", 0, 0, "R")

@app.route("/")
@login_required
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/estados")
@login_required
def estados():
    try:
        response = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados", timeout=10)
        response.raise_for_status()
        data = response.json()
        estados = [{"id": e["sigla"], "text": e["nome"]} for e in sorted(data, key=lambda x: x["nome"])]
        return jsonify(estados)
    except Exception as e:
        print(f"Erro ao carregar estados da API IBGE: {e}. Usando fallback.")
        return jsonify(ESTADOS_FALLBACK)

@app.route("/municipios/<uf>")
@login_required
def municipios(uf):
    try:
        response = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios", timeout=10)
        response.raise_for_status()
        data = response.json()
        municipios = [{"id": normalizar_cidade(m["nome"]), "text": m["nome"].title()} for m in sorted(data, key=lambda x: x["nome"])]
        return jsonify(municipios)
    except Exception as e:
        print(f"Erro ao carregar municípios para UF {uf}: {e}")
        return jsonify([])

@app.route("/historico")
@login_required
def historico():
    return jsonify(HISTORICO_PESQUISAS)

@app.route("/calcular", methods=["POST"])
@login_required
def calcular():
    data = request.json
    municipio_origem = data["municipio_origem"]
    uf_origem = data["uf_origem"]
    municipio_destino = data["municipio_destino"]
    uf_destino = data["uf_destino"]
    peso = float(data.get("peso", 0))
    cubagem = float(data.get("cubagem", 0))
    coord_origem = geocode(municipio_origem, uf_origem)
    coord_destino = geocode(municipio_destino, uf_destino)
    if not coord_origem or not coord_destino:
        return jsonify({"error": "Não foi possível identificar os locais"}), 400
    rota_info = calcular_distancia_osrm(coord_origem, coord_destino) or \
                calcular_distancia_openroute(coord_origem, coord_destino) or \
                calcular_distancia_reta(coord_origem, coord_destino)
    if not rota_info:
        return jsonify({"error": "Não foi possível calcular a distância"}), 500
    distancia = rota_info["distance"]
    custos = calcular_custos_dedicado(df_unificado, uf_origem, municipio_origem, uf_destino, municipio_destino, distancia)
    analise = gerar_analise_trajeto(coord_origem, coord_destino, rota_info, custos, "Dedicado")
    HISTORICO_PESQUISAS.append(analise)
    if len(HISTORICO_PESQUISAS) > 50:
        HISTORICO_PESQUISAS.pop(0)
    return jsonify({
        "id_historico": analise["id_historico"],
        "distancia": round(distancia, 2),
        "duracao": round(rota_info["duration"], 2),
        "custos": custos,
        "peso": peso,
        "cubagem": cubagem,
        "rota_pontos": rota_info["route_points"],
        "analise": analise
    })

@app.route("/calcular_frete_fracionado", methods=["POST"])
@login_required
def calcular_frete_fracionado():
    try:
        # Extrair e validar dados do formulário
        uf_origem = request.form.get("estado_origem")
        cidade_origem = request.form.get("municipio_origem")
        uf_destino = request.form.get("estado_destino")
        cidade_destino = request.form.get("municipio_destino")
        peso = request.form.get("peso", "10")
        cubagem = request.form.get("cubagem", "0.05")

        if not all([uf_origem, cidade_origem, uf_destino, cidade_destino]):
            return render_template_string(HTML_TEMPLATE, erro="Todos os campos são obrigatórios.")

        # Calcular frete fracionado
        resultado_fracionado = calcular_fracionado_completo(
            df_unificado, 
            uf_origem, 
            cidade_origem, 
            uf_destino, 
            cidade_destino, 
            peso, 
            cubagem
        )
        
        if not resultado_fracionado["combinacoes"]:
            return render_template_string(
                HTML_TEMPLATE, 
                erro="Não foi possível encontrar combinações completas para o trajeto informado. "
                     "Verifique se existem agentes e companhias de transferência disponíveis para origem e destino."
            )
        
        melhor_opcao = resultado_fracionado["melhor_opcao"]
        
        # Preparar resultado para o template
        resultado = {
            "cidades_origem": cidade_origem,
            "uf_origem": uf_origem,
            "cidades_destino": cidade_destino,
            "uf_destino": uf_destino,
            "peso": float(peso),
            "cubagem": float(cubagem),
            "peso_cubado": resultado_fracionado["peso_cubado"],
            "tipo_calculo": "Fracionado A+B+C+D+E",
            "melhor_opcao": melhor_opcao,
            "custo_total": melhor_opcao["custo_total"],
            "prazo_total": melhor_opcao["prazo_total"],
            "etapas": melhor_opcao["etapas"],
            "fornecedores_completo": melhor_opcao["fornecedores"],
            "total_combinacoes": resultado_fracionado["total_combinacoes"],
            "etapas_disponiveis": resultado_fracionado["etapas_disponiveis"],
            "todas_combinacoes": resultado_fracionado["combinacoes"][:10]  # Limitar a 10 melhores opções
        }
        
        # Registrar no histórico
        id_historico = registrar_pesquisa_fracionada(resultado)
        resultado["id_historico"] = id_historico
        
        return render_template_string(HTML_TEMPLATE, resultado=resultado, historico=HISTORICO_PESQUISAS)
        
    except ValueError as ve:
        return render_template_string(HTML_TEMPLATE, erro=str(ve))
    except Exception as e:
        print(f"Erro ao calcular frete fracionado: {e}")
        return render_template_string(HTML_TEMPLATE, erro=f"Erro ao processar: {str(e)}")

@app.route("/gerar-pdf", methods=["POST"])
@login_required
def gerar_pdf():
    try:
        data = request.json
        analise = data.get("analise", {})
        tipo = analise.get("tipo", "Dedicado")
        
        pdf = PDF()
        pdf.add_page()
        
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 10, "Relatório de Análise de Transporte", 0, new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(5)
        
        if "id_historico" in analise:
            pdf.set_font("helvetica", "B", 12)
            pdf.cell(0, 8, f"ID: {analise.get('id_historico', 'N/A')}", 0, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, f"Rota: {analise.get('origem', 'N/A')} → {analise.get('destino', 'N/A')}", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 8, f"Data/Hora: {analise.get('data_hora', 'N/A')}", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Distância: {analise.get('distancia', 'N/A')} km", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Tempo estimado: {analise.get('tempo_estimado', 'N/A')}", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Consumo estimado: {analise.get('consumo_combustivel', 'N/A')} L", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Emissão de CO₂: {analise.get('emissao_co2', 'N/A')} kg", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Pedágio estimado: R$ {analise.get('pedagio_estimado', 'N/A')}", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        
        if tipo == "Dedicado":
            pdf.set_font("helvetica", "B", 12)
            pdf.cell(0, 10, "Custos por Tipo de Veículo", 0, new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(60, 8, "Tipo de Veículo", 1, 0, "C")
            pdf.cell(60, 8, "Custo (R$)", 1, new_x="LMARGIN", new_y="NEXT", align="C")
            
            pdf.set_font("helvetica", "", 10)
            for tipo_veiculo, custo in analise.get("custos", {}).items():
                pdf.cell(60, 8, tipo_veiculo, 1, 0)
                pdf.cell(60, 8, f"R$ {custo:.2f}", 1, new_x="LMARGIN", new_y="NEXT", align="R")
        else:
            pdf.set_font("helvetica", "B", 12)
            pdf.cell(0, 10, "Detalhamento do Fluxo Fracionado", 0, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(15, 8, "Etapa", 1, 0, "C")
            pdf.cell(45, 8, "Fornecedor", 1, 0, "C")
            pdf.cell(35, 8, "Categoria", 1, 0, "C")
            pdf.cell(30, 8, "Custo (R$)", 1, 0, "C")
            pdf.cell(25, 8, "Prazo", 1, new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.set_font("helvetica", "", 10)
            for etapa in analise.get("etapas", []):
                pdf.cell(15, 8, etapa.get("etapa", ""), 1, 0, "C")
                pdf.cell(45, 8, str(etapa.get("fornecedor", "N/A")), 1, 0)
                pdf.cell(35, 8, str(etapa.get("categoria", "N/A")), 1, 0, "C")
                pdf.cell(30, 8, f"R$ {etapa.get('custo', 0):.2f}", 1, 0, "R")
                pdf.cell(25, 8, str(etapa.get("prazo", "N/A")), 1, new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(5)
            pdf.set_font("helvetica", "B", 11)
            pdf.cell(0, 8, f"Custo Total: R$ {analise.get('custo_total', 0):.2f}", 0, new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 8, f"Prazo Total: {analise.get('prazo_total', 'N/A')} dias", 0, new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(10)
        pdf.set_font("helvetica", "I", 8)
        pdf.cell(0, 8, "Este relatório é gerado automaticamente pelo sistema PortoEx.", 0, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, "Os valores apresentados são estimativas e podem variar conforme condições específicas.", 0, new_x="LMARGIN", new_y="NEXT")
        
        pdf_output = io.BytesIO()
        pdf.output(pdf_output)
        pdf_output.seek(0)
        
        return send_file(
            pdf_output,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"relatorio_{tipo.lower()}.pdf"
        )
    
    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/exportar-excel", methods=["POST"])
@login_required
def exportar_excel():
    try:
        data = request.json
        tipo = data.get("tipo", "Dedicado")
        dados = data.get("dados", {})
        
        output = io.BytesIO();
        
        if tipo == "Dedicado":
            df = pd.DataFrame({
                "Tipo de Veículo": list(dados.get("custos", {}).keys()),
                "Custo (R$)": list(dados.get("custos", {}).values())
            })
            
            info = {
                "ID": [dados.get("id_historico", "N/A")],
                "Origem": [dados.get("origem", "N/A")],
                "Destino": [dados.get("destino", "N/A")],
                "Distância (km)": [dados.get("distancia", "N/A")],
                "Tempo Estimado": [dados.get("tempo_estimado", "N/A")],
                "Data/Hora": [dados.get("data_hora", "N/A")]
            }
            df_info = pd.DataFrame(info)
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_info.to_excel(writer, sheet_name='Informações', index=False)
                df.to_excel(writer, sheet_name='Custos por Veículo', index=False)
        
        else:
            ranking = dados.get("ranking", []);
            if ranking:
                df_ranking = pd.DataFrame(ranking)
                df_ranking.rename(columns={
                    'fornecedor': 'Fornecedor',
                    'categoria': 'Categoria',
                    'custo': 'Custo (R$)',
                    'prazo': 'Prazo (dias)',
                    'gris': 'Gris',
                    'zona_parceiro': 'Zona Parceiro',
                    'nova_zona': 'Nova Zona',
                    'dfl': 'DFL',
                    'peso_maximo': 'Peso Máximo (kg)',
                    'excedente': 'Excedente (R$/kg)'
                }, inplace=True)
                
                info = {
                    "ID": [dados.get("id_historico", "N/A")],
                    "Origem": [f"{dados.get('cidades_origem', 'N/A')} - {dados.get('uf_origem', 'N/A')}`"],
                    "Destino": [f"{dados.get('cidades_destino', 'N/A')} - {dados.get('uf_destino', 'N/A')}`"],
                    "Peso (kg)": [dados.get("peso", "N/A")],
                    "Cubagem (m³)": [dados.get("cubagem", "N/A")],
                    "Distância (km)": [dados.get("distancia", "N/A")],
                    "Data/Hora": [dados.get("data_hora", "N/A")]
                }
                df_info = pd.DataFrame(info)
                
                melhor_pior = {
                    "Categoria": ["Melhor Preço", "Melhor Prazo", "Pior Preço"],
                    "Fornecedor": [
                        dados.get("melhor_preco", {}).get("fornecedor", "N/A"),
                        dados.get("melhor_prazo", {}).get("fornecedor", "N/A"),
                        dados.get("pior_preco", {}).get("fornecedor", "N/A")
                    ],
                    "Tipo": [
                        dados.get("melhor_preco", {}).get("categoria", "N/A"),
                        dados.get("melhor_prazo", {}).get("categoria", "N/A"),
                        dados.get("pior_preco", {}).get("categoria", "N/A")
                    ],
                    "Custo (R$)": [
                        dados.get("melhor_preco", {}).get("custo", "N/A"),
                        dados.get("melhor_prazo", {}).get("custo", "N/A"),
                        dados.get("pior_preco", {}).get("custo", "N/A")
                    ],
                    "Prazo (dias)": [
                        dados.get("melhor_preco", {}).get("prazo", "N/A"),
                        dados.get("melhor_prazo", {}).get("prazo", "N/A"),
                        dados.get("pior_preco", {}).get("prazo", "N/A")
                    ]
                }
                df_melhor_pior = pd.DataFrame(melhor_pior)
                
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_info.to_excel(writer, sheet_name='Informações', index=False)
                    df_ranking.to_excel(writer, sheet_name='Ranking Filtrado', index=False)
                    df_melhor_pior.to_excel(writer, sheet_name='Melhor e Pior', index=False)
                    
                    ranking_completo = dados.get("ranking_completo", [])
                    if ranking_completo:
                        df_completo = pd.DataFrame(ranking_completo)
                        df_completo.rename(columns={
                            'fornecedor': 'Fornecedor',
                            'categoria': 'Categoria',
                            'custo': 'Custo (R$)',
                            'prazo': 'Prazo (dias)',
                            'gris': 'Gris',
                            'zona_parceiro': 'Zona Parceiro',
                            'nova_zona': 'Nova Zona',
                            'dfl': 'DFL',
                            'peso_maximo': 'Peso Máximo (kg)',
                            'excedente': 'Excedente (R$/kg)'
                        }, inplace=True)
                        df_completo.to_excel(writer, sheet_name='Ranking Completo', index=False)
            else:
                info = {
                    "ID": [dados.get("id_historico", "N/A")],
                    "Origem": [f"{dados.get('cidades_origem', 'N/A')} - {dados.get('uf_origem', 'N/A')}`"],
                    "Destino": [f"{dados.get('cidades_destino', 'N/A')} - {dados.get('uf_destino', 'N/A')}`"],
                    "Peso (kg)": [dados.get("peso", "N/A")],
                    "Cubagem (m³)": [dados.get("cubagem", "N/A")],
                    "Distância (km)": [dados.get("distancia", "N/A")],
                    "Data/Hora": [dados.get("data_hora", "N/A")]
                }
                df_info = pd.DataFrame(info)
                
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_info.to_excel(writer, sheet_name='Informações', index=False)
        
        output.seek(0);
        
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"dados_{tipo.lower()}.xlsx"
        )
    
    except Exception as e:
        print(f"Erro ao exportar Excel: {e}")
        return jsonify({"error": str(e)}), 500

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PortoEx - Calculadora de Frete</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.3/dist/leaflet.css">
  <script src="https://code.jquery.com/jquery-3.6.3.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://unpkg.com/leaflet@1.9.3/dist/leaflet.js"></script>
  <style>
    body { padding: 20px; }
    .select2-container { width: 100% !important; }
    #map { height: 400px; width: 100%; margin-top: 20px; }
    .tab-content { padding-top: 20px; }
    .resultado-info { background-color: #f8f9fa; padding: 15px; border-radius: 5px; }
    .pbi-container { width: 100%; height: 600px; }
    .comparacao-card { margin-top: 20px; padding: 15px; border-radius: 5px; background-color: #f0f8ff; }
    .agentes-list { margin-top: 10px; }
    .agentes-list span { display: inline-block; margin-right: 10px; margin-bottom: 5px; padding: 5px 10px; background-color: #e9ecef; border-radius: 15px; }
    .historico-item { cursor: pointer; transition: background-color 0.3s; }
    .historico-item:hover { background-color: #f5f5f5; }
    .historico-badge { font-size: 0.8em; padding: 3px 8px; margin-right: 5px; }
    .chart-container { height: 300px; margin-bottom: 20px; }
    .btn-group-export { margin-top: 15px; margin-bottom: 20px; }
    .categoria-badge { font-size: 0.75em; padding: 2px 6px; vertical-align: middle; margin-left: 5px; }
    .btn-compor-trajeto { font-size: 0.8em; padding: 2px 5px; margin-left: 10px; }
    .logout-bar { position: absolute; top: 10px; right: 20px; z-index: 1000; }
  </style>
</head>
<body>
  {% if current_user.is_authenticated %}
  <div class="logout-bar">
    <span class="me-2">Usuário: <strong>{{ current_user.id }}</strong></span>
    <a href="{{ url_for('logout') }}" class="btn btn-outline-danger btn-sm">Sair</a>
  </div>
  {% endif %}
  <div class="container">
    <h1 class="mb-4">📦 PortoEx - Cotação</h1>
    <ul class="nav nav-tabs" id="myTab" role="tablist">
      <li class="nav-item">
        <a class="nav-link active" data-bs-toggle="tab" href="#tab-fracionado">Fracionado</a>
      </li>
      <li class="nav-item">
        <a class="nav-link" data-bs-toggle="tab" href="#tab-dedicado">Dedicado</a>
      </li>
      <li class="nav-item">
        <a class="nav-link" data-bs-toggle="tab" href="#tab-historico">Histórico</a>
      </li>
      <li class="nav-item">
        <a class="nav-link" data-bs-toggle="tab" href="#tab-dashboard">Target</a>
      </li>
    </ul>
    <div class="tab-content">
      <!-- Dedicado -->
      <div class="tab-pane fade" id="tab-dedicado">
        <form id="form-dedicado" class="row g-3">
          <div class="col-md-6">
            <label for="uf_origem" class="form-label">Estado de Origem</label>
            <select id="uf_origem" class="form-select select2-enable"></select>
          </div>
          <div class="col-md-6">
            <label for="uf_destino" class="form-label">Estado de Destino</label>
            <select id="uf_destino" class="form-select select2-enable"></select>
          </div>
          <div class="col-md-6">
            <label for="municipio_origem" class="form-label">Município de Origem</label>
            <select id="municipio_origem" class="form-select select2-enable" disabled></select>
          </div>
          <div class="col-md-6">
            <label for="municipio_destino" class="form-label">Município de Destino</label>
            <select id="municipio_destino" class="form-select select2-enable" disabled></select>
          </div>
          <div class="col-md-6">
            <label for="peso" class="form-label">Peso (kg) - Opcional</label>
            <input type="number" id="peso" class="form-control" min="0" step="0.01">
          </div>
          <div class="col-md-6">
            <label for="cubagem" class="form-label">Cubagem (m³) - Opcional</label>
            <input type="number" id="cubagem" class="form-control" min="0" step="0.01">
          </div>
          <div class="col-12">
            <button type="button" id="btn_calcular" class="btn btn-primary">Calcular Custos</button>
          </div>
        </form>
        <div id="resultados" style="display: none;">
          <h3 class="mt-4" id="id-historico-dedicado"></h3>
          <div id="map"></div>
          <h3 class="mt-4">Resultados</h3>
          
          <div class="btn-group-export">
            <button id="btn_gerar_pdf" class="btn btn-secondary">Salvar Relatório em PDF</button>
            <button id="btn_exportar_excel" class="btn btn-success ms-2">Exportar para Excel</button>
          </div>
          
          <div class="row mt-4">
            <div class="col-md-6">
              <div class="chart-container">
                <h4>Custos por Veículo</h4>
                <canvas id="custoChart"></canvas>
              </div>
            </div>
            <div class="col-md-6">
              <table class="table table-striped mt-4">
                <thead>
                  <tr>
                    <th>Tipo de Veículo</th>
                    <th>Custo (R$)</th>
                  </tr>
                </thead>
                <tbody id="tabela-resultado"></tbody>
              </table>
            </div>
          </div>
          <div class="resultado-info mt-4">
            <p><strong>Rota:</strong> <span id="res-origem"></span> → <span id="res-destino"></span></p>
            <p><strong>Distância:</strong> <span id="res-distancia"></span> km</p>
            <p><strong>Tempo estimado:</strong> <span id="res-tempo"></span></p>
            <p><strong>Consumo estimado:</strong> <span id="res-consumo"></span> L</p>
            <p><strong>Emissão de CO₂:</strong> <span id="res-co2"></span> kg</p>
            <p><strong>Pedágio estimado:</strong> R$ <span id="res-pedagio"></span></p>
            <p><strong>Peso informado:</strong> <span id="res-peso"></span></p>
            <p><strong>Cubagem informada:</strong> <span id="res-cubagem"></span></p>
          </div>
        </div>
      </div>
      <!-- Fracionado -->
      <div class="tab-pane fade show active" id="tab-fracionado">
        <form method="POST" action="/calcular_frete_fracionado" class="row g-3">
          <div class="col-md-6">
            <label for="uf_origem_frac" class="form-label">Estado de Origem</label>
            <select name="estado_origem" id="uf_origem_frac" class="form-select select2-enable"></select>
          </div>
          <div class="col-md-6">
            <label for="uf_destino_frac" class="form-label">Estado de Destino</label>
            <select name="estado_destino" id="uf_destino_frac" class="form-select select2-enable"></select>
          </div>
          <div class="col-md-6">
            <label for="municipio_origem_frac" class="form-label">Município de Origem</label>
            <select name="municipio_origem" id="municipio_origem_frac" class="form-select select2-enable" disabled></select>
          </div>
          <div class="col-md-6">
            <label for="municipio_destino_frac" class="form-label">Município de Destino</label>
            <select name="municipio_destino" id="municipio_destino_frac" class="form-select select2-enable" disabled></select>
          </div>
          <div class="col-md-6">
            <label for="peso-frac" class="form-label">Peso (kg)</label>
            <input type="number" name="peso" id="peso-frac" value="10" min="0" step="0.01" class="form-control">
          </div>
          <div class="col-md-6">
            <label for="cubagem-frac" class="form-label">Cubagem (m³)</label>
            <input type="number" name="cubagem" id="cubagem-frac" value="0.05" min="0" step="0.01" class="form-control">
          </div>
          <div class="col-12">
            <button type="submit" class="btn btn-primary">Calcular Lista de Agentes</button>
          </div>
        </form>
        {% if erro %}
          <div class="alert alert-danger mt-3">{{ erro }}</div>
        {% endif %}
        {% if resultado %}
          <h3 class="mt-4">{{ resultado.id_historico }} - Cotação: {{ resultado.cidades_origem }} - {{ resultado.uf_origem }} → {{ resultado.cidades_destino }} - {{ resultado.uf_destino }}</h3>
          
          <div class="btn-group-export">
            <button id="btn_gerar_pdf_fracionado" class="btn btn-secondary">Salvar Relatório em PDF</button>
            <button id="btn_exportar_excel_fracionado" class="btn btn-success ms-2">Exportar para Excel</button>
            <button id="btn_calcular_dedicado" class="btn btn-warning ms-2" data-uf-origem="{{ resultado.uf_origem }}" data-municipio-origem="{{ resultado.cidade_origem_norm }}" data-uf-destino="{{ resultado.uf_destino }}" data-municipio-destino="{{ resultado.cidade_destino_norm }}" data-peso="{{ resultado.peso }}" data-cubagem="{{ resultado.cubagem }}">Calcular Frete Dedicado para esta Rota</button>
          </div>
          
          <div id="map"></div>
          
          <div class="row mt-4">
            <div class="col-md-6">
              <div class="chart-container">
                               <h4>Comparação de Custos por Fornecedor (Filtrado)</h4>
                <canvas id="custoAgentesChart"></canvas>
              </div>
            </div>
            <div class="col-md-6">
              <div class="resultado-info">
                <p><strong>Rota:</strong> {{ resultado.cidades_origem }} - {{ resultado.uf_origem }} → {{ resultado.cidades_destino }} - {{ resultado.uf_destino }}</p>
                <p><strong>Distância:</strong> {{ resultado.distancia | default('N/A') }} km</p>
                <p><strong>Peso:</strong> {{ resultado.peso }} kg</p>
                <p><strong>Cubagem:</strong> {{ resultado.cubagem }} m³</p>
                <p><strong>Agentes Disponíveis:</strong></p>
                <div class="agentes-list">
                  {% for agente in resultado.todos_agentes %}
                    <span>{{ agente }}</span>
                  {% endfor %}
                </div>
              </div>
            </div>
          </div>
          
          <div class="row mt-4">
            <div class="col-md-6">
              <div class="card">
                <div class="card-header bg-primary text-white">
                  <h5 class="mb-0">Melhor Preço</h5>
                </div>
                <div class="card-body">
                  {% if resultado.melhor_preco %}
                    <p><strong>Fornecedor:</strong> {{ resultado.melhor_preco.fornecedor }} 
                       <span class="badge {{ 'bg-danger' if resultado.melhor_preco.categoria == 'Cia de Transferência' else 'bg-success' }} categoria-badge">{{ resultado.melhor_preco.categoria }}</span>
                    </p>
                    <p><strong>Custo:</strong> R$ {{ resultado.melhor_preco.custo | round(2) }}</p>
                    <p><strong>Prazo:</strong> {{ resultado.melhor_preco.prazo }} dias</p>
                    {% if resultado.melhor_preco.categoria == 'Cia de Transferência' %}
                      <button class="btn btn-sm btn-outline-primary btn-compor-trajeto-final" data-fornecedor="{{ resultado.melhor_preco.fornecedor }}" data-custo="{{ resultado.melhor_preco.custo }}" data-prazo="{{ resultado.melhor_preco.prazo }}" data-uf-destino-cia="{{ resultado.melhor_preco.uf_destino_norm }}" data-cidade-destino-cia="{{ resultado.melhor_preco.cidade_destino_norm }}">Compor Trajeto Final</button>
                    {% else %}
                      <button class="btn btn-sm btn-outline-info btn-compor-trajeto-inicial" data-fornecedor="{{ resultado.melhor_preco.fornecedor }}" data-custo="{{ resultado.melhor_preco.custo }}" data-prazo="{{ resultado.melhor_preco.prazo }}" data-uf-origem-agente="{{ resultado.melhor_preco.uf_origem_norm }}" data-cidade-origem-agente="{{ resultado.melhor_preco.cidade_origem_norm }}">Compor Trajeto Inicial</button>
                    {% endif %}
                  {% else %}
                    <p>Nenhum fornecedor disponível</p>
                  {% endif %}
                </div>
              </div>
            </div>
            <div class="col-md-6">
              <div class="card">
                <div class="card-header bg-primary text-white">
                  <h5 class="mb-0">Melhor Prazo</h5>
                </div>
                <div class="card-body">
                  {% if resultado.melhor_prazo %}
                    <p><strong>Fornecedor:</strong> {{ resultado.melhor_prazo.fornecedor }} 
                       <span class="badge {{ 'bg-danger' if resultado.melhor_prazo.categoria == 'Cia de Transferência' else 'bg-success' }} categoria-badge">{{ resultado.melhor_prazo.categoria }}</span>
                    </p>
                    <p><strong>Custo:</strong> R$ {{ resultado.melhor_prazo.custo | round(2) }}</p>
                    <p><strong>Prazo:</strong> {{ resultado.melhor_prazo.prazo }} dias</p>
                    {% if resultado.melhor_prazo.categoria == 'Cia de Transferência' %}
                      <button class="btn btn-sm btn-outline-primary btn-compor-trajeto-final" data-fornecedor="{{ resultado.melhor_prazo.fornecedor }}" data-custo="{{ resultado.melhor_prazo.custo }}" data-prazo="{{ resultado.melhor_prazo.prazo }}" data-uf-destino-cia="{{ resultado.melhor_prazo.uf_destino_norm }}" data-cidade-destino-cia="{{ resultado.melhor_prazo.cidade_destino_norm }}">Compor Trajeto Final</button>
                    {% else %}
                      <button class="btn btn-sm btn-outline-info btn-compor-trajeto-inicial" data-fornecedor="{{ resultado.melhor_prazo.fornecedor }}" data-custo="{{ resultado.melhor_prazo.custo }}" data-prazo="{{ resultado.melhor_prazo.prazo }}" data-uf-origem-agente="{{ resultado.melhor_prazo.uf_origem_norm }}" data-cidade-origem-agente="{{ resultado.melhor_prazo.cidade_origem_norm }}">Compor Trajeto Inicial</button>
                    {% endif %}
                  {% else %}
                    <p>Nenhum fornecedor disponível</p>
                  {% endif %}
                </div>
              </div>
            </div>
          </div>
          
          <div class="row mt-4">
            <div class="col-md-12">
              <h4>Ranking de Transportadoras (Filtrado por Fornecedor)</h4>
              <table class="table table-striped">
                <thead>
                  <tr>
                    <th>Posição</th>
                    <th>Fornecedor</th>
                    <th>Categoria</th>
                    <th>Custo (R$)</th>
                    <th>Prazo (dias)</th>
                    <th>Gris</th>
                    <th>Zona Parceiro</th>
                    <th>Nova Zona</th>
                    <th>DFL</th>
                    <th>Peso Máximo (kg)</th>
                    <th>Excedente (R$/kg)</th>
                    <th>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {% for item in resultado.ranking %}
                    <tr>
                      <td>{{ loop.index }}</td>
                      <td>{{ item.fornecedor }}</td>
                      <td><span class="badge {{ 'bg-danger' if item.categoria == 'Cia de Transferência' else 'bg-success' }} categoria-badge">{{ item.categoria }}</span></td>
                      <td>{{ item.custo | round(2) }}</td>
                      <td>{{ item.prazo }}</td>
                      <td>{{ item.gris }}</td>
                      <td>{{ item.zona_parceiro }}</td>
                      <td>{{ item.nova_zona }}</td>
                      <td>{{ item.dfl }}</td>
                      <td>{{ item.peso_maximo }}</td>
                      <td>{{ item.excedente | round(2) }}</td>
                      <td>
                        {% if item.categoria == 'Cia de Transferência' %}
                          <button class="btn btn-sm btn-outline-primary btn-compor-trajeto-final" data-fornecedor="{{ item.fornecedor }}" data-custo="{{ item.custo }}" data-prazo="{{ item.prazo }}" data-uf-destino-cia="{{ item.uf_destino_norm }}" data-cidade-destino-cia="{{ item.cidade_destino_norm }}">Compor Trajeto Final</button>
                        {% else %}
                          <button class="btn btn-sm btn-outline-info btn-compor-trajeto-inicial" data-fornecedor="{{ item.fornecedor }}" data-custo="{{ item.custo }}" data-prazo="{{ item.prazo }}" data-uf-origem-agente="{{ item.uf_origem_norm }}" data-cidade-origem-agente="{{ item.cidade_origem_norm }}">Compor Trajeto Inicial</button>
                        {% endif %}
                      </td>
                    </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
          </div>
          
          <div class="row mt-4">
            <div class="col-md-12">
              <h4>Ranking Completo de Transportadoras (Todas as Opções)</h4>
              <table class="table table-striped">
                <thead>
                  <tr>
                    <th>Posição</th>
                    <th>Fornecedor</th>
                    <th>Categoria</th>
                    <th>Custo (R$)</th>
                    <th>Prazo (dias)</th>
                    <th>Gris</th>
                    <th>Zona Parceiro</th>
                    <th>Nova Zona</th>
                    <th>DFL</th>
                    <th>Peso Máximo (kg)</th>
                    <th>Excedente (R$/kg)</th>
                  </tr>
                </thead>
                <tbody>
                  {% for item in resultado.ranking_completo %}
                    <tr>
                      <td>{{ loop.index }}</td>
                      <td>{{ item.fornecedor }}</td>
                      <td><span class="badge {{ 'bg-danger' if item.categoria == 'Cia de Transferência' else 'bg-success' }} categoria-badge">{{ item.categoria }}</span></td>
                      <td>{{ item.custo | round(2) }}</td>
                      <td>{{ item.prazo }}</td>
                      <td>{{ item.gris }}</td>
                      <td>{{ item.zona_parceiro }}</td>
                      <td>{{ item.nova_zona }}</td>
                      <td>{{ item.dfl }}</td>
                      <td>{{ item.peso_maximo }}</td>
                      <td>{{ item.excedente | round(2) }}</td>
                    </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
          </div>
          
          <div class="modal fade" id="modalComporTrajetoFinal" tabindex="-1" aria-labelledby="modalComporTrajetoFinalLabel" aria-hidden="true">
            <div class="modal-dialog modal-lg">
              <div class="modal-content">
                <div class="modal-header">
                  <h5 class="modal-title" id="modalComporTrajetoFinalLabel">Compor Trajeto Final (Cia → Agente)</h5>
                  <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                  <p>A transportadora <strong id="modal-final-cia-nome"></strong> (Cia de Transferência) leva a carga até <strong id="modal-final-cia-destino"></strong>.</p>
                  <p>Selecione um Agente para completar o trajeto até <strong id="modal-final-destino-final"></strong>:</p>
                  <div id="modal-final-agentes-disponiveis">
                    <p class="text-center"><span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Carregando agentes...</p>
                  </div>
                  <div id="modal-final-resultado-composicao" class=" potansiy: none;">
                    <h5>Resultado da Composição:</h5>
                    <p><strong>Trecho 1 (Cia):</strong> <span id="modal-final-res-cia-nome"></span> - R$ <span id="modal-final-res-cia-custo"></span> - <span id="modal-final-res-cia-prazo"></span> dias</p>
                    <p><strong>Trecho 2 (Agente):</strong> <span id="modal-final-res-agente-nome"></span> - R$ <span id="modal-final-res-agente-custo"></span> - <span id="modal-final-res-agente-prazo"></span> dias</p>
                    <hr>
                    <p><strong>Custo Total: R$ <span id="modal-final-res-custo-total"></span></strong></p>
                    <p><strong>Prazo Total: <span id="modal-final-res-prazo-total"></span> dias</strong></p>
                  </div>
                </div>
                <div class="modal-footer">
                  <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fechar</button>
                </div>
              </div>
            </div>
          </div>
          
          <div class="modal fade" id="modalComporTrajetoInicial" tabindex="-1" aria-labelledby="modalComporTrajetoInicialLabel" aria-hidden="true">
            <div class="modal-dialog modal-lg">
              <div class="modal-content">
                <div class="modal-header">
                  <h5 class="modal-title" id="modalComporTrajetoInicialLabel">Compor Trajeto Inicial (Agente → Cia)</h5>
                  <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                  <p>O transportador <strong id="modal-inicial-agente-nome"></strong> (Agente) faz o trecho de <strong id="modal-inicial-agente-origem"></strong> até <strong id="modal-inicial-destino-final"></strong>.</p>
                  <p>Selecione uma Cia de Transferência para fazer o trecho inicial de <strong id="modal-inicial-origem-inicial"></strong> até <strong id="modal-inicial-agente-origem"></strong>:</p>
                  <div id="modal-inicial-cias-disponiveis">
                    <!-- Lista de Cias será carregada aqui -->
                    <p class="text-center"><span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Carregando Cias de Transferência...</p>
                  </div>
                  <div id="modal-inicial-resultado-composicao" class="mt-3" style="display: none;">
                    <h5>Resultado da Composição:</h5>
                    <p><strong>Trecho 1 (Cia):</strong> <span id="modal-inicial-res-cia-nome"></span> - R$ <span id="modal-inicial-res-cia-custo"></span> - <span id="modal-inicial-res-cia-prazo"></span> dias</p>
                    <p><strong>Trecho 2 (Agente):</strong> <span id="modal-final-res-agente-nome"></span> - R$ <span id="modal-final-res-agente-custo"></span> - <span id="modal-final-res-agente-prazo"></span> dias</p>
                    <hr>
                    <p><strong>Custo Total: R$ <span id="modal-inicial-res-custo-total"></span></strong></p>
                    <p><strong>Prazo Total: <span id="modal-inicial-res-prazo-total"></span> dias</strong></p>
                  </div>
                </div>
                <div class="modal-footer">
                  <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fechar</button>
                </div>
              </div>
            </div>
          </div>
          
        {% endif %}
      </div>
      
      <!-- Histórico -->
      <div class="tab-pane fade" id="tab-historico">
        <h3 class="mt-4">Histórico de Pesquisas</h3>
        <div class="table-responsive">
          <table class="table table-hover">
            <thead>
              <tr>
                <th>ID</th>
                <th>Tipo</th>
                <th>Origem</th>
                <th>Destino</th>
                <th>Data/Hora</th>
                <th>Detalhes</th>
              </tr>
            </thead>
            <tbody id="historico-tbody">
              <!-- Será preenchido via JavaScript -->
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- Dashboard -->
      <div class="tab-pane fade" id="tab-dashboard">
        <div class="pbi-container">
          <iframe src="https://app.powerbi.com/view?r=eyJrIjoiYWUzODBiYmUtMWI1OC00NGVjLWFjNDYtYzYyMDQ3MzQ0MTQ0IiwidCI6IjM4MjViNTlkLTY1ZGMtNDM1Zi04N2M4LTkyM2QzMzkxYzMyOCJ9" allowfullscreen="true" style="width: 100%; height: 600px;"></iframe>
        </div>
      </div>
    </div>
  </div>

  <script>
    let map;
    let custoAgentesChart;
    let resultadoFracionado = {{ resultado | tojson if resultado else 'null' }};
    let resultadoDedicado = null;
    let historicoCompleto = {{ historico | tojson if historico else '[]' }};
    
    function initMap(points) {
      if (!map) {
        map = L.map('map').setView([-15.77972, -47.92972], 5);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© OpenStreetMap contributors'
        }).addTo(map);
      }
      
      if (points && points.length > 1) {
        // Limpar rotas e marcadores anteriores
        map.eachLayer(function(layer) {
          if (layer instanceof L.Polyline || layer instanceof L.Marker) {
            map.removeLayer(layer);
          }
        });
        
        let route = L.polyline(points, {color: 'blue'}).addTo(map);
        map.fitBounds(route.getBounds());
        L.marker(points[0]).addTo(map).bindPopup('Origem');
        L.marker(points[points.length - 1]).addTo(map).bindPopup('Destino');
      }
    }
    
    function carregarHistorico() {
      $.get('/historico', function(data) {
        historicoCompleto = data; // Atualiza o histórico local
        let html = '';
        data.slice().reverse().forEach(function(item) { // Mostra os mais recentes primeiro
          let badgeClass = item.tipo === 'Fracionado' ? 'bg-primary' : 'bg-success';
          html += `<tr class="historico-item" data-id="${item.id_historico}">
            <td><span class="badge ${badgeClass} historico-badge">${item.id_historico}</span></td>
            <td>${item.tipo}</td>
            <td>${item.origem}</td>
            <td>${item.destino}</td>
            <td>${item.data_hora}</td>
            <td><button class="btn btn-sm btn-info btn-ver-detalhes">Ver Detalhes</button></td>
          </tr>`;
        });
        $('#historico-tbody').html(html);
      });
    }
    
    function criarGraficoAgentes(ranking) {
      if (custoAgentesChart) {
        custoAgentesChart.destroy();
      }
      
      const ctx = document.getElementById('custoAgentesChart').getContext('2d');
      
      // Extrair dados para o gráfico (usando ranking filtrado)
      const labels = ranking.map(item => item.fornecedor);
      const data = ranking.map(item => item.custo);
      const backgroundColors = [
        'rgba(54, 162, 235, 0.5)',
        'rgba(255, 99, 132, 0.5)',
        'rgba(255, 206, 86, 0.5)',
        'rgba(75, 192, 192, 0.5)',
        'rgba(153, 102, 255, 0.5)',
        'rgba(255, 159, 64, 0.5)',
        'rgba(199, 199, 199, 0.5)'
      ];
      
      custoAgentesChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Custo (R$)',
            data: data,
            backgroundColor: backgroundColors.slice(0, labels.length),
            borderColor: backgroundColors.map(color => color.replace('0.5', '1')),
            borderWidth: 1
          }]
        },
        options: {
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: 'Custo (R$)'
              }
            },
            x: {
              title: {
                display: true,
                text: 'Fornecedor'
              }
            }
          },
          plugins: {
            title: {
              display: true,
              text: 'Comparação de Custos por Fornecedor (Filtrado)'
            }
          }
        }
      });
    }
    
    // Função para buscar agentes para o trecho final
    function buscarAgentesTrechoFinal(uf_origem_trecho, cidade_origem_trecho, uf_destino_final, cidade_destino_final, peso, cubagem, callback) {
        $.ajax({
            url: '/buscar_agentes',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                uf_origem: uf_origem_trecho,
                cidade_origem: cidade_origem_trecho,
                uf_destino: uf_destino_final,
                cidade_destino: cidade_destino_final,
                peso: peso,
                cubagem: cubagem
            }),
            success: function(response) {
                callback(response.agentes);
            },
            error: function() {
                callback([]); // Retorna lista vazia em caso de erro
            }
        });
    }
    
    // Função para buscar Cias de Transferência para o trecho inicial
    function buscarCiasTrechoInicial(uf_origem_inicial, cidade_origem_inicial, uf_destino_trecho, cidade_destino_trecho, peso, cubagem, callback) {
        $.ajax({
            url: '/buscar_cias_transferencia',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                uf_origem: uf_origem_inicial,
                cidade_origem: cidade_origem_inicial,
                uf_destino: uf_destino_trecho,
                cidade_destino: cidade_destino_trecho,
                peso: peso,
                cubagem: cubagem
            }),
            success: function(response) {
                callback(response.cias);
            },
            error: function() {
                callback([]); // Retorna lista vazia em caso de erro
            }
        });
    }

    $(document).ready(function() {
      $('.select2-enable').select2();
      
      // Carregar histórico inicial
      carregarHistorico();
      
      // Atualizar histórico quando a aba for selecionada
      $('a[data-bs-toggle="tab"]').on('shown.bs.tab', function(e) {
        if ($(e.target).attr('href') === '#tab-historico') {
          carregarHistorico();
        }
      });

      // Carregar estados
      $.get('/estados', function(data) {
        ['#uf_origem', '#uf_destino', '#uf_origem_frac', '#uf_destino_frac'].forEach(function(id) {
          $(id).append('<option value="">Selecione</option>');
          data.forEach(function(estado) {
            $(id).append(`<option value="${estado.id}">${estado.text}</option>`);
          });
        });
      });

      // Carregar municípios
      ['#uf_origem', '#uf_destino', '#uf_origem_frac', '#uf_destino_frac'].forEach(function(id, index) {
        $(id).change(function() {
          let uf = $(this).val();
          let target = ['#municipio_origem', '#municipio_destino', '#municipio_origem_frac', '#municipio_destino_frac'][index];
          $(target).prop('disabled', true).empty().append('<option value="">Selecione</option>');
          if (uf) {
            $.get(`/municipios/${uf}`, function(data) {
              data.forEach(function(municipio) {
                $(target).append(`<option value="${municipio.id}">${municipio.text}</option>`);
              });
              $(target).prop('disabled', false);
            });
          }
        });
      });

      // Calcular frete dedicado
      $('#btn_calcular').click(function() {
        let data = {
          uf_origem: $('#uf_origem').val(),
          municipio_origem: $('#municipio_origem').val(),
          uf_destino: $('#uf_destino').val(),
          municipio_destino: $('#municipio_destino').val(),
          peso: $('#peso').val() || 0,
          cubagem: $('#cubagem').val() || 0
        };
        if (!data.uf_origem || !data.municipio_origem || !data.uf_destino || !data.municipio_destino) {
          alert('Preencha todos os campos obrigatórios.');
          return;
        }
        $.ajax({
          url: '/calcular',
          type: 'POST',
          contentType: 'application/json',
          data: JSON.stringify(data),
          success: function(response) {
            resultadoDedicado = response; // Armazena o resultado
            
            $('#id-historico-dedicado').text(response.id_historico);
            $('#res-origem').text(`${data.municipio_origem} - ${data.uf_origem}`);
            $('#res-destino').text(`${data.municipio_destino} - ${data.uf_destino}`);
            $('#res-distancia').text(response.distancia);
            let horas = Math.floor(response.duracao / 60);
            let minutos = Math.round(response.duracao % 60);
            $('#res-tempo').text(`${horas}h ${minutos}min`);
            $('#res-consumo').text((response.distancia / 10).toFixed(2));
            $('#res-co2').text(((response.distancia / 10) * 2.3).toFixed(2));
            $('#res-pedagio').text((response.distancia * 0.15).toFixed(2));
            $('#res-peso').text(response.peso > 0 ? `${response.peso} kg` : 'Não informado');
            $('#res-cubagem').text(response.cubagem > 0 ? `${response.cubagem} m³` : 'Não informado');

            let html = '';
            for (let tipo in response.custos) {
              html += `<tr><td>${tipo}</td><td>R$ ${response.custos[tipo].toFixed(2)}</td></tr>`;
            }
            $('#tabela-resultado').html(html);
            $('#resultados').show();

            initMap(response.rota_pontos);

            let ctx = document.getElementById('custoChart').getContext('2d');
            new Chart(ctx, {
              type: 'bar',
              data: {
                labels: Object.keys(response.custos),
                datasets: [{
                  label: 'Custo (R$)',
                  data: Object.values(response.custos),
                  backgroundColor: 'rgba(54, 162, 235, 0.5)',
                  borderColor: 'rgba(54, 162, 235, 1)',
                  borderWidth: 1
                }]
              },
              options: { 
                maintainAspectRatio: false,
                scales: { 
                  y: { 
                    beginAtZero: true,
                    title: {
                      display: true,
                      text: 'Custo (R$)'
                    }
                  },
                  x: {
                    title: {
                      display: true,
                      text: 'Tipo de Veículo'
                    }
                  }
                },
                plugins: {
                  title: {
                    display: true,
                    text: 'Custos por Tipo de Veículo'
                  }
                }
              }
            });
            
            // Atualizar histórico
            carregarHistorico();
          }
        });
      });

      // Gerar PDF para Dedicado
      $('#btn_gerar_pdf').click(function() {
        if (!resultadoDedicado || !resultadoDedicado.analise) {
          alert('Nenhum resultado disponível para gerar PDF.');
          return;
        }
        
        // Usar fetch para lidar com Blob
        fetch('/gerar-pdf', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ analise: resultadoDedicado.analise })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro na rede ou resposta do servidor');
            }
            const filename = response.headers.get('content-disposition').split('filename=')[1].replace(/"/g, '');
            return response.blob().then(blob => ({ blob, filename }));
        })
        .then(({ blob, filename }) => {
            const link = document.createElement('a');
            link.href = window.URL.createObjectURL(blob);
            link.download = filename || 'relatorio_dedicado.pdf';
            link.click();
            window.URL.revokeObjectURL(link.href);
        })
        .catch(error => {
            alert('Erro ao gerar PDF: ' + error);
        });
      });
      
      // Exportar Excel para Dedicado
      $('#btn_exportar_excel').click(function() {
        if (!resultadoDedicado || !resultadoDedicado.analise) {
          alert('Nenhum resultado disponível para exportar.');
          return;
        }
        
        // Usar fetch para lidar com Blob
        fetch('/exportar-excel', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                tipo: 'Dedicado', 
                dados: resultadoDedicado.analise 
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro na rede ou resposta do servidor');
            }
            const filename = response.headers.get('content-disposition').split('filename=')[1].replace(/"/g, '');
            return response.blob().then(blob => ({ blob, filename }));
        })
        .then(({ blob, filename }) => {
            const link = document.createElement('a');
            link.href = window.URL.createObjectURL(blob);
            link.download = filename || 'dados_dedicado.xlsx';
            link.click();
            window.URL.revokeObjectURL(link.href);
        })
        .catch(error => {
            alert('Erro ao exportar Excel: ' + error);
        });
      });
      
      // Gerar PDF para Fracionado
      $('#btn_gerar_pdf_fracionado').click(function() {
        if (!resultadoFracionado) {
          alert('Nenhum resultado disponível para gerar PDF.');
          return;
        }
        
        // Preparar dados para o PDF
        let analise = {
          id_historico: resultadoFracionado.id_historico,
          tipo: 'Fracionado',
          origem: resultadoFracionado.cidades_origem + ' - ' + resultadoFracionado.uf_origem,
          destino: resultadoFracionado.cidades_destino + ' - ' + resultadoFracionado.uf_destino,
          distancia: resultadoFracionado.distancia,
          data_hora: new Date().toLocaleString(),
          ranking: resultadoFracionado.ranking, // Usa o ranking filtrado
          melhor_preco: resultadoFracionado.melhor_preco,
          melhor_prazo: resultadoFracionado.melhor_prazo,
          pior_preco: resultadoFracionado.pior_preco,
          diferenca_valor: resultadoFracionado.diferenca_valor,
          diferenca_percentual: resultadoFracionado.diferenca_percentual
        };
        
        // Usar fetch para lidar com Blob
        fetch('/gerar-pdf', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ analise: analise })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro na rede ou resposta do servidor');
            }
            const filename = response.headers.get('content-disposition').split('filename=')[1].replace(/"/g, '');
            return response.blob().then(blob => ({ blob, filename }));
        })
        .then(({ blob, filename }) => {
            const link = document.createElement('a');
            link.href = window.URL.createObjectURL(blob);
            link.download = filename || 'relatorio_fracionado.pdf';
            link.click();
            window.URL.revokeObjectURL(link.href);
        })
        .catch(error => {
            alert('Erro ao gerar PDF: ' + error);
        });
      });
      
      // Exportar Excel para Fracionado
      $('#btn_exportar_excel_fracionado').click(function() {
        if (!resultadoFracionado) {
          alert('Nenhum resultado disponível para exportar.');
          return;
        }
        
        // Usar fetch para lidar com Blob
        fetch('/exportar-excel', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                tipo: 'Fracionado', 
                dados: resultadoFracionado 
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro na rede ou resposta do servidor');
            }
            const filename = response.headers.get('content-disposition').split('filename=')[1].replace(/"/g, '');
            return response.blob().then(blob => ({ blob, filename }));
        })
        .then(({ blob, filename }) => {
            const link = document.createElement('a');
            link.href = window.URL.createObjectURL(blob);
            link.download = filename || 'dados_fracionado.xlsx';
            link.click();
            window.URL.revokeObjectURL(link.href);
        })
        .catch(error => {
            alert('Erro ao exportar Excel: ' + error);
        });
      });

      // Criar gráfico de custos por agente (se houver resultado)
      if (resultadoFracionado && resultadoFracionado.ranking) {
          criarGraficoAgentes(resultadoFracionado.ranking);
      }
      
      // Lógica para o botão "Compor Trajeto Final" (Cia -> Agente)
      $(document).on('click', '.btn-compor-trajeto-final', function() {
          if (!resultadoFracionado) return;
          
          const fornecedorCia = $(this).data('fornecedor');
          const custoCia = parseFloat($(this).data('custo'));
          const prazoCia = parseInt($(this).data('prazo'));
      });
      
      // Lógica para selecionar o agente no modal final
      $(document).on('click', '.btn-selecionar-agente-final', function() {
          const agenteNome = $(this).data('agente-nome');
          const agenteCusto = parseFloat($(this).data('agente-custo'));
          const agentePrazo = parseInt($(this).data('agente-prazo'));
          const ciaNome = $(this).data('cia-nome');
          const ciaCusto = parseFloat($(this).data('cia-custo'));
          const ciaPrazo = parseInt($(this).data('cia-prazo'));
          
          const custoTotal = ciaCusto + agenteCusto;
          const prazoTotal = ciaPrazo + agentePrazo; // Soma simples de prazos
          
          // Exibir resultado da composição
          $('#modal-final-res-cia-nome').text(ciaNome);
          $('#modal-final-res-cia-custo').text(ciaCusto.toFixed(2));
          $('#modal-final-res-cia-prazo').text(ciaPrazo);
          $('#modal-final-res-agente-nome').text(agenteNome);
          $('#modal-final-res-agente-custo').text(agenteCusto.toFixed(2));
          $('#modal-final-res-agente-prazo').text(agentePrazo);
          $('#modal-final-res-custo-total').text(custoTotal.toFixed(2));
          $('#modal-final-res-prazo-total').text(prazoTotal);
          
          $('#modal-final-resultado-composicao').show();
      });
      
      // Lógica para o botão "Compor Trajeto Inicial" (Agente -> Cia)
      $(document).on('click', '.btn-compor-trajeto-inicial', function() {
          if (!resultadoFracionado) return;
          
          const fornecedorAgente = $(this).data('fornecedor');
          const custoAgente = parseFloat($(this).data('custo'));
          const prazoAgente = parseInt($(this).data('prazo'));
          const ufOrigemAgente = $(this).data('uf-origem-agente');
          const cidadeOrigemAgente = $(this).data('cidade-origem-agente');
          
          // Preencher informações no modal
          $('#modal-inicial-agente-nome').text(fornecedorAgente);
          $('#modal-inicial-agente-origem').text(`${cidadeOrigemAgente} - ${ufOrigemAgente}`);
          $('#modal-inicial-destino-final').text(`${resultadoFracionado.cidades_destino} - ${resultadoFracionado.uf_destino}`); // Destino final original
          $('#modal-inicial-origem-inicial').text(`${resultadoFracionado.cidades_origem} - ${resultadoFracionado.uf_origem}`); // Origem inicial original
          $('#modal-inicial-cias-disponiveis').html('<p class="text-center"><span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Carregando Cias de Transferência...</p>');
          $('#modal-inicial-resultado-composicao').hide();
          
          // Mostrar o modal
          var modal = new bootstrap.Modal(document.getElementById('modalComporTrajetoInicial'));
          modal.show();
          
          // Buscar Cias para o primeiro trecho
          buscarCiasTrechoInicial(
              resultadoFracionado.uf_origem_norm, 
              resultadoFracionado.cidade_origem_norm, 
              ufOrigemAgente, 
              cidadeOrigemAgente, 
              resultadoFracionado.peso, 
              resultadoFracionado.cubagem, 
              function(cias) {
                  let html = '';
                  if (cias && cias.length > 0) {
                      html += '<ul class="list-group">';
                      cias.forEach(cia => {
                          html += `<li class="list-group-item d-flex justify-content-between align-items-center">
                                      <div>
                                          <strong>${cia.fornecedor}</strong> (Cia de Transferência)<br>
                                          Custo: R$ ${cia.custo.toFixed(2)} | Prazo: ${cia.prazo} dias
                                      </div>
                                      <button class="btn btn-sm btn-success btn-selecionar-cia-inicial" 
                                              data-cia-nome="${cia.fornecedor}" 
                                              data-cia-custo="${cia.custo}" 
                                              data-cia-prazo="${cia.prazo}"
                                              data-agente-nome="${fornecedorAgente}"
                                              data-agente-custo="${custoAgente}"
                                              data-agente-prazo="${prazoAgente}"
                                              >Selecionar</button>
                                  </li>`;
                      });
                      html += '</ul>';
                  } else {
                      html = '<p class="text-danger">Nenhuma Cia de Transferência encontrada para o trecho inicial.</p>';
                  }
                  $('#modal-inicial-cias-disponiveis').html(html);
              }
          );
      });
      
      // Lógica para selecionar a Cia no modal inicial
      $(document).on('click', '.btn-selecionar-cia-inicial', function() {
          const ciaNome = $(this).data('cia-nome');
          const ciaCusto = parseFloat($(this).data('cia-custo'));
          const ciaPrazo = parseInt($(this).data('cia-prazo'));
          const agenteNome = $(this).data('agente-nome');
          const agenteCusto = parseFloat($(this).data('agente-custo'));
          const agentePrazo = parseInt($(this).data('agente-prazo'));
          
          const custoTotal = ciaCusto + agenteCusto;
          const prazoTotal = ciaPrazo + agentePrazo; // Soma simples de prazos
          
          // Exibir resultado da composição
          $('#modal-inicial-res-cia-nome').text(ciaNome);
          $('#modal-inicial-res-cia-custo').text(ciaCusto.toFixed(2));
          $('#modal-inicial-res-cia-prazo').text(ciaPrazo);
          $('#modal-inicial-res-agente-nome').text(agenteNome);
          $('#modal-inicial-res-agente-custo').text(agenteCusto.toFixed(2));
          $('#modal-inicial-res-agente-prazo').text(agentePrazo);
          $('#modal-inicial-res-custo-total').text(custoTotal.toFixed(2));
          $('#modal-inicial-res-prazo-total').text(prazoTotal);
          
          $('#modal-inicial-resultado-composicao').show();
      });
      
      // Lógica para ver detalhes do histórico
      $(document).on('click', '.btn-ver-detalhes', function() {
          const idHistorico = $(this).closest('tr').data('id');
          const item = historicoCompleto.find(h => h.id_historico === idHistorico);
          
          if (!item) {
              alert('Detalhes não encontrados para este item.');
              return;
          }
          
          if (item.tipo === 'Dedicado') {
              // Simular clique na aba Dedicado e preencher dados
              $('#myTab a[href="#tab-dedicado"]').tab('show');
              // Preencher resultados do dedicado (simplificado, idealmente recarregaria)
              $('#id-historico-dedicado').text(item.id_historico);
              $('#res-origem').text(item.origem);
              $('#res-destino').text(item.destino);
              $('#res-distancia').text(item.distancia);
              $('#res-tempo').text(item.tempo_estimado);
              $('#res-consumo').text(item.consumo_combustivel);
              $('#res-co2').text(item.emissao_co2);
              $('#res-pedagio').text(item.pedagio_estimado);
              $('#res-peso').text('N/A'); // Peso/Cubagem não armazenados no histórico dedicado
              $('#res-cubagem').text('N/A');
              
              let html = '';
              for (let tipo_veiculo in item.custos) {
                  html += `<tr><td>${tipo_veiculo}</td><td>R$ ${item.custos[tipo_veiculo].toFixed(2)}</td></tr>`;
              }
              $('#tabela-resultado').html(html);
              $('#resultados').show();
              initMap(item.rota_pontos);
              // Recriar gráfico dedicado
              // ... (código do gráfico dedicado omitido para brevidade)
              
          } else { // Fracionado
              // Simular clique na aba Fracionado e recarregar a página com os dados?
              // Ou tentar preencher dinamicamente (mais complexo)
              // Por simplicidade, vamos apenas mostrar um alerta com os dados
              alert(`Detalhes ${item.id_historico}:\nOrigem: ${item.origem}\nDestino: ${item.destino}\nPeso: ${item.peso} kg\nCubagem: ${item.cubagem} m³\nMelhor Preço: ${item.melhor_preco?.fornecedor} (R$ ${item.melhor_preco?.custo.toFixed(2)})\nMelhor Prazo: ${item.melhor_prazo?.fornecedor} (${item.melhor_prazo?.prazo} dias)`);
              // Idealmente, deveria recarregar a aba Fracionado com estes dados
          }
      });

    });
  </script>
</body>
</html>
"""

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Login - PortoEx</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background: #f8f9fa; }
    .login-container { max-width: 400px; margin: 80px auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
  </style>
</head>
<body>
  <div class="login-container">
    <h2 class="mb-4 text-center">PortoEx - Login</h2>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="alert alert-{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    <form method="POST">
      <div class="mb-3">
        <label for="username" class="form-label">Usuário</label>
        <input type="text" class="form-control" id="username" name="username" required autofocus>
      </div>
      <div class="mb-3">
        <label for="password" class="form-label">Senha</label>
        <input type="password" class="form-control" id="password" name="password" required>
      </div>
      <button type="submit" class="btn btn-primary w-100">Entrar</button>
    </form>
  </div>
</body>
</html>
'''

if __name__ == "__main__":
    # Usar configurações de ambiente para produção
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5000))
    
    if os.getenv('FLASK_ENV') == 'production':
        # Em produção, não usar o servidor de desenvolvimento
        app.run(host="0.0.0.0", port=port, debug=debug_mode)
    else:
        # Em desenvolvimento, usar o servidor de desenvolvimento
        app.run(host="0.0.0.0", port=port, debug=True)