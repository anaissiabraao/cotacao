# Freight Calculation Issue Analysis and Fix

## Problem Identified

The freight calculation system was returning zero cost for transfer routes (Jem/Dfl and SOL), causing them to be marked as invalid and excluded from results.

### Root Cause

In the transfer cost calculation logic (lines 2795-2805 in `improved_chico_automate_fpdf.py`), there was a bug in how weight-based pricing columns were being accessed:

```python
# INCORRECT: Converting integer column names to strings
valor_base_kg = float(linha.get(str(colunas_peso[i]), 0))
```

### Issue Details

1. **Column Structure**: The Excel base file (`Base_Unificada.xlsx`) has numeric weight columns as integers:
   - `['VALOR MÍNIMO ATÉ 10', 20, 30, 50, 70, 100, 150, 200, 300, 500, 'Acima 500']`

2. **Bug**: The code was converting integer column names to strings, so:
   - For a 90kg weight → falls into 100kg faixa (index 5)
   - `colunas_peso[5]` = `100` (integer)
   - `str(colunas_peso[5])` = `"100"` (string)
   - DataFrame lookup for column `"100"` failed → returned default value 0

3. **Result**: All transfer calculations returned R$ 0.00, causing routes to be invalid

### Log Evidence

From the error log:
```
[CUSTO-TRANSF] ✅ Peso 90.0kg na faixa até 100kg: 90.0kg × R$ 0.0000 = R$ 0.00
[CUSTO] ❌ Total inválido para Jem/Dfl: R$ 0.00
```

The pricing rate was 0.0000 because the column lookup failed.

## Fix Applied

**File**: `improved_chico_automate_fpdf.py`  
**Lines**: 2797 and 2803

### Before:
```python
valor_base_kg = float(linha.get(str(colunas_peso[i]), 0))
# and
valor_base_kg = float(linha.get(colunas_peso[-1], 0))
```

### After:
```python
col_name = colunas_peso[i]
valor_base_kg = float(linha.get(col_name, 0))
# and
col_name = colunas_peso[-1]
valor_base_kg = float(linha.get(col_name, 0))
```

## Impact

This fix should resolve the issue where transfer routes were being calculated as R$ 0.00, allowing them to be properly included in freight calculations for routes like:
- Ribeirão Preto/SP → Rio de Janeiro/RJ
- And other inter-state transfer routes

## Testing Recommendation

Test the same route that failed:
- **Origin**: Ribeirão Preto/SP
- **Destination**: Rio de Janeiro/RJ
- **Weight**: 90kg
- **Volume**: 0.01m³
- **Invoice Value**: R$ 10,000

The transfer routes (Jem/Dfl and SOL) should now return valid cost calculations instead of R$ 0.00.