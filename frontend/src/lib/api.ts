export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
export const WS_URL = API_URL.replace(/^http/, 'ws')

export interface Task {
  id: string
  task: string
  url: string
  status: 'queued' | 'running' | 'done' | 'error'
  created_at: number
  steps: AgentEvent[]
  result: string | null
  screenshot: string | null
}

export interface AgentEvent {
  type: 'status' | 'plan' | 'step' | 'screenshot' | 'extract' | 'step_error' | 'retry' | 'done' | 'error'
  action?: string
  description?: string
  screenshot?: string | null
  actions?: any[]
  count?: number
  data?: any[]
  error?: string
  message?: string
  result?: string
  status?: string
  attempt?: number
  hint?: string
}

export async function createTask(task: string, url?: string): Promise<{ task_id: string }> {
  const res = await fetch(`${API_URL}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task, url: url || null }),
  })
  if (!res.ok) throw new Error('Failed to create task')
  return res.json()
}

export async function fetchTasks(): Promise<Task[]> {
  const res = await fetch(`${API_URL}/tasks`)
  if (!res.ok) return []
  const data = await res.json()
  return data.tasks || []
}

export async function fetchTask(id: string): Promise<Task | null> {
  const res = await fetch(`${API_URL}/tasks/${id}`)
  if (!res.ok) return null
  return res.json()
}

export async function deleteTask(id: string): Promise<void> {
  await fetch(`${API_URL}/tasks/${id}`, { method: 'DELETE' })
}

export function connectWS(taskId: string, onEvent: (e: AgentEvent) => void): WebSocket {
  const ws = new WebSocket(`${WS_URL}/ws/${taskId}`)
  ws.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data)
      onEvent(data)
    } catch {}
  }
  return ws
}
