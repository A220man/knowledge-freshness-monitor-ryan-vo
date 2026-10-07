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
