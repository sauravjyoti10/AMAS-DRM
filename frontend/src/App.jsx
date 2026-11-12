import React, { useCallback, useEffect, useRef, useState } from 'react';
import 'leaflet/dist/leaflet.css';
import {
  MapContainer, TileLayer, Marker, Popup, Polyline, Polygon, Circle, useMap, useMapEvents,
} from 'react-leaflet';
import L from 'leaflet';
import { AlertTriangle, Radio, MapPin, Trash2 } from 'lucide-react';
import './index.css';

const API = 'http://127.0.0.1:8000';
const WS_URL = 'ws://127.0.0.1:8000/ws/feed';
const MAP_CENTER = [26.155, 91.765];

// Depots and incidents use different icons so they can never be confused on the map.
const depotIcon = L.divIcon({
  className: 'pin pin-depot', html: '<span>D</span>', iconSize: [30, 30], iconAnchor: [15, 15],
});
const incidentIcon = (severity) => L.divIcon({
  className: `pin pin-incident pin-${severity || 'LOW'}`, html: '<span>!</span>',
  iconSize: [30, 30], iconAnchor: [15, 15],
});

const SOURCE_LABEL = {
  message: 'Coordinates written in the SOS',
  geocoded: 'Found from the place name',
  manual: 'Pinned by dispatcher',
  unknown: 'Location unresolved',
};

const km = (m) => (m / 1000).toFixed(1);
const mins = (s) => Math.max(1, Math.round(s / 60));

// Insert or replace an incident (matched by its SOS text).
function upsert(list, state) {
  const i = list.findIndex((x) => x.raw_sos === state.raw_sos);
  if (i === -1) return [state, ...list];
  const copy = [...list];
  copy[i] = state;
  return copy;
}

// Move the map to an incident and its route.
function FocusController({ focus }) {
  const map = useMap();
  useEffect(() => {
    if (!focus || focus.points.length === 0) return;
    if (focus.points.length === 1) {
      map.flyTo(focus.points[0], 15, { duration: 0.8 });
    } else {
      map.flyToBounds(L.latLngBounds(focus.points), { padding: [70, 70], maxZoom: 16, duration: 0.8 });
    }
  }, [focus, map]);
  return null;
}

function MapResizeHandler() {
  const map = useMap();
  useEffect(() => {
    const timer = setTimeout(() => map.invalidateSize(), 250);
    return () => clearTimeout(timer);
  }, [map]);
  return null;
}

function MapClickHandler({ active, onPick }) {
  useMapEvents({
    click(e) {
      if (active) onPick(e.latlng);
    },
  });
  return null;
}

function focusPoints(state) {
  const inc = state.incident;
  if (!inc || inc.latitude == null || inc.longitude == null) return [];
  const route = state.route && state.route.path_coordinates;
  return route && route.length > 1 ? route : [[inc.latitude, inc.longitude]];
}

