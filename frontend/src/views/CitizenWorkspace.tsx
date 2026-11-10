import React, { useState, useEffect } from 'react';
import { useIncidents } from '../context/IncidentContext';
import { useAuth } from '../context/AuthContext';
import { ApiClient } from '../services/api';
import { InteractiveMap } from '../components/InteractiveMap';
import { StatusBadge } from '../components/StatusBadge';
import { LocationPoint } from '../types';
import { 
  CloudRain, Navigation, AlertTriangle, Send, MapPin, 
  ArrowRight, ShieldCheck, CheckCircle2, Clock, Info, 
  Crosshair, Search, Compass, Car, Sparkles, Sliders 
} from 'lucide-react';

const POPULAR_BENGALURU_CORRIDORS: LocationPoint[] = [
  { name: 'Sony World Junction (Koramangala)', lat: 12.9352, lon: 77.6245 },
  { name: 'Indiranagar 100ft Rd / CMH Rd', lat: 12.9780, lon: 77.6410 },
  { name: 'Ejipura Main Signal', lat: 12.9425, lon: 77.6250 },
  { name: 'Intermediate Ring Road / Domlur', lat: 12.9610, lon: 77.6380 },
  { name: 'Central Silk Board Junction', lat: 12.9175, lon: 77.6225 },
  { name: 'Koramangala 80ft Road / 1st Block', lat: 12.9279, lon: 77.6271 },
  { name: 'Koramangala 5th Block Junction', lat: 12.9355, lon: 77.6180 },
  { name: 'Trinity Circle / MG Road', lat: 12.9720, lon: 77.6160 },
  { name: 'HSR Layout Sector 1 / 5th Main', lat: 12.9150, lon: 77.6350 },
  { name: 'Hosur Road / Forum Mall', lat: 12.9345, lon: 77.6110 }
];

