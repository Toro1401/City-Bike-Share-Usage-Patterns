/**
 * City Bike-Share Dashboard — Interactive Map & Analytics
 * Loads pre-aggregated JSON data and renders Leaflet map + charts
 */

// ── State ───────────────────────────────────────────────────────────────────
const state = {
    data: {},
    map: null,
    layers: {
        stations: null,
        routes: null,
        heat: null,
        recs: null
    },
    activeLayer: 'stations'
};

// ── Data Loading ────────────────────────────────────────────────────────────
async function loadData() {
    const files = ['kpi', 'stations', 'routes', 'hourly_heatmap', 'monthly_trends', 'recommendations', 'yearly_summary'];
    const promises = files.map(async (name) => {
        try {
            const res = await fetch(`data/${name}.json`);
            if (!res.ok) throw new Error(`${name}: ${res.status}`);
            return [name, await res.json()];
        } catch (e) {
            console.warn(`Failed to load ${name}:`, e);
            return [name, null];
        }
    });

    const results = await Promise.all(promises);
    results.forEach(([name, data]) => { state.data[name] = data; });
}

// ── Format Helpers ──────────────────────────────────────────────────────────
function fmt(n) {
    if (n == null) return '--';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(n >= 10_000 ? 0 : 1) + 'K';
    return n.toLocaleString();
}

function fmtPct(n) { return n != null ? n.toFixed(1) + '%' : '--'; }

// ── KPI Cards ───────────────────────────────────────────────────────────────
function renderKPIs() {
    const kpi = state.data.kpi;
    if (!kpi) return;

    document.getElementById('kpi-total-trips').textContent = fmt(kpi.total_trips);
    document.getElementById('kpi-stations').textContent = kpi.total_stations;
    document.getElementById('kpi-duration').textContent = kpi.avg_duration_min + ' min';
    document.getElementById('kpi-member-pct').textContent = fmtPct(kpi.member_pct);
    document.getElementById('kpi-duration-sub').textContent = `median: ${kpi.median_duration_min} min`;

    if (kpi.yoy_growth_pct != null) {
        const el = document.getElementById('kpi-growth');
        const isPos = kpi.yoy_growth_pct >= 0;
        el.className = `change ${isPos ? 'positive' : 'negative'}`;
        el.textContent = `${isPos ? '↑' : '↓'} ${Math.abs(kpi.yoy_growth_pct)}% YoY growth`;
    }

    // Data span
    if (kpi.first_trip && kpi.last_trip) {
        const y1 = new Date(kpi.first_trip).getFullYear();
        const y2 = new Date(kpi.last_trip).getFullYear();
        document.getElementById('kpi-span').textContent = `${y2 - y1}+ yrs`;
        document.getElementById('kpi-span-sub').textContent = `${y1} - ${y2}`;
    }
}

// ── Map Initialization ─────────────────────────────────────────────────────
function initMap() {
    state.map = L.map('map', {
        center: [40.730, -74.040],
        zoom: 13,
        zoomControl: true,
        attributionControl: false
    });

    // Dark tile layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        subdomains: 'abcd'
    }).addTo(state.map);

    // Attribution
    L.control.attribution({ position: 'bottomleft' })
        .addAttribution('&copy; <a href="https://carto.com/">CARTO</a> | Citi Bike Data')
        .addTo(state.map);
}

