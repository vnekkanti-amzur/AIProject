import { Component, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// -- API helpers ------------------------------------------------
const BASE = '/api'

async function apiPost(path, body) {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail?.message ?? `Error ${res.status}`)
  }
  return res.json()
}

async function apiGet(path) {
  const res = await fetch(BASE + path, { credentials: 'include' })
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

async function apiPatch(path, body) {
  const res = await fetch(BASE + path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail?.message ?? `Error ${res.status}`)
  }
  return res.json()
}

async function apiDelete(path) {
  const res = await fetch(BASE + path, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail?.message ?? `Error ${res.status}`)
  }
  return res.json()
}

const listThreads = () => apiGet('/simple-chat/threads')
const createThread = (firstMessage) => apiPost('/simple-chat/threads', { first_message: firstMessage ?? null })
const renameThread = (threadId, title) => apiPatch(`/simple-chat/threads/${threadId}`, { title })
const deleteThreadApi = (threadId) => apiDelete(`/simple-chat/threads/${threadId}`)
const getThreadHistory = (threadId) => apiGet(`/simple-chat/history?thread_id=${encodeURIComponent(threadId)}`)

async function streamChat(message, onToken) {
  const res = await fetch(BASE + '/simple-chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ message }),
  })
  if (!res.ok || !res.body) throw new Error(`Request failed: ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const flush = (raw) => {
    const dataLines = []
    for (const line of raw.split('\n')) {
      if (line.startsWith('data:')) {
        // Per SSE format, remove only the optional single space after `data:`.
        const text = line.startsWith('data: ') ? line.slice(6) : line.slice(5)
        dataLines.push(text)
      }
    }
    if (dataLines.length === 0) return
    const joined = dataLines.join('\n')
    if (joined !== '[DONE]') onToken(joined)
  }

  for (;;) {
    const { value, done } = await reader.read()
    if (done) { if (buffer.trim()) flush(buffer); break }
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    parts.forEach(flush)
  }
}

async function streamChatForThread(threadId, message, onToken) {
  const res = await fetch(BASE + '/simple-chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ message, thread_id: threadId }),
  })
  if (!res.ok || !res.body) throw new Error(`Request failed: ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const flush = (raw) => {
    const dataLines = []
    for (const line of raw.split('\n')) {
      if (line.startsWith('data:')) {
        const text = line.startsWith('data: ') ? line.slice(6) : line.slice(5)
        dataLines.push(text)
      }
    }
    if (dataLines.length === 0) return
    const joined = dataLines.join('\n')
    if (joined !== '[DONE]') onToken(joined)
  }

  for (;;) {
    const { value, done } = await reader.read()
    if (done) { if (buffer.trim()) flush(buffer); break }
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    parts.forEach(flush)
  }
}

