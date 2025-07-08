#!/usr/bin/env python3
"""
Script para corrigir problemas de indentação no arquivo improved_chico_automate_fpdf.py
"""

def corrigir_arquivo():
    # Ler o arquivo
    with open('improved_chico_automate_fpdf.py', 'r', encoding='utf-8') as f:
        linhas = f.readlines()
    
    print(f"Total de linhas: {len(linhas)}")
    
    # Corrigir problemas específicos
    for i, linha in enumerate(linhas):
        linha_num = i + 1
        
        # Problema 1: Linha 1620 - if deve estar dentro do try
        if linha_num == 1620 and linha.strip().startswith('if custo_coleta'):
            if not linha.startswith('                            if'):
                linhas[i] = '                            if custo_coleta and custo_transferencia and custo_entrega:\n'
                print(f"Corrigida linha {linha_num}: indentação do if")
        
        # Problema 2: Linha 1674 - else solto
        if linha_num == 1674 and linha.strip() == 'else:':
            if not linha.startswith('                            else:'):
                linhas[i] = '                            else:\n'
                print(f"Corrigida linha {linha_num}: indentação do else")
        
        # Problema 3: Linha 1675 - print após else
        if linha_num == 1675 and 'Erro no cálculo de custos' in linha:
            if not linha.startswith('                                print'):
                linhas[i] = '                                print(f"[AGENTES] ⚠️ Erro no cálculo de custos para rota via base")\n'
                print(f"Corrigida linha {linha_num}: indentação do print após else")
        
        # Problema 4: Linhas de peso_cubado mal indentadas (1615-1619)
        if linha_num >= 1615 and linha_num <= 1619:
            if 'peso_cubado_' in linha and not linha.startswith('                            peso_cubado_'):
                # Corrigir indentação
                linhas[i] = '                            ' + linha.lstrip()
                print(f"Corrigida linha {linha_num}: indentação do cálculo de peso_cubado")
        
        # Problema 5: Linhas de custo_* mal indentadas (1620-1622)
        if linha_num >= 1620 and linha_num <= 1622:
            if 'custo_' in linha and not linha.startswith('                            custo_'):
                linhas[i] = '                            ' + linha.lstrip()
                print(f"Corrigida linha {linha_num}: indentação do cálculo de custo")
    
    # Escrever o arquivo corrigido
    with open('improved_chico_automate_fpdf.py', 'w', encoding='utf-8') as f:
        f.writelines(linhas)
    
    print("Arquivo corrigido!")

if __name__ == "__main__":
    corrigir_arquivo() 