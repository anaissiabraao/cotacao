// Funcoes para manipulacao dos formularios e botoes
// Padronizacao completa de todos os fluxos: dedicado, aereo, fracionado, exportacao
// Versao corrigida com melhorias de funcionalidade e depuracao

document.addEventListener('DOMContentLoaded', function() {
    console.log('=== SISTEMA DE COTACAO INICIADO ===');
    
    // Carregar estados iniciais para todos os formularios
    carregarEstados('uf_origem_all');
    carregarEstados('uf_destino_all');
    carregarEstados('uf_origem_frac');
    carregarEstados('uf_destino_frac');
    carregarEstados('uf_origem');
    carregarEstados('uf_destino');
    carregarEstados('uf_origem_aereo');
    carregarEstados('uf_destino_aereo');
    
    // Aguardar um pouco para garantir que tudo esteja carregado
    setTimeout(() => {
        configurarEventoMudancaEstado('uf_origem_all');
        configurarEventoMudancaEstado('uf_destino_all');
        configurarEventoMudancaEstado('uf_origem_frac');
        configurarEventoMudancaEstado('uf_destino_frac');
        configurarEventoMudancaEstado('uf_origem');
        configurarEventoMudancaEstado('uf_destino');
        configurarEventoMudancaEstado('uf_origem_aereo');
        configurarEventoMudancaEstado('uf_destino_aereo');
        console.log('[DEBUG] Eventos de mudanca de estado configurados');
    }, 1500);

    // Configurar eventos de mudanca de estado para carregar municipios
    function configurarEventoMudancaEstado(inputId) {
        const input = document.getElementById(inputId);
        if (!input) return;
        
        input.addEventListener('change', function() {
            processarMudancaEstado(this.value, this.id);
        });
        
        input.addEventListener('input', function() {
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
        
        if (municipioId && uf) {
            const municipioInput = document.getElementById(municipioId);
            if (municipioInput) {
                municipioInput.value = '';
                municipioInput.placeholder = 'Carregando municipios...';
            }
            carregarMunicipios(uf, municipioId);
        }
    }

    // Configurar formularios
    setupFormularios();
    
    // Carregar historico inicial
    carregarHistorico();

    async function carregarEstados(inputId) {
        const input = document.getElementById(inputId);
        const datalistId = `datalist_${inputId}`;
        let datalist = document.getElementById(datalistId);
        
        if (!input) return;

        if (!datalist) {
            datalist = document.createElement('datalist');
            datalist.id = datalistId;
            input.parentNode.insertBefore(datalist, input.nextSibling);
        }
        
        try {
            const response = await fetch('/estados');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const estados = await response.json();
            
            datalist.innerHTML = '';
            estados.forEach(estado => {
                const option = document.createElement('option');
                option.value = estado.sigla;
                option.textContent = estado.nome;
                datalist.appendChild(option);
            });
            
            input.placeholder = `Digite para buscar entre ${estados.length} estados...`;
            
        } catch (error) {
            console.error(`[ERROR] Erro ao carregar estados para ${inputId}:`, error);
            input.placeholder = 'Erro ao carregar - Digite manualmente';
        }
    }

    async function carregarMunicipios(uf, inputId) {
        const input = document.getElementById(inputId);
        const datalistId = `datalist_${inputId}`;
        let datalist = document.getElementById(datalistId);
        
        if (!input) return;
        
        if (!datalist) {
            datalist = document.createElement('datalist');
            datalist.id = datalistId;
            input.parentNode.insertBefore(datalist, input.nextSibling);
        }
        
        try {
            const url = `/municipios/${encodeURIComponent(uf)}`;
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            if (!Array.isArray(data)) {
                throw new Error(`Resposta nao e um array valido: ${typeof data}`);
            }
            
            datalist.innerHTML = '';
            
            data.forEach((municipio, index) => {
                const option = document.createElement('option');
                option.value = municipio;
                option.textContent = municipio;
                datalist.appendChild(option);
            });
            
            input.value = '';
            input.placeholder = `Digite para buscar entre ${data.length} municipios...`;
            
        } catch (error) {
            console.error(`[ERROR] Erro ao carregar municipios para ${uf}:`, error);
            input.placeholder = 'Erro ao carregar - Digite manualmente';
        }
    }

    function setupFormularios() {
        // Configurar formulario All In
        const formAllIn = document.getElementById('form-all-in');
        if (formAllIn) {
            formAllIn.addEventListener('submit', async function(e) {
                e.preventDefault();
                await calcularAllIn();
            });
        }

        // Configurar formulario Frete Fracionado
        const formFracionado = document.getElementById('form-fracionado');
        if (formFracionado) {
            formFracionado.addEventListener('submit', async function(e) {
                e.preventDefault();
                await calcularFreteFragcionado();
            });
        }

        // Configurar formulario Dedicado
        const formDedicado = document.getElementById('form-dedicado');
        if (formDedicado) {
            formDedicado.addEventListener('submit', async function(e) {
                e.preventDefault();
                await calcularFreteDedicado();
            });
        }

        // Configurar formulario Aereo
        const formAereo = document.getElementById('form-aereo');
        if (formAereo) {
            formAereo.addEventListener('submit', async function(e) {
                e.preventDefault();
                await calcularFreteAereo();
            });
        }
    }

    async function calcularAllIn() {
        console.log('[ALL IN] Função calcularAllIn iniciada');
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
                throw new Error('Todos os campos de origem e destino sao obrigatorios');
            }

            // Calcular Frete Fracionado
            try {
                console.log('[ALL IN] Iniciando cálculo fracionado...');
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
                    exibirResultadoAllInFracionado({ erro: 'Erro ao calcular frete fracionado' });
                }
            } catch (error) {
                console.error('[ALL IN] Erro na requisicao de frete fracionado:', error);
                exibirResultadoAllInFracionado({ erro: `Erro: ${error.message}` });
            }

            // Calcular Frete Dedicado
            console.log('[ALL IN] Iniciando cálculo dedicado...');
            const dedicadoResponse = await fetch('/calcular', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            console.log('[ALL IN] Resposta dedicado status:', dedicadoResponse.status);
            
            if (dedicadoResponse.ok) {
                const dedicadoData = await dedicadoResponse.json();
                console.log('[ALL IN] Dados frete dedicado recebidos:', dedicadoData);
                console.log('[ALL IN] Chamando exibirResultadoAllInDedicado...');
                exibirResultadoAllInDedicado(dedicadoData);
            } else {
                console.error('[ALL IN] Erro na resposta do frete dedicado:', dedicadoResponse.status);
                const errorText = await dedicadoResponse.text();
                console.error('[ALL IN] Erro detalhado:', errorText);
            }

            // Calcular Frete Aereo
            console.log('[ALL IN] Iniciando cálculo aéreo...');
            const aereoResponse = await fetch('/calcular_aereo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (aereoResponse.ok) {
                const aereoData = await aereoResponse.json();
                console.log('[ALL IN] Dados frete aéreo recebidos:', aereoData);
                exibirResultadoAllInAereo(aereoData);
            }
                
        } catch (error) {
            console.error('[ALL IN] Erro:', error);
            showError(`Erro no calculo All In: ${error.message}`);
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

            console.log('[FRACIONADO] Dados do formulario:', formData);

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
                if (data.sem_opcoes || data.error.includes('Nao ha nenhuma opcao')) {
                    showNoOptionsMessage(data.error);
                    return;
                }
                throw new Error(data.error);
            }

            exibirResultadoFracionado(data);
                
            } catch (error) {
            console.error('[FRACIONADO] Erro:', error);
            showError(`Erro no calculo fracionado: ${error.message}`);
        } finally {
            if (loading) loading.style.display = 'none';
        }
    }

    async function calcularFreteDedicado() {
        const loading = document.getElementById('loading-dedicado');
        if (loading) loading.style.display = 'block';

        try {
            const formData = {
                uf_origem: document.getElementById('uf_origem').value,
                municipio_origem: document.getElementById('municipio_origem').value,
                uf_destino: document.getElementById('uf_destino').value,
                municipio_destino: document.getElementById('municipio_destino').value,
                peso: parseFloat(document.getElementById('peso').value) || 0,
                cubagem: parseFloat(document.getElementById('cubagem').value) || 0
            };

            if (!formData.uf_origem || !formData.municipio_origem || !formData.uf_destino || !formData.municipio_destino) {
                throw new Error('Origem e destino sao obrigatorios');
            }

            const response = await fetch('/calcular', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                throw new Error(`Erro HTTP: ${response.status}`);
            }

            const data = await response.json();
                
            if (data.error) {
                throw new Error(data.error);
            }

            exibirResultadoDedicado(data);

        } catch (error) {
            console.error('[DEDICADO] Erro:', error);
            showError(`Erro no calculo dedicado: ${error.message}`, 'resultados-dedicado-all-in');
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

            const response = await fetch('/calcular_aereo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

                if (!response.ok) {
                    throw new Error(`Erro HTTP: ${response.status}`);
                }

            const data = await response.json();
                
                if (data.error) {
                throw new Error(data.error);
            }

            exibirResultadoAereo(data);

        } catch (error) {
            console.error('[AEREO] Erro:', error);
            showError(`Erro no calculo aereo: ${error.message}`);
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
            exibirHistorico(historico);

        } catch (error) {
            console.error('[HISTORICO] Erro ao carregar:', error);
            const container = document.getElementById('listaHistorico');
            if (container) {
                container.innerHTML = `<div class="alert alert-danger">Erro ao carregar historico: ${error.message}</div>`;
            }
        }
    }

    // Funcoes de exibicao de resultados
        function exibirResultadoAllInFracionado(data) {
        const container = document.getElementById('resumo-fracionado-completo');
        if (!container) {
            console.error('[ALL IN FRAC] Container resumo-fracionado-completo nao encontrado');
            return;
        }
        
        console.log('[ALL IN FRAC] Dados recebidos:', data);
        
        if (data.sem_opcoes || (data.error && data.error.includes('Nao ha nenhuma opcao'))) {
            container.innerHTML = '<div class="no-results">Nenhuma opcao encontrada para esta rota.</div>';
            return;
        }
        
        const opcoes = data.opcoes || [];
        
        if (opcoes.length > 0) {
            const melhoresOpcoes = opcoes.slice(0, 3);
            
            let html = `
                <div style="background: #f8f9fa; padding: 20px; border-radius: 12px; border: 1px solid #dee2e6;">
                    <h4 style="color: #28a745; margin-bottom: 15px; display: flex; align-items: center;">
                        <i class="fa-solid fa-truck" style="margin-right: 8px;"></i> 
                        Melhores Opções de Frete Fracionado (${opcoes.length})
                    </h4>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">
            `;
            
            melhoresOpcoes.forEach((opcao, index) => {
                const ismelhor = opcao.eh_melhor_opcao || index === 0;
                const borderColor = ismelhor ? '#28a745' : '#dee2e6';
                const bgColor = ismelhor ? '#e8f5e9' : '#ffffff';
                const badge = ismelhor ? '<div style="background: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; margin-top: 8px; text-align: center;">⭐ Melhor Opção</div>' : '';
                        
                        html += `
                    <div style="background: ${bgColor}; border: 2px solid ${borderColor}; border-radius: 8px; padding: 15px; transition: transform 0.2s;">
                        <div style="text-align: center; margin-bottom: 12px;">
                            <h6 style="color: #495057; margin: 0; font-size: 1.1rem; font-weight: bold;">${opcao.fornecedor}</h6>
                            ${badge}
                                </div>
                        <div style="text-align: center; margin: 15px 0;">
                            <div style="font-size: 1.5rem; font-weight: bold; color: #28a745;">R$ ${opcao.total.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>
                                    </div>
                        <div style="font-size: 0.9rem; color: #6c757d; line-height: 1.4;">
                            <div><strong>Peso usado:</strong> ${opcao.peso_usado}</div>
                            <div><strong>Serviço:</strong> ${opcao.tipo_servico}</div>
                                    </div>
                        <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #dee2e6; font-size: 0.8rem; color: #6c757d;">
                            <div style="display: flex; justify-content: space-between;"><span>Base:</span><span>R$ ${opcao.custo_base.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span></div>
                            <div style="display: flex; justify-content: space-between;"><span>GRIS:</span><span>R$ ${opcao.gris.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span></div>
                            <div style="display: flex; justify-content: space-between;"><span>Pedágio:</span><span>R$ ${opcao.pedagio.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span></div>
                            <div style="display: flex; justify-content: space-between;"><span>Seguro:</span><span>R$ ${opcao.seguro.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span></div>
                                    </div>
                            </div>
                        `;
                    });
                        
                        html += `
                                </div>
                            </div>
                        `;
            container.innerHTML = html;
            } else {
            container.innerHTML = '<div class="alert alert-info">Nenhuma opcao de frete fracionado encontrada.</div>';
        }
        
        console.log('[ALL IN FRAC] Resultado exibido com sucesso');
    }

    function exibirResultadoFracionado(data) {
        const container = document.getElementById('fracionado-resultado');
        if (!container) {
            console.error('[FRACIONADO] Container fracionado-resultado nao encontrado');
            return;
        }

        console.log('[FRACIONADO] Dados recebidos:', data);
        
        if (data.ranking_fracionado) {
            console.log('[FRACIONADO] Usando novo formato de ranking');
            exibirRankingFracionado(data.ranking_fracionado, container);
            return;
        }

        // Formato atual do backend
        console.log('[FRACIONADO] Usando formato atual');
        exibirFormatoAtualFracionado(data, container);
    }

    function exibirFormatoAtualFracionado(data, container) {
        console.log('[FRACIONADO] Dados recebidos:', data);
        
        const opcoes = data.opcoes || [];
        
        if (data.sem_opcoes || opcoes.length === 0) {
            container.innerHTML = `
                <div class="no-results">
                    <h3>⚠️ Nenhuma opção encontrada</h3>
                    <p>${data.erro || 'Não há rotas disponíveis para esta origem e destino.'}</p>
                </div>
            `;
            return;
        }
        
        const origem = data.origem || 'N/A';
        const destino = data.destino || 'N/A';
        
        let html = `
            <div class="success">
                <h3><i class="fa-solid fa-boxes"></i> Cotação de Frete Fracionado Calculada</h3>
                
                <div class="info-rota-fracionado" style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p><strong>Rota:</strong> ${origem} → ${destino}</p>
                    <p><strong>Total de opções encontradas:</strong> ${opcoes.length}</p>
                                </div>
                
                <div class="opcoes-fracionado">
                    <h4><i class="fa-solid fa-truck"></i> Opções Disponíveis:</h4>
                    <div class="table-responsive">
                        <table class="table table-striped" style="width: 100%; border-collapse: collapse;">
                            <thead style="background: #f8f9fa;">
                                <tr>
                                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: left;">Fornecedor</th>
                                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: left;">Tipo Serviço</th>
                                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">Custo Base</th>
                                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">GRIS</th>
                                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">Pedágio</th>
                                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">Seguro</th>
                                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: right;">Total</th>
                                    <th style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">Peso Usado</th>
                                </tr>
                            </thead>
                            <tbody>
        `;
        
        opcoes.forEach((opcao, index) => {
            const ismelhor = opcao.eh_melhor_opcao;
            const rowStyle = ismelhor ? 'background: #d4edda; border-left: 4px solid #28a745;' : 'background: #ffffff;';
            const badge = ismelhor ? '<br><span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem;">Melhor Opção</span>' : '';
            
            html += `
                <tr style="${rowStyle}">
                    <td style="padding: 12px; border: 1px solid #dee2e6;">
                        <strong style="color: #495057;">${opcao.fornecedor}</strong>
                        ${badge}
                    </td>
                    <td style="padding: 12px; border: 1px solid #dee2e6; color: #6c757d;">${opcao.tipo_servico}</td>
                    <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-family: monospace;">R$ ${opcao.custo_base.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                    <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-family: monospace;">R$ ${opcao.gris.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                    <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-family: monospace;">R$ ${opcao.pedagio.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                    <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-family: monospace;">R$ ${opcao.seguro.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                    <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: bold; color: #28a745; font-size: 1.1rem; font-family: monospace;">R$ ${opcao.total.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                    <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center; font-weight: 600;">${opcao.peso_usado}</td>
                </tr>
                        `;
                    });
                
        html += `
                            </tbody>
                        </table>
                        </div>
                        </div>
                
                <div class="resumo-melhor-opcao" style="background: #e8f5e9; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #28a745;">
                    <h5 style="color: #28a745; margin-bottom: 10px;"><i class="fa-solid fa-star"></i> Melhor Opção:</h5>
                    <p style="margin: 0; font-size: 1.1rem;"><strong>${opcoes[0].fornecedor}</strong> - <span style="color: #28a745; font-weight: bold;">R$ ${opcoes[0].total.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span></p>
                        </div>
                    </div>
                `;
        
        container.innerHTML = html;
        console.log('[FRACIONADO] Resultado exibido com sucesso');
    }

    // Função para exibir ranking detalhado (layout original da primeira imagem)
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
                        💰 <strong>CUSTO TOTAL: R$ ${ranking.melhor_opcao ? ranking.melhor_opcao.total.toFixed(2) : '0.00'}</strong>
                    </div>
                    <div class="analise-item"><strong>Peso Cubado:</strong> ${ranking.peso_cubado} (${ranking.peso_usado_tipo})</div>
                    ${ranking.valor_nf ? `<div class="analise-item"><strong>Valor NF:</strong> R$ ${ranking.valor_nf.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>` : ''}
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
                            • <strong>Peso Cubado:</strong> ${ranking.peso_cubado} (${ranking.peso_usado_tipo})<br>
                        </div>
                    </div>
                </div>
        `;
        
        // Tabela de ranking com detalhes expandíveis
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

                html += `
                    <tr style="${rowStyle}">
                        <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; font-size: 1.1em;">${posicaoIcon}</td>
                        <td style="padding: 12px; border: 1px solid #dee2e6;">
                            <strong>${opcao.tipo_servico}</strong><br>
                            <small style="color: #6c757d;">${opcao.descricao}</small><br>
                            <small style="color: #007bff; font-weight: bold;">Fornecedor: ${opcao.fornecedor}</small>
                        </td>
                        <td style="padding: 12px; border: 1px solid #dee2e6; text-align: right; font-weight: bold; color: #28a745; font-size: 1.1em;">
                            R$ ${opcao.custo_total.toFixed(2)}
                        </td>
                        <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                            <strong>Peso Máximo:</strong> ${opcao.peso_maximo_agente || 'N/A'}<br>
                            <strong>Prazo:</strong> ${opcao.prazo || 'N/A'} dias
                        </td>
                        <td style="padding: 12px; border: 1px solid #dee2e6; text-align: center;">
                            <button class="btn btn-info btn-sm" onclick="toggleDetalhesOpcao(${index})" style="background: #17a2b8; border: none; color: white; padding: 6px 12px; border-radius: 4px; font-size: 0.8rem;">
                                <span id="btn-text-${index}">🔎 Ver Detalhes</span>
                            </button>
                        </td>
                    </tr>
                `;
                
                // Linha expansível com detalhes
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
                
                // Exibir informações dos agentes
                const detalhes = opcao.detalhes_expandidos || {};
                const agentes = detalhes.agentes_info || {};
                const rota_info = detalhes.rota_info || {};
                
                if (agentes.agente_coleta && agentes.agente_coleta !== 'N/A') {
                    html += `
                        <div onclick="exibirCustosAgente('coleta', ${index})" style="margin-bottom: 10px; padding: 8px; background: #e8f5e8; border-radius: 4px; cursor: pointer; transition: background 0.3s;" onmouseover="this.style.background='#d4ecda'" onmouseout="this.style.background='#e8f5e8'">
                            <strong>🚛 Agente de Coleta:</strong> ${agentes.agente_coleta}<br>
                            ${agentes.base_origem !== 'N/A' ? `<small>📍 Base: ${agentes.base_origem}</small>` : `<small>📍 Base: Base de Origem</small>`}
                            <br><small style="color: #007bff;">👆 Clique para ver custos específicos</small>
                        </div>
                    `;
                }
                
                if (agentes.transferencia && agentes.transferencia !== 'N/A') {
                    html += `
                        <div onclick="exibirCustosAgente('transferencia', ${index})" style="margin-bottom: 10px; padding: 8px; background: #e3f2fd; border-radius: 4px; cursor: pointer; transition: background 0.3s;" onmouseover="this.style.background='#bbdefb'" onmouseout="this.style.background='#e3f2fd'">
                            <strong>🚚 Transferência:</strong> ${agentes.transferencia}<br>
                            <small>🛣️ Rota: ${agentes.base_origem || 'Origem'} → ${agentes.base_destino || 'Destino'}</small>
                            <br><small style="color: #007bff;">👆 Clique para ver custos específicos</small>
                        </div>
                    `;
                }
                
                if (agentes.agente_entrega && agentes.agente_entrega !== 'N/A') {
                    html += `
                        <div onclick="exibirCustosAgente('entrega', ${index})" style="margin-bottom: 10px; padding: 8px; background: #fff3e0; border-radius: 4px; cursor: pointer; transition: background 0.3s;" onmouseover="this.style.background='#ffe0b2'" onmouseout="this.style.background='#fff3e0'">
                            <strong>🚛 Agente de Entrega:</strong> ${agentes.agente_entrega}<br>
                            ${agentes.base_destino !== 'N/A' ? `<small>📍 Base: ${agentes.base_destino}</small>` : `<small>📍 Base: Base de Destino</small>`}
                            <br><small style="color: #007bff;">👆 Clique para ver custos específicos</small>
                        </div>
                    `;
                }
                
                html += `
                                        <div style="margin-top: 10px; padding: 8px; background: #f0f0f0; border-radius: 4px;">
                                            <strong>⚖️ Peso Utilizado:</strong> 
                                            ${rota_info.peso_cubado ? rota_info.peso_cubado + ' kg' : 'N/A'}
                                            <br>
                                            <small>
                                                Tipo: ${rota_info.tipo_peso_usado || 'Desconhecido'}
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
                                            <p style="color: #6c757d; text-align: center; font-style: italic;">
                                                Clique em um agente ao lado para ver custos específicos
                                            </p>
                                                </div>
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
        
        // Armazenar ranking para acesso global
        window.ultimoRankingFracionado = ranking;
        
        console.log('[FRACIONADO] Ranking exibido no formato detalhado com sucesso');
    }

    // Função para expandir/colapsar detalhes de cada opção
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

    // Função para exibir custos específicos de cada agente
    window.exibirCustosAgente = function(tipoAgente, opcaoIndex) {
        console.log(`[AGENTE-CLICK] Clicado em ${tipoAgente} da opção ${opcaoIndex}`);
        
        const rankingData = window.ultimoRankingFracionado;
        if (!rankingData || !rankingData.ranking_opcoes || !rankingData.ranking_opcoes[opcaoIndex]) {
            console.error('[AGENTE-CLICK] Dados da opção não encontrados');
            return;
        }
        
        const opcao = rankingData.ranking_opcoes[opcaoIndex];
        const detalhes = opcao.detalhes_expandidos || {};
        const agentes = detalhes.agentes_info || {};
        const rota_info = detalhes.rota_info || {};
        const custos = detalhes.custos_detalhados || {};
        
        let agenteInfo = {};
        let custoEspecifico = 0;
        let nomeAgente = '';
        
        switch(tipoAgente) {
            case 'coleta':
                nomeAgente = agentes.agente_coleta || 'N/A';
                agenteInfo = {
                    tipo: 'Agente de Coleta',
                    fornecedor: agentes.agente_coleta,
                    base: agentes.base_origem,
                    funcao: 'Coleta na origem e transporte até a base'
                };
                custoEspecifico = custos.custo_coleta || 0;
                break;
            case 'transferencia':
                nomeAgente = agentes.transferencia || 'N/A';
                agenteInfo = {
                    tipo: 'Transferência',
                    fornecedor: agentes.transferencia,
                    rota: `${agentes.base_origem} → ${agentes.base_destino}`,
                    funcao: 'Transporte entre bases'
                };
                custoEspecifico = custos.custo_transferencia || 0;
                break;
            case 'entrega':
                nomeAgente = agentes.agente_entrega || 'N/A';
                agenteInfo = {
                    tipo: 'Agente de Entrega',
                    fornecedor: agentes.agente_entrega,
                    base: agentes.base_destino,
                    funcao: 'Coleta na base e entrega no destino'
                };
                custoEspecifico = custos.custo_entrega || 0;
                break;
        }

        const custosHtml = `
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
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; margin-top: 8px; background: #d4edda; border-radius: 4px; font-weight: bold;">
                        <span>💰 Custo Estimado:</span>
                        <span style="color: #28a745;">R$ ${custoEspecifico.toFixed(2)}</span>
                    </div>
                </div>
                <div style="margin-top: 10px; padding: 8px; background: #f8f9fa; border-radius: 4px; font-size: 0.8rem; color: #6c757d;">
                    <strong>💡 Informação:</strong> Este é o custo estimado específico deste ${agenteInfo.tipo.toLowerCase()}. 
                    O valor total da cotação inclui todos os serviços da rota.
                </div>
            </div>
        `;
        
        // Atualizar o container de custos
        const custosContainer = document.getElementById(`custos-container-${opcaoIndex}`);
        if (custosContainer) {
            custosContainer.innerHTML = custosHtml;
        }
        
        console.log('[AGENTE-CLICK] Custos específicos exibidos:', agenteInfo);
    }

    // Função para toggle de detalhes
    window.toggleDetails = function(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.style.display = element.style.display === 'none' ? 'block' : 'none';
        }
    };

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
                    const icone = veiculo.includes('VAN') ? '🚐' : 
                                 veiculo.includes('3/4') ? '🚛' : 
                                 veiculo.includes('TOCO') ? '🚛' : 
                                 veiculo.includes('TRUCK') ? '🚛' : 
                                 veiculo.includes('CARRETA') ? '🚛' : 
                                 veiculo.includes('FIORINO') ? '🚛' : '🚛';
                    
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
                <h4>💰 Custos Operacionais</h4>
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
            let htmlCustos = `<h4>💰 Custos Operacionais - ${veiculo}</h4>`;
            
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
                htmlCustos += `<div class="analise-item">💰 Custo combustível: R$ ${consumoVeiculo.custo.toFixed(2)}</div>`;
                
                // Pedágio
                if (dadosFreteDedicadoAll.analise.pedagio_real || dadosFreteDedicadoAll.analise.pedagio_estimado) {
                    const pedagio = dadosFreteDedicadoAll.analise.pedagio_real || dadosFreteDedicadoAll.analise.pedagio_estimado;
                    const pedagioVeiculo = calcularPedagioVeiculo(veiculo, pedagio);
                    htmlCustos += `<div class="analise-item">🛣️ Pedágio: R$ ${pedagioVeiculo.toFixed(2)}</div>`;
                }
                
                htmlCustos += '</div>';
            }
            
            containerCustos.innerHTML = htmlCustos;
        }
        
        // Atualizar Margens Comerciais
        const containerMargens = document.getElementById('resumo-dedicado-margens');
        if (containerMargens) {
            let htmlMargens = `<h4>📈 Margens Comerciais - ${veiculo}</h4>`;
            
            if (dadosFreteDedicadoAll.custos && dadosFreteDedicadoAll.custos[veiculo]) {
                const custoTotal = dadosFreteDedicadoAll.custos[veiculo];
                const custosVeiculo = calcularCustosOperacionaisVeiculo(veiculo, dadosFreteDedicadoAll);
                
                htmlMargens += '<div class="margens-dedicado">';
                htmlMargens += `<div class="margem-item">💰 Custo total: R$ ${custoTotal.toFixed(2)}</div>`;
                htmlMargens += `<div class="margem-item">📊 Margem sugerida (15%): R$ ${(custoTotal * 0.15).toFixed(2)}</div>`;
                htmlMargens += `<div class="margem-item">💵 Preço sugerido: R$ ${(custoTotal * 1.15).toFixed(2)}</div>`;
                htmlMargens += '</div>';
            }
            
            containerMargens.innerHTML = htmlMargens;
        }
    };

    // Funções auxiliares para cálculos
    function obterCapacidadeVeiculo(veiculo) {
        const capacidades = {
            'FIORINO': { peso_max: 1000, volume_max: 4 },
            'VAN': { peso_max: 1500, volume_max: 8 },
            '3/4': { peso_max: 4000, volume_max: 15 },
            'TOCO': { peso_max: 6000, volume_max: 25 },
            'TRUCK': { peso_max: 8000, volume_max: 35 },
            'CARRETA': { peso_max: 27000, volume_max: 90 }
        };
        
        return capacidades[veiculo] || { peso_max: 1000, volume_max: 4 };
    }

    function calcularConsumoVeiculo(veiculo, distancia) {
        const consumos = {
            'FIORINO': 0.12,
            'VAN': 0.15,
            '3/4': 0.18,
            'TOCO': 0.20,
            'TRUCK': 0.22,
            'CARRETA': 0.25
        };
        
        const consumoPorKm = consumos[veiculo] || 0.15;
        const litros = distancia * consumoPorKm;
        const custo = litros * 5.50; // Preço médio do diesel
        
        return { litros: litros.toFixed(2), custo: custo.toFixed(2) };
    }

    function calcularPedagioVeiculo(veiculo, pedagioBase) {
        const multiplicadores = {
            'FIORINO': 1.0,
            'VAN': 1.2,
            '3/4': 1.5,
            'TOCO': 2.0,
            'TRUCK': 2.5,
            'CARRETA': 3.0
        };
        
        const multiplicador = multiplicadores[veiculo] || 1.0;
        return pedagioBase * multiplicador;
    }

    function calcularCustosOperacionaisVeiculo(veiculo, dados) {
        // Implementação básica - pode ser expandida
        return {
            combustivel: 0,
            pedagio: 0,
            manutencao: 0,
            total: 0
        };
    }

    function exibirResultadoAllInAereo(data) {
        const container = document.getElementById('resumo-aereo-opcoes');
        
        if (container) {
            if (data.erro) {
                container.innerHTML = `<div class="alert alert-warning">${data.erro}</div>`;
            } else {
                container.innerHTML = '<div class="alert alert-info">Calculo aereo em desenvolvimento</div>';
            }
        }
    }

    function exibirResultadoDedicado(data) {
        console.log('[DEDICADO] Exibindo resultado:', data);
        const container = document.getElementById('resultados-dedicado-all-in');
        
        if (container) {
            if (data.error) {
                container.innerHTML = `<div class="alert alert-warning">${data.error}</div>`;
            } else if (data.custos) {
                // Usar o mesmo layout da aba All In
                console.log('[DEDICADO] Usando layout All In para frete dedicado');
                
                // Armazenar dados globalmente para uso nas funções de seleção
                window.dadosFreteDedicado = data;
                
                let html = `
                    <div class="resumo-section">
                        <h3><i class="fa-solid fa-truck"></i> Frete Dedicado</h3>
                        <div class="resumo-grid">
                            <!-- Veículos -->
                            <div class="resumo-card">
                                <div class="resumo-card-header">
                                    <i class="fa-solid fa-truck-moving"></i> Veículos Disponíveis
                                </div>
                                <div id="resumo-dedicado-veiculos" class="resumo-card-body">
                `;
                
                // Verificar se há custos para exibir
                if (data.custos && Object.keys(data.custos).length > 0) {
                    html += '<h4>🚛 Veículos Disponíveis</h4>';
                    html += '<p style="font-size: 0.9rem; color: #6c757d; margin-bottom: 15px;">Clique em um veículo para ver detalhes específicos</p>';
                    html += '<div class="veiculos-grid">';
                    
                    Object.entries(data.custos).forEach(([veiculo, valor]) => {
                        const icone = veiculo.includes('VAN') ? '🚐' : 
                                     veiculo.includes('3/4') ? '🚛' : 
                                     veiculo.includes('TOCO') ? '🚛' : 
                                     veiculo.includes('TRUCK') ? '🚛' : 
                                     veiculo.includes('CARRETA') ? '🚛' : 
                                     veiculo.includes('FIORINO') ? '🚛' : '🚛';
                        
                        // Obter capacidade do veículo
                        const capacidade = obterCapacidadeVeiculo(veiculo);
                        
                        html += `
                            <div class="veiculo-card" onclick="selecionarVeiculoDedicado('${veiculo}')" style="cursor: pointer;">
                                <div class="veiculo-icone">${icone}</div>
                                <div class="veiculo-nome">${veiculo}</div>
                                <div class="veiculo-valor">R$ ${valor.toFixed(2)}</div>
                                <div class="veiculo-capacidade">
                                    <small>
                                        <div>⚖️ ${capacidade.peso_max.toLocaleString('pt-BR')} kg</div>
                                        <div>📦 ${capacidade.volume_max.toLocaleString('pt-BR')} m³</div>
                                    </small>
                                </div>
                            </div>
                        `;
                    });
                    
                    html += '</div>';
                } else {
                    html += '<p class="placeholder-text">Nenhum veículo disponível encontrado.</p>';
                }
                
                html += `
                                </div>
                            </div>
                            
                            <!-- Custos Operacionais -->
                            <div class="resumo-card">
                                <div class="resumo-card-header">
                                    <i class="fa-solid fa-calculator"></i> Custos Operacionais
                                </div>
                                <div id="resumo-dedicado-custos" class="resumo-card-body">
                                    <h4>💰 Custos Operacionais</h4>
                                    <p class="placeholder-text">
                                        <i class="fa-solid fa-hand-pointer"></i> Selecione um veículo para ver os custos operacionais
                                    </p>
                                </div>
                            </div>
                            
                            <!-- Margens Comerciais -->
                            <div class="resumo-card">
                                <div class="resumo-card-header">
                                    <i class="fa-solid fa-chart-line"></i> Margens Comerciais
                                </div>
                                <div id="resumo-dedicado-margens" class="resumo-card-body">
                                    <h4>📈 Margens Comerciais</h4>
                                    <p class="placeholder-text">
                                        <i class="fa-solid fa-hand-pointer"></i> Selecione um veículo para ver as margens sugeridas
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                container.innerHTML = html;
            } else {
                container.innerHTML = '<div class="alert alert-info">Dados do cálculo dedicado não disponíveis</div>';
            }
        }
    }

    function exibirResultadoAereo(data) {
        const container = document.getElementById('resultados-aereo');
        
        if (container) {
            if (data.erro) {
                container.innerHTML = `<div class="alert alert-warning">${data.erro}</div>`;
            } else {
                container.innerHTML = '<div class="alert alert-info">Calculo aereo em desenvolvimento</div>';
            }
        }
    }

    function exibirHistorico(historico) {
        const container = document.getElementById('listaHistorico');
        if (!container) return;

        if (!historico || historico.length === 0) {
            container.innerHTML = '<div class="alert alert-info">Nenhum item no historico ainda.</div>';
                return;
            }
            
        let html = '<h3>Ultimos Calculos</h3>';
        html += '<div class="historico-lista">';
        
        historico.slice(-10).reverse().forEach((item, index) => {
            html += `
                <div class="historico-item">
                    <div class="historico-header">
                        <strong>${item.tipo || 'Calculo'} #${item.id_historico || index + 1}</strong>
                        <span class="historico-data">${item.data_hora || 'Data nao disponivel'}</span>
                    </div>
                    <div class="historico-detalhes">
                        <span>${item.origem || 'Origem'} → ${item.destino || 'Destino'}</span>
                        <span>Distancia: ${item.distancia || 'N/A'} km</span>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
    }

    function showError(msg, containerId) {
        console.error(`[ERROR] ${msg} (Container: ${containerId})`);
        
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger';
        alertDiv.style.position = 'fixed';
        alertDiv.style.top = '20px';
        alertDiv.style.right = '20px';
        alertDiv.style.zIndex = '9999';
        alertDiv.style.maxWidth = '400px';
        alertDiv.innerHTML = `
            <strong>Erro:</strong> ${msg}
            <button type="button" class="close" style="float: right; background: none; border: none; font-size: 1.5rem;" onclick="this.parentElement.remove()">
                &times;
                            </button>
        `;
        
        document.body.appendChild(alertDiv);
        
        setTimeout(() => {
            if (alertDiv.parentElement) {
                alertDiv.remove();
            }
        }, 10000);
    }

    function showNoOptionsMessage(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-warning';
        alertDiv.style.position = 'fixed';
        alertDiv.style.top = '50%';
        alertDiv.style.left = '50%';
        alertDiv.style.transform = 'translate(-50%, -50%)';
        alertDiv.style.zIndex = '9999';
        alertDiv.style.maxWidth = '500px';
        alertDiv.innerHTML = `
            <h4>Nenhuma opcao encontrada</h4>
            <p>${message}</p>
            <button type="button" class="btn btn-primary" onclick="this.parentElement.remove()">
                Entendi
            </button>
        `;
        
        document.body.appendChild(alertDiv);
        
        setTimeout(() => {
            if (alertDiv.parentElement) {
                alertDiv.remove();
            }
        }, 8000);
    }

    // Funcoes para abrir abas
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
        
        if (tabName === 'historico') {
            carregarHistorico();
        }
    };

    // Funcoes de calculadora de volume
    window.calcularCubagem = function() {
        const largura = parseFloat(document.getElementById('largura_frac').value) || 0;
        const altura = parseFloat(document.getElementById('altura_frac').value) || 0;
        const comprimento = parseFloat(document.getElementById('comprimento_frac').value) || 0;
        
        if (largura > 0 && altura > 0 && comprimento > 0) {
            const cubagem = largura * altura * comprimento;
            document.getElementById('cubagem_frac').value = cubagem.toFixed(3);
        }
    };

    window.calcularCubagemAll = function() {
        const largura = parseFloat(document.getElementById('largura_all').value) || 0;
        const altura = parseFloat(document.getElementById('altura_all').value) || 0;
        const comprimento = parseFloat(document.getElementById('comprimento_all').value) || 0;
        
        if (largura > 0 && altura > 0 && comprimento > 0) {
            const cubagem = largura * altura * comprimento;
            document.getElementById('cubagem_all').value = cubagem.toFixed(3);
        }
    };

    window.calcularCubagemDedicado = function() {
        const largura = parseFloat(document.getElementById('largura').value) || 0;
        const altura = parseFloat(document.getElementById('altura').value) || 0;
        const comprimento = parseFloat(document.getElementById('comprimento').value) || 0;
        
        if (largura > 0 && altura > 0 && comprimento > 0) {
            const cubagem = largura * altura * comprimento;
            document.getElementById('cubagem').value = cubagem.toFixed(3);
        }
    };

    // Funcoes para resetar calculadoras
    window.resetarCubagem = function() {
        document.getElementById('largura_frac').value = '';
        document.getElementById('altura_frac').value = '';
        document.getElementById('comprimento_frac').value = '';
        document.getElementById('cubagem_frac').value = '';
    };

    window.resetarCubagemAll = function() {
        document.getElementById('largura_all').value = '';
        document.getElementById('altura_all').value = '';
        document.getElementById('comprimento_all').value = '';
        document.getElementById('cubagem_all').value = '';
    };

    window.resetarCubagemDedicado = function() {
        document.getElementById('largura').value = '';
        document.getElementById('altura').value = '';
        document.getElementById('comprimento').value = '';
        document.getElementById('cubagem').value = '';
    };

    // Expor funcoes globalmente
    window.showError = showError;
    window.showNoOptionsMessage = showNoOptionsMessage;
    
    // Funções auxiliares para frete dedicado
    function obterCapacidadeVeiculo(veiculo) {
        const capacidades = {
            'FIORINO': { peso_max: 1000, volume_max: 4 },
            'VAN': { peso_max: 1500, volume_max: 8 },
            '3/4': { peso_max: 4000, volume_max: 15 },
            'TOCO': { peso_max: 6000, volume_max: 25 },
            'TRUCK': { peso_max: 8000, volume_max: 35 },
            'CARRETA': { peso_max: 27000, volume_max: 90 }
        };
        
        return capacidades[veiculo] || { peso_max: 1000, volume_max: 4 };
    }

    function calcularConsumoVeiculo(veiculo, distancia) {
        const consumos = {
            'FIORINO': 0.12,
            'VAN': 0.15,
            '3/4': 0.18,
            'TOCO': 0.20,
            'TRUCK': 0.22,
            'CARRETA': 0.25
        };
        
        const consumoPorKm = consumos[veiculo] || 0.15;
        const litros = distancia * consumoPorKm;
        const custo = litros * 5.50;
        
        return { litros: litros.toFixed(2), custo: custo.toFixed(2) };
    }

    function calcularPedagioVeiculo(veiculo, pedagioBase) {
        const multiplicadores = {
            'FIORINO': 1.0,
            'VAN': 1.2,
            '3/4': 1.5,
            'TOCO': 2.0,
            'TRUCK': 2.5,
            'CARRETA': 3.0
        };
        
        const multiplicador = multiplicadores[veiculo] || 1.0;
        return pedagioBase * multiplicador;
    }

    // Função para selecionar veículo na aba dedicado
    window.selecionarVeiculoDedicado = function(veiculo) {
        console.log('[SELECIONAR VEICULO DEDICADO] Veículo selecionado:', veiculo);
        
        if (!window.dadosFreteDedicado) {
            console.error('[SELECIONAR VEICULO DEDICADO] Dados não disponíveis');
            return;
        }
        
        // Destacar veículo selecionado
        document.querySelectorAll('.veiculo-card').forEach(card => {
            card.classList.remove('veiculo-selecionado');
            if (card.querySelector('.veiculo-nome').textContent === veiculo) {
                card.classList.add('veiculo-selecionado');
            }
        });
        
        // Atualizar Custos Operacionais
        const containerCustos = document.getElementById('resumo-dedicado-custos');
        if (containerCustos && window.dadosFreteDedicado.analise) {
            let htmlCustos = `<h4>💰 Custos Operacionais - ${veiculo}</h4>`;
            
            htmlCustos += '<div class="analise-dedicado">';
            htmlCustos += `<div class="analise-item">📏 Distância: ${window.dadosFreteDedicado.analise.distancia} km</div>`;
            htmlCustos += `<div class="analise-item">⏱️ Tempo estimado: ${window.dadosFreteDedicado.analise.tempo_estimado}</div>`;
            
            const consumoVeiculo = calcularConsumoVeiculo(veiculo, window.dadosFreteDedicado.analise.distancia);
            htmlCustos += `<div class="analise-item">⛽ Consumo estimado: ${consumoVeiculo.litros} litros</div>`;
            htmlCustos += `<div class="analise-item">💰 Custo combustível: R$ ${consumoVeiculo.custo}</div>`;
            
            const pedagioVeiculo = calcularPedagioVeiculo(veiculo, window.dadosFreteDedicado.analise.pedagio_real);
            htmlCustos += `<div class="analise-item">🛣️ Pedágio: R$ ${pedagioVeiculo.toFixed(2)}</div>`;
            
            htmlCustos += '</div>';
            
            containerCustos.innerHTML = htmlCustos;
        }
        
        // Atualizar Margens Comerciais
        const containerMargens = document.getElementById('resumo-dedicado-margens');
        if (containerMargens && window.dadosFreteDedicado.custos && window.dadosFreteDedicado.custos[veiculo]) {
            let htmlMargens = `<h4>📈 Margens Comerciais - ${veiculo}</h4>`;
            
            const custoTotal = window.dadosFreteDedicado.custos[veiculo];
            
            htmlMargens += '<div class="margens-dedicado">';
            htmlMargens += `<div class="margem-item">💰 Custo total: R$ ${custoTotal.toFixed(2)}</div>`;
            htmlMargens += `<div class="margem-item">📊 Margem sugerida (15%): R$ ${(custoTotal * 0.15).toFixed(2)}</div>`;
            htmlMargens += `<div class="margem-item">💵 Preço sugerido: R$ ${(custoTotal * 1.15).toFixed(2)}</div>`;
            htmlMargens += '</div>';
            
            containerMargens.innerHTML = htmlMargens;
        }
    };
});
