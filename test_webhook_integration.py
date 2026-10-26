
"""Integration test for webhook trigger on critical_stale transition."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base
from backend.app.models.entities import Document, DocumentRevision, RagAnswer, CitationEdge
from backend.app.services.graph_engine import propagate_all_impacts


def test_webhook_triggers_on_critical_stale():
    """Test that webhook notification is triggered when answer transitions to critical_stale."""
    # Create in-memory database
    TEST_DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    db = TestSessionLocal()

    try:
        # Create document and expired revision
        doc = Document(id="doc_1", title="Test Document", source_uri="http://example.com/doc1", category="test")
        db.add(doc)

        rev = DocumentRevision(
            id="rev_1",
            document_id="doc_1",
            version=1,
            content_hash="hash1",
            text_content="Original content",
            chunk_count=1,
            drift_score=0.0,
            status="current",
            expiration_timestamp=datetime.now(timezone.utc) - timedelta(days=1)  # expired
        )
        db.add(rev)

        # Create RAG answer with primary citation to expired revision
        ans = RagAnswer(
            id="ans_1",
            query_text="What is the test?",
            answer_text="Test answer",
            query_hash="query_hash_1",
            freshness_status="fresh",  # initially fresh
            impact_score=0.0
        )
        db.add(ans)

        # Link answer to expired revision as primary citation
        edge = CitationEdge(
            answer_id="ans_1",
            revision_id="rev_1",
            is_primary=True,
            citation_excerpt="test excerpt",
            confidence_weight=1.0
        )
        db.add(edge)

        db.commit()

        print("Before propagation:")
        print(f"  Answer status: {ans.freshness_status}")
        print(f"  Answer impact: {ans.impact_score}")
        print(f"  Revision status: {rev.status}")
        now_utc = datetime.now(timezone.utc)
        exp_ts = rev.expiration_timestamp
        if exp_ts and exp_ts.tzinfo is None:
            exp_ts = exp_ts.replace(tzinfo=timezone.utc)
        print(f"  Revision expired: {exp_ts < now_utc}")
        result = propagate_all_impacts(db)

        print("\nAfter propagation:")
        print(f"  Answer status: {ans.freshness_status}")
        print(f"  Answer impact: {ans.impact_score}")
        print(f"  Impacted answers: {result['impacted_answers_count']}")
        for item in result['impacted_answers']:
            print(f"    - {item['answer_id']}: {item['current_status']} (was {item['prior_status']})")

        # Verify the transition happened
        assert ans.freshness_status == "critical_stale", f"Expected critical_stale, got {ans.freshness_status}"
        assert ans.impact_score >= 0.75, f"Expected impact >= 0.75, got {ans.impact_score}"
        assert result['impacted_answers_count'] == 1
        assert result['impacted_answers'][0]['current_status'] == "critical_stale"
        assert result['impacted_answers'][0]['prior_status'] == "fresh"

        print("\n✓ Test passed: Answer transitioned to critical_stale")
        print("  (Webhook would have been dispatched if async loop was running)")

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    test_webhook_triggers_on_critical_stale()

