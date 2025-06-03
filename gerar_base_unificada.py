import pandas as pd
import unicodedata
import re

# Função para normalizar cidades
def normalizar_cidade(cidade):
    if not cidade:
        return ""
    cidade = ''.join(c for c in unicodedata.normalize('NFD', str(cidade)) if unicodedata.category(c) != 'Mn')
    cidade = re.sub(r'[^a-zA-Z0-9\s]', '', cidade).strip().upper()
    return re.sub(r'\s+', ' ', cidade)

def normalizar_uf(uf):
    if not uf:
        return ""
    uf = str(uf).strip().upper()
    if uf in ["SAO", "SÃO", "SAO PAULO", "SÃO PAULO", "SAO PAULO - SP", "SÃO PAULO - SP"]:
        return "SP"
    return uf[:2]

# Mapeamento expandido de colunas para cada aba
COLUNAS_ABAS = {
    "Base_Agentes": {
        "uf_origem": "UF",
        "cidade_origem": "CIDADES",
        "uf_destino": "UF",
        "cidade_destino": "CIDADES",
        "fornecedor": "Agente",
        "custo_base": "10kg",
        "excedente": "excedente",
        "gris_min": "GRIS mínimo",
        "excedente_peso": "excedente",
        "pedagio": "Pedágio",
        "dfl": "DFL",
        "prazo_expresso": "Prazo Expresso",
        "prazo_economico": "Prazo Econômico",
        "peso_max": "Peso Máximo",
        "valor_min": "Valor Mínimo"
    },
    "JEM_DFL": {
        "uf_origem": "Sigla Origem",
        "cidade_origem": "Origem",
        "uf_destino": "Sigla Destino",
        "cidade_destino": "Destino",
        "fornecedor": "Fornecedor",
        "custo_base": "10kg",
        "excedente": "excedente",
        "gris_min": "GRIS mínimo",
        "excedente_peso": "excedente",
        "pedagio": "Pedágio",
        "dfl": "DFL",
        "prazo_expresso": "Prazo Expresso",
        "prazo_economico": "Prazo Econômico",
        "peso_max": "Peso Máximo",
        "valor_min": "Valor Mínimo"
    },
    "Concept": {
        "uf_origem": "Sigla Origem",
        "cidade_origem": "Origem",
        "uf_destino": "Sigla Destino",
        "cidade_destino": "Destino",
        "fornecedor": "Fornecedor",
        "custo_base": "10kg",
        "excedente": "excedente",
        "gris_min": "GRIS mínimo",
        "excedente_peso": "excedente",
        "pedagio": "Pedágio",
        "dfl": "DFL",
        "prazo_expresso": "Prazo Expresso",
        "prazo_economico": "Prazo Econômico",
        "peso_max": "Peso Máximo",
        "valor_min": "Valor Mínimo"
    },
    "Reunidas": {
        "uf_origem": "uf_origem",
        "cidade_origem": "unidade_origem",
        "uf_destino": "uf_destino",
        "cidade_destino": "cidade_destino",
        "fornecedor": "Fornecedor",
        "custo_base": "10kg",
        "excedente": "excedente",
        "gris_min": "GRIS mínimo",
        "excedente_peso": "excedente",
        "pedagio": "Pedágio",
        "dfl": "DFL",
        "prazo_expresso": "Prazo Expresso",
        "prazo_economico": "Prazo Econômico",
        "peso_max": "Peso Máximo",
        "valor_min": "Valor Mínimo"
    },
    "Gritsch": {
        "uf_origem": "uf_origem",
        "cidade_origem": "unidade_origem",
        "uf_destino": "uf_destino",
        "cidade_destino": "cidade_destino",
        "fornecedor": "Fornecedor",
        "custo_base": "10kg",
        "excedente": "excedente",
        "gris_min": "GRIS mínimo",
        "excedente_peso": "excedente",
        "pedagio": "Pedágio",
        "dfl": "DFL",
        "prazo_expresso": "Prazo Expresso",
        "prazo_economico": "Prazo Econômico",
        "peso_max": "Peso Máximo",
        "valor_min": "Valor Mínimo"
    },
}

EXCEL_FILE = "base_unificada_simplificada.xlsx"
abas = list(COLUNAS_ABAS.keys())
xl = pd.ExcelFile(EXCEL_FILE)

# Lista de todas as colunas padronizadas que queremos na base final
CAMPOS_PADRAO = [
    "uf_origem", "cidade_origem", "uf_destino", "cidade_destino", "fornecedor", "custo_base", "excedente",
    "gris_min", "excedente_peso", "pedagio", "dfl", "prazo_expresso", "prazo_economico", "peso_max", "valor_min", "tipo", "origem_aba"
]

linhas = []
for aba in abas:
    df = pd.read_excel(xl, sheet_name=aba)
    col = COLUNAS_ABAS[aba]
    for _, row in df.iterrows():
        linha = {}
        for campo in CAMPOS_PADRAO:
            if campo in ["tipo", "origem_aba"]:
                continue
            # Busca o nome da coluna real para este campo nesta aba
            nome_col = col.get(campo)
            if nome_col and nome_col in row:
                valor = row[nome_col]
            else:
                valor = None
            # Normalização para UF e cidade
            if campo == "uf_origem" or campo == "uf_destino":
                valor = normalizar_uf(valor)
            if campo == "cidade_origem" or campo == "cidade_destino":
                valor = normalizar_cidade(valor)
            linha[campo] = valor
        linha["tipo"] = "Agente" if aba == "Base_Agentes" else "Cia de Transferencia"
        linha["origem_aba"] = aba
        # Só adiciona se tiver UF e cidade de origem e destino
        if linha["uf_origem"] and linha["cidade_origem"] and linha["uf_destino"] and linha["cidade_destino"]:
            linhas.append(linha)

# Cria DataFrame único
unificado = pd.DataFrame(linhas, columns=CAMPOS_PADRAO)
# Remove duplicatas
unificado = unificado.drop_duplicates()
# Salva em novo arquivo
unificado.to_excel("base_unificada_final.xlsx", index=False)
print("Base unificada salva como base_unificada_final.xlsx")

# 1. Listar fornecedores únicos da Base_Agentes
fornecedores_agentes = set()
df_agentes = pd.read_excel(xl, sheet_name="Base_Agentes")
col_agentes = COLUNAS_ABAS["Base_Agentes"]
for _, row in df_agentes.iterrows():
    nome = row.get(col_agentes["fornecedor"])
    if nome:
        fornecedores_agentes.add(str(nome).strip())
print("Fornecedores únicos da Base_Agentes:")
for f in sorted(fornecedores_agentes):
    print(f)

# 2. Diagnóstico de campos ausentes nas demais abas
campos_diagnostico = ["fornecedor", "custo_base", "excedente", "gris_min", "excedente_peso", "pedagio", "prazo_expresso", "prazo_economico", "peso_max", "valor_min"]
for aba in abas:
    if aba == "Base_Agentes":
        continue
    print(f"\nDiagnóstico da aba: {aba}")
    df = pd.read_excel(xl, sheet_name=aba)
    col = COLUNAS_ABAS[aba]
    for campo in campos_diagnostico:
        nome_col = col.get(campo)
        if not nome_col or nome_col not in df.columns:
            print(f"  Campo ausente: {campo} (coluna esperada: {nome_col})")
        else:
            # Verifica se todos os valores estão vazios/None
            if df[nome_col].isnull().all() or (df[nome_col] == '').all():
                print(f"  Campo vazio: {campo} (coluna: {nome_col})")
print("\nDiagnóstico concluído.")
