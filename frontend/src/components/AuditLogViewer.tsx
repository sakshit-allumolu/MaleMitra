import React, { useState } from 'react';
import { useIncidents } from '../context/IncidentContext';
import { AuditEventItem } from '../types';
import { ShieldCheck, Clock, User, FileText, ChevronRight } from 'lucide-react';

export const AuditLogViewer: React.FC = () => {
  const { auditEvents } = useIncidents();
  const [selectedAudit, setSelectedAudit] = useState<AuditEventItem | null>(null);

  const getActionColor = (action: string) => {
    if (action.includes('BLOCK')) return { text: '#B91C1C', bg: '#FEE2E2' };
    if (action.includes('REOPEN') || action.includes('CLEAR')) return { text: '#059669', bg: '#ECFDF5' };
    if (action.includes('ASSIGN')) return { text: '#6D28D9', bg: '#EDE9FE' };
    if (action.includes('VERIFY')) return { text: '#D97706', bg: '#FEF3C7' };
    return { text: '#0369A1', bg: '#E0F2FE' };
  };

  return (
    <div style={{
      backgroundColor: '#FFFFFF',
      borderRadius: '10px',
      border: '1px solid #E2E8F0',
      padding: '16px',
      boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
      height: '100%',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', borderBottom: '1px solid #E2E8F0', paddingBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldCheck size={18} color="#0B8B95" />
          <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: '#1E293B' }}>
            System Audit Trail & State Mutation Log
          </h3>
        </div>
        <span style={{ fontSize: '11px', color: '#64748B', backgroundColor: '#F1F5F9', padding: '2px 8px', borderRadius: '4px' }}>
          {auditEvents.length} audited actions
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px', paddingRight: '4px', maxHeight: '480px' }}>
        {auditEvents.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: '#94A3B8', fontSize: '13px' }}>
            No audit events recorded yet. Perform administrative actions or submit reports to view immutable state logs.
          </div>
        ) : (
          auditEvents.map((audit) => {
            const color = getActionColor(audit.action);
            const isSelected = selectedAudit?.id === audit.id;

            return (
              <div
                key={audit.id}
                onClick={() => setSelectedAudit(isSelected ? null : audit)}
                style={{
                  padding: '10px 12px',
                  borderRadius: '8px',
                  border: `1px solid ${isSelected ? '#0B8B95' : '#E2E8F0'}`,
                  backgroundColor: isSelected ? '#F0FDFA' : '#FAFAFA',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    color: color.text,
                    backgroundColor: color.bg,
                    padding: '2px 6px',
                    borderRadius: '4px'
                  }}>
                    {audit.action}
                  </span>
                  <span style={{ fontSize: '11px', color: '#94A3B8', display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <Clock size={11} />
                    {new Date(audit.timestamp).toLocaleTimeString()}
                  </span>
                </div>

                <div style={{ fontSize: '12px', color: '#334155', marginBottom: '2px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <User size={12} color="#64748B" />
                  <span>Actor: <strong>{audit.actor_name}</strong> (<code>{audit.actor_id}</code>)</span>
                </div>

                <div style={{ fontSize: '11px', color: '#64748B' }}>
                  Entity: <strong>{audit.entity_type}</strong> • ID: <code>{audit.entity_id}</code>
                </div>

                {isSelected && (
                  <div style={{
                    marginTop: '8px',
                    padding: '8px',
                    borderRadius: '6px',
                    backgroundColor: '#1E293B',
                    color: '#E2E8F0',
                    fontSize: '11px',
                    fontFamily: 'monospace',
                    overflowX: 'auto'
                  }}>
                    <div style={{ color: '#F87171', fontWeight: 700, marginBottom: '2px' }}>// Before State</div>
                    <pre style={{ margin: '0 0 6px 0' }}>{JSON.stringify(audit.before_state, null, 2) || 'null'}</pre>
                    <div style={{ color: '#34D399', fontWeight: 700, marginBottom: '2px' }}>// After State</div>
                    <pre style={{ margin: 0 }}>{JSON.stringify(audit.after_state, null, 2) || 'null'}</pre>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
