import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CitationGraphView } from '../components/CitationGraphView';
import { AuthProvider } from '../context/AuthContext';

describe('CitationGraphView Component', () => {
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
      if (url.includes('/api/citations/graph')) {
        const filtered = url.includes('domain=policy');
        const payload = filtered
          ? {
              nodes: [
                { id: 'doc_1', type: 'document', label: 'Policy Manual', status: 'active', category: 'policy', cluster_id: 'c1' },
                { id: 'ans_9', type: 'answer', label: 'Retention window?', status: 'critical_stale', impact_score: 0.91, cluster_id: 'c1' }
              ],
              links: [{ source: 'ans_9', target: 'doc_1', type: 'cites', is_primary: true, weight: 0.9 }],
              clusters: [{ id: 'c1', node_ids: ['doc_1', 'ans_9'], max_impact: 0.91, domains: ['policy'], answer_count: 1 }],
              summary: { total_documents: 1, total_revisions: 0, total_answers: 1, total_citations: 1, cluster_count: 1 }
            }
          : {
              nodes: [{ id: 'doc_1', type: 'document', label: 'API Specs', status: 'active' }],
              links: [],
              clusters: [],
              summary: { total_documents: 1, total_revisions: 1, total_answers: 1, total_citations: 1, cluster_count: 1 }
            };
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(payload) });
      }
      if (url.includes('/api/citations/answers')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve([
              {
                id: 'ans_1',
                query_text: 'What are rate limits?',
                answer_text: 'Rate limits are 100 RPM.',
                query_hash: 'qhash1',
                freshness_status: 'fresh',
                impact_score: 0.0,
                last_validated_at: new Date().toISOString(),
                created_at: new Date().toISOString()
              },
              {
                id: '9',
                query_text: 'Retention window?',
                answer_text: 'Records stay for 90 days.',
                query_hash: 'qhash9',
                freshness_status: 'critical_stale',
                impact_score: 0.91,
                last_validated_at: new Date().toISOString(),
                created_at: new Date().toISOString()
              }
            ])
        });
      }
      if (url.includes('/api/documents')) {
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

  it('renders citation graph topology and registered answers', async () => {
    render(
      <AuthProvider>
        <CitationGraphView />
      </AuthProvider>
    );

    expect(screen.getByText('RAG Citation Dependency Graph')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('1 Documents')).toBeInTheDocument();
      expect(screen.getByText('What are rate limits?')).toBeInTheDocument();
    });
  });

  it('filters the citation subgraph and isolates the matching cluster', async () => {
    render(
      <AuthProvider>
        <CitationGraphView />
      </AuthProvider>
    );

    fireEvent.change(await screen.findByLabelText('Document domain'), { target: { value: 'policy' } });
    fireEvent.change(screen.getByLabelText('Impact threshold'), { target: { value: '0.7' } });
    fireEvent.change(screen.getByLabelText('Answer recency'), { target: { value: '30' } });

    await waitFor(() => {
      const urls = (global.fetch as any).mock.calls.map((call: any[]) => String(call[0]));
      expect(urls.some((url: string) =>
        url.includes('domain=policy') && url.includes('min_impact=0.7') && url.includes('recency_days=30')
      )).toBe(true);
      expect(screen.getByText('Cluster 1 · policy')).toBeInTheDocument();
      expect(screen.getByText('Retention window?')).toBeInTheDocument();
      expect(screen.queryByText('What are rate limits?')).not.toBeInTheDocument();
    });
  });
});
