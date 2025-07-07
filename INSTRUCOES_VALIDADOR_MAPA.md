# 🗺️ Sistema de Validação de Posições das Siglas do Mapa do Brasil

## 📝 Descrição

Este sistema valida e corrige automaticamente as posições das siglas dos estados brasileiros no mapa SVG, garantindo que:

- ✅ Cada sigla esteja posicionada dentro dos limites geográficos corretos do seu estado
- ✅ Não haja colisões/sobreposições entre siglas (distância mínima de 30px)
- ✅ As posições sejam visualmente harmoniosas e funcionais
- ✅ O sistema funcione tanto offline (Python) quanto online (JavaScript)

## 🛠️ Componentes do Sistema

### 1. **Validador Python** (`validador_posicoes_mapa.py`)
- **Uso**: Validação offline completa e correção em lote
- **Funcionalidades**:
  - Análise detalhada de todas as 27 siglas
  - Relatório completo com estatísticas por região
  - Correção automática com algoritmo de posicionamento ótimo
  - Exportação para JSON e JavaScript

### 2. **Validador JavaScript** (`static/js/validador_mapa.js`)
- **Uso**: Validação em tempo real na interface web
- **Funcionalidades**:
  - Interface visual com botões de controle
  - Destaque colorido dos problemas no mapa
  - Correção individual ou em lote
  - Salvar no localStorage automaticamente

## 🚀 Como Usar

### **Validação Offline (Python)**

```bash
# Executar validação completa
python validador_posicoes_mapa.py

# O sistema irá:
# 1. Carregar posições atuais das siglas
# 2. Validar cada uma individualmente
# 3. Mostrar relatório detalhado
# 4. Oferecer correção automática
# 5. Gerar arquivos de saída
```

### **Validação Online (JavaScript)**

1. **Acesse a aba "Mapa de Agentes"** no sistema
2. **Controles automáticos** aparecerão no canto superior esquerdo
3. **Botões disponíveis**:
   - 🔍 **Validar Mapa**: Análise completa com relatório
   - 🎨 **Destacar Problemas**: Marca visualmente problemas em vermelho
   - 🎨 **Remover Destaque**: Remove cores do mapa
   - 💾 **Exportar**: Baixa arquivo JSON com posições

### **Via Console do Navegador**

```javascript
// Validação manual
validadorMapa.validarMapaCompleto()

// Corrigir estado específico
validadorMapa.corrigirSigla('AL')

// Aplicar todas as correções
validadorMapa.aplicarTodasCorrecoes()

// Destacar problemas visualmente
validadorMapa.destacarProblemas()

// Exportar posições
validadorMapa.exportarPosicoes()
```

## 📊 Exemplo de Resultados

### **Problemas Detectados**
```
❌ AL - Alagoas | Muito próximo de: PE (28.3px), SE (10.0px)
❌ AM - Amazonas | Muito próximo de: RR (23.3px) 
❌ DF - Distrito Federal | Muito próximo de: GO (27.7px)
❌ GO - Goiás | Muito próximo de: DF (27.7px)
```

### **Estatísticas**
- **Total de estados**: 27
- **Posições válidas**: 23 (85.2%)
- **Posições com problemas**: 4 (14.8%)

### **Correções Aplicadas**
```
✅ AL: (568.0, 235.0) → (575.0, 242.0)
✅ AM: (215.0, 130.0) → (225.0, 140.0)
✅ DF: (417.0, 334.0) → (410.0, 330.0)
✅ GO: (390.0, 340.0) → (395.0, 345.0)
```

## 🔧 Configurações Técnicas

### **Parâmetros de Validação**
```python
# Distância mínima entre siglas (pixels)
distancia_minima_siglas = 30

# Tolerância para limites geográficos (pixels)  
tolerancia_limites = 20
```

### **Limites Geográficos por Estado**
O sistema usa coordenadas precisas baseadas no SVG do mapa:

```python
'SP': {
    'min_x': 400, 'max_x': 470,    # Limites horizontais
    'min_y': 450, 'max_y': 510,    # Limites verticais
    'regiao': 'Sudeste'            # Região brasileira
}
```

### **Algoritmo de Correção**
1. **Centro Ótimo**: Tenta posicionar no centro geográfico do estado
2. **Busca Circular**: Se ocupado, busca em círculos concêntricos (raio 10-50px)
3. **Verificação Múltipla**: Testa 24 ângulos por círculo (15° de intervalo)
4. **Fallback Inteligente**: Retorna ao centro se não encontrar posição livre

## 📁 Arquivos Gerados

### **posicoes_corrigidas.json**
```json
{
  "AC": {"x": 55.0, "y": 240.0},
  "AL": {"x": 575.0, "y": 242.0},
  "AM": {"x": 225.0, "y": 140.0},
  ...
}
```

