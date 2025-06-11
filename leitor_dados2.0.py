# Adicionar import para ler a planilha GOLLOG (modal aéreo)
import pandas as pd

def ler_gollog_aereo(excel_file="GOLLOG_Base_Unica.xlsx", sheet_name="Aéreo"):
    """Lê a planilha GOLLOG_Base_Unica.xlsx (modal aéreo) e retorna um DataFrame com os dados.
       Se a aba 'Aéreo' não existir, lê a primeira aba.
    """
    try:
        xl = pd.ExcelFile(excel_file)
        if sheet_name not in xl.sheet_names:
            sheet_name = xl.sheet_names[0]
        df = pd.read_excel(xl, sheet_name=sheet_name)
        # Aqui você pode renomear ou filtrar colunas conforme necessário.
        # Por exemplo, se a planilha tiver colunas como "UF Origem", "Cidade Origem", "UF Destino", "Cidade Destino", "Fornecedor", "Custo Base", "Prazo", etc.
        # (Ajuste conforme a estrutura real da sua planilha.)
        # Exemplo (comentado):
        # df = df.rename(columns={"UF Origem": "uf_origem", "Cidade Origem": "cidade_origem", "UF Destino": "uf_destino", "Cidade Destino": "cidade_destino", "Fornecedor": "fornecedor", "Custo Base": "custo_base", "Prazo": "prazo"})
        # df = df[["uf_origem", "cidade_origem", "uf_destino", "cidade_destino", "fornecedor", "custo_base", "prazo"]]
        return df
    except Exception as e:
        logging.error(f"Erro ao ler a planilha GOLLOG (modal aéreo): {e}")
        return None

if __name__ == "__main__":
    # Chamar a função ler_gollog_aereo para diagnóstico
    df_aereo = ler_gollog_aereo()
    if df_aereo is not None:
        print(f"Modal aéreo (GOLLOG): {len(df_aereo)} linhas lidas.")
    else:
        print("Modal aéreo (GOLLOG): falha na leitura.")
    # (Código existente, por exemplo, chamar criar_base_unica() se necessário)
    # criar_base_unica() 