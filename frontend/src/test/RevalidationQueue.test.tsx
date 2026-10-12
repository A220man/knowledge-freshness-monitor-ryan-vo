import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RevalidationQueue } from '../components/RevalidationQueue';
import { AuthProvider } from '../context/AuthContext';

describe('RevalidationQueue Component', () => {
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
      if (url.includes('/api/revalidation/tasks')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve([
              {
                id: 'task_1',
                answer_id: 'ans_1',
                reason: 'Primary citation expired',
                priority_score: 0.85,
                priority_level: 'high',
                status: 'pending',
                scheduled_at: new Date().toISOString(),
                completed_at: null,
                resolved_by: null,
                notes: 'Automated scan',
                answer: {
                  id: 'ans_1',
                  query_text: 'What is the refund policy?',
                  answer_text: 'Refunds within 30 days.',
                  query_hash: 'hash1',
                  freshness_status: 'critical_stale',
                  impact_score: 0.85,
                  last_validated_at: new Date().toISOString(),
                  created_at: new Date().toISOString()
                }
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

  it('renders revalidation queue and handles filtered export click', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);

    render(
      <AuthProvider>
        <RevalidationQueue />
      </AuthProvider>
    );

    expect(screen.getByText('Revalidation Task Queue')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('What is the refund policy?')).toBeInTheDocument();
      expect(screen.getByText('HIGH (85%)')).toBeInTheDocument();
    });

    const exportBtn = screen.getByText(/Export CSV/i);
    fireEvent.click(exportBtn);

    expect(openSpy).toHaveBeenCalledWith('/api/revalidation/export', '_blank');

    // Change status filter to pending and test export URL includes status_filter
    const statusSelect = screen.getByDisplayValue('All Statuses');
    await waitFor(() => {
      fireEvent.change(statusSelect, { target: { value: 'pending' } });
    });

    fireEvent.click(exportBtn);
    expect(openSpy).toHaveBeenCalledWith('/api/revalidation/export?status_filter=pending', '_blank');

    openSpy.mockRestore();
  });
});