### **atualizar_posicoes.js**
```javascript
function atualizarPosicoesSiglas() {
    const posicoesCorrigidas = { ... };
    
    // Aplicar no DOM
    Object.entries(posicoesCorrigidas).forEach(([sigla, pos]) => {
        const elemento = document.querySelector(`[data-sigla="${sigla}"]`);
        if (elemento) {
            elemento.setAttribute('x', pos.x);
            elemento.setAttribute('y', pos.y);
        }
    });
}
```

## 🎯 Casos de Uso Práticos

### **1. Correção Após Mudanças no Mapa**
Quando o SVG do mapa é atualizado, execute a validação para garantir que as siglas continuem posicionadas corretamente.

### **2. Otimização Visual**
Use o validador para encontrar a melhor distribuição visual das siglas, evitando sobreposições.

### **3. Manutenção Preventiva**
Execute periodicamente para detectar problemas antes que afetem a experiência do usuário.

### **4. Integração com CI/CD**
Inclua o validador Python nos testes automatizados para garantir qualidade.

## 🔍 Debug e Troubleshooting

### **Problemas Comuns**

**1. Elemento não encontrado**
```javascript
// Verificar se a sigla existe no DOM
const elemento = document.querySelector('.estado-sigla:contains("SP")');
console.log(elemento ? "Encontrado" : "Não encontrado");
```

**2. Posições não salvam**
```javascript
// Verificar localStorage
console.log(localStorage.getItem('siglas_positions'));
```

**3. Validação não detecta problemas**
```javascript
// Ajustar tolerâncias
validadorMapa.distanciaMinima = 25; // Reduzir para detectar mais problemas
validadorMapa.toleranciaLimites = 15; // Ser mais restritivo
```

### **Logs Detalhados**
```javascript
// Ativar logs verbose
validadorMapa.debug = true;
validadorMapa.validarMapaCompleto();
```

## 🎨 Interface Visual

### **Cores dos Estados**
- 🟢 **Verde**: Posição válida
- 🔴 **Vermelho**: Problema detectado (pisca)
- 🔵 **Azul**: Estado sendo corrigido (temporário)

### **Modal de Relatório**
- 📊 Estatísticas visuais com gráficos
- 📋 Lista detalhada de problemas
- 🔧 Botões de correção individual
- 💾 Opções de exportação

### **Notificações Toast**
- ✅ Sucesso: Verde
- ❌ Erro: Vermelho  
- ⚠️ Aviso: Laranja
- ℹ️ Info: Azul

## 🚦 Workflow Recomendado

1. **📊 Análise**: Execute validação para entender estado atual
2. **🎨 Visualização**: Use destaque para ver problemas no mapa
3. **🔧 Correção**: Aplique correções automáticas ou manuais
4. **💾 Salvamento**: Exporte/salve as posições corrigidas
5. **✅ Validação**: Confirme que todos os problemas foram resolvidos

## 🔧 Integração com Sistema Existente

O validador se integra perfeitamente com o sistema de mapa existente:

- **Compatível** com `loadSavedPositions()`
- **Usa** o mesmo formato de localStorage
- **Respeita** o sistema de edição manual existente
- **Complementa** as funcionalidades de drag & drop

## 📈 Métricas de Qualidade

### **Metas de Validação**
- ✅ **95%** de posições válidas
- ✅ **0** colisões entre siglas
- ✅ **100%** siglas dentro dos limites geográficos
- ✅ **<2 segundos** tempo de validação

### **Indicadores de Performance**
- 🔄 Validação completa: ~200ms
- 🔧 Correção automática: ~500ms  
- 💾 Salvamento localStorage: ~50ms
- 🎨 Atualização visual: ~100ms

---

## 💡 Dicas Avançadas

### **Customização de Limites**
```javascript
// Ajustar limites específicos
validadorMapa.limitesEstados['SP'].min_x = 395;
validadorMapa.limitesEstados['SP'].max_x = 475;
```

### **Algoritmo Personalizado**
```javascript
// Implementar lógica de posicionamento customizada
validadorMapa.calcularPosicaoOtima = function(sigla) {
    // Sua lógica aqui
    return {x: novoX, y: novoY};
};
```

### **Integração com Backend**
```python
# Salvar posições validadas no banco
def salvar_posicoes_validadas():
    validador = ValidadorMapaBrasil()
    resultados = validador.validar_mapa_completo()
    
    # Integrar com seu sistema de persistência
    for sigla, resultado in resultados.items():
        if resultado.valido:
            save_to_database(sigla, resultado.posicao_atual)
```

🎉 **Sistema pronto para uso!** Agora você tem controle total sobre o posicionamento das siglas no mapa do Brasil. 