// ── Station Bubbles Layer ───────────────────────────────────────────────────
function createStationsLayer() {
    const stations = state.data.stations;
    if (!stations) return;

    const maxTrips = Math.max(...stations.map(s => s.total));
    const group = L.layerGroup();

    stations.forEach(s => {
        if (!s.lat || !s.lng) return;

        const ratio = s.total / maxTrips;
        const radius = 4 + ratio * 22;
        const opacity = 0.3 + ratio * 0.5;

        // Color based on net flow
        let color;
        if (s.net_flow > 500) color = '#10b981';       // net exporter
        else if (s.net_flow < -500) color = '#ef4444';  // net importer
        else color = '#3b82f6';                          // balanced

        const circle = L.circleMarker([s.lat, s.lng], {
            radius: radius,
            fillColor: color,
            color: color,
            weight: 1,
            opacity: 0.8,
            fillOpacity: opacity
        });

        circle.bindPopup(`
            <h4>${s.name}</h4>
            <div class="popup-stat"><span class="popup-label">Total Trips</span><span class="popup-value">${fmt(s.total)}</span></div>
            <div class="popup-stat"><span class="popup-label">Departures</span><span class="popup-value">${fmt(s.departures)}</span></div>
            <div class="popup-stat"><span class="popup-label">Arrivals</span><span class="popup-value">${fmt(s.arrivals)}</span></div>
            <div class="popup-stat"><span class="popup-label">Net Flow</span><span class="popup-value" style="color:${s.net_flow > 0 ? '#10b981' : '#ef4444'}">${s.net_flow > 0 ? '+' : ''}${fmt(s.net_flow)}</span></div>
            <div class="popup-stat"><span class="popup-label">Avg Duration</span><span class="popup-value">${s.avg_dur} min</span></div>
            <div class="popup-stat"><span class="popup-label">Peak Hour</span><span class="popup-value">${s.peak_hour}:00</span></div>
            <div class="popup-stat"><span class="popup-label">Members</span><span class="popup-value">${fmt(s.member_dep)}</span></div>
            <div class="popup-stat"><span class="popup-label">Casual</span><span class="popup-value">${fmt(s.casual_dep)}</span></div>
        `, { maxWidth: 240 });

        group.addLayer(circle);
    });

    state.layers.stations = group;
    group.addTo(state.map);
}

// ── Route Flow Lines ────────────────────────────────────────────────────────
function createRoutesLayer() {
    const routes = state.data.routes;
    if (!routes) return;

    const maxTrips = Math.max(...routes.map(r => r.trips));
    const group = L.layerGroup();

    routes.slice(0, 30).forEach(r => {
        if (!r.start_lat || !r.end_lat) return;

        const ratio = r.trips / maxTrips;
        const weight = 1 + ratio * 5;
        const opacity = 0.2 + ratio * 0.5;

        // Curved line using midpoint offset
        const midLat = (r.start_lat + r.end_lat) / 2;
        const midLng = (r.start_lng + r.end_lng) / 2;
        const dx = r.end_lng - r.start_lng;
        const dy = r.end_lat - r.start_lat;
        const offsetLat = midLat + dx * 0.15;
        const offsetLng = midLng - dy * 0.15;

        const line = L.polyline([
            [r.start_lat, r.start_lng],
            [offsetLat, offsetLng],
            [r.end_lat, r.end_lng]
        ], {
            color: '#8b5cf6',
            weight: weight,
            opacity: opacity,
            smoothFactor: 2,
            dashArray: ratio > 0.5 ? null : '6 4'
        });

        line.bindPopup(`
            <h4>${r.start_name} &rarr; ${r.end_name}</h4>
            <div class="popup-stat"><span class="popup-label">Total Trips</span><span class="popup-value">${fmt(r.trips)}</span></div>
            <div class="popup-stat"><span class="popup-label">Avg Duration</span><span class="popup-value">${r.avg_dur} min</span></div>
        `, { maxWidth: 280 });

        group.addLayer(line);
    });

    state.layers.routes = group;
}

// ── Heat Map Layer ──────────────────────────────────────────────────────────
function createHeatLayer() {
    const stations = state.data.stations;
    if (!stations) return;

    const points = stations
        .filter(s => s.lat && s.lng)
        .map(s => [s.lat, s.lng, s.total / 1000]);

    state.layers.heat = L.heatLayer(points, {
        radius: 25,
        blur: 20,
        maxZoom: 16,
        max: Math.max(...points.map(p => p[2])) * 0.6,
        gradient: {
            0.1: '#0f172a',
            0.3: '#1e40af',
            0.5: '#3b82f6',
            0.7: '#f59e0b',
            0.9: '#ef4444',
            1.0: '#ffffff'
        }
    });
}

