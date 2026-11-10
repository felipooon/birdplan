// BirdRuta Los Lagos - Route Planner & Map Integration

let routeMap = null;
let routeLayerGroup = null;
let currentRouteData = null;

function initRouteMap() {
  if (routeMap) return;

  const mapElement = document.getElementById('routeMap');
  if (!mapElement) return;

  // Center on Región de Los Lagos (Lake Llanquihue area)
  routeMap = L.map('routeMap', {
    center: [-41.35, -73.05],
    zoom: 9,
    zoomControl: true
  });

  // Base map tile layers (100% free, no API key required)
  const osmStandard = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
  });

  const esriSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: '&copy; Esri, Maxar, Earthstar Geographics',
    maxZoom: 18
  });

  const openTopo = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://opentopomap.org">OpenTopoMap</a>',
    maxZoom: 17
  });

  // Add OpenStreetMap by default
  osmStandard.addTo(routeMap);

  // Add layer switcher control in top-right
  const baseLayers = {
    'Mapa Callejero (OSM)': osmStandard,
    'Satélite Aéreo (Esri)': esriSatellite,
    'Topográfico (Relieve)': openTopo
  };

  L.control.layers(baseLayers, null, { position: 'topright' }).addTo(routeMap);

  routeLayerGroup = L.layerGroup().addTo(routeMap);
}

