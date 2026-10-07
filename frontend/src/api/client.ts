import {
  UserProfile,
  Document,
  DocumentRevision,
  RagAnswer,
  ImpactAnalysisResponse,
  RevalidationTask,
  AdvisoryReportResponse,
  BenchmarkMetrics,
  CitationGraphData
} from '../types';

let cachedCsrfToken: string = '';

export function setCsrfToken(token: string) {
  cachedCsrfToken = token;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  headers.set('Accept', 'application/json');

  if (options.body && typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  // Attach CSRF token on mutating requests
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method || 'GET')) {
    if (cachedCsrfToken) {
      headers.set('X-CSRF-Token', cachedCsrfToken);
    }
  }

  const res = await fetch(path, {
    ...options,
    headers,
    credentials: 'include'
  });

  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
    try {
      const errorJson = await res.json();
      if (errorJson.detail) {
        errorDetail = typeof errorJson.detail === 'string'
          ? errorJson.detail
          : JSON.stringify(errorJson.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errorDetail);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json() as Promise<T>;
}

export const api = {
  auth: {
    me: () => request<UserProfile>('/api/auth/me'),
    demoLogin: (role: 'viewer' | 'analyst' | 'admin' = 'analyst', username?: string) =>
      request<UserProfile>('/api/auth/demo-login', {
        method: 'POST',
        body: JSON.stringify({ role, username })
      }),
    logout: () => request<{ status: string }>('/api/auth/logout', { method: 'POST' }),
    getOidcLoginUrl: () => request<{ auth_url: string }>('/api/auth/oidc/login')
  },

  documents: {
    list: (category?: string) => {
      const url = category ? `/api/documents?category=${encodeURIComponent(category)}` : '/api/documents';
      return request<Document[]>(url);
    },
    get: (id: string) => request<Document>(`/api/documents/${id}`),
    create: (data: { title: string; source_uri: string; category: string; retention_days: number; initial_content: string }) =>
      request<Document>('/api/documents', {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    addRevision: (id: string, text_content: string, expiration_days?: number) =>
      request<DocumentRevision>(`/api/documents/${id}/revisions`, {
        method: 'POST',
        body: JSON.stringify({ text_content, expiration_days })
      }),
    checkExpirations: () =>
      request<{ expired_count: number }>('/api/documents/check-expirations', { method: 'POST' }),
    delete: (id: string) =>
      request<void>(`/api/documents/${id}`, { method: 'DELETE' })
  },

  citations: {
    listAnswers: (status?: string) => {
      const url = status ? `/api/citations/answers?freshness_status=${encodeURIComponent(status)}` : '/api/citations/answers';
      return request<RagAnswer[]>(url);
    },
    getAnswer: (id: string) => request<RagAnswer>(`/api/citations/answers/${id}`),
    registerAnswer: (data: {
      query_text: string;
      answer_text: string;
      citations: Array<{ revision_id: string; chunk_id?: string; citation_excerpt: string; confidence_weight: number; is_primary: boolean }>;
    }) =>
      request<RagAnswer>('/api/citations/answers', {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    runImpactAnalysis: () =>
      request<ImpactAnalysisResponse>('/api/citations/impact-analysis', { method: 'POST' }),
    getGraph: () => request<CitationGraphData>('/api/citations/graph'),
    getAdvisoryReport: (answerId: string, providerOverride?: string) =>
      request<AdvisoryReportResponse>(`/api/citations/answers/${answerId}/advisory`, {
        method: 'POST',
        body: JSON.stringify({ provider_override: providerOverride })
      })
  },

  revalidation: {
    listTasks: (statusFilter?: string, priorityFilter?: string) => {
      const params = new URLSearchParams();
      if (statusFilter) params.append('status_filter', statusFilter);
      if (priorityFilter) params.append('priority_filter', priorityFilter);
      const query = params.toString() ? `?${params.toString()}` : '';
      return request<RevalidationTask[]>(`/api/revalidation/tasks${query}`);
    },
    createTask: (data: { answer_id: string; reason: string; priority_level: 'high' | 'medium' | 'low'; notes?: string }) =>
      request<RevalidationTask>('/api/revalidation/tasks', {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    batchSchedule: (minImpactThreshold: number = 0.3) =>
      request<{ evaluated_answers: number; tasks_scheduled: number; tasks_skipped: number }>('/api/revalidation/batch', {
        method: 'POST',
        body: JSON.stringify({ min_impact_threshold: minImpactThreshold })
      }),
    updateTaskStatus: (taskId: string, status: string, notes?: string) =>
      request<RevalidationTask>(`/api/revalidation/tasks/${taskId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status, notes })
      }),
    exportCsvUrl: '/api/revalidation/export'
  },

  evaluation: {
    runBenchmark: () => request<BenchmarkMetrics>('/api/evaluation/run')
  }
};
