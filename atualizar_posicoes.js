
// Código JavaScript para atualizar posições das siglas
function atualizarPosicoesSiglas() {
    const posicoesCorrigidas = {
        "AC": {x: 55.0, y: 240.0},
        "AL": {x: 568.0, y: 235.0},
        "AM": {x: 212.4, y: 139.7},
        "AP": {x: 285.0, y: 128.0},
        "BA": {x: 527.0, y: 270.0},
        "CE": {x: 548.0, y: 168.0},
        "DF": {x: 422.0, y: 325.3},
        "ES": {x: 492.0, y: 415.0},
        "GO": {x: 390.0, y: 350.0},
        "MA": {x: 458.0, y: 180.0},
        "MG": {x: 470.0, y: 370.0},
        "MS": {x: 315.0, y: 455.0},
        "MT": {x: 275.0, y: 310.0},
        "PA": {x: 328.0, y: 160.0},
        "PB": {x: 602.5, y: 208.0},
        "PE": {x: 539.3, y: 220.0},
        "PI": {x: 505.0, y: 185.0},
        "PR": {x: 390.0, y: 505.0},
        "RJ": {x: 458.0, y: 455.0},
        "RN": {x: 587.5, y: 165.0},
        "RO": {x: 158.0, y: 285.0},
        "RR": {x: 245.0, y: 118.0},
        "RS": {x: 358.0, y: 588.0},
        "SC": {x: 378.0, y: 548.0},
        "SE": {x: 568.0, y: 265.0},
        "SP": {x: 435.0, y: 475.0},
        "TO": {x: 415.0, y: 238.0},
    };
    
    // Aplicar posições
    Object.entries(posicoesCorrigidas).forEach(([sigla, pos]) => {
        const elemento = document.querySelector(`.estado-sigla:contains("${sigla}")`);
        if (elemento) {
            elemento.setAttribute('x', pos.x);
            elemento.setAttribute('y', pos.y);
        }
    });
    
    // Salvar no localStorage
    localStorage.setItem('siglas_positions', JSON.stringify(posicoesCorrigidas));
    
    console.log('✅ Posições das siglas atualizadas com sucesso!');
}

// Executar atualização
atualizarPosicoesSiglas();