// Custom Leaflet marker icons with numbers and habitat colors
function createCustomPin(number, color = '#10b981') {
  return L.divIcon({
    className: 'custom-map-pin',
    html: `
      <div style="
        background: ${color};
        color: #fff;
        width: 32px;
        height: 32px;
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        border: 2px solid #ffffff;
      ">
        <span style="
          transform: rotate(45deg);
          font-family: 'Outfit', sans-serif;
          font-weight: 700;
          font-size: 13px;
        ">${number}</span>
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 32],
    popupAnchor: [0, -32]
  });
}

async function generateOptimalRoute() {
  const btn = document.getElementById('btnCalculateRoute');
  const btnText = document.getElementById('btnCalculateRouteText');
  const spinner = document.getElementById('btnCalculateRouteSpinner');

  const hub = document.getElementById('routeHub').value;
  const subzone = document.getElementById('routeSubzone').value;
  const focus = document.getElementById('routeFocus').value;
  const duration = parseFloat(document.getElementById('routeDuration').value);
  const maxStops = parseInt(document.getElementById('routeStops').value);
  const startTime = document.getElementById('routeStartTime').value;
  const pace = document.getElementById('routePace') ? document.getElementById('routePace').value : 'blitz';

  btn.disabled = true;
  btnText.textContent = 'Calculando ruta para 10 de Octubre...';
  spinner.style.display = 'inline-block';

  const targetDate = document.getElementById('routeDate')?.value || '2026-10-10';

  try {
    const res = await fetch('/api/route/optimize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        hub,
        date: targetDate,
        subzone,
        focus,
        duration_hours: duration,
        max_stops: maxStops,
        start_time: startTime,
        pace: pace,
        is_big_day: maxStops >= 7 || pace === 'blitz'
      })
    });

    if (!res.ok) throw new Error('Error al optimizar la ruta');

    const data = await res.json();
    currentRouteData = data;
    renderRouteResults(data);
  } catch (err) {
    console.error(err);
    alert('No se pudo generar la ruta. Verifica la conexión o los parámetros.');
  } finally {
    btn.disabled = false;
    btnText.textContent = 'Calcular Ruta Óptima';
    spinner.style.display = 'none';
  }
}

function renderRouteResults(data) {
  const summary = data.summary;
  const stops = data.stops;

  // Render Metric Ribbon
  document.getElementById('metricSpeciesCount').textContent = `${summary.estimated_total_species}+`;
  document.getElementById('metricTotalKm').textContent = `${summary.total_km} km`;
  document.getElementById('metricBirdingTime').textContent = `${Math.round(summary.total_birding_minutes / 60)}h ${summary.total_birding_minutes % 60}m (${summary.birding_minutes_per_stop || 35}m/stop)`;
  document.getElementById('metricSunTimes').textContent = `${summary.sunrise} / ${summary.sunset}`;

  const tideEl = document.getElementById('metricTideTimes');
  if (tideEl) {
    if (summary.tides && summary.tides.events && summary.tides.events.length >= 3) {
      const b1 = summary.tides.events[1];
      const p2 = summary.tides.events[2];
      tideEl.textContent = `Baja ${b1.time} (${b1.height_m}m) / Alta ${p2.time} (${p2.height_m}m)`;
    } else {
      tideEl.textContent = 'Baja 07:55 (0.7m) / Alta 14:15 (6.5m)';
    }
  }

  // Update Map
  initRouteMap();
  routeLayerGroup.clearLayers();

  const latlngs = [];

  // Start point
  const origin = data.origin;
  latlngs.push([origin.lat, origin.lng]);

  const originMarker = L.marker([origin.lat, origin.lng], {
    icon: createCustomPin('★', '#06b6d4')
  }).bindPopup(`
    <div style="font-family: sans-serif; padding: 4px;">
      <b style="color: #0284c7;">Punto de Partida / Retorno</b>
      <p style="margin: 4px 0 0 0; font-size: 13px;">${origin.name}</p>
    </div>
  `);
  routeLayerGroup.addLayer(originMarker);

  // Stop pins
  stops.forEach((stop, i) => {
    latlngs.push([stop.lat, stop.lng]);

    const marker = L.marker([stop.lat, stop.lng], {
      icon: createCustomPin(stop.stop_number, '#10b981')
    }).bindPopup(`
      <div style="font-family: sans-serif; min-width: 220px; padding: 4px;">
        <div style="font-size: 11px; text-transform: uppercase; color: #10b981; font-weight: 700;">
          Parada ${stop.stop_number} (${stop.arrival_time} - ${stop.departure_time})
        </div>
        <h4 style="margin: 4px 0; font-size: 14px; font-weight: 700; color: #0f172a;">${stop.locName}</h4>
        <div style="font-size: 12px; color: #475569; margin-bottom: 6px;">
          ${stop.habitat_label}
        </div>
        <div style="font-size: 12px; background: #f1f5f9; padding: 6px; border-radius: 6px; margin-bottom: 8px;">
          <b>${stop.activity.temp_c}°C</b> | Lluvia: <b>${stop.activity.rain_prob}%</b> | Viento: <b>${stop.activity.wind_kmh} km/h</b>
          ${stop.tide ? `<div style="margin-top: 4px; color: #0284c7; font-weight: 600;">Marea: ${stop.tide.status_label} (${stop.tide.height_m}m)</div>` : ''}
        </div>
        <a href="https://ebird.org/hotspot/${stop.locId}" target="_blank" style="color: #0284c7; text-decoration: none; font-size: 12px; font-weight: 600;">
          Ver hotspot en eBird ↗
        </a>
      </div>
    `);
    routeLayerGroup.addLayer(marker);
  });

  // Polyline back to start
  latlngs.push([origin.lat, origin.lng]);

  const polyline = L.polyline(latlngs, {
    color: '#10b981',
    weight: 4,
    opacity: 0.8,
    dashArray: '8, 8',
    lineCap: 'round'
  }).addTo(routeLayerGroup);

  routeMap.fitBounds(polyline.getBounds(), { padding: [50, 50] });

  // Render Timeline Stops
  const timelineEl = document.getElementById('timelineContainer');
  let timelineHtml = '';

  if (summary.is_big_day || stops.length >= 7) {
    timelineHtml += `
      <div style="background: linear-gradient(135deg, rgba(217, 119, 6, 0.2), rgba(16, 185, 129, 0.12)); border: 1px solid rgba(217, 119, 6, 0.4); padding: 1.1rem 1.35rem; border-radius: 14px; margin-bottom: 1.5rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem;">
        <div>
          <span style="font-size: 0.75rem; background: var(--amber); color: #000; font-weight: 800; padding: 2px 8px; border-radius: 9999px; text-transform: uppercase;">MODO BIG DAY SUR DE CHILE</span>
          <h4 style="font-family: var(--font-heading); font-size: 1.15rem; margin-top: 4px; color: var(--text-primary);">Maratón: ${stops.length} Hotspots Estratégicos (10 de Octubre)</h4>
          <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 2px;">Ritmo continuo de <b>${summary.birding_minutes_per_stop || 35} min</b> por parada. Paradas encadenadas por proximidad para maximizar la ventana de luz.</p>
        </div>
        <div style="text-align: right; background: rgba(0,0,0,0.06); padding: 8px 16px; border-radius: 10px; border: 1px solid rgba(245, 158, 11, 0.3);">
          <div style="font-size: 1.8rem; font-weight: 800; color: var(--amber); font-family: var(--font-heading); line-height: 1;">${summary.estimated_total_species}+</div>
          <div style="font-size: 0.7rem; color: var(--text-secondary); text-transform: uppercase; font-weight: 600; margin-top: 3px;">Meta de Especies</div>
        </div>
      </div>
    `;
  }

  stops.forEach((stop, idx) => {
    const isPeak = stop.activity.is_peak_window;
    const peakBadge = isPeak
      ? `<span style="background: rgba(245, 158, 11, 0.15); color: var(--amber); padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 700; border: 1px solid rgba(245, 158, 11, 0.4);">Pico de Actividad Aviar</span>`
      : `<span style="background: rgba(6, 182, 212, 0.12); color: var(--cyan); padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">Actividad Normal</span>`;

    const rainColor = stop.activity.rain_prob > 40 ? '#f43f5e' : '#10b981';

    const tideBadge = stop.tide ? `
      <div class="weather-chip" style="border-color: rgba(2, 132, 199, 0.4); background: rgba(2, 132, 199, 0.08);" title="${stop.tide.note}">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 3px;">
          <path d="M2 12c2.5-3 5-3 7 0s4.5 3 7 0 4.5-3 6 0"/><path d="M2 18c2.5-3 5-3 7 0s4.5 3 7 0 4.5-3 6 0"/>
        </svg>
        <span style="color: #0284c7; font-weight: 700;">Marea: ${stop.tide.status_label} (${stop.tide.height_m}m)</span>
      </div>
    ` : '';

    const tideAlert = stop.tide ? `
      <div style="font-size: 0.77rem; color: #0369a1; background: rgba(2, 132, 199, 0.07); padding: 5px 10px; border-radius: 6px; margin-top: 8px; border-left: 3px solid #0284c7; display: flex; align-items: center; gap: 6px;">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0;">
          <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
        </svg>
        <span><b>Dinámica Intermareal (10 Oct):</b> ${stop.tide.note}</span>
      </div>
    ` : '';

    let birdPills = '';
    stop.target_species.forEach(sp => {
      const isTarget = sp.isTarget;
      birdPills += `
        <span class="bird-pill ${isTarget ? 'target-highlight' : ''}">
          <b>${sp.comName}</b>
          <span class="sci-name">(${sp.sciName})</span>
          ${isTarget ? `<span style="color: var(--amber); font-size: 10px; margin-left: 2px;">[${sp.rarity}]</span>` : ''}
        </span>
      `;
    });

    timelineHtml += `
      ${idx > 0 ? `
        <div class="drive-connector">
          <span class="line"></span>
          <span>${stop.distance_from_prev_km} km • ~${stop.drive_time_from_prev_min} min de traslado</span>
          <span class="line"></span>
        </div>
      ` : ''}

      <div class="timeline-step">
        <div class="timeline-time-col">
          <div class="time-badge">${stop.arrival_time}</div>
          <div class="duration-label">${stop.birding_minutes} min pajareo</div>
          <div class="time-badge" style="color: var(--text-muted); font-size: 0.75rem;">${stop.departure_time}</div>
        </div>

        <div class="timeline-card">
          <div class="stop-header">
            <div>
              <span class="stop-number-badge">${stop.stop_number}</span>
              <span class="stop-title">${stop.locName}</span>
              <div class="habitat-badge">${stop.habitat_label}</div>
            </div>
            
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
              ${peakBadge}
              ${tideBadge}
              <div class="weather-chip">
                <span class="temp">${stop.activity.temp_c}°C</span>
                <span class="rain" style="color: ${rainColor};">Lluvia: ${stop.activity.rain_prob}%</span>
                <span class="wind">Viento: ${stop.activity.wind_kmh} km/h</span>
              </div>
            </div>
          </div>
          ${tideAlert}

          <div style="margin-top: 0.75rem;">
            <div style="font-size: 0.8rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em;">
              Especies Clave a Buscar en esta parada (${stop.target_species.length}):
            </div>
            <div class="target-species-list">
              ${birdPills}
            </div>
          </div>

          <div style="margin-top: 0.85rem; display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: var(--text-muted); border-top: 1px solid var(--border-color); padding-top: 0.6rem;">
            <span>Total histórico de especies registradas: <b>${stop.numSpeciesAllTime}</b></span>
            <a href="https://ebird.org/hotspot/${stop.locId}" target="_blank" style="color: var(--cyan); text-decoration: none; font-weight: 600;">
              Ver Hotspot en eBird.org ↗
            </a>
          </div>
        </div>
      </div>
    `;
  });

    timelineEl.innerHTML = timelineHtml;
  document.getElementById('routeResultsSection').style.display = 'block';

  // Render Master Probable Species Checklist
  currentProbableSpecies = data.all_probable_species || [];
  renderProbableSpeciesChecklist(currentProbableSpecies);

  // Smooth scroll to map
  document.getElementById('routeResultsSection').scrollIntoView({ behavior: 'smooth' });
}

// Master Probable Species Checklist Logic
let currentProbableSpecies = [];
let checkedSpecies = new Set();
let currentGroupFilter = 'all';

function renderProbableSpeciesChecklist(speciesList) {
  const container = document.getElementById('probableSpeciesContainer');
  if (!container) return;

  const countBadge = document.getElementById('checklistProgressBadge');
  const subtitle = document.getElementById('masterChecklistSubtitle');

  const total = currentProbableSpecies.length;
  const checked = checkedSpecies.size;

  if (countBadge) {
    countBadge.textContent = `✓ ${checked} / ${total} Registradas`;
  }

  if (subtitle) {
    subtitle.textContent = `Mostrando ${speciesList.length} de ${total} especies probables para esta ruta en Región de Los Lagos`;
  }

  if (!speciesList || speciesList.length === 0) {
    container.innerHTML = `
      <div style="padding: 2.5rem; text-align: center; color: var(--text-muted);">
        <p>No se encontraron especies con los filtros seleccionados.</p>
      </div>
    `;
    return;
  }

  let html = `<div class="checklist-table-wrapper">`;

  speciesList.forEach((sp, idx) => {
    const isChecked = checkedSpecies.has(sp.speciesCode);
    const probClass = sp.probability.toLowerCase().replace(/[^a-z]/g, '-').replace('muy-alta', 'muy-alta');
    let probTagClass = 'ocasional';
    if (sp.probability.includes('Muy Alta')) probTagClass = 'muy-alta';
    else if (sp.probability.includes('Alta')) probTagClass = 'alta';
    else if (sp.probability.includes('Media')) probTagClass = 'media';

    html += `
      <div class="checklist-item-row ${isChecked ? 'checked' : ''}" id="row_sp_${sp.speciesCode}">
        <input 
          type="checkbox" 
          class="checklist-checkbox" 
          ${isChecked ? 'checked' : ''} 
          onchange="toggleSpeciesCheck('${sp.speciesCode}')"
          id="chk_${sp.speciesCode}"
        >
        <div class="spp-name-col">
          <label for="chk_${sp.speciesCode}" class="spp-name" style="cursor: pointer;">
            ${sp.comName}
          </label>
          <span class="spp-sci">${sp.sciName}</span>
        </div>
        <span class="group-badge">${sp.groupName}</span>
        <span class="prob-tag ${probTagClass}">${sp.probability}</span>
        <span class="best-stop-pill" title="Mejor parada para detectar esta especie">
          📍 ${sp.best_stop_name}
        </span>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
}

function toggleSpeciesCheck(speciesCode) {
  if (checkedSpecies.has(speciesCode)) {
    checkedSpecies.delete(speciesCode);
  } else {
    checkedSpecies.add(speciesCode);
  }

  const row = document.getElementById(`row_sp_${speciesCode}`);
  if (row) {
    row.classList.toggle('checked', checkedSpecies.has(speciesCode));
  }

  const countBadge = document.getElementById('checklistProgressBadge');
  if (countBadge) {
    countBadge.textContent = `✓ ${checkedSpecies.size} / ${currentProbableSpecies.length} Registradas`;
  }
}

function filterProbableSpecies(group) {
  currentGroupFilter = group;

  document.querySelectorAll('.probable-filter-chip').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-group') === group);
  });

  applyProbableFilters();
}