export const CitizenWorkspace: React.FC = () => {
  const { incidents, refreshData, calculateRoutes, routesResult, isLoading, setHighlightedCoordinates } = useIncidents();
  const { currentUser } = useAuth();

  // Dynamic Route Location States
  const [originQuery, setOriginQuery] = useState<string>('Sony World Junction (Koramangala)');
  const [originPoint, setOriginPoint] = useState<LocationPoint>({ name: 'Sony World Junction (Koramangala)', lat: 12.9352, lon: 77.6245 });
  const [originSuggestions, setOriginSuggestions] = useState<LocationPoint[]>([]);

  const [destQuery, setDestQuery] = useState<string>('Indiranagar 100ft Rd / CMH Rd');
  const [destPoint, setDestPoint] = useState<LocationPoint>({ name: 'Indiranagar 100ft Rd / CMH Rd', lat: 12.9780, lon: 77.6410 });
  const [destSuggestions, setDestSuggestions] = useState<LocationPoint[]>([]);

  // Map Click Pin Target Mode: 'origin' | 'destination' | 'report'
  const [pinMode, setPinMode] = useState<'origin' | 'destination' | 'report'>('origin');

  // GPS Status
  const [gpsStatus, setGpsStatus] = useState<string | null>(null);

  // Preference Tuning
  const [vehicleType, setVehicleType] = useState<string>('car');
  const [hazardSensitivity, setHazardSensitivity] = useState<string>('high');

  // Hazard Report Form State & Photo Upload Simulation
  const [reportLat, setReportLat] = useState<number>(12.9352);
  const [reportLon, setReportLon] = useState<number>(77.6245);
  const [reportType, setReportType] = useState<string>('waterlogging');
  const [reportSeverity, setReportSeverity] = useState<string>('high');
  const [reportDesc, setReportDesc] = useState<string>('Heavy water accumulation across roadway. Water level above 30cm.');
  const [reportEvidence, setReportEvidence] = useState<string>('Observed slow moving traffic and 1 stalled scooter.');
  const [photoSelected, setPhotoSelected] = useState<string>('submerged_underpass');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  // Search Origin Place Suggestions
  const handleOriginSearchChange = async (val: string) => {
    setOriginQuery(val);
    if (val.trim().length >= 2) {
      const places = await ApiClient.searchLocations(val);
      if (places.length > 0) {
        setOriginSuggestions(places);
      } else {
        // Fallback filter from local corridors
        const local = POPULAR_BENGALURU_CORRIDORS.filter(p => p.name.toLowerCase().includes(val.toLowerCase()));
        setOriginSuggestions(local);
      }
    } else {
      setOriginSuggestions([]);
    }
  };

  // Search Destination Place Suggestions
  const handleDestSearchChange = async (val: string) => {
    setDestQuery(val);
    if (val.trim().length >= 2) {
      const places = await ApiClient.searchLocations(val);
      if (places.length > 0) {
        setDestSuggestions(places);
      } else {
        const local = POPULAR_BENGALURU_CORRIDORS.filter(p => p.name.toLowerCase().includes(val.toLowerCase()));
        setDestSuggestions(local);
      }
    } else {
      setDestSuggestions([]);
    }
  };

  // HTML5 Device GPS Geolocation
  const handleUseCurrentGpsLocation = (target: 'origin' | 'destination') => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser.');
      return;
    }

    setGpsStatus('Acquiring high-accuracy GPS coordinates from device...');
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = Number(position.coords.latitude.toFixed(4));
        const lon = Number(position.coords.longitude.toFixed(4));
        const locName = `📍 My Current Device Location (${lat}, ${lon})`;

        if (target === 'origin') {
          setOriginPoint({ name: locName, lat, lon });
          setOriginQuery(locName);
        } else {
          setDestPoint({ name: locName, lat, lon });
          setDestQuery(locName);
        }

        setHighlightedCoordinates([lat, lon]);
        setGpsStatus(`GPS acquired: ${lat}, ${lon} (Accuracy ±${Math.round(position.coords.accuracy)}m)`);
        setTimeout(() => setGpsStatus(null), 4000);
      },
      (error) => {
        console.warn('GPS error, using Bengaluru centroid fallback:', error.message);
        // Fallback to active Koramangala coordinate
        const lat = 12.9352;
        const lon = 77.6245;
        const locName = `📍 Koramangala GPS Pin (${lat}, ${lon})`;
        if (target === 'origin') {
          setOriginPoint({ name: locName, lat, lon });
          setOriginQuery(locName);
        } else {
          setDestPoint({ name: locName, lat, lon });
          setDestQuery(locName);
        }
        setGpsStatus('Device GPS mock acquired: Koramangala corridor');
        setTimeout(() => setGpsStatus(null), 3000);
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  // Map Click Handler based on Active Pin Mode
  const handleMapClick = (lat: number, lon: number) => {
    const roundedLat = Number(lat.toFixed(4));
    const roundedLon = Number(lon.toFixed(4));

    if (pinMode === 'origin') {
      const name = `📍 Custom Map Pin (${roundedLat}, ${roundedLon})`;
      setOriginPoint({ name, lat: roundedLat, lon: roundedLon });
      setOriginQuery(name);
    } else if (pinMode === 'destination') {
      const name = `🎯 Custom Target Pin (${roundedLat}, ${roundedLon})`;
      setDestPoint({ name, lat: roundedLat, lon: roundedLon });
      setDestQuery(name);
    } else {
      setReportLat(roundedLat);
      setReportLon(roundedLon);
    }
  };

  const handleRouteSearch = async () => {
    await calculateRoutes(originPoint, destPoint);
  };

  const handleReportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmitSuccess(null);
    try {
      const res = await ApiClient.createReport({
        lat: reportLat,
        lon: reportLon,
        type: reportType,
        severity: reportSeverity,
        description: reportDesc,
        evidence_note: `${reportEvidence} [Attached: ${photoSelected}]`
      });
      setSubmitSuccess(`Report submitted successfully! Mapped to: ${res.road_name || 'Road Segment'}`);
      await refreshData();
    } catch (err: any) {
      alert(`Error submitting report: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '20px', alignItems: 'start' }}>
      {/* Left Column: Interactive Route Search + Map + Community Feed */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        
        {/* Dynamic Location Search Card */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '10px',
          border: '1px solid #E2E8F0',
          padding: '18px 20px',
          boxShadow: '0 2px 6px rgba(0,0,0,0.04)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Navigation size={18} color="#0B8B95" />
              <h2 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: '#1E293B' }}>
                Monsoon Risk-Aware Route Finder
              </h2>
            </div>
            
            {/* Map Click Target Mode Toggles */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', backgroundColor: '#F1F5F9', padding: '3px', borderRadius: '6px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', padding: '0 6px' }}>Map Click:</span>
              <button
                type="button"
                onClick={() => setPinMode('origin')}
                style={{
                  padding: '3px 8px',
                  borderRadius: '4px',
                  border: 'none',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  backgroundColor: pinMode === 'origin' ? '#059669' : 'transparent',
                  color: pinMode === 'origin' ? '#FFF' : '#475569'
                }}
              >
                🏁 Set Start
              </button>
              <button
                type="button"
                onClick={() => setPinMode('destination')}
                style={{
                  padding: '3px 8px',
                  borderRadius: '4px',
                  border: 'none',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  backgroundColor: pinMode === 'destination' ? '#DC2626' : 'transparent',
                  color: pinMode === 'destination' ? '#FFF' : '#475569'
                }}
              >
                🎯 Set End
              </button>
              <button
                type="button"
                onClick={() => setPinMode('report')}
                style={{
                  padding: '3px 8px',
                  borderRadius: '4px',
                  border: 'none',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  backgroundColor: pinMode === 'report' ? '#0B8B95' : 'transparent',
                  color: pinMode === 'report' ? '#FFF' : '#475569'
                }}
              >
                ⚠️ Set Hazard
              </button>
            </div>
          </div>

          {gpsStatus && (
            <div style={{ padding: '8px 12px', backgroundColor: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: '6px', fontSize: '12px', color: '#065F46', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Crosshair size={14} color="#059669" />
              <span>{gpsStatus}</span>
            </div>
          )}

          {/* Dynamic Origin & Destination Input Boxes */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '12px', alignItems: 'flex-start' }}>
            
            {/* Origin Place Search Box */}
            <div style={{ position: 'relative' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569' }}>
                  📍 Start Origin Location:
                </label>
                <button
                  type="button"
                  onClick={() => handleUseCurrentGpsLocation('origin')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '3px',
                    backgroundColor: '#ECFDF5',
                    color: '#047857',
                    border: '1px solid #A7F3D0',
                    borderRadius: '4px',
                    padding: '2px 6px',
                    fontSize: '10px',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                  title="Acquire live GPS from browser device"
                >
                  <Crosshair size={11} /> Use Device GPS
                </button>
              </div>

              <input
                type="text"
                value={originQuery}
                onChange={(e) => handleOriginSearchChange(e.target.value)}
                placeholder="Search any place in Bengaluru..."
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  fontSize: '12px',
                  backgroundColor: '#F8FAFC'
                }}
              />

              {/* Suggestions Dropdown */}
              {originSuggestions.length > 0 && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #CBD5E1',
                  borderRadius: '6px',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                  zIndex: 200,
                  marginTop: '2px',
                  maxHeight: '180px',
                  overflowY: 'auto'
                }}>
                  {originSuggestions.map((sug, idx) => (
                    <div
                      key={idx}
                      onClick={() => {
                        setOriginPoint(sug);
                        setOriginQuery(sug.name);
                        setOriginSuggestions([]);
                      }}
                      style={{
                        padding: '8px 10px',
                        fontSize: '12px',
                        cursor: 'pointer',
                        borderBottom: '1px solid #F1F5F9',
                        color: '#1E293B'
                      }}
                    >
                      📍 {sug.name}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Destination Place Search Box */}
            <div style={{ position: 'relative' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569' }}>
                  🎯 Destination Target:
                </label>
                <button
                  type="button"
                  onClick={() => handleUseCurrentGpsLocation('destination')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '3px',
                    backgroundColor: '#ECFDF5',
                    color: '#047857',
                    border: '1px solid #A7F3D0',
                    borderRadius: '4px',
                    padding: '2px 6px',
                    fontSize: '10px',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                  title="Acquire live GPS from browser device"
                >
                  <Crosshair size={11} /> Use Device GPS
                </button>
              </div>

              <input
                type="text"
                value={destQuery}
                onChange={(e) => handleDestSearchChange(e.target.value)}
                placeholder="Search destination landmark..."
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  fontSize: '12px',
                  backgroundColor: '#F8FAFC'
                }}
              />

              {destSuggestions.length > 0 && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #CBD5E1',
                  borderRadius: '6px',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                  zIndex: 200,
                  marginTop: '2px',
                  maxHeight: '180px',
                  overflowY: 'auto'
                }}>
                  {destSuggestions.map((sug, idx) => (
                    <div
                      key={idx}
                      onClick={() => {
                        setDestPoint(sug);
                        setDestQuery(sug.name);
                        setDestSuggestions([]);
                      }}
                      style={{
                        padding: '8px 10px',
                        fontSize: '12px',
                        cursor: 'pointer',
                        borderBottom: '1px solid #F1F5F9',
                        color: '#1E293B'
                      }}
                    >
                      🎯 {sug.name}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Find Routes Button */}
            <button
              onClick={handleRouteSearch}
              disabled={isLoading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '9px 18px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: '#0B8B95',
                color: '#FFFFFF',
                fontWeight: 700,
                fontSize: '13px',
                cursor: isLoading ? 'not-allowed' : 'pointer',
                marginTop: '18px',
                boxShadow: '0 2px 4px rgba(11, 139, 149, 0.3)'
              }}
            >
              <Navigation size={15} />
              {isLoading ? 'Computing...' : 'Find Routes'}
            </button>
          </div>

          {/* Quick Corridor Selection Chips */}
          <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '6px', overflowX: 'auto', paddingBottom: '4px' }}>
            <span style={{ fontSize: '11px', color: '#64748B', fontWeight: 700, whiteSpace: 'nowrap' }}>
              Quick Corridors:
            </span>
            {POPULAR_BENGALURU_CORRIDORS.slice(0, 6).map((corridor, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  setDestPoint(corridor);
                  setDestQuery(corridor.name);
                }}
                style={{
                  padding: '3px 8px',
                  borderRadius: '4px',
                  border: '1px solid #CBD5E1',
                  backgroundColor: '#F8FAFC',
                  fontSize: '11px',
                  color: '#334155',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap'
                }}
              >
                {corridor.name.split('(')[0]}
              </button>
            ))}
          </div>

          {/* Commuter Preference Tuning Controls */}
          <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '16px', backgroundColor: '#F8FAFC', padding: '8px 12px', borderRadius: '6px', border: '1px solid #E2E8F0', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
              <span style={{ fontWeight: 700, color: '#475569' }}>🚗 Vehicle:</span>
              <select
                value={vehicleType}
                onChange={(e) => setVehicleType(e.target.value)}
                style={{ padding: '3px 8px', borderRadius: '4px', border: '1px solid #CBD5E1', fontSize: '12px', backgroundColor: '#FFF' }}
              >
                <option value="scooter">2-Wheeler / Scooter (High Risk of Water Stalling)</option>
                <option value="auto">3-Wheeler Auto Rickshaw</option>
                <option value="car">4-Wheeler Car / SUV</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
              <span style={{ fontWeight: 700, color: '#475569' }}>🌊 Caution Level:</span>
              <select
                value={hazardSensitivity}
                onChange={(e) => setHazardSensitivity(e.target.value)}
                style={{ padding: '3px 8px', borderRadius: '4px', border: '1px solid #CBD5E1', fontSize: '12px', backgroundColor: '#FFF' }}
              >
                <option value="high">High (Avoid Any Puddles &gt;20cm)</option>
                <option value="moderate">Moderate Caution</option>
                <option value="standard">Standard Travel Time Only</option>
              </select>
            </div>
          </div>

          {/* Route Comparison Results Cards */}
          {routesResult && routesResult.routes && routesResult.routes.length > 0 && (
            <div style={{ marginTop: '16px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              {routesResult.routes.map((rt) => {
                const isRiskAware = rt.type === 'risk_aware';
                const isAlternative = rt.type === 'alternative';

                return (
                  <div
                    key={rt.type}
                    style={{
                      padding: '14px',
                      borderRadius: '8px',
                      border: `2px solid ${isRiskAware ? '#0B8B95' : isAlternative ? '#7C3AED' : '#CBD5E1'}`,
                      backgroundColor: isRiskAware ? '#F0FDFA' : isAlternative ? '#FAF5FF' : '#F8FAFC'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <span style={{
                        fontSize: '11px',
                        fontWeight: 800,
                        textTransform: 'uppercase',
                        color: isRiskAware ? '#0F766E' : isAlternative ? '#6D28D9' : '#475569',
                        backgroundColor: isRiskAware ? '#CCFBF1' : isAlternative ? '#EDE9FE' : '#E2E8F0',
                        padding: '2px 8px',
                        borderRadius: '4px'
                      }}>
                        {rt.label}
                      </span>
                      {isRiskAware && (
                        <span style={{ fontSize: '11px', color: '#059669', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '2px' }}>
                          <ShieldCheck size={13} /> Recommended
                        </span>
                      )}
                    </div>

                    <div style={{ fontSize: '20px', fontWeight: 800, color: '#1E293B', marginTop: '4px' }}>
                      {Math.round(rt.estimated_duration_s / 60)} min
                      <span style={{ fontSize: '12px', fontWeight: 500, color: '#64748B', marginLeft: '6px' }}>
                        ({(rt.distance_m / 1000).toFixed(2)} km)
                      </span>
                    </div>

                    <div style={{ fontSize: '12px', color: '#475569', marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                      <div>Blocked roads crossed: <strong>{rt.blocked_edges_crossed}</strong></div>
                      <div>Estimated delay: <strong>+{Math.round(rt.congestion_delay_s)}s</strong></div>
                      <div>Risk penalty: <strong>+{Math.round(rt.hazard_penalty_s)}s</strong></div>
                    </div>

                    <div style={{ marginTop: '8px', fontSize: '10px', color: '#64748B', borderTop: '1px solid rgba(0,0,0,0.06)', paddingTop: '6px' }}>
                      ⚠️ {rt.uncertainty}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Map View with Start / End / Report Pins */}
        <InteractiveMap 
          originPin={[originPoint.lat, originPoint.lon]} 
          destPin={[destPoint.lat, destPoint.lon]}
          reportPin={[reportLat, reportLon]} 
          onMapClick={handleMapClick} 
          height="520px" 
        />

        {/* Community Hazards Feed */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '10px',
          border: '1px solid #E2E8F0',
          padding: '18px 20px',
          boxShadow: '0 2px 6px rgba(0,0,0,0.04)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CloudRain size={18} color="#3576B8" />
              <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: '#1E293B' }}>
                Active Monsoon Hazard Reports ({incidents.length})
              </h3>
            </div>
            <span style={{ fontSize: '12px', color: '#64748B' }}>
              Bounded Bengaluru South-East Network
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {incidents.slice(0, 5).map((inc) => (
              <div
                key={inc.id}
                onClick={() => setHighlightedCoordinates([inc.lat, inc.lon])}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  backgroundColor: '#F8FAFC',
                  border: '1px solid #E2E8F0',
                  cursor: 'pointer',
                  transition: 'background-color 0.1s'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: 700, fontSize: '13px', color: '#1E293B' }}>
                      {inc.road_name || 'Waterlogging Hazard'}
                    </span>
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', color: '#B91C1C', fontWeight: 700 }}>
                      [{inc.severity}]
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#64748B', marginTop: '2px' }}>
                    {inc.evidence_list[0]?.text_notes || 'Reported standing water disruption.'}
                  </div>
                </div>

                <StatusBadge status={inc.status} size="sm" />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Column: Citizen Hazard Reporting Form */}
      <div style={{
        backgroundColor: '#FFFFFF',
        borderRadius: '10px',
        border: '1px solid #E2E8F0',
        padding: '20px',
        boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
        position: 'sticky',
        top: '80px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px', paddingBottom: '10px', borderBottom: '1px solid #E2E8F0' }}>
          <AlertTriangle size={18} color="#C78420" />
          <h3 style={{ fontSize: '15px', fontWeight: 800, margin: 0, color: '#1E293B' }}>
            Report Waterlogging Hazard
          </h3>
        </div>

        <p style={{ fontSize: '12px', color: '#64748B', marginBottom: '14px' }}>
          Select <strong>⚠️ Set Hazard</strong> pin mode and click on map, or adjust coordinates below.
        </p>

        {submitSuccess && (
          <div style={{
            padding: '10px 12px',
            backgroundColor: '#ECFDF5',
            border: '1px solid #A7F3D0',
            borderRadius: '6px',
            fontSize: '12px',
            color: '#065F46',
            marginBottom: '14px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            <CheckCircle2 size={16} color="#059669" />
            <span>{submitSuccess}</span>
          </div>
        )}

        <form onSubmit={handleReportSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
                Latitude
              </label>
              <input
                type="number"
                step="0.0001"
                value={reportLat}
                onChange={(e) => setReportLat(Number(e.target.value))}
                style={{
                  width: '100%',
                  padding: '6px 8px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  fontSize: '12px',
                  backgroundColor: '#F8FAFC'
                }}
                required
              />
            </div>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
                Longitude
              </label>
              <input
                type="number"
                step="0.0001"
                value={reportLon}
                onChange={(e) => setReportLon(Number(e.target.value))}
                style={{
                  width: '100%',
                  padding: '6px 8px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  fontSize: '12px',
                  backgroundColor: '#F8FAFC'
                }}
                required
              />
            </div>
          </div>

          <div>
            <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
              Hazard Type
            </label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 8px',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                fontSize: '12px',
                backgroundColor: '#F8FAFC'
              }}
            >
              <option value="waterlogging">Waterlogging (&gt;25cm Depth)</option>
              <option value="drain_overflow">Storm Drain Overflow / Debris</option>
              <option value="road_submerged">Road Completely Submerged</option>
              <option value="manhole_hazard">Open/Dislodged Manhole Under Water</option>
              <option value="fallen_tree_water">Fallen Tree / Electric Wire in Puddle</option>
            </select>
          </div>

          <div>
            <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
              Reported Severity
            </label>
            <select
              value={reportSeverity}
              onChange={(e) => setReportSeverity(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 8px',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                fontSize: '12px',
                backgroundColor: '#F8FAFC'
              }}
            >
              <option value="critical">Critical (Impassable / Vehicles Stalling)</option>
              <option value="high">High (Deep Water / Crawling Traffic)</option>
              <option value="medium">Medium (One Lane Flooded)</option>
              <option value="low">Low (Puddle / Minor Silt)</option>
            </select>
          </div>

          <div>
            <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
              Observed Description
            </label>
            <textarea
              rows={3}
              value={reportDesc}
              onChange={(e) => setReportDesc(e.target.value)}
              placeholder="Describe water depth, vehicle passability, landmarks..."
              style={{
                width: '100%',
                padding: '6px 8px',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                fontSize: '12px',
                backgroundColor: '#F8FAFC',
                resize: 'none'
              }}
              required
            />
          </div>

          <div>
            <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
              Evidence / Visual Note
            </label>
            <input
              type="text"
              value={reportEvidence}
              onChange={(e) => setReportEvidence(e.target.value)}
              placeholder="e.g. 2 cars stranded near bus stop"
              style={{
                width: '100%',
                padding: '6px 8px',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                fontSize: '12px',
                backgroundColor: '#F8FAFC'
              }}
            />
          </div>

          <div>
            <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
              Attach Field Photo (Simulation)
            </label>
            <select
              value={photoSelected}
              onChange={(e) => setPhotoSelected(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 8px',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                fontSize: '12px',
                backgroundColor: '#F8FAFC'
              }}
            >
              <option value="submerged_underpass">📷 Photo: Submerged Underpass (&gt;45cm Water)</option>
              <option value="drain_overflow">📷 Photo: Choked Storm Drain &amp; Road Puddle</option>
              <option value="tree_water">📷 Photo: Fallen Tree Branch in Flood Water</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              padding: '10px',
              borderRadius: '6px',
              border: 'none',
              backgroundColor: '#0B8B95',
              color: '#FFFFFF',
              fontWeight: 700,
              fontSize: '13px',
              cursor: isSubmitting ? 'not-allowed' : 'pointer',
              marginTop: '6px',
              boxShadow: '0 2px 4px rgba(11, 139, 149, 0.3)'
            }}
          >
            <Send size={15} />
            {isSubmitting ? 'Submitting Report...' : 'Submit Incident Report'}
          </button>
        </form>

        <div style={{ marginTop: '16px', padding: '10px', backgroundColor: '#F8FAFC', borderRadius: '6px', fontSize: '11px', color: '#64748B', display: 'flex', gap: '6px' }}>
          <Info size={14} color="#0B8B95" style={{ flexShrink: 0 }} />
          <span>
            <strong>Civic Notice:</strong> Submitted reports undergo administrative triage & field verification before road restriction authorization.
          </span>
        </div>
      </div>
    </div>
  );
};
