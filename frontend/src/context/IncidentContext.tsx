import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { 
  Incident, RouteCompareResponse, RippleImpactResponse, 
  AgentEventItem, AuditEventItem, RoadNetworkData, ResponseTeam 
} from '../types';
import { ApiClient } from '../services/api';
import { useAuth } from './AuthContext';

interface IncidentContextType {
  incidents: Incident[];
  selectedIncident: Incident | null;
  setSelectedIncident: (inc: Incident | null) => void;
  roadNetwork: RoadNetworkData | null;
  graphVersion: number;
  routesResult: RouteCompareResponse | null;
  setRoutesResult: (res: RouteCompareResponse | null) => void;
  rippleResult: RippleImpactResponse | null;
  agentEvents: AgentEventItem[];
  auditEvents: AuditEventItem[];
  teams: ResponseTeam[];
  isLoading: boolean;
  activeView: 'citizen' | 'admin' | 'responder' | 'evaluation' | 'ripple';
  setActiveView: (view: 'citizen' | 'admin' | 'responder' | 'evaluation' | 'ripple') => void;
  refreshData: () => Promise<void>;
  calculateRoutes: (origin: { lat: number; lon: number }, destination: { lat: number; lon: number }) => Promise<void>;
  triggerSimulation: (blockedEdges?: string[]) => Promise<void>;
  highlightedCoordinates: [number, number] | null;
  setHighlightedCoordinates: (coord: [number, number] | null) => void;
  walkthroughOpen: boolean;
  setWalkthroughOpen: (open: boolean) => void;
}

const IncidentContext = createContext<IncidentContextType | undefined>(undefined);

export const IncidentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { activeRole, currentUser } = useAuth();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [roadNetwork, setRoadNetwork] = useState<RoadNetworkData | null>(null);
  const [graphVersion, setGraphVersion] = useState<number>(1);
  const [routesResult, setRoutesResult] = useState<RouteCompareResponse | null>(null);
  const [rippleResult, setRippleResult] = useState<RippleImpactResponse | null>(null);
  const [agentEvents, setAgentEvents] = useState<AgentEventItem[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEventItem[]>([]);
  const [teams, setTeams] = useState<ResponseTeam[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [activeView, setActiveView] = useState<'citizen' | 'admin' | 'responder' | 'evaluation' | 'ripple'>('citizen');
  const [highlightedCoordinates, setHighlightedCoordinates] = useState<[number, number] | null>(null);
  const [walkthroughOpen, setWalkthroughOpen] = useState<boolean>(false);

  // Sync active view with role initially
  useEffect(() => {
    if (activeRole === 'citizen') setActiveView('citizen');
    else if (activeRole === 'admin') setActiveView('admin');
    else if (activeRole === 'responder') setActiveView('responder');
  }, [activeRole]);

  const refreshData = useCallback(async () => {
    try {
      const [incList, net, agEvents, audEvents, teamList] = await Promise.all([
        ApiClient.getIncidents(),
        ApiClient.getRoadNetwork(),
        ApiClient.getAgentEvents(),
        ApiClient.getAuditEvents(),
        ApiClient.getTeams()
      ]);
      setIncidents(incList);
      setRoadNetwork(net);
      setGraphVersion(net.graph_version);
      setAgentEvents(agEvents);
      setAuditEvents(audEvents);
      setTeams(teamList);

      // If an incident was selected, refresh its details
      if (selectedIncident) {
        const updated = incList.find(i => i.id === selectedIncident.id);
        if (updated) setSelectedIncident(updated);
      }
    } catch (err) {
      console.error('Error refreshing incident data:', err);
    }
  }, [selectedIncident]);

  const calculateRoutes = async (origin: { lat: number; lon: number }, destination: { lat: number; lon: number }) => {
    setIsLoading(true);
    try {
      const res = await ApiClient.compareRoutes(origin, destination);
      setRoutesResult(res);
      setGraphVersion(res.graph_version);
    } catch (err) {
      console.error('Route calculation failed:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const triggerSimulation = async (blockedEdges?: string[]) => {
    setIsLoading(true);
    try {
      const res = await ApiClient.runSimulation(blockedEdges);
      setRippleResult(res);
      setGraphVersion(res.graph_version);
      await refreshData();
    } catch (err) {
      console.error('Ripple simulation failed:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    refreshData();
    triggerSimulation();
  }, [currentUser]);

  // Server-Sent Events / 3-second Polling fallback
  useEffect(() => {
    const eventSource = new EventSource('/api/v1/events/stream');
    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.version_changed || payload.graph_version !== graphVersion) {
          setGraphVersion(payload.graph_version);
          refreshData();
        }
      } catch (e) {
        console.error('SSE error:', e);
      }
    };
    eventSource.onerror = () => {
      eventSource.close();
    };

    // Polling fallback
    const interval = setInterval(() => {
      refreshData();
    }, 4000);

    return () => {
      eventSource.close();
      clearInterval(interval);
    };
  }, [graphVersion, refreshData]);

  return (
    <IncidentContext.Provider value={{
      incidents,
      selectedIncident,
      setSelectedIncident,
      roadNetwork,
      graphVersion,
      routesResult,
      setRoutesResult,
      rippleResult,
      agentEvents,
      auditEvents,
      teams,
      isLoading,
      activeView,
      setActiveView,
      refreshData,
      calculateRoutes,
      triggerSimulation,
      highlightedCoordinates,
      setHighlightedCoordinates,
      walkthroughOpen,
      setWalkthroughOpen
    }}>
      {children}
    </IncidentContext.Provider>
  );
};

export const useIncidents = () => {
  const context = useContext(IncidentContext);
  if (!context) throw new Error('useIncidents must be used within an IncidentProvider');
  return context;
};
