// ========================================
// CORREÇÕES PARA O FRETE FRACIONADO
// ========================================

// 🔧 CORREÇÃO 1: Remover "Distância:" e "Tempo Estimado:" da interface
// ❌ REMOVER ESTAS LINHAS DO ARQUIVO PRINCIPAL (linhas ~1362-1363):
/*
<div class="analise-item"><strong>Distância:</strong> ${ranking.distancia} km</div>
<div class="analise-item"><strong>Tempo Estimado:</strong> ${ranking.tempo_estimado}</div>
*/

// ✅ SUBSTITUIR POR: (manter apenas peso cubado e valor NF)
/*
<div class="analise-item"><strong>Peso Cubado:</strong> ${ranking.peso_cubado}kg (${ranking.peso_usado_tipo})</div>
${ranking.valor_nf ? `<div class="analise-item"><strong>Valor NF:</strong> R$ ${ranking.valor_nf.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>` : ''}
*/

// 🔧 CORREÇÃO 2: Adicionar funcionalidade de clique nos agentes
// ✅ ADICIONAR ESTAS FUNÇÕES AO FINAL DO ARQUIVO PRINCIPAL:

// 🆕 FUNÇÃO PARA EXIBIR CUSTOS ESPECÍFICOS DE CADA AGENTE
window.exibirCustosAgente = function(tipoAgente, opcaoIndex) {
    console.log(`[AGENTE-CLICK] Clicado em ${tipoAgente} da opção ${opcaoIndex}`);
    
    // Buscar dados da opção selecionada
    const rankingData = window.ultimoRankingFracionado;
    if (!rankingData || !rankingData.ranking_opcoes || !rankingData.ranking_opcoes[opcaoIndex]) {
        console.error('[AGENTE-CLICK] Dados da opção não encontrados');
        return;
    }
    
    const opcao = rankingData.ranking_opcoes[opcaoIndex];
    const detalhes = opcao.detalhes_expandidos || {};
    const agentes = detalhes.agentes_info || {};
    
    // Preparar informações específicas do agente clicado
    let agenteInfo = {};
    let custoEspecifico = 0;
    let nomeAgente = '';
    
    switch(tipoAgente) {
        case 'coleta':
            nomeAgente = agentes.agente_coleta || 'N/A';
            agenteInfo = {
                tipo: 'Agente de Coleta',
                fornecedor: agentes.agente_coleta,
                base: agentes.base_origem !== 'N/A' ? agentes.base_origem : 'Base de Origem',
                funcao: 'Coleta na origem e transporte até a base'
            };
            custoEspecifico = detalhes.custos_detalhados?.custo_coleta || (detalhes.custos_detalhados?.custo_base_frete * 0.3) || 0; // ✅ Custo real da coleta com fallback
            break;
        case 'transferencia':
            nomeAgente = agentes.transferencia || 'N/A';
            agenteInfo = {
                tipo: 'Transferência',
                fornecedor: agentes.transferencia,
                rota: `${agentes.base_origem !== 'N/A' ? agentes.base_origem : 'Origem'} → ${agentes.base_destino !== 'N/A' ? agentes.base_destino : 'Destino'}`,
                funcao: 'Transporte entre bases'
            };
            custoEspecifico = detalhes.custos_detalhados?.custo_transferencia || (detalhes.custos_detalhados?.custo_base_frete * 0.5) || 0; // ✅ Custo real da transferência com fallback
            break;
        case 'entrega':
            nomeAgente = agentes.agente_entrega || 'N/A';
            agenteInfo = {
                tipo: 'Agente de Entrega',
                fornecedor: agentes.agente_entrega,
                base: agentes.base_destino !== 'N/A' ? agentes.base_destino : 'Base de Destino',
                funcao: 'Coleta na base e entrega no destino'
            };
            custoEspecifico = detalhes.custos_detalhados?.custo_entrega || (detalhes.custos_detalhados?.custo_base_frete * 0.2) || 0; // ✅ Custo real da entrega com fallback
            break;
    }
    
    // Montar HTML com informações específicas do agente
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
        custo: custoEspecifico
    };
    
    console.log('[AGENTE-CLICK] Custos específicos exibidos:', agenteInfo);
}

