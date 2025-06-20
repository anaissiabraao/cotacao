import pandas as pd
import sys
import os

# Adicionar o diretório atual ao path para importar as funções
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from improved_chico_automate_fpdf import carregar_base_unificada, processar_linha_transferencia, normalizar_cidade

def investigar_agentes():
    """
    Investigar os dados dos agentes para identificar problemas com GRIS, Prazo e Peso Máximo
    """
    print("=" * 70)
    print("INVESTIGAÇÃO DOS DADOS DOS AGENTES")
    print("=" * 70)
    
    try:
        # Carregar diretamente a planilha
        df = pd.read_excel('Base_Unificada.xlsx')
        print(f"Total de registros na planilha: {len(df)}")
        
        # Filtrar apenas agentes
        df_agentes = df[df['Tipo'] == 'Agente'].copy()
        print(f"Total de agentes: {len(df_agentes)}")
        
        # Buscar agente GLI especificamente
        gli_agentes = df_agentes[df_agentes['Fornecedor'] == 'GLI']
        print(f"Registros do agente GLI: {len(gli_agentes)}")
        
        if len(gli_agentes) > 0:
            # Pegar o primeiro registro GLI para análise
            primeiro_gli = gli_agentes.iloc[0]
            
            print(f"\n📊 ANÁLISE DO AGENTE GLI:")
            print(f"Fornecedor: {primeiro_gli['Fornecedor']}")
            print(f"Origem: {primeiro_gli['Origem']}")
            print(f"Destino: {primeiro_gli['Destino']}")
            print(f"VALOR MÍNIMO ATÉ 10: R$ {primeiro_gli.get('VALOR MÍNIMO ATÉ 10', 'N/A')}")
            print(f"EXCEDENTE: R$ {primeiro_gli.get('EXCEDENTE', 'N/A')}")
            print(f"Pedagio (100 Kg): R$ {primeiro_gli.get('Pedagio (100 Kg)', 'N/A')}")
            print(f"GRIS Min: R$ {primeiro_gli.get('Gris Min', 'N/A')}")
            print(f"GRIS Exc: {primeiro_gli.get('Gris Exc', 'N/A')}%")
            print(f"Prazo: {primeiro_gli.get('Prazo', 'N/A')} dias")
            print(f"Peso Máximo: {primeiro_gli.get('PESO MÁXIMO TRANSPORTADO', 'N/A')} kg")
            
            # Testar processamento
            peso_teste = 1660
            valor_nf_teste = 100000
            
            print(f"\n🧮 TESTE DE PROCESSAMENTO (Peso: {peso_teste}kg, NF: R$ {valor_nf_teste:,}):")
            resultado = processar_linha_transferencia(primeiro_gli, peso_teste, valor_nf_teste)
            
            if resultado:
                print(f"Custo: R$ {resultado['custo']:,.2f}")
                print(f"Pedágio: R$ {resultado['pedagio']:,.2f}")
                print(f"GRIS: R$ {resultado['gris']:,.2f}")
                print(f"Total: R$ {resultado['total']:,.2f}")
                print(f"Prazo: {resultado['prazo']} dias")
                print(f"Fornecedor: {resultado['fornecedor']}")
                print(f"É agente: {resultado['is_agente']}")
                
                # Verificar se GRIS foi calculado corretamente
                if valor_nf_teste > 0 and primeiro_gli.get('Gris Exc') is not None:
                    gris_exc = float(primeiro_gli.get('Gris Exc', 0))
                    gris_esperado = valor_nf_teste * (gris_exc / 100)
                    gris_min = float(primeiro_gli.get('Gris Min', 0) or 0)
                    gris_final_esperado = max(gris_esperado, gris_min)
                    
                    print(f"\n🔍 VERIFICAÇÃO DO GRIS:")
                    print(f"GRIS Exc planilha: {gris_exc}%")
                    print(f"GRIS calculado esperado: R$ {valor_nf_teste:,} × {gris_exc/100} = R$ {gris_esperado:,.2f}")
                    print(f"GRIS mínimo: R$ {gris_min:,.2f}")
                    print(f"GRIS final esperado: R$ {gris_final_esperado:,.2f}")
                    print(f"GRIS retornado: R$ {resultado['gris']:,.2f}")
                    
                    if abs(resultado['gris'] - gris_final_esperado) < 0.01:
                        print("✅ GRIS calculado corretamente!")
                    else:
                        print("❌ GRIS incorreto!")
            else:
                print("❌ Erro no processamento")
        
        # Buscar agente MARCO AURELIO
        print(f"\n" + "=" * 50)
        marco_agentes = df_agentes[df_agentes['Fornecedor'] == 'MARCO AURELIO']
        print(f"Registros do agente MARCO AURELIO: {len(marco_agentes)}")
        
        if len(marco_agentes) > 0:
            primeiro_marco = marco_agentes.iloc[0]
            
            print(f"\n📊 ANÁLISE DO AGENTE MARCO AURELIO:")
            print(f"Fornecedor: {primeiro_marco['Fornecedor']}")
            print(f"Origem: {primeiro_marco['Origem']}")
            print(f"Destino: {primeiro_marco['Destino']}")
            print(f"VALOR MÍNIMO ATÉ 10: R$ {primeiro_marco.get('VALOR MÍNIMO ATÉ 10', 'N/A')}")
            print(f"EXCEDENTE: R$ {primeiro_marco.get('EXCEDENTE', 'N/A')}")
            print(f"Pedagio (100 Kg): R$ {primeiro_marco.get('Pedagio (100 Kg)', 'N/A')}")
            print(f"GRIS Min: R$ {primeiro_marco.get('Gris Min', 'N/A')}")
            print(f"GRIS Exc: {primeiro_marco.get('Gris Exc', 'N/A')}%")
            print(f"Prazo: {primeiro_marco.get('Prazo', 'N/A')} dias")
            print(f"Peso Máximo: {primeiro_marco.get('PESO MÁXIMO TRANSPORTADO', 'N/A')} kg")
        
        # Verificar colunas disponíveis
        print(f"\n📋 COLUNAS DISPONÍVEIS NA PLANILHA:")
        for i, col in enumerate(df.columns):
            print(f"{i+1:2d}. {col}")
        
        # Verificar se há valores válidos para Prazo e Peso Máximo
        print(f"\n🔍 VERIFICAÇÃO DE DADOS VÁLIDOS:")
        prazo_validos = df_agentes['Prazo'].notna().sum()
        peso_max_validos = df_agentes['PESO MÁXIMO TRANSPORTADO'].notna().sum()
        gris_exc_validos = df_agentes['Gris Exc'].notna().sum()
        
        print(f"Agentes com Prazo válido: {prazo_validos}/{len(df_agentes)}")
        print(f"Agentes com Peso Máximo válido: {peso_max_validos}/{len(df_agentes)}")
        print(f"Agentes com GRIS Exc válido: {gris_exc_validos}/{len(df_agentes)}")
        
        # Mostrar alguns valores únicos
        print(f"\nPrazos únicos (primeiros 10): {df_agentes['Prazo'].dropna().unique()[:10]}")
        print(f"Pesos máximos únicos (primeiros 10): {df_agentes['PESO MÁXIMO TRANSPORTADO'].dropna().unique()[:10]}")
        print(f"GRIS Exc únicos (primeiros 10): {df_agentes['Gris Exc'].dropna().unique()[:10]}")
        
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    investigar_agentes() 