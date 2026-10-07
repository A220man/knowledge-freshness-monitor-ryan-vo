import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';

describe('App Component', () => {
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
              username: 'ryan_vo',
              email: 'ryandtvo@gmail.com',
              role: 'analyst',
              csrf_token: 'csrf123'
            })
        });
      }
      if (url.includes('/api/documents')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve([])
        });
      }
      if (url.includes('/api/citations/answers')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve([])
        });
      }
      if (url.includes('/api/revalidation/tasks')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve([])
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({})
      });
    });
  });

  it('renders application header and navbar navigation tabs', async () => {
    render(<App />);
    expect(screen.getByText('Knowledge Freshness Monitor')).toBeInTheDocument();
    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Documents & Drift')).toBeInTheDocument();
    expect(screen.getByText('Citation Graph')).toBeInTheDocument();
    expect(screen.getByText('Revalidation Queue')).toBeInTheDocument();
    expect(screen.getByText('AI/ML Evaluation')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('ryan_vo')).toBeInTheDocument();
    });
  });
});
