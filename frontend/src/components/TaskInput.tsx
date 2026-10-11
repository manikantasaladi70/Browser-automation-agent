import React, { useState, useRef } from 'react'
import { Send, Globe, ChevronDown, ChevronUp, Sparkles } from 'lucide-react'

interface Props {
  onSubmit: (task: string, url?: string) => void
  disabled: boolean
}

const EXAMPLES = [
  { label: 'Scrape table', task: 'Go to https://en.wikipedia.org/wiki/List_of_countries_by_population and extract the top 10 countries and their populations from the table' },
  { label: 'Fill form', task: 'Go to https://httpbin.org/forms/post and fill the customer name as "John Doe", phone as "9876543210", and email as "john@example.com"' },
  { label: 'Screenshot page', task: 'Navigate to https://news.ycombinator.com and take a screenshot of the top 5 stories' },
  { label: 'Extract links', task: 'Go to https://github.com/trending and extract the names and descriptions of the top 5 trending repositories' },
]

export default function TaskInput({ onSubmit, disabled }: Props) {
  const [task, setTask] = useState('')
  const [url, setUrl] = useState('')
  const [showUrl, setShowUrl] = useState(false)
  const textRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = () => {
    const t = task.trim()
    if (!t || disabled) return
    onSubmit(t, url.trim() || undefined)
    setTask('')
    setUrl('')
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit()
  }

  const useExample = (ex: typeof EXAMPLES[0]) => {
    setTask(ex.task)
    textRef.current?.focus()
  }

  return (
    <div className="input-card">
      <div className="input-header">
        <span className="input-label"><Sparkles size={13} style={{marginRight: 6, verticalAlign: 'middle'}} />Describe what to do</span>
        <button className="url-toggle" onClick={() => setShowUrl(v => !v)}>
          <Globe size={13} />
          {showUrl ? 'Hide URL' : 'Add start URL'}
          {showUrl ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {showUrl && (
        <input
          className="url-input"
          type="url"
          placeholder="https://example.com (optional — agent can navigate itself)"
          value={url}
          onChange={e => setUrl(e.target.value)}
        />
      )}

      <div className="textarea-wrap">
        <textarea
          ref={textRef}
          className="task-textarea"
          placeholder={`Try: "Go to wikipedia.org and extract the 10 most spoken languages"\nOr: "Fill the contact form at example.com with test data"`}
          value={task}
          onChange={e => setTask(e.target.value)}
          onKeyDown={handleKey}
          rows={4}
          disabled={disabled}
        />
        <button
          className={`run-btn ${disabled || !task.trim() ? 'disabled' : ''}`}
          onClick={handleSubmit}
          disabled={disabled || !task.trim()}
        >
          <Send size={15} />
          {disabled ? 'Running…' : 'Run agent'}
        </button>
      </div>

      <div className="examples-row">
        <span className="examples-label">Quick start:</span>
        {EXAMPLES.map(ex => (
          <button key={ex.label} className="example-chip" onClick={() => useExample(ex)}>
            {ex.label}
          </button>
        ))}
      </div>
    </div>
  )
}
