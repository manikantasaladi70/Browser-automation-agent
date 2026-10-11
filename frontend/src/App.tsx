import React, { useState, useEffect, useRef } from 'react'
import { Bot, Github, Zap, Volume2, VolumeX } from 'lucide-react'
import TaskInput from './components/TaskInput'
import LiveFeed from './components/LiveFeed'
import TaskHistory from './components/TaskHistory'
import { useAgent } from './hooks/useAgent'
import { useVoice } from './hooks/useVoice'
import { Task, AgentEvent } from './lib/api'
import './App.css'

function voiceText(event: AgentEvent): string | null {
  if (event.type === 'plan') return `Agent planned ${event.count} actions`
  if (event.type === 'step') return event.description || null
  if (event.type === 'done') return `Task complete. ${event.result || ''}`
  if (event.type === 'error') return `Error: ${event.message}`
  if (event.type === 'retry') return `Retrying, attempt ${event.attempt}`
  if (event.type === 'extract') return `Extracted: ${event.description}`
  return null
}

export default function App() {
  const { state, run, reset } = useAgent()
  const { speak, stop, setEnabled } = useVoice()
  const [historyRefresh, setHistoryRefresh] = useState(0)
  const [voiceOn, setVoiceOn] = useState(true)
  const prevEventsLen = useRef(0)

  // Speak new events as they arrive
  useEffect(() => {
    const events = state.events
    if (events.length > prevEventsLen.current) {
      const newEvents = events.slice(prevEventsLen.current)
      newEvents.forEach(e => {
        const text = voiceText(e)
        if (text) speak(text)
      })
    }
    prevEventsLen.current = events.length
  }, [state.events, speak])

  // Stop voice on reset
  const handleReset = () => {
    stop()
    prevEventsLen.current = 0
    reset()
  }

  const handleRun = async (task: string, url?: string) => {
    stop()
    prevEventsLen.current = 0
    speak('Starting task: ' + task.slice(0, 60))
    await run(task, url)
    setTimeout(() => setHistoryRefresh(n => n + 1), 2000)
  }

  const toggleVoice = () => {
    const next = !voiceOn
    setVoiceOn(next)
    setEnabled(next)
    if (next) speak('Voice enabled')
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <Bot size={20} />
            <span className="logo-text">BrowseAI</span>
            <span className="logo-badge">AGENT</span>
          </div>
          <span className="header-tagline">Plain English → Real browser actions</span>
        </div>
        <div className="header-right">
          <div className="status-indicator">
            <span className={`status-dot ${state.status === 'running' ? 'running' : state.status === 'done' ? 'done' : state.status === 'error' ? 'error' : 'idle'}`} />
            <span className="status-text">
              {state.status === 'idle' ? 'Ready' : state.status === 'queued' ? 'Queued' : state.status === 'running' ? 'Running' : state.status === 'done' ? 'Done' : 'Error'}
            </span>
          </div>
          {state.status !== 'idle' && (
            <button className="reset-btn" onClick={handleReset}>New task</button>
          )}
          {/* Voice toggle */}
          <button
            className={`voice-btn ${voiceOn ? 'active' : ''}`}
            onClick={toggleVoice}
            title={voiceOn ? 'Mute voice' : 'Enable voice'}
          >
            {voiceOn ? <Volume2 size={15} /> : <VolumeX size={15} />}
            <span>{voiceOn ? 'Voice on' : 'Voice off'}</span>
          </button>
          <a href="https://github.com" className="github-link" target="_blank" rel="noreferrer">
            <Github size={16} />
          </a>
        </div>
      </header>

      <main className="main">
        <aside className="sidebar">
          <TaskHistory
            currentTaskId={state.taskId}
            onSelect={(_task: Task) => {}}
            refreshTrigger={historyRefresh}
          />
        </aside>

        <div className="center">
          <TaskInput
            onSubmit={handleRun}
            disabled={state.status === 'queued' || state.status === 'running'}
          />

          {state.status !== 'idle' && (
            <div className="stats-bar">
              <div className="stat">
                <Zap size={12} />
                <span>{state.planCount} planned actions</span>
              </div>
              <div className="stat">
                <span>{state.stepCount} executed</span>
              </div>
              {state.taskId && (
                <div className="stat mono">
                  <span>ID: {state.taskId.slice(0, 8)}…</span>
                </div>
              )}
              {voiceOn && state.status === 'running' && (
                <div className="stat" style={{marginLeft: 'auto', color: 'var(--accent)'}}>
                  <Volume2 size={12} />
                  <span>Speaking steps</span>
                </div>
              )}
            </div>
          )}

          <LiveFeed state={state} />
        </div>
      </main>
    </div>
  )
}