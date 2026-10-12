"""API tests for revalidation queue, priority scheduling, and export."""
from fastapi import status
from backend.app.models.entities import RagAnswer


def test_manual_revalidation_task_creation(client, auth_headers_factory, db_session):
    """Analyst can manually queue a revalidation task for an answer."""
    headers = auth_headers_factory(role="analyst")
    ans = RagAnswer(
        query_text="Sample query to revalidate",
        answer_text="Sample answer text",
        query_hash="hash_samp_1",
        freshness_status="stale",
        impact_score=0.65
    )
    db_session.add(ans)
    db_session.commit()

    payload = {
        "answer_id": ans.id,
        "reason": "Suspected regulatory policy shift",
        "priority_level": "high",
        "notes": "Verify against Q4 compliance directive."
    }
    res = client.post("/api/revalidation/tasks", json=payload, headers=headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["answer_id"] == ans.id
    assert data["priority_level"] == "high"
    assert data["status"] == "pending"


def test_batch_scheduling_tasks(client, auth_headers_factory, db_session):
    """Batch scheduling identifies stale answers above threshold and creates tasks."""
    headers = auth_headers_factory(role="analyst")
    ans = RagAnswer(
        query_text="Batch query test",
        answer_text="Batch answer test",
        query_hash="hash_batch_1",
        freshness_status="stale",
        impact_score=0.75
    )
    db_session.add(ans)
    db_session.commit()

    res = client.post("/api/revalidation/batch", json={"min_impact_threshold": 0.50}, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["tasks_scheduled"] >= 1


def test_modify_task_status_lifecycle(client, auth_headers_factory, db_session):
    """Transitioning task to completed sets completion timestamp and resets answer freshness."""
    headers = auth_headers_factory(role="analyst")
    ans = RagAnswer(
        query_text="Lifecycle query",
        answer_text="Lifecycle answer",
        query_hash="hash_lc_1",
        freshness_status="critical_stale",
        impact_score=0.9
    )
    db_session.add(ans)
    db_session.commit()

    task_res = client.post("/api/revalidation/tasks", json={
        "answer_id": ans.id,
        "reason": "Test lifecycle completion",
        "priority_level": "high"
    }, headers=headers)
    task_id = task_res.json()["id"]

    # Transition to completed
    update_res = client.patch(f"/api/revalidation/tasks/{task_id}", json={
        "status": "completed",
        "notes": "Re-verified with revised documentation."
    }, headers=headers)
    assert update_res.status_code == status.HTTP_200_OK
    assert update_res.json()["status"] == "completed"
    assert update_res.json()["completed_at"] is not None

    # Check answer status was reset
    db_session.refresh(ans)
    assert ans.freshness_status == "fresh"
    assert ans.impact_score == 0.0


def test_export_tasks_csv(client, auth_headers_factory):
    """Export endpoint delivers a valid CSV file."""
    headers = auth_headers_factory(role="viewer")
    res = client.get("/api/revalidation/export", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.headers["content-type"] == "text/csv; charset=utf-8"
    csv_text = res.text
    assert "task_id,answer_id,query_text,status" in csv_text


def test_export_tasks_csv_with_status_and_priority_filters(client, auth_headers_factory, db_session):
    """Export endpoint filters tasks by status and priority level."""
    import csv
    import io
    headers = auth_headers_factory(role="viewer")

    ans1 = RagAnswer(query_text="Pending High Query", answer_text="Ans1", query_hash="flt_1", impact_score=0.8)
    ans2 = RagAnswer(query_text="Completed Medium Query", answer_text="Ans2", query_hash="flt_2", impact_score=0.4)
    ans3 = RagAnswer(query_text="Pending Low Query", answer_text="Ans3", query_hash="flt_3", impact_score=0.2)
    db_session.add_all([ans1, ans2, ans3])
    db_session.flush()

    from backend.app.models.entities import RevalidationTask
    t1 = RevalidationTask(answer_id=ans1.id, reason="Reason 1", status="pending", priority_level="high", priority_score=0.85)
    t2 = RevalidationTask(answer_id=ans2.id, reason="Reason 2", status="completed", priority_level="medium", priority_score=0.45)
    t3 = RevalidationTask(answer_id=ans3.id, reason="Reason 3", status="pending", priority_level="low", priority_score=0.20)
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    # Filter by status=pending
    res_pending = client.get("/api/revalidation/export?status_filter=pending", headers=headers)
    assert res_pending.status_code == status.HTTP_200_OK
    rows_pending = list(csv.DictReader(io.StringIO(res_pending.text)))
    assert len(rows_pending) == 2
    assert all(r["status"] == "pending" for r in rows_pending)
    queries = {r["query_text"] for r in rows_pending}
    assert "Pending High Query" in queries
    assert "Pending Low Query" in queries
    assert "Completed Medium Query" not in queries

    # Filter by priority=high
    res_high = client.get("/api/revalidation/export?priority_filter=high", headers=headers)
    assert res_high.status_code == status.HTTP_200_OK
    rows_high = list(csv.DictReader(io.StringIO(res_high.text)))
    assert len(rows_high) == 1
    assert rows_high[0]["query_text"] == "Pending High Query"
    assert rows_high[0]["priority_level"] == "high"

    # Combined filters
    res_comb = client.get("/api/revalidation/export?status_filter=pending&priority_filter=low", headers=headers)
    assert res_comb.status_code == status.HTTP_200_OK
    rows_comb = list(csv.DictReader(io.StringIO(res_comb.text)))
    assert len(rows_comb) == 1
    assert rows_comb[0]["query_text"] == "Pending Low Query"

    # Filter matching nothing returns headers only
    res_empty = client.get("/api/revalidation/export?status_filter=dismissed", headers=headers)
    assert res_empty.status_code == status.HTTP_200_OK
    rows_empty = list(csv.DictReader(io.StringIO(res_empty.text)))
    assert len(rows_empty) == 0