// 🔧 CORREÇÃO 3: Modificar a exibição dos agentes para adicionar onclick
// ✅ SUBSTITUIR as divs dos agentes por estas versões com onclick:

/* 
PROCURAR POR (linha ~1486):
<div style="margin-bottom: 10px; padding: 8px; background: #e8f5e8; border-radius: 4px;">
    <strong>🚛 Agente de Coleta:</strong> ${agentes.agente_coleta}<br>
    ${agentes.base_origem !== 'N/A' ? `<small>Base Destino: ${agentes.base_origem}</small>` : ''}
</div>

SUBSTITUIR POR:
<div onclick="exibirCustosAgente('coleta', ${index})" style="margin-bottom: 10px; padding: 8px; background: #e8f5e8; border-radius: 4px; cursor: pointer; transition: background 0.3s;" onmouseover="this.style.background='#d4ecda'" onmouseout="this.style.background='#e8f5e8'">
    <strong>🚛 Agente de Coleta:</strong> ${agentes.agente_coleta}<br>
    ${agentes.base_origem !== 'N/A' ? `<small>Base Destino: ${agentes.base_origem}</small>` : ''}
    <br><small style="color: #007bff;">👆 Clique para ver custos específicos</small>
</div>
*/

/* 
PROCURAR POR (linha ~1493):
<div style="margin-bottom: 10px; padding: 8px; background: #e3f2fd; border-radius: 4px;">
    <strong>🚚 Transferência:</strong> ${agentes.transferencia}<br>
    ${agentes.base_origem !== 'N/A' && agentes.base_destino !== 'N/A' ? 
      `<small>Rota: ${agentes.base_origem} → ${agentes.base_destino}</small>` : ''}
</div>

SUBSTITUIR POR:
<div onclick="exibirCustosAgente('transferencia', ${index})" style="margin-bottom: 10px; padding: 8px; background: #e3f2fd; border-radius: 4px; cursor: pointer; transition: background 0.3s;" onmouseover="this.style.background='#bbdefb'" onmouseout="this.style.background='#e3f2fd'">
    <strong>🚚 Transferência:</strong> ${agentes.transferencia}<br>
    ${agentes.base_origem !== 'N/A' && agentes.base_destino !== 'N/A' ? 
      `<small>Rota: ${agentes.base_origem} → ${agentes.base_destino}</small>` : ''}
    <br><small style="color: #007bff;">👆 Clique para ver custos específicos</small>
</div>
*/

/* 
PROCURAR POR (linha ~1500):
<div style="margin-bottom: 10px; padding: 8px; background: #fff3e0; border-radius: 4px;">
    <strong>🚛 Agente de Entrega:</strong> ${agentes.agente_entrega}<br>
    ${agentes.base_destino !== 'N/A' ? `<small>Base Origem: ${agentes.base_destino}</small>` : ''}
</div>

SUBSTITUIR POR:
<div onclick="exibirCustosAgente('entrega', ${index})" style="margin-bottom: 10px; padding: 8px; background: #fff3e0; border-radius: 4px; cursor: pointer; transition: background 0.3s;" onmouseover="this.style.background='#ffe0b2'" onmouseout="this.style.background='#fff3e0'">
    <strong>🚛 Agente de Entrega:</strong> ${agentes.agente_entrega}<br>
    ${agentes.base_destino !== 'N/A' ? `<small>Base Origem: ${agentes.base_destino}</small>` : ''}
    <br><small style="color: #007bff;">👆 Clique para ver custos específicos</small>
</div>
*/

// 🔧 CORREÇÃO 4: Adicionar ID ao container de custos
/* 
PROCURAR POR (linha ~1516):
<div style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6;">
    <h5 style="color: #007bff; margin-bottom: 15px; font-size: 1rem;">
        💰 Detalhamento de Custos
    </h5>

SUBSTITUIR POR:
<div style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6;">
    <h5 style="color: #007bff; margin-bottom: 15px; font-size: 1rem;">
        💰 Detalhamento de Custos
    </h5>
    <div id="custos-container-${index}">
*/

// 🔧 CORREÇÃO 5: Fechar a div do container
/* 
PROCURAR POR o final dos custos e ADICIONAR:
    </div> <!-- Fecha custos-container -->
ANTES de:
</div> <!-- Fecha div de detalhamento de custos -->
*/

