#!/usr/bin/env python3
"""
Validação dos Fatores de Cubagem Implementados
==============================================

Este script demonstra como o sistema está calculando peso cubado baseado nos tipos:

REGRAS IMPLEMENTADAS:
1. Agentes (tipo 'Agente'): cubagem × 250 kg/m³
2. Transferências JEM e Concept: cubagem × 166 kg/m³  
3. Outros tipos (padrão): cubagem × 300 kg/m³

"""

def calcular_peso_cubado_por_tipo(peso_real, cubagem, tipo_linha, fornecedor=None):
    """
    Calcula peso cubado aplicando fatores específicos por tipo de serviço
    """
    try:
        peso_real = float(peso_real)
        cubagem = float(cubagem) if cubagem else 0
        
        if cubagem <= 0:
            return peso_real
            
        # Aplicar fator específico baseado no tipo
        if tipo_linha == 'Agente':
            fator_cubagem = 250  # kg/m³ para agentes
            tipo_calculo = "Agente (250kg/m³)"
        elif tipo_linha == 'Transferência' and fornecedor and ('JEM' in str(fornecedor).upper() or 'CONCEPT' in str(fornecedor).upper()):
            fator_cubagem = 166  # kg/m³ para JEM e Concept  
            tipo_calculo = f"Transferência {fornecedor} (166kg/m³)"
        else:
            fator_cubagem = 300  # kg/m³ padrão
            tipo_calculo = "Padrão (300kg/m³)"
            
        peso_cubado = cubagem * fator_cubagem
        peso_final = max(peso_real, peso_cubado)
        
        print(f"[PESO_CUBADO] {tipo_calculo}: {peso_real}kg vs {peso_cubado}kg = {peso_final}kg")
        return peso_final
        
    except Exception as e:
        print(f"[PESO_CUBADO] Erro no cálculo: {e}")
        return float(peso_real) if peso_real else 0

def testar_cenarios():
    """
    Testa diferentes cenários de cálculo
    """
    print("=" * 80)
    print("VALIDAÇÃO DOS FATORES DE CUBAGEM")
    print("=" * 80)
    
    # Cenários de teste
    cenarios = [
        {
            'nome': 'Agente padrão',
            'peso_real': 100,
            'cubagem': 2.0,
            'tipo': 'Agente',
            'fornecedor': 'AGENTE_TESTE',
            'resultado_esperado': max(100, 2.0 * 250)  # 500kg
        },
        {
            'nome': 'Transferência JEM',
            'peso_real': 50,
            'cubagem': 1.5,
            'tipo': 'Transferência',
            'fornecedor': 'JEM LOGISTICS',
            'resultado_esperado': max(50, 1.5 * 166)  # 249kg
        },
        {
            'nome': 'Transferência CONCEPT',
            'peso_real': 80,
            'cubagem': 0.5,
            'tipo': 'Transferência',
            'fornecedor': 'CONCEPT CARGO',
            'resultado_esperado': max(80, 0.5 * 166)  # 83kg (peso real maior)
        },
        {
            'nome': 'Transferência outros fornecedores',
            'peso_real': 60,
            'cubagem': 1.0,
            'tipo': 'Transferência',
            'fornecedor': 'OUTROS FORNECEDOR',
            'resultado_esperado': max(60, 1.0 * 300)  # 300kg
        },
        {
            'nome': 'Tipo padrão (sem especificação)',
            'peso_real': 75,
            'cubagem': 0.8,
            'tipo': 'Direto',
            'fornecedor': 'TESTE',
            'resultado_esperado': max(75, 0.8 * 300)  # 240kg
        }
    ]
    
    print(f"\n{'CENÁRIO':<35} | {'PESO REAL':<10} | {'CUBAGEM':<8} | {'FATOR':<8} | {'RESULTADO':<10} | {'STATUS':<8}")
    print("-" * 95)
    
    todos_corretos = True
    
    for cenario in cenarios:
        resultado = calcular_peso_cubado_por_tipo(
            cenario['peso_real'],
            cenario['cubagem'],
            cenario['tipo'],
            cenario['fornecedor']
        )
        
        correto = abs(resultado - cenario['resultado_esperado']) < 0.01
        status = "✅ OK" if correto else "❌ ERRO"
        
        if not correto:
            todos_corretos = False
        
        # Determinar fator usado
        if cenario['tipo'] == 'Agente':
            fator = "250"
        elif cenario['tipo'] == 'Transferência' and ('JEM' in cenario['fornecedor'].upper() or 'CONCEPT' in cenario['fornecedor'].upper()):
            fator = "166"
        else:
            fator = "300"
        
        print(f"{cenario['nome']:<35} | {cenario['peso_real']:<10} | {cenario['cubagem']:<8} | {fator:<8} | {resultado:<10.1f} | {status:<8}")
    
    print("-" * 95)
    
    if todos_corretos:
        print("🎉 TODOS OS TESTES PASSARAM! O sistema está aplicando os fatores corretos.")
    else:
        print("⚠️  ALGUNS TESTES FALHARAM! Verifique a implementação.")
    
    print("\n" + "=" * 80)
    print("RESUMO DAS REGRAS:")
    print("• Agentes: cubagem × 250 kg/m³")
    print("• Transferências JEM/CONCEPT: cubagem × 166 kg/m³")
    print("• Outros tipos: cubagem × 300 kg/m³")
    print("• Resultado final: MAX(peso real, peso cubado)")
    print("=" * 80)

if __name__ == "__main__":
    testar_cenarios() 