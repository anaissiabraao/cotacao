#!/usr/bin/env python3
"""
Script para corrigir problemas estruturais no código improved_chico_automate_fpdf.py
"""

def corrigir_estrutura():
    try:
        with open('improved_chico_automate_fpdf.py', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"Total de linhas: {len(lines)}")
        
        # Localizar e corrigir o problema nas linhas ~1739
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Problema: código mal posicionado após um loop for
            if line_num == 1739 and 'if not agentes_entrega.empty:' in line:
                print(f"Linha {line_num}: {line.strip()}")
                # Verificar se está com indentação incorreta
                if line.startswith('                    if'):  # 20 espaços
                    # Corrigir para 13 espaços (fora dos loops)
                    lines[i] = '             if not agentes_entrega.empty:\n'
                    print(f"Corrigido para: if not agentes_entrega.empty: (13 espaços)")
            
            elif line_num == 1740 and 'Processamento de rotas parciais concluído' in line:
                print(f"Linha {line_num}: {line.strip()}")
                lines[i] = '                 print(f"[AGENTES] ✅ Processamento de rotas parciais concluído")\n'
                print(f"Corrigido para: 17 espaços")
            
            elif line_num == 1741 and line.strip() == 'else:':
                print(f"Linha {line_num}: {line.strip()}")
                lines[i] = '             else:\n'
                print(f"Corrigido para: else: (13 espaços)")
            
            elif line_num == 1742 and 'Sem agentes de entrega para criar rotas parciais' in line:
                print(f"Linha {line_num}: {line.strip()}")
                lines[i] = '                 print(f"[AGENTES] ⚠️ Sem agentes de entrega para criar rotas parciais")\n'
                print(f"Corrigido para: 17 espaços")
        
        # Salvar o arquivo corrigido
        with open('improved_chico_automate_fpdf.py', 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print("✅ Estrutura do código corrigida com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao corrigir estrutura: {e}")
        return False

if __name__ == "__main__":
    corrigir_estrutura() 