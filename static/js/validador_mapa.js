/**
 * Validador de Posições das Siglas do Mapa do Brasil
 * Sistema JavaScript para validação em tempo real
 * Versão: 1.0
 */

class ValidadorMapaBrasil {
    constructor() {
        this.distanciaMinima = 30; // Distância mínima entre siglas (pixels)
        this.toleranciaLimites = 20; // Tolerância para limites (pixels)
        
        // Limites geográficos dos estados (baseado no SVG)
        this.limitesEstados = {
            // REGIÃO NORTE
            'AC': { min_x: 15, max_x: 95, min_y: 200, max_y: 280, regiao: 'Norte' },
            'AP': { min_x: 250, max_x: 320, min_y: 80, max_y: 180, regiao: 'Norte' },
            'AM': { min_x: 120, max_x: 310, min_y: 90, max_y: 200, regiao: 'Norte' },
            'PA': { min_x: 280, max_x: 400, min_y: 120, max_y: 240, regiao: 'Norte' },
            'RO': { min_x: 130, max_x: 190, min_y: 250, max_y: 320, regiao: 'Norte' },
            'RR': { min_x: 200, max_x: 270, min_y: 80, max_y: 160, regiao: 'Norte' },
            'TO': { min_x: 380, max_x: 450, min_y: 200, max_y: 280, regiao: 'Norte' },
            
            // REGIÃO NORDESTE
            'AL': { min_x: 550, max_x: 590, min_y: 220, max_y: 250, regiao: 'Nordeste' },
            'BA': { min_x: 460, max_x: 590, min_y: 220, max_y: 380, regiao: 'Nordeste' },
            'CE': { min_x: 520, max_x: 580, min_y: 140, max_y: 200, regiao: 'Nordeste' },
            'MA': { min_x: 420, max_x: 510, min_y: 140, max_y: 220, regiao: 'Nordeste' },
            'PB': { min_x: 575, max_x: 615, min_y: 175, max_y: 215, regiao: 'Nordeste' },
            'PE': { min_x: 520, max_x: 590, min_y: 190, max_y: 240, regiao: 'Nordeste' },
            'PI': { min_x: 470, max_x: 540, min_y: 160, max_y: 210, regiao: 'Nordeste' },
            'RN': { min_x: 575, max_x: 615, min_y: 160, max_y: 195, regiao: 'Nordeste' },
            'SE': { min_x: 550, max_x: 585, min_y: 235, max_y: 265, regiao: 'Nordeste' },
            
            // REGIÃO CENTRO-OESTE
            'DF': { min_x: 410, max_x: 425, min_y: 325, max_y: 340, regiao: 'Centro-Oeste' },
            'GO': { min_x: 350, max_x: 450, min_y: 300, max_y: 380, regiao: 'Centro-Oeste' },
            'MT': { min_x: 220, max_x: 350, min_y: 260, max_y: 380, regiao: 'Centro-Oeste' },
            'MS': { min_x: 270, max_x: 360, min_y: 420, max_y: 490, regiao: 'Centro-Oeste' },
            
            // REGIÃO SUDESTE
            'ES': { min_x: 475, max_x: 510, min_y: 390, max_y: 440, regiao: 'Sudeste' },
            'MG': { min_x: 420, max_x: 530, min_y: 330, max_y: 420, regiao: 'Sudeste' },
            'RJ': { min_x: 440, max_x: 485, min_y: 440, max_y: 475, regiao: 'Sudeste' },
            'SP': { min_x: 400, max_x: 470, min_y: 450, max_y: 510, regiao: 'Sudeste' },
            
            // REGIÃO SUL
            'PR': { min_x: 350, max_x: 430, min_y: 480, max_y: 530, regiao: 'Sul' },
            'RS': { min_x: 300, max_x: 420, min_y: 540, max_y: 640, regiao: 'Sul' },
            'SC': { min_x: 340, max_x: 420, min_y: 530, max_y: 570, regiao: 'Sul' }
        };
        
        // Centros geográficos ótimos
        this.centrosOtimos = {
            'AC': {x: 55, y: 240}, 'AL': {x: 568, y: 235}, 'AP': {x: 285, y: 128},
            'AM': {x: 215, y: 130}, 'BA': {x: 527, y: 270}, 'CE': {x: 548, y: 168},
            'DF': {x: 417, y: 334}, 'ES': {x: 492, y: 415}, 'GO': {x: 390, y: 340},
            'MA': {x: 458, y: 180}, 'MG': {x: 470, y: 370}, 'MS': {x: 315, y: 455},
            'MT': {x: 275, y: 310}, 'PA': {x: 328, y: 160}, 'PB': {x: 595, y: 195},
            'PE': {x: 548, y: 215}, 'PI': {x: 505, y: 185}, 'PR': {x: 390, y: 505},
            'RJ': {x: 458, y: 455}, 'RN': {x: 595, y: 178}, 'RS': {x: 358, y: 588},
            'RO': {x: 158, y: 285}, 'RR': {x: 235, y: 118}, 'SC': {x: 378, y: 548},
            'SP': {x: 435, y: 475}, 'SE': {x: 568, y: 245}, 'TO': {x: 415, y: 238}
        };
    }
    
