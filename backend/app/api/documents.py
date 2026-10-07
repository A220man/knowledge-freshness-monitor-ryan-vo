"""Document lifecycle, revisions, and expiration monitoring API."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import require_viewer, require_analyst, require_admin
from backend.app.models.entities import Document, DocumentRevision, UserSession
from backend.app.models.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentRevisionCreate,
    DocumentRevisionResponse
)
from backend.app.services.document_service import (
    create_document,
    add_document_revision,
    check_and_update_expirations
)
from backend.app.services.audit_service import log_action

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    category: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: UserSession = Depends(require_viewer),
    db: Session = Depends(get_db)
) -> List[Document]:
    query = db.query(Document)
    if category:
        query = query.filter(Document.category == category)
    return query.order_by(Document.updated_at.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_new_document(
    payload: DocumentCreate,
    session: UserSession = Depends(require_analyst),
    db: Session = Depends(get_db)
) -> Document:
    doc = create_document(
        db=db, title=payload.title, source_uri=payload.source_uri,
        category=payload.category, retention_days=payload.retention_days,
        initial_content=payload.initial_content
    )
    log_action(db=db, user_id=session.user_id, action="document.create", resource_type="document", resource_id=doc.id, details={})
    return doc


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_details(
    document_id: str,
    session: UserSession = Depends(require_viewer),
    db: Session = Depends(get_db)
) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return doc


@router.post("/{document_id}/revisions", response_model=DocumentRevisionResponse, status_code=status.HTTP_201_CREATED)
def submit_new_revision(
    document_id: str,
    payload: DocumentRevisionCreate,
    session: UserSession = Depends(require_analyst),
    db: Session = Depends(get_db)
) -> DocumentRevision:
    try:
        rev = add_document_revision(
            db=db, document_id=document_id, new_content=payload.text_content, expiration_days=payload.expiration_days
        )
        log_action(db=db, user_id=session.user_id, action="document.revision_add", resource_type="document_revision", resource_id=rev.id, details={})
        return rev
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/check-expirations", response_model=Dict[str, int])
def trigger_expiration_scan(
    session: UserSession = Depends(require_analyst),
    db: Session = Depends(get_db)
) -> Dict[str, int]:
    results = check_and_update_expirations(db)
    log_action(db=db, user_id=session.user_id, action="document.expiration_scan", resource_type="system", resource_id="expiration", details=results)
    return results


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    session: UserSession = Depends(require_admin),
    db: Session = Depends(get_db)
) -> None:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    db.delete(doc)
    db.commit()
    log_action(db=db, user_id=session.user_id, action="document.delete", resource_type="document", resource_id=document_id, details={})
