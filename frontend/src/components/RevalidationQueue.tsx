import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { RevalidationTask } from '../types';
import { useAuth } from '../context/AuthContext';

export const RevalidationQueue: React.FC = () => {
  const { user } = useAuth();
  const [tasks, setTasks] = useState<RevalidationTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [updatingTaskId, setUpdatingTaskId] = useState<string | null>(null);

  const fetchTasks = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.revalidation.listTasks(statusFilter || undefined, priorityFilter || undefined);
      setTasks(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load tasks');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTasks(); }, [statusFilter, priorityFilter]);

  const handleUpdateStatus = async (taskId: string, newStatus: string) => {
    try {
      setUpdatingTaskId(taskId);
      await api.revalidation.updateTaskStatus(taskId, newStatus, `Updated by ${user?.username}`);
      await fetchTasks();
    } catch (err: any) {
      setError(err.message || 'Failed to update task');
    } finally {
      setUpdatingTaskId(null);
    }
  };

  return (
    <div className="queue-container">
      <div className="section-toolbar">
        <div>
          <h2>Revalidation Task Queue</h2>
          <p className="section-desc">Prioritized re-evaluation queue targeting stale and drifted RAG answers.</p>
        </div>
        <button onClick={() => window.open(api.revalidation.exportCsvUrl, '_blank')} className="btn-secondary">
          📥 Export CSV
        </button>
      </div>

      <div className="filter-bar">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="filter-select">
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="dismissed">Dismissed</option>
        </select>
        <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)} className="filter-select">
          <option value="">All Priorities</option>
          <option value="high">High Priority</option>
          <option value="medium">Medium Priority</option>
          <option value="low">Low Priority</option>
        </select>
      </div>

      {error && <div className="alert alert-error"><span>⚠️ {error}</span><button onClick={() => setError(null)} className="btn-close">×</button></div>}

      {loading ? (
        <div className="card loading-card"><div className="spinner"></div><p>Loading queue...</p></div>
      ) : tasks.length === 0 ? (
        <div className="empty-state card"><p>No tasks found.</p></div>
      ) : (
        <div className="card">
          <table className="data-table">
            <thead>
              <tr><th>Priority</th><th>Query & Answer</th><th>Reason</th><th>Status</th><th>Scheduled</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td>
                    <span className={`priority-pill priority-${task.priority_level}`}>
                      {task.priority_level.toUpperCase()} ({(task.priority_score * 100).toFixed(0)}%)
                    </span>
                  </td>
                  <td className="query-cell">
                    <strong>{task.answer?.query_text || `ID: ${task.answer_id}`}</strong>
                    {task.answer?.answer_text && <div className="answer-snippet">{task.answer.answer_text}</div>}
                  </td>
                  <td>{task.reason}</td>
                  <td><span className={`status-pill status-${task.status}`}>{task.status.replace('_', ' ').toUpperCase()}</span></td>
                  <td className="date-cell">{new Date(task.scheduled_at).toLocaleDateString()}</td>
                  <td>
                    {task.status === 'pending' && (
                      <button onClick={() => handleUpdateStatus(task.id, 'in_progress')} disabled={updatingTaskId === task.id || user?.role === 'viewer'} className="btn-sm btn-primary">
                        Start
                      </button>
                    )}
                    {task.status === 'in_progress' && (
                      <button onClick={() => handleUpdateStatus(task.id, 'completed')} disabled={updatingTaskId === task.id || user?.role === 'viewer'} className="btn-sm btn-success">
                        Resolve
                      </button>
                    )}
                    {['pending', 'in_progress'].includes(task.status) && (
                      <button onClick={() => handleUpdateStatus(task.id, 'dismissed')} disabled={updatingTaskId === task.id || user?.role === 'viewer'} className="btn-sm btn-secondary ml-2">
                        Dismiss
                      </button>
                    )}
                    {task.status === 'completed' && <span className="text-muted">Resolved</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
