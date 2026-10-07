import React, { createContext, useContext, useState, useEffect } from 'react';
import { UserProfile } from '../types';
import { api, setCsrfToken } from '../api/client';

interface AuthContextType {
  user: UserProfile | null;
  loading: boolean;
  error: string | null;
  loginAsDemo: (role: 'viewer' | 'analyst' | 'admin', username?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refreshUser = async () => {
    try {
      setLoading(true);
      const profile = await api.auth.me();
      setUser(profile);
      setCsrfToken(profile.csrf_token);
      setError(null);
    } catch {
      // If not authenticated, attempt automatic demo login as analyst for smooth developer experience
      try {
        const demoProfile = await api.auth.demoLogin('analyst', 'demo_analyst');
        setUser(demoProfile);
        setCsrfToken(demoProfile.csrf_token);
        setError(null);
      } catch (demoErr: any) {
        setUser(null);
        setError(demoErr.message || 'Authentication required');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const loginAsDemo = async (role: 'viewer' | 'analyst' | 'admin', username?: string) => {
    setLoading(true);
    try {
      const profile = await api.auth.demoLogin(role, username);
      setUser(profile);
      setCsrfToken(profile.csrf_token);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Demo login failed');
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    setLoading(true);
    try {
      await api.auth.logout();
      setUser(null);
      setCsrfToken('');
    } catch (err: any) {
      setError(err.message || 'Logout failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, error, loginAsDemo, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
