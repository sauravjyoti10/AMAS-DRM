import React, { useState, useEffect } from 'react';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import { AlertTriangle, Radio } from 'lucide-react';
import './index.css';

// Fix Leaflet marker icon asset paths in Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

// Helper component to invalidate Leaflet map size on mount (fixes broken grid tiles)
function MapResizeHandler() {
  const map = useMap();
  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 250);
    return () => clearTimeout(timer);
  }, [map]);
  return null;
}

const DEPOTS = [
  { id: 'Depot_ZooRoad', name: 'Zoo Road Central Depot', lat: 26.1750, lon: 91.7750 },
  { id: 'Depot_Dispur', name: 'Dispur Emergency Depot', lat: 26.1433, lon: 91.7898 }
];

export default function App() {
  const [sosText, setSosText] = useState('');
  const [incidents, setIncidents] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [loading, setLoading] = useState(false);

  const mapCenter = [26.1550, 91.7650];

  useEffect(() => {
    const ws = new WebSocket('ws://127.0.0.1:8000/ws/feed');

    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.event === 'INCIDENT_PROCESSED' || message.event === 'DISPATCH_APPROVED') {
        const stateData = message.data;
        setIncidents((prev) => {
          const index = prev.findIndex(item => item.raw_sos === stateData.raw_sos);
          if (index !== -1) {
            const updated = [...prev];
            updated[index] = stateData;
            return updated;
          }
          return [stateData, ...prev];
        });
      }
    };

    return () => ws.close();
  }, []);

  const handleSendSOS = async () => {
    if (!sosText.trim()) return;
    setLoading(true);
    try {
      await fetch('http://127.0.0.1:8000/api/sos/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_sos: sosText })
      });
      setSosText('');
    } catch (err) {
      console.error('Failed to send SOS:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (incidentState) => {
    try {
      await fetch('http://127.0.0.1:8000/api/sos/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: incidentState, approved: true })
      });
    } catch (err) {
      console.error('Approval failed:', err);
    }
  };

  return (
    <div className="dashboard-container">
      {/* Sidebar Controls & Active Feed */}
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

        <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem', color: '#cbd5e1' }}>
          Active Emergency Incidents ({incidents.length})
        </h3>

        <div style={{ flex: 1 }}>
          {incidents.map((item, idx) => {
            const inc = item.incident || {};
            return (
              <div key={idx} className={`incident-card ${inc.severity || 'LOW'}`}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                  <span className={`badge badge-${inc.severity || 'LOW'}`}>
                    {inc.severity || 'UNKNOWN'}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: item.status === 'failed' ? '#ef4444' : '#94a3b8' }}>
                    Status: {item.status}
                  </span>
                </div>

                <p style={{ fontSize: '0.85rem', marginBottom: '0.4rem' }}>"{item.raw_sos}"</p>

                {inc.location_name && (
                  <p style={{ fontSize: '0.75rem', color: '#64748b' }}>📍 {inc.location_name}</p>
                )}

                {/* Render error details if triage or agent pipeline failed */}
                {item.status === 'failed' && item.error && (
                  <p style={{ fontSize: '0.75rem', color: '#ef4444', marginTop: '0.25rem' }}>
                    ⚠️ {item.error}
                  </p>
                )}

                {/* HITL Verification Banner */}
                {item.needs_human_verification && item.status === 'triaged' && (
                  <div className="hitl-banner">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.4rem' }}>
                      <AlertTriangle size={16} />
                      <strong style={{ fontSize: '0.85rem' }}>Human Approval Required</strong>
                    </div>
                    <p style={{ fontSize: '0.75rem', marginBottom: '0.5rem' }}>
                      Critical priority flagged. Verify resource allocation before dispatch.
                    </p>
                    <div>
                      <button className="btn-approve" onClick={() => handleApprove(item)}>
                        Approve Dispatch
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Leaflet Map Viewport */}
      <div className="map-viewport">
        <MapContainer center={mapCenter} zoom={13} scrollWheelZoom={true}>
          <MapResizeHandler />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {DEPOTS.map((depot) => (
            <Marker key={depot.id} position={[depot.lat, depot.lon]}>
              <Popup>
                <strong>🏢 {depot.name}</strong><br />
                Capacity: 50 units
              </Popup>
            </Marker>
          ))}

          {incidents.map((item, idx) => {
            const inc = item.incident;
            if (!inc || !inc.latitude || !inc.longitude) return null;

            return (
              <React.Fragment key={idx}>
                <Marker position={[inc.latitude, inc.longitude]}>
                  <Popup>
                    <strong>🚨 Incident #{idx + 1}</strong><br />
                    Severity: {inc.severity}<br />
                    Location: {inc.location_name}
                  </Popup>
                </Marker>

                {item.route && item.route.path_coordinates && (
                  <Polyline
                    positions={item.route.path_coordinates}  // 👈 Uses the actual road turning points!
                    color={inc.severity === 'CRITICAL' ? '#ef4444' : '#2563eb'}
                    weight={4}
                    dashArray="6, 6"
                  />
                )}
              </React.Fragment>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
}