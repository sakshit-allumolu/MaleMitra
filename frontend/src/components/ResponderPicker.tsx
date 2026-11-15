import React, { useEffect, useState } from 'react';
import { ApiClient } from '../services/api';
import { useIncidents } from '../context/IncidentContext';
import { ResponderAvailability } from '../types';

// Admin-only: every responder with their live free/busy state. Refreshes whenever incident data does.
export function useResponders(): ResponderAvailability[] {
  const { incidents } = useIncidents();
  const [responders, setResponders] = useState<ResponderAvailability[]>([]);
  useEffect(() => {
    let cancelled = false;
    ApiClient.getResponders().then(r => { if (!cancelled) setResponders(r); });
    return () => { cancelled = true; };
  }, [incidents]);
  return responders;
}

interface Props {
  teamId: string;
  value: string;                       // '' = leave in the team queue
  onChange: (responderId: string) => void;
  responders: ResponderAvailability[];
  style?: React.CSSProperties;
}

export const ResponderPicker: React.FC<Props> = ({ teamId, value, onChange, responders, style }) => {
  const onTeam = responders.filter(r => r.team_id === teamId);
  const noneFree = onTeam.length > 0 && onTeam.every(r => !r.is_free);
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      title={noneFree ? 'Nobody on this team is free: the incident will wait in the team queue.' : undefined}
      style={{ padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px', fontWeight: 600, ...style }}
    >
      <option value="">Team queue (anyone free can take it)</option>
      {onTeam.map(r => (
        <option key={r.id} value={r.id}>
          {r.name} — {r.is_free ? 'free' : `busy (${r.active_incident_ids.length})`}
        </option>
      ))}
    </select>
  );
};
