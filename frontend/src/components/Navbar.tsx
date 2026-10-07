import React from 'react';
import { useAuth } from '../context/AuthContext';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab }) => {
  const { user, loginAsDemo, logout } = useAuth();

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'documents', label: 'Documents & Drift' },
    { id: 'graph', label: 'Citation Graph' },
    { id: 'queue', label: 'Revalidation Queue' },
    { id: 'evaluation', label: 'AI/ML Evaluation' },
  ];

  return (
    <header className="navbar">
      <div className="navbar-container">
        <div className="navbar-brand">
          <span className="brand-logo">⚡</span>
          <div>
            <div className="brand-title">Knowledge Freshness Monitor</div>
            <div className="brand-subtitle">Ryan Vo | RAG Citation Drift & Impact Engine</div>
          </div>
        </div>

        <nav className="navbar-nav">
          {tabs.map((t) => (
            <button
              key={t.id}
              className={`nav-tab ${activeTab === t.id ? 'active' : ''}`}
              onClick={() => setActiveTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="navbar-auth">
          {user ? (
            <div className="user-badge">
              <span className={`role-pill role-${user.role}`}>{user.role.toUpperCase()}</span>
              <span className="user-name">{user.username}</span>
              <div className="role-switcher">
                <select
                  value={user.role}
                  onChange={(e) => loginAsDemo(e.target.value as any)}
                  aria-label="Switch User Role"
                  className="role-select"
                >
                  <option value="viewer">Switch: Viewer</option>
                  <option value="analyst">Switch: Analyst</option>
                  <option value="admin">Switch: Admin</option>
                </select>
              </div>
              <button onClick={() => logout()} className="btn-logout" title="Log out">
                Sign Out
              </button>
            </div>
          ) : (
            <div className="login-actions">
              <button onClick={() => loginAsDemo('analyst')} className="btn-login">
                Demo Login
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
