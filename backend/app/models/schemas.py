"""Pydantic request and response schemas for validation and API serialization."""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class UserProfile(BaseModel):
    user_id: str
    username: str
    email: str
    role: str
    csrf_token: str


class DemoLoginRequest(BaseModel):
    role: str = Field(default="analyst", pattern="^(viewer|analyst|admin)$")
    username: Optional[str] = "demo_operator"


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=256)
    source_uri: str = Field(..., min_length=3, max_length=512)
    category: str = Field(default="knowledge_base", max_length=64)
    retention_days: int = Field(default=90, ge=1, le=3650)
    initial_content: str = Field(..., min_length=10)


class DocumentRevisionCreate(BaseModel):
    text_content: str = Field(..., min_length=10)
    expiration_days: Optional[int] = Field(default=None, ge=1, le=3650)


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    chunk_index: int
    chunk_text: str
    chunk_hash: str


class DocumentRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    version: int
    content_hash: str
    text_content: str
    chunk_count: int
    drift_score: float
    expiration_timestamp: Optional[datetime]
    status: str
    created_at: datetime
    chunks: Optional[List[DocumentChunkResponse]] = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    source_uri: str
    category: str
    retention_days: int
    created_at: datetime
    updated_at: datetime
    revisions: Optional[List[DocumentRevisionResponse]] = None


class CitationEdgeCreate(BaseModel):
    revision_id: str
    chunk_id: Optional[str] = None
    citation_excerpt: str = Field(default="", max_length=1000)
    confidence_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    is_primary: bool = True


class CitationEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    answer_id: str
    revision_id: str
    chunk_id: Optional[str]
    citation_excerpt: str
    confidence_weight: float
    is_primary: bool


class RagAnswerCreate(BaseModel):
    query_text: str = Field(..., min_length=3)
    answer_text: str = Field(..., min_length=3)
    citations: List[CitationEdgeCreate] = Field(..., min_length=1)


class RagAnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    query_text: str
    answer_text: str
    query_hash: str
    freshness_status: str
    impact_score: float
    last_validated_at: datetime
    created_at: datetime
    citations: Optional[List[CitationEdgeResponse]] = None


class ImpactedAnswerItem(BaseModel):
    answer_id: str
    query_text: str
    prior_status: str
    current_status: str
    impact_score: float
    stale_reasons: List[str]
    primary_citation_stale: bool
    affected_revisions: List[str]


class ImpactAnalysisResponse(BaseModel):
    analyzed_documents: int
    stale_or_expired_revisions: int
    total_answers_evaluated: int
    impacted_answers_count: int
    impacted_answers: List[ImpactedAnswerItem]
    execution_time_ms: float


class RevalidationTaskCreate(BaseModel):
    answer_id: str
    reason: str = Field(..., min_length=3, max_length=256)
    priority_level: str = Field(default="medium", pattern="^(high|medium|low)$")
    notes: Optional[str] = ""


class RevalidationTaskUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|in_progress|completed|dismissed)$")
    notes: Optional[str] = None


class RevalidationTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    answer_id: str
    reason: str
    priority_score: float
    priority_level: str
    status: str
    scheduled_at: datetime
    completed_at: Optional[datetime]
    resolved_by: Optional[str]
    notes: str
    answer: Optional[RagAnswerResponse] = None


class BatchRevalidationScheduleRequest(BaseModel):
    min_impact_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    override_existing_pending: bool = False


class AdvisoryReportRequest(BaseModel):
    answer_id: str
    provider_override: Optional[str] = None


class AdvisoryReportResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    answer_id: str
    provider_used: str
    model_used: str
    is_advisory: bool = True
    grounding_verified: bool
    summary: str
    recommendation: str
    raw_reasoning: Optional[str] = None
    citations_referenced: List[str]


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    details_json: str
    created_at: datetime


class BenchmarkResultResponse(BaseModel):
    dataset_name: str
    total_cases: int
    precision: float
    recall: float
    f1_score: float
    mean_latency_ms: float
    drift_detection_accuracy: float
    failure_cases: List[Dict[str, Any]]
