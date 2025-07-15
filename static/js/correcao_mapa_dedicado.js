// Função para verificar se o Leaflet está carregado
function verificarLeaflet() {
    if (typeof L === 'undefined') {
        return false;
    }
    return true;
}

// Função para garantir que o container está visível
function garantirContainerVisivel(container) {
    if (!container) return false;
    
    // Forçar visibilidade
    container.style.display = 'block';
    container.style.visibility = 'visible';
    container.style.opacity = '1';
    container.style.height = '400px';
    container.style.width = '100%';
    container.style.position = 'relative';
    container.style.zIndex = '1';
    
    // Remover classes que possam ocultar
    container.classList.remove('hidden');
    container.classList.remove('d-none');
    
    return container.offsetHeight > 0;
}

// Função principal de inicialização do mapa
window.initializeDedicadoMap = function(routePoints, mapId = 'map-dedicado') {
    const mapContainer = document.getElementById(mapId);

    if (!mapContainer) {
        return;
    }

    mapContainer.style.display = 'block';
    mapContainer.style.height = '400px';
    mapContainer.classList.remove('hidden');

    // Remove mapa anterior se existir
    if (window[mapId] && window[mapId].remove) {
        window[mapId].remove();
        window[mapId] = null;
    }

    if (!Array.isArray(routePoints) || routePoints.length < 2) {
        mapContainer.innerHTML = '<div style="color:#e53935;font-weight:600;text-align:center;padding:20px;">Nenhuma rota disponível para exibir o mapa.</div>';
        return;
    }

    window[mapId] = L.map(mapId).setView(routePoints[0], 7);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: 'Map data © OpenStreetMap contributors'
    }).addTo(window[mapId]);

    const latlngs = routePoints.map(pt => [pt[0], pt[1]]);
    const polyline = L.polyline(latlngs, {color: 'blue', weight: 5}).addTo(window[mapId]);

    window[mapId].fitBounds(polyline.getBounds(), {padding: [30, 30]});

    L.marker(latlngs[0]).addTo(window[mapId]).bindPopup('Origem').openPopup();
    L.marker(latlngs[latlngs.length - 1]).addTo(window[mapId]).bindPopup('Destino');
};

// Exportar função
window.initializeDedicadoMap = initializeDedicadoMap; 