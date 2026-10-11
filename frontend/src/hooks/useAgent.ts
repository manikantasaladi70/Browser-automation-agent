import { useState, useCallback, useRef, useEffect } from 'react'
import { createTask, connectWS, AgentEvent } from '../lib/api'

export interface AgentState {
  taskId: string | null
  status: 'idle' | 'queued' | 'running' | 'done' | 'error'
  events: AgentEvent[]
  latestScreenshot: string | null
  result: string | null
  error: string | null
  planCount: number
  stepCount: number
}

const INITIAL: AgentState = {
  taskId: null,
  status: 'idle',
  events: [],
  latestScreenshot: null,
  result: null,
  error: null,
  planCount: 0,
  stepCount: 0,
}

export function useAgent() {
  const [state, setState] = useState<AgentState>(INITIAL)
  const wsRef = useRef<WebSocket | null>(null)

  const reset = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
    setState(INITIAL)
  }, [])

  const run = useCallback(async (task: string, url?: string) => {
    reset()
    setState(s => ({ ...s, status: 'queued', taskId: null, events: [], result: null, error: null }))

    try {
      const { task_id } = await createTask(task, url)
      setState(s => ({ ...s, taskId: task_id, status: 'queued' }))

      const ws = connectWS(task_id, (event: AgentEvent) => {
        setState(s => {
          const events = [...s.events, event]
          let patch: Partial<AgentState> = { events }

          if (event.type === 'status') patch.status = event.status as any
          if (event.type === 'screenshot' && event.screenshot) patch.latestScreenshot = event.screenshot
          if (event.type === 'plan') patch.planCount = event.count || 0
          if (event.type === 'step') patch.stepCount = s.stepCount + 1
          if (event.type === 'done') {
            patch.status = 'done'
            patch.result = event.result || null
            if (event.screenshot) patch.latestScreenshot = event.screenshot
          }
          if (event.type === 'error') {
            patch.status = 'error'
            patch.error = event.message || 'Unknown error'
          }

          return { ...s, ...patch }
        })
      })

      wsRef.current = ws
    } catch (e: any) {
      setState(s => ({ ...s, status: 'error', error: e.message }))
    }
  }, [reset])

  // cleanup on unmount
  useEffect(() => () => { wsRef.current?.close() }, [])

  return { state, run, reset }
}
