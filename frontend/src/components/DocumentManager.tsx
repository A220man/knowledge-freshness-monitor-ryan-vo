import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Document } from '../types';
import { useAuth } from '../context/AuthContext';

export const DocumentManager: React.FC = () => {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showRevisionModal, setShowRevisionModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newSourceUri, setNewSourceUri] = useState('');
  const [newCategory, setNewCategory] = useState('knowledge_base');
  const [newRetention, setNewRetention] = useState(90);
  const [newContent, setNewContent] = useState('');
  const [revisionContent, setRevisionContent] = useState('');
  const [revisionDays, setRevisionDays] = useState<number | undefined>(undefined);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.documents.list(categoryFilter || undefined);
      setDocuments(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDocuments(); }, [categoryFilter]);

  const handleSelectDoc = async (docId: string) => {
    try {
      const detailed = await api.documents.get(docId);
      setSelectedDoc(detailed);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch document details');
    }
  };

  const handleCreateDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newContent.trim()) return;
    try {
      setIsSubmitting(true);
      await api.documents.create({
        title: newTitle.trim(),
        source_uri: newSourceUri.trim() || 'https://internal.docs',
        category: newCategory,
        retention_days: Number(newRetention),
        initial_content: newContent.trim()
      });
      setShowCreateModal(false);
      setNewTitle(''); setNewSourceUri(''); setNewContent('');
      await fetchDocuments();
    } catch (err: any) {
      setError(err.message || 'Failed to create document');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAddRevision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDoc || !revisionContent.trim()) return;
    try {
      setIsSubmitting(true);
      await api.documents.addRevision(
        selectedDoc.id,
        revisionContent.trim(),
        revisionDays ? Number(revisionDays) : undefined
      );
      setShowRevisionModal(false);
      setRevisionContent(''); setRevisionDays(undefined);
      await handleSelectDoc(selectedDoc.id);
      await fetchDocuments();
    } catch (err: any) {
      setError(err.message || 'Failed to submit revision');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    if (!window.confirm('Delete document and all revisions?')) return;
    try {
      await api.documents.delete(docId);
      if (selectedDoc?.id === docId) setSelectedDoc(null);
      await fetchDocuments();
    } catch (err: any) {
      setError(err.message || 'Failed to delete document');
    }
  };

  const filteredDocs = documents.filter((doc) =>
    doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    doc.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="doc-manager-container">
      <div className="section-toolbar">
        <div>
          <h2>Monitored Knowledge Documents</h2>
          <p className="section-desc">Manage versioned documents, inspect chunk indexing, and track drift.</p>
        </div>
        <button onClick={() => setShowCreateModal(true)} disabled={user?.role === 'viewer'} className="btn-primary">
          + Ingest Document
        </button>
      </div>

      <div className="filter-bar">
        <input type="text" placeholder="Search by title or category..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="search-input" />
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="category-filter">
          <option value="">All Categories</option>
          <option value="knowledge_base">Knowledge Base</option>
          <option value="api_spec">API Specs</option>
          <option value="compliance">Compliance</option>
          <option value="policy">Policy</option>
        </select>
      </div>

      {error && <div className="alert alert-error"><span>⚠️ {error}</span><button onClick={() => setError(null)} className="btn-close">×</button></div>}

      {loading ? (
        <div className="card loading-card"><div className="spinner"></div><p>Loading documents...</p></div>
      ) : filteredDocs.length === 0 ? (
        <div className="empty-state card"><p>No documents found matching your criteria.</p></div>
      ) : (
        <div className="docs-layout">
          <div className="docs-list card">
            <table className="data-table">
              <thead><tr><th>Title</th><th>Category</th><th>Retention</th><th>Updated</th><th>Actions</th></tr></thead>
              <tbody>
                {filteredDocs.map((doc) => (
                  <tr key={doc.id} className={selectedDoc?.id === doc.id ? 'row-selected' : ''} onClick={() => handleSelectDoc(doc.id)}>
                    <td><div className="doc-title">{doc.title}</div><div className="doc-uri">{doc.source_uri}</div></td>
                    <td><span className="category-pill">{doc.category}</span></td>
                    <td>{doc.retention_days}d</td>
                    <td className="date-cell">{new Date(doc.updated_at).toLocaleDateString()}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <button onClick={() => handleSelectDoc(doc.id)} className="btn-sm btn-secondary">Inspect</button>
                      {user?.role === 'admin' && <button onClick={() => handleDeleteDocument(doc.id)} className="btn-sm btn-danger ml-2">Delete</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedDoc && (
            <div className="doc-detail-pane card">
              <div className="detail-header">
                <div>
                  <h3>{selectedDoc.title}</h3>
                  <div className="detail-meta">Category: <strong>{selectedDoc.category}</strong> | Retention: <strong>{selectedDoc.retention_days}d</strong></div>
                </div>
                <button onClick={() => { setRevisionContent(selectedDoc.revisions?.[0]?.text_content || ''); setShowRevisionModal(true); }} disabled={user?.role === 'viewer'} className="btn-primary btn-sm">
                  + Add Revision
                </button>
              </div>
              <h4 style={{ margin: '1rem 0 0.5rem' }}>Revision History & Drift</h4>
              <div className="revision-timeline">
                {selectedDoc.revisions?.map((rev) => (
                  <div key={rev.id} className="revision-item">
                    <div className="revision-header">
                      <span className="rev-badge">v{rev.version}</span>
                      <span className={`status-pill status-${rev.status}`}>{rev.status.toUpperCase()}</span>
                      <span className="drift-badge">Drift: {(rev.drift_score * 100).toFixed(1)}%</span>
                      <span className="timestamp">{new Date(rev.created_at).toLocaleString()}</span>
                    </div>
                    <div className="rev-content-preview">{rev.text_content}</div>
                    <div className="rev-footer">
                      <span>Chunks: {rev.chunk_count}</span>
                      <span>Hash: {rev.content_hash.slice(0, 10)}...</span>
                      {rev.expiration_timestamp && <span>Expires: {new Date(rev.expiration_timestamp).toLocaleDateString()}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {showCreateModal && (
        <div className="modal-backdrop">
          <div className="modal-box">
            <div className="modal-header"><h3>Ingest Knowledge Document</h3><button onClick={() => setShowCreateModal(false)} className="btn-close">×</button></div>
            <form onSubmit={handleCreateDocument}>
              <div className="form-group"><label>Title</label><input type="text" required value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Document title" /></div>
              <div className="form-row">
                <div className="form-group"><label>Source URI</label><input type="text" required value={newSourceUri} onChange={(e) => setNewSourceUri(e.target.value)} placeholder="https://..." /></div>
                <div className="form-group"><label>Category</label><select value={newCategory} onChange={(e) => setNewCategory(e.target.value)}><option value="knowledge_base">Knowledge Base</option><option value="api_spec">API Specs</option><option value="compliance">Compliance</option><option value="policy">Policy</option></select></div>
                <div className="form-group"><label>Retention (Days)</label><input type="number" min="1" max="3650" value={newRetention} onChange={(e) => setNewRetention(Number(e.target.value))} /></div>
              </div>
              <div className="form-group"><label>Content Text</label><textarea rows={6} required value={newContent} onChange={(e) => setNewContent(e.target.value)} placeholder="Document text..." /></div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowCreateModal(false)} className="btn-secondary">Cancel</button>
                <button type="submit" disabled={isSubmitting} className="btn-primary">{isSubmitting ? 'Ingesting...' : 'Ingest Document'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showRevisionModal && selectedDoc && (
        <div className="modal-backdrop">
          <div className="modal-box">
            <div className="modal-header"><h3>Submit Revision: {selectedDoc.title}</h3><button onClick={() => setShowRevisionModal(false)} className="btn-close">×</button></div>
            <form onSubmit={handleAddRevision}>
              <div className="form-group"><label>Revised Content</label><textarea rows={7} required value={revisionContent} onChange={(e) => setRevisionContent(e.target.value)} /></div>
              <div className="form-group"><label>Expiration Override (Days, optional)</label><input type="number" placeholder={`Default: ${selectedDoc.retention_days}`} value={revisionDays || ''} onChange={(e) => setRevisionDays(e.target.value ? Number(e.target.value) : undefined)} /></div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowRevisionModal(false)} className="btn-secondary">Cancel</button>
                <button type="submit" disabled={isSubmitting} className="btn-primary">{isSubmitting ? 'Evaluating...' : 'Commit Revision'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