// ── Recommendations Layer ───────────────────────────────────────────────────
function createRecsLayer() {
    const recs = state.data.recommendations;
    if (!recs || !recs.recommendations) return;

    const group = L.layerGroup();

    recs.recommendations.forEach((rec, i) => {
        if (!rec.lat || !rec.lng) return;

        // Pulsing marker using divIcon
        const icon = L.divIcon({
            className: 'rec-marker',
            html: `<div style="
                width: 28px; height: 28px;
                background: rgba(16, 185, 129, 0.3);
                border: 2px solid #10b981;
                border-radius: 50%;
                display: flex; align-items: center; justify-content: center;
                color: #10b981; font-weight: 800; font-size: 11px;
                font-family: Inter, sans-serif;
                animation: pulse 2s ease-in-out infinite;
                box-shadow: 0 0 12px rgba(16, 185, 129, 0.4);
            ">${i + 1}</div>
            <style>
                @keyframes pulse {
                    0%, 100% { transform: scale(1); box-shadow: 0 0 12px rgba(16, 185, 129, 0.4); }
                    50% { transform: scale(1.15); box-shadow: 0 0 20px rgba(16, 185, 129, 0.6); }
                }
            </style>`,
            iconSize: [28, 28],
            iconAnchor: [14, 14]
        });

        const marker = L.marker([rec.lat, rec.lng], { icon });

        marker.bindPopup(`
            <h4>Recommended Station #${i + 1}</h4>
            <div class="popup-stat"><span class="popup-label">Score</span><span class="popup-value">${Math.round(rec.score)}</span></div>
            <div class="popup-stat"><span class="popup-label">Nearest Station</span><span class="popup-value">${Math.round(rec.nearest_station_dist_m)}m</span></div>
            <div class="popup-stat"><span class="popup-label">Nearby Stations</span><span class="popup-value">${rec.nearby_stations}</span></div>
            <div style="margin-top:8px; font-size: 0.72rem; color: #94a3b8; line-height: 1.4;">
                ${rec.rationale || rec.signals?.join('. ') || 'Coverage gap detected'}
            </div>
        `, { maxWidth: 260 });

        group.addLayer(marker);
    });

    state.layers.recs = group;
}

// ── Layer Toggle ────────────────────────────────────────────────────────────
function toggleLayer(name) {
    // Toggle layer on/off
    const layer = state.layers[name];
    if (!layer) return;

    const btn = document.getElementById(`btn-layer-${name}`);

    if (state.map.hasLayer(layer)) {
        state.map.removeLayer(layer);
        btn.classList.remove('active');
    } else {
        layer.addTo(state.map);
        btn.classList.add('active');
    }
}

// Make toggleLayer global
window.toggleLayer = toggleLayer;

// ── Hourly Heatmap ──────────────────────────────────────────────────────────
function renderHeatmap() {
    const data = state.data.hourly_heatmap;
    if (!data) return;

    const container = document.getElementById('heatmap-container');
    const { days, hours, matrix } = data;
    const allValues = matrix.flat();
    const maxVal = Math.max(...allValues);

    let html = '<div class="heatmap-grid">';

    // Hour labels row
    html += '<div class="heatmap-label"></div>'; // empty corner
    for (let h = 0; h < 24; h++) {
        html += `<div class="heatmap-hour-label">${h % 3 === 0 ? h : ''}</div>`;
    }

    // Data rows
    for (let d = 0; d < 7; d++) {
        html += `<div class="heatmap-label">${days[d]}</div>`;
        for (let h = 0; h < 24; h++) {
            const val = matrix[d][h];
            const intensity = val / maxVal;
            const bg = heatColor(intensity);
            const textColor = intensity > 0.6 ? '#fff' : 'transparent';

            html += `<div class="heatmap-cell" style="background:${bg}; color:${textColor}"
                      title="${days[d]} ${h}:00 — ${fmt(val)} trips"></div>`;
        }
    }

    html += '</div>';
    container.innerHTML = html;
}

function heatColor(t) {
    // Blue → Cyan → Yellow → Orange → Red
    if (t < 0.2) return `rgba(30, 64, 175, ${0.2 + t * 2})`;
    if (t < 0.4) return `rgba(59, 130, 246, ${0.4 + t})`;
    if (t < 0.6) return `rgba(6, 182, 212, ${0.5 + t * 0.5})`;
    if (t < 0.8) return `rgba(245, 158, 11, ${0.6 + t * 0.3})`;
    return `rgba(239, 68, 68, ${0.7 + t * 0.3})`;
}

