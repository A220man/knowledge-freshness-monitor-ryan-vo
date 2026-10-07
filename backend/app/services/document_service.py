"""Document lifecycle, chunking, versioning, and retention management."""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models.entities import Document, DocumentRevision, DocumentChunk
from backend.app.services.drift_engine import compute_drift_score
from backend.app.services.graph_engine import propagate_all_impacts


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_document_text(text: str, target_chunk_size: int = 350) -> List[str]:
    clean_text = text.strip()
    if not clean_text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", clean_text) if p.strip()]
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_length = 0

    for para in paragraphs:
        para_words = len(para.split())
        if current_length + para_words <= target_chunk_size:
            current_chunk.append(para)
            current_length += para_words
        else:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            if para_words > target_chunk_size:
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
                sent_chunk: List[str] = []
                sent_len = 0
                for sent in sentences:
                    s_words = len(sent.split())
                    if sent_len + s_words <= target_chunk_size:
                        sent_chunk.append(sent)
                        sent_len += s_words
                    else:
                        if sent_chunk:
                            chunks.append(" ".join(sent_chunk))
                        sent_chunk = [sent]
                        sent_len = s_words
                if sent_chunk:
                    chunks.append(" ".join(sent_chunk))
            else:
                current_chunk.append(para)
                current_length += para_words
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    return chunks if chunks else [clean_text]


def create_document(
    db: Session,
    title: str,
    source_uri: str,
    category: str,
    retention_days: int,
    initial_content: str
) -> Document:
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(days=retention_days)
    doc = Document(
        title=title, source_uri=source_uri, category=category,
        retention_days=retention_days, created_at=now, updated_at=now
    )
    db.add(doc)
    db.flush()

    chunks = chunk_document_text(initial_content)
    rev = DocumentRevision(
        document_id=doc.id, version=1, content_hash=compute_sha256(initial_content),
        text_content=initial_content, chunk_count=len(chunks), drift_score=0.0,
        expiration_timestamp=expiration, status="fresh", created_at=now
    )
    db.add(rev)
    db.flush()

    for idx, c_text in enumerate(chunks):
        db.add(DocumentChunk(
            revision_id=rev.id, chunk_index=idx, chunk_text=c_text,
            chunk_hash=compute_sha256(c_text),
            metadata_json=json.dumps({"word_count": len(c_text.split()), "index": idx})
        ))
    db.commit()
    db.refresh(doc)
    return doc


def add_document_revision(
    db: Session,
    document_id: str,
    new_content: str,
    expiration_days: Optional[int] = None
) -> DocumentRevision:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document with id {document_id} not found.")

    now = datetime.now(timezone.utc)
    days_to_expire = expiration_days if expiration_days is not None else doc.retention_days
    new_expiration = now + timedelta(days=days_to_expire)

    latest_rev = (
        db.query(DocumentRevision)
        .filter(DocumentRevision.document_id == document_id)
        .order_by(DocumentRevision.version.desc())
        .first()
    )
    prior_version = latest_rev.version if latest_rev else 0
    drift = 0.0
    if latest_rev:
        drift = compute_drift_score(latest_rev.text_content, new_content)
        prior_revs = db.query(DocumentRevision).filter(
            DocumentRevision.document_id == document_id,
            DocumentRevision.status != "superseded"
        ).all()
        for pr in prior_revs:
            pr.status = "superseded"

    new_version_num = prior_version + 1
    chunks = chunk_document_text(new_content)
    new_rev = DocumentRevision(
        document_id=doc.id, version=new_version_num, content_hash=compute_sha256(new_content),
        text_content=new_content, chunk_count=len(chunks), drift_score=drift,
        expiration_timestamp=new_expiration, status="fresh", created_at=now
    )
    db.add(new_rev)
    db.flush()

    for idx, c_text in enumerate(chunks):
        db.add(DocumentChunk(
            revision_id=new_rev.id, chunk_index=idx, chunk_text=c_text,
            chunk_hash=compute_sha256(c_text),
            metadata_json=json.dumps({"word_count": len(c_text.split()), "index": idx})
        ))

    doc.updated_at = now
    db.commit()
    db.refresh(new_rev)
    propagate_all_impacts(db)
    return new_rev


def check_and_update_expirations(db: Session) -> Dict[str, int]:
    now = datetime.now(timezone.utc)
    active_revisions = db.query(DocumentRevision).filter(
        DocumentRevision.status.in_(["fresh", "stale"]),
        DocumentRevision.expiration_timestamp.isnot(None)
    ).all()

    expired_count = 0
    for rev in active_revisions:
        exp_ts = rev.expiration_timestamp
        if exp_ts.tzinfo is None:
            exp_ts = exp_ts.replace(tzinfo=timezone.utc)
        if now >= exp_ts:
            rev.status = "expired"
            expired_count += 1

    if expired_count > 0:
        db.commit()
        propagate_all_impacts(db)
    return {"expired_count": expired_count}