    /**
     * Obtém todas as siglas do mapa
     */
    obterSiglas() {
        return document.querySelectorAll('.estado-sigla');
    }
    
    /**
     * Obtém posição atual de uma sigla
     */
    obterPosicaoSigla(elemento) {
        return {
            x: parseFloat(elemento.getAttribute('x')),
            y: parseFloat(elemento.getAttribute('y')),
            sigla: elemento.textContent.trim()
        };
    }
    
    /**
     * Calcula distância entre duas posições
     */
    calcularDistancia(pos1, pos2) {
        return Math.sqrt(Math.pow(pos1.x - pos2.x, 2) + Math.pow(pos1.y - pos2.y, 2));
    }
    
    /**
     * Verifica se posição está dentro dos limites
     */
    dentroDosLimites(posicao, sigla) {
        const limites = this.limitesEstados[sigla];
        if (!limites) return false;
        
        return (posicao.x >= limites.min_x - this.toleranciaLimites &&
                posicao.x <= limites.max_x + this.toleranciaLimites &&
                posicao.y >= limites.min_y - this.toleranciaLimites &&
                posicao.y <= limites.max_y + this.toleranciaLimites);
    }
    
    /**
     * Verifica conflitos de proximidade
     */
    verificarConflitos(posicao, siglaAtual) {
        const conflitos = [];
        const siglas = this.obterSiglas();
        
        siglas.forEach(elemento => {
            const outraPosicao = this.obterPosicaoSigla(elemento);
            if (outraPosicao.sigla !== siglaAtual) {
                const distancia = this.calcularDistancia(posicao, outraPosicao);
                if (distancia < this.distanciaMinima) {
                    conflitos.push({
                        sigla: outraPosicao.sigla,
                        distancia: distancia
                    });
                }
            }
        });
        
        return conflitos;
    }
    
    /**
     * Valida posição de uma sigla específica
     */
    validarSigla(sigla) {
        const elemento = this.encontrarElementoSigla(sigla);
        if (!elemento) {
            return {
                valido: false,
                motivo: 'Elemento não encontrado',
                sigla: sigla
            };
        }
        
        const posicao = this.obterPosicaoSigla(elemento);
        const erros = [];
        
        // Verificar limites geográficos
        if (!this.dentroDosLimites(posicao, sigla)) {
            const limites = this.limitesEstados[sigla];
            erros.push(`Fora dos limites geográficos (${limites.min_x}-${limites.max_x}, ${limites.min_y}-${limites.max_y})`);
        }
        
        // Verificar conflitos
        const conflitos = this.verificarConflitos(posicao, sigla);
        if (conflitos.length > 0) {
            const conflitosTexto = conflitos.map(c => `${c.sigla} (${c.distancia.toFixed(1)}px)`).join(', ');
            erros.push(`Muito próximo de: ${conflitosTexto}`);
        }
        
        return {
            valido: erros.length === 0,
            motivo: erros.length > 0 ? erros.join('; ') : 'Posição válida',
            sigla: sigla,
            posicao: posicao,
            conflitos: conflitos,
            posicaoSugerida: erros.length > 0 ? this.calcularPosicaoOtima(sigla) : null
        };
    }
    