function normalizeAssistantMarkdown(input) {
  let out = input.replace(/\r/g, '')
  // Force a blank line before any heading or horizontal rule that got glued to previous text.
  out = out.replace(/([^\n])\n?(#{1,6}\s)/g, '$1\n\n$2')
  out = out.replace(/([^\n])(#{1,6}\s)/g, '$1\n\n$2')
  out = out.replace(/([^\n])\n?(---\s*\n)/g, '$1\n\n$2')
  // Ensure list markers and numbered steps start on their own line.
  out = out.replace(/([^\n])\s(\d+)\.\s+(\*\*)/g, '$1\n$2. $3')
  out = out.replace(/([^\n])\s([-*])\s+/g, '$1\n$2 ')
  out = out.replace(/\n{3,}/g, '\n\n')
  return out.trim()
}

class MarkdownErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return (
        <pre className="whitespace-pre-wrap text-sm leading-relaxed">{String(this.props.rawText ?? '')}</pre>
      )
    }
    return this.props.children
  }
}

// -- Google sign-in button --------------------------------------
function GoogleButton() {
  return (
    <a
      href="/api/auth/google/login"
      className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 transition-colors"
    >
      <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
        <path fill="#FFC107" d="M43.6 20H24v8h11.3C33.7 33.1 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3 0 5.8 1.1 7.9 3l5.7-5.7C34.1 6.5 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20c11 0 20-8 20-20 0-1.3-.1-2.7-.4-4z"/>
        <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.5 15.1 18.9 12 24 12c3 0 5.8 1.1 7.9 3l5.7-5.7C34.1 6.5 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
        <path fill="#4CAF50" d="M24 44c5.2 0 9.9-1.9 13.5-5.1l-6.2-5.2C29.5 35.6 26.9 36 24 36c-5.2 0-9.6-2.9-11.2-7.1l-6.5 5C9.8 39.7 16.4 44 24 44z"/>
        <path fill="#1976D2" d="M43.6 20H24v8h11.3c-.8 2.2-2.3 4.1-4.2 5.4l6.2 5.2C41 34.8 44 29.8 44 24c0-1.3-.1-2.7-.4-4z"/>
      </svg>
      Continue with Google
    </a>
  )
}

// -- Login screen -----------------------------------------------
function LoginPage({ onLogin, oauthError }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(oauthError ?? null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const data = await apiPost(mode === 'login' ? '/auth/login' : '/auth/register', { email, password })
      onLogin(data.email)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 dark:bg-slate-950 px-4">
      <div className="w-full max-w-sm bg-white dark:bg-slate-900 rounded-2xl shadow-lg p-8 flex flex-col gap-4">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-white text-xl font-extrabold select-none">A</div>
          <span className="text-2xl font-bold text-slate-800 dark:text-slate-100">Amzur AI Chat</span>
        </div>
        <h2 className="text-base font-semibold text-slate-600 dark:text-slate-300">
          {mode === 'login' ? 'Sign in to continue' : 'Create your account'}
        </h2>

        <GoogleButton />

        <div className="flex items-center gap-2">
          <div className="flex-1 border-t border-slate-200 dark:border-slate-700" />
          <span className="text-xs text-slate-400">or</span>
          <div className="flex-1 border-t border-slate-200 dark:border-slate-700" />
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3">
          <input
            type="email" required value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Work email"
            className="rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="password" required value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            className="rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {error && <p className="text-xs text-red-500">{error}</p>}
          <button
            type="submit" disabled={busy}
            className="rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white py-2 text-sm font-medium transition-colors"
          >
            {busy ? '…' : mode === 'login' ? 'Sign in' : 'Register'}
          </button>
        </form>
        <button
          onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}
          className="text-xs text-blue-600 hover:underline text-center"
        >
          {mode === 'login' ? "Don't have an account? Register" : 'Already have an account? Sign in'}
        </button>
      </div>
    </div>
  )
}

// -- Message bubble ---------------------------------------------
function Message({ role, content }) {
  const isUser = role === 'user'
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch { /* ignore */ }
  }

  if (isUser) {
    return (
      <div className="mb-5 flex justify-end">
        <div className="max-w-[72%] rounded-2xl rounded-br-md bg-linear-to-br from-blue-600 to-blue-700 px-4 py-2.5 text-[14px] leading-relaxed text-white shadow-md">
          <p className="m-0 whitespace-pre-wrap">{content}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="group mb-6 flex items-start gap-3">
      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-linear-to-br from-indigo-500 to-purple-600 text-sm font-bold text-white shadow-sm">A</div>
      <div className="assistant-card relative">
        {content && (
          <button
            onClick={copy}
            className="absolute right-3 top-3 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-500 opacity-0 shadow-sm transition hover:bg-slate-50 hover:text-slate-700 group-hover:opacity-100"
            title="Copy"
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
        )}
        {content ? (
          <MarkdownErrorBoundary rawText={content}>
            <div className="assistant-md">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  table: (props) => (
                    <div className="table-wrap">
                      <table {...props} />
                    </div>
                  ),
                  code: ({ inline, children, ...props }) => {
                    if (inline) {
                      return <code className="inline-code" {...props}>{children}</code>
                    }
                    return <code className="code-block" {...props}>{children}</code>
                  },
                }}
              >
                {normalizeAssistantMarkdown(String(content))}
              </ReactMarkdown>
            </div>
          </MarkdownErrorBoundary>
        ) : (
          <span className="animate-pulse">▌</span>
        )}
      </div>
    </div>
  )
}

