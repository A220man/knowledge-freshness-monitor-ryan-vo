import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { CitationGraphData, RagAnswer, Document, AdvisoryReportResponse } from '../types';
import { useAuth } from '../context/AuthContext';

function nodeSpot(graph: CitationGraphData, id: string) {
  const node = graph.nodes.find((n) => n.id === id);
  const clusters = graph.clusters?.length ? graph.clusters : [{ id: 'all', node_ids: graph.nodes.map((n) => n.id), domains: [] as string[] }];
  const ci = Math.max(0, clusters.findIndex((c) => c.node_ids.includes(id)));
  const column = node?.type === 'document' ? 90 : node?.type === 'revision' ? 300 : 520;
  const same = clusters[ci].node_ids.filter((nid) => graph.nodes.find((n) => n.id === nid)?.type === node?.type);
  return { x: column, y: 40 + ci * 88 + Math.max(0, same.indexOf(id)) * 22 };
}

export const CitationGraphView: React.FC = () => {
  const { user } = useAuth();
  const [graphData, setGraphData] = useState<CitationGraphData | null>(null);
  const [answers, setAnswers] = useState<RagAnswer[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedAnswer, setSelectedAnswer] = useState<RagAnswer | null>(null);
  const [advisoryReport, setAdvisoryReport] = useState<AdvisoryReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [advisoryLoading, setAdvisoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [queryText, setQueryText] = useState('');
  const [answerText, setAnswerText] = useState('');
  const [selectedRevisionId, setSelectedRevisionId] = useState('');
  const [citationExcerpt, setCitationExcerpt] = useState('');
  const [confidenceWeight, setConfidenceWeight] = useState(0.9);
  const [isPrimary, setIsPrimary] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [domainFilter, setDomainFilter] = useState('');
  const [impactFilter, setImpactFilter] = useState('');
  const [recencyFilter, setRecencyFilter] = useState('');
  const requestSeq = useRef(0);

  const fetchGraphAndAnswers = async () => {
    const seq = ++requestSeq.current;
    try {
      setLoading(true);
      setError(null);
      const [gData, aData, dData] = await Promise.all([
        api.citations.getGraph({
          domain: domainFilter.trim() || undefined,
          minImpact: impactFilter === '' ? undefined : Number(impactFilter),
          recencyDays: recencyFilter === '' ? undefined : Number(recencyFilter)
        }),
        api.citations.listAnswers(),
        api.documents.list()
      ]);
      if (seq !== requestSeq.current) return;
      setGraphData(gData);
      setAnswers(aData);
      setDocuments(dData);
    } catch (err: any) {
      if (seq !== requestSeq.current) return;
      setError(err.message || 'Failed to load graph');
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  };

  useEffect(() => { fetchGraphAndAnswers(); }, [domainFilter, impactFilter, recencyFilter]);

  const handleSelectAnswer = async (ansId: string) => {
    try {
      const detailed = await api.citations.getAnswer(ansId);
      setSelectedAnswer(detailed);
      setAdvisoryReport(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch answer');
    }
  };

  const handleGenerateAdvisory = async (ansId: string) => {
    try {
      setAdvisoryLoading(true);
      setError(null);
      const report = await api.citations.getAdvisoryReport(ansId);
      setAdvisoryReport(report);
    } catch (err: any) {
      setError(err.message || 'Advisory synthesis error');
    } finally {
      setAdvisoryLoading(false);
    }
  };

  const handleRegisterAnswer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryText.trim() || !answerText.trim() || !selectedRevisionId) return;
    try {
      setIsSubmitting(true);
      await api.citations.registerAnswer({
        query_text: queryText.trim(),
        answer_text: answerText.trim(),
        citations: [{
          revision_id: selectedRevisionId,
          citation_excerpt: citationExcerpt.trim(),
          confidence_weight: Number(confidenceWeight),
          is_primary: isPrimary
        }]
      });
      setShowRegisterModal(false);
      setQueryText(''); setAnswerText(''); setCitationExcerpt('');
      await fetchGraphAndAnswers();
    } catch (err: any) {
      setError(err.message || 'Failed to register answer');
    } finally {
      setIsSubmitting(false);
    }
  };

  const filtersActive = Boolean(domainFilter.trim() || impactFilter || recencyFilter);
  const visibleAnswerIds = new Set(
    (graphData?.nodes ?? []).filter((n) => n.type === 'answer').map((n) => n.id.replace(/^ans_/, ''))
  );
  const visibleAnswers = filtersActive ? answers.filter((a) => visibleAnswerIds.has(a.id)) : answers;

  return (
    <div className="graph-view-container">
      <div className="section-toolbar">
        <div>
          <h2>RAG Citation Dependency Graph</h2>
          <p className="section-desc">Documents, revisions, and the RAG answers that cite them.</p>
        </div>
        <button onClick={() => setShowRegisterModal(true)} disabled={user?.role === 'viewer'} className="btn-primary">
          + Index RAG Answer
        </button>
      </div>

      <form className="filter-bar" onSubmit={(e) => e.preventDefault()}>
        <input aria-label="Document domain" className="filter-select" placeholder="All domains" value={domainFilter} onChange={(e) => setDomainFilter(e.target.value)} />
        <select aria-label="Impact threshold" className="filter-select" value={impactFilter} onChange={(e) => setImpactFilter(e.target.value)}>
          <option value="">Any impact</option>
          <option value="0.25">≥ 0.25</option>
          <option value="0.7">≥ 0.70</option>
        </select>
        <select aria-label="Answer recency" className="filter-select" value={recencyFilter} onChange={(e) => setRecencyFilter(e.target.value)}>
          <option value="">Any age</option>
          <option value="7">7 days</option>
          <option value="30">30 days</option>
          <option value="90">90 days</option>
        </select>
      </form>

      {error && <div className="alert alert-error"><span>⚠️ {error}</span><button onClick={() => setError(null)} className="btn-close">×</button></div>}

      {loading ? (
        <div className="card loading-card"><div className="spinner"></div><p>Constructing graph...</p></div>
      ) : (
        <div className="graph-layout">
          <div className="graph-canvas-card card">
            <div className="canvas-header">
              <h3>Topology Visualization</h3>
              <div className="graph-legend">
                <span className="legend-item"><span className="dot dot-doc"></span> Doc</span>
                <span className="legend-item"><span className="dot dot-rev"></span> Rev</span>
                <span className="legend-item"><span className="dot dot-ans"></span> Answer</span>
              </div>
            </div>

            <div className="svg-container">
              {graphData && graphData.nodes.length === 0 ? (
                <div className="empty-state"><p>No matching clusters.</p></div>
              ) : graphData && (
                <svg width="100%" height={Math.max(220, (graphData.clusters?.length || 1) * 88 + 16)} viewBox={`0 0 650 ${Math.max(220, (graphData.clusters?.length || 1) * 88 + 16)}`} className="topology-svg">
                  <defs>
                    <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                      <polygon points="0 0, 6 3, 0 6" fill="#94a3b8" />
                    </marker>
                  </defs>
                  {(graphData.clusters ?? []).map((c, i) => (
                    <text key={c.id} x="8" y={16 + i * 88} className="node-text">Cluster {i + 1}{c.domains.length ? ` · ${c.domains.join(', ')}` : ''}</text>
                  ))}
                  {graphData.links.map((l, i) => {
                    const a = nodeSpot(graphData, l.source);
                    const b = nodeSpot(graphData, l.target);
                    return <line key={`l-${i}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={l.is_primary ? '#38bdf8' : '#94a3b8'} strokeWidth={l.is_primary ? 2.2 : 1.2} markerEnd="url(#arrow)" />;
                  })}
                  {graphData.nodes.map((n) => {
                    const p = nodeSpot(graphData, n.id);
                    const fill = n.type === 'document' ? '#0284c7' : (n.status === 'fresh' ? '#10b981' : n.status === 'stale' ? '#f59e0b' : '#ef4444');
                    return (
                      <g key={n.id} className="node-group" onClick={() => n.type === 'answer' && handleSelectAnswer(n.id.replace('ans_', ''))}>
                        <circle cx={p.x} cy={p.y} r="12" fill={fill} />
                        <text x={p.x} y={p.y + 20} textAnchor="middle" className="node-text">{n.label.slice(0, 16)}</text>
                      </g>
                    );
                  })}
                </svg>
              )}
            </div>
            <div className="topology-stats">
              <span>{graphData?.summary.total_documents} Documents</span>
              <span>{graphData?.summary.total_revisions} Revisions</span>
              <span>{graphData?.summary.total_answers} Answers</span>
              <span>{graphData?.summary.total_citations} Citations</span>
              <span>{graphData?.summary.cluster_count ?? graphData?.clusters?.length ?? (graphData && graphData.nodes.length ? 1 : 0)} Clusters</span>
            </div>
          </div>

          <div className="graph-answers-pane card">
            <h3>Registered Answers</h3>
            <div className="answers-list" style={{ maxHeight: '200px', overflowY: 'auto', marginBottom: '1rem' }}>
              {visibleAnswers.length === 0 ? <p className="section-desc">No answers in view.</p> : visibleAnswers.map((a) => (
                <div key={a.id} className={`answer-item ${selectedAnswer?.id === a.id ? 'active' : ''}`} onClick={() => handleSelectAnswer(a.id)}>
                  <div className="ans-query">{a.query_text}</div>
                  <div className="ans-meta">
                    <span className={`status-pill status-${a.freshness_status}`}>{a.freshness_status.toUpperCase()}</span>
                    <span>Impact: {(a.impact_score * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>

            {selectedAnswer && (
              <div className="selected-answer-details">
                <h4>Inspecting: {selectedAnswer.query_text.slice(0, 45)}...</h4>
                <div className="quote-box">{selectedAnswer.answer_text}</div>
                <div style={{ margin: '0.75rem 0' }}>
                  <button onClick={() => handleGenerateAdvisory(selectedAnswer.id)} disabled={advisoryLoading || user?.role === 'viewer'} className="btn-primary btn-sm">
                    {advisoryLoading ? 'Synthesizing...' : 'Generate Advisory Report'}
                  </button>
                </div>
                {advisoryReport && (
                  <div className="advisory-result-card">
                    <div className="advisory-header">
                      <span className="badge badge-advisory">ADVISORY REPORT</span>
                      <span className="provider-info">{advisoryReport.provider_used} ({advisoryReport.model_used})</span>
                    </div>
                    <p className="advisory-summary">{advisoryReport.summary}</p>
                    <div className="advisory-rec"><strong>Recommendation:</strong> {advisoryReport.recommendation}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {showRegisterModal && (
        <div className="modal-backdrop">
          <div className="modal-box">
            <div className="modal-header"><h3>Index Tracked RAG Answer</h3><button onClick={() => setShowRegisterModal(false)} className="btn-close">×</button></div>
            <form onSubmit={handleRegisterAnswer}>
              <div className="form-group"><label>Query</label><input type="text" required value={queryText} onChange={(e) => setQueryText(e.target.value)} placeholder="User query" /></div>
              <div className="form-group"><label>Answer Text</label><textarea rows={3} required value={answerText} onChange={(e) => setAnswerText(e.target.value)} placeholder="Model answer..." /></div>
              <div className="form-group"><label>Source Revision</label>
                <select required value={selectedRevisionId} onChange={(e) => setSelectedRevisionId(e.target.value)}>
                  <option value="">Select Document Revision...</option>
                  {documents.map((d) => d.revisions?.map((r) => (
                    <option key={r.id} value={r.id}>{d.title} (v{r.version} - {r.status})</option>
                  )))}
                </select>
              </div>
              <div className="form-row">
                <div className="form-group"><label>Confidence (0-1)</label><input type="number" step="0.1" min="0" max="1" value={confidenceWeight} onChange={(e) => setConfidenceWeight(Number(e.target.value))} /></div>
                <div className="form-group checkbox-group" style={{ display: 'flex', alignItems: 'center' }}>
                  <label><input type="checkbox" checked={isPrimary} onChange={(e) => setIsPrimary(e.target.checked)} /> Primary Citation</label>
                </div>
              </div>
              <div className="form-group"><label>Excerpt</label><input type="text" value={citationExcerpt} onChange={(e) => setCitationExcerpt(e.target.value)} placeholder="Quoted excerpt" /></div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowRegisterModal(false)} className="btn-secondary">Cancel</button>
                <button type="submit" disabled={isSubmitting} className="btn-primary">{isSubmitting ? 'Indexing...' : 'Index Answer'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
