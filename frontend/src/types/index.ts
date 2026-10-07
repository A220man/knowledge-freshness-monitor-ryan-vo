export interface UserProfile {
  user_id: string;
  username: string;
  email: string;
  role: 'viewer' | 'analyst' | 'admin';
  csrf_token: string;
}

export interface DocumentChunk {
  id: string;
  chunk_index: number;
  chunk_text: string;
  chunk_hash: string;
}

export interface DocumentRevision {
  id: string;
  document_id: string;
  version: number;
  content_hash: string;
  text_content: string;
  chunk_count: number;
  drift_score: float;
  expiration_timestamp: string | null;
  status: 'fresh' | 'stale' | 'expired' | 'superseded';
  created_at: string;
  chunks?: DocumentChunk[];
}

export type float = number;

export interface Document {
  id: string;
  title: string;
  source_uri: string;
  category: string;
  retention_days: number;
  created_at: string;
  updated_at: string;
  revisions?: DocumentRevision[];
}

export interface CitationEdge {
  id: string;
  answer_id: string;
  revision_id: string;
  chunk_id: string | null;
  citation_excerpt: string;
  confidence_weight: number;
  is_primary: boolean;
}

export interface RagAnswer {
  id: string;
  query_text: string;
  answer_text: string;
  query_hash: string;
  freshness_status: 'fresh' | 'stale' | 'critical_stale';
  impact_score: number;
  last_validated_at: string;
  created_at: string;
  citations?: CitationEdge[];
}

export interface ImpactedAnswerItem {
  answer_id: string;
  query_text: string;
  prior_status: string;
  current_status: string;
  impact_score: number;
  stale_reasons: string[];
  primary_citation_stale: boolean;
  affected_revisions: string[];
}

export interface ImpactAnalysisResponse {
  analyzed_documents: number;
  stale_or_expired_revisions: number;
  total_answers_evaluated: number;
  impacted_answers_count: number;
  impacted_answers: ImpactedAnswerItem[];
  execution_time_ms: number;
}

export interface RevalidationTask {
  id: string;
  answer_id: string;
  reason: string;
  priority_score: number;
  priority_level: 'high' | 'medium' | 'low';
  status: 'pending' | 'in_progress' | 'completed' | 'dismissed';
  scheduled_at: string;
  completed_at: string | null;
  resolved_by: string | null;
  notes: string;
  answer?: RagAnswer;
}

export interface AdvisoryReportResponse {
  answer_id: string;
  provider_used: string;
  model_used: string;
  is_advisory: boolean;
  grounding_verified: boolean;
  summary: string;
  recommendation: string;
  raw_reasoning?: string;
  citations_referenced: string[];
}

export interface BenchmarkMetrics {
  dataset_name: string;
  total_cases: number;
  precision: number;
  recall: number;
  f1_score: number;
  mean_latency_ms: number;
  drift_detection_accuracy: number;
  failure_cases: Array<{
    id: string;
    description: string;
    type: string;
    drift_score: number;
    pred_severity: string;
    expected_severity: string;
  }>;
}

export interface GraphNode {
  id: string;
  type: 'document' | 'revision' | 'answer';
  label: string;
  status: string;
  category?: string;
  drift_score?: number;
  impact_score?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  type: 'has_revision' | 'cites';
  is_primary?: boolean;
  weight?: number;
}

export interface CitationGraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  summary: {
    total_documents: number;
    total_revisions: number;
    total_answers: number;
    total_citations: number;
  };
}