// -- Chat screen ------------------------------------------------
function ChatPage({ userEmail, onLogout }) {
  const [threads, setThreads] = useState([])
  const [activeThreadId, setActiveThreadId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const bottomRef = useRef(null)
  const justCreatedRef = useRef(false)

  useEffect(() => {
    listThreads()
      .then((rows) => {
        setThreads(rows)
        if (rows.length > 0) {
          setActiveThreadId(rows[0].id)
        } else {
          setHistoryLoaded(true)
        }
      })
      .catch(() => setHistoryLoaded(true))
  }, [])

  useEffect(() => {
    if (!activeThreadId) {
      setMessages([])
      setHistoryLoaded(true)
      return
    }
    if (justCreatedRef.current) {
      justCreatedRef.current = false
      setHistoryLoaded(true)
      return
    }
    setHistoryLoaded(false)
    getThreadHistory(activeThreadId)
      .then((data) => {
        setMessages(
          data.map((m) => ({
            id: String(m.id ?? crypto.randomUUID()),
            role: m.role === 'user' ? 'user' : 'assistant',
            content: String(m.content ?? ''),
          }))
        )
        setHistoryLoaded(true)
      })
      .catch(() => {
        setMessages([])
        setHistoryLoaded(true)
      })
  }, [activeThreadId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const createNewThread = () => {
    // Don't pre-create the thread — the first message will create it with an auto-title.
    setActiveThreadId(null)
    setMessages([])
    setHistoryLoaded(true)
    setError(null)
  }

  const handleRenameThread = async (threadId) => {
    const current = threads.find((t) => t.id === threadId)
    const next = window.prompt('Rename thread', current?.title ?? 'New Chat')
    if (!next) return
    try {
      const updated = await renameThread(threadId, next)
      setThreads((prev) => prev.map((t) => (t.id === threadId ? updated : t)))
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDeleteThread = async (threadId) => {
    if (!window.confirm('Delete this thread?')) return
    try {
      await deleteThreadApi(threadId)
      setThreads((prev) => prev.filter((t) => t.id !== threadId))
      if (activeThreadId === threadId) {
        const remaining = threads.filter((t) => t.id !== threadId)
        setActiveThreadId(remaining[0]?.id ?? null)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setError(null)

    let threadId = activeThreadId
    if (!threadId) {
      try {
        const t = await createThread(text)
        setThreads((prev) => [t, ...prev])
        justCreatedRef.current = true
        setActiveThreadId(t.id)
        threadId = t.id
      } catch (err) {
        setError(err.message)
        return
      }
    }

    const userMsg = { id: crypto.randomUUID(), role: 'user', content: text }
    const assistantId = crypto.randomUUID()

    setMessages((prev) => [...prev, userMsg, { id: assistantId, role: 'assistant', content: '' }])
    setLoading(true)

    try {
      await streamChatForThread(threadId, text, (token) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + token } : m))
        )
      })

      setThreads((prev) => {
        const found = prev.find((t) => t.id === threadId)
        if (!found) return prev
        const updated = { ...found, updated_at: new Date().toISOString() }
        return [updated, ...prev.filter((t) => t.id !== threadId)]
      })
    } catch (err) {
      setError(err.message)
      setMessages((prev) => prev.filter((m) => m.id !== assistantId))
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const logout = async () => {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
    onLogout()
  }

  const userInitial = (userEmail || '?').charAt(0).toUpperCase()

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="flex w-72 shrink-0 flex-col border-r border-slate-200 bg-slate-50">
        <div className="flex items-center gap-2 px-4 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-linear-to-br from-blue-600 to-indigo-600 text-base font-extrabold text-white shadow-md shadow-blue-500/20">A</div>
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-slate-800">Amzur AI</p>
            <p className="truncate text-[11px] text-slate-400">Internal chat</p>
          </div>
        </div>

        <div className="px-3 pb-2">
          <button
            onClick={createNewThread}
            className="group flex w-full items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 hover:shadow"
          >
            <span className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-linear-to-br from-blue-600 to-indigo-600 text-white shadow-sm">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              </span>
              New chat
            </span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-slate-400 transition group-hover:text-blue-600"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/></svg>
          </button>
        </div>

        <div className="px-4 pb-1 pt-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Conversations</p>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 pb-3">
          {threads.length === 0 && (
            <div className="mx-2 mt-2 rounded-xl border border-dashed border-slate-200 px-3 py-6 text-center">
              <p className="text-xs text-slate-400">No conversations yet.</p>
              <p className="mt-1 text-[11px] text-slate-400">Start chatting to create one.</p>
            </div>
          )}
          <ul className="space-y-0.5">
            {threads.map((t) => {
              const active = activeThreadId === t.id
              return (
                <li key={t.id} className="group relative">
                  <button
                    onClick={() => setActiveThreadId(t.id)}
                    className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 pr-16 text-left text-sm transition ${
                      active
                        ? 'bg-white text-blue-700 shadow-sm ring-1 ring-blue-100'
                        : 'text-slate-600 hover:bg-white hover:text-slate-900'
                    }`}
                    title={t.title}
                  >
                    <span
                      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                        active ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200'
                      }`}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                    </span>
                    <span className="min-w-0 flex-1 truncate">{t.title}</span>
                  </button>
                  <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 gap-0.5 opacity-0 transition group-hover:opacity-100">
                    <button
                      onClick={(e) => { e.stopPropagation(); handleRenameThread(t.id) }}
                      className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                      title="Rename"
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/></svg>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteThread(t.id) }}
                      className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-red-500"
                      title="Delete"
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        </nav>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-slate-200 bg-white/80 px-6 py-3 backdrop-blur">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-linear-to-br from-indigo-500 to-purple-600 text-sm font-bold text-white shadow-sm">A</div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-800">
                {threads.find((t) => t.id === activeThreadId)?.title || 'New conversation'}
              </p>
              <p className="text-[11px] text-slate-400">Powered by Gemini via LiteLLM</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="#profile"
              className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              title="Profile"
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-200 text-xs font-bold text-slate-600">
                {userInitial}
              </div>
              <span className="hidden max-w-45 truncate sm:inline">{userEmail}</span>
            </a>
            <button
              onClick={logout}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium text-slate-600 hover:bg-red-50 hover:text-red-600"
              title="Sign out"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto w-full max-w-3xl">
            {historyLoaded && messages.length === 0 && (
              <div className="mt-16 flex flex-col items-center justify-center gap-4 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-linear-to-br from-blue-500 to-indigo-600 text-3xl font-extrabold text-white shadow-lg">A</div>
                <div>
                  <h2 className="text-2xl font-bold text-slate-800">How can I help today?</h2>
                  <p className="mt-1 text-sm text-slate-500">Ask anything — from recipes to code reviews.</p>
                </div>
                <div className="mt-4 grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2">
                  {[
                    'Give me the recipe for Biryani',
                    'Explain async/await in Python',
                    'Draft a polite leave email',
                    'Compare React vs Vue in 2026',
                  ].map((s) => (
                    <button
                      key={s}
                      onClick={() => setInput(s)}
                      className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-sm transition hover:border-blue-300 hover:bg-blue-50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {!historyLoaded && (
              <div className="mt-16 flex items-center justify-center text-sm text-slate-400">Loading history…</div>
            )}
            {messages.map((m) => <Message key={m.id} role={m.role} content={m.content} />)}
            {error && <p className="mt-2 text-center text-xs text-red-500">{error}</p>}
            <div ref={bottomRef} />
          </div>
        </main>

        <footer className="border-t border-slate-200 bg-white px-4 py-4">
          <div className="mx-auto max-w-3xl">
            <div className="flex items-end gap-2 rounded-2xl border border-slate-300 bg-white px-3 py-2 shadow-sm focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100">
              <textarea
                rows={1}
                value={input}
                onChange={(e) => {
                  setInput(e.target.value)
                  e.target.style.height = 'auto'
                  e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'
                }}
                onKeyDown={handleKey}
                placeholder="Message Amzur AI…"
                className="max-h-50 flex-1 resize-none border-0 bg-transparent px-1 py-1.5 text-sm text-slate-800 placeholder-slate-400 outline-none"
              />
              <button
                onClick={send}
                disabled={loading || !input.trim()}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-linear-to-br from-blue-600 to-indigo-600 text-white shadow-sm transition hover:from-blue-700 hover:to-indigo-700 disabled:cursor-not-allowed disabled:from-slate-300 disabled:to-slate-300"
                title="Send"
              >
                {loading ? (
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25"/><path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/></svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                )}
              </button>
            </div>
            <p className="mt-2 text-center text-[11px] text-slate-400">Press Enter to send, Shift+Enter for new line</p>
          </div>
        </footer>
      </div>
    </div>
  )
}

// -- Root -------------------------------------------------------
export default function App() {
  const [userEmail, setUserEmail] = useState(null)
  const [checking, setChecking] = useState(true)
  const [oauthError, setOauthError] = useState(null)

  // Handle Google OAuth redirect back: /?error=...
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const err = params.get('error')
    if (err) {
      setOauthError(decodeURIComponent(err))
      window.history.replaceState({}, '', '/')
    }
  }, [])

  // Restore session from existing cookie on hard refresh
  useEffect(() => {
    apiGet('/auth/me')
      .then((data) => setUserEmail(data.email))
      .catch(() => {})
      .finally(() => setChecking(false))
  }, [])

  if (checking) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-100 dark:bg-slate-950 text-slate-400 text-sm">
        Loading…
      </div>
    )
  }

  if (!userEmail) {
    return <LoginPage onLogin={(email) => setUserEmail(email)} oauthError={oauthError} />
  }

  return <ChatPage userEmail={userEmail} onLogout={() => setUserEmail(null)} />
}
