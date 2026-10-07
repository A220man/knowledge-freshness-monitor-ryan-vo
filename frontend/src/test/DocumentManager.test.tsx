import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DocumentManager } from '../components/DocumentManager';
import { AuthProvider } from '../context/AuthContext';

describe('DocumentManager Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/api/auth/me')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              user_id: 'u1',
              username: 'analyst_user',
              email: 'analyst@test.local',
              role: 'analyst',
              csrf_token: 'csrf123'
            })
        });
      }
      if (url.includes('/api/documents')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve([
              {
                id: 'doc_1',
                title: 'Security Compliance Guidelines',
                source_uri: 'https://docs.corp/sec',
                category: 'compliance',
                retention_days: 90,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
              }
            ])
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve([])
      });
    });
  });

  it('renders document list with items returned from API', async () => {
    render(
      <AuthProvider>
        <DocumentManager />
      </AuthProvider>
    );

    expect(screen.getByText('Monitored Knowledge Documents')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Security Compliance Guidelines')).toBeInTheDocument();
      expect(screen.getByText('https://docs.corp/sec')).toBeInTheDocument();
    });
  });
});