function applyProbableFilters() {
  const query = (document.getElementById('probableSearchInput')?.value || '').toLowerCase().trim();

  let list = currentProbableSpecies;

  if (currentGroupFilter !== 'all') {
    list = list.filter(sp => sp.group === currentGroupFilter);
  }

  if (query) {
    list = list.filter(sp =>
      sp.comName.toLowerCase().includes(query) ||
      sp.sciName.toLowerCase().includes(query) ||
      (sp.best_stop_name && sp.best_stop_name.toLowerCase().includes(query))
    );
  }

  renderProbableSpeciesChecklist(list);
}

function exportChecklistToClipboard() {
  if (!currentProbableSpecies || currentProbableSpecies.length === 0) return;

  let text = `🦅 CHECKLIST DE ESPECIES PROBABLES - BIRDRUTA LOS LAGOS\n`;
  text += `Ruta con ${currentRouteData?.stops?.length || 0} paradas | Total especies probables: ${currentProbableSpecies.length}\n`;
  text += `Registradas en terreno: ${checkedSpecies.size} / ${currentProbableSpecies.length}\n\n`;

  let currentGrp = '';
  currentProbableSpecies.forEach(sp => {
    if (sp.groupName !== currentGrp) {
      currentGrp = sp.groupName;
      text += `\n--- ${currentGrp} ---\n`;
    }
    const check = checkedSpecies.has(sp.speciesCode) ? '[X]' : '[ ]';
    text += `${check} ${sp.comName} (${sp.sciName}) - Prob: ${sp.probability} | Mejor spot: ${sp.best_stop_name}\n`;
  });

  navigator.clipboard.writeText(text);
  alert('¡Lista copiada al portapapeles! Lista para pegar en notas o compartir con tu grupo.');
}

function resetChecklistTicks() {
  if (checkedSpecies.size === 0) return;
  if (confirm('¿Deseas desmarcar todas las especies registradas?')) {
    checkedSpecies.clear();
    applyProbableFilters();
  }
}

// Hook search input listener
document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('probableSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', applyProbableFilters);
  }
});

// Generate Google Maps navigation link with all waypoints
function openGoogleMapsRoute() {
  if (!currentRouteData || !currentRouteData.stops.length) return;

  const origin = currentRouteData.origin;
  const stops = currentRouteData.stops;

  let url = `https://www.google.com/maps/dir/${origin.lat},${origin.lng}/`;
  stops.forEach(s => {
    url += `${s.lat},${s.lng}/`;
  });
  url += `${origin.lat},${origin.lng}`;

  window.open(url, '_blank');
}

// Print / Export Field Checklist
function printFieldChecklist() {
  if (!currentRouteData) return;
  window.print();
}
