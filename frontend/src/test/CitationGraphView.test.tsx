import { render, screen, waitFor } from '@testing-library/react';
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
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              nodes: [
                { id: 'doc_1', type: 'document', label: 'API Specs', status: 'active' }
              ],
              links: [],
              summary: {
                total_documents: 1,
                total_revisions: 1,
                total_answers: 1,
                total_citations: 1
              }
            })
        });
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
});
