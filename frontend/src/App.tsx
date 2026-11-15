import React from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { IncidentProvider } from './context/IncidentContext';
import { Navbar } from './components/Navbar';
import { CitizenWorkspace } from './views/CitizenWorkspace';
import { AdminWorkspace } from './views/AdminWorkspace';
import { ResponderWorkspace } from './views/ResponderWorkspace';
import { RippleVisualizer } from './components/RippleVisualizer';
import { EvaluationView } from './views/EvaluationView';
import { DemoWalkthroughModal } from './components/DemoWalkthroughModal';
import { LoginPage } from './components/LoginPage';
import { OnboardingTour } from './components/OnboardingTour';
import { useIncidents } from './context/IncidentContext';

const MainLayout: React.FC = () => {
  const { activeView } = useIncidents();

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#F4F6F9' }}>
      <Navbar />

      <main style={{ maxWidth: '1440px', width: '100%', margin: '0 auto', padding: '24px', flex: 1 }}>
        {activeView === 'citizen' && <CitizenWorkspace />}
        {activeView === 'admin' && <AdminWorkspace />}
        {activeView === 'responder' && <ResponderWorkspace />}
        {activeView === 'ripple' && <RippleVisualizer />}
        {activeView === 'evaluation' && <EvaluationView />}
      </main>

      <footer style={{
        backgroundColor: '#FFFFFF',
        borderTop: '1px solid #E2E8F0',
        padding: '16px 24px',
        textAlign: 'center',
        fontSize: '12px',
        color: '#64748B'
      }}>
        <div style={{ maxWidth: '1440px', margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
          <div>
            <strong>MaleMitra (ಮಳೆ ಮಿತ್ರ) v1.0</strong> • A Connected Monsoon Mobility and Civic Response Platform
          </div>
          <div>
            Smarter Streets, Better Living
          </div>
        </div>
      </footer>

      <DemoWalkthroughModal />
      <OnboardingTour />
    </div>
  );
};

const AppGate: React.FC = () => {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <IncidentProvider>
      <MainLayout />
    </IncidentProvider>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppGate />
    </AuthProvider>
  );
};

export default App;
