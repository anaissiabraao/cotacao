// Funções para manipulação dos formulários e botões
// Padronização completa de todos os fluxos: dedicado, aéreo, fracionado, exportação
// Versão corrigida com melhorias de funcionalidade e depuração

document.addEventListener('DOMContentLoaded', function() {
    console.log('[DEBUG] DOMContentLoaded disparado');
    
    // Função para carregar estados via AJAX
    function carregarEstados(selectId) {
        const select = document.getElementById(selectId);
        if (!select) { 
            console.warn(`[DEBUG] Select não encontrado: ${selectId}`); 
            return; 
        }
        
        select.innerHTML = '<option value="">Carregando...</option>';
        select.disabled = true;
        
        // Adicionar timeout para garantir que a requisição não fique pendente indefinidamente
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Timeout ao carregar estados')), 10000);
        });
        
        Promise.race([
            fetch('/estados'),
            timeoutPromise
        ])
        .then(r => {
            if (!r.ok) throw new Error(`Erro HTTP: ${r.status}`);
            return r.json();
        })
        .then(estados => {
            select.innerHTML = '<option value="">Selecione o estado</option>';
            estados.forEach(e => {
                const opt = document.createElement('option');
                opt.value = e.id;
                opt.textContent = e.text;
                select.appendChild(opt);
            });
            select.disabled = false;
            console.log(`[DEBUG] Estados carregados para ${selectId}`);
            
            // Inicializar Select2 se disponível
            if (typeof $ !== 'undefined' && $.fn.select2) {
                $(select).select2({
                    placeholder: "Selecione o estado",
                    allowClear: true,
                    width: '100%'
                });
            }
        })
        .catch(error => {
            console.error(`[DEBUG] Erro ao carregar estados: ${error.message}`);
            select.innerHTML = '<option value="">Erro ao carregar estados</option>';
            select.disabled = false;
            
            // Usar fallback de estados
            const ESTADOS_FALLBACK = [
                {id: "AC", text: "Acre"}, {id: "AL", text: "Alagoas"}, {id: "AP", text: "Amapá"},
                {id: "AM", text: "Amazonas"}, {id: "BA", text: "Bahia"}, {id: "CE", text: "Ceará"},
                {id: "DF", text: "Distrito Federal"}, {id: "ES", text: "Espírito Santo"}, {id: "GO", text: "Goiás"},
                {id: "MA", text: "Maranhão"}, {id: "MT", text: "Mato Grosso"}, {id: "MS", text: "Mato Grosso do Sul"},
                {id: "MG", text: "Minas Gerais"}, {id: "PA", text: "Pará"}, {id: "PB", text: "Paraíba"},
                {id: "PR", text: "Paraná"}, {id: "PE", text: "Pernambuco"}, {id: "PI", text: "Piauí"},
                {id: "RJ", text: "Rio de Janeiro"}, {id: "RN", text: "Rio Grande do Norte"}, {id: "RS", text: "Rio Grande do Sul"},
                {id: "RO", text: "Rondônia"}, {id: "RR", text: "Roraima"}, {id: "SC", text: "Santa Catarina"},
                {id: "SP", text: "São Paulo"}, {id: "SE", text: "Sergipe"}, {id: "TO", text: "Tocantins"}
            ];
            
            select.innerHTML = '<option value="">Selecione o estado</option>';
            ESTADOS_FALLBACK.forEach(e => {
                const opt = document.createElement('option');
                opt.value = e.id;
                opt.textContent = e.text;
                select.appendChild(opt);
            });
            select.disabled = false;
            
            // Inicializar Select2 se disponível
            if (typeof $ !== 'undefined' && $.fn.select2) {
                $(select).select2({
                    placeholder: "Selecione o estado",
                    allowClear: true,
                    width: '100%'
                });
            }
        });
    }
    
    // Função para carregar municípios via AJAX
    function carregarMunicipios(uf, selectId) {
        const select = document.getElementById(selectId);
        if (!select) { 
            console.warn(`[DEBUG] Select município não encontrado: ${selectId}`); 
            return; 
        }

        // Destruir Select2 antes de recarregar
        if (typeof $ !== 'undefined' && $.fn.select2 && $(select).hasClass('select2-hidden-accessible')) {
            $(select).select2('destroy');
        }
        select.innerHTML = '<option value="">Carregando...</option>';
        select.value = '';
        select.disabled = true;
        if (!uf) {
            select.innerHTML = '<option value="">Selecione o estado primeiro</option>';
            select.value = '';
            select.disabled = true;
            return;
        }
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Timeout ao carregar municípios')), 10000);
        });
        Promise.race([
            fetch(`/municipios/${uf}`),
            timeoutPromise
        ])
        .then(r => {
            if (!r.ok) throw new Error(`Erro HTTP: ${r.status}`);
            return r.json();
        })
        .then(municipios => {
            select.innerHTML = '<option value="">Selecione o município</option>';
            municipios.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.id;
                opt.textContent = m.text;
                select.appendChild(opt);
            });
            select.value = '';
            select.disabled = false;
            setTimeout(() => {
                if (typeof $ !== 'undefined' && $.fn.select2) {
                    $(select).select2({
                        placeholder: "Selecione o município",
                        allowClear: true,
                        width: '100%'
                    });
                }
            }, 0);
            console.log(`[DEBUG] Municípios carregados para ${selectId}: ${municipios.length} municípios`);
        })
        .catch(error => {
            console.error(`[DEBUG] Erro ao carregar municípios: ${error.message}`);
            select.innerHTML = '<option value="">Erro ao carregar municípios</option>';
            select.value = '';
            select.disabled = false;
            setTimeout(() => {
                if (typeof $ !== 'undefined' && $.fn.select2) {
                    $(select).select2({
                        placeholder: "Erro ao carregar municípios",
                        allowClear: true,
                        width: '100%'
                    });
                }
            }, 0);
        });
    }

    // IDs dos selects de cada formulário
    const ids = {
        dedicado: {
            ufOrigem: 'uf_origem', munOrigem: 'municipio_origem',
            ufDestino: 'uf_destino', munDestino: 'municipio_destino',
            peso: 'peso', cubagem: 'cubagem',
            form: 'form-dedicado', loading: 'loading-dedicado',
            tabela: '#tabela-custos tbody', analise: 'analise-dedicado',
            mapContainer: 'map-dedicado'
        },
        aereo: {
            ufOrigem: 'uf_origem_aereo', munOrigem: 'municipio_origem_aereo',
            ufDestino: 'uf_destino_aereo', munDestino: 'municipio_destino_aereo',
            peso: 'peso_aereo', cubagem: 'cubagem_aereo',
            form: 'form-aereo', loading: 'loading-aereo',
            resultados: 'resultados-aereo',
            mapContainer: 'map-aereo'
        },
        fracionado: {
            ufOrigem: 'uf_origem_frac', munOrigem: 'municipio_origem_frac',
            ufDestino: 'uf_destino_frac', munDestino: 'municipio_destino_frac',
            peso: 'peso_frac', cubagem: 'cubagem_frac', valorNf: 'valor_nf_frac',
            form: 'form-fracionado', loading: 'loading-fracionado',
            resultados: 'fracionado-resultado',
            mapContainer: 'map-fracionado'
        }
    };

    // Carregar estados para todos os formulários - evitar múltiplas chamadas
    let estadosCarregados = false;
    
    function carregarEstadosSeNecessario() {
        if (estadosCarregados) return;
        
        // Só carregar se estivermos em uma página que precisa dos estados
        if (window.location.pathname === '/' || window.location.pathname.includes('admin')) {
            estadosCarregados = true;
            
            for (const tipo in ids) {
                carregarEstados(ids[tipo].ufOrigem);
                carregarEstados(ids[tipo].ufDestino);
            }
        }
    }
    
    // Carregar apenas quando a aba for clicada
    function carregarEstadosQuandoNecessario() {
        if (!estadosCarregados) {
            carregarEstadosSeNecessario();
        }
    }
    
    // Aguardar um pouco antes de verificar se deve carregar
    setTimeout(() => {
        // Só carregar se não estiver na página de login
        if (!window.location.pathname.includes('/login')) {
            carregarEstadosQuandoNecessario();
        }
    }, 2000);
    
    // Configurar eventos para carregar municípios
    function configurarEventosMunicipios() {
        for (const tipo in ids) {
            const ufOrigemEl = document.getElementById(ids[tipo].ufOrigem);
            const ufDestinoEl = document.getElementById(ids[tipo].ufDestino);
            
            if (ufOrigemEl) {
                $(ufOrigemEl).on('select2:select', function(e) {
                    console.log(`[DEBUG] Mudança de UF origem (${tipo}): ${this.value}`);
                    carregarMunicipios(this.value, ids[tipo].munOrigem);
                });
            }
            
            if (ufDestinoEl) {
                $(ufDestinoEl).on('select2:select', function(e) {
                    console.log(`[DEBUG] Mudança de UF destino (${tipo}): ${this.value}`);
                    carregarMunicipios(this.value, ids[tipo].munDestino);
                });
            }
        }
    }
    
    // Aguardar um pouco antes de configurar eventos
    setTimeout(configurarEventosMunicipios, 1000);

    // Função utilitária para mostrar loading
    function showLoading(id, show) {
        const el = document.getElementById(id);
        if (el) {
            el.style.display = show ? 'flex' : 'none';
            el.style.justifyContent = 'center';
            el.style.alignItems = 'center';
            el.style.margin = '18px auto 0 auto';
            console.log(`[DEBUG] Loading ${id}: ${show ? 'exibido' : 'ocultado'}`);
        } else {
            console.warn(`[DEBUG] Elemento loading não encontrado: ${id}`);
        }
    }

    // Função utilitária para exibir erros
    function showError(msg, containerId) {
        console.error(`[DEBUG] Erro: ${msg} (container: ${containerId})`);
        const el = document.getElementById(containerId);
        if (el) {
            el.innerHTML = `<div class='error'>${msg}</div>`;
            el.scrollIntoView({behavior: 'smooth', block: 'center'});
        } else {
            alert(msg);
        }
    }

    // Função para verificar se o mapa está inicializado
    function verificarMapaInicializado(mapId) {
        const mapContainer = document.getElementById(mapId);
        if (!mapContainer) {
            console.error(`[DEBUG] Container de mapa não encontrado: ${mapId}`);
            return false;
        }
        
        // Verificar se o mapa já foi inicializado
        if (!window[mapId]) {
            console.log(`[DEBUG] Mapa ${mapId} não inicializado ainda`);
            return false;
        }
        
        return true;
    }

    // === FUNÇÃO UNIVERSAL DE MAPA ===
    // Função robusta que funciona para todos os tipos de mapa (dedicado, aéreo, fracionado)
    function criarMapaUniversal(pontos, containerId) {
        console.log(`[MAPA] Iniciando criação do mapa no container: ${containerId}`);
        console.log(`[MAPA] Pontos recebidos:`, pontos);
        
        // Verificar se os pontos são válidos
        if (!pontos || !Array.isArray(pontos) || pontos.length < 2) {
            console.error('[MAPA] Pontos inválidos ou insuficientes:', pontos);
            const container = document.getElementById(containerId);
            if (container) {
                container.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">Pontos de rota insuficientes para exibir o mapa</div>';
            }
            return;
        }
        
        // Aguardar container estar disponível
        function aguardarContainer(tentativas = 0) {
            const container = document.getElementById(containerId);
            
            if (!container) {
                if (tentativas < 20) {
                    console.log(`[MAPA] Container ${containerId} não encontrado, tentativa ${tentativas + 1}/20`);
                    setTimeout(() => aguardarContainer(tentativas + 1), 100);
                } else {
                    console.error(`[MAPA] Container ${containerId} não encontrado após 20 tentativas`);
                }
                return;
            }
            
            // Garantir visibilidade e dimensões
            container.style.display = 'block';
            container.style.height = '400px';
            container.style.width = '100%';
            container.classList.remove('hidden');
            container.innerHTML = '';
            
            // Forçar reflow
            container.offsetHeight;
            
            // Aguardar um pouco mais para garantir que o container está pronto
            setTimeout(() => {
                inicializarLeaflet(container, pontos, containerId);
            }, 100);
        }
        
        function inicializarLeaflet(container, pontos, mapId) {
            try {
                console.log(`[MAPA] Inicializando Leaflet para ${mapId}`);
                
                // Verificar se o Leaflet está disponível
                if (typeof L === 'undefined') {
                    console.error('[MAPA] Leaflet não está carregado!');
                    container.innerHTML = '<div style="padding: 20px; text-align: center; color: #f44336;">Erro: Leaflet não carregado</div>';
                    return;
                }
                
                // Verificar se o container tem dimensões válidas
                const rect = container.getBoundingClientRect();
                console.log(`[MAPA] Dimensões do container ${mapId}:`, rect);
                
                if (rect.width === 0 || rect.height === 0) {
                    console.warn(`[MAPA] Container ${mapId} sem dimensões válidas, aguardando...`);
                    setTimeout(() => inicializarLeaflet(container, pontos, mapId), 300);
                    return;
                }
                
                // Remover mapa anterior se existir
                const mapKey = `mapa_${mapId.replace('-', '_')}`;
                if (window[mapKey]) {
                    try {
                        window[mapKey].remove();
                        console.log(`[MAPA] Mapa anterior ${mapKey} removido`);
                    } catch (e) {
                        console.warn(`[MAPA] Erro ao remover mapa anterior: ${e.message}`);
                    }
                    window[mapKey] = null;
                }
                
                // Limpar container
                container.innerHTML = '';
                
                // Calcular centro do mapa
                const lats = pontos.map(p => p[0]);
                const lngs = pontos.map(p => p[1]);
                const centerLat = (Math.min(...lats) + Math.max(...lats)) / 2;
                const centerLng = (Math.min(...lngs) + Math.max(...lngs)) / 2;
                
                console.log(`[MAPA] Centro calculado para ${mapId}:`, [centerLat, centerLng]);
                
                // Criar mapa
                const map = L.map(container, {
                    center: [centerLat, centerLng],
                    zoom: 6,
                    zoomControl: true,
                    scrollWheelZoom: true
                });
                
                console.log(`[MAPA] Mapa L.map criado para ${mapId}`);
                
                // Adicionar tiles do OpenStreetMap
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors',
                    maxZoom: 18
                }).addTo(map);
                
                // Adicionar marcador de origem (verde)
                const origemIcon = L.divIcon({
                    html: '<div style="background: #4CAF50; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3);"></div>',
                    iconSize: [20, 20],
                    className: 'custom-marker'
                });
                L.marker(pontos[0], {icon: origemIcon})
                    .bindPopup('<b>Origem</b>')
                    .addTo(map);
                
                // Adicionar marcador de destino (vermelho)
                const destinoIcon = L.divIcon({
                    html: '<div style="background: #F44336; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3);"></div>',
                    iconSize: [20, 20],
                    className: 'custom-marker'
                });
                L.marker(pontos[pontos.length - 1], {icon: destinoIcon})
                    .bindPopup('<b>Destino</b>')
                    .addTo(map);
                
                // Adicionar linha da rota
                const cor = mapId.includes('aereo') ? '#FF5722' : '#2196F3'; // Laranja para aéreo, azul para outros
                const polyline = L.polyline(pontos, {
                    color: cor,
                    weight: 4,
                    opacity: 0.8
                }).addTo(map);
                
                // Ajustar zoom para mostrar toda a rota
                map.fitBounds(polyline.getBounds(), {padding: [20, 20]});
                
                // Salvar referência do mapa
                window[mapKey] = map;
                
                console.log(`[MAPA] Mapa ${mapId} criado com sucesso!`);
                
                // Invalidar o tamanho após um breve delay (importante para Leaflet)
                setTimeout(() => {
                    if (map) {
                        map.invalidateSize();
                    }
                }, 200);
                
            } catch (error) {
                console.error(`[MAPA] Erro ao criar mapa ${mapId}:`, error);
                container.innerHTML = `<div style="padding: 20px; text-align: center; color: #f44336;">Erro ao carregar o mapa: ${error.message}</div>`;
            }
        }
        
        aguardarContainer();
    }
    
    // === ATUALIZAR FLUXOS PARA USAR A FUNÇÃO UNIVERSAL ===
    
    // Função robusta para garantir que o mapa aéreo só é inicializado quando o container existir
    function mostrarMapaAereo(rota) {
        criarMapaUniversal(rota, 'map-aereo');
    }

    // --- FLUXO DEDICADO ---
    const formDedicado = document.getElementById(ids.dedicado.form);
    if (formDedicado) {
        console.log('[DEBUG] form-dedicado encontrado');
        formDedicado.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('[DEBUG] Submit do dedicado acionado');
            
            // Obter valores dos campos
            const uf_origem = document.getElementById(ids.dedicado.ufOrigem).value;
            const municipio_origem = document.getElementById(ids.dedicado.munOrigem).value;
            const uf_destino = document.getElementById(ids.dedicado.ufDestino).value;
            const municipio_destino = document.getElementById(ids.dedicado.munDestino).value;
            const peso = document.getElementById(ids.dedicado.peso) ? document.getElementById(ids.dedicado.peso).value : '';
            const cubagem = document.getElementById(ids.dedicado.cubagem) ? document.getElementById(ids.dedicado.cubagem).value : '';
            
            console.log('[DEBUG] Dados enviados:', {uf_origem, municipio_origem, uf_destino, municipio_destino, peso, cubagem});
            
            // Validar campos obrigatórios
            if (!uf_origem || !municipio_origem || !uf_destino || !municipio_destino) {
                showError('Por favor, selecione origem e destino completos.', ids.dedicado.analise);
                return;
            }
            
            // Mostrar loading
            showLoading(ids.dedicado.loading, true);
            
            // Preparar o container do mapa
            const mapContainer = document.getElementById(ids.dedicado.mapContainer);
            if (mapContainer) {
                mapContainer.style.display = 'block';
                mapContainer.classList.remove('hidden');
            }
            
            // Enviar requisição para o backend
            fetch('/calcular', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    uf_origem, municipio_origem, uf_destino, municipio_destino,
                    peso: peso ? parseFloat(peso) : 0,
                    cubagem: cubagem ? parseFloat(cubagem) : 0
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Erro HTTP: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                showLoading(ids.dedicado.loading, false);
                console.log('[DEBUG] Resposta do backend:', data);
                
                if (data.error) {
                    showError(data.error, ids.dedicado.analise);
                    return;
                }
                
                // Salvar rota para uso posterior
                console.log('[DEBUG] Salvando rota:', data.rota_pontos);
                window.ultimaRotaDedicado = data.rota_pontos;
                try {
                    localStorage.setItem('ultimaRotaDedicado', JSON.stringify(data.rota_pontos));
                } catch (e) { console.warn('[DEBUG] Falha ao salvar rota no localStorage:', e); }
                
                // Atualiza análise
                const analiseDiv = document.getElementById(ids.dedicado.analise);
                if (analiseDiv && data.analise) {
                    // Mostrar seção do mapa primeiro
                    const mapaSection = document.getElementById('mapa-section-dedicado');
                    if (mapaSection) {
                        mapaSection.style.display = 'block';
                    }
                    
                    // Montar análise textual em container estilizado
                    let analiseHtml = `
                        <div class="analise-container">
                            <h3 class="analise-title"><i class="fa-solid fa-chart-bar" aria-hidden="true"></i> Análise da Rota</h3>
                            <div class="results-grid">
                              <div>
                                <div class="analise-item"><strong>Distância:</strong> ${data.analise.distancia} km</div>
                                <div class="analise-item"><strong>Tempo estimado:</strong> ${data.analise.tempo_estimado}</div>
                                <div class="analise-item"><strong>Consumo estimado:</strong> ${data.analise.consumo_combustivel} L</div>
                              </div>
                              <div>
                                <div class="analise-item"><strong>Emissão de CO₂:</strong> ${data.analise.emissao_co2} kg</div>
                                <div class="analise-item"><strong>Pedágio estimado:</strong> R$ ${data.analise.pedagio_estimado}</div>
                                <div class="analise-item"><strong>Provedor de rota:</strong> ${data.analise.provider}</div>
                              </div>
                            </div>
                        </div>
                    `;

                    analiseDiv.innerHTML = analiseHtml;
                    analiseDiv.style.display = 'block';
                } else if (!analiseDiv) {
                    console.warn('[DEBUG] Div de análise não encontrada');
                }
                
                // Atualizar resultados com tabela e gráfico menores
                const resultadosDiv = document.getElementById('resultados-dedicado');
                if (resultadosDiv) {
                    // Montar tabela de custos compacta
                    let tabelaCustos = '<h4 style="color: #0a6ed1; margin-bottom: 10px;"><i class="fa-solid fa-money-bill-wave"></i> Custos por Veículo</h4>';
                    tabelaCustos += '<table class="results"><thead><tr><th>Veículo</th><th>Custo (R$)</th></tr></thead><tbody>';
                    Object.entries(data.custos).forEach(([tipo, valor]) => {
                        tabelaCustos += `<tr><td>${tipo}</td><td>R$ ${valor.toFixed(2)}</td></tr>`;
                    });
                    tabelaCustos += '</tbody></table>';

                    // Container do gráfico menor
                    let chartContainer = `
                        <div class="chart-container">
                            <h5 style="color: #0a6ed1; margin: 15px 0 10px 0; text-align: center;">Gráfico de Custos</h5>
                            <canvas id="dedicadoChart" width="400" height="150"></canvas>
                        </div>
                    `;

                    // Botões de exportação
                    let exportBtns = `
                        <div id="dedicado-export-btns" style="margin-top:18px; text-align: center;">
                            <button class="btn-primary" onclick="window.exportarPDF('Dedicado')" style="margin-right: 10px;">Baixar PDF</button>
                            <button class="btn-primary" onclick="window.exportarExcel('Dedicado')">Exportar Excel</button>
                        </div>
                    `;

                    resultadosDiv.innerHTML = tabelaCustos + chartContainer + exportBtns;
                    resultadosDiv.style.display = 'block';
                    resultadosDiv.scrollIntoView({behavior: 'smooth', block: 'center'});

                    // Gráfico de barras menor
                    setTimeout(() => {
                        if (window.dedicadoChart && typeof window.dedicadoChart.destroy === 'function') {
                            window.dedicadoChart.destroy();
                        }
                        const ctx = document.getElementById('dedicadoChart');
                        if (ctx) {
                            const chart = ctx.getContext('2d');
                            const veiculos = Object.keys(data.custos);
                            const custos = Object.values(data.custos);
                            window.dedicadoChart = new Chart(chart, {
                                type: 'bar',
                                data: {
                                    labels: veiculos,
                                    datasets: [
                                        {
                                            label: 'Custo (R$)',
                                            data: custos,
                                            backgroundColor: '#0a6ed1',
                                            borderRadius: 8
                                        }
                                    ]
                                },
                                options: {
                                    responsive: true,
                                    maintainAspectRatio: true,
                                    aspectRatio: 2.5,
                                    plugins: { 
                                        legend: { display: false },
                                        title: { display: false }
                                    },
                                    scales: { 
                                        y: { 
                                            beginAtZero: true, 
                                            grid: { display: true },
                                            ticks: { font: { size: 11 } }
                                        },
                                        x: { 
                                            grid: { display: false },
                                            ticks: { font: { size: 11 } }
                                        }
                                    },
                                    layout: {
                                        padding: {
                                            top: 10,
                                            bottom: 10,
                                            left: 10,
                                            right: 10
                                        }
                                    }
                                }
                            });
                        }
                    }, 100);
                } else {
                    console.warn('[DEBUG] Div de resultados não encontrada');
                }
                
                // Armazenar resultado para exportação
                window.ultimoResultadoDedicado = data.analise;
                // Mostrar mapa dedicado
                if (data.rota_pontos && Array.isArray(data.rota_pontos) && data.rota_pontos.length > 1) {
                    console.log('[DEBUG] Chamando criarMapaUniversal para dedicado com pontos:', data.rota_pontos);
                    criarMapaUniversal(data.rota_pontos, 'map-dedicado');
                } else {
                    console.warn('[DEBUG] Pontos de rota inválidos para mapa dedicado:', data.rota_pontos);
                }
            })
            .catch(error => {
                showLoading(ids.dedicado.loading, false);
                console.error('[DEBUG] Erro no fetch dedicado:', error);
                showError('Erro ao calcular frete dedicado: ' + error.message, ids.dedicado.analise);
            });
        });
    } else {
        console.warn('[DEBUG] form-dedicado NÃO encontrado');
    }

    // --- FLUXO AÉREO ---
    const formAereo = document.getElementById(ids.aereo.form);
    if (formAereo) {
        console.log('[DEBUG] form-aereo encontrado');
        formAereo.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('[DEBUG] Submit do aéreo acionado');
            
            // Obter valores dos campos
            const uf_origem = document.getElementById(ids.aereo.ufOrigem).value;
            const municipio_origem = document.getElementById(ids.aereo.munOrigem).value;
            const uf_destino = document.getElementById(ids.aereo.ufDestino).value;
            const municipio_destino = document.getElementById(ids.aereo.munDestino).value;
            const peso = document.getElementById(ids.aereo.peso) ? document.getElementById(ids.aereo.peso).value : '';
            const cubagem = document.getElementById(ids.aereo.cubagem) ? document.getElementById(ids.aereo.cubagem).value : '';
            
            console.log('[DEBUG] Dados enviados:', {uf_origem, municipio_origem, uf_destino, municipio_destino, peso, cubagem});
            
            // Validar campos obrigatórios
            if (!uf_origem || !municipio_origem || !uf_destino || !municipio_destino) {
                showError('Por favor, selecione origem e destino completos.', ids.aereo.resultados);
                return;
            }
            
            // Mostrar loading
            showLoading(ids.aereo.loading, true);
            
            // Preparar o container do mapa
            const mapContainer = document.getElementById(ids.aereo.mapContainer);
            if (mapContainer) {
                mapContainer.style.display = 'block';
                mapContainer.style.height = '400px';
                mapContainer.classList.remove('hidden');
                mapContainer.innerHTML = '';
                mapContainer.offsetHeight; // força reflow
            }
            
            // Enviar requisição para o backend
            fetch('/calcular_aereo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    uf_origem, municipio_origem, uf_destino, municipio_destino,
                    peso: peso ? parseFloat(peso) : 0,
                    cubagem: cubagem ? parseFloat(cubagem) : 0
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Erro HTTP: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                showLoading(ids.aereo.loading, false);
                console.log('[DEBUG] Resposta do backend aéreo:', data);
                
                if (data.error) {
                    showError(data.error, ids.aereo.resultados);
                    return;
                }
                // Garantir que o container do mapa aéreo está visível, limpo e com altura
                const mapContainer = document.getElementById('map-aereo');
                if (mapContainer) {
                    mapContainer.style.display = 'block';
                    mapContainer.style.height = '400px';
                    mapContainer.classList.remove('hidden');
                    mapContainer.innerHTML = '';
                    mapContainer.offsetHeight; // força reflow
                }
                // Mostrar mapa aéreo (linha reta entre origem e destino)
                if (data.rota_pontos && Array.isArray(data.rota_pontos) && data.rota_pontos.length > 1) {
                    const linhaReta = [data.rota_pontos[0], data.rota_pontos[data.rota_pontos.length - 1]];
                    console.log('[DEBUG] Chamando criarMapaUniversal para aéreo com linha reta:', linhaReta);
                    criarMapaUniversal(linhaReta, 'map-aereo');
                } else {
                    console.warn('[DEBUG] Pontos de rota inválidos para mapa aéreo:', data.rota_pontos);
                }
                // Atualiza resultados
                const resultadosDiv = document.getElementById(ids.aereo.resultados);
                if (resultadosDiv) {
                    let exportBtns = `
                        <div id="aereo-export-btns" style="margin-top:18px;">
                            <button class="btn-primary" onclick="window.exportarPDF('Aéreo')" style="margin-right: 10px;">Baixar PDF</button>
                            <button class="btn-primary" onclick="window.exportarExcel('Aéreo')">Exportar Excel</button>
                        </div>
                    `;
                    resultadosDiv.innerHTML = `
                        <div class="card slide-up">
                          <h3><i class="fa-solid fa-plane" aria-hidden="true"></i> Resultado do Cálculo Aéreo</h3>
                          <div class="results-grid">
                            <div>
                              <p><strong>Origem:</strong> ${municipio_origem} - ${uf_origem}</p>
                              <p><strong>Destino:</strong> ${municipio_destino} - ${uf_destino}</p>
                              <p><strong>Peso:</strong> ${peso} kg</p>
                              <p><strong>Cubagem:</strong> ${cubagem} m³</p>
                            </div>
                            <div>
                              <p><strong>Distância:</strong> ${data.distancia.toFixed(2)} km</p>
                              <p><strong>Tempo de voo:</strong> ${Math.round(data.duracao)} min</p>
                              <p><strong>Tipo:</strong> Modal Aéreo (Linha Reta)</p>
                            </div>
                          </div>
                          <h4><i class="fa-solid fa-money-bill-wave" aria-hidden="true"></i> Custos por Modalidade</h4>
                          <table class="results">
                            <thead>
                              <tr>
                                <th scope="col">Modalidade</th>
                                <th scope="col">Custo (R$)</th>
                                <th scope="col">Prazo (dias)</th>
                              </tr>
                            </thead>
                            <tbody>
                              ${Object.entries(data.custos).map(([modalidade, custo]) => `
                                <tr>
                                  <td>${modalidade}</td>
                                  <td>R$ ${custo.toFixed(2)}</td>
                                  <td>1</td>
                                </tr>
                              `).join("")}
                            </tbody>
                          </table>
                          ${exportBtns}
                        </div>
                    `;
                    resultadosDiv.style.display = 'block';
                    resultadosDiv.scrollIntoView({behavior: 'smooth', block: 'center'});
                } else {
                    console.warn('[DEBUG] Div de resultados aéreo não encontrada');
                }
                
                // Armazenar resultado para exportação
                window.ultimoResultadoAereo = data.analise;
            })
            .catch(error => {
                showLoading(ids.aereo.loading, false);
                console.error('[DEBUG] Erro no fetch aéreo:', error);
                showError('Erro ao calcular frete aéreo: ' + error.message, ids.aereo.resultados);
            });
        });
    } else {
        console.warn('[DEBUG] form-aereo NÃO encontrado');
    }

    // --- FLUXO FRACIONADO ---
    const formFracionado = document.getElementById(ids.fracionado.form);
    if (formFracionado) {
        console.log('[DEBUG] form-fracionado encontrado');
        formFracionado.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('[DEBUG] Submit do fracionado acionado');
            
            // Obter valores dos campos
            const uf_origem = document.getElementById(ids.fracionado.ufOrigem).value;
            const municipio_origem = document.getElementById(ids.fracionado.munOrigem).value;
            const uf_destino = document.getElementById(ids.fracionado.ufDestino).value;
            const municipio_destino = document.getElementById(ids.fracionado.munDestino).value;
            const peso = document.getElementById(ids.fracionado.peso) ? document.getElementById(ids.fracionado.peso).value : '';
            const cubagem = document.getElementById(ids.fracionado.cubagem) ? document.getElementById(ids.fracionado.cubagem).value : '';
            const valor_nf = document.getElementById(ids.fracionado.valorNf) ? document.getElementById(ids.fracionado.valorNf).value : '';
            
            console.log('[DEBUG] Dados enviados:', {uf_origem, municipio_origem, uf_destino, municipio_destino, peso, cubagem, valor_nf});
            
            // Validar campos obrigatórios
            if (!uf_origem || !municipio_origem || !uf_destino || !municipio_destino) {
                showError('Por favor, selecione origem e destino completos.', ids.fracionado.resultados);
                return;
            }
            
            // Mostrar loading
            showLoading(ids.fracionado.loading, true);
            
            // Preparar o container do mapa
            const mapContainer = document.getElementById(ids.fracionado.mapContainer);
            if (mapContainer) {
                mapContainer.style.display = 'block';
                mapContainer.classList.remove('hidden');
            }
            
            // Enviar requisição para o backend
            fetch('/calcular_frete_fracionado', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    estado_origem: uf_origem, 
                    municipio_origem,
                    estado_destino: uf_destino, 
                    municipio_destino,
                    peso: peso ? parseFloat(peso) : 0,
                    cubagem: cubagem ? parseFloat(cubagem) : 0,
                    valor_nf: valor_nf ? parseFloat(valor_nf) : null
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Erro HTTP: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                showLoading(ids.fracionado.loading, false);
                console.log('[DEBUG] Resposta do backend fracionado:', data);
                
                if (data.error) {
                    showError(data.error, ids.fracionado.resultados);
                    return;
                }
                
                // Atualiza mapa fracionado
                if (data.rota_pontos && typeof initializeFracionadoMap === 'function') {
                    console.log('[DEBUG] Inicializando mapa fracionado com rota');
                    initializeFracionadoMap(data.rota_pontos);
                } else {
                    console.warn('[DEBUG] Não foi possível inicializar o mapa fracionado');
                }
                
                // Atualiza resultados
                const resultadosDiv = document.getElementById(ids.fracionado.resultados);
                if (resultadosDiv) {
                    resultadosDiv.innerHTML = data.html || '<div class="success">Cálculo realizado com sucesso!</div>';
                    resultadosDiv.style.display = 'block';
                    resultadosDiv.scrollIntoView({behavior: 'smooth', block: 'center'});
                } else {
                    console.warn('[DEBUG] Div de resultados fracionado não encontrada');
                }
                
                // Armazenar resultado para exportação
                window.ultimoResultadoFracionado = data.analise;
                // Mostrar mapa fracionado (rota completa)
                if (data.rota_pontos && Array.isArray(data.rota_pontos) && data.rota_pontos.length > 1) {
                    console.log('[DEBUG] Chamando criarMapaUniversal para fracionado com pontos:', data.rota_pontos);
                    criarMapaUniversal(data.rota_pontos, 'map-fracionado');
                } else {
                    console.warn('[DEBUG] Pontos de rota inválidos para mapa fracionado:', data.rota_pontos);
                }
            })
            .catch(error => {
                showLoading(ids.fracionado.loading, false);
                console.error('[DEBUG] Erro no fetch fracionado:', error);
                showError('Erro ao calcular frete fracionado: ' + error.message, ids.fracionado.resultados);
            });
        });
    } else {
        console.warn('[DEBUG] form-fracionado NÃO encontrado');
    }

    // --- NAVEGAÇÃO ENTRE ABAS ---
    function openTab(evt, tabName) {
        console.log(`[DEBUG] Abrindo aba: ${tabName}`);
        
        // Carregar estados quando necessário (lazy loading)
        if ((tabName === 'dedicado' || tabName === 'fracionado') && !estadosCarregados) {
            carregarEstadosQuandoNecessario();
        }
        
        // Esconder todas as abas
        var tabcontent = document.getElementsByClassName("tab-content");
        for (var i = 0; i < tabcontent.length; i++) {
            tabcontent[i].classList.remove("active");
            tabcontent[i].setAttribute("aria-hidden", "true");
        }
        // Remover classe ativa de todos os botões
        var tabbuttons = document.getElementsByClassName("tab-btn");
        for (var i = 0; i < tabbuttons.length; i++) {
            tabbuttons[i].classList.remove("active");
            tabbuttons[i].setAttribute("aria-selected", "false");
        }
        // Mostrar aba selecionada
        var currentTab = document.getElementById(tabName);
        if (currentTab) {
            currentTab.classList.add("active");
            currentTab.setAttribute("aria-hidden", "false");
        } else {
            console.error(`[DEBUG] Aba não encontrada: ${tabName}`);
        }
        // Ativar botão da aba
        if (evt && evt.currentTarget) {
            evt.currentTarget.classList.add("active");
            evt.currentTarget.setAttribute("aria-selected", "true");
        }
        // Carregar conteúdo específico da aba
        if (tabName === "historico") {
            carregarHistorico();
        }
        // Inicializar mapa dedicado ao ativar a aba
        if (tabName === 'dedicado') {
            setTimeout(() => {
                const mapContainer = document.getElementById('map-dedicado');
                let rota = window.ultimaRotaDedicado;
                if ((!rota || !Array.isArray(rota) || rota.length <= 1) && localStorage.getItem('ultimaRotaDedicado')) {
                    try {
                        rota = JSON.parse(localStorage.getItem('ultimaRotaDedicado'));
                        window.ultimaRotaDedicado = rota;
                        console.log('[DEBUG] Lendo rota do localStorage:', rota);
                    } catch (e) { rota = undefined; }
                }
                console.log('[DEBUG] Valor de rota ao abrir aba dedicado:', rota);
                // Função robusta para garantir container visível e inicializar mapa
                function tentarInicializarMapaDedicado(rota, tentativas = 1) {
                    const mapContainer = document.getElementById('map-dedicado');
                    if (!mapContainer) {
                        console.error('[MAPA] Container do mapa não encontrado!');
                        if (tentativas < 10) setTimeout(() => tentarInicializarMapaDedicado(rota, tentativas + 1), 300);
                        return;
                    }
                    // Checar se está visível e com altura
                    const style = window.getComputedStyle(mapContainer);
                    if (style.display === 'none' || mapContainer.offsetHeight < 50) {
                        mapContainer.style.display = 'block';
                        mapContainer.style.height = '400px';
                        mapContainer.classList.remove('hidden');
                        if (tentativas < 10) setTimeout(() => tentarInicializarMapaDedicado(rota, tentativas + 1), 300);
                        return;
                    }
                    mapContainer.innerHTML = '';
                    initializeDedicadoMap(rota);
                }
                if (rota && Array.isArray(rota) && rota.length > 1 && mapContainer) {
                    tentarInicializarMapaDedicado(rota);
                } else if (mapContainer) {
                    mapContainer.innerHTML = '<div style="color:#e53935;font-weight:600;text-align:center;padding:20px;">Nenhuma rota disponível para exibir o mapa (JS).</div>';
                }
            }, 300);
        }
    }
    
    // Adicionar event listeners para os botões de aba
    document.querySelectorAll(".tab-btn").forEach(function(btn) {
        btn.addEventListener("click", function(e) {
            e.preventDefault();
            const tabId = this.getAttribute("aria-controls");
            if (tabId) {
                openTab(e, tabId);
            } else {
                console.error("[DEBUG] Botão de aba sem atributo aria-controls");
            }
        });
    });
    
    // Navegação por teclado para acessibilidade
    document.addEventListener("keydown", function(e) {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
            const tabs = document.querySelectorAll(".tab-btn");
            const activeTab = document.querySelector(".tab-btn.active");
            const activeIndex = Array.from(tabs).indexOf(activeTab);
            
            let newIndex;
            if (e.key === "ArrowRight") {
                newIndex = (activeIndex + 1) % tabs.length;
            } else {
                newIndex = (activeIndex - 1 + tabs.length) % tabs.length;
            }
            
            tabs[newIndex].click();
            tabs[newIndex].focus();
            e.preventDefault();
        }
    });

    // --- EXPORTAÇÃO PDF/EXCEL ---
    function exportar(tipo, endpoint, nomeBase) {
        console.log(`[DEBUG] Exportando ${tipo} para ${endpoint}`);
        
        let dados = null;
        if (tipo === 'Fracionado' && window.ultimoResultadoFracionado) {
            dados = window.ultimoResultadoFracionado;
        } else if (tipo === 'Dedicado' && window.ultimoResultadoDedicado) {
            dados = window.ultimoResultadoDedicado;
        } else if (tipo === 'Aereo' && window.ultimoResultadoAereo) {
            dados = window.ultimoResultadoAereo;
        }
        
        if (!dados) {
            alert('Nenhum resultado disponível para exportação. Faça um cálculo primeiro.');
            return;
        }
        
        fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tipo, analise: dados, dados })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Erro HTTP: ${response.status}`);
            }
            return response.blob();
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const dataStr = new Date().toISOString().replace(/[:.]/g, '-');
            a.download = `${nomeBase}_${tipo.toLowerCase()}_${dataStr}.${endpoint.includes('pdf') ? 'pdf' : 'xlsx'}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            console.log(`[DEBUG] Arquivo ${tipo} exportado com sucesso`);
        })
        .catch(error => {
            console.error(`[DEBUG] Erro ao exportar arquivo: ${error.message}`);
            alert('Erro ao exportar arquivo: ' + error.message);
        });
    }
    
    // Expor funções de exportação globalmente
    window.exportarPDF = tipo => exportar(tipo, '/gerar-pdf', 'relatorio');
    window.exportarExcel = tipo => exportar(tipo, '/exportar-excel', 'dados');
    
    // Expor função openTab globalmente
    window.openTab = openTab;
    
    // Carregar histórico
    function carregarHistorico() {
        console.log('[DEBUG] Carregando histórico');
        const historicoDiv = document.getElementById('listaHistorico');
        if (!historicoDiv) {
            console.warn('[DEBUG] Div de histórico não encontrada');
            return;
        }
        
        fetch('/historico')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Erro HTTP: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log(`[DEBUG] Histórico carregado: ${data.length} registros`);
                if (data.length === 0) {
                    historicoDiv.innerHTML = '<p>Nenhum cálculo realizado ainda.</p>';
                    return;
                }
                
                let html = '';
                data.forEach(item => {
                    html += `
                        <div class="history-card">
                            <h3>${item.id_historico} - ${item.tipo}</h3>
                            <p><strong>Origem:</strong> ${item.origem}</p>
                            <p><strong>Destino:</strong> ${item.destino}</p>
                            <p><strong>Distância:</strong> ${item.distancia} km</p>
                            <p><strong>Data:</strong> ${item.data_hora}</p>
                            <button class="btn-primary btn-sm" onclick="verDetalhesHistorico('${item.id_historico}')">
                                Ver Detalhes
                            </button>
                        </div>
                    `;
                });
                
                historicoDiv.innerHTML = html;
            })
            .catch(error => {
                console.error(`[DEBUG] Erro ao carregar histórico: ${error.message}`);
                historicoDiv.innerHTML = `<div class="error">Erro ao carregar histórico: ${error.message}</div>`;
            });
    }
    
    // Filtro de histórico
    const filtroHistorico = document.getElementById('filtroHistorico');
    if (filtroHistorico) {
        filtroHistorico.addEventListener('input', function() {
            const filtro = this.value.toLowerCase();
            const cards = document.querySelectorAll('.history-card');
            
            cards.forEach(card => {
                const id = card.querySelector('h3').textContent.toLowerCase();
                if (id.includes(filtro)) {
                    card.style.display = '';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    }
    
    // Função para ver detalhes do histórico
    window.verDetalhesHistorico = function(id) {
        console.log(`[DEBUG] Vendo detalhes do histórico: ${id}`);
        fetch(`/historico/${id}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Erro HTTP: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log(`[DEBUG] Detalhes do histórico carregados: ${id}`);
                alert(`Detalhes do cálculo ${id}:\n\n${JSON.stringify(data, null, 2)}`);
            })
            .catch(error => {
                console.error(`[DEBUG] Erro ao carregar detalhes do histórico: ${error.message}`);
                alert(`Erro ao carregar detalhes: ${error.message}`);
            });
    };
    
    // Abrir a primeira aba por padrão
    const firstTabButton = document.querySelector(".tab-btn");
    if (firstTabButton) {
        console.log('[DEBUG] Abrindo primeira aba por padrão');
        firstTabButton.click();
    } else {
        console.warn('[DEBUG] Nenhum botão de aba encontrado');
    }
    
    // Função para toggle de detalhes de cotações
    function toggleDetails(elementId) {
        console.log(`[DEBUG] Tentando toggle para elemento: ${elementId}`);
        const element = document.getElementById(elementId);
        
        if (element) {
            console.log(`[DEBUG] Elemento encontrado. Display atual: ${element.style.display}`);
            
            if (element.style.display === 'none' || element.style.display === '') {
                if (element.tagName.toLowerCase() === 'tr') {
                    element.style.display = 'table-row';
                } else {
                    element.style.display = 'block';
                }
                console.log(`[DEBUG] Elemento ${elementId} mostrado`);
            } else {
                element.style.display = 'none';
                console.log(`[DEBUG] Elemento ${elementId} ocultado`);
            }
        } else {
            console.error(`[DEBUG] Elemento não encontrado: ${elementId}`);
            // Tentar encontrar por classe ou outros seletores
            const allElements = document.querySelectorAll(`[id*="${elementId}"], .${elementId}`);
            console.log(`[DEBUG] Elementos similares encontrados:`, allElements);
        }
    }

    // Tornar a função globalmente disponível
    window.toggleDetails = toggleDetails;

    // Função auxiliar para debugar elementos de detalhes
    function debugDetalhes() {
        const detailElements = document.querySelectorAll('[id*="details"], [id*="cotacao"], [id*="detalhes"]');
        console.log('[DEBUG] Elementos de detalhes encontrados:', detailElements);
        detailElements.forEach(el => {
            console.log(`[DEBUG] ID: ${el.id}, Display: ${el.style.display}, TagName: ${el.tagName}`);
        });
    }

    // Tornar função de debug globalmente disponível
    window.debugDetalhes = debugDetalhes;

    console.log('[DEBUG] Funções toggleDetails e debugDetalhes registradas globalmente');
    
    console.log('[DEBUG] Inicialização concluída');
});