    /**
     * Encontra elemento da sigla no DOM
     */
    encontrarElementoSigla(sigla) {
        const siglas = this.obterSiglas();
        for (let elemento of siglas) {
            if (elemento.textContent.trim() === sigla) {
                return elemento;
            }
        }
        return null;
    }
    
    /**
     * Calcula posição ótima para uma sigla
     */
    calcularPosicaoOtima(sigla) {
        const centroOtimo = this.centrosOtimos[sigla];
        if (!centroOtimo) return null;
        
        // Verificar se o centro ótimo está livre
        if (this.posicaoLivre(centroOtimo, sigla)) {
            return centroOtimo;
        }
        
        // Buscar posição livre em círculos concêntricos
        for (let raio = 10; raio <= 50; raio += 5) {
            for (let angulo = 0; angulo < 360; angulo += 15) {
                const rad = angulo * Math.PI / 180;
                const novaPosicao = {
                    x: centroOtimo.x + raio * Math.cos(rad),
                    y: centroOtimo.y + raio * Math.sin(rad)
                };
                
                if (this.dentroDosLimites(novaPosicao, sigla) && 
                    this.posicaoLivre(novaPosicao, sigla)) {
                    return novaPosicao;
                }
            }
        }
        
        return centroOtimo; // Fallback para centro ótimo
    }
    
    /**
     * Verifica se posição está livre
     */
    posicaoLivre(posicao, siglaExcluir) {
        const conflitos = this.verificarConflitos(posicao, siglaExcluir);
        return conflitos.length === 0;
    }
    
    /**
     * Valida todo o mapa
     */
    validarMapaCompleto() {
        console.log('🔍 Iniciando validação completa do mapa...');
        
        const resultados = {};
        const siglas = Object.keys(this.limitesEstados);
        
        let validos = 0;
        let problemas = 0;
        
        siglas.forEach(sigla => {
            const resultado = this.validarSigla(sigla);
            resultados[sigla] = resultado;
            
            if (resultado.valido) {
                validos++;
                console.log(`✅ ${sigla} - ${resultado.motivo}`);
            } else {
                problemas++;
                console.log(`❌ ${sigla} - ${resultado.motivo}`);
            }
        });
        
        console.log(`\n📊 Resultados: ${validos} válidos, ${problemas} com problemas`);
        
        // Mostrar relatório na interface
        this.exibirRelatorio(resultados);
        
        return resultados;
    }
    
    /**
     * Exibe relatório na interface
     */
    exibirRelatorio(resultados) {
        const problemas = Object.values(resultados).filter(r => !r.valido);
        
        if (problemas.length === 0) {
            this.mostrarToast('✅ Todas as posições estão válidas!', 'success');
            return;
        }
        
        // Criar modal com relatório
        const modal = this.criarModalRelatorio(resultados);
        document.body.appendChild(modal);
        
        // Mostrar modal
        setTimeout(() => modal.style.opacity = '1', 100);
    }
    
