# Correções para Remover TH EXPRESS e Agentes Simulados

## Problema Identificado
TH EXPRESS está aparecendo porque o código busca agentes em "cidades próximas" quando não encontra na cidade específica. Para SC, isso inclui FLORIANOPOLIS, JOINVILLE, BLUMENAU, etc.

## Correções Necessárias

### 1. Na função `calcular_frete_com_agentes` (linha ~1390-1460)

**REMOVER** toda a lógica de busca expandida:

```python
# REMOVER TUDO ISSO:
if agentes_coleta.empty:
    # ESTRATÉGIA 0.5: Buscar agentes em cidades próximas primeiro
    print(f"[AGENTES] 🗺️ ESTRATÉGIA 0.5: Buscando agentes em cidades próximas a {origem_norm}...")
    
    # Mapa de cidades próximas
    cidades_proximas_mapa = {
        # ... todo o mapa ...
        '_DEFAULT_SC': ['FLORIANOPOLIS', 'JOINVILLE', 'BLUMENAU', 'ITAJAI', 'CHAPECO'],
        # ...
    }
    
    # ... toda a lógica de busca em cidades próximas ...
```

**SUBSTITUIR POR:**

```python
if agentes_coleta.empty:
    print(f"[AGENTES] ⚠️ Nenhum agente de coleta encontrado em {origem_norm}/{uf_origem}")
    # Manter vazio para permitir rotas parciais
```

### 2. Fazer o mesmo para agentes de entrega (linha ~1470-1540)

**REMOVER** todas as estratégias 1, 2, 3 e 4.

### 3. Modificar a lógica de rotas parciais (linha ~2000)

**ADICIONAR** após verificar se há agentes:

```python
# Se não há agentes de coleta, criar rotas parciais apenas com transferência
if agentes_coleta.empty and not transferencias_origem_destino.empty:
    print(f"[ROTAS] 🔄 Criando rotas parciais: Apenas Transferência (sem coleta)")
    for _, transf in transferencias_origem_destino.iterrows():
        # Criar rota com coleta = 0
        rota_parcial = {
            'tipo_rota': 'transferencia_direta',
            'resumo': f"PARCIAL: Cliente entrega → {transf.get('Fornecedor')} → Cliente retira",
            'total': calcular_custo_agente(transf, peso_cubado, valor_nf)['total'],
            'observacoes': 'ATENÇÃO: Sem agente de coleta - cliente deve entregar na origem',
            'agente_coleta': {
                'fornecedor': 'SEM AGENTE',
                'total': 0,
                'observacao': f"Cliente deve entregar em {origem}"
            },
            'transferencia': calcular_custo_agente(transf, peso_cubado, valor_nf),
            'agente_entrega': {
                'fornecedor': 'SEM AGENTE',
                'total': 0,
                'observacao': f"Cliente deve retirar em {destino}"
            }
        }
        rotas_encontradas.append(rota_parcial)
```

### 4. Corrigir erro 'bool' object has no attribute 'get'

Na função `extrair_detalhamento_custos` (linha ~3380), verificar se os objetos são dicionários antes de usar .get():

```python
# Verificar tipo antes de extrair
if isinstance(agente_coleta, dict):
    custo_coleta = agente_coleta.get('total', 0)
else:
    custo_coleta = 0
```

## Resultado Esperado

1. **Sem TH EXPRESS**: Não aparecerá mais agentes de outras cidades
2. **Rotas Parciais**: Quando não houver agente, mostrar apenas transferência com valor 0 para coleta/entrega
3. **Transparência**: Cliente verá claramente onde precisa entregar/retirar a carga

## Exemplo de Saída Esperada

Para Itajaí → São Paulo sem agente em Itajaí:
```
PARCIAL: Cliente entrega → JEM/DFL → FILIAL SP
- Coleta: R$ 0,00 (Cliente entrega em Itajaí)
- Transferência: R$ 136,32
- Entrega: R$ 138,00
- Total: R$ 274,32
```