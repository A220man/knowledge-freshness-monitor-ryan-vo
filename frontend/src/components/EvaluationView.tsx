import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { BenchmarkMetrics } from '../types';

export const EvaluationView: React.FC = () => {
  const [metrics, setMetrics] = useState<BenchmarkMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const runEvaluation = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.evaluation.runBenchmark();
      setMetrics(res);
    } catch (err: any) {
      setError(err.message || 'Failed to run benchmark suite');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runEvaluation();
  }, []);

  return (
    <div className="evaluation-container">
      <div className="section-toolbar">
        <div>
          <h2>AI/ML Evaluation & Drift Benchmark</h2>
          <p className="section-desc">
            Offline reproducible evaluation measuring precision, recall, and latency of the deterministic freshness pipeline.
          </p>
        </div>
        <button onClick={runEvaluation} disabled={loading} className="btn-primary">
          {loading ? 'Evaluating Pipeline...' : 'Re-run Benchmark Suite'}
        </button>
      </div>

      <div className="card cli-command-card">
        <div className="cli-header">Reproducible CLI Verification Command:</div>
        <code>PYTHONPATH=. .venv/bin/python -m backend.evaluation.evaluator</code>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)} className="btn-close">×</button>
        </div>
      )}

      {loading ? (
        <div className="card loading-card">
          <div className="spinner"></div>
          <p>Running 20-scenario ground-truth evaluation harness...</p>
        </div>
      ) : metrics ? (
        <div className="evaluation-results">
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Evaluation Cases</div>
              <div className="metric-value">{metrics.total_cases}</div>
              <div className="metric-detail">{metrics.dataset_name}</div>
            </div>

            <div className="metric-card accent">
              <div className="metric-label">Precision</div>
              <div className="metric-value">{(metrics.precision * 100).toFixed(1)}%</div>
              <div className="metric-detail">False positive control</div>
            </div>

            <div className="metric-card accent">
              <div className="metric-label">Recall</div>
              <div className="metric-value">{(metrics.recall * 100).toFixed(1)}%</div>
              <div className="metric-detail">Stale detection sensitivity</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">F1 Score</div>
              <div className="metric-value">{metrics.f1_score.toFixed(4)}</div>
              <div className="metric-detail">Harmonic mean</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Severity Accuracy</div>
              <div className="metric-value">{(metrics.drift_detection_accuracy * 100).toFixed(1)}%</div>
              <div className="metric-detail">Exact category match</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Mean Latency</div>
              <div className="metric-value">{metrics.mean_latency_ms.toFixed(3)} ms</div>
              <div className="metric-detail">Deterministic offline speed</div>
            </div>
          </div>

          <div className="card failure-cases-card">
            <div className="card-header">
              <h3>Observed Boundary & Failure Cases ({metrics.failure_cases.length})</h3>
              <span className="badge">Heuristic Limitations</span>
            </div>
            <p className="card-desc">
              Deterministic offline n-gram Jaccard and Term-Frequency metrics provide instant sub-millisecond evaluation without LLM costs, but exhibit boundary limitations on pure lexical rephrasings:
            </p>

            <div className="failure-list">
              {metrics.failure_cases.map((fc) => (
                <div key={fc.id} className="failure-item">
                  <div className="failure-header">
                    <span className="failure-id">[{fc.id}]</span>
                    <span className="failure-desc">{fc.description}</span>
                    <span className={`pill-type pill-${fc.type}`}>{fc.type.toUpperCase()}</span>
                  </div>
                  <div className="failure-body">
                    <span>Drift Score: {(fc.drift_score * 100).toFixed(1)}%</span> |{' '}
                    <span>Predicted: <strong>{fc.pred_severity}</strong></span> |{' '}
                    <span>Expected: <strong>{fc.expected_severity}</strong></span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};
