"""SQLAlchemy database entities representing documents, citations, tasks, and sessions."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    token = Column(String(128), unique=True, index=True, nullable=False)
    user_id = Column(String(64), index=True, nullable=False)
    username = Column(String(64), nullable=False)
    email = Column(String(128), nullable=False)
    role = Column(String(32), default="viewer", nullable=False)
    csrf_token = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class Document(Base):
    __tablename__ = "documents"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(256), nullable=False, index=True)
    source_uri = Column(String(512), nullable=False)
    category = Column(String(64), default="general", index=True, nullable=False)
    retention_days = Column(Integer, default=90, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    revisions = relationship("DocumentRevision", back_populates="document", cascade="all, delete-orphan", order_by="desc(DocumentRevision.version)")


class DocumentRevision(Base):
    __tablename__ = "document_revisions"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    text_content = Column(Text, nullable=False)
    chunk_count = Column(Integer, default=0, nullable=False)
    drift_score = Column(Float, default=0.0, nullable=False)
    expiration_timestamp = Column(DateTime, nullable=True, index=True)
    status = Column(String(32), default="fresh", nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    document = relationship("Document", back_populates="revisions")
    chunks = relationship("DocumentChunk", back_populates="revision", cascade="all, delete-orphan")
    citations = relationship("CitationEdge", back_populates="revision", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    revision_id = Column(String(64), ForeignKey("document_revisions.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_hash = Column(String(64), nullable=False)
    metadata_json = Column(Text, default="{}", nullable=False)
    revision = relationship("DocumentRevision", back_populates="chunks")
    citations = relationship("CitationEdge", back_populates="chunk", cascade="all, delete-orphan")


class RagAnswer(Base):
    __tablename__ = "rag_answers"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=False)
    query_hash = Column(String(64), nullable=False, index=True)
    freshness_status = Column(String(32), default="fresh", nullable=False, index=True)
    impact_score = Column(Float, default=0.0, nullable=False)
    last_validated_at = Column(DateTime, default=utc_now, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    citations = relationship("CitationEdge", back_populates="answer", cascade="all, delete-orphan")
    revalidations = relationship("RevalidationTask", back_populates="answer", cascade="all, delete-orphan")


class CitationEdge(Base):
    __tablename__ = "citation_edges"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_id = Column(String(64), ForeignKey("rag_answers.id", ondelete="CASCADE"), nullable=False, index=True)
    revision_id = Column(String(64), ForeignKey("document_revisions.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String(64), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=True, index=True)
    citation_excerpt = Column(Text, default="", nullable=False)
    confidence_weight = Column(Float, default=1.0, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    answer = relationship("RagAnswer", back_populates="citations")
    revision = relationship("DocumentRevision", back_populates="citations")
    chunk = relationship("DocumentChunk", back_populates="citations")


class RevalidationTask(Base):
    __tablename__ = "revalidation_tasks"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_id = Column(String(64), ForeignKey("rag_answers.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(String(256), nullable=False)
    priority_score = Column(Float, default=0.5, nullable=False, index=True)
    priority_level = Column(String(32), default="medium", nullable=False, index=True)
    status = Column(String(32), default="pending", nullable=False, index=True)
    scheduled_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(64), nullable=True)
    notes = Column(Text, default="", nullable=False)
    answer = relationship("RagAnswer", back_populates="revalidations")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False, index=True)
    resource_id = Column(String(64), nullable=False)
    details_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False, index=True)
