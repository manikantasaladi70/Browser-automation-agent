import React, { useEffect, useRef } from 'react'
import { Monitor, CheckCircle, XCircle, Loader, AlertCircle, RefreshCw, Database, Navigation, MousePointer, Type, Scroll, Camera } from 'lucide-react'
import { AgentEvent, AgentState } from '../hooks/useAgent'

interface Props {
  state: AgentState
}

function StepIcon({ type, action }: { type: string; action?: string }) {
  const s = { size: 13 }
  if (type === 'step') {
    if (action === 'navigate') return <Navigation {...s} />
    if (action === 'click') return <MousePointer {...s} />
    if (action === 'type') return <Type {...s} />
    if (action === 'scroll') return <Scroll {...s} />
    return <Monitor {...s} />
  }
  if (type === 'screenshot') return <Camera {...s} />
  if (type === 'extract') return <Database {...s} />
  if (type === 'plan') return <Loader {...s} />
  if (type === 'retry') return <RefreshCw {...s} />
  if (type === 'step_error') return <AlertCircle {...s} />
  if (type === 'done') return <CheckCircle {...s} />
  if (type === 'error') return <XCircle {...s} />
  return <Monitor {...s} />
}

function stepColor(event: AgentEvent): string {
  if (event.type === 'done') return 'step-done'
  if (event.type === 'error' || event.type === 'step_error') return 'step-error'
  if (event.type === 'retry') return 'step-warning'
  if (event.type === 'plan') return 'step-plan'
  if (event.type === 'extract') return 'step-extract'
  return 'step-default'
}

function stepLabel(event: AgentEvent): string {
  if (event.type === 'status') return `Status: ${event.status}`
  if (event.type === 'plan') return `Agent planned ${event.count} action${event.count !== 1 ? 's' : ''}`
  if (event.type === 'step') return event.description || event.action || 'Action'
  if (event.type === 'screenshot') return event.description || 'Screenshot captured'
  if (event.type === 'extract') return `Extracted: ${event.description}`
  if (event.type === 'step_error') return `Failed: ${event.error}`
  if (event.type === 'retry') return `Retrying (attempt ${event.attempt})…`
  if (event.type === 'done') return `Done: ${event.result}`
  if (event.type === 'error') return `Error: ${event.message}`
  return event.type
}

export default function LiveFeed({ state }: Props) {
  const logRef = useRef<HTMLDivElement>(null)
  const visibleSteps = state.events.filter(e => e.type !== 'screenshot' || !e.screenshot)

  const timelineEvents = state.events.filter(e =>
    ['plan', 'step', 'extract', 'step_error', 'retry', 'done', 'error'].includes(e.type)
  )

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [state.events])

  if (state.status === 'idle') {
    return (
      <div className="feed-empty">
        <div className="feed-empty-icon"><Monitor size={36} strokeWidth={1} /></div>
        <div className="feed-empty-title">Agent is ready</div>
        <div className="feed-empty-sub">Describe a task above and the agent will control a real browser — you'll see every action live.</div>
      </div>
    )
  }

  return (
    <div className="live-feed">
      {/* Screenshot panel */}
      <div className="screenshot-panel">
        <div className="panel-label">
          <Camera size={12} />
          Live browser view
          {state.status === 'running' && <span className="live-dot" />}
        </div>
        <div className="screenshot-frame">
          {state.latestScreenshot ? (
            <img
              src={`data:image/jpeg;base64,${state.latestScreenshot}`}
              alt="Browser screenshot"
              className="screenshot-img"
            />
          ) : (
            <div className="screenshot-placeholder">
              {state.status === 'queued' || state.status === 'running'
                ? <><Loader size={24} className="spin" /><span>Loading browser…</span></>
                : <><Monitor size={24} /><span>No screenshot yet</span></>
              }
            </div>
          )}
        </div>

        {/* Result banner */}
        {state.status === 'done' && state.result && (
          <div className="result-banner success">
            <CheckCircle size={14} />
            <span>{state.result}</span>
          </div>
        )}
        {state.status === 'error' && state.error && (
          <div className="result-banner error">
            <XCircle size={14} />
            <span>{state.error}</span>
          </div>
        )}
      </div>

      {/* Timeline */}
      <div className="timeline-panel">
        <div className="panel-label">
          <Loader size={12} className={state.status === 'running' ? 'spin' : ''} />
          Agent log
          <span className="step-count">{timelineEvents.length} events</span>
        </div>
        <div className="timeline-scroll" ref={logRef}>
          {timelineEvents.length === 0 && (
            <div className="timeline-empty">
              <Loader size={16} className="spin" />
              <span>Starting agent…</span>
            </div>
          )}
          {timelineEvents.map((event, i) => (
            <div key={i} className={`timeline-item ${stepColor(event)}`}>
              <div className="timeline-icon">
                <StepIcon type={event.type} action={event.action} />
              </div>
              <div className="timeline-content">
                <span className="timeline-label">{stepLabel(event)}</span>
                {event.type === 'extract' && event.data && event.data.length > 0 && (
                  <div className="extract-data">
                    {event.data.slice(0, 5).map((d, j) => (
                      <span key={j} className="extract-item">{String(d).slice(0, 80)}</span>
                    ))}
                    {event.data.length > 5 && <span className="extract-more">+{event.data.length - 5} more</span>}
                  </div>
                )}
                {event.type === 'plan' && event.actions && (
                  <div className="plan-actions">
                    {event.actions.map((a: any, j: number) => (
                      <span key={j} className="plan-action">{a.action}{a.description ? `: ${a.description}` : ''}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {state.status === 'running' && (
            <div className="timeline-item step-default running-pulse">
              <div className="timeline-icon"><Loader size={13} className="spin" /></div>
              <div className="timeline-content"><span className="timeline-label">Agent working…</span></div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
