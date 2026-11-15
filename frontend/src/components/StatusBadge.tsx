import React from 'react';
import { IncidentStatus } from '../types';

interface StatusBadgeProps {
  status: IncidentStatus | string;
  size?: 'sm' | 'md' | 'lg';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const getStatusConfig = () => {
    switch (status) {
      case 'reported':
        return {
          label: 'Reported (Pending Review)',
          bg: '#FEF3C7',
          text: '#92400E',
          border: '#FCD34D'
        };
      case 'under_review':
        return {
          label: 'Under Triage Review',
          bg: '#E0F2FE',
          text: '#0369A1',
          border: '#BAE6FD'
        };
      case 'assigned':
        return {
          label: 'Field Unit Assigned',
          bg: '#EDE9FE',
          text: '#6D28D9',
          border: '#DDD6FE'
        };
      case 'field_verified':
        return {
          label: 'Field Verified (Evidence Ready)',
          bg: '#FEF08A',
          text: '#854D0E',
          border: '#FDE047'
        };
      case 'blocked':
        return {
          label: 'Road Restricted / Blocked',
          bg: '#FEE2E2',
          text: '#B91C1C',
          border: '#FCA5A5'
        };
      case 'clearance_proposed':
        return {
          label: 'Clearance Proposed',
          bg: '#D1FAE5',
          text: '#065F46',
          border: '#A7F3D0'
        };
      case 'cleared':
        return {
          label: 'Cleared & Reopened',
          bg: '#ECFDF5',
          text: '#047857',
          border: '#6EE7B7'
        };
      case 'rejected':
        return {
          label: 'Rejected / Duplicate',
          bg: '#F1F5F9',
          text: '#475569',
          border: '#CBD5E1'
        };
      default:
        return {
          label: status,
          bg: '#F3F4F6',
          text: '#374151',
          border: '#D1D5DB'
        };
    }
  };

  const config = getStatusConfig();
  const sizeStyles = {
    sm: { padding: '2px 8px', fontSize: '11px' },
    md: { padding: '4px 10px', fontSize: '12px' },
    lg: { padding: '6px 14px', fontSize: '14px' }
  }[size];

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        fontWeight: 600,
        borderRadius: '9999px',
        backgroundColor: config.bg,
        color: config.text,
        border: `1px solid ${config.border}`,
        ...sizeStyles
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: config.text
        }}
      />
      {config.label}
    </span>
  );
};
