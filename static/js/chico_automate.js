// Funções para manipulação dos formulários e botões
// Padronização completa de todos os fluxos: dedicado, aéreo, fracionado, exportação
// Versão corrigida com melhorias de funcionalidade e depuração

document.addEventListener('DOMContentLoaded', function() {
    console.log('=== SISTEMA DE COTAÇÃO INICIADO ===');
    
    // Debug: Verificar se as funções globais estão disponíveis
    setTimeout(() => {
        console.log('🔍 Verificando funções globais:');
        console.log('- window.adicionarSku:', typeof window.adicionarSku);
        console.log('- window.adicionarSkuAll:', typeof window.adicionarSkuAll);
        console.log('- window.adicionarSkuDedicado:', typeof window.adicionarSkuDedicado);
        console.log('- window.skusDataAll:', window.skusDataAll);
        console.log('- window.skusDataFracionado:', window.skusDataFracionado);
        console.log('- window.skusDataDedicado:', window.skusDataDedicado);
    }, 1000);

    // Carregar estados iniciais para todos os formulários (agora usando input + datalist)
    carregarEstados('uf_origem_all');
    carregarEstados('uf_destino_all');
    carregarEstados('uf_origem_frac');
    carregarEstados('uf_destino_frac');
    carregarEstados('uf_origem');
    carregarEstados('uf_destino');
    carregarEstados('uf_origem_aereo');
    carregarEstados('uf_destino_aereo');
    
    // Aguardar um pouco para garantir que tudo esteja carregado antes de configurar eventos
    setTimeout(() => {
        configurarEventoMudancaEstado('uf_origem_all');
        configurarEventoMudancaEstado('uf_destino_all');
        configurarEventoMudancaEstado('uf_origem_frac');
        configurarEventoMudancaEstado('uf_destino_frac');
        configurarEventoMudancaEstado('uf_origem');
        configurarEventoMudancaEstado('uf_destino');
        configurarEventoMudancaEstado('uf_origem_aereo');
        configurarEventoMudancaEstado('uf_destino_aereo');
        console.log('[DEBUG] ✅ Eventos de mudança de estado configurados');
        
        // TESTE DIRETO: Carregar municípios de SP para debug
        console.log('[DEBUG] 🧪 Teste direto: carregando municípios de SP...');
        carregarMunicipios('SP', 'municipio_origem_all');
        
        // Criar painel de status do sistema (canto inferior direito, clicável)
        criarPainelStatusFlutuante();
    }, 1500);

    // Configurar eventos de mudança de estado para carregar municípios
    function configurarEventoMudancaEstado(inputId) {
        const input = document.getElementById(inputId);
        if (!input) return;
        
        // Evento nativo para input
        input.addEventListener('change', function() {
            processarMudancaEstado(this.value, this.id);
        });
        
        // Evento de input para busca em tempo real
        input.addEventListener('input', function() {
            // Delay para evitar muitas requisições
            clearTimeout(input.searchTimeout);
            input.searchTimeout = setTimeout(() => {
                if (this.value.length >= 2) {
                    processarMudancaEstado(this.value, this.id);
                }
            }, 500);
        });
    }
    
    function processarMudancaEstado(uf, inputId) {
        console.log(`[DEBUG] Estado selecionado: ${uf} no input: ${inputId}`);
        
        // Mapeamento correto dos IDs (verificado no HTML)
        const mapeamentoIds = {
            'uf_origem_all': 'municipio_origem_all',
            'uf_destino_all': 'municipio_destino_all',
            'uf_origem_frac': 'municipio_origem_frac',
            'uf_destino_frac': 'municipio_destino_frac',
            'uf_origem': 'municipio_origem',
            'uf_destino': 'municipio_destino',
            'uf_origem_aereo': 'municipio_origem_aereo',
            'uf_destino_aereo': 'municipio_destino_aereo'
        };
        
        const municipioId = mapeamentoIds[inputId];
        
        if (!municipioId) {
            console.warn(`[WARNING] Mapeamento não encontrado para ID: ${inputId}`);
            return; 
        }

        console.log(`[DEBUG] Município ID mapeado: ${municipioId}`);
        
        if (municipioId && uf) {
            // Limpar o input de município antes de carregar novos dados
            const municipioInput = document.getElementById(municipioId);
            if (municipioInput) {
                console.log(`[DEBUG] Limpando input de município: ${municipioId}`);
                municipioInput.value = '';
                municipioInput.placeholder = 'Carregando municípios...';
            }
            
            carregarMunicipios(uf, municipioId);
        }
    }

    // Configurar formulários
    setupFormularios();
    
    // Carregar histórico inicial
    carregarHistorico();

    async function carregarEstados(inputId) {
        const input = document.getElementById(inputId);
        const datalistId = `datalist_${inputId}`;
        let datalist = document.getElementById(datalistId);
        
        if (!input) { 
            console.warn(`[WARNING] Input não encontrado: ${inputId}`);
            return;
        }

        // Se não existe datalist, criar um
        if (!datalist) {
            datalist = document.createElement('datalist');
            datalist.id = datalistId;
            input.parentNode.insertBefore(datalist, input.nextSibling);
        }

        console.log(`[DEBUG] Carregando estados para: ${inputId}`);
        
        // Aplicar estilo de carregamento
        input.classList.add('carregando-municipios');
        input.placeholder = 'Carregando estados...';
        
        try {
            const response = await fetch('/estados');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const estados = await response.json();
            console.log(`[DEBUG] Estados carregados: ${estados.length} itens`);
            
            // Limpar e popular o datalist
            datalist.innerHTML = '';
            estados.forEach(estado => {
                const option = document.createElement('option');
                option.value = estado.id;
                datalist.appendChild(option);
            });
            
            // Aplicar estilo de sucesso
            input.classList.remove('carregando-municipios');
            input.classList.add('municipios-carregados');
            input.placeholder = `Digite para buscar entre ${estados.length} estados...`;
            
            setTimeout(() => {
                input.classList.remove('municipios-carregados');
    }, 2000);
    
            console.log(`[DEBUG] Estados carregados com sucesso para: ${inputId}`);
        } catch (error) {
            console.error(`[ERROR] Erro ao carregar estados para ${inputId}:`, error);
            
            // Aplicar estilo de erro
            input.classList.remove('carregando-municipios');
            input.classList.add('erro-municipios');
            input.placeholder = 'Erro ao carregar - Digite manualmente';
            
            setTimeout(() => {
                input.classList.remove('erro-municipios');
            }, 3000);
            
            showError(`Erro ao carregar estados: ${error.message}`, inputId);
        }
    }

    async function carregarMunicipios(uf, inputId) {
        // Buscar o input e o datalist correspondente
        const input = document.getElementById(inputId);
        const datalistId = `datalist_${inputId}`;
        let datalist = document.getElementById(datalistId);
        
        if (!input) {
            console.warn(`[WARNING] Input de município não encontrado: ${inputId}`);
            return;
        }
        
        // Se não existe datalist, criar um
        if (!datalist) {
            datalist = document.createElement('datalist');
            datalist.id = datalistId;
            input.parentNode.insertBefore(datalist, input.nextSibling);
        }
        
        console.log(`[DEBUG] Carregando municípios para UF: ${uf}, Input: ${inputId}`);
        
        // Aplicar estilo de carregamento
        input.classList.remove('municipios-carregados', 'erro-municipios');
        input.classList.add('carregando-municipios');
        input.placeholder = 'Carregando municípios...';
        
        try {
            const url = `/municipios/${encodeURIComponent(uf)}`;
            console.log(`[DEBUG] URL da requisição: ${url}`);
            
            const response = await fetch(url);
            console.log(`[DEBUG] Status da resposta: ${response.status}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log(`[DEBUG] Resposta recebida (${data.length} itens):`, data.slice(0, 3));
            
            // Verificar se há erro na resposta
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Verificar se é um array
            if (!Array.isArray(data)) {
                throw new Error(`Resposta não é um array válido: ${typeof data}`);
            }
            
            console.log(`[DEBUG] Municípios encontrados: ${data.length} itens`);
            
            // Limpar e popular o datalist
            datalist.innerHTML = '';
            
            data.forEach((municipio, index) => {
                const option = document.createElement('option');
                option.value = municipio.text || municipio.id;
                datalist.appendChild(option);
                
                // Log dos primeiros 3 para debug
                if (index < 3) {
                    console.log(`[DEBUG] Município ${index + 1}: ${option.value}`);
                }
            });
            
            // Aplicar estilo de sucesso
            input.classList.remove('carregando-municipios', 'erro-municipios');
            input.classList.add('municipios-carregados');
            
            // Limpar o campo de input e atualizar placeholder
            input.value = '';
            input.placeholder = `Digite para buscar entre ${data.length} municípios...`;
            
            console.log(`[DEBUG] ✅ Municípios carregados com sucesso para: ${inputId} (${data.length} opções)`);
            
            // Mostrar mensagem de sucesso temporária
            const parentElement = input.parentElement;
            if (parentElement) {
                // Remover mensagem anterior se existir
                const existingMsg = parentElement.querySelector('.municipio-status-msg');
                if (existingMsg) existingMsg.remove();
                
                const successMsg = document.createElement('small');
                successMsg.className = 'municipio-status-msg';
                successMsg.style.color = '#28a745';
                successMsg.style.fontSize = '0.8rem';
                successMsg.textContent = `✅ ${data.length} municípios carregados`;
                successMsg.style.display = 'block';
                successMsg.style.marginTop = '4px';
                parentElement.appendChild(successMsg);
                
                setTimeout(() => {
                    if (successMsg.parentElement) {
                        successMsg.remove();
                    }
                    // Remover classe visual após um tempo
                    input.classList.remove('municipios-carregados');
                }, 3000);
            }
            
        } catch (error) {
            console.error(`[ERROR] Erro ao carregar municípios para ${uf}:`, error);
            
            // Aplicar estilo de erro
            input.classList.remove('carregando-municipios', 'municipios-carregados');
            input.classList.add('erro-municipios');
            
            showError(`Erro ao carregar municípios de ${uf}: ${error.message}`, inputId);
            
            // Em caso de erro, manter placeholder informativo
            input.placeholder = 'Erro ao carregar - Digite manualmente';
            
            // Mostrar mensagem de erro temporária
            const parentElement = input.parentElement;
            if (parentElement) {
                // Remover mensagem anterior se existir
                const existingMsg = parentElement.querySelector('.municipio-status-msg');
                if (existingMsg) existingMsg.remove();
                
                const errorMsg = document.createElement('small');
                errorMsg.className = 'municipio-status-msg';
                errorMsg.style.color = '#dc3545';
                errorMsg.style.fontSize = '0.8rem';
                errorMsg.textContent = `❌ Erro ao carregar municípios`;
                errorMsg.style.display = 'block';
                errorMsg.style.marginTop = '4px';
                parentElement.appendChild(errorMsg);
                
    setTimeout(() => {
                    if (errorMsg.parentElement) {
                        errorMsg.remove();
                    }
                    // Remover classe visual após um tempo
                    input.classList.remove('erro-municipios');
                }, 5000);
            }
        }
    }

    function setupFormularios() {
        // Configurar formulário All In
        const formAllIn = document.getElementById('form-all-in');
        if (formAllIn) {
            formAllIn.addEventListener('submit', async function(e) {
                e.preventDefault();
                await calcularAllIn();
            });
        }

        // Configurar formulário Frete Fracionado
        const formFracionado = document.getElementById('form-fracionado');
        if (formFracionado) {
            formFracionado.addEventListener('submit', async function(e) {
                e.preventDefault();
                await calcularFreteFragcionado();
            });
        }

        // Configurar formulário Dedicado
        const formDedicado = document.getElementById('form-dedicado');
        if (formDedicado) {
            formDedicado.addEventListener('submit', async function(e) {
                e.preventDefault();
                await calcularFreteDedicado();
            });
        }

        // Configurar formulário Aéreo
        const formAereo = document.getElementById('form-aereo');
        if (formAereo) {
            formAereo.addEventListener('submit', async function(e) {
                e.preventDefault();
                await calcularFreteAereo();
            });
        }
    }

    async function calcularAllIn() {
        const loading = document.getElementById('loading-all');
        if (loading) loading.style.display = 'block';

        try {
            const formData = {
                uf_origem: document.getElementById('uf_origem_all').value,
                municipio_origem: document.getElementById('municipio_origem_all').value,
                uf_destino: document.getElementById('uf_destino_all').value,
                municipio_destino: document.getElementById('municipio_destino_all').value,
                peso: parseFloat(document.getElementById('peso_all').value),
                cubagem: parseFloat(document.getElementById('cubagem_all').value),
                valor_nf: parseFloat(document.getElementById('valor_nf_all').value) || null
            };

            console.log('[ALL IN] Dados do formulário:', formData);

            if (!formData.uf_origem || !formData.municipio_origem || !formData.uf_destino || !formData.municipio_destino) {
                throw new Error('Todos os campos de origem e destino são obrigatórios');
            }

            // Calcular Frete Fracionado
            console.log('[ALL IN] Iniciando cálculo de frete fracionado...');
            try {
                const fracionadoResponse = await fetch('/calcular_frete_fracionado', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });

                if (fracionadoResponse.ok) {
                    const fracionadoData = await fracionadoResponse.json();
                    console.log('[ALL IN] Dados frete fracionado recebidos:', fracionadoData);
                    exibirResultadoAllInFracionado(fracionadoData);
        } else {
                    console.error('[ALL IN] Erro na resposta do frete fracionado:', fracionadoResponse.status);
                    const errorText = await fracionadoResponse.text();
                    console.error('[ALL IN] Detalhes do erro:', errorText);
                    exibirResultadoAllInFracionado({ mensagem: 'Erro ao calcular frete fracionado' });
                }
            } catch (error) {
                console.error('[ALL IN] Erro na requisição de frete fracionado:', error);
                exibirResultadoAllInFracionado({ mensagem: `Erro: ${error.message}` });
            }

            // Calcular Frete Dedicado
            const dedicadoResponse = await fetch('/calcular', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (dedicadoResponse.ok) {
                const dedicadoData = await dedicadoResponse.json();
                exibirResultadoAllInDedicado(dedicadoData);
            }

            // Calcular Frete Aéreo
            const aereoResponse = await fetch('/calcular_aereo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (aereoResponse.ok) {
                const aereoData = await aereoResponse.json();
                exibirResultadoAllInAereo(aereoData);
            }
                
            } catch (error) {
            console.error('[ALL IN] Erro:', error);
            showError(`Erro no cálculo All In: ${error.message}`);
        } finally {
            if (loading) loading.style.display = 'none';
        }
    }

    async function calcularFreteFragcionado() {
        const loading = document.getElementById('loading-fracionado');
        if (loading) loading.style.display = 'block';

        try {
            const formData = {
                uf_origem: document.getElementById('uf_origem_frac').value,
                municipio_origem: document.getElementById('municipio_origem_frac').value,
                uf_destino: document.getElementById('uf_destino_frac').value,
                municipio_destino: document.getElementById('municipio_destino_frac').value,
                peso: parseFloat(document.getElementById('peso_frac').value),
                cubagem: parseFloat(document.getElementById('cubagem_frac').value),
                valor_nf: parseFloat(document.getElementById('valor_nf_frac').value) || null
            };

            console.log('[FRACIONADO] Dados do formulário:', formData);

            const response = await fetch('/calcular_frete_fracionado', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                throw new Error(`Erro HTTP: ${response.status}`);
            }

            const data = await response.json();
            console.log('[FRACIONADO] Resposta:', data);

            if (data.error) {
                // 🔧 CORREÇÃO: Verificar se é erro de "sem opções"
                if (data.sem_opcoes || data.error.includes('Não há nenhuma opção')) {
                    showNoOptionsMessage(data.error);
                    return;
                }
                throw new Error(data.error);
            }

            exibirResultadoFracionado(data);
                
            } catch (error) {
            console.error('[FRACIONADO] Erro:', error);
            showError(`Erro no cálculo fracionado: ${error.message}`);
        } finally {
            if (loading) loading.style.display = 'none';
        }
    }

    async function calcularFreteDedicado() {
        const loading = document.getElementById('loading-dedicado');
        if (loading) loading.style.display = 'block';

        try {
            console.log('[DEDICADO] Iniciando cálculo de frete dedicado');
            
            const formData = {
                uf_origem: document.getElementById('uf_origem').value,
                municipio_origem: document.getElementById('municipio_origem').value,
                uf_destino: document.getElementById('uf_destino').value,
                municipio_destino: document.getElementById('municipio_destino').value,
                peso: parseFloat(document.getElementById('peso').value) || 0,
                cubagem: parseFloat(document.getElementById('cubagem').value) || 0
            };

            console.log('[DEDICADO] Dados do formulário:', formData);

            // Validar dados obrigatórios
            if (!formData.uf_origem || !formData.municipio_origem || !formData.uf_destino || !formData.municipio_destino) {
                throw new Error('Origem e destino são obrigatórios');
            }

            console.log('[DEDICADO] Enviando requisição para /calcular');
            const response = await fetch('/calcular', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            console.log('[DEDICADO] Status da resposta:', response.status);
            console.log('[DEDICADO] Headers da resposta:', Object.fromEntries(response.headers.entries()));

            if (!response.ok) {
                const errorText = await response.text();
                console.error('[DEDICADO] Erro na resposta:', errorText);
                throw new Error(`Erro HTTP: ${response.status} - ${errorText}`);
            }

            const data = await response.json();
            console.log('[DEDICADO] Resposta recebida:', data);
                
            if (data.error) {
                console.error('[DEDICADO] Erro nos dados:', data.error);
                throw new Error(data.error);
            }

            console.log('[DEDICADO] Chamando exibirResultadoDedicado');
            exibirResultadoDedicado(data);

        } catch (error) {
            console.error('[DEDICADO] Erro:', error);
            showError(`Erro no cálculo dedicado: ${error.message}`, 'resultados-dedicado-all-in');
        } finally {
            if (loading) loading.style.display = 'none';
        }
    }

    async function calcularFreteAereo() {
        const loading = document.getElementById('loading-aereo');
        if (loading) loading.style.display = 'block';

        try {
            const formData = {
                uf_origem: document.getElementById('uf_origem_aereo').value,
                municipio_origem: document.getElementById('municipio_origem_aereo').value,
                uf_destino: document.getElementById('uf_destino_aereo').value,
                municipio_destino: document.getElementById('municipio_destino_aereo').value,
                peso: parseFloat(document.getElementById('peso_aereo').value),
                cubagem: parseFloat(document.getElementById('cubagem_aereo').value)
            };

            console.log('[AEREO] Dados do formulário:', formData);

            const response = await fetch('/calcular_aereo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

                if (!response.ok) {
                    throw new Error(`Erro HTTP: ${response.status}`);
                }

            const data = await response.json();
            console.log('[AEREO] Resposta:', data);
                
                if (data.error) {
                throw new Error(data.error);
            }

            exibirResultadoAereo(data);

        } catch (error) {
            console.error('[AEREO] Erro:', error);
            showError(`Erro no cálculo aéreo: ${error.message}`);
        } finally {
            if (loading) loading.style.display = 'none';
        }
    }

    async function carregarHistorico() {
        try {
            const response = await fetch('/historico');
            if (!response.ok) {
                throw new Error(`Erro HTTP: ${response.status}`);
            }

            const historico = await response.json();
            console.log('[HISTORICO] Dados carregados:', historico);

            exibirHistorico(historico);

        } catch (error) {
            console.error('[HISTORICO] Erro ao carregar:', error);
            const container = document.getElementById('listaHistorico');
            if (container) {
                container.innerHTML = `<div class="alert alert-danger">Erro ao carregar histórico: ${error.message}</div>`;
            }
        }
    }

    // Funções de exibição de resultados
        function exibirResultadoAllInFracionado(data) {
        const container = document.getElementById('resumo-fracionado-completo');
        if (!container) {
            console.error('[ALL IN FRAC] Container resumo-fracionado-completo não encontrado');
            return;
        }
        
        console.log('[ALL IN FRAC] Dados recebidos:', data);
        
        // 🔧 CORREÇÃO: Verificar se é erro de "sem opções"
        if (data.sem_opcoes || (data.error && data.error.includes('Não há nenhuma opção'))) {
            showNoOptionsMessage(data.error || 'Não há nenhuma opção para a rota solicitada');
            container.innerHTML = '<div class="no-results">Nenhuma opção encontrada para esta rota.</div>';
            return;
        }
        
        let html = '<div class="fracionado-all-in-layout">';
        
        // Verificar se há dados válidos
        if (data && typeof data === 'object') {
            // 🔧 CORREÇÃO: Acessar a estrutura correta dos dados
            const rankingFracionado = data.ranking_fracionado || {};
            const cotacoes = rankingFracionado.ranking_opcoes || data.cotacoes_ranking || data.ranking_completo || data.rotas || [];
            const rotasAgentes = data.rotas_agentes || {};
            
            console.log('[ALL IN FRAC] Ranking fracionado:', rankingFracionado);
            console.log('[ALL IN FRAC] Cotações encontradas:', cotacoes.length);
            console.log('[ALL IN FRAC] Estrutura rotas_agentes:', rotasAgentes);
            
            if (cotacoes.length > 0) {
                // Filtrar rotas por tipo
                const rotasComAgentes = cotacoes.filter(r => {
                    // Verificar se é rota com transferência + entrega
                    return r.tipo_rota === 'transferencia_entrega' || 
                           r.tipo_rota === 'coleta_transferencia_entrega' ||
                           (r.transferencia && r.agente_entrega) ||
                           (r.resumo && r.resumo.includes('+'));
                }).slice(0, 3);
                
                const rotasDiretas = cotacoes.filter(r => {
                    // Verificar se é rota direta
                    return r.tipo_rota === 'direta' || 
                           r.tipo_rota === 'agente_direto' ||
                           r.agente_direto ||
                           (r.resumo && !r.resumo.includes('+'));
                });
                
                console.log('[ALL IN FRAC] Rotas com agentes:', rotasComAgentes.length);
                console.log('[ALL IN FRAC] Rotas diretas:', rotasDiretas.length);
                
                // Container esquerdo - Agente + Transferência + Agente
                html += '<div class="fracionado-coluna-esquerda">';
                if (rotasComAgentes.length > 0) {
                    html += '<h5>🚛 Agente + Transferência + Agente</h5>';
                    html += '<div class="opcoes-fracionado">';
                    
                    rotasComAgentes.forEach((rota, index) => {
                        const destaque = index === 0 ? 'destaque' : '';
                        const transferencia = rota.transferencia || {};
                        const agenteEntrega = rota.agente_entrega || {};
                        const agenteColeta = rota.agente_coleta || {};
                        
                        // 🔧 CORREÇÃO: Acessar dados do custo total da opção
                        const custoTotal = rota.custo_total || rota.total || 0;
                        const prazoTotal = rota.prazo_estimado || rota.prazo_total || 'N/A';
                        
                        // Extrair informações do resumo se necessário
                        let fornecedorTransf = transferencia.fornecedor || '';
                        let fornecedorEntrega = agenteEntrega.fornecedor || '';
                        let custoTransf = transferencia.total || transferencia.custo || 0;
                        let custoEntrega = agenteEntrega.total || agenteEntrega.custo || 0;
                        let custoColeta = agenteColeta.total || agenteColeta.custo || 0;
                        
                        // Se não tiver estrutura detalhada, tentar extrair do resumo
                        if (!fornecedorTransf && rota.resumo) {
                            const partes = rota.resumo.split(' + ');
                            if (partes.length >= 2) {
                                fornecedorTransf = partes[0];
                                fornecedorEntrega = partes[1];
                            }
                        }
                        
                        html += `
                            <div class="opcao-fracionado ${destaque}">
                                <div class="opcao-header">
                                    ${index === 0 ? '⭐ Melhor Opção' : `Opção ${index + 1}`}
                            </div>
                                <div class="opcao-rota">
                                                                    <div class="rota-etapa">
                                    <span class="etapa-icon">📦</span>
                                    <span class="etapa">Coleta:</span> ${agenteColeta.fornecedor || 'Cliente leva até base'}
                                        <span class="etapa-valor">R$ ${custoColeta.toFixed(2)}</span>
                            </div>
                                <div class="rota-etapa">
                                    <span class="etapa-icon">🚛</span>
                                    <span class="etapa">Transfer:</span> ${fornecedorTransf || 'N/A'}
                                    <span class="etapa-valor">R$ ${custoTransf.toFixed(2)}</span>
                        </div>
                                <div class="rota-etapa">
                                    <span class="etapa-icon">🏠</span>
                                    <span class="etapa">Entrega:</span> ${fornecedorEntrega || 'N/A'}
                                    <span class="etapa-valor">R$ ${custoEntrega.toFixed(2)}</span>
                                </div>
                                </div>
                                <div class="opcao-footer">
                                    <div class="opcao-total">
                                        <strong>Total: R$ ${custoTotal.toFixed(2)}</strong>
                                    </div>
                                    <div class="opcao-prazo">
                                        ⏱️ ${prazoTotal} dias úteis
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    
                    html += '</div>';
                } else {
                    html += '<p class="text-muted">Nenhuma rota com agentes encontrada.</p>';
                }
                html += '</div>'; // Fecha coluna esquerda
                
                // Container direito - Agente Direto
                html += '<div class="fracionado-coluna-direita">';
                if (rotasDiretas.length > 0) {
                    html += '<h5>🚀 Agente Direto</h5>';
                    html += '<div class="agentes-diretos">';
                    
                    rotasDiretas.slice(0, 2).forEach((rota, index) => {
                        const agente = rota.agente_direto || {};
                        const alerta = agente.validacao_peso && !agente.validacao_peso.valido;
                        
                        // Extrair nome do fornecedor
                        let fornecedor = agente.fornecedor || rota.fornecedor_direto || rota.resumo || 'N/A';
                        const custoTotal = rota.custo_total || rota.total || 0;
                        const prazoTotal = rota.prazo_estimado || rota.prazo_total || agente.prazo || 'N/A';
                        
                        html += `
                            <div class="agente-direto-card ${alerta ? 'com-alerta' : ''}">
                                <div class="direto-header">
                                    <strong>${fornecedor}</strong>
                                    ${alerta ? '<span class="badge badge-warning">⚠️ Peso excedido</span>' : ''}
                                </div>
                                <div class="direto-info">
                                    <div class="info-linha">
                                        <span>Origem:</span> ${agente.origem || rota.base_origem || 'N/A'}
                                    </div>
                                    <div class="info-linha">
                                        <span>Destino:</span> ${agente.destino || rota.base_destino || 'N/A'}
                                    </div>
                                    <div class="info-linha">
                                        <span>Prazo:</span> ${prazoTotal} dias
                                    </div>
                                </div>
                                <div class="direto-valor">
                                    <strong>R$ ${custoTotal.toFixed(2)}</strong>
                                </div>
                                ${alerta ? '<div class="alerta-peso">Necessário validar com o agente</div>' : ''}
                            </div>
                        `;
                    });
                    
                    html += '</div>';
                } else {
                    html += '<p class="text-muted">Nenhuma rota direta disponível.</p>';
                }
                html += '</div>'; // Fecha coluna direita
                
                html += '</div>'; // Fecha layout fracionado
                
                // Se não houver rotas com agentes mas houver outras
                if (rotasComAgentes.length === 0 && cotacoes.length > 0) {
                    html += '<div class="opcoes-fracionado">';
                    
                    cotacoes.slice(0, 3).forEach((rota, index) => {
                        const destaque = index === 0 ? 'destaque' : '';
                        const custoTotal = rota.custo_total || rota.total || 0;
                        const prazoTotal = rota.prazo_estimado || rota.prazo_total || 'N/A';
                        
                        html += `
                            <div class="opcao-fracionado ${destaque}">
                                <div class="opcao-header">
                                    ${index === 0 ? '⭐ Melhor Opção' : `Opção ${index + 1}`}
                                </div>
                                <div class="opcao-info">
                                    <div class="info-linha">
                                        <span>Rota:</span> ${rota.resumo || rota.tipo_servico || 'N/A'}
                                    </div>
                                    <div class="info-linha">
                                        <span>Origem:</span> ${rota.base_origem || data.origem || rankingFracionado.origem || 'N/A'}
                                    </div>
                                    <div class="info-linha">
                                        <span>Destino:</span> ${rota.base_destino || data.destino || rankingFracionado.destino || 'N/A'}
                                    </div>
                                    <div class="info-linha">
                                        <span>Prazo:</span> ${prazoTotal} dias
                                    </div>
                                </div>
                                <div class="opcao-footer">
                                    <div class="opcao-total">
                                        <strong>Total: R$ ${custoTotal.toFixed(2)}</strong>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    
                    html += '</div>';
                }
                
            } else if (data.error) {
                html += `<div class="alert alert-warning">⚠️ ${data.error}</div>`;
            } else {
                html += '<div class="alert alert-info">📋 Nenhuma opção de frete fracionado encontrada para este trajeto.</div>';
            }
        } else {
            html += '<p class="text-muted">❌ Erro ao processar dados do frete fracionado.</p>';
        }
        
        container.innerHTML = html;
        
        // Adicionar estilos CSS se ainda não existirem
        if (!document.getElementById('fracionado-all-in-styles')) {
            const style = document.createElement('style');
            style.id = 'fracionado-all-in-styles';
            style.innerHTML = `
                .fracionado-all-in-layout {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 30px;
                    margin-top: 20px;
                }
                
                .fracionado-coluna-esquerda,
                .fracionado-coluna-direita {
                    background: #f8f9fa;
                    border-radius: 12px;
                    padding: 20px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                }
                
                .fracionado-coluna-esquerda h5,
                .fracionado-coluna-direita h5 {
                    color: #495057;
                    margin-bottom: 15px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #dee2e6;
                    font-size: 1.2rem;
                }
                
                @media (max-width: 768px) {
                    .fracionado-all-in-layout {
                        grid-template-columns: 1fr;
                    }
                }
                
                .opcoes-fracionado {
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                    margin-top: 15px;
                }
                
                .opcao-fracionado {
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    padding: 15px;
                    background: #fff;
                    transition: all 0.3s ease;
                }
                
                .opcao-fracionado.destaque {
                    border-color: #28a745;
                    background: #e8f5e9;
                }
                
                .opcao-fracionado:hover {
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    transform: translateY(-2px);
                }
                
                .opcao-header {
                    font-weight: bold;
                    color: #28a745;
                    margin-bottom: 10px;
                    font-size: 1.1em;
                }
                
                .rota-etapa {
                    display: flex;
                    align-items: center;
                    margin: 8px 0;
                    padding: 5px 0;
                    border-bottom: 1px dashed #dee2e6;
                }
                
                .rota-etapa:last-child {
                    border-bottom: none;
                }
                
                .etapa-icon {
                    font-size: 1.2em;
                    margin-right: 8px;
                }
                
                .etapa {
                    font-weight: 600;
                    color: #495057;
                    margin-right: 8px;
                    min-width: 80px;
                }
                
                .etapa-valor {
                    margin-left: auto;
                    color: #28a745;
                    font-weight: bold;
                }
                
                .opcao-footer {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-top: 15px;
                    padding-top: 15px;
                    border-top: 2px solid #dee2e6;
                }
                
                .opcao-total {
                    font-size: 1.2em;
                    color: #28a745;
                }
                
                .opcao-prazo {
                    color: #6c757d;
                    font-size: 0.9em;
                }
                
                .agentes-diretos {
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                    margin-top: 15px;
                }
                
                .agente-direto-card {
                    border: 1px solid #17a2b8;
                    border-radius: 8px;
                    padding: 15px;
                    background: #e7f3ff;
                    transition: all 0.3s ease;
                }
                
                .agente-direto-card.com-alerta {
                    border-color: #ffc107;
                    background: #fff3cd;
                }
                
                .agente-direto-card:hover {
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    transform: translateY(-2px);
                }
                
                .direto-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 10px;
                    font-size: 1.1em;
                    color: #17a2b8;
                }
                
                .direto-info {
                    margin: 10px 0;
                }
                
                .info-linha {
                    display: flex;
                    justify-content: space-between;
                    margin: 5px 0;
                    font-size: 0.9em;
                }
                
                .info-linha span:first-child {
                    font-weight: 600;
                    color: #6c757d;
                }
                
                .direto-valor {
                    text-align: center;
                    font-size: 1.3em;
                    color: #17a2b8;
                    margin-top: 10px;
                    padding-top: 10px;
                    border-top: 2px solid #dee2e6;
                }
                
                .alerta-peso {
                    text-align: center;
                    color: #856404;
                    font-size: 0.85em;
                    margin-top: 8px;
                    font-style: italic;
                }
                
                .badge-warning {
                    background: #ffc107;
                    color: #000;
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: 0.75em;
                }
                
                .opcao-info {
                    margin: 10px 0;
                }
                
                .alert {
                    padding: 15px;
                    margin-bottom: 20px;
                    border: 1px solid transparent;
                    border-radius: 4px;
                }
                
                .alert-warning {
                    color: #856404;
                    background-color: #fff3cd;
                    border-color: #ffeaa7;
                }
                
                .alert-info {
                    color: #0c5460;
                    background-color: #d1ecf1;
                    border-color: #bee5eb;
                }
                
                .text-muted {
                    color: #6c757d !important;
                }
            `;
            document.head.appendChild(style);
        }
    }

    // Variável global para armazenar dados do frete dedicado
    let dadosFreteDedicadoAll = null;
    let veiculoSelecionado = null;

    function exibirResultadoAllInDedicado(data) {
        console.log('[EXIBIR ALL IN DEDICADO] Iniciando função');
        console.log('[EXIBIR ALL IN DEDICADO] Procurando containers...');
        
        const containerVeiculos = document.getElementById('resumo-dedicado-veiculos');
        const containerCustos = document.getElementById('resumo-dedicado-custos');
        const containerMargens = document.getElementById('resumo-dedicado-margens');
        
        console.log('[EXIBIR ALL IN DEDICADO] Container veículos:', containerVeiculos);
        console.log('[EXIBIR ALL IN DEDICADO] Container custos:', containerCustos);
        console.log('[EXIBIR ALL IN DEDICADO] Container margens:', containerMargens);
        console.log('[DEBUG] Dados recebidos para frete dedicado All In:', data);
        
        // Armazenar dados globalmente
        dadosFreteDedicadoAll = data;
        
        // Veículos Disponíveis
        console.log('[EXIBIR ALL IN DEDICADO] Verificando container veículos...');
        if (containerVeiculos) {
            let htmlVeiculos = '<h4>🚛 Veículos Disponíveis</h4>';
            htmlVeiculos += '<p style="font-size: 0.9rem; color: #6c757d; margin-bottom: 15px;">Clique em um veículo para ver detalhes específicos</p>';
            
            console.log('[EXIBIR ALL IN DEDICADO] Verificando data.custos:', data.custos);
            console.log('[EXIBIR ALL IN DEDICADO] Tipo de data.custos:', typeof data.custos);
            console.log('[EXIBIR ALL IN DEDICADO] data.custos é objeto?', typeof data.custos === 'object');
            
            if (data && data.custos) {
                console.log('[EXIBIR ALL IN DEDICADO] Custos encontrados, criando grid');
                console.log('[EXIBIR ALL IN DEDICADO] Chaves dos custos:', Object.keys(data.custos));
                htmlVeiculos += '<div class="veiculos-grid">';
                
                Object.entries(data.custos).forEach(([veiculo, valor]) => {
                    console.log('[EXIBIR ALL IN DEDICADO] Processando veículo:', veiculo, 'valor:', valor);
                    const icone = veiculo.includes('VUC') ? '🚐' : 
                                 veiculo.includes('3/4') ? '🚚' : 
                                 veiculo.includes('TOCO') ? '🚛' : 
                                 veiculo.includes('TRUCK') ? '🚛' : 
                                 veiculo.includes('CARRETA') ? '🚛' : '🚚';
                    
                    // Obter capacidade do veículo
                    const capacidade = obterCapacidadeVeiculo(veiculo);
                    
                    // Verificar se o veículo comporta a carga (se tivermos os dados)
                    const pesoSolicitado = parseFloat(document.getElementById('peso_all')?.value) || 0;
                    const volumeSolicitado = parseFloat(document.getElementById('cubagem_all')?.value) || 0;
                    
                    const pesoOk = pesoSolicitado <= capacidade.peso_max;
                    const volumeOk = volumeSolicitado <= capacidade.volume_max;
                    const capacidadeOk = pesoOk && volumeOk;
                    
                    htmlVeiculos += `
                        <div class="veiculo-card ${!capacidadeOk && pesoSolicitado > 0 ? 'capacidade-excedida' : ''}" 
                             onclick="selecionarVeiculo('${veiculo}')" style="cursor: pointer;">
                            <div class="veiculo-icone">${icone}</div>
                            <div class="veiculo-nome">${veiculo}</div>
                            <div class="veiculo-valor">R$ ${valor.toFixed(2)}</div>
                            <div class="veiculo-capacidade">
                                <small>
                                    <div class="${!pesoOk && pesoSolicitado > 0 ? 'capacidade-insuficiente' : ''}">
                                        ⚖️ ${capacidade.peso_max.toLocaleString('pt-BR')} kg
                                </div>
                                    <div class="${!volumeOk && volumeSolicitado > 0 ? 'capacidade-insuficiente' : ''}">
                                        📦 ${capacidade.volume_max.toLocaleString('pt-BR')} m³
                              </div>
                                </small>
                            </div>
                            ${!capacidadeOk && pesoSolicitado > 0 ? '<div class="aviso-capacidade">⚠️ Capacidade excedida</div>' : ''}
                        </div>
                    `;
                });
                
                htmlVeiculos += '</div>';
            } else {
                htmlVeiculos += '<p class="text-muted">Nenhum veículo disponível encontrado.</p>';
            }
            
            console.log('[EXIBIR ALL IN DEDICADO] HTML gerado:', htmlVeiculos);
            containerVeiculos.innerHTML = htmlVeiculos;
        }
        
        // Custos Operacionais - Exibir mensagem inicial
        console.log('[EXIBIR ALL IN DEDICADO] Verificando container custos...');
        if (containerCustos) {
            containerCustos.innerHTML = `
                <h4>📊 Custos Operacionais</h4>
                <p class="text-muted" style="text-align: center; padding: 20px;">
                    <i class="fa-solid fa-hand-pointer"></i> Selecione um veículo para ver os custos operacionais
                </p>
            `;
        }
        
        // Margens Comerciais - Exibir mensagem inicial
        console.log('[EXIBIR ALL IN DEDICADO] Verificando container margens...');
        if (containerMargens) {
            containerMargens.innerHTML = `
                <h4>📈 Margens Comerciais</h4>
                <p class="text-muted" style="text-align: center; padding: 20px;">
                    <i class="fa-solid fa-hand-pointer"></i> Selecione um veículo para ver as margens sugeridas
                </p>
            `;
        }
    }

    // Função para selecionar veículo e atualizar custos e margens
    window.selecionarVeiculo = function(veiculo) {
        if (!dadosFreteDedicadoAll) return;
        
        veiculoSelecionado = veiculo;
        
        // Destacar veículo selecionado
        document.querySelectorAll('.veiculo-card').forEach(card => {
            card.classList.remove('veiculo-selecionado');
            if (card.querySelector('.veiculo-nome').textContent === veiculo) {
                card.classList.add('veiculo-selecionado');
            }
        });
        
        // Atualizar Custos Operacionais
        const containerCustos = document.getElementById('resumo-dedicado-custos');
        if (containerCustos) {
            let htmlCustos = `<h4>📊 Custos Operacionais - ${veiculo}</h4>`;
            
            if (dadosFreteDedicadoAll.analise) {
                htmlCustos += '<div class="analise-dedicado">';
                
                // Informações gerais da rota
                if (dadosFreteDedicadoAll.analise.distancia) {
                    htmlCustos += `<div class="analise-item">📏 Distância: ${dadosFreteDedicadoAll.analise.distancia} km</div>`;
                }
                
                if (dadosFreteDedicadoAll.analise.tempo_estimado) {
                    htmlCustos += `<div class="analise-item">⏱️ Tempo estimado: ${dadosFreteDedicadoAll.analise.tempo_estimado}</div>`;
                }
                
                // Consumo específico do veículo
                const consumoVeiculo = calcularConsumoVeiculo(veiculo, dadosFreteDedicadoAll.analise.distancia);
                htmlCustos += `<div class="analise-item">⛽ Consumo estimado: ${consumoVeiculo.litros} litros</div>`;
                htmlCustos += `<div class="analise-item">💵 Custo combustível: R$ ${consumoVeiculo.custo.toFixed(2)}</div>`;
                
                // Pedágio
                if (dadosFreteDedicadoAll.analise.pedagio_real || dadosFreteDedicadoAll.analise.pedagio_estimado) {
                    const pedagio = dadosFreteDedicadoAll.analise.pedagio_real || dadosFreteDedicadoAll.analise.pedagio_estimado;
                    const pedagioVeiculo = calcularPedagioVeiculo(veiculo, pedagio);
                    htmlCustos += `<div class="analise-item">💰 Pedágio: R$ ${pedagioVeiculo.toFixed(2)}</div>`;
                }
                
                // Custos operacionais específicos do veículo
                htmlCustos += '<div class="custos-operacionais">';
                
                const custosVeiculo = calcularCustosOperacionaisVeiculo(veiculo, dadosFreteDedicadoAll);
                Object.entries(custosVeiculo).forEach(([item, valor]) => {
                    htmlCustos += `
                        <div class="custo-item">
                            <span>${item}:</span>
                            <span>R$ ${valor.toFixed(2)}</span>
                        </div>
                        `;
                    });
                
                htmlCustos += '</div>';
                htmlCustos += '</div>';
            } else {
                htmlCustos += '<p class="text-muted">Análise operacional não disponível.</p>';
            }
            
            containerCustos.innerHTML = htmlCustos;
        }
        
        // Atualizar Margens Comerciais
        const containerMargens = document.getElementById('resumo-dedicado-margens');
        if (containerMargens && dadosFreteDedicadoAll.custos && dadosFreteDedicadoAll.custos[veiculo]) {
            let htmlMargens = `<h4>📈 Margens Comerciais - ${veiculo}</h4>`;
            htmlMargens += '<div class="margens-comerciais">';
            
            const custoVeiculo = dadosFreteDedicadoAll.custos[veiculo];
            const margens = [20, 30, 40, 50];
            
            margens.forEach(margem => {
                const valorComMargem = custoVeiculo * (1 + margem / 100);
                const lucro = valorComMargem - custoVeiculo;
                htmlMargens += `
                    <div class="margem-item ${margem === 30 ? 'margem-destaque' : ''}">
                        <div class="margem-info">
                            <span class="margem-label">Margem ${margem}%:</span>
                            <span class="margem-valor">R$ ${valorComMargem.toFixed(2)}</span>
                        </div>
                        <div class="margem-lucro">
                            <small>Lucro: R$ ${lucro.toFixed(2)}</small>
                        </div>
                        </div>
                    `;
            });
            
            htmlMargens += '</div>';
            
            // Adicionar recomendação
            htmlMargens += `
                <div class="margem-recomendacao">
                    <i class="fa-solid fa-lightbulb"></i> 
                    <strong>Recomendação:</strong> Para o ${veiculo}, sugerimos uma margem de 30% para competitividade no mercado.
                        </div>
                    `;

            containerMargens.innerHTML = htmlMargens;
        }
    };

    // Função para obter capacidade do veículo
    function obterCapacidadeVeiculo(veiculo) {
        // Capacidades dos veículos (baseado no backend Python)
        const capacidades = {
            'FIORINO': { peso_max: 500, volume_max: 1.20, descricao: 'Utilitário pequeno' },
            'VAN': { peso_max: 1500, volume_max: 6.0, descricao: 'Van/Kombi' },
            'VUC': { peso_max: 3000, volume_max: 15.0, descricao: 'Veículo Urbano de Carga' },
            '3/4': { peso_max: 3500, volume_max: 12.0, descricao: 'Caminhão 3/4' },
            'TOCO': { peso_max: 7000, volume_max: 40.0, descricao: 'Caminhão toco' },
            'TRUCK': { peso_max: 12000, volume_max: 70.0, descricao: 'Caminhão truck' },
            'CARRETA': { peso_max: 28000, volume_max: 110.0, descricao: 'Carreta/bitrem' },
            'CARRETA LS': { peso_max: 30000, volume_max: 120.0, descricao: 'Carreta LS' }
        };
        
        // Procurar a capacidade baseada no tipo de veículo
        for (const [tipo, dados] of Object.entries(capacidades)) {
            if (veiculo.includes(tipo)) {
                return dados;
            }
        }
        
        // Retornar valores padrão se não encontrar
        return { peso_max: 10000, volume_max: 50.0, descricao: 'Veículo padrão' };
    }

    // Funções auxiliares para cálculos específicos por veículo
    function calcularConsumoVeiculo(veiculo, distancia) {
        // Consumo médio em km/l por tipo de veículo
        const consumoMedio = {
            'VUC': 8,
            '3/4': 7,
            'TOCO': 5,
            'TRUCK': 4,
            'CARRETA': 3,
            'CARRETA LS': 2.8
        };
        
        // Encontrar o consumo baseado no tipo
        let kmPorLitro = 4; // padrão
        for (const [tipo, consumo] of Object.entries(consumoMedio)) {
            if (veiculo.includes(tipo)) {
                kmPorLitro = consumo;
                break;
            }
        }
        
        const litros = Math.ceil(distancia / kmPorLitro);
        const precoDiesel = 6.20; // preço médio do diesel
        const custo = litros * precoDiesel;
        
        return { litros, custo, kmPorLitro };
    }

    function calcularPedagioVeiculo(veiculo, pedagioBase) {
        // Multiplicador de pedágio por eixos
        let multiplicador = 1;
        
        if (veiculo.includes('VUC')) multiplicador = 1;
        else if (veiculo.includes('3/4')) multiplicador = 1.5;
        else if (veiculo.includes('TOCO')) multiplicador = 2;
        else if (veiculo.includes('TRUCK')) multiplicador = 3;
        else if (veiculo.includes('CARRETA')) multiplicador = 4;
        
        return pedagioBase * multiplicador;
    }

    function calcularCustosOperacionaisVeiculo(veiculo, dados) {
        const distancia = dados.analise?.distancia || 0;
        const consumo = calcularConsumoVeiculo(veiculo, distancia);
        
        // Custos operacionais específicos
        const custos = {
            'Combustível': consumo.custo,
            'Manutenção': distancia * 0.35, // R$ 0,35 por km
            'Pneus': distancia * 0.15, // R$ 0,15 por km
            'Depreciação': distancia * 0.25, // R$ 0,25 por km
            'Seguro': distancia * 0.10, // R$ 0,10 por km
            'Motorista': calcularCustoMotorista(distancia, dados.analise?.tempo_estimado)
        };
        
        // Adicionar custos específicos por tipo de veículo
        if (veiculo.includes('CARRETA')) {
            custos['Licenciamento especial'] = 150;
        }
        
        return custos;
    }

    function calcularCustoMotorista(distancia, tempoEstimado) {
        // Calcular horas baseado no tempo estimado ou distância
        let horas = 8; // padrão
        if (tempoEstimado) {
            // Extrair horas do tempo estimado (formato: "X horas Y minutos")
            const match = tempoEstimado.match(/(\d+)\s*horas?/);
            if (match) {
                horas = parseInt(match[1]);
            }
                } else {
            // Estimar baseado na distância (média 60km/h)
            horas = Math.ceil(distancia / 60);
        }
        
        const valorHora = 25; // R$ 25 por hora
        return horas * valorHora;
    }

    function exibirResultadoAllInAereo(data) {
        const container = document.getElementById('resumo-aereo-opcoes');
        if (!container) return;
        
        console.log('[DEBUG] Dados recebidos para frete aéreo All In:', data);
        
        let html = '<h4>✈️ Frete Aéreo</h4>';
        
        if (data && data.custos && Object.keys(data.custos).length > 0) {
            html += '<div class="opcoes-aereas">';
            
            Object.entries(data.custos).forEach(([opcao, valor]) => {
                html += `
                    <div class="opcao-aerea">
                        <div class="opcao-nome">✈️ ${opcao}</div>
                        <div class="opcao-valor">R$ ${valor.toFixed(2)}</div>
                    </div>
                `;
            });
            
            html += '</div>';
            
            // Adicionar informações adicionais se disponíveis
            if (data.prazo) {
                html += `<div class="info-aereo">⏰ Prazo estimado: ${data.prazo}</div>`;
            }
            
            if (data.observacoes) {
                html += `<div class="info-aereo">📝 ${data.observacoes}</div>`;
            }
        } else if (data && data.mensagem) {
            html += `<p class="text-warning">⚠️ ${data.mensagem}</p>`;
        } else if (data && data.error) {
            html += `<p class="text-danger">❌ ${data.error}</p>`;
    } else {
            html += '<p class="text-muted">Nenhuma opção de frete aéreo encontrada para esta rota.</p>';
        }
        
        container.innerHTML = html;
    }

    function exibirResultadoFracionado(data) {
        const container = document.getElementById('fracionado-resultado');
        if (!container) {
            console.error('[FRACIONADO] Container fracionado-resultado não encontrado');
            return;
        }

        console.log('[FRACIONADO] Dados recebidos:', data);
        
        // 🆕 VERIFICAR SE HÁ RANKING FRACIONADO (NOVO FORMATO)
        if (data.ranking_fracionado) {
            console.log('[FRACIONADO] Usando novo formato de ranking');
            exibirRankingFracionado(data.ranking_fracionado, container);
            return;
        }

        // Fallback para formato antigo (caso necessário)
        console.log('[FRACIONADO] Usando formato legacy');
        exibirFormatoLegacyFracionado(data, container);
    }

    // 🆕 NOVA FUNÇÃO PARA EXIBIR RANKING NO FORMATO DEDICADO
    function exibirRankingFracionado(ranking, container) {
        // Armazenar dados para exportação
        window.ultimaAnalise = ranking;
        window.ultimosDados = {
            origem: ranking.origem,
            destino: ranking.destino,
            peso: ranking.peso,
            cubagem: ranking.cubagem,
            valor_nf: ranking.valor_nf,
            tipo: "Fracionado",
            rotas_agentes: {
                cotacoes_ranking: ranking.ranking_opcoes
            }
        };

        // Check if there are any location warnings in the ranking options
        const hasLocationWarning = ranking.ranking_opcoes && 
                                 ranking.ranking_opcoes.some(opcao => opcao.localizacao_alternativa);
        
        let html = `
            <div class="success">
                <h3><i class="fa-solid fa-boxes"></i> Cotação de Frete Fracionado Calculada - ${ranking.id_calculo}</h3>
                
                ${hasLocationWarning ? `
                <div class="location-warning alert-warning">
                    <i class="fas fa-info-circle"></i>
                    <p>⚠️ Atenção: Alguns agentes estão localizados em cidades próximas. Por favor, consulte o parceiro para confirmar a disponibilidade.</p>
                </div>` : ''}
                
                <div class="analise-container">
                    <div class="analise-title">📦 Melhor Opção: ${ranking.melhor_opcao ? ranking.melhor_opcao.tipo_servico : 'N/A'}</div>
                    <div class="analise-item" style="font-size: 1.3rem; font-weight: bold; color: #28a745; background: #d4edda; padding: 12px; border-radius: 8px; text-align: center;">
                        💰 <strong>CUSTO TOTAL: R$ ${ranking.melhor_opcao ? ranking.melhor_opcao.custo_total.toFixed(2) : '0.00'}</strong>
                    </div>
                    <div class="analise-item"><strong>Peso Cubado:</strong> ${ranking.peso_cubado}kg (${ranking.peso_usado_tipo})</div>
                    ${ranking.valor_nf ? `<div class="analise-item"><strong>Valor NF:</strong> R$ ${ranking.valor_nf.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>` : ''}
                </div>

                <!-- Botões de Exportação -->
                <div class="export-buttons" style="margin: 10px 0; text-align: right;">
                    <button onclick="exportarPDF({analise: window.ultimaAnalise, dados: window.ultimosDados})" class="btn btn-info">
                        <i class="fas fa-file-pdf"></i> Exportar PDF
                    </button>
                    <button onclick="exportarExcel({tipo: 'Fracionado', dados: window.ultimosDados})" class="btn btn-info">
                        <i class="fas fa-file-excel"></i> Exportar Excel
                    </button>
                </div>

                <!-- Informações da Rota -->
                <div class="analise-container">
                    <div class="analise-title">
                        📍 Informações da Rota
                        <button class="btn-secondary" onclick="toggleDetails('detalhes_rota_fracionado')" style="float: right; margin-left: 10px; font-size: 0.8rem; padding: 4px 8px; background: #28a745;">
                            Ver Detalhes
                        </button>
                    </div>
                    <div class="analise-item"><strong>Origem:</strong> ${ranking.origem}</div>
                    <div class="analise-item"><strong>Destino:</strong> ${ranking.destino}</div>
                    <div class="analise-item"><strong>Tipo de Frete:</strong> Fracionado</div>
                    
                    <!-- Detalhes da Rota -->
                    <div id="detalhes_rota_fracionado" style="display: none; margin-top: 15px; padding: 15px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px;">
                        <strong style="color: #28a745;">📦 Detalhamento do Frete Fracionado:</strong><br><br>
                        <div style="margin-bottom: 10px;">
                            <strong>📦 Características do Serviço:</strong><br>
                            • <strong>Modalidade:</strong> Frete fracionado com agentes<br>
                            • <strong>Peso Real:</strong> ${ranking.peso}kg<br>
                            • <strong>Cubagem:</strong> ${ranking.cubagem}m³<br>
                            • <strong>Peso Cubado:</strong> ${ranking.peso_cubado}kg (${ranking.peso_usado_tipo})<br>
                        </div>
                        <div style="margin-bottom: 10px;">
                            <strong>🚚 Tipos de Rota:</strong><br>
                            • <strong>Agente Direto:</strong> Porta-a-porta direto<br>
                            • <strong>Coleta + Transferência:</strong> Agente coleta + transferência<br>
                            • <strong>Transferência + Entrega:</strong> Transferência + agente entrega<br>
                            • <strong>Rota Completa:</strong> Coleta + transferência + entrega
                        </div>
                        <div>
                            <strong>⚙️ Processamento:</strong><br>
                            • Busca em <strong>base unificada de agentes</strong><br>
                            • Cálculo baseado em <strong>peso cubado</strong> (maior entre peso real e cubagem × 300)<br>
                            • Consideração de <strong>GRIS e pedágios</strong> quando aplicável<br>
                            • Ranking por <strong>menor custo total</strong>
                        </div>
                    </div>
                </div>
        `;
        
        // 🎯 TABELA DE RANKING (FORMATO DEDICADO) COM DETALHES EXPANDÍVEIS
        if (ranking.ranking_opcoes && ranking.ranking_opcoes.length > 0) {
                html += `
                <div class="analise-container">
                    <div class="analise-title">📊 Opções de Frete Fracionado Disponíveis</div>
                    <table class="result-table" style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                        <thead style="background: #f8f9fa;">
                            <tr>
                                <th style="padding: 12px; text-align: left; border: 1px solid #dee2e6;">Posição</th>
                                <th style="padding: 12px; text-align: left; border: 1px solid #dee2e6;">Tipo de Serviço</th>
                                <th style="padding: 12px; text-align: right; border: 1px solid #dee2e6;">Custo Total</th>
                                <th style="padding: 12px; text-align: center; border: 1px solid #dee2e6;">Capacidade</th>
                                <th style="padding: 12px; text-align: center; border: 1px solid #dee2e6;">Ações</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            ranking.ranking_opcoes.forEach((opcao, index) => {
                let posicaoIcon, rowStyle;
                if (index === 0) {
                    posicaoIcon = "🥇";
                    rowStyle = "background: #d4edda; border-left: 4px solid #28a745;";
                } else if (index === 1) {
                    posicaoIcon = "🥈";
                    rowStyle = "background: #f8f9fa; border-left: 4px solid #6c757d;";
                } else if (index === 2) {
                    posicaoIcon = "🥉";
                    rowStyle = "background: #fff3cd; border-left: 4px solid #fd7e14;";
                } else {
                    posicaoIcon = `${index + 1}º`;
                    rowStyle = "background: #ffffff;";
                }
                
                // Add location warning if this is an alternative location
                const locationWarning = opcao.localizacao_alternativa ? 
                    `<div class="location-warning alert-info" style="margin: 8px 0; padding: 8px 12px; font-size: 0.85em; display: flex; align-items: center;">
                        <i class="fas fa-map-marker-alt" style="margin-right: 8px;"></i>
                        <span>${opcao.mensagem_aviso || 'Agente localizado em cidade próxima'}</span>
                    </div>` : '';

                html += `
                    <tr style="${rowStyle}">
                        <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; font-size: 1.1em;">${posicaoIcon}</td>
                        <td style="padding: 12px; border: 1px solid #dee2e6;">
                            <strong>${opcao.tipo_servico}</strong><br>
                            <small style="color: #6c757d;">${opcao.descricao}</small><br>
                            <small style="color: #007bff; font-weight: bold;">Fornecedor: ${opcao.fornecedor}</small>
                            ${locationWarning}
                        </td>
                        <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: bold; color: #28a745; font-size: 1.1em;">
                            R$ ${opcao.custo_total.toFixed(2)}
                        </td>
                        <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                            <strong>Peso Máximo Transportado:</strong> ${opcao.peso_maximo_agente || 'N/A'}<br>
                        </td>
                        <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                            <button class="btn btn-info btn-sm" onclick="toggleDetalhesOpcao(${index})" style="background: #17a2b8; border: none; color: white; padding: 6px 12px; border-radius: 4px; font-size: 0.8rem;">
                                <span id="btn-text-${index}">🔎 Ver Detalhes</span>
                            </button>
                        </td>
                    </tr>
                `;
                
                // 🆕 LINHA EXPANSÍVEL COM DETALHES
                html += `
                    <tr id="detalhes-row-${index}" style="display: none;">
                        <td colspan="5" style="padding: 0; border: 1px solid #dee2e6;">
                            <div style="background: #f8f9fa; padding: 20px; margin: 0;">
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                                    
                                    <!-- Informações dos Agentes -->
                                    <div style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6;">
                                        <h5 style="color: #28a745; margin-bottom: 15px; font-size: 1rem;">
                                            🚚 Informações dos Agentes
                                        </h5>
                `;
                
                // Exibir informações dos agentes baseado no tipo de rota
                const detalhes = opcao.detalhes_expandidos || {};
                const agentes = detalhes.agentes_info || {};
                const rota_info = detalhes.rota_info || {};
                
                // Debug: verificar se os dados dos agentes estão chegando
                console.log(`[DEBUG] Dados dos agentes para opção ${index}:`, agentes);
                console.log(`[DEBUG] Dados da rota para opção ${index}:`, rota_info);
                
                if (agentes.agente_coleta && agentes.agente_coleta !== 'N/A') {
                    html += `
                        <div onclick="exibirCustosAgente('coleta', ${index})" style="margin-bottom: 10px; padding: 8px; background: #e8f5e8; border-radius: 4px; cursor: pointer; transition: background 0.3s;" onmouseover="this.style.background='#d4ecda'" onmouseout="this.style.background='#e8f5e8'">
                            <strong>🚛 Agente de Coleta:</strong> ${agentes.agente_coleta}<br>
                            ${agentes.base_origem !== 'N/A' ? `<small>Base Destino: ${agentes.base_origem}</small>` : ''}
                            <br><small style="color: #007bff;">👆 Clique para ver custos específicos</small>
                        </div>
                    `;
                }
                
                if (agentes.transferencia && agentes.transferencia !== 'N/A') {
                    html += `
                        <div onclick="exibirCustosAgente('transferencia', ${index})" style="margin-bottom: 10px; padding: 8px; background: #e3f2fd; border-radius: 4px; cursor: pointer; transition: background 0.3s;" onmouseover="this.style.background='#bbdefb'" onmouseout="this.style.background='#e3f2fd'">
                            <strong>🚚 Transferência:</strong> ${agentes.transferencia}<br>
                            ${agentes.base_origem !== 'N/A' && agentes.base_destino !== 'N/A' ? 
                              `<small>Rota: ${agentes.base_origem} → ${agentes.base_destino}</small>` : ''}
                            <br><small style="color: #007bff;">👆 Clique para ver custos específicos</small>
                        </div>
                    `;
                }
                
                if (agentes.agente_entrega && agentes.agente_entrega !== 'N/A') {
                    html += `
                        <div onclick="exibirCustosAgente('entrega', ${index})" style="margin-bottom: 10px; padding: 8px; background: #fff3e0; border-radius: 4px; cursor: pointer; transition: background 0.3s;" onmouseover="this.style.background='#ffe0b2'" onmouseout="this.style.background='#fff3e0'">
                            <strong>🚛 Agente de Entrega:</strong> ${agentes.agente_entrega}<br>
                            ${agentes.base_destino !== 'N/A' ? `<small>Base Origem: ${agentes.base_destino}</small>` : ''}
                            <br><small style="color: #007bff;">👆 Clique para ver custos específicos</small>
                        </div>
                    `;
                }
                
                html += `
                                        <div style="margin-top: 10px; padding: 8px; background: #f0f0f0; border-radius: 4px;">
                                            <strong>⚖️ Peso Utilizado:</strong> 
                                            ${rota_info.peso_cubado ? rota_info.peso_cubado + ' kg' : (opcao.peso_usado ? opcao.peso_usado.replace('kg', '').trim() + ' kg' : 'N/A')}
                                            <br>
                                            <small>
                                                Tipo: ${(rota_info.tipo_peso_usado || opcao.peso_usado_tipo) ? (rota_info.tipo_peso_usado || opcao.peso_usado_tipo) : 'Desconhecido'}
                                                (Real: ${rota_info.peso_real ? rota_info.peso_real + ' kg' : 'N/A'}, Cubado: ${rota_info.cubagem ? (rota_info.cubagem * 300) + ' kg' : 'N/A'})
                                            </small>
                                        </div>
                                    </div>
                                    
                                    <!-- Detalhamento de Custos -->
                                    <div style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6;">
                                        <h5 style="color: #007bff; margin-bottom: 15px; font-size: 1rem;">
                                            💰 Detalhamento de Custos por Agente
                                        </h5>
                                        <div id="custos-container-${index}">
                `;
                
                // Exibir breakdown de custos detalhado por agente
                const custos = detalhes.custos_detalhados || {};
                const dadosAgentes = detalhes.dados_agentes || {};
                
                // Agente de Coleta
                if (agentes.agente_coleta && agentes.agente_coleta !== 'N/A') {
                    const dadosColeta = dadosAgentes.agente_coleta || {};
                    html += `
                                        <div style="margin-bottom: 15px; padding: 12px; background: #e8f5e8; border-radius: 6px; border-left: 4px solid #28a745;">
                                            <h6 style="color: #28a745; margin: 0 0 8px 0; font-weight: bold;">🚛 Agente de Coleta: ${agentes.agente_coleta}</h6>
                                            <div style="font-family: 'Courier New', monospace; font-size: 0.85rem;">
                                                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                                                    <span>💼 Custo Base:</span>
                                                    <span>R$ ${(custos.custo_coleta || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                                                    <span>🛣️ Pedágio:</span>
                                                    <span>R$ ${(custos.pedagio_coleta || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                                                    <span>📊 GRIS:</span>
                                                    <span>R$ ${(custos.gris_coleta || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                                                    <span>🛡️ Seguro:</span>
                                                    <span>R$ ${(custos.seguro_coleta || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 4px 0; margin-top: 4px; background: rgba(40, 167, 69, 0.1); border-radius: 3px; font-weight: bold;">
                                                    <span>💰 Subtotal Coleta:</span>
                                                    <span>R$ ${((custos.custo_coleta || 0) + (custos.pedagio_coleta || 0) + (custos.gris_coleta || 0) + (custos.seguro_coleta || 0)).toFixed(2)}</span>
                                                </div>
                                            </div>
                                        </div>
                    `;
                }
                
                // Transferência
                if (agentes.transferencia && agentes.transferencia !== 'N/A') {
                    const dadosTransferencia = dadosAgentes.transferencia || {};
                    html += `
                                        <div style="margin-bottom: 15px; padding: 12px; background: #e3f2fd; border-radius: 6px; border-left: 4px solid #2196f3;">
                                            <h6 style="color: #2196f3; margin: 0 0 8px 0; font-weight: bold;">🚚 Transferência: ${agentes.transferencia}</h6>
                                            <div style="font-family: 'Courier New', monospace; font-size: 0.85rem;">
                                                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                                                    <span>💼 Custo Base:</span>
                                                    <span>R$ ${(custos.custo_transferencia || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                                                    <span>🛣️ Pedágio:</span>
                                                    <span>R$ ${(custos.pedagio_transferencia || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                                                    <span>📊 GRIS:</span>
                                                    <span>R$ ${(custos.gris_transferencia || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                                                    <span>🛡️ Seguro:</span>
                                                    <span>R$ ${(custos.seguro_transferencia || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 4px 0; margin-top: 4px; background: rgba(33, 150, 243, 0.1); border-radius: 3px; font-weight: bold;">
                                                    <span>💰 Subtotal Transferência:</span>
                                                    <span>R$ ${((custos.custo_transferencia || 0) + (custos.pedagio_transferencia || 0) + (custos.gris_transferencia || 0) + (custos.seguro_transferencia || 0)).toFixed(2)}</span>
                                                </div>
                                            </div>
                                        </div>
                    `;
                }
                
                // Agente de Entrega
                if (agentes.agente_entrega && agentes.agente_entrega !== 'N/A') {
                    const dadosEntrega = dadosAgentes.agente_entrega || {};
                    html += `
                                        <div style="margin-bottom: 15px; padding: 12px; background: #fff3e0; border-radius: 6px; border-left: 4px solid #ff9800;">
                                            <h6 style="color: #ff9800; margin: 0 0 8px 0; font-weight: bold;">🚛 Agente de Entrega: ${agentes.agente_entrega}</h6>
                                            <div style="font-family: 'Courier New', monospace; font-size: 0.85rem;">
                                                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                                                    <span>💼 Custo Base:</span>
                                                    <span>R$ ${(custos.custo_entrega || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                                                    <span>🛣️ Pedágio:</span>
                                                    <span>R$ ${(custos.pedagio_entrega || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                                                    <span>📊 GRIS:</span>
                                                    <span>R$ ${(custos.gris_entrega || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                                                    <span>🛡️ Seguro:</span>
                                                    <span>R$ ${(custos.seguro_entrega || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 4px 0; margin-top: 4px; background: rgba(255, 152, 0, 0.1); border-radius: 3px; font-weight: bold;">
                                                    <span>💰 Subtotal Entrega:</span>
                                                    <span>R$ ${((custos.custo_entrega || 0) + (custos.pedagio_entrega || 0) + (custos.gris_entrega || 0) + (custos.seguro_entrega || 0)).toFixed(2)}</span>
                                                </div>
                                            </div>
                                        </div>
                    `;
                }
                
                // Total Geral
                html += `
                                        <div style="margin-top: 15px; padding: 12px; background: #e8f5e8; border-radius: 6px; border: 2px solid #28a745;">
                                            <h6 style="color: #28a745; margin: 0 0 8px 0; font-weight: bold;">💰 RESUMO GERAL</h6>
                                            <div style="font-family: 'Courier New', monospace; font-size: 0.9rem;">
                                                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc;">
                                                    <span>💼 Custo Base Total:</span>
                                                    <span><strong>R$ ${(custos.custo_base_frete || 0).toFixed(2)}</strong></span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc;">
                                                    <span>🛣️ Pedágio Total:</span>
                                                    <span>R$ ${(custos.pedagio || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc;">
                                                    <span>📊 GRIS Total:</span>
                                                    <span>R$ ${(custos.gris || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc;">
                                                    <span>🛡️ Seguro Total:</span>
                                                    <span>R$ ${(custos.seguro || 0).toFixed(2)}</span>
                                                </div>
                                                <div style="display: flex; justify-content: space-between; padding: 6px 0; margin-top: 8px; background: #28a745; color: white; border-radius: 4px; font-weight: bold; font-size: 1rem;">
                                                    <span>💰 TOTAL GERAL:</span>
                                                    <span>R$ ${opcao.custo_total.toFixed(2)}</span>
                                                </div>
                                            </div>
                                        </div>
                `;
                
                if (detalhes.observacoes) {
                    html += `
                                        <div style="margin-top: 15px; padding: 10px; background: #fffbf0; border-left: 4px solid #ffc107; border-radius: 4px;">
                                            <strong>📝 Observações:</strong><br>
                                            <small>${detalhes.observacoes}</small>
                                        </div>
                    `;
                }
                
                html += `
                                    </div>
                                </div>
                            </div>
                        </td>
                              </tr>
                        `;
                    });
            
            html += `
                        </tbody>
                    </table>
                    <div style="margin-top: 10px; font-size: 0.85rem; color: #666; text-align: center;">
                        <strong>Legenda:</strong> 
                        🥇 Melhor preço | 🥈 2º melhor | 🥉 3º melhor | 
                        📦 Frete Fracionado | 🔎 Clique em "Ver Detalhes" para mais informações
                    </div>
                </div>
            `;
        }
        
        html += `
            </div>
            
            <style>
            .analise-container {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
                margin: 15px 0;
            }
            
            .analise-title {
                font-size: 1.1rem;
                font-weight: bold;
                color: #495057;
                margin-bottom: 10px;
                padding-bottom: 8px;
                border-bottom: 2px solid #e9ecef;
            }
            
            .analise-item {
                margin: 8px 0;
                padding: 5px 0;
                font-size: 0.95rem;
            }
            
            .result-table {
                font-size: 0.9rem;
            }
            
            .result-table th, .result-table td {
                border: 1px solid #dee2e6;
                padding: 8px 12px;
            }
            
            .btn-secondary {
                background: #6c757d;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.8rem;
                cursor: pointer;
            }
            
            .btn-secondary:hover {
                background: #5a6268;
            }
            
            .btn-info:hover {
                background: #138496 !important;
                transform: translateY(-1px);
                transition: all 0.2s;
            }
            </style>
        `;
        
        container.innerHTML = html;
        
        // ✅ ARMAZENAR RANKING PARA ACESSO GLOBAL (NOVO)
        window.ultimoRankingFracionado = ranking;
        
        console.log('[FRACIONADO] Ranking exibido no formato dedicado com sucesso');
    }

    // 🆕 FUNÇÃO PARA EXPANDIR/COLAPSAR DETALHES DE CADA OPÇÃO
    window.toggleDetalhesOpcao = function(index) {
        const detalhesRow = document.getElementById(`detalhes-row-${index}`);
        const btnText = document.getElementById(`btn-text-${index}`);
        
        if (detalhesRow.style.display === 'none' || detalhesRow.style.display === '') {
            detalhesRow.style.display = 'table-row';
            btnText.innerHTML = '🔙 Ocultar Detalhes';
        } else {
            detalhesRow.style.display = 'none';
            btnText.innerHTML = '🔎 Ver Detalhes';
        }
    }

    // 🆕 FUNÇÃO PARA EXIBIR CUSTOS ESPECÍFICOS DE CADA AGENTE
    window.exibirCustosAgente = function(tipoAgente, opcaoIndex) {
        console.log(`[AGENTE-CLICK] Clicado em ${tipoAgente} da opção ${opcaoIndex}`);
        
        // Buscar dados da opção selecionada
        const rankingData = window.ultimoRankingFracionado;
        if (!rankingData || !rankingData.ranking_opcoes || !rankingData.ranking_opcoes[opcaoIndex]) {
            console.error('[AGENTE-CLICK] Dados da opção não encontrados');
            console.error('[AGENTE-CLICK] rankingData:', rankingData);
            console.error('[AGENTE-CLICK] ranking_opcoes:', rankingData?.ranking_opcoes);
            return;
        }
        
        const opcao = rankingData.ranking_opcoes[opcaoIndex];
        const detalhes = opcao.detalhes_expandidos || {};
        const agentes = detalhes.agentes_info || {};
        const rota_info = detalhes.rota_info || {};
        
        // Debug: verificar estrutura dos dados
        console.log(`[AGENTE-CLICK] Estrutura da opção:`, opcao);
        console.log(`[AGENTE-CLICK] Detalhes expandidos:`, detalhes);
        console.log(`[AGENTE-CLICK] Agentes info:`, agentes);
        console.log(`[AGENTE-CLICK] Rota info:`, rota_info);
        
        // Preparar informações específicas do agente clicado
        let agenteInfo = {};
        let custoEspecifico = 0;
        let nomeAgente = '';
        let alertaPeso = '';
        let pesoMaximo = null;
        let excedePeso = false;
        
        // ✅ BUSCAR DADOS DE PESO MÁXIMO DO AGENTE (NOVO)
        const dadosAgentesExpandidos = detalhes.dados_agentes || {};
        
        switch(tipoAgente) {
            case 'coleta':
                nomeAgente = agentes.agente_coleta || 'N/A';
                const dadosColeta = dadosAgentesExpandidos.agente_coleta || opcao.detalhes?.agente_coleta || {};
                pesoMaximo = dadosColeta.peso_maximo;
                alertaPeso = dadosColeta.alerta_peso;
                excedePeso = dadosColeta.excede_peso;
                agenteInfo = {
                    tipo: 'Agente de Coleta',
                    fornecedor: agentes.agente_coleta,
                    base: agentes.base_origem,
                    funcao: 'Coleta na origem e transporte até a base'
                };
                custoEspecifico = detalhes.custos_detalhados?.custo_coleta || (detalhes.custos_detalhados?.custo_base_frete * 0.3) || 0; // ✅ Custo real da coleta com fallback
                break;
            case 'transferencia':
                nomeAgente = agentes.transferencia || 'N/A';
                const dadosTransferencia = dadosAgentesExpandidos.transferencia || opcao.detalhes?.transferencia || {};
                pesoMaximo = dadosTransferencia.peso_maximo;
                alertaPeso = dadosTransferencia.alerta_peso;
                excedePeso = dadosTransferencia.excede_peso;
                agenteInfo = {
                    tipo: 'Transferência',
                    fornecedor: agentes.transferencia,
                    rota: `${agentes.base_origem} → ${agentes.base_destino}`,
                    funcao: 'Transporte entre bases'
                };
                custoEspecifico = detalhes.custos_detalhados?.custo_transferencia || (detalhes.custos_detalhados?.custo_base_frete * 0.5) || 0; // ✅ Custo real da transferência com fallback
                break;
            case 'entrega':
                nomeAgente = agentes.agente_entrega || 'N/A';
                const dadosEntrega = dadosAgentesExpandidos.agente_entrega || opcao.detalhes?.agente_entrega || {};
                pesoMaximo = dadosEntrega.peso_maximo;
                alertaPeso = dadosEntrega.alerta_peso;
                excedePeso = dadosEntrega.excede_peso;
                agenteInfo = {
                    tipo: 'Agente de Entrega',
                    fornecedor: agentes.agente_entrega,
                    base: agentes.base_destino,
                    funcao: 'Coleta na base e entrega no destino'
                };
                custoEspecifico = detalhes.custos_detalhados?.custo_entrega || (detalhes.custos_detalhados?.custo_base_frete * 0.2) || 0; // ✅ Custo real da entrega com fallback
                break;
        }
        
        // Montar HTML com informações específicas do agente
        // ✅ GERAR ALERTA DE PESO SE NECESSÁRIO (NOVO)
        let alertaPesoHtml = '';
        if (alertaPeso || excedePeso) {
            const corAlerta = excedePeso ? '#dc3545' : '#ffc107'; // Vermelho se excede, amarelo se aviso
            const iconeAlerta = excedePeso ? '🚨' : '⚠️';
            const backgroundAlerta = excedePeso ? '#f8d7da' : '#fff3cd';
            
            alertaPesoHtml = `
                <div style="background: ${backgroundAlerta}; border: 2px solid ${corAlerta}; padding: 12px; border-radius: 8px; margin-bottom: 15px; animation: pulse 1s infinite;">
                    <h6 style="color: ${corAlerta}; margin: 0 0 8px 0; font-weight: bold;">
                        ${iconeAlerta} ALERTA DE PESO MÁXIMO
                    </h6>
                    <div style="color: ${corAlerta}; font-size: 0.9rem; font-weight: 600;">
                        ${alertaPeso || `Peso cubado (${rota_info.peso_cubado || 'N/A'}kg) pode exceder limite do agente`}
                    </div>
                    ${pesoMaximo ? `
                    <div style="margin-top: 8px; padding: 8px; background: rgba(255,255,255,0.5); border-radius: 4px; font-size: 0.85rem;">
                        <strong>Peso Máximo do Agente:</strong> ${pesoMaximo}kg<br>
                        <strong>Peso da Carga:</strong> ${rota_info.peso_cubado || 'N/A'}kg (${rota_info.tipo_peso_usado || 'N/A'})<br>
                        <strong>Situação:</strong> ${excedePeso ? 'EXCEDE O LIMITE' : 'Dentro do limite'}
                    </div>
                    ` : ''}
                </div>
                
                <style>
                @keyframes pulse {
                    0% { transform: scale(1); }
                    50% { transform: scale(1.02); }
                    100% { transform: scale(1); }
                }
                </style>
            `;
        }

        const custosHtml = `
            ${alertaPesoHtml}
            
            <div style="background: #e8f5e8; padding: 15px; border-radius: 8px; border: 2px solid #28a745; margin-bottom: 10px;">
                <h6 style="color: #28a745; margin-bottom: 10px; font-weight: bold;">
                    📊 ${agenteInfo.tipo}: ${nomeAgente}
                </h6>
                <div style="font-family: 'Courier New', monospace; font-size: 0.9rem;">
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #28a745;">
                        <span><strong>Fornecedor:</strong></span>
                        <span><strong>${agenteInfo.fornecedor}</strong></span>
                    </div>
                    ${agenteInfo.base ? `
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #28a745;">
                        <span>📍 Base:</span>
                        <span>${agenteInfo.base}</span>
                    </div>
                    ` : ''}
                    ${agenteInfo.rota ? `
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #28a745;">
                        <span>🛣️ Rota:</span>
                        <span>${agenteInfo.rota}</span>
                    </div>
                    ` : ''}
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #28a745;">
                        <span>⚙️ Função:</span>
                        <span style="font-size: 0.8rem;">${agenteInfo.funcao}</span>
                    </div>
                    ${pesoMaximo ? `
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #28a745;">
                        <span>⚖️ Peso Máximo:</span>
                        <span style="font-weight: bold; color: ${excedePeso ? '#dc3545' : '#28a745'};">${pesoMaximo}kg</span>
                    </div>
                    ` : ''}
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #28a745;">
                        <span>📦 Peso da Carga:</span>
                        <span style="font-weight: bold;">${rota_info.peso_cubado || 'N/A'}kg (${rota_info.tipo_peso_usado || 'N/A'})</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; margin-top: 8px; background: #d4edda; border-radius: 4px; font-weight: bold;">
                        <span>💰 Custo Estimado:</span>
                        <span style="color: #28a745;">R$ ${custoEspecifico.toFixed(2)}</span>
                    </div>
                </div>
                <div style="margin-top: 10px; padding: 8px; background: #f8f9fa; border-radius: 4px; font-size: 0.8rem; color: #6c757d;">
                    <strong>💡 Informação:</strong> Este é o custo estimado específico deste ${agenteInfo.tipo.toLowerCase()}. 
                    O valor total da cotação inclui todos os serviços da rota.
                    ${pesoMaximo ? `<br><strong>Capacidade:</strong> Este agente suporta até ${pesoMaximo}kg.` : ''}
                </div>
            </div>
            
            <!-- Custos Gerais da Cotação -->
            <div style="font-family: 'Courier New', monospace; font-size: 0.9rem;">
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc;">
                    <span>🚛 Coleta:</span>
                    <span>R$ ${(detalhes.custos_detalhados?.custo_coleta || (detalhes.custos_detalhados?.custo_base_frete * 0.3) || 0).toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc;">
                    <span>🚚 Transferência:</span>
                    <span>R$ ${(detalhes.custos_detalhados?.custo_transferencia || (detalhes.custos_detalhados?.custo_base_frete * 0.5) || 0).toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc;">
                    <span>🚛 Entrega:</span>
                    <span>R$ ${(detalhes.custos_detalhados?.custo_entrega || (detalhes.custos_detalhados?.custo_base_frete * 0.2) || 0).toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc; background: #f0f0f0; font-weight: bold;">
                    <span>💼 Subtotal Frete:</span>
                    <span><strong>R$ ${(detalhes.custos_detalhados?.custo_base_frete || 0).toFixed(2)}</strong></span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc;">
                    <span>🛣️ Pedágio:</span>
                    <span>R$ ${(detalhes.custos_detalhados?.pedagio || 0).toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc;">
                    <span>📊 GRIS:</span>
                    <span>R$ ${(detalhes.custos_detalhados?.gris || 0).toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc;">
                    <span>🛡️ Seguro:</span>
                    <span>R$ ${(detalhes.custos_detalhados?.seguro || 0).toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc;">
                    <span>💳 ICMS:</span>
                    <span>R$ ${(detalhes.custos_detalhados?.icms || 0).toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dotted #ccc;">
                    <span>📋 Outros:</span>
                    <span>R$ ${(detalhes.custos_detalhados?.outros || 0).toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 8px 0; margin-top: 10px; background: #e8f5e8; border-radius: 4px; font-weight: bold; font-size: 1rem;">
                    <span>💰 TOTAL GERAL:</span>
                    <span style="color: #28a745;">R$ ${opcao.custo_total.toFixed(2)}</span>
                </div>
            </div>
        `;
        
        // Atualizar o container de custos
        const custosContainer = document.getElementById(`custos-container-${opcaoIndex}`);
        if (custosContainer) {
            custosContainer.innerHTML = custosHtml;
            
            // Animação de destaque
            custosContainer.style.transition = 'all 0.3s ease';
            custosContainer.style.transform = 'scale(1.02)';
            setTimeout(() => {
                custosContainer.style.transform = 'scale(1)';
            }, 300);
        }
        
        // Armazenar dados para referência
        window.ultimoAgenteClicado = {
            tipo: tipoAgente,
            opcaoIndex: opcaoIndex,
            agente: agenteInfo,
            custo: custoEspecifico,
            peso_maximo: pesoMaximo,
            alerta_peso: alertaPeso,
            excede_peso: excedePeso
        };
        
        console.log('[AGENTE-CLICK] Custos específicos exibidos:', agenteInfo);
        console.log('[AGENTE-CLICK] Dados de peso:', { pesoMaximo, alertaPeso, excedePeso, pesoCubado: rota_info.peso_cubado });
    }

    // 📦 FUNÇÃO PARA FORMATO ANTIGO (LEGACY) 
    function exibirFormatoLegacyFracionado(data, container) {
        // ... manter código legacy caso necessário para compatibilidade ...
        let html = '<h3>📦 Resultados do Frete Fracionado (Formato Legacy)</h3>';
        
        // Verificar se há opções detalhadas (nossa estrutura)
        const opcoes = data.opcoes_detalhadas || [];
        const resultado_base = data.resultado_base || {};
        
        // Informações da rota
        const origem = resultado_base.origem || data.analise?.origem || 'N/A';
        const uf_origem = resultado_base.uf_origem || 'N/A';
        const destino = resultado_base.destino || data.analise?.destino || 'N/A';
        const uf_destino = resultado_base.uf_destino || 'N/A';
        const peso = resultado_base.peso || data.analise?.peso || 0;
        const cubagem = resultado_base.cubagem || data.analise?.cubagem || 0;
        const peso_cubado = resultado_base.peso_cubado || data.peso_cubado || Math.max(peso, cubagem * 300);
        const valor_nf = resultado_base.valor_nf || data.analise?.valor_nf;

        html += `
            <div class="info-rota-fracionado">
                <p><strong>Rota:</strong> ${origem}/${uf_origem} → ${destino}/${uf_destino}</p>
                <p><strong>Peso:</strong> ${peso}kg | <strong>Cubagem:</strong> ${cubagem}m³ | <strong>Peso Cubado:</strong> ${peso_cubado}kg</p>
                ${valor_nf ? `<p><strong>Valor NF:</strong> R$ ${valor_nf.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</p>` : ''}
            </div>
            <p class="no-results">⚠️ Formato legacy - considere atualizar o backend</p>
        `;
        
        container.innerHTML = html;
        console.log('[FRACIONADO] Formato legacy exibido');
    }

    function exibirResultadoDedicado(data) {
        console.log('[DEDICADO] Iniciando exibição de resultados');
        
        // Detectar em qual aba estamos
        const abaAtiva = document.querySelector('.tab-content.active');
        const isAbaDedicado = abaAtiva && abaAtiva.id === 'dedicado';
        const isAbaAllIn = abaAtiva && abaAtiva.id === 'all-in';
        
        console.log('[DEDICADO] Aba ativa:', abaAtiva?.id);
        console.log('[DEDICADO] É aba dedicado?', isAbaDedicado);
        console.log('[DEDICADO] É aba all-in?', isAbaAllIn);
        console.log('[DEDICADO] Elemento aba ativa:', abaAtiva);
        console.log('[DEDICADO] Todas as abas:', document.querySelectorAll('.tab-content'));
        
        let container;
        let containerId;
        
        if (isAbaDedicado) {
            // Estamos na aba específica "Frete Dedicado"
            console.log('[DEDICADO] Exibindo na aba específica Frete Dedicado');
            container = document.getElementById('resultados-dedicado');
            containerId = 'resultados-dedicado';
            
            // Se o container não existir, vamos criá-lo
            if (!container) {
                console.log('[DEDICADO] Container não existe, criando...');
                const dedicadoTab = document.getElementById('dedicado');
                if (dedicadoTab) {
                    // Criar o container de resultados
                    const novoContainer = document.createElement('div');
                    novoContainer.id = 'resultados-dedicado';
                    novoContainer.className = 'resultados-dedicado';
                    novoContainer.style.marginTop = '20px';
                    
                    // Inserir após o mapa
                    const mapaSection = dedicadoTab.querySelector('#mapa-section-dedicado');
                    if (mapaSection) {
                        mapaSection.parentNode.insertBefore(novoContainer, mapaSection.nextSibling);
                    } else {
                        dedicadoTab.appendChild(novoContainer);
                    }
                    
                    container = novoContainer;
                    console.log('[DEDICADO] Container criado:', container);
                }
            }
        } else {
            // Estamos na aba "All In" ou outra aba
            console.log('[DEDICADO] Exibindo na aba All In');
            container = document.getElementById('resultados-dedicado-all-in');
            containerId = 'resultados-dedicado-all-in';
        }
        
        const analiseContainer = document.getElementById('analise-dedicado');
        const mapaSection = document.getElementById('mapa-section-dedicado');
        const mapContainer = document.getElementById('map-dedicado');
        
        console.log('[DEDICADO] Container encontrado:', !!container);
        console.log('[DEDICADO] Container element:', container);
        console.log('[DEDICADO] Dados recebidos:', data);

        if (!container) {
            console.error('[DEDICADO] Container de resultados não encontrado');
            showError('Container de resultados não encontrado. Recarregue a página.', containerId);
            return;
        }

        // Verificar se temos dados válidos
        if (!data) {
            console.error('[DEDICADO] Dados vazios recebidos');
            showError('Nenhum dado recebido do servidor.', containerId);
            return;
        }

        // Verificar se temos custos básicos
        if (!data.custos || Object.keys(data.custos).length === 0) {
            console.error('[DEDICADO] Nenhum custo encontrado nos dados');
            showError('Nenhum custo de frete encontrado para esta rota.', containerId);
            return;
        }

        console.log('[DEDICADO] Custos encontrados:', data.custos);

        // Se estamos na aba específica "Frete Dedicado", SEMPRE usar layout específico
        if (isAbaDedicado) {
            console.log('[DEDICADO] Usando layout específico para aba Frete Dedicado');
            exibirResultadoDedicadoEspecifico(data, container);
        } else {
            // Estamos na aba "All In" - verificar formato dos dados
            console.log('[DEDICADO] Verificando formato dos dados para All In:', data);
            console.log('[DEDICADO] data.ranking_dedicado:', data.ranking_dedicado);
            console.log('[DEDICADO] data.ranking_dedicado?.ranking_opcoes:', data.ranking_dedicado?.ranking_opcoes);
            
            if (data.ranking_dedicado && data.ranking_dedicado.ranking_opcoes) {
                console.log('[DEDICADO] Usando formato All In com ranking');
                exibirResultadoAllInDedicado(data);
            } else {
                console.log('[DEDICADO] Usando formato All In básico');
                exibirResultadoAllInDedicado(data);
            }
        }
    }

    // Função para exibir detalhes do veículo dedicado
    function exibirDetalhesVeiculoDedicado(tipo, valor, descricao, peso, volume) {
        const detailsContainer = document.getElementById('detalhes-content');
        if (!detailsContainer) {
            console.error('[DEDICADO] Container detalhes-content não encontrado');
            return;
        }
        
        console.log('[DEDICADO] Exibindo detalhes do veículo:', tipo, valor);
        
        // Destacar item selecionado
        document.querySelectorAll('#ranking-list-dedicado .ranking-item').forEach(item => {
            item.style.border = '1px solid #ddd';
        });
        const selectedItem = document.querySelector(`[data-veiculo="${tipo}"]`);
        if (selectedItem) {
            selectedItem.style.border = '2px solid #0a6ed1';
            selectedItem.style.boxShadow = '0 2px 8px rgba(10, 110, 209, 0.3)';
        }
        
        const capacidades = window.capacidadesDedicado || {};
        const veiculo = capacidades[tipo] || { icon: '🚛', descricao: 'Veículo', peso: 'N/A', volume: 'N/A' };
        
        const detailsHtml = `
            <div class="vehicle-details" style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <div class="vehicle-header" style="display: flex; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #eee;">
                    <div class="vehicle-icon-large" style="font-size: 3em; margin-right: 15px;">${veiculo.icon}</div>
                    <div class="vehicle-title" style="flex: 1;">
                        <h4 style="margin: 0; color: #0a6ed1; font-size: 1.5em;">${tipo}</h4>
                        <p style="margin: 5px 0 0 0; color: #666;">${descricao}</p>
                    </div>
                    <div class="vehicle-price" style="text-align: right;">
                        <span class="price-label" style="display: block; font-size: 0.9em; color: #666;">Preço Total</span>
                        <span class="price-value" style="display: block; font-size: 2em; font-weight: bold; color: #28a745;">R$ ${valor.toFixed(2)}</span>
                    </div>
                </div>
                
                <div class="vehicle-specs" style="margin-bottom: 20px;">
                    <h5 style="color: #0a6ed1; margin-bottom: 15px;"><i class="fa-solid fa-cogs"></i> Especificações Técnicas</h5>
                    <div class="specs-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                        <div class="spec-item" style="display: flex; align-items: center; padding: 10px; background: #f8f9fa; border-radius: 6px;">
                            <span class="spec-icon" style="font-size: 1.5em; margin-right: 10px;">⚖️</span>
                            <div class="spec-info">
                                <span class="spec-label" style="display: block; font-size: 0.8em; color: #666;">Capacidade de Peso</span>
                                <span class="spec-value" style="display: block; font-weight: bold;">${peso}</span>
                            </div>
                        </div>
                        <div class="spec-item" style="display: flex; align-items: center; padding: 10px; background: #f8f9fa; border-radius: 6px;">
                            <span class="spec-icon" style="font-size: 1.5em; margin-right: 10px;">📦</span>
                            <div class="spec-info">
                                <span class="spec-label" style="display: block; font-size: 0.8em; color: #666;">Volume Útil</span>
                                <span class="spec-value" style="display: block; font-weight: bold;">${volume}</span>
                            </div>
                        </div>
                        <div class="spec-item" style="display: flex; align-items: center; padding: 10px; background: #f8f9fa; border-radius: 6px;">
                            <span class="spec-icon" style="font-size: 1.5em; margin-right: 10px;">🚛</span>
                            <div class="spec-info">
                                <span class="spec-label" style="display: block; font-size: 0.8em; color: #666;">Tipo de Veículo</span>
                                <span class="spec-value" style="display: block; font-weight: bold;">${descricao}</span>
                            </div>
                        </div>
                        <div class="spec-item" style="display: flex; align-items: center; padding: 10px; background: #f8f9fa; border-radius: 6px;">
                            <span class="spec-icon" style="font-size: 1.5em; margin-right: 10px;">🛣️</span>
                            <div class="spec-info">
                                <span class="spec-label" style="display: block; font-size: 0.8em; color: #666;">Modalidade</span>
                                <span class="spec-value" style="display: block; font-weight: bold;">Frete Dedicado</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="vehicle-advantages" style="margin-bottom: 20px;">
                    <h5 style="color: #0a6ed1; margin-bottom: 15px;"><i class="fa-solid fa-star"></i> Vantagens</h5>
                    <div class="advantages-list" style="background: #f8f9fa; padding: 15px; border-radius: 6px;">
                        ${getVehicleAdvantages(tipo)}
                    </div>
                </div>
                
                <div class="vehicle-cost-breakdown" style="margin-bottom: 20px;">
                    <h5 style="color: #0a6ed1; margin-bottom: 15px;"><i class="fa-solid fa-calculator"></i> Composição do Custo</h5>
                    <div class="cost-items" style="background: #f8f9fa; padding: 15px; border-radius: 6px;">
                        <div class="cost-item" style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                            <span class="cost-label">🚛 Frete Base</span>
                            <span class="cost-value">R$ ${(valor * 0.7).toFixed(2)}</span>
                        </div>
                        <div class="cost-item" style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                            <span class="cost-label">⛽ Combustível</span>
                            <span class="cost-value">R$ ${(valor * 0.15).toFixed(2)}</span>
                        </div>
                        <div class="cost-item" style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                            <span class="cost-label">🛣️ Pedágios</span>
                            <span class="cost-value">R$ ${(valor * 0.08).toFixed(2)}</span>
                        </div>
                        <div class="cost-item" style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                            <span class="cost-label">📋 Outros</span>
                            <span class="cost-value">R$ ${(valor * 0.07).toFixed(2)}</span>
                        </div>
                        <div class="cost-total" style="display: flex; justify-content: space-between; margin-top: 15px; padding-top: 15px; border-top: 2px solid #0a6ed1;">
                            <span class="cost-label"><strong>💰 Total</strong></span>
                            <span class="cost-value"><strong>R$ ${valor.toFixed(2)}</strong></span>
                        </div>
                    </div>
                </div>
                
                <div class="vehicle-actions" style="display: flex; gap: 10px; justify-content: center;">
                    <button class="btn-primary" onclick="selecionarVeiculoDedicado('${tipo}', ${valor})" style="padding: 12px 24px; font-size: 1.1em;">
                        <i class="fa-solid fa-check"></i> Selecionar Este Veículo
                    </button>
                    <button class="btn-secondary" onclick="exportarCotacaoDedicado('${tipo}', ${valor})" style="padding: 12px 24px; font-size: 1.1em;">
                        <i class="fa-solid fa-download"></i> Exportar Cotação
                    </button>
                </div>
            </div>
        `;
        
        detailsContainer.innerHTML = detailsHtml;
        
        // Mostrar o container de detalhes
        const detalhesContainer = document.getElementById('detalhes-veiculo-dedicado');
        if (detalhesContainer) {
            detalhesContainer.style.display = 'block';
        }
        
        console.log('[DEDICADO] Detalhes do veículo exibidos com sucesso');
    }

    // Função para obter vantagens específicas do veículo
    function getVehicleAdvantages(tipo) {
        const advantages = {
            'FIORINO': [
                '💰 Menor custo para cargas pequenas',
                '🏃 Agilidade em entregas urbanas',
                '🚗 Acesso facilitado a locais restritos',
                '⚡ Rapidez na coleta e entrega'
            ],
            'VAN': [
                '📦 Ideal para volumes médios',
                '🚗 Flexibilidade urbana',
                '💰 Custo-benefício equilibrado',
                '🔒 Proteção da carga'
            ],
            '3/4': [
                '⚖️ Boa capacidade de peso',
                '📏 Volume adequado para diversos tipos de carga',
                '🛣️ Versatilidade em diferentes rotas',
                '💰 Preço competitivo'
            ],
            'TOCO': [
                '🏋️ Alta capacidade de peso',
                '📦 Grande volume útil',
                '🛣️ Ideal para médias distâncias',
                '⚙️ Robustez e confiabilidade'
            ],
            'TRUCK': [
                '💪 Excelente capacidade de carga',
                '🚛 Otimizado para longas distâncias',
                '📦 Grande volume disponível',
                '⚡ Eficiência no transporte'
            ],
            'CARRETA': [
                '🚛 Máxima capacidade de transporte',
                '💰 Melhor custo por tonelada',
                '🛣️ Ideal para longas distâncias',
                '📦 Volume superior para cargas grandes'
            ]
        };
        
        const vehicleAdvantages = advantages[tipo] || ['✅ Solução de transporte confiável'];
        return vehicleAdvantages.map(adv => `<div class="advantage-item">${adv}</div>`).join('');
    }

    // Função para selecionar veículo (placeholder)
    function selecionarVeiculoDedicado(tipo, valor) {
        alert(`Veículo ${tipo} selecionado!\nValor: R$ ${valor.toFixed(2)}\n\nEm breve: integração com sistema de pedidos.`);
    }

    // Função para exportar cotação (placeholder)
    function exportarCotacaoDedicado(tipo, valor) {
        alert(`Exportando cotação do veículo ${tipo}...\nValor: R$ ${valor.toFixed(2)}\n\nEm breve: geração de PDF automático.`);
    }

    function exibirResultadoAereo(data) {
        const container = document.getElementById('resultados-aereo');
        if (!container) return;

        let html = '<h3>Resultados do Frete Aéreo</h3>';
        
        if (data.custos) {
            html += '<table class="results"><thead><tr><th>Modalidade</th><th>Valor</th></tr></thead><tbody>';
            
            Object.entries(data.custos).forEach(([modalidade, valor]) => {
                html += `
                                <tr>
                                  <td>${modalidade}</td>
                        <td><strong>R$ ${valor.toFixed(2)}</strong></td>
                                </tr>
                `;
            });
            
            html += '</tbody></table>';
        }
        
        container.innerHTML = html;
    }

    function exibirHistorico(historico) {
        const container = document.getElementById('listaHistorico');
        if (!container) return;

        if (!historico || historico.length === 0) {
            container.innerHTML = '<div class="alert alert-info">Nenhum item no histórico ainda.</div>';
                return;
            }
            
        let html = '<h3>Últimos Cálculos</h3>';
        html += '<div class="historico-lista">';
        
        historico.slice(-10).reverse().forEach((item, index) => {
            html += `
                <div class="historico-item">
                    <div class="historico-header">
                        <strong>${item.tipo || 'Cálculo'} #${item.id_historico || index + 1}</strong>
                        <span class="historico-data">${item.data_hora || 'Data não disponível'}</span>
                    </div>
                    <div class="historico-detalhes">
                        <span>${item.origem || 'Origem'} → ${item.destino || 'Destino'}</span>
                        <span>Distância: ${item.distancia || 'N/A'} km</span>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
    }

    function toggleLoading(id, show) {
        const loading = document.getElementById(id);
        if (loading) {
            loading.style.display = show ? 'block' : 'none';
        }
    }

    function showError(msg, containerId) {
        console.error(`[ERROR] ${msg} (Container: ${containerId})`);
        
        // Criar um alerta temporário
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger';
        alertDiv.style.position = 'fixed';
        alertDiv.style.top = '20px';
        alertDiv.style.right = '20px';
        alertDiv.style.zIndex = '9999';
        alertDiv.style.maxWidth = '400px';
        alertDiv.innerHTML = `
            <strong>Erro:</strong> ${msg}
            <button type="button" class="close" style="float: right; background: none; border: none; font-size: 1.5rem; line-height: 1;" onclick="this.parentElement.remove()">
                &times;
                            </button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Remover o alerta após 10 segundos
        setTimeout(() => {
            if (alertDiv.parentElement) {
                alertDiv.remove();
            }
        }, 10000);
    }

    // Função para criar painel de status flutuante
    function criarPainelStatusFlutuante() {
        // Criar botão flutuante
        const botaoStatus = document.createElement('button');
        botaoStatus.id = 'botao-status-flutuante';
        botaoStatus.innerHTML = '📊';
        botaoStatus.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #0a6ed1 0%, #1e88e5 100%);
            border: none;
            color: white;
            font-size: 20px;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            transition: all 0.3s ease;
        `;
        
        // Criar painel de detalhes (inicialmente oculto)
        const painelDetalhes = document.createElement('div');
        painelDetalhes.id = 'sistema-status-painel';
        painelDetalhes.style.cssText = `
            position: fixed;
            bottom: 80px;
            right: 20px;
            z-index: 9998;
            background: linear-gradient(135deg, #e3f2fd 0%, #f1f8e9 100%);
            border: 2px solid #0a6ed1;
            border-radius: 12px;
            padding: 15px;
            font-size: 0.85rem;
            max-width: 300px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.2);
            display: none;
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s ease;
        `;
        
        painelDetalhes.innerHTML = `
            <div style="font-weight: 600; color: #0a6ed1; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                📊 Status do Sistema
                <button onclick="toggleStatusPanel()" style="background: none; border: none; color: #0a6ed1; font-size: 18px; cursor: pointer;">×</button>
            </div>
            <div id="status-apis" style="margin: 6px 0;">
                🔄 Verificando APIs...
            </div>
            <div id="status-formularios" style="margin: 6px 0;">
                📝 Formulários: <span style="color: #28a745;">4 ativos</span>
            </div>
            <div id="status-municipios" style="margin: 6px 0;">
                🏙️ Municípios: <span style="color: #ffc107;">Aguardando teste</span>
            </div>
            <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #dee2e6; font-size: 0.75rem; color: #6c757d;">
                Sistema funcionando corretamente ✅
                        </div>
                    `;
                    
        // Adicionar eventos
        botaoStatus.onclick = function() {
            toggleStatusPanel();
            atualizarStatusSistema();
        };
        
        // Efeito hover no botão
        botaoStatus.onmouseenter = function() {
            this.style.transform = 'scale(1.1)';
            this.style.boxShadow = '0 6px 16px rgba(0,0,0,0.4)';
        };
        
        botaoStatus.onmouseleave = function() {
            this.style.transform = 'scale(1)';
            this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
        };
        
        document.body.appendChild(botaoStatus);
        document.body.appendChild(painelDetalhes);
        
        // Verificar status das APIs automaticamente
        setTimeout(verificarStatusAPIs, 1000);
    }
    
    // Função para alternar o painel de status
    window.toggleStatusPanel = function() {
        const painel = document.getElementById('sistema-status-painel');
        if (!painel) return;
        
        if (painel.style.display === 'none' || painel.style.display === '') {
            painel.style.display = 'block';
            setTimeout(() => {
                painel.style.opacity = '1';
                painel.style.transform = 'translateY(0)';
            }, 10);
                } else {
            painel.style.opacity = '0';
            painel.style.transform = 'translateY(20px)';
            setTimeout(() => {
                painel.style.display = 'none';
            }, 300);
        }
    };

    // Função para verificar status das APIs
    async function verificarStatusAPIs() {
        const statusElement = document.getElementById('status-apis');
        if (!statusElement) return;
        
        try {
            // Testar API de estados
            const estadosResponse = await fetch('/estados');
            const estadosData = await estadosResponse.json();
            
            // Testar API de municípios
            const municipiosResponse = await fetch('/municipios/SP');
            const municipiosData = await municipiosResponse.json();
            
            if (estadosResponse.ok && municipiosResponse.ok) {
                statusElement.innerHTML = `🟢 APIs: Estados (${estadosData.length}) | Municípios (${municipiosData.length})`;
                statusElement.style.color = '#28a745';
    } else {
                throw new Error('APIs retornaram erro');
            }
        } catch (error) {
            statusElement.innerHTML = '🔴 APIs: Erro na conexão';
            statusElement.style.color = '#dc3545';
        }
    }

    // Função para atualizar status do sistema
    function atualizarStatusSistema() {
        const statusMunicipios = document.getElementById('status-municipios');
        if (!statusMunicipios) return;
        
        // Contar quantos datalists foram populados
        const datalists = document.querySelectorAll('datalist[id^="datalist_municipio"]');
        let totalCarregados = 0;
        
        datalists.forEach(datalist => {
            if (datalist.children.length > 0) {
                totalCarregados++;
            }
        });
        
        if (totalCarregados > 0) {
            statusMunicipios.innerHTML = `🟢 Municípios: ${totalCarregados} formulários carregados`;
            statusMunicipios.style.color = '#28a745';
        } else {
            statusMunicipios.innerHTML = '🟡 Municípios: Nenhum carregado ainda';
            statusMunicipios.style.color = '#ffc107';
        }
    }

    // Funções globais para calculadoras de volume
    window.calcularCubagem = function() {
        const largura = parseFloat(document.getElementById('largura_frac').value) || 0;
        const altura = parseFloat(document.getElementById('altura_frac').value) || 0;
        const comprimento = parseFloat(document.getElementById('comprimento_frac').value) || 0;
        
        if (largura > 0 && altura > 0 && comprimento > 0) {
            const cubagem = largura * altura * comprimento;
            document.getElementById('cubagem_frac').value = cubagem.toFixed(3);
            
            const formulaTexto = document.getElementById('formula-texto');
            if (formulaTexto) {
                formulaTexto.innerHTML = `📐 ${largura}m × ${altura}m × ${comprimento}m = ${cubagem.toFixed(3)}m³`;
                formulaTexto.style.color = '#28a745';
                formulaTexto.style.fontWeight = '600';
            }
        }
    };

    window.calcularCubagemDedicado = function() {
        const largura = parseFloat(document.getElementById('largura').value) || 0;
        const altura = parseFloat(document.getElementById('altura').value) || 0;
        const comprimento = parseFloat(document.getElementById('comprimento').value) || 0;
        
        if (largura > 0 && altura > 0 && comprimento > 0) {
            const cubagem = largura * altura * comprimento;
            document.getElementById('cubagem').value = cubagem.toFixed(3);
            
            const formulaTexto = document.getElementById('formula-texto-dedicado');
            if (formulaTexto) {
                formulaTexto.innerHTML = `📐 ${largura}m × ${altura}m × ${comprimento}m = ${cubagem.toFixed(3)}m³`;
                formulaTexto.style.color = '#28a745';
                formulaTexto.style.fontWeight = '600';
            }
        }
    };

    window.calcularCubagemAll = function() {
        const largura = parseFloat(document.getElementById('largura_all').value) || 0;
        const altura = parseFloat(document.getElementById('altura_all').value) || 0;
        const comprimento = parseFloat(document.getElementById('comprimento_all').value) || 0;
        
        if (largura > 0 && altura > 0 && comprimento > 0) {
            const cubagem = largura * altura * comprimento;
            document.getElementById('cubagem_all').value = cubagem.toFixed(3);
            
            const formulaTexto = document.getElementById('formula-texto-all');
            if (formulaTexto) {
                formulaTexto.innerHTML = `📐 ${largura}m × ${altura}m × ${comprimento}m = ${cubagem.toFixed(3)}m³`;
                formulaTexto.style.color = '#28a745';
                formulaTexto.style.fontWeight = '600';
            }
        }
    };

    // Funções para resetar calculadoras
    window.resetarCubagem = function() {
        document.getElementById('largura_frac').value = '';
        document.getElementById('altura_frac').value = '';
        document.getElementById('comprimento_frac').value = '';
        document.getElementById('cubagem_frac').value = '';
        
        const formulaTexto = document.getElementById('formula-texto');
        if (formulaTexto) {
            formulaTexto.innerHTML = '📝 Digite diretamente ou use a calculadora abaixo';
            formulaTexto.style.color = '#6c757d';
            formulaTexto.style.fontWeight = 'normal';
        }
    };

    window.resetarCubagemDedicado = function() {
        document.getElementById('largura').value = '';
        document.getElementById('altura').value = '';
        document.getElementById('comprimento').value = '';
        document.getElementById('cubagem').value = '';
        
        const formulaTexto = document.getElementById('formula-texto-dedicado');
        if (formulaTexto) {
            formulaTexto.innerHTML = '📝 Digite diretamente ou use a calculadora abaixo';
            formulaTexto.style.color = '#6c757d';
            formulaTexto.style.fontWeight = 'normal';
        }
    };

    window.resetarCubagemAll = function() {
        document.getElementById('largura_all').value = '';
        document.getElementById('altura_all').value = '';
        document.getElementById('comprimento_all').value = '';
        document.getElementById('cubagem_all').value = '';
        
        const formulaTexto = document.getElementById('formula-texto-all');
        if (formulaTexto) {
            formulaTexto.innerHTML = '📝 Digite diretamente ou use a calculadora abaixo';
            formulaTexto.style.color = '#6c757d';
            formulaTexto.style.fontWeight = 'normal';
        }
    };

    // Função para abrir abas
    window.openTab = function(evt, tabName) {
        var i, tabcontent, tablinks;
        
        tabcontent = document.getElementsByClassName("tab-content");
        for (i = 0; i < tabcontent.length; i++) {
            tabcontent[i].classList.remove("active");
        }
        
        tablinks = document.getElementsByClassName("tab-btn");
        for (i = 0; i < tablinks.length; i++) {
            tablinks[i].classList.remove("active");
        }
        
        document.getElementById(tabName).classList.add("active");
            evt.currentTarget.classList.add("active");
        
        // Recarregar histórico quando a aba for aberta
        if (tabName === 'historico') {
            carregarHistorico();
        }
    };

    // ===== FUNÇÕES DE CALCULADORA DE VOLUME =====

    // Calculadora de volume para Frete Fracionado
    window.calcularCubagem = function() {
        console.log('Calculando cubagem para frete fracionado...');
        
        const comprimento = parseFloat(document.getElementById('comprimento')?.value) || 0;
        const largura = parseFloat(document.getElementById('largura')?.value) || 0;
        const altura = parseFloat(document.getElementById('altura')?.value) || 0;
        
        if (comprimento > 0 && largura > 0 && altura > 0) {
            const cubagem = comprimento * largura * altura;
            const cubagemFormatada = cubagem.toFixed(4);
            
            // Atualizar o campo de volume
            const volumeInput = document.getElementById('volume');
            if (volumeInput) {
                volumeInput.value = cubagemFormatada;
            }
            
            // Mostrar fórmula de cálculo
            const formulaDiv = document.getElementById('formula-calculo');
            if (formulaDiv) {
                formulaDiv.innerHTML = `
                    <div style="background: #e8f5e8; padding: 10px; border-radius: 5px; margin-top: 10px;">
                        <strong>Cálculo:</strong> ${comprimento} × ${largura} × ${altura} = <span style="color: #28a745; font-weight: bold;">${cubagemFormatada} m³</span>
                    </div>
                `;
            }
            
            console.log(`Cubagem calculada: ${cubagemFormatada} m³`);
        } else {
            // Limpar o volume se alguma dimensão estiver vazia
            const volumeInput = document.getElementById('volume');
            if (volumeInput) {
                volumeInput.value = '';
            }
            
            const formulaDiv = document.getElementById('formula-calculo');
            if (formulaDiv) {
                formulaDiv.innerHTML = '';
            }
        }
    }

    window.resetarCubagem = function() {
        console.log('Resetando cubagem para frete fracionado...');
        
        // Limpar campos de dimensões
        const campos = ['comprimento', 'largura', 'altura', 'volume'];
        campos.forEach(campo => {
            const elemento = document.getElementById(campo);
            if (elemento) {
                elemento.value = '';
            }
        });
        
        // Limpar fórmula
        const formulaDiv = document.getElementById('formula-calculo');
        if (formulaDiv) {
            formulaDiv.innerHTML = '';
        }
        
        console.log('Cubagem resetada para frete fracionado');
    }

    // Calculadora de volume para All In
    window.calcularCubagemAll = function() {
        console.log('Calculando cubagem para All In...');
        
        const comprimento = parseFloat(document.getElementById('comprimento_all')?.value) || 0;
        const largura = parseFloat(document.getElementById('largura_all')?.value) || 0;
        const altura = parseFloat(document.getElementById('altura_all')?.value) || 0;
        
        if (comprimento > 0 && largura > 0 && altura > 0) {
            const cubagem = comprimento * largura * altura;
            const cubagemFormatada = cubagem.toFixed(4);
            
            // Atualizar o campo de volume
            const volumeInput = document.getElementById('volume_all');
            if (volumeInput) {
                volumeInput.value = cubagemFormatada;
            }
            
            // Mostrar fórmula de cálculo
            const formulaDiv = document.getElementById('formula-calculo-all');
            if (formulaDiv) {
                formulaDiv.innerHTML = `
                    <div style="background: #e8f5e8; padding: 10px; border-radius: 5px; margin-top: 10px;">
                        <strong>Cálculo:</strong> ${comprimento} × ${largura} × ${altura} = <span style="color: #28a745; font-weight: bold;">${cubagemFormatada} m³</span>
                        </div>
                    `;
            }
            
            console.log(`Cubagem All In calculada: ${cubagemFormatada} m³`);
                } else {
            // Limpar o volume se alguma dimensão estiver vazia
            const volumeInput = document.getElementById('volume_all');
            if (volumeInput) {
                volumeInput.value = '';
            }
            
            const formulaDiv = document.getElementById('formula-calculo-all');
            if (formulaDiv) {
                formulaDiv.innerHTML = '';
            }
        }
    }

    window.resetarCubagemAll = function() {
        console.log('Resetando cubagem para All In...');
        
        // Limpar campos de dimensões
        const campos = ['comprimento_all', 'largura_all', 'altura_all', 'volume_all'];
        campos.forEach(campo => {
            const elemento = document.getElementById(campo);
            if (elemento) {
                elemento.value = '';
            }
        });
        
        // Limpar fórmula
        const formulaDiv = document.getElementById('formula-calculo-all');
        if (formulaDiv) {
            formulaDiv.innerHTML = '';
        }
        
        console.log('Cubagem resetada para All In');
    }

    // Calculadora de volume para Frete Dedicado
    window.calcularCubagemDedicado = function() {
        console.log('Calculando cubagem para frete dedicado...');
        
        const comprimento = parseFloat(document.getElementById('comprimento_dedicado')?.value) || 0;
        const largura = parseFloat(document.getElementById('largura_dedicado')?.value) || 0;
        const altura = parseFloat(document.getElementById('altura_dedicado')?.value) || 0;
        
        if (comprimento > 0 && largura > 0 && altura > 0) {
            const cubagem = comprimento * largura * altura;
            const cubagemFormatada = cubagem.toFixed(4);
            
            // Atualizar o campo de volume
            const volumeInput = document.getElementById('volume_dedicado');
            if (volumeInput) {
                volumeInput.value = cubagemFormatada;
            }
            
            // Mostrar fórmula de cálculo
            const formulaDiv = document.getElementById('formula-calculo-dedicado');
            if (formulaDiv) {
                formulaDiv.innerHTML = `
                    <div style="background: #e8f5e8; padding: 10px; border-radius: 5px; margin-top: 10px;">
                        <strong>Cálculo:</strong> ${comprimento} × ${largura} × ${altura} = <span style="color: #28a745; font-weight: bold;">${cubagemFormatada} m³</span>
                        </div>
                    `;
            }
            
            console.log(`Cubagem Dedicado calculada: ${cubagemFormatada} m³`);
        } else {
            // Limpar o volume se alguma dimensão estiver vazia
            const volumeInput = document.getElementById('volume_dedicado');
            if (volumeInput) {
                volumeInput.value = '';
            }
            
            const formulaDiv = document.getElementById('formula-calculo-dedicado');
            if (formulaDiv) {
                formulaDiv.innerHTML = '';
            }
        }
    }

    window.resetarCubagemDedicado = function() {
        console.log('Resetando cubagem para frete dedicado...');
        
        // Limpar campos de dimensões
        const campos = ['comprimento_dedicado', 'largura_dedicado', 'altura_dedicado', 'volume_dedicado'];
        campos.forEach(campo => {
            const elemento = document.getElementById(campo);
            if (elemento) {
                elemento.value = '';
            }
        });
        
        // Limpar fórmula
        const formulaDiv = document.getElementById('formula-calculo-dedicado');
        if (formulaDiv) {
            formulaDiv.innerHTML = '';
        }
        
        console.log('Cubagem resetada para frete dedicado');
    }

    // Funções para calculadoras avançadas (modais)
    window.abrirCalculadoraAvancada = function() {
        console.log('Abrindo calculadora avançada para frete fracionado');
        const modal = document.getElementById('calculadora-modal');
        if (modal) {
            modal.style.display = 'block';
            
            // Inicializar com um SKU se ainda não houver nenhum
            if (window.skusDataFracionado.length === 0) {
                window.adicionarSku();
            }
        } else {
            console.error('Modal calculadora-modal não encontrado');
        }
    }

    window.fecharCalculadoraAvancada = function() {
        console.log('Fechando calculadora avançada para frete fracionado');
        const modal = document.getElementById('calculadora-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    window.abrirCalculadoraAvancadaAll = function() {
        console.log('Abrindo calculadora avançada para All In');
        const modal = document.getElementById('calculadora-modal-all');
        if (modal) {
            modal.style.display = 'block';
            
            // Inicializar com um SKU se ainda não houver nenhum
            if (window.skusDataAll.length === 0) {
                window.adicionarSkuAll();
            }
        } else {
            console.error('Modal calculadora-modal-all não encontrado');
        }
    }

    window.fecharCalculadoraAvancadaAll = function() {
        console.log('Fechando calculadora avançada para All In');
        const modal = document.getElementById('calculadora-modal-all');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    window.abrirCalculadoraAvancadaDedicado = function() {
        console.log('Abrindo calculadora avançada para frete dedicado');
        const modal = document.getElementById('calculadora-modal-dedicado');
        if (modal) {
            modal.style.display = 'block';
            
            // Inicializar com um SKU se ainda não houver nenhum
            if (window.skusDataDedicado.length === 0) {
                window.adicionarSkuDedicado();
            }
        } else {
            console.error('Modal calculadora-modal-dedicado não encontrado');
        }
    }

    window.fecharCalculadoraAvancadaDedicado = function() {
        console.log('Fechando calculadora avançada para frete dedicado');
        const modal = document.getElementById('calculadora-modal-dedicado');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    // Variáveis globais para as calculadoras avançadas
    window.skusDataAll = [];
    window.skusDataFracionado = [];
    window.skusDataDedicado = [];

    // Funções para adicionar/remover SKUs nas calculadoras avançadas
    window.adicionarSku = function() {
        console.log('Adicionando SKU na calculadora avançada fracionado');
        adicionarSkuGenerico('lista-volumes', window.skusDataFracionado, 'resumo-calculo');
    }

    window.adicionarSkuAll = function() {
        console.log('Adicionando SKU na calculadora avançada All In');
        adicionarSkuGenerico('lista-volumes-all', window.skusDataAll, 'resumo-calculo-all');
    }

    window.adicionarSkuDedicado = function() {
        console.log('Adicionando SKU na calculadora avançada Dedicado');
        adicionarSkuGenerico('lista-volumes-dedicado', window.skusDataDedicado, 'resumo-calculo-dedicado');
    }

    function adicionarSkuGenerico(listaId, skusArray, resumoId) {
        const skuId = 'sku_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        
        const skuData = {
            id: skuId,
            nome: '',
            quantidade_total: 1,
            qtd_por_medida: 1,
            largura: 0,
            altura: 0,
            comprimento: 0,
            cubagem_unitaria: 0,
            cubagem_total: 0,
            total_volumes: 0
        };
        
        skusArray.push(skuData);
        
        const listaVolumes = document.getElementById(listaId);
        if (!listaVolumes) {
            console.error(`Lista de volumes não encontrada: ${listaId}`);
            return;
        }
        
        const skuHtml = `
            <div class="sku-item" id="${skuId}">
                <div class="sku-header">
                    <span class="sku-title">📦 Grupo de Medidas ${skusArray.length}</span>
                    <button type="button" class="btn-remove-sku" onclick="removerSku('${skuId}', '${listaId}', '${resumoId}')">
                        <i class="fa-solid fa-trash"></i> Remover
                    </button>
                </div>
                
                <div class="sku-info-row">
                    <div class="form-group">
                        <label>Nome/Descrição (opcional):</label>
                        <input type="text" placeholder="Ex: Caixas grandes" onchange="atualizarSku('${skuId}', 'nome', this.value, '${listaId}', '${resumoId}')">
                    </div>
                </div>
                
                <div class="sku-fields">
                    <div class="form-group">
                        <label>Total de SKUs:</label>
                        <input type="number" min="1" value="1" onchange="atualizarSku('${skuId}', 'quantidade_total', this.value, '${listaId}', '${resumoId}')">
                    </div>
                    <div class="form-group">
                        <label>SKUs por medida:</label>
                        <input type="number" min="1" value="1" onchange="atualizarSku('${skuId}', 'qtd_por_medida', this.value, '${listaId}', '${resumoId}')" title="Quantos SKUs têm essa mesma medida">
                    </div>
                </div>
                
                <div class="medidas-header">
                    <strong>📐 Medidas (por unidade):</strong>
                </div>
                
                <div class="sku-fields">
                    <div class="form-group">
                        <label>Largura (m):</label>
                        <input type="number" step="0.01" min="0.01" placeholder="1.20" onchange="atualizarSku('${skuId}', 'largura', this.value, '${listaId}', '${resumoId}')">
                    </div>
                    <div class="form-group">
                        <label>Altura (m):</label>
                        <input type="number" step="0.01" min="0.01" placeholder="0.80" onchange="atualizarSku('${skuId}', 'altura', this.value, '${listaId}', '${resumoId}')">
                    </div>
                    <div class="form-group">
                        <label>Comprimento (m):</label>
                        <input type="number" step="0.01" min="0.01" placeholder="2.40" onchange="atualizarSku('${skuId}', 'comprimento', this.value, '${listaId}', '${resumoId}')">
                    </div>
                </div>
                
                <div class="sku-resultado" id="resultado-${skuId}">
                    <div class="resultado-linha">
                        <strong>📏 Cubagem unitária:</strong> 0.000 m³
                    </div>
                    <div class="resultado-linha">
                        <strong>📦 Total de volumes:</strong> 0 (0 grupos de 0)
                    </div>
                    <div class="resultado-linha resultado-destaque">
                        <strong>🎯 Cubagem total:</strong> 0.000 m³
                    </div>
                </div>
            </div>
        `;
        
        listaVolumes.insertAdjacentHTML('beforeend', skuHtml);
        atualizarResumoCalculadoraGenerico(skusArray, resumoId);
    }

    window.removerSku = function(skuId, listaId, resumoId) {
        console.log('Removendo SKU:', skuId);
        
        // Determinar qual array usar
        let skusArray;
        if (listaId === 'lista-volumes-all') {
            skusArray = window.skusDataAll;
        } else if (listaId === 'lista-volumes-dedicado') {
            skusArray = window.skusDataDedicado;
        } else {
            skusArray = window.skusDataFracionado;
        }
        
        // Não permitir remover se for o último SKU
        if (skusArray.length <= 1) {
            alert('Deve haver pelo menos um SKU configurado!');
            return;
        }
        
        // Remover do array
        const index = skusArray.findIndex(sku => sku.id === skuId);
        if (index > -1) {
            skusArray.splice(index, 1);
        }
        
        // Remover do DOM
        const element = document.getElementById(skuId);
        if (element) {
            element.remove();
        }
        
        // Renumerar os SKUs
        renumerarSkusGenerico(listaId, skusArray);
        atualizarResumoCalculadoraGenerico(skusArray, resumoId);
    }

    window.atualizarSku = function(skuId, campo, valor, listaId, resumoId) {
        // Determinar qual array usar
        let skusArray;
        if (listaId === 'lista-volumes-all') {
            skusArray = window.skusDataAll;
        } else if (listaId === 'lista-volumes-dedicado') {
            skusArray = window.skusDataDedicado;
        } else {
            skusArray = window.skusDataFracionado;
        }
        
        const sku = skusArray.find(s => s.id === skuId);
        if (!sku) return;
        
        // Atualizar campo
        if (campo === 'nome') {
            sku[campo] = valor;
        } else {
            sku[campo] = parseFloat(valor) || 0;
        }
        
        // Calcular cubagem unitária e total
        if (sku.largura > 0 && sku.altura > 0 && sku.comprimento > 0) {
            sku.cubagem_unitaria = sku.largura * sku.altura * sku.comprimento;
            
            // Calcular total de volumes (grupos)
            if (sku.qtd_por_medida > 0) {
                sku.total_volumes = Math.ceil(sku.quantidade_total / sku.qtd_por_medida);
            } else {
                sku.total_volumes = 0;
            }
            
            // Cubagem total = cubagem unitária × total de SKUs
            sku.cubagem_total = sku.cubagem_unitaria * sku.quantidade_total;
        } else {
            sku.cubagem_unitaria = 0;
            sku.cubagem_total = 0;
            sku.total_volumes = 0;
        }
        
        // Atualizar display do SKU
        const resultadoDiv = document.getElementById(`resultado-${skuId}`);
        if (resultadoDiv) {
            const grupos = sku.total_volumes;
            const porGrupo = sku.qtd_por_medida;
            
            resultadoDiv.innerHTML = `
                <div class="resultado-linha">
                    <strong>📏 Cubagem unitária:</strong> ${sku.cubagem_unitaria.toFixed(3)} m³
                </div>
                <div class="resultado-linha">
                    <strong>📦 Total de volumes:</strong> ${sku.quantidade_total} (${grupos} grupos de ${porGrupo})
                </div>
                <div class="resultado-linha resultado-destaque">
                    <strong>🎯 Cubagem total:</strong> ${sku.cubagem_total.toFixed(3)} m³
                </div>
            `;
        }
        
        atualizarResumoCalculadoraGenerico(skusArray, resumoId);
    }

    function renumerarSkusGenerico(listaId, skusArray) {
        const lista = document.getElementById(listaId);
        if (!lista) return;
        
        const skuItems = lista.querySelectorAll('.sku-item');
        skuItems.forEach((item, index) => {
            const title = item.querySelector('.sku-title');
            if (title) {
                title.textContent = `📦 Grupo de Medidas ${index + 1}`;
            }
        });
    }

        function atualizarResumoCalculadoraGenerico(skusArray, resumoId) {
        const totalSKUs = skusArray.reduce((sum, sku) => sum + sku.quantidade_total, 0);
        const totalVolumes = skusArray.reduce((sum, sku) => sum + sku.total_volumes, 0);
        const totalCubagem = skusArray.reduce((sum, sku) => sum + sku.cubagem_total, 0);
        const skusValidos = skusArray.filter(sku => sku.cubagem_total > 0);
        
        const resumoDiv = document.getElementById(resumoId);
        if (!resumoDiv) return;
        
        if (skusValidos.length === 0) {
            resumoDiv.innerHTML = '<p>Configure pelo menos um grupo de medidas para ver o resumo</p>';
            return;
        }
        
        let resumoHtml = `
            <div class="resumo-item">
                <span>📊 Grupos de medidas:</span>
                <span><strong>${skusArray.length}</strong></span>
                    </div>
            <div class="resumo-item">
                <span>📦 Total de SKUs:</span>
                <span><strong>${totalSKUs}</strong></span>
                </div>
            <div class="resumo-item">
                <span>📋 Total de volumes físicos:</span>
                <span><strong>${totalVolumes}</strong></span>
                </div>
        `;
        
        // Detalhar cada grupo
        skusValidos.forEach((sku, index) => {
            const grupoIndex = skusArray.indexOf(sku) + 1;
            const nome = sku.nome || `Grupo ${grupoIndex}`;
            resumoHtml += `
                <div class="resumo-detalhado">
                    <div class="resumo-grupo-header">
                        🔸 ${nome}
                </div>
                    <div class="resumo-grupo-info">
                        <span>• Medidas: ${sku.largura}×${sku.altura}×${sku.comprimento}m</span><br>
                        <span>• SKUs: ${sku.quantidade_total} (${sku.total_volumes} grupos de ${sku.qtd_por_medida})</span><br>
                        <span>• Cubagem unitária: ${sku.cubagem_unitaria.toFixed(3)} m³</span><br>
                        <span>• Cubagem total: <strong>${sku.cubagem_total.toFixed(3)} m³</strong></span>
                    </div>
                </div>
            `;
        });
        
        // Total final
        resumoHtml += `
            <div class="resumo-item resumo-total">
                <span>🎯 <strong>CUBAGEM TOTAL FINAL:</strong></span>
                <span class="valor-destaque">${totalCubagem.toFixed(3)} m³</span>
            </div>
        `;
        
        resumoDiv.innerHTML = resumoHtml;
    }

    window.aplicarCubagemCalculada = function() {
        console.log('Aplicando cubagem calculada para frete fracionado');
        aplicarCubagemGenerico(window.skusDataFracionado, 'volume', 'comprimento', 'largura', 'altura');
        fecharCalculadoraAvancada();
    }

    window.aplicarCubagemCalculadaAll = function() {
        console.log('Aplicando cubagem calculada para All In');
        aplicarCubagemGenerico(window.skusDataAll, 'volume_all', 'comprimento_all', 'largura_all', 'altura_all');
        fecharCalculadoraAvancadaAll();
    }

    window.aplicarCubagemCalculadaDedicado = function() {
        console.log('Aplicando cubagem calculada para frete dedicado');
        aplicarCubagemGenerico(window.skusDataDedicado, 'volume_dedicado', 'comprimento_dedicado', 'largura_dedicado', 'altura_dedicado');
        fecharCalculadoraAvancadaDedicado();
    }

    function aplicarCubagemGenerico(skusArray, volumeFieldId, compFieldId, largFieldId, altFieldId) {
        const totalCubagem = skusArray.reduce((sum, sku) => sum + sku.cubagem_total, 0);
        
        if (totalCubagem <= 0) {
            alert('Configure pelo menos um SKU com medidas válidas antes de aplicar!');
            return;
        }
        
        // Aplicar no campo principal
        const volumeField = document.getElementById(volumeFieldId);
        if (volumeField) {
            volumeField.value = totalCubagem.toFixed(4);
        }
        
        // Limpar campos individuais
        const campos = [compFieldId, largFieldId, altFieldId];
        campos.forEach(campoId => {
            const campo = document.getElementById(campoId);
            if (campo) {
                campo.value = '';
            }
        });
        
        // Feedback visual
        if (volumeField) {
            volumeField.style.backgroundColor = '#e8f5e8';
            volumeField.style.borderColor = '#28a745';
            
            setTimeout(() => {
                volumeField.style.backgroundColor = '';
                volumeField.style.borderColor = '';
            }, 1000);
        }
        
        console.log(`Cubagem aplicada: ${totalCubagem.toFixed(4)} m³`);
    }

    // ... existing code ...

    // Funções auxiliares para controle de detalhes técnicos
    window.toggleDetails = function(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.style.display = element.style.display === 'none' ? 'block' : 'none';
        }
    };

    window.toggleTechnicalSections = function() {
        const sections = document.getElementById('technicalSections');
        const button = document.getElementById('toggleTechnicalSections');
        if (sections && button) {
            if (sections.style.display === 'none' || sections.style.display === '') {
                sections.style.display = 'block';
                button.innerHTML = '🔙 Ocultar Informações Técnicas';
                button.style.background = '#6c757d';
            } else {
                sections.style.display = 'none';
                button.innerHTML = '📊 Mostrar Informações Técnicas';
                button.style.background = '#17a2b8';
            }
        }
    };

    // Funções de exportação
    async function exportarPDF(dados) {
        try {
            const response = await fetch('/gerar-pdf', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(dados)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Criar um link temporário para download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `relatorio_frete_${new Date().toISOString().slice(0,10)}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

        } catch (error) {
            console.error('Erro ao exportar PDF:', error);
            showError('Erro ao gerar PDF. Por favor, tente novamente.');
        }
    }

    async function exportarExcel(dados) {
        try {
            const response = await fetch('/exportar-excel', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(dados)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Criar um link temporário para download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `dados_frete_${new Date().toISOString().slice(0,10)}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

        } catch (error) {
            console.error('Erro ao exportar Excel:', error);
            showError('Erro ao gerar Excel. Por favor, tente novamente.');
        }
    }

    // 🔧 FUNÇÃO PARA EXIBIR MENSAGEM FLUTUANTE - Não há opções
    function showNoOptionsMessage(message) {
        // Remover mensagens existentes
        const existingMessage = document.querySelector('.no-options-message');
        const existingOverlay = document.querySelector('.overlay');
        if (existingMessage) existingMessage.remove();
        if (existingOverlay) existingOverlay.remove();

        // Criar overlay
        const overlay = document.createElement('div');
        overlay.className = 'overlay';
        document.body.appendChild(overlay);

        // Criar mensagem
        const messageDiv = document.createElement('div');
        messageDiv.className = 'no-options-message';
        messageDiv.innerHTML = `
            <span class="icon">🚫</span>
            <div class="message">${message}</div>
            <button class="close-btn" onclick="closeNoOptionsMessage()">Entendi</button>
        `;
        document.body.appendChild(messageDiv);

        // Fechar ao clicar no overlay
        overlay.addEventListener('click', closeNoOptionsMessage);

        // Auto-fechar após 8 segundos
        setTimeout(() => {
            closeNoOptionsMessage();
        }, 8000);
    }

    // 🔧 FUNÇÃO PARA FECHAR MENSAGEM FLUTUANTE
    function closeNoOptionsMessage() {
        const message = document.querySelector('.no-options-message');
        const overlay = document.querySelector('.overlay');
        if (message) {
            message.style.animation = 'slideInDown 0.3s ease-out reverse';
            setTimeout(() => message.remove(), 300);
        }
        if (overlay) {
            overlay.style.animation = 'fadeIn 0.3s ease-out reverse';
            setTimeout(() => overlay.remove(), 300);
        }
    }

    // 🔧 EXPORTAÇÃO DA FUNÇÃO PARA USO GLOBAL
    window.showNoOptionsMessage = showNoOptionsMessage;
    window.closeNoOptionsMessage = closeNoOptionsMessage;

    function exibirResultadoDedicadoEspecifico(data, container) {
        console.log('[DEDICADO ESPECÍFICO] Iniciando exibição específica');
        console.log('[DEDICADO ESPECÍFICO] Container:', container);
        console.log('[DEDICADO ESPECÍFICO] Dados:', data);
        
        // Armazenar dados globalmente
        dadosFreteDedicadoAll = data;
        
        // Obter dados do formulário para informações da rota
        const origem = document.getElementById('uf_origem')?.value + '/' + document.getElementById('municipio_origem')?.value;
        const destino = document.getElementById('uf_destino')?.value + '/' + document.getElementById('municipio_destino')?.value;
        const peso = parseFloat(document.getElementById('peso')?.value) || 0;
        const cubagem = parseFloat(document.getElementById('cubagem')?.value) || 0;
        
        // Criar layout específico para a aba Frete Dedicado (SEM RANKING)
        let html = `
            <div class="resultados-dedicado-especifico" style="margin-top: 20px;">
                <div class="card">
                    <h3><i class="fa-solid fa-truck"></i> Resultados - Frete Dedicado</h3>
                    
                    <!-- Informações da Rota -->
                    <div class="info-rota" style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                        <h4><i class="fa-solid fa-route"></i> Informações da Rota</h4>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px;">
                            <div><strong>Origem:</strong> ${origem || 'N/A'}</div>
                            <div><strong>Destino:</strong> ${destino || 'N/A'}</div>
                            <div><strong>Distância:</strong> ${data.distancia ? `${data.distancia.toLocaleString('pt-BR')} km` : 'N/A'}</div>
                            <div><strong>Peso:</strong> ${peso ? `${peso.toLocaleString('pt-BR')} kg` : 'N/A'}</div>
                            <div><strong>Cubagem:</strong> ${cubagem ? `${cubagem.toLocaleString('pt-BR')} m³` : 'N/A'}</div>
                        </div>
                    </div>
                    
                    <!-- Veículos Disponíveis (SEM RANKING) -->
                    <div class="veiculos-section" style="margin-bottom: 30px;">
                        <h4><i class="fa-solid fa-truck"></i> Veículos Disponíveis</h4>
                        <p style="color: #6c757d; margin-bottom: 15px;">Clique em um veículo para ver detalhes específicos</p>
                        
                        <div class="veiculos-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px;">
        `;
        
        // Listar veículos (sem ranking)
        Object.entries(data.custos).forEach(([veiculo, valor]) => {
            const icone = veiculo.includes('VUC') ? '🚐' : 
                         veiculo.includes('3/4') ? '🚚' : 
                         veiculo.includes('TOCO') ? '🚛' : 
                         veiculo.includes('TRUCK') ? '🚛' : 
                         veiculo.includes('CARRETA') ? '🚛' : '🚚';
            
            const capacidade = obterCapacidadeVeiculo(veiculo);
            const pesoOk = peso <= capacidade.peso_max;
            const volumeOk = cubagem <= capacidade.volume_max;
            const capacidadeOk = pesoOk && volumeOk;
            
            html += `
                <div class="veiculo-card ${!capacidadeOk && peso > 0 ? 'capacidade-excedida' : ''}" 
                     onclick="selecionarVeiculoDedicadoEspecifico('${veiculo}', ${valor})" 
                     style="cursor: pointer; background: white; border: 2px solid #e3e8ee; border-radius: 12px; padding: 15px; transition: all 0.3s ease;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 1.5rem;">${icone}</span>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 1.3rem; font-weight: bold; color: #0a6ed1;">R$ ${valor.toFixed(2)}</div>
                        </div>
                    </div>
                    <div style="font-weight: 600; margin-bottom: 8px;">${veiculo}</div>
                    <div style="font-size: 0.9rem; color: #6c757d;">
                        <div class="${!pesoOk && peso > 0 ? 'capacidade-insuficiente' : ''}">
                            ⚖️ ${capacidade.peso_max.toLocaleString('pt-BR')} kg
                        </div>
                        <div class="${!volumeOk && cubagem > 0 ? 'capacidade-insuficiente' : ''}">
                            📦 ${capacidade.volume_max.toLocaleString('pt-BR')} m³
                        </div>
                    </div>
                    ${!capacidadeOk && peso > 0 ? '<div class="aviso-capacidade" style="color: #dc3545; font-size: 0.8rem; margin-top: 5px;">⚠️ Capacidade excedida</div>' : ''}
                </div>
            `;
        });
        
        html += `
                        </div>
                    </div>
                    
                    <!-- Detalhes do Veículo Selecionado -->
                    <div id="detalhes-veiculo-especifico" class="detalhes-veiculo-especifico" style="margin-top: 20px; padding: 20px; background: #f8f9fa; border-radius: 8px; display: none;">
                        <h4><i class="fa-solid fa-info-circle"></i> Detalhes do Veículo Selecionado</h4>
                        <div id="detalhes-content-especifico"></div>
                    </div>
                    
                    <!-- Ações -->
                    <div class="acoes-section" style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e3e8ee;">
                        <h4><i class="fa-solid fa-tools"></i> Ações</h4>
                        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                            <button onclick="exportarCotacaoDedicadoEspecifico()" class="btn-secondary" style="padding: 10px 20px;">
                                <i class="fa-solid fa-download"></i> Exportar Cotação
                            </button>
                            <button onclick="limparResultadosDedicado()" class="btn-secondary" style="padding: 10px 20px;">
                                <i class="fa-solid fa-trash"></i> Limpar Resultados
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        container.innerHTML = html;
        console.log('[DEDICADO ESPECÍFICO] Layout específico criado com sucesso');
    }

    // Funções auxiliares para o layout específico
    function selecionarVeiculoDedicadoEspecifico(tipo, valor) {
        console.log('[DEDICADO ESPECÍFICO] Veículo selecionado:', tipo, 'valor:', valor);
        
        // Remover seleção anterior
        document.querySelectorAll('.veiculo-card').forEach(card => {
            card.style.border = '2px solid #e3e8ee';
            card.style.transform = 'scale(1)';
        });
        
        // Destacar o veículo selecionado
        event.target.closest('.veiculo-card').style.border = '2px solid #0a6ed1';
        event.target.closest('.veiculo-card').style.transform = 'scale(1.02)';
        
        // Exibir detalhes do veículo
        const detalhesContainer = document.getElementById('detalhes-veiculo-especifico');
        const detalhesContent = document.getElementById('detalhes-content-especifico');
        
        if (detalhesContainer && detalhesContent) {
            detalhesContainer.style.display = 'block';
            
            const capacidade = obterCapacidadeVeiculo(tipo);
            const vantagens = getVehicleAdvantages(tipo);
            
            detalhesContent.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px;">
                    <div class="detalhe-card" style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #e3e8ee;">
                        <h5><i class="fa-solid fa-truck"></i> Informações do Veículo</h5>
                        <p><strong>Tipo:</strong> ${tipo}</p>
                        <p><strong>Valor:</strong> R$ ${valor.toFixed(2)}</p>
                        <p><strong>Capacidade Peso:</strong> ${capacidade.peso_max.toLocaleString('pt-BR')} kg</p>
                        <p><strong>Capacidade Volume:</strong> ${capacidade.volume_max.toLocaleString('pt-BR')} m³</p>
                    </div>
                    
                    <div class="detalhe-card" style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #e3e8ee;">
                        <h5><i class="fa-solid fa-star"></i> Vantagens</h5>
                        <ul style="margin: 0; padding-left: 20px;">
                            ${vantagens.map(vantagem => `<li>${vantagem}</li>`).join('')}
                        </ul>
                    </div>
                    
                    <div class="detalhe-card" style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #e3e8ee;">
                        <h5><i class="fa-solid fa-calculator"></i> Análise de Custos</h5>
                        <p><strong>Custo por km:</strong> R$ ${(valor / (dadosFreteDedicadoAll.distancia || 1)).toFixed(2)}</p>
                        <p><strong>Eficiência:</strong> ${((capacidade.peso_max / valor) * 100).toFixed(1)} kg/R$</p>
                    </div>
                </div>
                
                <div style="margin-top: 20px; text-align: center;">
                    <button onclick="exportarCotacaoDedicadoEspecifico('${tipo}', ${valor})" class="btn-primary" style="margin-right: 10px;">
                        <i class="fa-solid fa-download"></i> Exportar Cotação
                    </button>
                    <button onclick="fecharDetalhesDedicado()" class="btn-secondary">
                        <i class="fa-solid fa-times"></i> Fechar
                    </button>
                </div>
            `;
        }
    }

    function exportarCotacaoDedicadoEspecifico(tipo, valor) {
        console.log('[DEDICADO ESPECÍFICO] Exportando cotação:', tipo, valor);
        
        const dados = {
            tipo: 'Frete Dedicado',
            veiculo: tipo,
            valor: valor,
            origem: dadosFreteDedicadoAll.origem,
            destino: dadosFreteDedicadoAll.destino,
            distancia: dadosFreteDedicadoAll.distancia,
            peso: dadosFreteDedicadoAll.peso,
            data: new Date().toLocaleDateString('pt-BR'),
            hora: new Date().toLocaleTimeString('pt-BR')
        };
        
        // Criar arquivo JSON para download
        const blob = new Blob([JSON.stringify(dados, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cotacao_dedicado_${tipo.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        alert('Cotação exportada com sucesso!');
    }

    function limparResultadosDedicado() {
        console.log('[DEDICADO ESPECÍFICO] Limpando resultados');
        
        const container = document.getElementById('resultados-dedicado');
        if (container) {
            container.innerHTML = '';
        }
        
        // Limpar também os containers da aba All In se existirem
        const containerAllIn = document.getElementById('resultados-dedicado-all-in');
        if (containerAllIn) {
            containerAllIn.innerHTML = '';
        }
        
        // Limpar dados globais
        dadosFreteDedicadoAll = null;
        
        console.log('[DEDICADO ESPECÍFICO] Resultados limpos');
    }

    function fecharDetalhesDedicado() {
        const detalhesContainer = document.getElementById('detalhes-veiculo-especifico');
        if (detalhesContainer) {
            detalhesContainer.style.display = 'none';
        }
        
        // Remover destaque dos veículos
        document.querySelectorAll('.veiculo-card').forEach(card => {
            card.style.border = '2px solid #e3e8ee';
            card.style.transform = 'scale(1)';
        });
    }

    // Expor funções globalmente
    window.selecionarVeiculoDedicadoEspecifico = selecionarVeiculoDedicadoEspecifico;
    window.exportarCotacaoDedicadoEspecifico = exportarCotacaoDedicadoEspecifico;
    window.limparResultadosDedicado = limparResultadosDedicado;
    window.fecharDetalhesDedicado = fecharDetalhesDedicado;

    // Variáveis globais para múltiplas bases
    let basesSelecionadas = [];
    let todasBases = [];

    // Carregar bases disponíveis ao inicializar
    carregarBasesDisponiveis();

    async function carregarBasesDisponiveis() {
        try {
            const response = await fetch('/api/bases-disponiveis');
            const data = await response.json();
            
            if (data.bases) {
                todasBases = data.bases;
                console.log('[BASES] Bases carregadas:', todasBases.length);
            }
        } catch (error) {
            console.error('[BASES] Erro ao carregar bases:', error);
        }
    }

    function abrirModalBases() {
        const modal = document.getElementById('modal-bases');
        const grid = document.getElementById('bases-grid');
        
        if (!modal || !grid) {
            console.error('[BASES] Modal ou grid não encontrado');
            return;
        }
        
        // Limpar grid
        grid.innerHTML = '';
        
        // Adicionar bases ao grid
        todasBases.forEach(base => {
            const baseItem = document.createElement('div');
            baseItem.className = 'base-item';
            baseItem.onclick = () => toggleBaseSelecao(base);
            
            baseItem.innerHTML = `
                <div class="base-codigo">${base.codigo}</div>
                <div class="base-nome">${base.nome}</div>
                <div class="base-regiao">${base.regiao}</div>
            `;
            
            grid.appendChild(baseItem);
        });
        
        // Atualizar lista de bases selecionadas
        atualizarListaBasesSelecionadas();
        
        modal.style.display = 'block';
    }

    function fecharModalBases() {
        const modal = document.getElementById('modal-bases');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    function toggleBaseSelecao(base) {
        // Permitir apenas uma base selecionada
        basesSelecionadas = [base];
        atualizarListaBasesSelecionadas();
        atualizarGridBases();
    }

    function atualizarListaBasesSelecionadas() {
        const lista = document.getElementById('bases-selecionadas-lista');
        if (!lista) return;
        
        lista.innerHTML = '';
        
        basesSelecionadas.forEach((base, index) => {
            const baseItem = document.createElement('span');
            baseItem.className = 'base-selecionada';
            baseItem.innerHTML = `
                ${base.codigo}
                <span class="remove" onclick="removerBase(${index})">&times;</span>
            `;
            lista.appendChild(baseItem);
        });
    }

    function atualizarGridBases() {
        const items = document.querySelectorAll('.base-item');
        
        items.forEach(item => {
            const codigo = item.querySelector('.base-codigo').textContent;
            const isSelected = basesSelecionadas.some(b => b.codigo === codigo);
            
            if (isSelected) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        });
    }

    function removerBase(index) {
        basesSelecionadas.splice(index, 1);
        atualizarListaBasesSelecionadas();
        atualizarGridBases();
    }

    function aplicarBasesSelecionadas() {
        const input = document.getElementById('bases_intermediarias');
        if (input) {
            const codigos = basesSelecionadas.map(b => b.codigo).join(', ');
            input.value = codigos;
        }
        fecharModalBases();
    }

    async function calcularFreteFracionadoMultiplasBases() {
        const form = document.getElementById('form-fracionado');
        if (!form) {
            showError('Formulário não encontrado', 'fracionado-resultado');
            return;
        }
        
        // Obter dados do formulário
        const formData = {
            uf_origem: document.getElementById('uf_origem_frac').value,
            municipio_origem: document.getElementById('municipio_origem_frac').value,
            uf_destino: document.getElementById('uf_destino_frac').value,
            municipio_destino: document.getElementById('municipio_destino_frac').value,
            peso: parseFloat(document.getElementById('peso_frac').value),
            cubagem: parseFloat(document.getElementById('cubagem_frac').value),
            valor_nf: parseFloat(document.getElementById('valor_nf_frac').value) || null
        };
        
        // Obter bases do input ou das selecionadas
        let basesInput = document.getElementById('bases_intermediarias').value;
        let basesArray = [];
        
        if (basesInput) {
            basesArray = basesInput.split(',').map(b => b.trim().toUpperCase()).filter(b => b);
        } else if (basesSelecionadas.length > 0) {
            basesArray = basesSelecionadas.map(b => b.codigo);
        }
        
        formData.bases_intermediarias = basesArray;
        
        console.log('[MULTIPLAS_BASES] Dados do formulário:', formData);
        
        if (!formData.uf_origem || !formData.municipio_origem || !formData.uf_destino || !formData.municipio_destino) {
            showError('Por favor, preencha todos os campos obrigatórios', 'fracionado-resultado');
            return;
        }
        
        if (basesArray.length !== 1) {
            showError('É necessário selecionar exatamente 1 base intermediária', 'fracionado-resultado');
            return;
        }
        
        const loading = document.getElementById('loading-fracionado-multiplas-bases');
        if (loading) loading.style.display = 'block';
        
        try {
            const response = await fetch('/calcular_frete_fracionado_multiplas_bases', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });
            
            const result = await response.json();
            
            if (result.error) {
                showError(result.error, 'fracionado-resultado');
                if (result.sem_opcoes) {
                    showNoOptionsMessage(result.error);
                }
            } else {
                exibirResultadoFracionadoMultiplasBases(result);
            }
        } catch (error) {
            console.error('Erro ao calcular frete fracionado com múltiplas bases:', error);
            showError('Erro ao calcular frete fracionado com múltiplas bases. Tente novamente.', 'fracionado-resultado');
        } finally {
            if (loading) loading.style.display = 'none';
        }
    }

    function exibirResultadoFracionadoMultiplasBases(data) {
        const container = document.getElementById('fracionado-resultado');
        if (!container) return;
        
        let html = `
            <div class="card" style="margin-top: 20px;">
                <h3><i class="fa-solid fa-route"></i> Frete Fracionado com Múltiplas Bases</h3>
                
                <div class="resumo-section">
                    <h4><i class="fa-solid fa-map-marker-alt"></i> Rota Completa</h4>
                    <div class="rota-completa" style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 10px 0;">
                        <span class="rota-item origem" style="background: #28a745; color: white; padding: 5px 10px; border-radius: 15px;">${data.origem}</span>
                        ${data.bases_intermediarias.map(base => `<span class="rota-item base" style="background: #0a6ed1; color: white; padding: 5px 10px; border-radius: 15px;">${base}</span>`).join('')}
                        <span class="rota-item destino" style="background: #dc3545; color: white; padding: 5px 10px; border-radius: 15px;">${data.destino}</span>
                    </div>
                </div>
                
                <div class="resumo-section">
                    <h4><i class="fa-solid fa-calculator"></i> Resumo Financeiro</h4>
                    <div class="resumo-grid">
                        <div class="resumo-card">
                            <div class="resumo-card-header">
                                <i class="fa-solid fa-dollar-sign"></i> Custo Total
                            </div>
                            <div class="resumo-card-body">
                                <div class="valor-principal" style="font-size: 1.5rem; font-weight: bold; color: #28a745;">R$ ${data.custo_total.toFixed(2)}</div>
                                <div class="detalhes">
                                    <div>Prazo: ${data.prazo_total} dias</div>
                                    <div>Peso Cubado: ${data.peso_cubado.toFixed(2)} kg</div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="resumo-card">
                            <div class="resumo-card-header">
                                <i class="fa-solid fa-shield-alt"></i> Custos Adicionais
                            </div>
                            <div class="resumo-card-body">
                                <div>GRIS: R$ ${data.gris.toFixed(2)}</div>
                                <div>Seguro: R$ ${data.seguro.toFixed(2)}</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="resumo-section">
                    <h4><i class="fa-solid fa-truck"></i> Detalhamento por Trecho</h4>
                    <div class="trechos-container">
        `;
        
        data.trechos.forEach((trecho, index) => {
            html += `
                <div class="trecho-item" style="background: #f8f9fa; border-radius: 8px; padding: 15px; margin: 10px 0; border-left: 4px solid #0a6ed1;">
                    <div class="trecho-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <span class="trecho-numero" style="background: #0a6ed1; color: white; padding: 5px 10px; border-radius: 15px; font-weight: bold;">${index + 1}</span>
                        <span class="trecho-rota" style="font-weight: bold; color: #495057;">${trecho.trecho}</span>
                        <span class="trecho-custo" style="background: #28a745; color: white; padding: 5px 10px; border-radius: 15px; font-weight: bold;">R$ ${trecho.custo.toFixed(2)}</span>
                    </div>
                    <div class="trecho-detalhes" style="color: #6c757d;">
                        <div><strong>Fornecedor:</strong> ${trecho.fornecedor}</div>
                        <div><strong>Tipo:</strong> ${trecho.tipo_servico || 'FRACIONADO'}</div>
                        <div><strong>Prazo:</strong> ${trecho.prazo} dias</div>
                    </div>
                </div>
            `;
        });
        
        html += `
                    </div>
                </div>
                
                <div class="resumo-section">
                    <h4><i class="fa-solid fa-info-circle"></i> Informações Adicionais</h4>
                    <div class="info-grid" style="background: #f8f9fa; border-radius: 8px; padding: 15px;">
                        <div><strong>Fornecedores Utilizados:</strong> ${data.fornecedores_utilizados.join(', ')}</div>
                        <div><strong>Tempo de Cálculo:</strong> ${data.tempo_calculo.toFixed(2)}s</div>
                    </div>
                </div>
            </div>
        `;
        
        container.innerHTML = html;
    }

    // Expor funções de múltiplas bases globalmente
    window.abrirModalBases = abrirModalBases;
    window.fecharModalBases = fecharModalBases;
    window.toggleBaseSelecao = toggleBaseSelecao;
    window.removerBase = removerBase;
    window.aplicarBasesSelecionadas = aplicarBasesSelecionadas;
    window.calcularFreteFracionadoMultiplasBases = calcularFreteFracionadoMultiplasBases;
});