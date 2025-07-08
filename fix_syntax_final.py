#!/usr/bin/env python3
"""
Script final para corrigir problemas de sintaxe no arquivo improved_chico_automate_fpdf.py
"""

def fix_syntax():
    # Ler o arquivo
    with open('improved_chico_automate_fpdf.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Corrigir a estrutura try/except e indentação
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Encontrar o bloco problemático
        if 'except Exception as e:' in line and line.startswith(' ' * 13):
            # Encontramos o bloco problemático
            # Voltar algumas linhas para pegar o contexto
            context_start = max(0, i - 5)
            context = lines[context_start:i]
            
            # Verificar se há um try correspondente
            has_try = any('try:' in l for l in context)
            
            if not has_try:
                # Remover o bloco except malformado
                i += 3  # Pular as próximas 3 linhas (except + print + continue)
            else:
                new_lines.append(line)
                i += 1
        else:
            new_lines.append(line)
            i += 1
    
    # Escrever o arquivo corrigido
    with open('improved_chico_automate_fpdf.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print("Correções de sintaxe aplicadas!")

if __name__ == "__main__":
    fix_syntax() 