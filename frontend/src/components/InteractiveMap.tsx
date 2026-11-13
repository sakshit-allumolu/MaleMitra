import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { useIncidents } from '../context/IncidentContext';
import { Incident, RoutePathItem } from '../types';

interface InteractiveMapProps {
  onMapClick?: (lat: number, lon: number) => void;
  reportPin?: [number, number] | null;
  originPin?: [number, number] | null;
  destPin?: [number, number] | null;
  height?: string;
  showRippleOverlay?: boolean;
  pinMode?: 'origin' | 'destination' | 'report';
}

// Layer visibility state
interface LayerVisibility {
  roads: boolean;
  blocked: boolean;
  hazards: boolean;
  routes: boolean;
  congestion: boolean;
  nodes: boolean;
}

const DEFAULT_LAYERS: LayerVisibility = {
  roads: true,
  blocked: true,
  hazards: true,
  routes: true,
  congestion: false,
  nodes: true,
};

export const InteractiveMap: React.FC<InteractiveMapProps> = ({
  onMapClick,
  reportPin,
  originPin,
  destPin,
  height = '560px',
  showRippleOverlay = false,
  pinMode = 'origin',
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layersGroupRef = useRef<L.LayerGroup | null>(null);
  // Use ref for onMapClick and pinMode to avoid stale closure bug
  const onMapClickRef = useRef(onMapClick);
  const pinModeRef = useRef(pinMode);

  // Live location refs — kept as refs (not state) so position updates never
  // trigger a full React re-render; the Leaflet layers are updated directly.
  const userDotRef = useRef<L.CircleMarker | null>(null);
  const userRingRef = useRef<L.Circle | null>(null);
  const watchIdRef = useRef<number | null>(null);
  const [locationStatus, setLocationStatus] = useState<'idle' | 'tracking' | 'denied' | 'unavailable'>('idle');
  const [locationAccuracy, setLocationAccuracy] = useState<number | null>(null);
  const [followUser, setFollowUser] = useState(false);
  const followUserRef = useRef(false);

  const [layers, setLayers] = useState<LayerVisibility>(DEFAULT_LAYERS);
  const [legendOpen, setLegendOpen] = useState(true);

  const {
    incidents,
    selectedIncident,
    setSelectedIncident,
    roadNetwork,
    routesResult,
    rippleResult,
    highlightedCoordinates,
  } = useIncidents();

  // Always keep refs in sync — this is the fix for the stale closure bug
  useEffect(() => { onMapClickRef.current = onMapClick; }, [onMapClick]);
  useEffect(() => { pinModeRef.current = pinMode; }, [pinMode]);
  useEffect(() => { followUserRef.current = followUser; }, [followUser]);

  // ── Live user location via watchPosition ──────────────────────────────────
  useEffect(() => {
    if (!navigator.geolocation) {
      setLocationStatus('unavailable');
      return;
    }

    const updatePosition = (pos: GeolocationPosition) => {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      const acc = pos.coords.accuracy;
      setLocationAccuracy(Math.round(acc));
      setLocationStatus('tracking');

      const map = mapInstanceRef.current;
      if (!map) return;

      // Create or move the blue dot
      if (!userDotRef.current) {
        userDotRef.current = L.circleMarker([lat, lon], {
          radius: 10,
          fillColor: '#2563EB',
          fillOpacity: 0.95,
          color: '#ffffff',
          weight: 3,
          pane: 'markerPane',
        }).addTo(map).bindTooltip('You are here', { direction: 'top', permanent: false });
      } else {
        userDotRef.current.setLatLng([lat, lon]);
      }

      // Create or resize the accuracy ring
      if (!userRingRef.current) {
        userRingRef.current = L.circle([lat, lon], {
          radius: acc,
          fillColor: '#2563EB',
          fillOpacity: 0.08,
          color: '#2563EB',
          weight: 1,
          opacity: 0.35,
          pane: 'overlayPane',
        }).addTo(map);
      } else {
        userRingRef.current.setLatLng([lat, lon]);
        userRingRef.current.setRadius(acc);
      }

      // Pan map if follow mode is on
      if (followUserRef.current) {
        map.panTo([lat, lon], { animate: true, duration: 0.5 });
      }
    };

    const handleError = (err: GeolocationPositionError) => {
      if (err.code === err.PERMISSION_DENIED) setLocationStatus('denied');
      else setLocationStatus('unavailable');
    };

    watchIdRef.current = navigator.geolocation.watchPosition(
      updatePosition,
      handleError,
      { enableHighAccuracy: true, maximumAge: 3000, timeout: 10000 }
    );

    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
      // Remove dot and ring from map on unmount
      userDotRef.current?.remove();
      userDotRef.current = null;
      userRingRef.current?.remove();
      userRingRef.current = null;
    };
  }, []); // runs once — watchPosition handles its own updates

  // Initialize Map once
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [12.942, 77.628],
      zoom: 13,
      zoomControl: true,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    const layerGroup = L.layerGroup().addTo(map);
    layersGroupRef.current = layerGroup;
    mapInstanceRef.current = map;

    // Click handler reads from ref — never stale
    map.on('click', (e: L.LeafletMouseEvent) => {
      if (onMapClickRef.current) {
        onMapClickRef.current(e.latlng.lat, e.latlng.lng);
      }
    });

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Redraw layers whenever data or visibility changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layerGroup = layersGroupRef.current;
    if (!map || !layerGroup || !roadNetwork) return;

    layerGroup.clearLayers();

    const blockedEdgeIds = new Set(
      roadNetwork.edges.filter(e => e.is_blocked).map(e => e.edge_id)
    );

    const rippleEdgeMap = new Map<string, any>();
    if (rippleResult?.edge_metrics) {
      rippleResult.edge_metrics.forEach(m => rippleEdgeMap.set(m.edge_id, m));
    }

    // ── 1. Road Network Edges ─────────────────────────────────────────────
    if (layers.roads || layers.blocked) {
      roadNetwork.edges.forEach((edge) => {
        if (!edge.geometry || edge.geometry.length < 2) return;

        const isBlocked = edge.is_blocked || blockedEdgeIds.has(edge.edge_id);
        if (isBlocked && !layers.blocked) return;
        if (!isBlocked && !layers.roads) return;

        const rippleMetric = rippleEdgeMap.get(edge.edge_id);

        let color = '#94A3B8';
        let weight = 2.5;
        let opacity = 0.55;
        let dashArray: string | undefined;

        if (isBlocked) {
          color = '#DC2626';
          weight = 6;
          opacity = 0.95;
          dashArray = '8, 5';
        } else if (layers.congestion && showRippleOverlay && rippleMetric) {
          if (rippleMetric.status === 'severely_congested') {
            color = '#EA580C'; weight = 5; opacity = 0.9;
          } else if (rippleMetric.status === 'congested') {
            color = '#D97706'; weight = 4; opacity = 0.85;
          } else {
            color = '#22C55E'; weight = 2.5; opacity = 0.6;
          }
        } else if (edge.hazard_severity && edge.hazard_severity !== 'none') {
          color = '#F59E0B'; weight = 3.5; opacity = 0.8;
        }

        const polyline = L.polyline(edge.geometry as [number, number][], {
          color, weight, opacity, dashArray,
        }).addTo(layerGroup);

        const statusLabel = isBlocked
          ? '🛑 BLOCKED — Closed to traffic'
          : rippleMetric?.status === 'severely_congested' ? '⚡ High congestion (ripple model)'
          : edge.hazard_severity !== 'none' ? `⚠️ Hazard: ${edge.hazard_severity}`
          : '✅ Open — Normal flow';

        polyline.bindTooltip(`
          <div style="font-size:12px;font-family:system-ui;line-height:1.5">
            <strong>${edge.road_name}</strong><br/>
            ${edge.length_m}m · ${Math.round(edge.travel_time_s)}s base<br/>
            <span style="color:${isBlocked ? '#DC2626' : '#059669'}">${statusLabel}</span>
            ${rippleMetric ? `<br/>Flow: ${rippleMetric.disrupted_load}/${rippleMetric.capacity_proxy} (${rippleMetric.congestion_ratio}×)` : ''}
          </div>
        `, { sticky: true, className: 'mm-tooltip' });
      });
    }

    // ── 2. Junction Nodes ─────────────────────────────────────────────────
    if (layers.nodes) {
      roadNetwork.nodes.forEach((node) => {
        const circle = L.circleMarker([node.lat, node.lon], {
          radius: 4,
          fillColor: '#1E293B',
          color: '#FFFFFF',
          weight: 1.5,
          opacity: 1,
          fillOpacity: 0.85,
        }).addTo(layerGroup);
        circle.bindTooltip(`<strong>${node.name}</strong>`, { direction: 'top' });
      });
    }

    // ── 3. Incident Markers ───────────────────────────────────────────────
    if (layers.hazards) {
      incidents.forEach((inc) => {
        const statusColors: Record<string, string> = {
          reported: '#F59E0B', under_review: '#6366F1',
          assigned: '#8B5CF6', field_verified: '#EA580C',
          blocked: '#DC2626', clearance_proposed: '#0891B2',
          cleared: '#059669', rejected: '#64748B',
        };
        const statusEmoji: Record<string, string> = {
          reported: '⚠️', under_review: '🔍', assigned: '🚒',
          field_verified: '📋', blocked: '🛑', clearance_proposed: '🔧',
          cleared: '✅', rejected: '❌',
        };

        const color = statusColors[inc.status] ?? '#94A3B8';
        const emoji = statusEmoji[inc.status] ?? '⚠️';
        const isSelected = selectedIncident?.id === inc.id;
        const size = isSelected ? 38 : 28;

        const icon = L.divIcon({
          className: '',
          html: `<div style="
            width:${size}px;height:${size}px;
            background:${color};border:2.5px solid #FFF;
            border-radius:50%;display:flex;align-items:center;justify-content:center;
            font-size:${isSelected ? 17 : 13}px;
            box-shadow:0 3px 10px ${color}66;
            cursor:pointer;
            ${isSelected ? 'outline:3px solid ' + color + ';outline-offset:2px;' : ''}
          ">${emoji}</div>`,
          iconSize: [size, size],
          iconAnchor: [size / 2, size / 2],
        });

        const marker = L.marker([inc.lat, inc.lon], { icon }).addTo(layerGroup);
        marker.on('click', () => setSelectedIncident(inc));
        marker.bindTooltip(`
          <div style="font-size:12px;font-family:system-ui;line-height:1.5">
            <strong>${inc.road_name ?? 'Hazard Report'}</strong><br/>
            ${inc.type.replace(/_/g, ' ')} · ${inc.severity.toUpperCase()}<br/>
            Status: <strong>${inc.status.replace(/_/g, ' ').toUpperCase()}</strong>
          </div>
        `, { direction: 'top' });
      });
    }

    // ── 4. Report / Origin / Destination Pins ────────────────────────────
    const makePin = (pos: [number, number], bg: string, label: string, symbol: string, permanent = false) => {
      const icon = L.divIcon({
        className: '',
        html: `<div style="
          position:relative;width:34px;height:34px;
          background:${bg};border:2.5px solid #FFF;
          border-radius:50% 50% 50% 0;transform:rotate(-45deg);
          box-shadow:0 4px 12px ${bg}66;
          display:flex;align-items:center;justify-content:center;
        ">
          <span style="transform:rotate(45deg);font-size:15px">${symbol}</span>
        </div>`,
        iconSize: [34, 34],
        iconAnchor: [17, 34],
      });
      const m = L.marker(pos, { icon }).addTo(layerGroup);
      m.bindTooltip(label, { permanent, direction: 'top', className: 'mm-pin-label' });
      return m;
    };

    if (reportPin) makePin(reportPin, '#0B8B95', 'Hazard Location', '📍', true);
    if (originPin) makePin(originPin, '#059669', 'Start', '🏁', true);
    if (destPin) makePin(destPin, '#DC2626', 'Destination', '🎯', true);

    // ── 5. Routes ─────────────────────────────────────────────────────────
    if (layers.routes && routesResult?.routes) {
      const routeStyles: Record<string, { color: string; weight: number; dash?: string }> = {
        fastest:    { color: '#3B82F6', weight: 5 },
        risk_aware: { color: '#0B8B95', weight: 7 },
        alternative:{ color: '#7C3AED', weight: 4, dash: '6,4' },
      };

      routesResult.routes.forEach((route: RoutePathItem) => {
        if (!route.coordinates || route.coordinates.length < 2) return;
        const s = routeStyles[route.type] ?? { color: '#64748B', weight: 4 };

        const line = L.polyline(route.coordinates as [number, number][], {
          color: s.color, weight: s.weight, opacity: 0.92,
          dashArray: s.dash,
          lineCap: 'round', lineJoin: 'round',
        }).addTo(layerGroup);

        line.bindTooltip(`
          <div style="font-size:12px;font-family:system-ui;line-height:1.5">
            <strong>${route.label}</strong><br/>
            ${Math.round(route.estimated_duration_s / 60)} min · ${(route.distance_m / 1000).toFixed(1)} km<br/>
            Blocked crossings: <strong style="color:${route.blocked_edges_crossed > 0 ? '#DC2626' : '#059669'}">${route.blocked_edges_crossed}</strong>
          </div>
        `, { sticky: true });

        // Animate route drawing for risk_aware route
        if (route.type === 'risk_aware') {
          line.setStyle({ weight: 7, color: '#0B8B95' });
        }
      });
    }

  }, [roadNetwork, incidents, selectedIncident, reportPin, originPin, destPin, routesResult, rippleResult, showRippleOverlay, layers]);

  // Pan to highlighted coordinate ONLY when it actually changes — kept separate
  // from the layer-redraw effect so polling/refreshes never trigger a zoom jump.
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !highlightedCoordinates) return;
    const currentZoom = map.getZoom();
    // Pan without zooming in if already close enough; zoom to 15 only from far away
    const targetZoom = currentZoom >= 14 ? currentZoom : 15;
    map.setView(highlightedCoordinates, targetZoom, { animate: true });
  }, [highlightedCoordinates]);

  // ── Cursor style based on pin mode ────────────────────────────────────────
  const cursorStyle: Record<string, string> = {
    origin: 'crosshair',
    destination: 'crosshair',
    report: 'crosshair',
  };

  // ── Layer toggle helpers ───────────────────────────────────────────────────
  const toggleLayer = (key: keyof LayerVisibility) =>
    setLayers(prev => ({ ...prev, [key]: !prev[key] }));

  const LEGEND_ITEMS = [
    { key: 'roads' as const, color: '#94A3B8', label: 'Road Network', dash: false },
    { key: 'blocked' as const, color: '#DC2626', label: 'Blocked Roads', dash: true },
    { key: 'routes' as const, color: '#0B8B95', label: 'Safe Routes', dash: false },
    { key: 'hazards' as const, color: '#F59E0B', label: 'Hazard Reports', dot: true },
    { key: 'congestion' as const, color: '#EA580C', label: 'Ripple Congestion', dash: false },
    { key: 'nodes' as const, color: '#1E293B', label: 'Junctions', dot: true },
  ];

  const PIN_MODE_LABEL: Record<string, { label: string; color: string }> = {
    origin:      { label: '🏁 Click map to set Start', color: '#059669' },
    destination: { label: '🎯 Click map to set Destination', color: '#DC2626' },
    report:      { label: '📍 Click map to pin Hazard', color: '#0B8B95' },
  };
  const activePinLabel = PIN_MODE_LABEL[pinMode];

  return (
    <div style={{ position: 'relative', width: '100%', height, borderRadius: '10px', overflow: 'hidden', border: '1px solid #CBD5E1', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
      <div
        ref={mapContainerRef}
        style={{ width: '100%', height: '100%', cursor: cursorStyle[pinMode] ?? 'default' }}
      />

      {/* ── Live Location Controls (top-right) ────────────────────────────── */}
      <div style={{
        position: 'absolute', top: '10px', right: '10px',
        display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '5px',
        zIndex: 500,
      }}>
        {/* Follow-me toggle button */}
        <button
          onClick={() => setFollowUser(f => !f)}
          title={followUser ? 'Stop following my location' : 'Follow my location'}
          style={{
            display: 'flex', alignItems: 'center', gap: '5px',
            padding: '5px 10px', borderRadius: '20px', border: 'none',
            fontSize: '11px', fontWeight: 700, cursor: 'pointer',
            backgroundColor: followUser ? '#2563EB' : 'rgba(255,255,255,0.95)',
            color: followUser ? '#fff' : '#1E293B',
            boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
            transition: 'background 0.2s',
          }}
        >
          {/* Blue dot icon */}
          <span style={{
            width: '10px', height: '10px', borderRadius: '50%',
            backgroundColor: locationStatus === 'tracking' ? '#2563EB' : '#94A3B8',
            border: '2px solid #fff',
            boxShadow: locationStatus === 'tracking' ? '0 0 0 2px #2563EB44' : 'none',
            flexShrink: 0,
            display: 'inline-block',
          }} />
          {followUser ? 'Following' : 'Follow Me'}
        </button>

        {/* Accuracy badge — shown only when tracking */}
        {locationStatus === 'tracking' && locationAccuracy !== null && (
          <div style={{
            padding: '2px 8px', borderRadius: '10px', fontSize: '10px', fontWeight: 600,
            backgroundColor: 'rgba(255,255,255,0.92)',
            color: locationAccuracy <= 20 ? '#059669' : locationAccuracy <= 60 ? '#92400E' : '#B91C1C',
            boxShadow: '0 1px 4px rgba(0,0,0,0.12)',
          }}>
            📡 ±{locationAccuracy}m
          </div>
        )}

        {/* Permission denied / unavailable notice */}
        {(locationStatus === 'denied' || locationStatus === 'unavailable') && (
          <div style={{
            padding: '3px 8px', borderRadius: '10px', fontSize: '10px', fontWeight: 600,
            backgroundColor: 'rgba(255,255,255,0.92)', color: '#B91C1C',
            boxShadow: '0 1px 4px rgba(0,0,0,0.12)',
          }}>
            {locationStatus === 'denied' ? '⛔ Location denied' : '📡 GPS unavailable'}
          </div>
        )}
      </div>

      {/* ── Active Pin Mode Banner ─────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', top: '10px', left: '50%', transform: 'translateX(-50%)',
        backgroundColor: activePinLabel.color,
        color: '#FFF', fontWeight: 700, fontSize: '12px',
        padding: '5px 14px', borderRadius: '20px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
        zIndex: 500, pointerEvents: 'none',
        whiteSpace: 'nowrap',
      }}>
        {activePinLabel.label}
      </div>

      {/* ── Layer Legend / Toggle ──────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', bottom: '16px', left: '10px',
        backgroundColor: 'rgba(255,255,255,0.97)',
        borderRadius: '10px', border: '1px solid #E2E8F0',
        boxShadow: '0 2px 10px rgba(0,0,0,0.12)',
        zIndex: 500, minWidth: '185px', overflow: 'hidden',
      }}>
        {/* Legend header */}
        <button
          onClick={() => setLegendOpen(o => !o)}
          style={{
            width: '100%', padding: '7px 12px',
            backgroundColor: '#1E293B', border: 'none',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            cursor: 'pointer',
          }}
        >
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#FFF', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Map Layers
          </span>
          <span style={{ color: '#94A3B8', fontSize: '14px' }}>{legendOpen ? '▲' : '▼'}</span>
        </button>

        {legendOpen && (
          <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
            {LEGEND_ITEMS.map(item => (
              <label
                key={item.key}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  cursor: 'pointer', fontSize: '11px',
                  color: layers[item.key] ? '#1E293B' : '#94A3B8',
                  padding: '3px 2px', borderRadius: '4px',
                  userSelect: 'none',
                }}
              >
                <input
                  type="checkbox"
                  checked={layers[item.key]}
                  onChange={() => toggleLayer(item.key)}
                  style={{ display: 'none' }}
                />
                {/* Visual checkbox */}
                <div style={{
                  width: '14px', height: '14px', borderRadius: '3px', flexShrink: 0,
                  border: `1.5px solid ${layers[item.key] ? item.color : '#CBD5E1'}`,
                  backgroundColor: layers[item.key] ? item.color : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {layers[item.key] && (
                    <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                      <path d="M1 3L3 5L7 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </div>
                {/* Swatch */}
                {(item as any).dot
                  ? <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: item.color, display: 'inline-block', flexShrink: 0 }} />
                  : <span style={{
                      width: '18px', height: '4px', borderRadius: '2px',
                      backgroundColor: item.color, display: 'inline-block', flexShrink: 0,
                      backgroundImage: (item as any).dash ? `repeating-linear-gradient(90deg,${item.color} 0,${item.color} 5px,transparent 5px,transparent 8px)` : undefined,
                    }} />
                }
                {item.label}
              </label>
            ))}

            {/* Quick presets */}
            <div style={{ borderTop: '1px solid #F1F5F9', marginTop: '4px', paddingTop: '6px', display: 'flex', gap: '5px' }}>
              <button onClick={() => setLayers({ roads: true, blocked: true, hazards: true, routes: true, congestion: true, nodes: true })}
                style={{ flex: 1, fontSize: '10px', fontWeight: 700, padding: '3px', border: '1px solid #CBD5E1', borderRadius: '4px', backgroundColor: '#F8FAFC', cursor: 'pointer', color: '#475569' }}>
                All On
              </button>
              <button onClick={() => setLayers({ roads: true, blocked: true, hazards: false, routes: true, congestion: false, nodes: false })}
                style={{ flex: 1, fontSize: '10px', fontWeight: 700, padding: '3px', border: '1px solid #CBD5E1', borderRadius: '4px', backgroundColor: '#F8FAFC', cursor: 'pointer', color: '#475569' }}>
                Routes
              </button>
              <button onClick={() => setLayers({ roads: true, blocked: true, hazards: true, routes: false, congestion: false, nodes: false })}
                style={{ flex: 1, fontSize: '10px', fontWeight: 700, padding: '3px', border: '1px solid #CBD5E1', borderRadius: '4px', backgroundColor: '#F8FAFC', cursor: 'pointer', color: '#475569' }}>
                Hazards
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
