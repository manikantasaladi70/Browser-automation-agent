import React, { useEffect, useState } from 'react'
import { Clock, CheckCircle, XCircle, Loader, Trash2, RefreshCw } from 'lucide-react'
import { fetchTasks, deleteTask, Task } from '../lib/api'

interface Props {
  currentTaskId: string | null
  onSelect: (task: Task) => void
  refreshTrigger: number
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'done') return <CheckCircle size={12} className="icon-done" />
  if (status === 'error') return <XCircle size={12} className="icon-error" />
  if (status === 'running') return <Loader size={12} className="spin icon-running" />
  return <Clock size={12} className="icon-queued" />
}

function timeAgo(ts: number): string {
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export default function TaskHistory({ currentTaskId, onSelect, refreshTrigger }: Props) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    const t = await fetchTasks()
    setTasks(t)
    setLoading(false)
  }

  useEffect(() => { load() }, [refreshTrigger])

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    await deleteTask(id)
    setTasks(t => t.filter(x => x.id !== id))
  }

  return (
    <div className="history-panel">
      <div className="history-header">
        <span className="history-title">History</span>
        <button className="icon-btn" onClick={load} title="Refresh">
          <RefreshCw size={13} className={loading ? 'spin' : ''} />
        </button>
      </div>

      {tasks.length === 0 && !loading && (
        <div className="history-empty">No tasks yet</div>
      )}

      <div className="history-list">
        {tasks.map(task => (
          <div
            key={task.id}
            className={`history-item ${task.id === currentTaskId ? 'active' : ''}`}
            onClick={() => onSelect(task)}
          >
            <div className="history-item-top">
              <StatusIcon status={task.status} />
              <span className="history-task">{task.task.slice(0, 60)}{task.task.length > 60 ? '…' : ''}</span>
              <button className="delete-btn" onClick={e => handleDelete(e, task.id)}>
                <Trash2 size={11} />
              </button>
            </div>
            <div className="history-meta">
              <span className={`status-badge ${task.status}`}>{task.status}</span>
              <span className="history-time">{timeAgo(task.created_at)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
