# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

automated-drift-webhook-notifications

## Roadmap

### document-drift-tracking — Document Revision and Expiration Drift Tracking

Status: done

Acceptance:
- Ingest documents and segment into content-hashed chunks
- Compute composite Jaccard and cosine drift scores across revisions
- Track retention deadlines and mark expired revisions

Implementation: `backend/app/services/document_service.py`, `backend/app/services/drift_engine.py`, `backend/app/api/documents.py`, `frontend/src/components/DocumentManager.tsx`

Tests: `backend/tests/test_drift_engine.py`, `backend/tests/test_documents_api.py`, `frontend/src/test/DocumentManager.test.tsx`

### citation-graph-propagation — Citation Dependency Graph and Impact Propagation

Status: done

Acceptance:
- Map RAG answer citations to versioned document revisions
- Propagate revision drift and expiration across citation graph
- Classify answer severity into fresh, stale, and critical_stale

Implementation: `backend/app/services/graph_engine.py`, `backend/app/api/citations.py`, `frontend/src/components/CitationGraphView.tsx`

Tests: `backend/tests/test_graph_engine.py`, `backend/tests/test_citations_api.py`, `frontend/src/test/CitationGraphView.test.tsx`

### revalidation-queue-workflow — Revalidation Task Queue and Priority Scheduling

Status: done

Acceptance:
- Score task priorities based on impact, primary citation breach, and breadth
- Support automated batch scheduling for stale answers
- Manage task lifecycle states and neutralize spreadsheet formulas in CSV export

Implementation: `backend/app/services/scheduler_service.py`, `backend/app/api/revalidation.py`, `frontend/src/components/RevalidationQueue.tsx`

Tests: `backend/tests/test_revalidation_api.py`, `backend/tests/test_export_safety.py`

### opt-in-llm-advisory — Opt-in Grounded Advisory Reports

Status: done

Acceptance:
- Synthesize grounded revision summaries across multi-provider adapters
- Provide offline fallback when LLM_API_KEY is not configured
- Redact credentials and sensitive headers from error messages

Implementation: `backend/app/services/llm_advisor.py`, `backend/app/api/citations.py`

Tests: `backend/tests/test_llm_advisor.py`

### oidc-rbac-security — OIDC Authentication and Role-Based Access Control

Status: done

Acceptance:
- Support Keycloak OIDC authorization code flow and local demo session mode
- Enforce viewer, analyst, and admin roles across all API endpoints
- Enforce CSRF token validation on state-modifying requests

Implementation: `backend/app/core/security.py`, `backend/app/api/auth.py`, `frontend/src/context/AuthContext.tsx`

Tests: `backend/tests/test_auth.py`

### offline-benchmark-suite — Offline AI/ML Freshness Evaluation Benchmark

Status: done

Acceptance:
- Evaluate drift and impact detection across 20 curated RAG revision cases
- Measure precision, recall, F1 score, severity accuracy, and evaluation latency
- Expose reproducible benchmark execution in backend and frontend

Implementation: `backend/evaluation/evaluator.py`, `backend/app/api/evaluation.py`, `frontend/src/components/EvaluationView.tsx`

Tests: `backend/tests/test_drift_engine.py`

### filtered-revalidation-export — Filtered Revalidation Task CSV Export

Status: done

Acceptance:
- Filter exported revalidation CSV tasks by status and priority level
- Synchronize frontend queue filter parameters with CSV export URL generation
- Preserve formula neutralization and spreadsheet safety on filtered exports

Implementation: `backend/app/services/scheduler_service.py`, `backend/app/api/revalidation.py`, `frontend/src/api/client.ts`, `frontend/src/components/RevalidationQueue.tsx`

Tests: `backend/tests/test_revalidation_api.py`, `backend/tests/test_export_safety.py`, `frontend/src/test/RevalidationQueue.test.tsx`

### citation-subgraph-filtering — Citation Subgraph Query Filtering

Status: done

Acceptance:
- Filter citation graph topology by document domain, impact threshold, and answer recency
- Isolate impacted clusters in visual DAG representation

Implementation: `backend/app/services/graph_engine.py`, `backend/app/api/citations.py`, `frontend/src/api/client.ts`, `frontend/src/components/CitationGraphView.tsx`

Tests: `backend/tests/test_graph_engine.py`, `backend/tests/test_citations_api.py`, `frontend/src/test/CitationGraphView.test.tsx`

### automated-drift-webhook-notifications — Automated Drift Webhook Notifications

Status: done

Acceptance:
- Dispatch webhook alerts when answers transition to critical_stale status
- Support retry backoff and HMAC signature verification

Implementation: `backend/app/services/webhook_service.py`, `backend/app/services/graph_engine.py`, `backend/app/api/webhooks.py`, `backend/app/core/config.py`

Tests: `backend/tests/test_webhook_service.py`

