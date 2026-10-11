// Voice narration hook using browser's built-in Web Speech API (free, no API key)
import { useCallback, useRef } from 'react'

export function useVoice() {
  const enabledRef = useRef(true)
  const queueRef = useRef<string[]>([])
  const speakingRef = useRef(false)

  const processQueue = useCallback(() => {
    if (speakingRef.current || queueRef.current.length === 0) return
    const text = queueRef.current.shift()!
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 1.05
    utterance.pitch = 1
    utterance.volume = 1
    // Pick a good English voice if available
    const voices = window.speechSynthesis.getVoices()
    const preferred = voices.find(v =>
      v.lang.startsWith('en') && (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Neural'))
    ) || voices.find(v => v.lang.startsWith('en'))
    if (preferred) utterance.voice = preferred
    utterance.onstart = () => { speakingRef.current = true }
    utterance.onend = () => { speakingRef.current = false; processQueue() }
    utterance.onerror = () => { speakingRef.current = false; processQueue() }
    window.speechSynthesis.speak(utterance)
  }, [])

  const speak = useCallback((text: string) => {
    if (!enabledRef.current || !('speechSynthesis' in window)) return
    queueRef.current.push(text)
    processQueue()
  }, [processQueue])

  const stop = useCallback(() => {
    window.speechSynthesis.cancel()
    queueRef.current = []
    speakingRef.current = false
  }, [])

  const setEnabled = useCallback((val: boolean) => {
    enabledRef.current = val
    if (!val) stop()
  }, [stop])

  return { speak, stop, setEnabled }
}
