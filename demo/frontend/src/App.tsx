import { useState, useEffect, useRef } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'

interface Memory {
  id: string
  text: string
  durability: string
  confidence: number
  created_at: string
  superseded_by: string | null
}

interface Message {
  role: 'user' | 'assistant'
  content: string
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [memories, setMemories] = useState<Memory[]>([])
  const [allMemories, setAllMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const fetchMemories = async () => {
    try {
      const [current, history] = await Promise.all([
        fetch(`${API_URL}/memories`).then(r => r.json()),
        fetch(`${API_URL}/memories/history`).then(r => r.json()),
      ])
      setMemories(current)
      setAllMemories(history)
    } catch (e) {
      console.error('Failed to fetch memories:', e)
    }
  }

  useEffect(() => {
    fetchMemories()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }])
      fetchMemories()
    } catch (e) {
      console.error('Chat error:', e)
      setMessages(prev => [...prev, { role: 'assistant', content: 'Error: Could not reach the server.' }])
    } finally {
      setLoading(false)
    }
  }

  const clearMemories = async () => {
    if (!confirm('Clear all memories?')) return
    await fetch(`${API_URL}/memories`, { method: 'DELETE' })
    fetchMemories()
  }

  const getDurabilityColor = (d: string) => {
    switch (d) {
      case 'core': return 'bg-purple-600'
      case 'situational': return 'bg-blue-600'
      case 'episodic': return 'bg-gray-600'
      default: return 'bg-gray-600'
    }
  }

  const supersededMemories = allMemories.filter(m => m.superseded_by)
  const displayMemories = showHistory ? allMemories : memories

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🧠</span>
          <h1 className="text-xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
            engram-ai demo
          </h1>
        </div>
        <button
          onClick={clearMemories}
          className="px-3 py-1.5 text-sm bg-red-600/20 text-red-400 rounded hover:bg-red-600/30 transition"
        >
          Clear Memories
        </button>
      </header>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat panel */}
        <div className="flex-1 flex flex-col">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="text-center text-gray-500 mt-8">
                <p className="text-lg">👋 Start a conversation!</p>
                <p className="text-sm mt-2">Tell me about yourself and I'll remember it.</p>
              </div>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[70%] rounded-lg px-4 py-2 ${
                    msg.role === 'user'
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-800 text-gray-100'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-800 rounded-lg px-4 py-2 text-gray-400">
                  Thinking...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="border-t border-gray-700 p-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                placeholder="Type a message..."
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 focus:outline-none focus:border-purple-500"
              />
              <button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                className="px-4 py-2 bg-purple-600 rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                Send
              </button>
            </div>
          </div>
        </div>

        {/* Memory panel */}
        <div className="w-80 border-l border-gray-700 flex flex-col bg-gray-850">
          <div className="p-4 border-b border-gray-700 flex items-center justify-between">
            <h2 className="font-semibold flex items-center gap-2">
              🧠 Memories
              <span className="text-xs bg-gray-700 px-2 py-0.5 rounded-full">
                {memories.length}
              </span>
            </h2>
            <button
              onClick={() => setShowHistory(!showHistory)}
              className={`text-xs px-2 py-1 rounded ${
                showHistory ? 'bg-purple-600' : 'bg-gray-700'
              }`}
            >
              {showHistory ? 'Current' : 'History'}
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {displayMemories.length === 0 && (
              <p className="text-gray-500 text-sm text-center">No memories yet</p>
            )}
            {displayMemories.map((mem) => (
              <div
                key={mem.id}
                className={`rounded-lg p-3 text-sm ${
                  mem.superseded_by ? 'bg-gray-800/50 opacity-60' : 'bg-gray-800'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className={mem.superseded_by ? 'line-through text-gray-500' : ''}>
                    {mem.text}
                  </p>
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${getDurabilityColor(mem.durability)}`}>
                    {mem.durability}
                  </span>
                  <span className="text-xs text-gray-500">
                    {Math.round(mem.confidence * 100)}%
                  </span>
                  {mem.superseded_by && (
                    <span className="text-xs text-red-400">superseded</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {supersededMemories.length > 0 && !showHistory && (
            <div className="p-4 border-t border-gray-700">
              <p className="text-xs text-gray-500">
                {supersededMemories.length} superseded memor{supersededMemories.length === 1 ? 'y' : 'ies'} hidden
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default App