// ── Top Stations List ───────────────────────────────────────────────────────
function renderStationList() {
    const stations = state.data.stations;
    if (!stations) return;

    const list = document.getElementById('station-list');
    const top15 = stations.slice(0, 15);
    document.getElementById('stations-count-badge').textContent = `Top ${top15.length}`;

    list.innerHTML = top15.map((s, i) => `
        <li class="station-item" onclick="flyToStation(${s.lat}, ${s.lng}, '${s.name.replace(/'/g, "\\'")}')">
            <div class="station-rank ${i < 3 ? 'top3' : ''}">${i + 1}</div>
            <div class="station-info">
                <div class="station-name">${s.name}</div>
                <div class="station-meta">
                    ${fmt(s.departures)} dep / ${fmt(s.arrivals)} arr
                    &middot; peak ${s.peak_hour}:00
                </div>
            </div>
            <div class="station-count">${fmt(s.total)}</div>
        </li>
    `).join('');
}

window.flyToStation = function(lat, lng, name) {
    state.map.flyTo([lat, lng], 16, { duration: 0.8 });
};

// ── User Type Breakdown ─────────────────────────────────────────────────────
function renderUserBreakdown() {
    const kpi = state.data.kpi;
    if (!kpi) return;

    const memberPct = kpi.member_pct || 50;
    document.getElementById('user-bar-member').style.width = memberPct + '%';
    document.getElementById('user-bar-casual').style.width = (100 - memberPct) + '%';

    // Calculate member/casual counts from total and pct
    const memberCount = Math.round(kpi.total_trips * memberPct / 100);
    const casualCount = kpi.total_trips - memberCount;

    document.getElementById('user-member-count').textContent = fmt(memberCount);
    document.getElementById('user-casual-count').textContent = fmt(casualCount);
}

// ── Monthly Trend Chart ─────────────────────────────────────────────────────
function renderMonthlyChart() {
    const trends = state.data.monthly_trends;
    if (!trends) return;

    const ctx = document.getElementById('chart-monthly').getContext('2d');

    const labels = trends.map(t => {
        const m = String(t.month).padStart(2, '0');
        return `${t.year}-${m}`;
    });

    // Show every 12th label
    const displayLabels = labels.map((l, i) => i % 12 === 0 ? l : '');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: displayLabels,
            datasets: [{
                data: trends.map(t => t.total),
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 0,
                borderWidth: 1.5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(10, 14, 26, 0.95)',
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    callbacks: {
                        title: function(items) {
                            const idx = items[0].dataIndex;
                            const t = trends[idx];
                            return `${t.year}-${String(t.month).padStart(2,'0')}`;
                        },
                        label: function(item) {
                            return `${fmt(item.raw)} trips`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#475569', font: { size: 9 }, maxRotation: 0 },
                    grid: { display: false },
                    border: { display: false }
                },
                y: {
                    ticks: {
                        color: '#475569',
                        font: { size: 9 },
                        callback: v => fmt(v)
                    },
                    grid: { color: 'rgba(51, 65, 85, 0.3)' },
                    border: { display: false }
                }
            }
        }
    });
}

// ── Recommendations List ────────────────────────────────────────────────────
function renderRecommendations() {
    const recs = state.data.recommendations;
    if (!recs || !recs.recommendations) return;

    const container = document.getElementById('recs-list');

    container.innerHTML = recs.recommendations.slice(0, 8).map((rec, i) => `
        <div class="rec-item" onclick="flyToStation(${rec.lat}, ${rec.lng}, 'Recommendation ${i + 1}')">
            <div class="rec-header">
                <span class="rec-number">#${i + 1}</span>
                <span class="rec-score">Score: ${Math.round(rec.score)}</span>
            </div>
            <div class="rec-rationale">
                ${rec.nearest_station ? `${Math.round(rec.nearest_station_dist_m)}m from ${rec.nearest_station}` : ''}
                ${rec.nearby_activity ? ` &middot; ${fmt(rec.nearby_activity)} nearby trips` : ''}
            </div>
        </div>
    `).join('');
}

// ── Initialize ──────────────────────────────────────────────────────────────
async function init() {
    await loadData();
    initMap();

    // Render all components
    renderKPIs();
    createStationsLayer();
    createRoutesLayer();
    createHeatLayer();
    createRecsLayer();
    renderHeatmap();
    renderStationList();
    renderUserBreakdown();
    renderMonthlyChart();
    renderRecommendations();

    // Hide loading overlay
    setTimeout(() => {
        document.getElementById('loading-overlay').classList.add('hidden');
    }, 300);
}

document.addEventListener('DOMContentLoaded', init);