// 🔧 CORREÇÃO 6: Armazenar dados do ranking para acesso global
/* 
ADICIONAR no final da função exibirRankingFracionado, ANTES de:
container.innerHTML = html;

ADICIONAR:
// Armazenar dados para acesso global
window.ultimoRankingFracionado = ranking;
*/

console.log('📋 Arquivo de correções carregado - aplique as modificações manualmente ao arquivo principal'); 

// 🔧 CORREÇÕES PARA EXIBIÇÃO DE ROTAS FRACIONADAS
// Corrigir exibição das rotas para mostrar bases e tipos de serviço corretos

function exibirResultadosFracionado(dados) {
    console.log('[FRACIONADO] Dados recebidos:', dados);
    
    const ranking = dados.ranking_fracionado;
    if (!ranking || !ranking.ranking_opcoes) {
        console.error('[FRACIONADO] Ranking não encontrado nos dados');
        return;
    }
    
    const container = document.getElementById('resultados-fracionado');
    if (!container) {
        console.error('[FRACIONADO] Container não encontrado');
        return;
    }
    
    let html = `
        <div class="resultado-header">
            <h3>🚛 Frete Fracionado - ${ranking.total_opcoes} Opções Encontradas</h3>
            <div class="info-basica">
                <div><strong>Origem:</strong> ${ranking.origem}</div>
                <div><strong>Destino:</strong> ${ranking.destino}</div>
                <div><strong>Peso:</strong> ${ranking.peso}kg</div>
                <div><strong>Cubagem:</strong> ${ranking.cubagem}m³</div>
                <div><strong>Peso Cubado:</strong> ${ranking.peso_cubado}kg (${ranking.peso_usado_tipo})</div>
                ${ranking.valor_nf ? `<div><strong>Valor NF:</strong> R$ ${ranking.valor_nf.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>` : ''}
            </div>
        </div>
        
        <div class="opcoes-container">
    `;
    
    ranking.ranking_opcoes.forEach((opcao, index) => {
        const detalhes = opcao.detalhes_expandidos || {};
        const custos = detalhes.custos_detalhados || {};
        const agentes = detalhes.dados_agentes || {};
        
        // ✅ EXTRAIR INFORMAÇÕES DE ROTA E BASES
        const rotaBases = opcao.detalhes?.rota_bases || 'Rota não definida';
        const tipoRota = opcao.detalhes?.tipo_rota || 'indefinido';
        
        html += `
            <div class="opcao-fracionado ${opcao.eh_melhor_opcao ? 'melhor-opcao' : ''}">
                <div class="opcao-header">
                    <span class="posicao">${opcao.icone}</span>
                    <div class="opcao-info">
                        <h4>${opcao.tipo_servico}</h4>
                        <div class="rota-info">
                            <strong>ROTA:</strong> ${rotaBases}
                        </div>
                        <div class="fornecedor">${opcao.fornecedor}</div>
                        <div class="descricao">${opcao.descricao}</div>
                    </div>
                    <div class="opcao-valores">
                        <div class="preco-total">R$ ${opcao.custo_total.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>
                        <div class="prazo">Prazo: ${opcao.prazo} ${opcao.prazo === 1 ? 'dia' : 'dias'}</div>
                    </div>
                </div>
                
                <div class="detalhes-expansivel" style="display: none;">
                    ${gerarDetalhesAgentes(agentes, tipoRota)}
                    ${gerarDetalhesCustos(custos)}
                </div>
                
                <button class="btn-expandir" onclick="toggleDetalhes(this)">
                    Ver Detalhes <span class="seta">▼</span>
                </button>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

function gerarDetalhesAgentes(agentes, tipoRota) {
    let html = '<div class="detalhes-agentes"><h5>📋 Detalhes dos Serviços</h5>';
    
    // ✅ AGENTE DE COLETA OU CLIENTE ENTREGA
    const agenteColeta = agentes.agente_coleta || {};
    if (agenteColeta.sem_agente) {
        html += `
            <div class="agente-item cliente-entrega">
                <div class="agente-header">
                    <span class="icone">👤</span>
                    <strong>COLETA: ${agenteColeta.fornecedor}</strong>
                </div>
                <div class="agente-details">
                    <div class="funcao">${agenteColeta.funcao || agenteColeta.observacao}</div>
                    <div class="custo">Custo: R$ 0,00 (Cliente responsável)</div>
                </div>
            </div>
        `;
    } else {
        html += `
            <div class="agente-item agente-coleta">
                <div class="agente-header">
                    <span class="icone">📦</span>
                    <strong>COLETA: ${agenteColeta.fornecedor || 'N/A'}</strong>
                </div>
                <div class="agente-details">
                    <div class="funcao">${agenteColeta.funcao || 'Coleta na origem'}</div>
                    <div class="custo">Custo: R$ ${(agenteColeta.total || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>
                    ${agenteColeta.peso_maximo ? `<div class="limite">Limite: ${agenteColeta.peso_maximo}kg</div>` : ''}
                </div>
            </div>
        `;
    }
    
    // ✅ TRANSFERÊNCIA
    const transferencia = agentes.transferencia || {};
    html += `
        <div class="agente-item transferencia">
            <div class="agente-header">
                <span class="icone">🚛</span>
                <strong>TRANSFERÊNCIA: ${transferencia.fornecedor || 'N/A'}</strong>
            </div>
            <div class="agente-details">
                <div class="funcao">${transferencia.funcao || 'Transferência entre bases'}</div>
                <div class="rota">${transferencia.rota || 'Rota não especificada'}</div>
                <div class="custo">Custo: R$ ${(transferencia.total || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>
                <div class="prazo">Prazo: ${transferencia.prazo || 1} ${transferencia.prazo === 1 ? 'dia' : 'dias'}</div>
            </div>
        </div>
    `;
    
    // ✅ AGENTE DE ENTREGA OU CLIENTE RETIRA
    const agenteEntrega = agentes.agente_entrega || {};
    if (agenteEntrega.sem_agente) {
        html += `
            <div class="agente-item cliente-retira">
                <div class="agente-header">
                    <span class="icone">👤</span>
                    <strong>ENTREGA: ${agenteEntrega.fornecedor}</strong>
                </div>
                <div class="agente-details">
                    <div class="funcao">${agenteEntrega.funcao || agenteEntrega.observacao}</div>
                    <div class="custo">Custo: R$ 0,00 (Cliente responsável)</div>
                </div>
            </div>
        `;
    } else {
        html += `
            <div class="agente-item agente-entrega">
                <div class="agente-header">
                    <span class="icone">🏠</span>
                    <strong>ENTREGA: ${agenteEntrega.fornecedor || 'N/A'}</strong>
                </div>
                <div class="agente-details">
                    <div class="funcao">${agenteEntrega.funcao || 'Entrega no destino'}</div>
                    <div class="custo">Custo: R$ ${(agenteEntrega.total || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>
                    ${agenteEntrega.peso_maximo ? `<div class="limite">Limite: ${agenteEntrega.peso_maximo}kg</div>` : ''}
                    <div class="prazo">Prazo: ${agenteEntrega.prazo || 1} ${agenteEntrega.prazo === 1 ? 'dia' : 'dias'}</div>
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

function gerarDetalhesCustos(custos) {
    return `
        <div class="detalhes-custos">
            <h5>💰 Detalhamento de Custos</h5>
            <div class="custos-grid">
                <div class="custo-item">
                    <span class="label">Coleta:</span>
                    <span class="valor">R$ ${(custos.custo_coleta || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>
                </div>
                <div class="custo-item">
                    <span class="label">Transferência:</span>
                    <span class="valor">R$ ${(custos.custo_transferencia || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>
                </div>
                <div class="custo-item">
                    <span class="label">Entrega:</span>
                    <span class="valor">R$ ${(custos.custo_entrega || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>
                </div>
                <div class="custo-item">
                    <span class="label">Pedágio:</span>
                    <span class="valor">R$ ${(custos.pedagio || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>
                </div>
                <div class="custo-item">
                    <span class="label">GRIS:</span>
                    <span class="valor">R$ ${(custos.gris || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>
                </div>
                <div class="custo-item">
                    <span class="label">Seguro:</span>
                    <span class="valor">R$ ${(custos.seguro || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>
                </div>
                ${custos.tda && custos.tda > 0 ? `
                <div class="custo-item">
                    <span class="label">TDA:</span>
                    <span class="valor">R$ ${custos.tda.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>
                </div>` : ''}
                ${custos.outros && custos.outros > 0 ? `
                <div class="custo-item">
                    <span class="label">Outros:</span>
                    <span class="valor">R$ ${custos.outros.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>
                </div>` : ''}
                <div class="custo-item total">
                    <span class="label"><strong>TOTAL:</strong></span>
                    <span class="valor"><strong>R$ ${(custos.total_custos || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</strong></span>
                </div>
            </div>
        </div>
    `;
}

function toggleDetalhes(botao) {
    const opcao = botao.closest('.opcao-fracionado');
    const detalhes = opcao.querySelector('.detalhes-expansivel');
    const seta = botao.querySelector('.seta');
    
    if (detalhes.style.display === 'none') {
        detalhes.style.display = 'block';
        botao.innerHTML = 'Ocultar Detalhes <span class="seta">▲</span>';
    } else {
        detalhes.style.display = 'none';
        botao.innerHTML = 'Ver Detalhes <span class="seta">▼</span>';
    }
}

// 🔧 ATUALIZAR CSS PARA MELHOR VISUALIZAÇÃO
function adicionarEstilosFracionado() {
    const styles = `
        <style>
        .opcao-fracionado {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        
        .opcao-fracionado.melhor-opcao {
            border-color: #28a745;
            background: #f8fff9;
        }
        
        .opcao-header {
            display: flex;
            align-items: center;
            padding: 15px;
            gap: 15px;
        }
        
        .posicao {
            font-size: 24px;
            font-weight: bold;
        }
        
        .opcao-info {
            flex: 1;
        }
        
        .opcao-info h4 {
            margin: 0 0 5px 0;
            color: #2c3e50;
            font-size: 16px;
        }
        
        .rota-info {
            font-size: 14px;
            color: #007bff;
            margin: 5px 0;
            font-weight: 500;
        }
        
        .fornecedor {
            font-size: 14px;
            color: #6c757d;
            margin: 3px 0;
        }
        
        .opcao-valores {
            text-align: right;
        }
        
        .preco-total {
            font-size: 20px;
            font-weight: bold;
            color: #28a745;
        }
        
        .prazo {
            font-size: 12px;
            color: #6c757d;
            margin-top: 5px;
        }
        
        .detalhes-agentes {
            padding: 15px;
            background: #f1f3f4;
            border-top: 1px solid #dee2e6;
        }
        
        .agente-item {
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            margin-bottom: 10px;
            overflow: hidden;
        }
        
        .agente-header {
            background: #f8f9fa;
            padding: 10px 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 1px solid #e9ecef;
        }
        
        .agente-details {
            padding: 10px 15px;
        }
        
        .agente-details > div {
            margin: 5px 0;
            font-size: 14px;
        }
        
        .cliente-entrega .agente-header {
            background: #fff3cd;
        }
        
        .cliente-retira .agente-header {
            background: #d1ecf1;
        }
        
        .detalhes-custos {
            padding: 15px;
            background: #f8f9fa;
        }
        
        .custos-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }
        
        .custo-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 12px;
            background: white;
            border-radius: 4px;
            border: 1px solid #e9ecef;
        }
        
        .custo-item.total {
            grid-column: 1 / -1;
            background: #e9f7ef;
            border-color: #28a745;
        }
        
        .btn-expandir {
            width: 100%;
            padding: 10px;
            background: #007bff;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.3s ease;
        }
        
        .btn-expandir:hover {
            background: #0056b3;
        }
        </style>
    `;
    
    if (!document.getElementById('estilos-fracionado')) {
        const styleElement = document.createElement('div');
        styleElement.id = 'estilos-fracionado';
        styleElement.innerHTML = styles;
        document.head.appendChild(styleElement);
    }
}

// Inicializar estilos quando o script carregar
adicionarEstilosFracionado();

// ✅ EXPORTAR FUNÇÃO PARA USO GLOBAL
window.exibirResultadosFracionado = exibirResultadosFracionado; 