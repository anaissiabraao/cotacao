import pandas as pd

def listar_fornecedores():
    try:
        # Ler o arquivo Excel
        df = pd.read_excel('Base_Unificada.xlsx')
        
        print("\n=== FORNECEDORES PRESENTES NA BASE ===")
        
        # Listar fornecedores por tipo
        for tipo in ['Agente', 'Transferência']:
            fornecedores = df[df['Tipo'] == tipo]['Fornecedor'].unique()
            print(f"\n{tipo}s:")
            for i, fornecedor in enumerate(sorted(fornecedores), 1):
                print(f"{i}. {fornecedor}")
            print(f"Total de {tipo}s: {len(fornecedores)}")
        
        # Mostrar estatísticas
        print("\n=== ESTATÍSTICAS ===")
        print("Quantidade de registros por fornecedor:")
        print(df.groupby(['Tipo', 'Fornecedor']).size().reset_index(name='Quantidade de Rotas'))
        
    except Exception as e:
        print(f"Erro ao processar o arquivo: {str(e)}")

if __name__ == "__main__":
    listar_fornecedores() 