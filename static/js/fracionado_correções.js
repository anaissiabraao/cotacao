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
                base: agentes.base_origem,
                funcao: 'Coleta na origem e transporte até a base'
            };
            custoEspecifico = detalhes.custos_detalhados?.custo_base_frete * 0.3 || 0; // 30% do custo base
            break;
        case 'transferencia':
            nomeAgente = agentes.transferencia || 'N/A';
            agenteInfo = {
                tipo: 'Transferência',
                fornecedor: agentes.transferencia,
                rota: `${agentes.base_origem} → ${agentes.base_destino}`,
                funcao: 'Transporte entre bases'
            };
            custoEspecifico = detalhes.custos_detalhados?.custo_base_frete * 0.5 || 0; // 50% do custo base
            break;
        case 'entrega':
            nomeAgente = agentes.agente_entrega || 'N/A';
            agenteInfo = {
                tipo: 'Agente de Entrega',
                fornecedor: agentes.agente_entrega,
                base: agentes.base_destino,
                funcao: 'Coleta na base e entrega no destino'
            };
            custoEspecifico = detalhes.custos_detalhados?.custo_base_frete * 0.2 || 0; // 20% do custo base
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
                <span>💼 Custo Base Frete:</span>
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