import pandas as pd
import os

def ler_e_processar_base():
    try:
        # Tentar diferentes caminhos possíveis para o arquivo
        caminhos = [
            'Base_Unificada.xlsx',
            'C:\\Users\\Usuário\\OneDrive\\Desktop\\SQL data\\Chico automate\\Base_Unificada.xlsx',
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Base_Unificada.xlsx')
        ]
        
        df = None
        for caminho in caminhos:
            if os.path.exists(caminho):
                print(f"\nArquivo encontrado em: {caminho}")
                df = pd.read_excel(caminho)
                break
                
        if df is None:
            print("Erro: Arquivo Base_Unificada.xlsx não encontrado em nenhum dos locais esperados!")
            return
            
        print("\nColunas disponíveis no arquivo:")
        print("-" * 50)
        print(df.columns.tolist())
        
        # Verificar se as colunas necessárias existem
        colunas_necessarias = ['Fornecedor', 'Base Origem', 'Tipo', 'Origem', 'Destino']
        colunas_faltando = [col for col in colunas_necessarias if col not in df.columns]
        
        if colunas_faltando:
            print(f"\nAviso: As seguintes colunas não foram encontradas: {colunas_faltando}")
            print("Colunas disponíveis:", df.columns.tolist())
            return
            
        # Verificar registros do TH EXPRESS (com variações de nome)
        print("\nVerificando registros do TH EXPRESS...")
        
        # Procurar variações do nome
        th_express_variations = df[df['Fornecedor'].str.contains('TH EXPRESS|TH-EXPRESS|TH_EXPRESS|THEXPRESS', 
                                                               case=False, na=False, regex=True)]
        
        # Verificar registros em Itajaí (código ITJ)
        th_express_itajai = df[(df['Fornecedor'].str.contains('TH EXPRESS|TH-EXPRESS|TH_EXPRESS|THEXPRESS', 
                                                           case=False, na=False, regex=True)) & 
                             (df['Base Origem'] == 'ITJ')]
        
        print("\n" + "="*80)
        print("RESULTADOS DA VERIFICAÇÃO")
        print("="*80)
        
        print(f"\nTotal de registros na base: {len(df)}")
        print(f"Registros com variações de 'TH EXPRESS': {len(th_express_variations)}")
        print(f"Registros 'TH EXPRESS' em Itajaí (ITJ): {len(th_express_itajai)}")
        
        if not th_express_variations.empty:
            print("\nTodas as variações de 'TH EXPRESS' encontradas:")
            print(th_express_variations[['Fornecedor', 'Base Origem', 'Tipo', 'Origem', 'Destino']])
        else:
            print("\nNenhum registro com variações de 'TH EXPRESS' encontrado na base.")
            
        if not th_express_itajai.empty:
            print("\nRegistros 'TH EXPRESS' em Itajaí:")
            print(th_express_itajai[['Fornecedor', 'Base Origem', 'Tipo', 'Origem', 'Destino']])
        else:
            print("\nNenhum registro do 'TH EXPRESS' encontrado em Itajaí (ITJ).")
            
        # Verificar se existem registros de Itajaí (para confirmar se a base está sendo lida corretamente)
        itajai_records = df[df['Base Origem'] == 'ITJ']
        print(f"\nTotal de registros de Itajaí (ITJ) na base: {len(itajai_records)}")
        
        if not itajai_records.empty:
            print("\nAlguns registros de Itajaí (ITJ) como exemplo:")
            print(itajai_records[['Fornecedor', 'Base Origem', 'Tipo', 'Origem', 'Destino']].head(3))
            
    except Exception as e:
        print(f"\nErro ao processar o arquivo: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    ler_e_processar_base() 