export default function App() {
  const [sosText, setSosText] = useState('');
  const [incidents, setIncidents] = useState([]);
  const [depots, setDepots] = useState([]);
  const [hazards, setHazards] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [mode, setMode] = useState(null); // null | 'hazard' | { pin: <raw_sos> }
  const [radius, setRadius] = useState(400);
  const [focus, setFocus] = useState(null);
  const incidentsRef = useRef([]);
  incidentsRef.current = incidents;

  const showFocus = useCallback((state) => {
    const points = focusPoints(state);
    if (points.length) setFocus({ id: Date.now(), points });
  }, []);

  const post = useCallback(async (path, body) => {
    const res = await fetch(`${API}${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
    return data;
  }, []);

  // Live feed with automatic reconnect.
  useEffect(() => {
    let ws;
    let timer;
    let closed = false;
    const connect = () => {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => {
        setWsConnected(false);
        if (!closed) timer = setTimeout(connect, 2000);
      };
      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.event === 'INCIDENT_PROCESSED' || message.event === 'DISPATCH_APPROVED') {
          setIncidents((prev) => upsert(prev, message.data));
          showFocus(message.data);
        } else if (message.event === 'HAZARDS_UPDATED') {
          setHazards(message.data);
        }
      };
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      if (ws) ws.close();
    };
  }, [showFocus]);

  // Depots and hazards come from the server (single source of truth).
  useEffect(() => {
    fetch(`${API}/api/depots`).then((r) => r.json()).then(setDepots).catch(() => {});
    fetch(`${API}/api/hazards`).then((r) => r.json()).then(setHazards).catch(() => {});
  }, []);

  // After hazards change, recompute every dispatched incident's route around the new zones.
  const rerouteAll = useCallback(async () => {
    const targets = incidentsRef.current.filter(
      (s) => s.allocation && s.incident && s.incident.latitude != null
        && (s.status === 'completed' || s.status === 'failed'),
    );
    for (const s of targets) {
      try {
        const updated = await post('/api/sos/reroute', { state: s });
        setIncidents((prev) => upsert(prev, updated));
      } catch (err) {
        setNotice(String(err.message || err));
      }
    }
  }, [post]);

  const handleSendSOS = async () => {
    if (!sosText.trim()) return;
    setLoading(true);
    setNotice('');
    try {
      await post('/api/sos/process', { raw_sos: sosText });
      setSosText('');
    } catch (err) {
      setNotice(`Could not send SOS: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (state, latlng) => {
    setNotice('');
    try {
      const body = { state, approved: true };
      if (latlng) {
        body.latitude = latlng.lat;
        body.longitude = latlng.lng;
      }
      const updated = await post('/api/sos/approve', body);
      setIncidents((prev) => upsert(prev, updated));
    } catch (err) {
      setNotice(`Dispatch failed: ${err.message}`);
    }
  };

  const handleMapPick = async (latlng) => {
    const current = mode;
    setMode(null);
    if (current === 'hazard') {
      try {
        await post('/api/hazards', {
          name: `Hazard ${hazards.length + 1}`,
          center: { lat: latlng.lat, lon: latlng.lng },
          radius_m: radius,
        });
        await rerouteAll();
      } catch (err) {
        setNotice(`Could not add hazard: ${err.message}`);
      }
    } else if (current && current.pin) {
      const target = incidentsRef.current.find((s) => s.raw_sos === current.pin);
      if (target) await handleApprove(target, latlng);
    }
  };

  const deleteHazard = async (id) => {
    try {
      const res = await fetch(`${API}/api/hazards/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      setHazards((prev) => prev.filter((h) => h.id !== id));
      await rerouteAll();
    } catch (err) {
      setNotice(`Could not remove hazard: ${err.message}`);
    }
  };

  const picking = mode !== null;

  return (
    <div className="dashboard-container">
      <div className="sidebar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
          <Radio color={wsConnected ? '#22c55e' : '#ef4444'} />
          <h2 style={{ fontSize: '1.2rem' }}>AMAS-DRM Command</h2>
        </div>

        <div className="sos-input-box">
          <label style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Ingest Distress Feed</label>
          <textarea
            className="sos-textarea"
            placeholder="Type raw SOS message... e.g., Critical emergency! Flooding near Zoo Road, 3 casualties trapped needing medical kits."
            value={sosText}
            onChange={(e) => setSosText(e.target.value)}
          />
          <button className="btn-primary" onClick={handleSendSOS} disabled={loading}>
            {loading ? 'Processing...' : 'Submit Distress Feed'}
          </button>
        </div>

        {notice && <div className="notice">{notice}</div>}

        <div className="hazard-box">
          <div className="hazard-head">
            <strong>Hazard zones ({hazards.length})</strong>
            <span className="muted">routes stay out of these</span>
          </div>
          <div className="hazard-controls">
            <button
              className={mode === 'hazard' ? 'btn-secondary active' : 'btn-secondary'}
              onClick={() => setMode(mode === 'hazard' ? null : 'hazard')}
            >
              {mode === 'hazard' ? 'Click the map… (cancel)' : '+ Add hazard on map'}
            </button>
            <input
              type="range" min="100" max="1500" step="50" value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
              title="Hazard radius"
            />
            <span className="muted">{radius} m</span>
          </div>
          {hazards.map((h) => (
            <div key={h.id} className="hazard-row">
              <span>{h.name}</span>
              <button className="icon-btn" onClick={() => deleteHazard(h.id)} title="Remove hazard">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>

        <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem', color: '#cbd5e1' }}>
          Active Emergency Incidents ({incidents.length})
        </h3>

        <div style={{ flex: 1 }}>
          {incidents.map((item) => {
            const inc = item.incident || {};
            const route = item.route;
            const located = inc.latitude != null && inc.longitude != null;
            const pinningThis = mode && mode.pin === item.raw_sos;
            return (
              <div
                key={item.raw_sos}
                className={`incident-card ${inc.severity || 'LOW'}`}
                onClick={() => showFocus(item)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                  <span className={`badge badge-${inc.severity || 'LOW'}`}>{inc.severity || 'UNKNOWN'}</span>
                  <span style={{ fontSize: '0.75rem', color: item.status === 'failed' ? '#ef4444' : '#94a3b8' }}>
                    Status: {item.status}
                  </span>
                </div>

                <p style={{ fontSize: '0.85rem', marginBottom: '0.4rem' }}>"{item.raw_sos}"</p>

                <p className="loc-line">
                  📍 {inc.location_text || 'No place named'}
                  {located && inc.location_label && inc.location_label !== inc.location_text
                    ? ` → ${inc.location_label}` : ''}
                </p>
                {inc.location_source && (
                  <p className="loc-sub">
                    {SOURCE_LABEL[inc.location_source]}
                    {located && inc.uncertainty_m > 0 ? ` · ±${Math.round(inc.uncertainty_m)} m` : ''}
                    {located ? ` · ${inc.latitude.toFixed(5)}, ${inc.longitude.toFixed(5)}` : ''}
                  </p>
                )}

                {route && (
                  <div className="route-info">
                    🚚 {route.depot_name} · <strong>{km(route.distance_m)} km</strong> · ~{mins(route.travel_time_s)} min
                    <div className="chips">
                      {route.hazards_avoided && route.hazards_avoided.length > 0 && (
                        <span className={route.hazard_safe ? 'chip ok' : 'chip bad'}>
                          {route.hazard_safe
                            ? `avoids ${route.hazards_avoided.length} hazard zone(s)`
                            : '⚠ route touches a hazard'}
                        </span>
                      )}
                      {route.baseline_distance_m != null
                        && route.distance_m - route.baseline_distance_m > 1 && (
                        <span className="chip warn">
                          detour +{km(route.distance_m - route.baseline_distance_m)} km
                          / +{mins(route.travel_time_s - route.baseline_travel_time_s)} min
                        </span>
                      )}
                      {route.hazards_ignored && route.hazards_ignored.length > 0 && (
                        <span className="chip warn">incident is inside a hazard: final approach unavoidable</span>
                      )}
                      {route.destination_snap_m > 300 && (
                        <span className="chip warn">pin is {Math.round(route.destination_snap_m)} m from the nearest road</span>
                      )}
                    </div>
                  </div>
                )}

                {item.warnings && item.warnings.map((w) => (
                  <p key={w} className="warn-line">⚠️ {w}</p>
                ))}

                {item.status === 'failed' && item.error && (
                  <p style={{ fontSize: '0.75rem', color: '#ef4444', marginTop: '0.25rem' }}>⚠️ {item.error}</p>
                )}

                {item.needs_human_verification && item.status === 'triaged' && (
                  <div className="hitl-banner" onClick={(e) => e.stopPropagation()}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.4rem' }}>
                      <AlertTriangle size={16} />
                      <strong style={{ fontSize: '0.85rem' }}>Human Approval Required</strong>
                    </div>
                    <p style={{ fontSize: '0.75rem', marginBottom: '0.5rem' }}>
                      {located
                        ? 'Critical priority flagged. Verify the pin and resource allocation before dispatch.'
                        : 'The location could not be resolved from the message. Pin it on the map to dispatch.'}
                    </p>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {located && (
                        <button className="btn-approve" onClick={() => handleApprove(item)}>
                          Approve Dispatch
                        </button>
                      )}
                      <button
                        className="btn-pin"
                        onClick={() => setMode(pinningThis ? null : { pin: item.raw_sos })}
                      >
                        <MapPin size={13} /> {pinningThis ? 'Click the map… (cancel)' : located ? 'Correct location' : 'Pin location'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className={picking ? 'map-viewport picking' : 'map-viewport'}>
        <MapContainer center={MAP_CENTER} zoom={13} scrollWheelZoom={true}>
          <MapResizeHandler />
          <FocusController focus={focus} />
          <MapClickHandler active={picking} onPick={handleMapPick} />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {hazards.map((h) => (
            <Polygon
              key={h.id}
              positions={h.polygon.map((p) => [p.lat, p.lon])}
              pathOptions={{ color: '#dc2626', fillColor: '#ef4444', fillOpacity: 0.35, weight: 2 }}
            >
              <Popup><strong>⛔ {h.name}</strong><br />Routes avoid this zone.</Popup>
            </Polygon>
          ))}

          {depots.map((depot) => (
            <Marker key={depot.id} position={[depot.lat, depot.lon]} icon={depotIcon}>
              <Popup>
                <strong>🏢 {depot.name || depot.id}</strong><br />
                Capacity: {depot.capacity} units
              </Popup>
            </Marker>
          ))}

          {incidents.map((item, idx) => {
            const inc = item.incident;
            if (!inc || inc.latitude == null || inc.longitude == null) return null;
            const route = item.route;
            const color = inc.severity === 'CRITICAL' ? '#dc2626' : '#2563eb';
            return (
              <React.Fragment key={item.raw_sos}>
                {inc.uncertainty_m > 0 && (
                  <Circle
                    center={[inc.latitude, inc.longitude]}
                    radius={inc.uncertainty_m}
                    pathOptions={{ color: '#f59e0b', weight: 1.5, dashArray: '4 4', fillOpacity: 0.08 }}
                  />
                )}

                {route && route.baseline_path_coordinates && route.baseline_distance_m !== route.distance_m && (
                  <Polyline
                    positions={route.baseline_path_coordinates}
                    pathOptions={{ color: '#64748b', weight: 3, dashArray: '2 8', opacity: 0.9 }}
                  />
                )}

                {route && route.path_coordinates && (
                  <>
                    <Polyline positions={route.path_coordinates} pathOptions={{ color: '#ffffff', weight: 9, opacity: 0.95 }} />
                    <Polyline positions={route.path_coordinates} pathOptions={{ color, weight: 5, opacity: 0.95 }} />
                  </>
                )}

                <Marker position={[inc.latitude, inc.longitude]} icon={incidentIcon(inc.severity)}>
                  <Popup>
                    <strong>🚨 Incident #{incidents.length - idx}</strong><br />
                    Severity: {inc.severity}<br />
                    Place: {inc.location_text || 'not named'}<br />
                    {SOURCE_LABEL[inc.location_source]}
                    {inc.uncertainty_m > 0 ? ` (±${Math.round(inc.uncertainty_m)} m)` : ''}
                    {route && (<><br />{route.depot_name}: {km(route.distance_m)} km, ~{mins(route.travel_time_s)} min</>)}
                  </Popup>
                </Marker>
              </React.Fragment>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
}
