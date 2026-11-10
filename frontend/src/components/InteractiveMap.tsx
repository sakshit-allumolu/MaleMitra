import React, { useEffect, useRef } from 'react';
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
}

export const InteractiveMap: React.FC<InteractiveMapProps> = ({
  onMapClick,
  reportPin,
  originPin,
  destPin,
  height = '560px',
  showRippleOverlay = false
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layersGroupRef = useRef<L.LayerGroup | null>(null);
  
  const { 
    incidents, 
    selectedIncident, 
    setSelectedIncident, 
    roadNetwork, 
    routesResult,
    rippleResult,
    highlightedCoordinates 
  } = useIncidents();

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [12.942, 77.628], // Centered between Koramangala & Indiranagar
      zoom: 13,
      zoomControl: true
    });

    // Free OpenStreetMap standard tiles (No API key required)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
      subdomains: ['a', 'b', 'c']
    }).addTo(map);

    const layerGroup = L.layerGroup().addTo(map);
    layersGroupRef.current = layerGroup;
    mapInstanceRef.current = map;

    // Map click handler
    map.on('click', (e: L.LeafletMouseEvent) => {
      if (onMapClick) {
        onMapClick(e.latlng.lat, e.latlng.lng);
      }
    });

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Render Road Network, Incidents, and Routes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layerGroup = layersGroupRef.current;
    if (!map || !layerGroup || !roadNetwork) return;

    layerGroup.clearLayers();

    // 1. Draw Road Graph Edges
    const blockedEdgeIds = new Set(
      roadNetwork.edges.filter(e => e.is_blocked).map(e => e.edge_id)
    );

    // Check if ripple simulation metrics available
    const rippleEdgeMap = new Map<string, any>();
    if (rippleResult && rippleResult.edge_metrics) {
      rippleResult.edge_metrics.forEach(m => rippleEdgeMap.set(m.edge_id, m));
    }

    roadNetwork.edges.forEach((edge) => {
      if (!edge.geometry || edge.geometry.length < 2) return;

      const isBlocked = edge.is_blocked || blockedEdgeIds.has(edge.edge_id);
      const rippleMetric = rippleEdgeMap.get(edge.edge_id);

      let color = '#3576B8';
      let weight = 3;
      let opacity = 0.65;
      let dashArray = undefined;

      if (isBlocked) {
        color = '#B53A3A';
        weight = 6;
        opacity = 0.95;
        dashArray = '6, 6';
      } else if (showRippleOverlay && rippleMetric) {
        if (rippleMetric.status === 'severely_congested') {
          color = '#E65100';
          weight = 5;
          opacity = 0.9;
        } else if (rippleMetric.status === 'congested') {
          color = '#C78420';
          weight = 4;
          opacity = 0.85;
        }
      } else if (edge.hazard_severity && edge.hazard_severity !== 'none') {
        color = '#D97706';
        weight = 4;
        opacity = 0.8;
      }

      const polyline = L.polyline(edge.geometry, {
        color,
        weight,
        opacity,
        dashArray
      }).addTo(layerGroup);

      const statusLabel = isBlocked 
        ? '🛑 VERIFIED BLOCKED (Closed to Traffic)' 
        : rippleMetric?.status === 'severely_congested'
        ? '⚠️ High Modeled Ripple Congestion'
        : edge.hazard_severity !== 'none'
        ? `⚠️ Unverified Hazard: ${edge.hazard_severity}`
        : 'Open (Normal)';

      polyline.bindTooltip(`
        <div style="font-size: 12px; font-family: sans-serif;">
          <strong>${edge.road_name}</strong><br/>
          <span>Length: ${edge.length_m}m | Base Time: ${edge.travel_time_s}s</span><br/>
          <span>Status: <strong>${statusLabel}</strong></span>
          ${rippleMetric ? `<br/><span>Modeled Flow: ${rippleMetric.disrupted_load} / ${rippleMetric.capacity_proxy} (${rippleMetric.congestion_ratio}x cap)</span>` : ''}
        </div>
      `, { sticky: true });
    });

    // 2. Draw Road Graph Junction Nodes
    roadNetwork.nodes.forEach((node) => {
      const circle = L.circleMarker([node.lat, node.lon], {
        radius: 4,
        fillColor: '#123047',
        color: '#FFFFFF',
        weight: 1.5,
        opacity: 0.9,
        fillOpacity: 0.8
      }).addTo(layerGroup);

      circle.bindTooltip(`<strong>${node.name}</strong> (${node.id})`, { direction: 'top' });
    });

    // 3. Draw Incidents
    incidents.forEach((inc) => {
      let markerColor = '#C78420'; // Amber for reported
      let iconEmoji = '⚠️';

      if (inc.status === 'blocked') {
        markerColor = '#B53A3A';
        iconEmoji = '🛑';
      } else if (inc.status === 'field_verified') {
        markerColor = '#D97706';
        iconEmoji = '📋';
      } else if (inc.status === 'assigned') {
        markerColor = '#6D28D9';
        iconEmoji = '🚒';
      } else if (inc.status === 'cleared') {
        markerColor = '#059669';
        iconEmoji = '✅';
      }

      const isSelected = selectedIncident?.id === inc.id;

      const customIcon = L.divIcon({
        className: 'custom-incident-pin',
        html: `
          <div style="
            width: ${isSelected ? '36px' : '28px'};
            height: ${isSelected ? '36px' : '28px'};
            background-color: ${markerColor};
            border: 2px solid #FFFFFF;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: ${isSelected ? '16px' : '13px'};
            box-shadow: 0 3px 8px rgba(0, 0, 0, 0.3);
            cursor: pointer;
            transition: transform 0.2s;
          ">
            ${iconEmoji}
          </div>
        `,
        iconSize: [isSelected ? 36 : 28, isSelected ? 36 : 28],
        iconAnchor: [isSelected ? 18 : 14, isSelected ? 18 : 14]
      });

      const marker = L.marker([inc.lat, inc.lon], { icon: customIcon }).addTo(layerGroup);

      marker.on('click', () => {
        setSelectedIncident(inc);
      });

      marker.bindTooltip(`
        <div style="font-size: 12px; font-family: sans-serif; line-height: 1.4;">
          <strong>${inc.road_name || 'Waterlogging Hazard'}</strong><br/>
          <span>Status: <strong>${inc.status.toUpperCase()}</strong></span><br/>
          <span>Severity: ${inc.severity.toUpperCase()}</span><br/>
          <span>Type: ${inc.type.replace('_', ' ')}</span>
        </div>
      `, { direction: 'top' });
    });

    // 4. Draw Citizen Report Pin (if setting a new report location)
    if (reportPin) {
      const pinIcon = L.divIcon({
        className: 'report-pin',
        html: `
          <div style="
            width: 32px;
            height: 32px;
            background-color: #0B8B95;
            border: 2px solid #FFFFFF;
            border-radius: 50% 50% 50% 0;
            transform: rotate(-45deg);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 10px rgba(11, 139, 149, 0.5);
          ">
            <div style="transform: rotate(45deg); color: #FFF; font-weight: bold; font-size: 14px;">📍</div>
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 32]
      });
      L.marker(reportPin, { icon: pinIcon }).addTo(layerGroup).bindTooltip('Selected Report Location', { permanent: true });
    }

    // 4b. Draw Origin & Destination Pins
    if (originPin) {
      const originIcon = L.divIcon({
        className: 'origin-pin',
        html: `
          <div style="
            width: 32px;
            height: 32px;
            background-color: #059669;
            border: 2px solid #FFFFFF;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 10px rgba(5, 150, 105, 0.5);
            color: #FFF;
            font-weight: bold;
            font-size: 14px;
          ">
            🏁
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      });
      L.marker(originPin, { icon: originIcon }).addTo(layerGroup).bindTooltip('Origin / Start Location', { permanent: false });
    }

    if (destPin) {
      const destIcon = L.divIcon({
        className: 'dest-pin',
        html: `
          <div style="
            width: 32px;
            height: 32px;
            background-color: #DC2626;
            border: 2px solid #FFFFFF;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 10px rgba(220, 38, 38, 0.5);
            color: #FFF;
            font-weight: bold;
            font-size: 14px;
          ">
            🎯
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      });
      L.marker(destPin, { icon: destIcon }).addTo(layerGroup).bindTooltip('Destination / Target Location', { permanent: false });
    }

    // 5. Draw Calculated Routes (Fastest vs Risk-Aware vs Alternative)
    if (routesResult && routesResult.routes && routesResult.routes.length > 0) {
      routesResult.routes.forEach((route: RoutePathItem) => {
        if (!route.coordinates || route.coordinates.length < 2) return;

        let routeColor = '#64748B';
        let routeWeight = 4;
        let routeOpacity = 0.7;
        let dashStyle = undefined;

        if (route.type === 'risk_aware') {
          routeColor = '#0B8B95'; // Teal for MaleMitra Risk-Aware Detour
          routeWeight = 6;
          routeOpacity = 0.95;
        } else if (route.type === 'alternative') {
          routeColor = '#7C3AED'; // Purple for Alternative
          routeWeight = 4;
          routeOpacity = 0.8;
          dashStyle = '4, 4';
        } else if (route.type === 'fastest') {
          routeColor = '#3B82F6'; // Blue
          routeWeight = 4;
          routeOpacity = 0.75;
        }

        const routeLine = L.polyline(route.coordinates, {
          color: routeColor,
          weight: routeWeight,
          opacity: routeOpacity,
          dashArray: dashStyle
        }).addTo(layerGroup);

        routeLine.bindTooltip(`
          <div style="font-size: 12px; font-family: sans-serif;">
            <strong>${route.label}</strong><br/>
            <span>Duration: ${Math.round(route.estimated_duration_s / 60)} min (${route.estimated_duration_s}s)</span><br/>
            <span>Distance: ${(route.distance_m / 1000).toFixed(2)} km</span><br/>
            <span>Blocked Segments Crossed: <strong>${route.blocked_edges_crossed}</strong></span>
          </div>
        `, { sticky: true });
      });
    }

    // Pan to highlighted coordinate if provided
    if (highlightedCoordinates) {
      map.setView(highlightedCoordinates, 15, { animate: true });
    }
  }, [roadNetwork, incidents, selectedIncident, reportPin, originPin, destPin, routesResult, rippleResult, showRippleOverlay, highlightedCoordinates]);

  return (
    <div style={{ position: 'relative', width: '100%', height, borderRadius: '10px', overflow: 'hidden', border: '1px solid #CBD5E1', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />

      {/* Map Legend */}
      <div style={{
        position: 'absolute',
        bottom: '16px',
        left: '16px',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(4px)',
        padding: '10px 14px',
        borderRadius: '8px',
        border: '1px solid #E2E8F0',
        fontSize: '11px',
        zIndex: 500,
        boxShadow: '0 2px 6px rgba(0,0,0,0.1)',
        maxWidth: '260px'
      }}>
        <div style={{ fontWeight: 700, marginBottom: '6px', color: '#1E293B', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Map Legend & States
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '16px', height: '4px', backgroundColor: '#B53A3A', display: 'inline-block', borderRadius: '2px' }} />
            <span>🛑 Verified Blocked Road</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '16px', height: '4px', backgroundColor: '#0B8B95', display: 'inline-block', borderRadius: '2px' }} />
            <span>🌊 MaleMitra Risk-Aware Route</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '16px', height: '4px', backgroundColor: '#E65100', display: 'inline-block', borderRadius: '2px' }} />
            <span>⚡ Modeled Ripple Congestion</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#C78420', display: 'inline-block' }} />
            <span>⚠️ Citizen Hazard Report</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#6D28D9', display: 'inline-block' }} />
            <span>🚒 Dispatched Field Unit</span>
          </div>
        </div>
      </div>
    </div>
  );
};
