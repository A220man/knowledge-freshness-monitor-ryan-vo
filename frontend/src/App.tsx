import React, { useState } from 'react';
import { AuthProvider } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { DashboardMetrics } from './components/DashboardMetrics';
import { DocumentManager } from './components/DocumentManager';
import { CitationGraphView } from './components/CitationGraphView';
import { RevalidationQueue } from './components/RevalidationQueue';
import { EvaluationView } from './components/EvaluationView';

export const AppContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('overview');

  return (
    <div className="app-shell">
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />
      <main className="main-content">
        {activeTab === 'overview' && <DashboardMetrics />}
        {activeTab === 'documents' && <DocumentManager />}
        {activeTab === 'graph' && <CitationGraphView />}
        {activeTab === 'queue' && <RevalidationQueue />}
        {activeTab === 'evaluation' && <EvaluationView />}
      </main>
      <footer className="footer">
        <div className="footer-container">
          <span>Knowledge Freshness Monitor &copy; 2026 Ryan Vo</span>
          <span>Contact: <a href="mailto:ryandtvo@gmail.com">ryandtvo@gmail.com</a></span>
          <span>Provider-Agnostic AI &amp; Machine Learning Operations</span>
        </div>
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;
