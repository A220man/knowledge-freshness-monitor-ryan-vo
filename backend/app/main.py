"""Knowledge Freshness Monitor - FastAPI Application Entrypoint."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.core.config import settings
from backend.app.core.database import init_db, SessionLocal
from backend.app.api.auth import router as auth_router
from backend.app.api.documents import router as documents_router
from backend.app.api.citations import router as citations_router
from backend.app.api.revalidation import router as revalidation_router
from backend.app.api.evaluation import router as evaluation_router
from backend.app.api.audit import router as audit_router
from backend.app.services.document_service import create_document
from backend.app.models.entities import Document, RagAnswer, CitationEdge, DocumentRevision


def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        if db.query(Document).count() > 0:
            return
        doc1 = create_document(
            db=db,
            title="Enterprise API Gateway Rate Limiting Policy",
            source_uri="https://docs.corp/gateway/rates",
            category="api_spec",
            retention_days=180,
            initial_content="Default rate limit is 100 RPM per tenant with 150 RPM burst capacity."
        )
        doc2 = create_document(
            db=db,
            title="Security Audit & Log Retention Standard",
            source_uri="https://compliance.corp/retention",
            category="compliance",
            retention_days=30,
            initial_content="Security audit logs must be retained in encrypted cold storage for 90 days."
        )
        rev1 = db.query(DocumentRevision).filter(DocumentRevision.document_id == doc1.id).first()
        if rev1:
            ans1 = RagAnswer(
                query_text="What are rate limits for tenant API calls?",
                answer_text="Tenants are limited to 100 requests per minute with 150 burst capacity.",
                query_hash="hash_rate_1",
                freshness_status="fresh",
                impact_score=0.0
            )
            db.add(ans1)
            db.flush()
            db.add(CitationEdge(
                answer_id=ans1.id, revision_id=rev1.id,
                citation_excerpt="Default rate limit is 100 RPM per tenant.",
                confidence_weight=0.95, is_primary=True
            ))
        rev2 = db.query(DocumentRevision).filter(DocumentRevision.document_id == doc2.id).first()
        if rev2:
            ans2 = RagAnswer(
                query_text="How long are security logs kept?",
                answer_text="Security logs are retained for 90 days in cold storage.",
                query_hash="hash_ret_2",
                freshness_status="fresh",
                impact_score=0.0
            )
            db.add(ans2)
            db.flush()
            db.add(CitationEdge(
                answer_id=ans2.id, revision_id=rev2.id,
                citation_excerpt="Security audit logs must be retained for 90 days.",
                confidence_weight=0.9, is_primary=True
            ))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_production_guards()
    init_db()
    seed_demo_data()
    yield


app = FastAPI(
    title="Knowledge Freshness Monitor",
    description="Tracks document revisions, citation graph impacts, and schedules revalidations.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error occurred.", "error_type": type(exc).__name__}
    )


app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(citations_router)
app.include_router(revalidation_router)
app.include_router(evaluation_router)
app.include_router(audit_router)


@app.get("/api/health")
def healthcheck():
    return {"status": "healthy", "version": "1.0.0", "environment": settings.ENVIRONMENT, "auth_method": settings.AUTH_METHOD}


@app.get("/")
def root_index():
    return {
        "name": "knowledge-freshness-monitor-ryan-vo",
        "version": "1.0.0",
        "author": "Ryan Vo <ryandtvo@gmail.com>",
        "docs_url": "/docs"
    }
