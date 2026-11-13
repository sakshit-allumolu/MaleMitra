import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useIncidents } from '../context/IncidentContext';
import { useAuth } from '../context/AuthContext';
import { ApiClient } from '../services/api';
import { InteractiveMap } from '../components/InteractiveMap';
import { StatusBadge } from '../components/StatusBadge';
import { LocationPoint } from '../types';
import {
  CloudRain, Navigation, AlertTriangle, Send, MapPin,
  ArrowRight, ShieldCheck, CheckCircle2, Clock, Info,
  Crosshair, Search, Compass, Car, Sparkles, Sliders,
  Volume2, VolumeX, ChevronRight, MapPinned
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

// ── helpers ──────────────────────────────────────────────────────────────────
function buildDirectionSteps(routesResult: any): { step: number; icon: string; instruction: string; road: string; dist: string }[] {
  if (!routesResult?.routes) return [];
  const route = routesResult.routes.find((r: any) => r.type === 'risk_aware') ?? routesResult.routes[0];
  if (!route) return [];

  // Prefer real OSRM steps if available
  if (route.osrm_steps && route.osrm_steps.length > 0) {
    return route.osrm_steps.map((s: any, i: number) => ({
      step: i + 1,
      icon: s.icon ?? '→',
      instruction: s.instruction,
      road: s.road ?? '',
      dist: s.dist ?? '',
    }));
  }

  // Fallback to node names
  const nodes: string[] = route.node_names ?? [];
  if (nodes.length < 2) return [];
  return [
    { step: 1, icon: '🏁', instruction: `Start from ${nodes[0]}`, road: '', dist: '' },
    ...nodes.slice(1, -1).map((n: string, i: number) => ({ step: i + 2, icon: '→', instruction: `Pass through ${n}`, road: '', dist: '' })),
    { step: nodes.length, icon: '🎯', instruction: `Arrive at ${nodes[nodes.length - 1]}`, road: '', dist: '' },
  ];
}

export const CitizenWorkspace: React.FC = () => {
  const { incidents, refreshData, calculateRoutes, routesResult, isLoading, setHighlightedCoordinates } = useIncidents();
  const { currentUser } = useAuth();

  // Voice narration
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [activeDirectionStep, setActiveDirectionStep] = useState(0);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  const speakText = useCallback((text: string) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'en-IN';
    u.rate = 0.92;
    u.pitch = 1;
    u.onstart = () => setIsSpeaking(true);
    u.onend = () => setIsSpeaking(false);
    utteranceRef.current = u;
    window.speechSynthesis.speak(u);
  }, []);

  const stopSpeech = useCallback(() => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, []);

  const announceRoute = useCallback(() => {
    if (!routesResult) return;
    const route = routesResult.routes?.find((r: any) => r.type === 'risk_aware') ?? routesResult.routes?.[0];
    if (!route) return;
    const mins = Math.round(route.estimated_duration_s / 60);
    const km = (route.distance_m / 1000).toFixed(1);
    const blocked = route.blocked_edges_crossed;
    const text = `MaleMitra route found. ${mins} minutes, ${km} kilometres. ${blocked === 0 ? 'No blocked roads on this route. Safe to proceed.' : `Warning: ${blocked} blocked segment${blocked > 1 ? 's' : ''} detected. Use the risk-aware route for a safer journey.`}`;
    speakText(text);
  }, [routesResult, speakText]);

  // Auto-announce when route is fetched and voice is on
  useEffect(() => {
    if (voiceEnabled && routesResult) {
      announceRoute();
      setActiveDirectionStep(0);
    }
  }, [routesResult]);

  // Dynamic Route Location States
  const [originQuery, setOriginQuery] = useState<string>('Sony World Junction (Koramangala)');
  const [originPoint, setOriginPoint] = useState<LocationPoint>({ name: 'Sony World Junction (Koramangala)', lat: 12.9352, lon: 77.6245 });
  const [originSuggestions, setOriginSuggestions] = useState<LocationPoint[]>([]);
  const [originSearching, setOriginSearching] = useState(false);
  const [originActiveIdx, setOriginActiveIdx] = useState(-1);

  const [destQuery, setDestQuery] = useState<string>('Indiranagar 100ft Rd / CMH Rd');
  const [destPoint, setDestPoint] = useState<LocationPoint>({ name: 'Indiranagar 100ft Rd / CMH Rd', lat: 12.9780, lon: 77.6410 });
  const [destSuggestions, setDestSuggestions] = useState<LocationPoint[]>([]);
  const [destSearching, setDestSearching] = useState(false);
  const [destActiveIdx, setDestActiveIdx] = useState(-1);

  // Refs for outside-click-to-close
  const originBoxRef = useRef<HTMLDivElement>(null);
  const destBoxRef = useRef<HTMLDivElement>(null);

  // Live-tracking flags: true when that endpoint was set via GPS button
  // so movement re-calculates the route automatically.
  const [liveOrigin, setLiveOrigin] = useState(false);
  const [liveDest,   setLiveDest]   = useState(false);
  const liveOriginRef = useRef(false);
  const liveDestRef   = useRef(false);
  const liveRouteWatchIdRef = useRef<number | null>(null);
  const liveRouteDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastLiveCalcRef = useRef<{ lat: number; lon: number } | null>(null);
  const [liveRouteUpdating, setLiveRouteUpdating] = useState(false);
  const [rerouting, setRerouting] = useState(false);
  const reroutingRef = useRef(false); // prevents double-trigger while reroute in-flight

  // Keep live refs in sync
  useEffect(() => { liveOriginRef.current = liveOrigin; }, [liveOrigin]);
  useEffect(() => { liveDestRef.current   = liveDest;   }, [liveDest]);

  // Store current dest/origin/routesResult in refs so watchPosition callbacks
  // can read the latest values without stale closures.
  const destPointRef = useRef(destPoint);
  useEffect(() => { destPointRef.current = destPoint; }, [destPoint]);
  const originPointRef = useRef(originPoint);
  useEffect(() => { originPointRef.current = originPoint; }, [originPoint]);
  const routesResultRef = useRef(routesResult);
  useEffect(() => { routesResultRef.current = routesResult; }, [routesResult]);

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
  const [reportLocQuery, setReportLocQuery] = useState<string>('Sony World Junction (Koramangala)');
  const [reportLocSuggestions, setReportLocSuggestions] = useState<LocationPoint[]>([]);
  const [reportLocSearching, setReportLocSearching] = useState(false);
  const [reportLocActiveIdx, setReportLocActiveIdx] = useState(-1);
  const [reportLocGpsStatus, setReportLocGpsStatus] = useState<string | null>(null);
  const reportLocBoxRef = useRef<HTMLDivElement>(null);

  const [reportType, setReportType] = useState<string>('waterlogging');
  const [reportSeverity, setReportSeverity] = useState<string>('high');
  const [reportDesc, setReportDesc] = useState<string>('Heavy water accumulation across roadway. Water level above 30cm.');
  const [reportEvidence, setReportEvidence] = useState<string>('Observed slow moving traffic and 1 stalled scooter.');
  const [photoSelected, setPhotoSelected] = useState<string>('submerged_underpass');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  // Outside-click-to-close for both dropdowns
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (originBoxRef.current && !originBoxRef.current.contains(e.target as Node)) {
        setOriginSuggestions([]);
        setOriginActiveIdx(-1);
      }
      if (destBoxRef.current && !destBoxRef.current.contains(e.target as Node)) {
        setDestSuggestions([]);
        setDestActiveIdx(-1);
      }
      if (reportLocBoxRef.current && !reportLocBoxRef.current.contains(e.target as Node)) {
        setReportLocSuggestions([]);
        setReportLocActiveIdx(-1);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  // ── Off-route detection utility ───────────────────────────────────────────
  // Returns the minimum distance in metres from (lat, lon) to any segment of
  // a route polyline [[lat,lon], ...].
  const distanceToPolyline = (lat: number, lon: number, coords: [number, number][]): number => {
    if (!coords || coords.length < 2) return Infinity;
    const M = 111_000; // metres per degree latitude
    let minDist = Infinity;
    for (let i = 0; i < coords.length - 1; i++) {
      const [lat1, lon1] = coords[i];
      const [lat2, lon2] = coords[i + 1];
      // Project point onto segment in a flat-earth approximation
      const cosLat = Math.cos(lat * Math.PI / 180);
      const ax = (lon1 - lon) * M * cosLat, ay = (lat1 - lat) * M;
      const bx = (lon2 - lon1) * M * cosLat, by = (lat2 - lat1) * M;
      const t = Math.max(0, Math.min(1, -(ax * bx + ay * by) / (bx * bx + by * by + 1e-12)));
      const dx = ax + bx * t, dy = ay + by * t;
      const d = Math.sqrt(dx * dx + dy * dy);
      if (d < minDist) minDist = d;
    }
    return minDist;
  };

  // ── Live route recalculation + off-route rerouting ────────────────────────
  // watchPosition fires on every GPS update:
  //  • If a live endpoint exists: debounce 4 s then recalculate (normal tracking)
  //  • If a route is active AND the user is >50 m off the nearest route segment:
  //    cancel the 4 s timer and reroute immediately (1 s debounce to avoid jitter)
  useEffect(() => {
    if (!navigator.geolocation) return;

    // OFF_ROUTE_THRESHOLD_M: how far off the polyline before rerouting triggers.
    // 50 m covers lane changes / GPS wobble; raises to 80 m in poor accuracy.
    const OFF_ROUTE_M = 50;

    const triggerReroute = async (lat: number, lon: number) => {
      if (reroutingRef.current) return; // already rerouting
      reroutingRef.current = true;
      setRerouting(true);
      setLiveRouteUpdating(false);
      lastLiveCalcRef.current = { lat, lon };
      try {
        // Always reroute from current position to the fixed destination
        const dest = destPointRef.current;
        const name = `📍 My Location (${lat.toFixed(4)}, ${lon.toFixed(4)})`;
        // Update origin to current position
        originPointRef.current = { name, lat, lon };
        setOriginPoint({ name, lat, lon });
        setOriginQuery(name);
        await calculateRoutes({ lat, lon }, dest);
      } finally {
        reroutingRef.current = false;
        setRerouting(false);
      }
    };

    const handlePosition = (pos: GeolocationPosition) => {
      const lat = Number(pos.coords.latitude.toFixed(5));
      const lon = Number(pos.coords.longitude.toFixed(5));
      const accuracy = pos.coords.accuracy;

      const isLiveOrigin = liveOriginRef.current;
      const isLiveDest   = liveDestRef.current;
      const hasActiveRoute = !!routesResultRef.current?.routes?.length;

      // ── Off-route detection (independent of live endpoint flags) ──────────
      // Triggers whenever a route exists and origin was set via GPS.
      if (hasActiveRoute && isLiveOrigin && !reroutingRef.current) {
        // Pick the risk_aware route coords for deviation check (most likely being followed)
        const routes = routesResultRef.current!.routes;
        const activeRoute = routes.find(r => r.type === 'risk_aware') ?? routes[0];
        const threshold = accuracy > 30 ? Math.max(OFF_ROUTE_M, accuracy * 1.5) : OFF_ROUTE_M;
        const distOff = distanceToPolyline(lat, lon, activeRoute.coordinates);

        if (distOff > threshold) {
          // Cancel any pending normal-tracking debounce and reroute immediately
          if (liveRouteDebounceRef.current) clearTimeout(liveRouteDebounceRef.current);
          liveRouteDebounceRef.current = setTimeout(() => triggerReroute(lat, lon), 1000);
          return; // reroute handles origin update + calculateRoutes
        }
      }

      // ── Normal live-tracking (endpoint set via GPS) ────────────────────────
      if (!isLiveOrigin && !isLiveDest) return;

      // Skip if we haven't moved more than ~15 m since last recalc
      const last = lastLiveCalcRef.current;
      if (last) {
        const dLat = (lat - last.lat) * 111_000;
        const dLon = (lon - last.lon) * 111_000 * Math.cos(lat * Math.PI / 180);
        if (Math.sqrt(dLat * dLat + dLon * dLon) < 15) return;
      }

      // Update live endpoint label + map pin immediately
      const name = `📍 My Location (${lat.toFixed(4)}, ${lon.toFixed(4)})`;
      if (isLiveOrigin) {
        originPointRef.current = { name, lat, lon };
        setOriginPoint({ name, lat, lon });
        setOriginQuery(name);
      }
      if (isLiveDest) {
        destPointRef.current = { name: `🎯 My Location (${lat.toFixed(4)}, ${lon.toFixed(4)})`, lat, lon };
        setDestPoint(destPointRef.current);
        setDestQuery(destPointRef.current.name);
      }

      // Debounce the route recalculation — wait 4 s of stillness
      if (liveRouteDebounceRef.current) clearTimeout(liveRouteDebounceRef.current);
      liveRouteDebounceRef.current = setTimeout(async () => {
        lastLiveCalcRef.current = { lat, lon };
        setLiveRouteUpdating(true);
        try {
          const origin = isLiveOrigin ? { lat, lon } : originPointRef.current;
          const dest   = isLiveDest   ? { lat, lon } : destPointRef.current;
          await calculateRoutes(origin, dest);
        } finally {
          setLiveRouteUpdating(false);
        }
      }, 4000);
    };

    liveRouteWatchIdRef.current = navigator.geolocation.watchPosition(
      handlePosition,
      () => { /* silent — map component already handles error UI */ },
      { enableHighAccuracy: true, maximumAge: 3000, timeout: 12000 }
    );

    return () => {
      if (liveRouteWatchIdRef.current !== null) {
        navigator.geolocation.clearWatch(liveRouteWatchIdRef.current);
        liveRouteWatchIdRef.current = null;
      }
      if (liveRouteDebounceRef.current) clearTimeout(liveRouteDebounceRef.current);
    };
  }, []); // runs once — refs handle all live state

  // Debounced search: hazard location
  useEffect(() => {
    if (reportLocQuery.trim().length < 2) {
      setReportLocSuggestions([]);
      setReportLocActiveIdx(-1);
      return;
    }
    const timer = setTimeout(async () => {
      setReportLocSearching(true);
      try {
        const places = await ApiClient.searchLocations(reportLocQuery);
        if (places.length > 0) {
          setReportLocSuggestions(places);
        } else {
          const local = POPULAR_BENGALURU_CORRIDORS.filter(p =>
            p.name.toLowerCase().includes(reportLocQuery.toLowerCase())
          );
          setReportLocSuggestions(local);
        }
      } finally {
        setReportLocSearching(false);
        setReportLocActiveIdx(-1);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [reportLocQuery]);

  const selectReportLoc = (sug: LocationPoint) => {
    setReportLat(sug.lat);
    setReportLon(sug.lon);
    setReportLocQuery(sug.name);
    setReportLocSuggestions([]);
    setReportLocActiveIdx(-1);
    setHighlightedCoordinates([sug.lat, sug.lon]);
    setPinMode('report');
  };

  const handleReportLocKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!reportLocSuggestions.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setReportLocActiveIdx(i => Math.min(i + 1, reportLocSuggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setReportLocActiveIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && reportLocActiveIdx >= 0) {
      e.preventDefault();
      selectReportLoc(reportLocSuggestions[reportLocActiveIdx]);
    } else if (e.key === 'Escape') {
      setReportLocSuggestions([]);
      setReportLocActiveIdx(-1);
    }
  };

  const handleReportLocGps = () => {
    if (!navigator.geolocation) {
      setReportLocGpsStatus('⛔ Geolocation not supported by your browser.');
      setTimeout(() => setReportLocGpsStatus(null), 4000);
      return;
    }
    setReportLocGpsStatus('Acquiring GPS coordinates...');
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(4));
        const lon = Number(pos.coords.longitude.toFixed(4));
        setReportLat(lat);
        setReportLon(lon);
        setReportLocQuery(`📍 My Location (${lat}, ${lon})`);
        setHighlightedCoordinates([lat, lon]);
        setPinMode('report');
        setReportLocGpsStatus(`GPS acquired: ${lat}, ${lon} (±${Math.round(pos.coords.accuracy)}m)`);
        setTimeout(() => setReportLocGpsStatus(null), 4000);
      },
      (err) => {
        const msgs: Record<number, string> = {
          1: '⛔ Location permission denied.',
          2: '📡 GPS position unavailable.',
          3: '⏱ GPS timed out.',
        };
        setReportLocGpsStatus(msgs[err.code] ?? '❌ Could not get your location.');
        setTimeout(() => setReportLocGpsStatus(null), 5000);
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  // Debounced search: origin
  useEffect(() => {
    if (originQuery.trim().length < 2) {
      setOriginSuggestions([]);
      setOriginActiveIdx(-1);
      return;
    }
    const timer = setTimeout(async () => {
      setOriginSearching(true);
      try {
        const places = await ApiClient.searchLocations(originQuery);
        if (places.length > 0) {
          setOriginSuggestions(places);
        } else {
          const local = POPULAR_BENGALURU_CORRIDORS.filter(p =>
            p.name.toLowerCase().includes(originQuery.toLowerCase())
          );
          setOriginSuggestions(local);
        }
      } finally {
        setOriginSearching(false);
        setOriginActiveIdx(-1);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [originQuery]);

  // Debounced search: destination
  useEffect(() => {
    if (destQuery.trim().length < 2) {
      setDestSuggestions([]);
      setDestActiveIdx(-1);
      return;
    }
    const timer = setTimeout(async () => {
      setDestSearching(true);
      try {
        const places = await ApiClient.searchLocations(destQuery);
        if (places.length > 0) {
          setDestSuggestions(places);
        } else {
          const local = POPULAR_BENGALURU_CORRIDORS.filter(p =>
            p.name.toLowerCase().includes(destQuery.toLowerCase())
          );
          setDestSuggestions(local);
        }
      } finally {
        setDestSearching(false);
        setDestActiveIdx(-1);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [destQuery]);

  const selectOrigin = (sug: LocationPoint) => {
    setOriginPoint(sug);
    setOriginQuery(sug.name);
    setOriginSuggestions([]);
    setOriginActiveIdx(-1);
    setHighlightedCoordinates([sug.lat, sug.lon]);
    setPinMode('destination');
    setLiveOrigin(false); // manual pick — stop live tracking for origin
  };

  const selectDest = (sug: LocationPoint) => {
    setDestPoint(sug);
    setDestQuery(sug.name);
    setDestSuggestions([]);
    setDestActiveIdx(-1);
    setHighlightedCoordinates([sug.lat, sug.lon]);
    setLiveDest(false); // manual pick — stop live tracking for dest
  };

  const handleOriginKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!originSuggestions.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setOriginActiveIdx(i => Math.min(i + 1, originSuggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setOriginActiveIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && originActiveIdx >= 0) {
      e.preventDefault();
      selectOrigin(originSuggestions[originActiveIdx]);
    } else if (e.key === 'Escape') {
      setOriginSuggestions([]);
      setOriginActiveIdx(-1);
    }
  };

  const handleDestKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!destSuggestions.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setDestActiveIdx(i => Math.min(i + 1, destSuggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setDestActiveIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && destActiveIdx >= 0) {
      e.preventDefault();
      selectDest(destSuggestions[destActiveIdx]);
    } else if (e.key === 'Escape') {
      setDestSuggestions([]);
      setDestActiveIdx(-1);
    }
  };

  // HTML5 Device GPS Geolocation — sets live-tracking flag so route auto-updates
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
        const locName = `📍 My Location (${lat}, ${lon})`;

        if (target === 'origin') {
          setOriginPoint({ name: locName, lat, lon });
          setOriginQuery(locName);
          setLiveOrigin(true);  // ← enable live route tracking for origin
          lastLiveCalcRef.current = { lat, lon };
        } else {
          setDestPoint({ name: locName, lat, lon });
          setDestQuery(locName);
          setLiveDest(true);    // ← enable live route tracking for dest
          lastLiveCalcRef.current = { lat, lon };
        }

        setHighlightedCoordinates([lat, lon]);
        setGpsStatus(`GPS acquired: ${lat}, ${lon} (±${Math.round(position.coords.accuracy)}m) · Route will update as you move`);
        setTimeout(() => setGpsStatus(null), 5000);
      },
      (error) => {
        console.warn('GPS error:', error.code, error.message);
        const errMessages: Record<number, string> = {
          1: '⛔ Location permission denied. Please allow location access in your browser settings.',
          2: '📡 GPS position unavailable. Check your device location settings.',
          3: '⏱ GPS timed out. Move to an open area and try again.',
        };
        const msg = errMessages[error.code] ?? '❌ Could not get your location. Please enter it manually.';
        setGpsStatus(msg);
        setTimeout(() => setGpsStatus(null), 6000);
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
      setLiveOrigin(false); // map pin = manual, stop live tracking
    } else if (pinMode === 'destination') {
      const name = `🎯 Custom Target Pin (${roundedLat}, ${roundedLon})`;
      setDestPoint({ name, lat: roundedLat, lon: roundedLon });
      setDestQuery(name);
      setLiveDest(false); // map pin = manual, stop live tracking
    } else {
      setReportLat(roundedLat);
      setReportLon(roundedLon);
      setReportLocQuery(`📍 Map Pin (${roundedLat}, ${roundedLon})`);
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

  // Withdraw state
  const [withdrawingId, setWithdrawingId] = useState<string | null>(null);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);

  const handleWithdraw = async (incidentId: string) => {
    setWithdrawingId(incidentId);
    setWithdrawError(null);
    try {
      await ApiClient.withdrawReport(incidentId);
      await refreshData();
    } catch (err: any) {
      setWithdrawError(err.message ?? 'Failed to withdraw report');
      setTimeout(() => setWithdrawError(null), 5000);
    } finally {
      setWithdrawingId(null);
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

          {gpsStatus && (() => {
            const isError = gpsStatus.startsWith('⛔') || gpsStatus.startsWith('📡') || gpsStatus.startsWith('⏱') || gpsStatus.startsWith('❌');
            return (
              <div style={{
                padding: '8px 12px', borderRadius: '6px', fontSize: '12px', marginBottom: '12px',
                display: 'flex', alignItems: 'center', gap: '6px',
                backgroundColor: isError ? '#FEF2F2' : '#ECFDF5',
                border: `1px solid ${isError ? '#FCA5A5' : '#A7F3D0'}`,
                color: isError ? '#B91C1C' : '#065F46',
              }}>
                <Crosshair size={14} color={isError ? '#DC2626' : '#059669'} />
                <span>{gpsStatus}</span>
              </div>
            );
          })()}

          {/* Dynamic Origin & Destination Input Boxes */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '12px', alignItems: 'flex-start' }}>

            {/* Origin Place Search Box */}
            <div ref={originBoxRef} style={{ position: 'relative' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569' }}>
                  📍 Start Origin Location:
                </label>
                <button
                  type="button"
                  onClick={() => handleUseCurrentGpsLocation('origin')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '3px',
                    backgroundColor: '#ECFDF5', color: '#047857',
                    border: '1px solid #A7F3D0', borderRadius: '4px',
                    padding: '2px 6px', fontSize: '10px', fontWeight: 700, cursor: 'pointer'
                  }}
                  title="Acquire live GPS from browser device"
                >
                  <Crosshair size={11} /> Use Device GPS
                </button>
              </div>

              {/* Input with search icon */}
              <div style={{ position: 'relative' }}>
                <span style={{ position: 'absolute', left: '9px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', display: 'flex', alignItems: 'center' }}>
                  {originSearching
                    ? <span style={{ width: '13px', height: '13px', border: '2px solid #CBD5E1', borderTopColor: '#0B8B95', borderRadius: '50%', display: 'inline-block', animation: 'mm-spin 0.6s linear infinite' }} />
                    : <Search size={13} color="#94A3B8" />
                  }
                </span>
                <input
                  type="text"
                  value={originQuery}
                  onChange={(e) => setOriginQuery(e.target.value)}
                  onKeyDown={handleOriginKeyDown}
                  placeholder="Search any place in Bengaluru..."
                  autoComplete="off"
                  style={{
                    width: '100%', padding: '8px 10px 8px 30px',
                    borderRadius: '6px', border: '1px solid #CBD5E1',
                    fontSize: '12px', backgroundColor: '#F8FAFC', boxSizing: 'border-box'
                  }}
                />
              </div>

              {/* Suggestions Dropdown */}
              {originSuggestions.length > 0 && (
                <div style={{
                  position: 'absolute', top: '100%', left: 0, right: 0,
                  backgroundColor: '#FFFFFF', border: '1px solid #CBD5E1',
                  borderRadius: '8px', boxShadow: '0 6px 20px rgba(0,0,0,0.12)',
                  zIndex: 600, marginTop: '4px', maxHeight: '220px', overflowY: 'auto'
                }}>
                  {originSuggestions.map((sug, idx) => (
                    <div
                      key={idx}
                      onMouseDown={(e) => { e.preventDefault(); selectOrigin(sug); }}
                      onMouseEnter={() => setOriginActiveIdx(idx)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '8px',
                        padding: '9px 12px', fontSize: '12px', cursor: 'pointer',
                        borderBottom: idx < originSuggestions.length - 1 ? '1px solid #F1F5F9' : 'none',
                        backgroundColor: idx === originActiveIdx ? '#F0FDF4' : '#FFFFFF',
                        color: '#1E293B',
                      }}
                    >
                      <MapPin size={13} color="#059669" style={{ flexShrink: 0 }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sug.name}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Destination Place Search Box */}
            <div ref={destBoxRef} style={{ position: 'relative' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569' }}>
                  🎯 Destination Target:
                </label>
                <button
                  type="button"
                  onClick={() => handleUseCurrentGpsLocation('destination')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '3px',
                    backgroundColor: '#ECFDF5', color: '#047857',
                    border: '1px solid #A7F3D0', borderRadius: '4px',
                    padding: '2px 6px', fontSize: '10px', fontWeight: 700, cursor: 'pointer'
                  }}
                  title="Acquire live GPS from browser device"
                >
                  <Crosshair size={11} /> Use Device GPS
                </button>
              </div>

              {/* Input with search icon */}
              <div style={{ position: 'relative' }}>
                <span style={{ position: 'absolute', left: '9px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', display: 'flex', alignItems: 'center' }}>
                  {destSearching
                    ? <span style={{ width: '13px', height: '13px', border: '2px solid #CBD5E1', borderTopColor: '#DC2626', borderRadius: '50%', display: 'inline-block', animation: 'mm-spin 0.6s linear infinite' }} />
                    : <Search size={13} color="#94A3B8" />
                  }
                </span>
                <input
                  type="text"
                  value={destQuery}
                  onChange={(e) => setDestQuery(e.target.value)}
                  onKeyDown={handleDestKeyDown}
                  placeholder="Search destination landmark..."
                  autoComplete="off"
                  style={{
                    width: '100%', padding: '8px 10px 8px 30px',
                    borderRadius: '6px', border: '1px solid #CBD5E1',
                    fontSize: '12px', backgroundColor: '#F8FAFC', boxSizing: 'border-box'
                  }}
                />
              </div>

              {destSuggestions.length > 0 && (
                <div style={{
                  position: 'absolute', top: '100%', left: 0, right: 0,
                  backgroundColor: '#FFFFFF', border: '1px solid #CBD5E1',
                  borderRadius: '8px', boxShadow: '0 6px 20px rgba(0,0,0,0.12)',
                  zIndex: 600, marginTop: '4px', maxHeight: '220px', overflowY: 'auto'
                }}>
                  {destSuggestions.map((sug, idx) => (
                    <div
                      key={idx}
                      onMouseDown={(e) => { e.preventDefault(); selectDest(sug); }}
                      onMouseEnter={() => setDestActiveIdx(idx)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '8px',
                        padding: '9px 12px', fontSize: '12px', cursor: 'pointer',
                        borderBottom: idx < destSuggestions.length - 1 ? '1px solid #F1F5F9' : 'none',
                        backgroundColor: idx === destActiveIdx ? '#FFF5F5' : '#FFFFFF',
                        color: '#1E293B',
                      }}
                    >
                      <MapPin size={13} color="#DC2626" style={{ flexShrink: 0 }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sug.name}</span>
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

          {/* Live route / rerouting badge */}
          {(liveOrigin || liveDest || rerouting) && (() => {
            const isRerouting = rerouting;
            const isUpdating  = liveRouteUpdating && !rerouting;
            const bg    = isRerouting ? '#FEF3C7' : isUpdating ? '#EFF6FF' : '#F0FDF4';
            const bdr   = isRerouting ? '#FDE68A' : isUpdating ? '#BFDBFE' : '#A7F3D0';
            const color = isRerouting ? '#92400E' : isUpdating ? '#1D4ED8' : '#065F46';
            const dotBg = isRerouting ? '#F59E0B' : isUpdating ? '#3B82F6' : '#10B981';
            return (
              <div style={{
                marginTop: '10px', padding: '5px 10px', borderRadius: '6px',
                display: 'flex', alignItems: 'center', gap: '7px', fontSize: '11px',
                backgroundColor: bg, border: `1px solid ${bdr}`, color,
              }}>
                <span style={{
                  width: '8px', height: '8px', borderRadius: '50%', flexShrink: 0,
                  backgroundColor: dotBg,
                  animation: (isRerouting || isUpdating) ? 'mm-spin 0.8s linear infinite' : undefined,
                  border: (isRerouting || isUpdating) ? `2px solid ${bdr}` : 'none',
                  display: 'inline-block',
                }} />
                {isRerouting
                  ? '🔀 Off route — rerouting from your current position...'
                  : isUpdating
                    ? '🔄 Recalculating route from your current location...'
                    : `📍 Live route active — reroutes if you go off-route${liveOrigin && liveDest ? ' (both)' : liveOrigin ? ' (start)' : ' (dest)'}`
                }
                {!isRerouting && (
                  <button
                    onClick={() => { setLiveOrigin(false); setLiveDest(false); }}
                    style={{ marginLeft: 'auto', fontSize: '10px', color: '#64748B', background: 'none', border: 'none', cursor: 'pointer', padding: '0 2px' }}
                    title="Stop live route tracking"
                  >✕ Stop</button>
                )}
              </div>
            );
          })()}

          {/* Traffic condition banner */}
          {routesResult && (routesResult as any).traffic_label && (
            <div style={{
              marginTop: '12px', padding: '7px 12px', borderRadius: '6px',
              display: 'flex', alignItems: 'center', gap: '8px',
              backgroundColor: (routesResult as any).traffic_factor >= 1.5 ? '#FEF2F2' : (routesResult as any).traffic_factor >= 1.25 ? '#FFFBEB' : '#F0FDF4',
              border: `1px solid ${(routesResult as any).traffic_factor >= 1.5 ? '#FCA5A5' : (routesResult as any).traffic_factor >= 1.25 ? '#FDE68A' : '#A7F3D0'}`,
            }}>
              <span style={{ fontSize: '14px' }}>
                {(routesResult as any).traffic_factor >= 1.5 ? '🔴' : (routesResult as any).traffic_factor >= 1.25 ? '🟡' : '🟢'}
              </span>
              <span style={{ fontSize: '12px', fontWeight: 700, color: '#1E293B' }}>
                Live Traffic:
              </span>
              <span style={{ fontSize: '12px', color: '#475569' }}>
                {(routesResult as any).traffic_label}
              </span>
              <span style={{
                marginLeft: 'auto', fontSize: '11px', fontWeight: 800,
                color: (routesResult as any).traffic_factor >= 1.5 ? '#B91C1C' : (routesResult as any).traffic_factor >= 1.25 ? '#92400E' : '#065F46',
                backgroundColor: (routesResult as any).traffic_factor >= 1.5 ? '#FEE2E2' : (routesResult as any).traffic_factor >= 1.25 ? '#FEF3C7' : '#DCFCE7',
                padding: '1px 7px', borderRadius: '4px'
              }}>
                ×{(routesResult as any).traffic_factor?.toFixed(2)}
              </span>
            </div>
          )}

          {/* Route Comparison Results Cards */}
          {routesResult && routesResult.routes && routesResult.routes.length > 0 && (
            <div style={{ marginTop: '12px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              {routesResult.routes.map((rt) => {
                const isRiskAware = rt.type === 'risk_aware';
                const isAlternative = rt.type === 'alternative';
                const trafficDelay = (rt as any).traffic_delay_s ?? 0;
                const hasIncidents = rt.hazard_penalty_s > 0 || rt.blocked_edges_crossed > 0;

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
                        fontSize: '11px', fontWeight: 800, textTransform: 'uppercase',
                        color: isRiskAware ? '#0F766E' : isAlternative ? '#6D28D9' : '#475569',
                        backgroundColor: isRiskAware ? '#CCFBF1' : isAlternative ? '#EDE9FE' : '#E2E8F0',
                        padding: '2px 8px', borderRadius: '4px'
                      }}>
                        {rt.label}
                      </span>
                      {isRiskAware && (
                        <span style={{ fontSize: '11px', color: '#059669', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '2px' }}>
                          <ShieldCheck size={13} /> Recommended
                        </span>
                      )}
                    </div>

                    {/* Total ETA */}
                    <div style={{ fontSize: '22px', fontWeight: 800, color: '#1E293B', marginTop: '4px' }}>
                      {Math.round(rt.estimated_duration_s / 60)} min
                      <span style={{ fontSize: '12px', fontWeight: 500, color: '#64748B', marginLeft: '6px' }}>
                        ({(rt.distance_m / 1000).toFixed(2)} km)
                      </span>
                    </div>

                    {/* Time breakdown */}
                    <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                      {/* Base travel */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#475569' }}>
                        <span>🛣 Base travel time</span>
                        <span style={{ fontWeight: 700 }}>{Math.round(rt.base_duration_s / 60)} min</span>
                      </div>
                      {/* Live traffic delay */}
                      {trafficDelay > 0 && (
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#92400E' }}>
                          <span>🚦 Live traffic delay</span>
                          <span style={{ fontWeight: 700 }}>+{Math.round(trafficDelay / 60)} min</span>
                        </div>
                      )}
                      {/* Incident hazard penalty */}
                      {rt.hazard_penalty_s > 0 && (
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#B91C1C' }}>
                          <span>⚠️ Incident penalty</span>
                          <span style={{ fontWeight: 700 }}>+{Math.round(rt.hazard_penalty_s / 60)} min</span>
                        </div>
                      )}
                      {/* Congestion from edge BPR */}
                      {rt.congestion_delay_s > 5 && (
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#92400E' }}>
                          <span>🔄 Ripple congestion</span>
                          <span style={{ fontWeight: 700 }}>+{Math.round(rt.congestion_delay_s)}s</span>
                        </div>
                      )}
                    </div>

                    {/* Incident / block badges */}
                    {(hasIncidents || rt.blocked_edges_crossed > 0) && (
                      <div style={{ marginTop: '7px', display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                        {rt.blocked_edges_crossed > 0 && (
                          <span style={{ fontSize: '10px', fontWeight: 700, color: '#B91C1C', backgroundColor: '#FEE2E2', padding: '1px 6px', borderRadius: '4px' }}>
                            🚧 {rt.blocked_edges_crossed} blocked road{rt.blocked_edges_crossed > 1 ? 's' : ''}
                          </span>
                        )}
                        {rt.hazard_penalty_s > 0 && (
                          <span style={{ fontSize: '10px', fontWeight: 700, color: '#92400E', backgroundColor: '#FEF3C7', padding: '1px 6px', borderRadius: '4px' }}>
                            🌊 Active hazards on route
                          </span>
                        )}
                      </div>
                    )}

                    <div style={{ marginTop: '8px', fontSize: '10px', color: '#64748B', borderTop: '1px solid rgba(0,0,0,0.06)', paddingTop: '6px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>⚠️ {rt.uncertainty}</span>
                      {(rt as any).geometry_source === 'osrm' && (
                        <span style={{ flexShrink: 0, fontSize: '9px', fontWeight: 700, color: '#0B8B95', backgroundColor: '#F0FDFA', padding: '1px 5px', borderRadius: '3px', whiteSpace: 'nowrap' }}>
                          🛣 Real roads
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* ── Voice & Turn-by-Turn Directions Panel ── */}
          {routesResult && routesResult.routes && routesResult.routes.length > 0 && (() => {
            const dirSteps = buildDirectionSteps(routesResult);
            const riskRoute = routesResult.routes.find((r: any) => r.type === 'risk_aware') ?? routesResult.routes[0];
            return (
              <div style={{ marginTop: '16px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0', overflow: 'hidden' }}>
                {/* Panel header */}
                <div style={{ padding: '10px 14px', backgroundColor: '#0B8B95', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <MapPinned size={16} color="#FFF" />
                    <span style={{ fontSize: '13px', fontWeight: 700, color: '#FFF' }}>
                      Turn-by-Turn Directions
                    </span>
                    <span style={{ fontSize: '11px', color: '#CCFBF1', backgroundColor: 'rgba(0,0,0,0.2)', padding: '1px 7px', borderRadius: '10px' }}>
                      {Math.round(riskRoute.estimated_duration_s / 60)} min · {(riskRoute.distance_m / 1000).toFixed(1)} km
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    {/* Voice toggle */}
                    <button
                      onClick={() => {
                        if (voiceEnabled) { stopSpeech(); setVoiceEnabled(false); }
                        else { setVoiceEnabled(true); announceRoute(); }
                      }}
                      title={voiceEnabled ? 'Turn off voice' : 'Turn on voice guidance'}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '5px',
                        padding: '4px 10px', borderRadius: '6px', border: 'none',
                        backgroundColor: voiceEnabled ? '#FFF' : 'rgba(255,255,255,0.2)',
                        color: voiceEnabled ? '#0B8B95' : '#FFF',
                        fontWeight: 700, fontSize: '11px', cursor: 'pointer',
                      }}
                    >
                      {voiceEnabled ? <Volume2 size={13} /> : <VolumeX size={13} />}
                      {isSpeaking ? 'Speaking…' : voiceEnabled ? 'Voice On' : 'Voice Off'}
                    </button>
                    {/* Replay */}
                    {voiceEnabled && (
                      <button onClick={announceRoute}
                        style={{ padding: '4px 10px', borderRadius: '6px', border: 'none', backgroundColor: 'rgba(255,255,255,0.15)', color: '#FFF', fontSize: '11px', fontWeight: 700, cursor: 'pointer' }}>
                        ▶ Replay
                      </button>
                    )}
                  </div>
                </div>

                {/* Step list */}
                {dirSteps.length > 0 ? (
                  <div style={{ maxHeight: '220px', overflowY: 'auto' }}>
                    {dirSteps.map((s, idx) => {
                      const isActive = idx === activeDirectionStep;
                      const isLast = idx === dirSteps.length - 1;
                      return (
                        <div
                          key={idx}
                          onClick={() => {
                            setActiveDirectionStep(idx);
                            if (voiceEnabled) speakText(s.instruction);
                          }}
                          style={{
                            display: 'flex', alignItems: 'flex-start', gap: '10px',
                            padding: '10px 14px', cursor: 'pointer',
                            backgroundColor: isActive ? '#F0FDFA' : 'transparent',
                            borderBottom: isLast ? 'none' : '1px solid #F1F5F9',
                            borderLeft: `3px solid ${isActive ? '#0B8B95' : 'transparent'}`,
                          }}
                        >
                          {/* Step icon / number */}
                          <div style={{
                            width: '26px', height: '26px', borderRadius: '50%', flexShrink: 0,
                            backgroundColor: isLast ? '#059669' : isActive ? '#0B8B95' : '#F1F5F9',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: s.icon && s.icon.length > 1 ? '13px' : '10px',
                            fontWeight: 700,
                            color: isActive || isLast ? '#FFF' : '#64748B',
                          }}>
                            {isLast ? '✓' : (s.icon || s.step)}
                          </div>

                          {/* Instruction */}
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: '12px', fontWeight: isActive ? 700 : 500, color: isActive ? '#0F766E' : '#1E293B', lineHeight: 1.4 }}>
                              {s.instruction}
                            </div>
                            {s.dist && (
                              <div style={{ fontSize: '10px', color: '#94A3B8', marginTop: '1px' }}>{s.dist}</div>
                            )}
                          </div>

                          {!isLast && <ChevronRight size={13} color="#CBD5E1" style={{ flexShrink: 0, marginTop: '4px' }} />}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  /* Fallback when no step data — show origin → dest summary */
                  <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {routesResult.routes.map((rt: any) => (
                      <div key={rt.type} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#475569' }}>
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: rt.type === 'risk_aware' ? '#0B8B95' : rt.type === 'fastest' ? '#3B82F6' : '#7C3AED', flexShrink: 0 }} />
                        <strong>{rt.label}</strong>: {Math.round(rt.estimated_duration_s / 60)} min, {(rt.distance_m / 1000).toFixed(1)} km
                        {rt.blocked_edges_crossed > 0 && (
                          <span style={{ fontSize: '10px', color: '#DC2626', fontWeight: 700 }}>⚠️ {rt.blocked_edges_crossed} blocked</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Blocked road warning */}
                {riskRoute.blocked_edges_crossed === 0 && (
                  <div style={{ padding: '8px 14px', backgroundColor: '#ECFDF5', borderTop: '1px solid #A7F3D0', fontSize: '11px', color: '#065F46', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <CheckCircle2 size={12} color="#059669" /> All clear — no blocked roads on recommended route
                  </div>
                )}
                {riskRoute.blocked_edges_crossed > 0 && (
                  <div style={{ padding: '8px 14px', backgroundColor: '#FEF2F2', borderTop: '1px solid #FCA5A5', fontSize: '11px', color: '#B91C1C', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <AlertTriangle size={12} color="#DC2626" /> {riskRoute.blocked_edges_crossed} blocked segment(s) detected — risk-aware route avoids them
                  </div>
                )}
              </div>
            );
          })()}
        </div>

        {/* Map View with Start / End / Report Pins */}
        <InteractiveMap
          originPin={[originPoint.lat, originPoint.lon]}
          destPin={[destPoint.lat, destPoint.lon]}
          reportPin={[reportLat, reportLon]}
          onMapClick={handleMapClick}
          height="520px"
          pinMode={pinMode}
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

          {/* Withdraw error banner */}
          {withdrawError && (
            <div style={{ padding: '7px 10px', borderRadius: '6px', marginBottom: '8px', fontSize: '11px', color: '#B91C1C', backgroundColor: '#FEF2F2', border: '1px solid #FCA5A5' }}>
              ⛔ {withdrawError}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {incidents.slice(0, 8).map((inc) => {
              const isOwn = inc.is_mine === true;
              const canWithdraw = isOwn && (inc.status === 'reported' || inc.status === 'under_review');
              const isWithdrawing = withdrawingId === inc.id;

              return (
                <div
                  key={inc.id}
                  onClick={() => setHighlightedCoordinates([inc.lat, inc.lon])}
                  style={{
                    padding: '10px 14px',
                    borderRadius: '8px',
                    backgroundColor: isOwn ? '#FAFFF5' : '#F8FAFC',
                    border: `1px solid ${isOwn ? '#BBF7D0' : '#E2E8F0'}`,
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span style={{ fontWeight: 700, fontSize: '13px', color: '#1E293B' }}>
                          {inc.road_name || 'Waterlogging Hazard'}
                        </span>
                        <span style={{ fontSize: '11px', textTransform: 'uppercase', color: '#B91C1C', fontWeight: 700 }}>
                          [{inc.severity}]
                        </span>
                        {isOwn && (
                          <span style={{ fontSize: '10px', fontWeight: 700, color: '#059669', backgroundColor: '#DCFCE7', padding: '1px 5px', borderRadius: '4px' }}>
                            My Report
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '12px', color: '#64748B', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {inc.evidence_list[0]?.text_notes || 'Reported standing water disruption.'}
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0, marginLeft: '10px' }}>
                      <StatusBadge status={inc.status} size="sm" />

                      {/* Withdraw button — only on own reports that are still actionable */}
                      {canWithdraw && (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleWithdraw(inc.id); }}
                          disabled={isWithdrawing}
                          title="Withdraw this report"
                          style={{
                            display: 'flex', alignItems: 'center', gap: '3px',
                            padding: '3px 8px', borderRadius: '5px', border: '1px solid #FCA5A5',
                            backgroundColor: isWithdrawing ? '#FEF2F2' : '#FFF5F5',
                            color: '#B91C1C', fontSize: '10px', fontWeight: 700,
                            cursor: isWithdrawing ? 'not-allowed' : 'pointer',
                            opacity: isWithdrawing ? 0.7 : 1,
                          }}
                        >
                          {isWithdrawing ? '…' : '✕ Withdraw'}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
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
          Search for a location, use your device GPS, or switch to <strong>⚠️ Set Hazard</strong> map mode and click directly on the map.
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

          {/* ── Hazard Location Search ─────────────────────────────────────── */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
              <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569' }}>
                📍 Hazard Location
              </label>
              <button
                type="button"
                onClick={handleReportLocGps}
                style={{
                  display: 'flex', alignItems: 'center', gap: '3px',
                  backgroundColor: '#ECFDF5', color: '#047857',
                  border: '1px solid #A7F3D0', borderRadius: '4px',
                  padding: '2px 6px', fontSize: '10px', fontWeight: 700, cursor: 'pointer'
                }}
                title="Use device GPS"
              >
                <Crosshair size={11} /> Use My Location
              </button>
            </div>

            {/* GPS status for report */}
            {reportLocGpsStatus && (() => {
              const isErr = reportLocGpsStatus.startsWith('⛔') || reportLocGpsStatus.startsWith('📡') || reportLocGpsStatus.startsWith('⏱') || reportLocGpsStatus.startsWith('❌');
              return (
                <div style={{
                  padding: '6px 10px', borderRadius: '6px', fontSize: '11px', marginBottom: '6px',
                  display: 'flex', alignItems: 'center', gap: '6px',
                  backgroundColor: isErr ? '#FEF2F2' : '#ECFDF5',
                  border: `1px solid ${isErr ? '#FCA5A5' : '#A7F3D0'}`,
                  color: isErr ? '#B91C1C' : '#065F46',
                }}>
                  <Crosshair size={12} color={isErr ? '#DC2626' : '#059669'} />
                  <span>{reportLocGpsStatus}</span>
                </div>
              );
            })()}

            {/* Search input with spinner/icon */}
            <div ref={reportLocBoxRef} style={{ position: 'relative' }}>
              <div style={{ position: 'relative' }}>
                <span style={{ position: 'absolute', left: '9px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', display: 'flex', alignItems: 'center' }}>
                  {reportLocSearching
                    ? <span style={{ width: '12px', height: '12px', border: '2px solid #CBD5E1', borderTopColor: '#C78420', borderRadius: '50%', display: 'inline-block', animation: 'mm-spin 0.6s linear infinite' }} />
                    : <Search size={12} color="#94A3B8" />
                  }
                </span>
                <input
                  type="text"
                  value={reportLocQuery}
                  onChange={(e) => setReportLocQuery(e.target.value)}
                  onKeyDown={handleReportLocKeyDown}
                  placeholder="Search place or click map in ⚠️ mode..."
                  autoComplete="off"
                  style={{
                    width: '100%', padding: '7px 10px 7px 28px',
                    borderRadius: '6px', border: '1px solid #CBD5E1',
                    fontSize: '12px', backgroundColor: '#F8FAFC', boxSizing: 'border-box'
                  }}
                />
              </div>

              {/* Suggestions dropdown */}
              {reportLocSuggestions.length > 0 && (
                <div style={{
                  position: 'absolute', top: '100%', left: 0, right: 0,
                  backgroundColor: '#FFFFFF', border: '1px solid #CBD5E1',
                  borderRadius: '8px', boxShadow: '0 6px 20px rgba(0,0,0,0.12)',
                  zIndex: 600, marginTop: '4px', maxHeight: '200px', overflowY: 'auto'
                }}>
                  {reportLocSuggestions.map((sug, idx) => (
                    <div
                      key={idx}
                      onMouseDown={(e) => { e.preventDefault(); selectReportLoc(sug); }}
                      onMouseEnter={() => setReportLocActiveIdx(idx)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '8px',
                        padding: '8px 10px', fontSize: '12px', cursor: 'pointer',
                        borderBottom: idx < reportLocSuggestions.length - 1 ? '1px solid #F1F5F9' : 'none',
                        backgroundColor: idx === reportLocActiveIdx ? '#FFFBEB' : '#FFFFFF',
                        color: '#1E293B',
                      }}
                    >
                      <MapPin size={12} color="#C78420" style={{ flexShrink: 0 }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sug.name}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Resolved coordinate pill */}
            <div style={{
              marginTop: '5px', display: 'flex', alignItems: 'center', gap: '5px',
              fontSize: '10px', color: '#64748B'
            }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: '4px',
                backgroundColor: '#F1F5F9', border: '1px solid #E2E8F0',
                borderRadius: '4px', padding: '2px 7px', fontFamily: 'monospace'
              }}>
                📌 {reportLat.toFixed(4)}, {reportLon.toFixed(4)}
              </span>
              <span style={{ color: '#94A3B8' }}>· or click map in ⚠️ Set Hazard mode</span>
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
