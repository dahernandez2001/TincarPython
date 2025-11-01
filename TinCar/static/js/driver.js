document.addEventListener("DOMContentLoaded", () => {
  console.log("Modo conductor cargado correctamente");

  // Inicializar mapa Leaflet
  const defaultLat = 4.60971; // Bogotá como centro por defecto
  const defaultLng = -74.08175;
  const map = L.map('map').setView([defaultLat, defaultLng], 12);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap'
  }).addTo(map);

  // Cargar parkings activos desde la API
  // Mejor estrategia: cargar sólo parkings dentro del viewport actual y refrescar cuando el mapa se mueva.
  const markersGroup = L.layerGroup().addTo(map);

  function debounce(fn, wait){
    let t = null;
    return function(...args){
      clearTimeout(t);
      t = setTimeout(()=> fn.apply(this, args), wait);
    };
  }

  async function loadParkingsForBounds(){
    const b = map.getBounds();
    const minLat = b.getSouth();
    const minLng = b.getWest();
    const maxLat = b.getNorth();
    const maxLng = b.getEast();
    const bbox = `${minLat},${minLng},${maxLat},${maxLng}`;
    try{
      const r = await fetch('/api/parkings/active?bbox='+encodeURIComponent(bbox));
      if(!r.ok) throw new Error('HTTP '+r.status);
      const data = await r.json();
      if(!data.success) { console.error('Error cargando parkings:', data.error); return; }
      const parkings = data.parkings || [];
      // limpiar markers existentes
      markersGroup.clearLayers();
      parkings.forEach(p => {
        const lat = p.latitude !== null && p.latitude !== undefined ? parseFloat(p.latitude) : null;
        const lng = p.longitude !== null && p.longitude !== undefined ? parseFloat(p.longitude) : null;
        if(!isNaN(lat) && !isNaN(lng)){
          // usar circleMarker (más ligero) y color según disponibilidad
          const isAvailable = true; // endpoint ya filtra por active
          const marker = L.circleMarker([lat,lng], { radius: 6, color: isAvailable ? '#2b8a3e' : '#b30000', fillOpacity: 0.9 });
          const fullAddress = `${p.address || ''}${p.city ? ', ' + p.city : ''}${p.department ? ', ' + p.department : ''}`;
          const popupHtml = `<strong>${p.name || 'Parqueadero'}</strong><br>${fullAddress || ''}<br><button class="btn-reserve" onclick="reserveParking(${p.id})">Reservar</button>`;
          marker.bindPopup(popupHtml);
          markersGroup.addLayer(marker);
        }
      });
    }catch(err){
      console.error('Error loading parkings for bounds:', err);
    }
  }

  const debouncedLoad = debounce(loadParkingsForBounds, 400);
  // cargar inicialmente
  loadParkingsForBounds();
  // recargar cuando el usuario termine de mover/zoom
  map.on('moveend', debouncedLoad);
  map.on('zoomend', debouncedLoad);

  // Cargar estadísticas del conductor (reservas y calificación)
  fetch('/api/driver/stats')
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        const countEl = document.getElementById('reservations-count');
        const ratingEl = document.getElementById('rating-sum');
        if (countEl) countEl.textContent = data.reservations_count || 0;
        if (ratingEl) ratingEl.textContent = data.rating_sum || 0;
      } else {
        console.warn('No se pudieron cargar stats del conductor:', data.error);
      }
    })
    .catch(err => console.error('Fetch driver stats failed', err));

  function refreshActiveParkings() {
    fetch('/api/parkings/active')
      .then(r => {
        if (!r.ok) {
          throw new Error(`HTTP error! status: ${r.status}`);
        }
        return r.json();
      })
      .then(data => {
        if (data.success) {
          map.eachLayer(layer => {
            if (layer instanceof L.Marker) {
              map.removeLayer(layer);
            }
          });
          const parkings = data.parkings || [];
            parkings.forEach(p => {
              const lat = p.latitude !== null && p.latitude !== undefined ? parseFloat(p.latitude) : null;
              const lng = p.longitude !== null && p.longitude !== undefined ? parseFloat(p.longitude) : null;
              if (!isNaN(lat) && !isNaN(lng)) {
                const marker = L.marker([lat, lng]).addTo(map);
                const popupHtml = `<strong>${p.name || 'Parqueadero'}</strong><br>${p.address || ''}<br><button class="btn-reserve" onclick="reserveParking(${p.id})">Reservar</button>`;
                marker.bindPopup(popupHtml);
              }
            });
        } else {
          console.error('Error cargando garajes activos:', data.error);
        }
      })
      .catch(err => console.error('Error al refrescar garajes activos:', err));
  }

  function activateParking(parkingId) {
    fetch(`/parkings/${parkingId}/active`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: true })
    })
      .then(r => {
        if (!r.ok) {
          throw new Error(`HTTP error! status: ${r.status}`);
        }
        return r.json();
      })
      .then(data => {
        if (data.success) {
          refreshActiveParkings();
        } else {
          console.error('Error activando parqueadero:', data.error);
        }
      })
      .catch(err => console.error('Error en la activación del parqueadero:', err));
  }

  document.addEventListener('DOMContentLoaded', () => {
    refreshActiveParkings();
  });
});
    // Exponer función global para que los popups puedan llamar a la reserva
    window.reserveParking = function(parkingId){
      if(!parkingId){
        alert('ID de parqueadero inválido');
        return;
      }
      // Confirmación mínima
      if(!confirm('¿Deseas reservar este parqueadero ahora?')) return;
      fetch('/api/reservations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parking_id: parkingId })
      })
      .then(r => r.json().then(j => ({ok: r.ok, status: r.status, json: j})))
      .then(({ok, json}) => {
        if(ok && json.success){
          alert('Reserva creada correctamente. ID: ' + (json.reservation && json.reservation.id ? json.reservation.id : 'N/A'));
          // opción: refrescar estadísticas del conductor
          fetch('/api/driver/stats').then(r=>r.json()).then(d=>{
            if(d.success){
              const countEl = document.getElementById('reservations-count');
              if(countEl) countEl.textContent = d.reservations_count || 0;
            }
          }).catch(()=>{});
        } else {
          alert('No se pudo crear la reserva: ' + (json.error || 'error'));
        }
      })
      .catch(err => alert('Error al crear reserva: '+err.message));
    };
