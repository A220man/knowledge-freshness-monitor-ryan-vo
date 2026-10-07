import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Document, RagAnswer, RevalidationTask, ImpactAnalysisResponse } from '../types';
import { useAuth } from '../context/AuthContext';

export const DashboardMetrics: React.FC = () => {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [answers, setAnswers] = useState<RagAnswer[]>([]);
  const [tasks, setTasks] = useState<RevalidationTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [docsData, ansData, tasksData] = await Promise.all([
        api.documents.list(),
        api.citations.listAnswers(),
        api.revalidation.listTasks()
      ]);
      setDocuments(docsData);
      setAnswers(ansData);
      setTasks(tasksData);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleRunImpactAnalysis = async () => {
    try {
      setIsProcessing(true);
      const res: ImpactAnalysisResponse = await api.citations.runImpactAnalysis();
      setActionMessage(`Propagated in ${res.execution_time_ms}ms: ${res.impacted_answers_count} impacted answers.`);
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Impact analysis error');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCheckExpirations = async () => {
    try {
      setIsProcessing(true);
      const res = await api.documents.checkExpirations();
      setActionMessage(`Expiration scan: ${res.expired_count} revisions expired.`);
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Expiration scan error');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBatchSchedule = async () => {
    try {
      setIsProcessing(true);
      const res = await api.revalidation.batchSchedule(0.3);
      setActionMessage(`Scheduled ${res.tasks_scheduled} tasks (${res.tasks_skipped} skipped).`);
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Batch scheduling error');
    } finally {
      setIsProcessing(false);
    }
  };

  if (loading) return <div className="card loading-card"><div className="spinner"></div><p>Loading metrics...</p></div>;
  if (error) return <div className="card error-card"><h3>Error</h3><p>{error}</p><button onClick={loadData} className="btn-secondary">Retry</button></div>;

  const staleCount = answers.filter((a) => a.freshness_status !== 'fresh').length;
  const criticalCount = answers.filter((a) => a.freshness_status === 'critical_stale').length;
  const pendingCount = tasks.filter((t) => t.status === 'pending').length;

  return (
    <div className="dashboard-container">
      <div className="section-toolbar">
        <div>
          <h2>Knowledge Freshness Overview</h2>
          <p className="section-desc">Deterministic graph engine monitoring revisions, drift, and RAG answer staleness.</p>
        </div>
        <div className="quick-actions">
          <button onClick={handleRunImpactAnalysis} disabled={isProcessing || user?.role === 'viewer'} className="btn-primary">
            {isProcessing ? 'Evaluating...' : 'Propagate Graph Impact'}
          </button>
          <button onClick={handleCheckExpirations} disabled={isProcessing || user?.role === 'viewer'} className="btn-secondary">
            Check Expirations
          </button>
          <button onClick={handleBatchSchedule} disabled={isProcessing || user?.role === 'viewer'} className="btn-secondary">
            Auto-Queue Tasks
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="alert alert-info">
          <span>ℹ️ {actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="btn-close">×</button>
        </div>
      )}

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-label">Monitored Documents</div>
          <div className="metric-value">{documents.length}</div>
          <div className="metric-detail">Continuous retention tracking</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Tracked RAG Answers</div>
          <div className="metric-value">{answers.length}</div>
          <div className="metric-detail">Active citation nodes</div>
        </div>
        <div className="metric-card warning">
          <div className="metric-label">Stale Answers</div>
          <div className="metric-value">{staleCount}</div>
          <div className="metric-detail">{criticalCount} critical severity</div>
        </div>
        <div className="metric-card accent">
          <div className="metric-label">Pending Revalidations</div>
          <div className="metric-value">{pendingCount}</div>
          <div className="metric-detail">{tasks.length} total tasks</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>Tracked Answer Freshness Overview</h3>
          <span className="badge">{answers.length} indexed</span>
        </div>
        {answers.length === 0 ? (
          <div className="empty-state"><p>No RAG answers indexed yet.</p></div>
        ) : (
          <table className="data-table">
            <thead><tr><th>Query</th><th>Freshness</th><th>Impact</th><th>Citations</th><th>Last Validated</th></tr></thead>
            <tbody>
              {answers.map((ans) => (
                <tr key={ans.id}>
                  <td className="query-cell">
                    <strong>{ans.query_text}</strong>
                    <div className="answer-snippet">{ans.answer_text}</div>
                  </td>
                  <td>
                    <span className={`status-pill status-${ans.freshness_status}`}>
                      {ans.freshness_status.replace('_', ' ').toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <div className="progress-bar-container">
                      <div
                        className={`progress-bar ${ans.impact_score >= 0.7 ? 'bar-critical' : ans.impact_score >= 0.25 ? 'bar-warning' : 'bar-success'}`}
                        style={{ width: `${Math.max(5, ans.impact_score * 100)}%` }}
                      ></div>
                      <span className="score-text">{(ans.impact_score * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td>{ans.citations ? ans.citations.length : 0} citations</td>
                  <td className="date-cell">{new Date(ans.last_validated_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
