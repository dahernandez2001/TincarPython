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
      const seen = new Set();
      parkings.forEach(p => {
        const lat = p.latitude !== null && p.latitude !== undefined ? parseFloat(p.latitude) : null;
        const lng = p.longitude !== null && p.longitude !== undefined ? parseFloat(p.longitude) : null;
          if(!isNaN(lat) && !isNaN(lng)){
            const key = `${lat.toFixed(6)},${lng.toFixed(6)}`;
            if(seen.has(key)) return; // evitar duplicados en la misma coordenada
            seen.add(key);
            // usar circleMarker (más ligero) y color según disponibilidad
            const isAvailable = true; // endpoint ya filtra por active
            const marker = L.circleMarker([lat,lng], { radius: 6, color: isAvailable ? '#2b8a3e' : '#b30000', fillOpacity: 0.9 });
            // En lugar de un popup pequeño, abrimos un modal más rico (similar al del arrendador)
            marker.on('click', ()=>{
              openDriverModalWithParking(p);
            });
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
    // Reuse the bounds-loading implementation to avoid duplicate markers
    try{
      loadParkingsForBounds();
    }catch(err){ console.error('Error al refrescar garajes activos:', err); }
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

  // no separate DOMContentLoaded listener here; initial load already performed
});
    // Exponer función global para que los popups puedan llamar a la reserva
    window.reserveParking = function(parkingId, durationMinutes, etaMinutes){
      if(!parkingId){
        alert('ID de parqueadero inválido');
        return;
      }
      // Normalizar y validaciones mínimas
      try{ durationMinutes = parseInt(durationMinutes); }catch(e){ durationMinutes = 10; }
      if(isNaN(durationMinutes) || durationMinutes < 10) durationMinutes = 10;
      try{ etaMinutes = parseInt(etaMinutes); }catch(e){ etaMinutes = 0; }
      if(isNaN(etaMinutes) || etaMinutes < 0) etaMinutes = 0;
      if(!confirm(`Reservar ${durationMinutes} min. ¿Confirmas?`)) return;
      fetch('/api/reservations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parking_id: parkingId, duration_minutes: durationMinutes, eta_minutes: etaMinutes })
      })
      .then(r => r.json().then(j => ({ok: r.ok, status: r.status, json: j})))
      .then(({ok, json}) => {
        if(ok && json.success){
          alert('Reserva creada correctamente. ID: ' + (json.reservation && json.reservation.id ? json.reservation.id : 'N/A'));
          // refrescar estadísticas del conductor
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

  // ===== Modal conductor =====
  const driverModal = document.getElementById('driverParkingModal');
  const driverClose = document.getElementById('closeDriverModal');
  const driverCancel = document.getElementById('dp-cancel');
  const driverReserveBtn = document.getElementById('dp-reserve');

  function openDriverModal(){
    if(!driverModal) return;
    driverModal.classList.add('open');
    driverModal.setAttribute('aria-hidden','false');
  }
  function closeDriverModal(){
    if(!driverModal) return;
    driverModal.classList.remove('open');
    driverModal.setAttribute('aria-hidden','true');
  }

  driverClose && driverClose.addEventListener('click', closeDriverModal);
  driverCancel && driverCancel.addEventListener('click', closeDriverModal);

  // Rellenar modal con los datos del parqueadero
  function openDriverModalWithParking(p){
    try{
  // populate inputs (use .value since they are inputs now)
  document.getElementById('dp-id').value = p.id;
  const setIf = (id, value) => { const el = document.getElementById(id); if(!el) return; el.value = value || ''; };
  setIf('dp-name', p.name || '');
  setIf('dp-phone', p.phone || '');
  setIf('dp-email', p.email || '');
  setIf('dp-address', p.address || '');
  setIf('dp-department', p.department || '');
  setIf('dp-city', p.city || '');
  setIf('dp-latitude', p.latitude !== null && p.latitude !== undefined ? p.latitude : '');
  setIf('dp-longitude', p.longitude !== null && p.longitude !== undefined ? p.longitude : '');
  setIf('dp-housing_type', p.housing_type || '');
  setIf('dp-size', p.size || '');
  setIf('dp-features', p.features || '');
  const imgContainer = document.getElementById('dp-image');
      if(imgContainer){
        if(p.image_path){
          imgContainer.innerHTML = `<img src="${p.image_path}" alt="img" style="max-width:220px; max-height:160px; border-radius:6px;">`;
        } else {
          imgContainer.innerHTML = `<div style="font-size:64px; opacity:0.2;">🏠</div>`;
        }
      }
      // Comprobar si el conductor ya tiene una reserva para este parqueadero
      // y ajustar el botón a "Cancelar reserva" si aplica.
  const reserveBtn = document.getElementById('dp-reserve');
      const prevFocus = document.activeElement;

      function setReserveActionToCreate(){
        if(!reserveBtn) return;
        reserveBtn.textContent = 'Reservar';
        reserveBtn.onclick = function(){
          const durEl = document.getElementById('dp-duration');
          const etaEl = document.getElementById('dp-eta');
          const dur = durEl ? parseInt(durEl.value) : 10;
          const eta = etaEl ? parseInt(etaEl.value) : 0;
          window.reserveParking(p.id, dur, eta);
          closeDriverModal();
        };
      }

      function cancelReservationById(resId){
        if(!resId) return;
        if(!confirm('¿Deseas cancelar la reserva?')) return;
        fetch(`/api/reservations/${resId}/cancel`, { method: 'POST' })
          .then(r => r.json().then(j=>({ok: r.ok, json: j})))
          .then(({ok, json}) => {
            if(ok && json.success){
              alert('Reserva cancelada.');
              // refrescar stats
              fetch('/api/driver/stats').then(r=>r.json()).then(d=>{ if(d.success){ const countEl = document.getElementById('reservations-count'); if(countEl) countEl.textContent = d.reservations_count || 0; } }).catch(()=>{});
              // limpiar info de reserva en modal
              const ri = document.getElementById('dp-reservation-info'); if(ri) ri.textContent = '';
            } else {
              alert('No se pudo cancelar la reserva: ' + (json.error||'error'));
            }
          })
          .catch(err=> alert('Error cancelando reserva: '+err.message));
      }

      // Por defecto, asignar acción de crear reserva
      setReserveActionToCreate();
      // Consultar si hay reserva existente
      fetch('/api/reservations?parking_id='+encodeURIComponent(p.id))
        .then(r => r.json())
        .then(data => {
          if(data && data.success && data.exists && data.reservation){
            // Si existe y no está cancelada, mostrar opción de cancelar
            if(data.reservation.status !== 'cancelled'){
              reserveBtn.textContent = 'Cancelar reserva';
              reserveBtn.onclick = function(){
                cancelReservationById(data.reservation.id);
                closeDriverModal();
              };
              // mostrar info de reserva en el placeholder
              const ri = document.getElementById('dp-reservation-info');
              if(ri){
                let text = `Reserva existente (ID: ${data.reservation.id}) - estado: ${data.reservation.status}`;
                if(data.reservation.duration_minutes) text += ` · duración: ${data.reservation.duration_minutes} min`;
                if(data.reservation.eta_minutes !== undefined) text += ` · ETA: ${data.reservation.eta_minutes} min`;
                ri.textContent = text;
              }
            }
          }
        }).catch(()=>{}).finally(()=>{
          // accesibilidad: focus al botón y almacenar foco previo
          try{ if(reserveBtn){ reserveBtn.focus(); } }catch(e){}
        });

      // cerrar con Escape y restablecer foco
      function onKeyDown(e){ if(e.key === 'Escape'){ closeDriverModal(); } }
      document.addEventListener('keydown', onKeyDown);
      // cuando se cierre el modal, quitar listener y restaurar foco
      const restore = function(){
        document.removeEventListener('keydown', onKeyDown);
        try{ if(prevFocus && prevFocus.focus) prevFocus.focus(); }catch(e){}
        // quitar este handler para evitar fugas
        driverModal.removeEventListener('transitionend', restore);
      };
      driverModal.addEventListener('transitionend', restore);

      openDriverModal();
    }catch(err){ console.error('openDriverModalWithParking error', err); }
  }
