"""User-controlled review fields must remain data when exported to a spreadsheet."""
import csv
import io
import pytest
from backend.app.models.entities import RagAnswer, RevalidationTask


@pytest.mark.parametrize('value', ['=1+1', '+1+1', '-1+1', '@SUM(1,2)', '  =1+1', '\t=1+1', '\r=1+1'])
def test_export_neutralizes_formula_cells_without_changing_stored_values(
    client, db_session, auth_headers_factory, value
):
    answer = RagAnswer(query_text=value, answer_text='Answer', query_hash='export-test', impact_score=.8)
    db_session.add(answer)
    db_session.flush()
    task = RevalidationTask(answer_id=answer.id, reason=value, resolved_by=value,
                            status='completed', priority_score=.75, priority_level='high')
    db_session.add(task)
    db_session.commit()
    response = client.get('/api/revalidation/export', headers=auth_headers_factory('viewer'))
    assert response.status_code == 200
    row = list(csv.DictReader(io.StringIO(response.text)))[0]
    for field in ('query_text', 'reason', 'resolved_by'):
        assert row[field] == "'" + value
    assert row['priority_score'] == '0.7500'
    db_session.refresh(answer)
    db_session.refresh(task)
    assert answer.query_text == value and task.reason == value and task.resolved_by == value


def test_export_preserves_ordinary_quoted_and_multiline_text(client, db_session, auth_headers_factory):
    value = 'Ordinary, "quoted" text\nwith a second line and café'
    answer = RagAnswer(query_text=value, answer_text='Answer', query_hash='ordinary-export')
    db_session.add(answer)
    db_session.flush()
    db_session.add(RevalidationTask(answer_id=answer.id, reason=value, priority_score=.2, priority_level='low'))
    db_session.commit()
    response = client.get('/api/revalidation/export', headers=auth_headers_factory('viewer'))
    row = list(csv.DictReader(io.StringIO(response.text)))[0]
    assert row['query_text'] == value and row['reason'] == value
