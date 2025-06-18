import pandas as pd
import os

def ler_e_processar_base():
    try:
        # Ler o arquivo Excel
        caminho_arquivo = 'Base_Unificada.xlsx'
        print(f"Tentando ler o arquivo: {os.path.abspath(caminho_arquivo)}")
        
        # Ler a base
        df = pd.read_excel(caminho_arquivo)
        print("\nColunas disponíveis:", df.columns.tolist())
        
        # Verificar valores únicos na coluna Tipo
        print("\nTipos disponíveis:", df['Tipo'].unique())
        
        # Filtrar apenas registros que são agentes ou transferência
        df_filtrado = df[df['Tipo'].isin(['Agente', 'Transferência'])]
        
        # Criar um backup do arquivo original
        backup_path = 'Base_Unificada_backup.xlsx'
        df.to_excel(backup_path, index=False)
        print(f"\nBackup criado em: {backup_path}")
        
        # Mostrar contagem por tipo
        print("\nQuantidade de registros por tipo:")
        print(df_filtrado['Tipo'].value_counts())
        
        # Salvar o resultado
        df_filtrado.to_excel(caminho_arquivo, index=False)
        print("\nArquivo atualizado com sucesso!")
        
        # Mostrar alguns exemplos dos dados mantidos
        print("\nExemplos dos registros mantidos:")
        print(df_filtrado.head())
        
    except Exception as e:
        print(f"Erro ao processar o arquivo: {str(e)}")

if __name__ == "__main__":
    ler_e_processar_base() 