    /**
     * Cria modal com relatório detalhado
     */
    criarModalRelatorio(resultados) {
        const modal = document.createElement('div');
        modal.className = 'validador-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 10000;
            opacity: 0;
            transition: opacity 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        
        const problemas = Object.values(resultados).filter(r => !r.valido);
        const validos = Object.values(resultados).filter(r => r.valido);
        
        modal.innerHTML = `
            <div style="
                background: white;
                border-radius: 12px;
                padding: 0;
                max-width: 600px;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 20px 40px rgba(0,0,0,0.3);
                width: 90%;
            ">
                <div style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 12px 12px 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <h3 style="margin: 0; font-size: 1.4rem;">
                        🗺️ Relatório de Validação do Mapa
                    </h3>
                    <button onclick="this.closest('.validador-modal').remove()" style="
                        background: none;
                        border: none;
                        color: white;
                        font-size: 24px;
                        cursor: pointer;
                        padding: 0;
                        width: 30px;
                        height: 30px;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    ">&times;</button>
                </div>
                
                <div style="padding: 20px;">
                    <div style="
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 20px;
                        margin-bottom: 20px;
                        text-align: center;
                    ">
                        <div style="
                            padding: 15px;
                            background: #e8f5e9;
                            border-radius: 8px;
                            border: 2px solid #4caf50;
                        ">
                            <div style="font-size: 2rem; color: #2e7d32;">✅</div>
                            <div style="font-weight: bold; color: #2e7d32;">${validos.length} Válidos</div>
                            <div style="font-size: 0.9rem; color: #666;">
                                ${(validos.length / Object.keys(resultados).length * 100).toFixed(1)}%
                            </div>
                        </div>
                        
                        <div style="
                            padding: 15px;
                            background: #ffebee;
                            border-radius: 8px;
                            border: 2px solid #f44336;
                        ">
                            <div style="font-size: 2rem; color: #c62828;">❌</div>
                            <div style="font-weight: bold; color: #c62828;">${problemas.length} Problemas</div>
                            <div style="font-size: 0.9rem; color: #666;">
                                ${(problemas.length / Object.keys(resultados).length * 100).toFixed(1)}%
                            </div>
                        </div>
                    </div>
                    
                    ${problemas.length > 0 ? `
                        <h4 style="color: #c62828; margin-bottom: 15px;">🔴 Estados com Problemas:</h4>
                        <div style="max-height: 300px; overflow-y: auto;">
                            ${problemas.map(problema => `
                                <div style="
                                    border: 1px solid #ddd;
                                    border-radius: 6px;
                                    padding: 12px;
                                    margin-bottom: 10px;
                                    background: #fafafa;
                                ">
                                    <div style="
                                        font-weight: bold;
                                        color: #333;
                                        margin-bottom: 5px;
                                        display: flex;
                                        justify-content: space-between;
                                        align-items: center;
                                    ">
                                        <span>${problema.sigla} - ${this.limitesEstados[problema.sigla]?.regiao || 'N/A'}</span>
                                        <button onclick="validadorMapa.corrigirSigla('${problema.sigla}')" style="
                                            background: #4caf50;
                                            color: white;
                                            border: none;
                                            padding: 4px 8px;
                                            border-radius: 4px;
                                            font-size: 0.8rem;
                                            cursor: pointer;
                                        ">Corrigir</button>
                                    </div>
                                    <div style="font-size: 0.9rem; color: #666;">
                                        ${problema.motivo}
                                    </div>
                                    <div style="font-size: 0.8rem; color: #999; margin-top: 5px;">
                                        Atual: (${problema.posicao?.x?.toFixed(1)}, ${problema.posicao?.y?.toFixed(1)})
                                        ${problema.posicaoSugerida ? 
                                            ` → Sugerida: (${problema.posicaoSugerida.x.toFixed(1)}, ${problema.posicaoSugerida.y.toFixed(1)})` 
                                            : ''
                                        }
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    ` : '<p style="text-align: center; color: #4caf50; font-weight: bold;">🎉 Todas as posições estão corretas!</p>'}
                    
                    <div style="
                        display: flex;
                        gap: 10px;
                        margin-top: 20px;
                        justify-content: center;
                    ">
                        ${problemas.length > 0 ? `
                            <button onclick="validadorMapa.aplicarTodasCorrecoes()" style="
                                background: #4caf50;
                                color: white;
                                border: none;
                                padding: 10px 20px;
                                border-radius: 6px;
                                cursor: pointer;
                                font-weight: bold;
                            ">🔧 Corrigir Todas</button>
                        ` : ''}
                        
                        <button onclick="validadorMapa.exportarPosicoes()" style="
                            background: #2196f3;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 6px;
                            cursor: pointer;
                            font-weight: bold;
                        ">💾 Exportar</button>
                        
                        <button onclick="this.closest('.validador-modal').remove()" style="
                            background: #666;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 6px;
                            cursor: pointer;
                        ">Fechar</button>
                    </div>
                </div>
            </div>
        `;
        
        return modal;
    }
    
    /**
     * Corrige posição de uma sigla específica
     */
    corrigirSigla(sigla) {
        const resultado = this.validarSigla(sigla);
        if (resultado.valido || !resultado.posicaoSugerida) {
            this.mostrarToast(`✅ ${sigla} já está em posição válida`, 'info');
            return;
        }
        
        const elemento = this.encontrarElementoSigla(sigla);
        if (!elemento) {
            this.mostrarToast(`❌ Elemento ${sigla} não encontrado`, 'error');
            return;
        }
        
        // Aplicar nova posição
        elemento.setAttribute('x', resultado.posicaoSugerida.x);
        elemento.setAttribute('y', resultado.posicaoSugerida.y);
        
        // Animação visual
        elemento.style.transition = 'fill 0.3s ease';
        elemento.style.fill = '#4caf50';
        setTimeout(() => {
            elemento.style.fill = '';
        }, 1000);
        
        this.mostrarToast(`✅ ${sigla} corrigido com sucesso!`, 'success');
        
        console.log(`✅ ${sigla} corrigido: (${resultado.posicao.x}, ${resultado.posicao.y}) → (${resultado.posicaoSugerida.x}, ${resultado.posicaoSugerida.y})`);
    }
    
    /**
     * Aplica todas as correções automaticamente
     */
    aplicarTodasCorrecoes() {
        const resultados = this.validarMapaCompleto();
        const problemas = Object.values(resultados).filter(r => !r.valido);
        
        if (problemas.length === 0) {
            this.mostrarToast('✅ Nenhuma correção necessária!', 'info');
            return;
        }
        
        let corrigidos = 0;
        problemas.forEach(problema => {
            if (problema.posicaoSugerida) {
                const elemento = this.encontrarElementoSigla(problema.sigla);
                if (elemento) {
                    elemento.setAttribute('x', problema.posicaoSugerida.x);
                    elemento.setAttribute('y', problema.posicaoSugerida.y);
                    corrigidos++;
                }
            }
        });
        
        // Salvar posições
        this.salvarPosicoes();
        
        // Fechar modal
        const modal = document.querySelector('.validador-modal');
        if (modal) modal.remove();
        
        this.mostrarToast(`✅ ${corrigidos} posições corrigidas com sucesso!`, 'success');
        
        console.log(`🎉 Correção automática concluída: ${corrigidos} siglas corrigidas`);
    }
    
    /**
     * Salva posições no localStorage
     */
    salvarPosicoes() {
        const posicoes = {};
        const siglas = this.obterSiglas();
        
        siglas.forEach(elemento => {
            const posicao = this.obterPosicaoSigla(elemento);
            posicoes[posicao.sigla] = {
                x: Math.round(posicao.x * 10) / 10,
                y: Math.round(posicao.y * 10) / 10
            };
        });
        
        try {
            localStorage.setItem('siglas_positions', JSON.stringify(posicoes));
            console.log('💾 Posições salvas no localStorage');
            return true;
        } catch (e) {
            console.error('❌ Erro ao salvar posições:', e);
            return false;
        }
    }
    
    /**
     * Exporta posições como JSON
     */
    exportarPosicoes() {
        const posicoes = {};
        const siglas = this.obterSiglas();
        
        siglas.forEach(elemento => {
            const posicao = this.obterPosicaoSigla(elemento);
            posicoes[posicao.sigla] = {
                x: Math.round(posicao.x * 10) / 10,
                y: Math.round(posicao.y * 10) / 10
            };
        });
        
        // Criar arquivo para download
        const dataStr = JSON.stringify(posicoes, null, 2);
        const dataBlob = new Blob([dataStr], {type: 'application/json'});
        
        const link = document.createElement('a');
        link.href = URL.createObjectURL(dataBlob);
        link.download = 'posicoes_mapa_brasil.json';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        this.mostrarToast('💾 Arquivo exportado com sucesso!', 'success');
    }
    
    /**
     * Mostra notificação toast
     */
    mostrarToast(mensagem, tipo = 'info') {
        const cores = {
            success: '#4caf50',
            error: '#f44336',
            warning: '#ff9800',
            info: '#2196f3'
        };
        
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${cores[tipo]};
            color: white;
            padding: 12px 20px;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 10001;
            font-weight: 500;
            max-width: 300px;
            opacity: 0;
            transform: translateX(100%);
            transition: all 0.3s ease;
        `;
        toast.textContent = mensagem;
        
        document.body.appendChild(toast);
        
        // Animar entrada
        setTimeout(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(0)';
        }, 100);
        
        // Remover após 4 segundos
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => document.body.removeChild(toast), 300);
        }, 4000);
    }
    
    /**
     * Destaque visual para problemas
     */
    destacarProblemas() {
        const resultados = this.validarMapaCompleto();
        
        Object.values(resultados).forEach(resultado => {
            const elemento = this.encontrarElementoSigla(resultado.sigla);
            if (elemento) {
                if (resultado.valido) {
                    // Verde para válidos
                    elemento.style.fill = '#4caf50';
                } else {
                    // Vermelho para problemas
                    elemento.style.fill = '#f44336';
                    elemento.style.animation = 'pulse 2s infinite';
                }
                
                // Adicionar title com informações
                elemento.setAttribute('title', 
                    `${resultado.sigla}: ${resultado.motivo}`
                );
            }
        });
        
        // Adicionar CSS para animação
        if (!document.querySelector('#validador-styles')) {
            const style = document.createElement('style');
            style.id = 'validador-styles';
            style.textContent = `
                @keyframes pulse {
                    0% { opacity: 1; }
                    50% { opacity: 0.5; }
                    100% { opacity: 1; }
                }
            `;
            document.head.appendChild(style);
        }
        
        this.mostrarToast('🎨 Problemas destacados no mapa', 'info');
    }
    
    /**
     * Remove destaque visual
     */
    removerDestaque() {
        const siglas = this.obterSiglas();
        siglas.forEach(elemento => {
            elemento.style.fill = '';
            elemento.style.animation = '';
            elemento.removeAttribute('title');
        });
        
        this.mostrarToast('🎨 Destaque removido', 'info');
    }
}

