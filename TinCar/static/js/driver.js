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
  fetch('/api/parkings/active')
    .then(r => {
      if (!r.ok) {
        throw new Error(`HTTP error! status: ${r.status}`);
      }
      return r.json();
    })
    .then(data => {
      if (!data.success) {
        console.error('Error cargando parkings:', data.error);
        return;
      }
      const parkings = data.parkings || [];
      parkings.forEach(p => {
        const lat = p.latitude;
        const lng = p.longitude;
        if (lat && lng) {
          const marker = L.marker([lat, lng]).addTo(map);
          const popupHtml = `
            <strong>${p.name || 'Parqueadero'}</strong><br>
            ${p.address || ''}<br>
            <button onclick="reserveParking(${p.id})">Reservar</button>
          `;
          marker.bindPopup(popupHtml);
        } else {
          // Si no hay coordenadas, se podría ampliar para geocodificar la dirección.
          console.warn('Parqueadero sin coordenas, omitiendo en mapa:', p.name);
        }
      });
      // Ajustar bounds si hay marcadores
      const markers = parkings.filter(p => p.latitude && p.longitude);
      if (markers.length) {
        const latlngs = markers.map(p => [p.latitude, p.longitude]);
        const bounds = L.latLngBounds(latlngs);
        map.fitBounds(bounds, {padding: [50, 50]});
      }
    })
    .catch(err => console.error('Fetch parkings failed:', err));

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
            const lat = p.latitude;
            const lng = p.longitude;
            if (lat && lng) {
              const marker = L.marker([lat, lng]).addTo(map);
              const popupHtml = `<strong>${p.name || 'Parqueadero'}</strong><br>${p.address || ''}`;
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