// Inicializar validador global
window.validadorMapa = new ValidadorMapaBrasil();

// Adicionar botões de controle na interface
function adicionarControlesValidador() {
    // Verificar se já existe
    if (document.querySelector('#validador-controls')) return;
    
    const controles = document.createElement('div');
    controles.id = 'validador-controls';
    controles.style.cssText = `
        position: fixed;
        top: 80px;
        left: 20px;
        z-index: 1000;
        background: rgba(255,255,255,0.95);
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        display: flex;
        flex-direction: column;
        gap: 8px;
        min-width: 200px;
    `;
    
    controles.innerHTML = `
        <h4 style="margin: 0 0 10px 0; color: #333; font-size: 1rem;">
            🗺️ Validador do Mapa
        </h4>
        
        <button onclick="validadorMapa.validarMapaCompleto()" style="
            background: #2196f3;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
        ">🔍 Validar Mapa</button>
        
        <button onclick="validadorMapa.destacarProblemas()" style="
            background: #ff9800;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
        ">🎨 Destacar Problemas</button>
        
        <button onclick="validadorMapa.removerDestaque()" style="
            background: #666;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
        ">🎨 Remover Destaque</button>
        
        <button onclick="validadorMapa.exportarPosicoes()" style="
            background: #4caf50;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
        ">💾 Exportar</button>
        
        <button onclick="document.getElementById('validador-controls').remove()" style="
            background: #f44336;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8rem;
            margin-top: 5px;
        ">✖ Fechar</button>
    `;
    
    document.body.appendChild(controles);
}

// Auto-inicializar quando a aba do mapa for aberta
document.addEventListener('click', function(event) {
    const target = event.target;
    
    // Verificar se é clique na aba do mapa
    if (target.classList.contains('tab-btn') || target.closest('.tab-btn')) {
        const tabBtn = target.classList.contains('tab-btn') ? target : target.closest('.tab-btn');
        const onclick = tabBtn.getAttribute('onclick');
        
        if (onclick && onclick.includes('mapa')) {
            setTimeout(() => {
                // Verificar se o mapa está visível
                const mapaDiv = document.getElementById('mapa');
                if (mapaDiv && mapaDiv.style.display !== 'none') {
                    // Adicionar controles do validador
                    setTimeout(adicionarControlesValidador, 500);
                }
            }, 300);
        }
    }
});

console.log('🗺️ Validador do Mapa do Brasil carregado com sucesso!');
console.log('💡 Use: validadorMapa.validarMapaCompleto() para validar todas as posições'); 