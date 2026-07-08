import { useState, useEffect } from 'react'

/**
 * App is the main dashboard component for the Multi-Agent Research Assistant.
 * 
 * It manages:
 * 1. Diagnostic connection checks to /health.
 * 2. User input and request state for the research agent endpoint (/research).
 * 3. Render states for answers and clickable sources.
 */
function App() {
  // Connection state
  const [healthStatus, setHealthStatus] = useState('checking')
  const [lastChecked, setLastChecked] = useState(null)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Research agent form states
  const [query, setQuery] = useState('')
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState([])
  const [isResearching, setIsResearching] = useState(false)
  const [researchError, setResearchError] = useState('')

  // Configure endpoint fallback
  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  /**
   * Diagnostic function to fetch connection health.
   */
  const checkBackendHealth = async () => {
    setIsRefreshing(true)
    try {
      const response = await fetch(`${API_BASE_URL}/health`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      if (data && data.status === 'ok') {
        setHealthStatus('connected')
      } else {
        setHealthStatus('unhealthy')
      }
    } catch (error) {
      console.error('Error fetching backend health:', error)
      setHealthStatus('disconnected')
    } finally {
      setLastChecked(new Date().toLocaleTimeString())
      setTimeout(() => {
        setIsRefreshing(false)
      }, 500)
    }
  }

  /**
   * Submits a user query to the backend agent endpoint.
   * 
   * Triggers loading state, invokes POST /research, parses the returned
   * answer and source URLs, and handles fallback errors.
   */
  const handleResearchSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return

    setIsResearching(true)
    setResearchError('')
    setAnswer('')
    setSources([])

    try {
      const response = await fetch(`${API_BASE_URL}/research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query: query.trim() })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Server returned ${response.status}`)
      }

      const data = await response.json()
      setAnswer(data.answer)
      setSources(data.sources || [])
    } catch (err) {
      console.error('Error running research:', err)
      setResearchError(err.message || 'Failed to complete research request.')
    } finally {
      setIsResearching(false)
    }
  }

  // Check health on initial load.
  useEffect(() => {
    checkBackendHealth()
  }, [])

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col font-sans selection:bg-purple-500/30 selection:text-purple-200">
      {/* Navbar Header */}
      <header className="border-b border-neutral-900 bg-neutral-900/40 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-purple-500/20">
              <span className="font-bold text-lg text-white">Ω</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-white m-0">Antigravity Research</h1>
              <p className="text-xs text-neutral-400">Multi-Agent Assistant System</p>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            {/* Minimal inline connection badge */}
            <span className="flex items-center space-x-1.5 bg-neutral-900 border border-neutral-800 rounded-full px-3 py-1 text-xs">
              <span className={`h-2.5 w-2.5 rounded-full ${
                healthStatus === 'connected' ? 'bg-emerald-500' :
                healthStatus === 'checking' ? 'bg-amber-500 animate-pulse' : 'bg-rose-500'
              }`} />
              <span className="text-neutral-400">API Gateway</span>
            </span>
          </div>
        </div>
      </header>

      {/* Main Grid Workspace */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-10 grid md:grid-cols-3 gap-8">
        
        {/* Left diagnostics panel */}
        <section className="space-y-6 md:col-span-1">
          <div className="bg-neutral-900 border border-neutral-850 rounded-2xl p-6 shadow-md">
            <h2 className="text-sm font-semibold uppercase text-neutral-400 tracking-wider mb-4">Diagnostics</h2>
            
            <div className="space-y-4">
              <div className="flex flex-col space-y-1 bg-neutral-950 p-3.5 rounded-xl border border-neutral-900">
                <span className="text-xs text-neutral-500">API Endpoint</span>
                <span className="font-mono text-xs text-purple-400 break-all">{API_BASE_URL}/health</span>
              </div>

              <div className="flex items-center justify-between p-3.5 bg-neutral-950 rounded-xl border border-neutral-900">
                <span className="text-xs text-neutral-500">Status</span>
                <span className={`text-xs font-semibold uppercase ${
                  healthStatus === 'connected' ? 'text-emerald-400' :
                  healthStatus === 'checking' ? 'text-amber-400' : 'text-rose-400'
                }`}>
                  {healthStatus}
                </span>
              </div>

              <div className="text-2xs text-neutral-500 leading-tight">
                {lastChecked ? `Last Pinged: ${lastChecked}` : 'Connecting...'}
              </div>

              <button
                type="button"
                onClick={checkBackendHealth}
                disabled={isRefreshing}
                className="w-full text-xs font-medium bg-neutral-800 hover:bg-neutral-700 text-white py-2 rounded-lg cursor-pointer transition-colors disabled:opacity-40"
              >
                {isRefreshing ? 'Checking...' : 'Ping Gateway'}
              </button>
            </div>
          </div>
          
          <div className="bg-neutral-900 border border-neutral-850 rounded-2xl p-6 shadow-md text-xs text-neutral-400 space-y-3 leading-relaxed">
            <h3 className="font-semibold text-neutral-300">Phase 1 Objectives:</h3>
            <p>• Uses native LLM tool schemas to toggle web search.</p>
            <p>• Fetches real-time search context using the Tavily API.</p>
            <p>• Cites sources and renders references dynamically.</p>
          </div>
        </section>

        {/* Right workspace panel (Agent client interface) */}
        <section className="md:col-span-2 space-y-6">
          <div className="bg-neutral-900 border border-neutral-850 rounded-2xl p-6 md:p-8 shadow-lg space-y-6">
            <div className="space-y-1">
              <h2 className="text-xl font-bold text-white">Ask the Research Agent</h2>
              <p className="text-sm text-neutral-400 leading-normal">
                Input a query. The agent decides if it requires web search to generate an up-to-date response.
              </p>
            </div>

            {/* Research query form */}
            <form onSubmit={handleResearchSubmit} className="space-y-4">
              <div className="flex flex-col space-y-2">
                <label htmlFor="query-input" className="text-xs text-neutral-400 font-medium">Research Query</label>
                <div className="flex gap-3">
                  <input
                    id="query-input"
                    type="text"
                    required
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="e.g. What is the current temperature in Seattle?"
                    disabled={isResearching}
                    className="flex-1 bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 text-sm text-white placeholder-neutral-600 focus:outline-none focus:border-purple-500 disabled:opacity-50 transition-colors"
                  />
                  
                  <button
                    id="submit-btn"
                    type="submit"
                    disabled={isResearching || !query.trim()}
                    className="bg-white hover:bg-neutral-200 text-neutral-950 font-semibold px-6 py-3 rounded-xl transition-all active:scale-95 disabled:opacity-40 disabled:pointer-events-none cursor-pointer flex items-center justify-center space-x-2"
                  >
                    {isResearching ? (
                      <>
                        <svg className="animate-spin h-4 w-4 text-neutral-950" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span>Researching...</span>
                      </>
                    ) : (
                      <span>Search</span>
                    )}
                  </button>
                </div>
              </div>
            </form>

            {/* Render errors if any */}
            {researchError && (
              <div className="p-4 bg-rose-950/40 border border-rose-900/60 rounded-xl text-rose-300 text-sm leading-normal">
                <strong>Error:</strong> {researchError}
              </div>
            )}

            {/* Agent results viewport */}
            {(isResearching || answer || sources.length > 0) && (
              <div className="border-t border-neutral-850 pt-6 space-y-6">
                
                {/* Loader skeleton */}
                {isResearching && (
                  <div className="space-y-4 animate-pulse">
                    <div className="h-4 bg-neutral-850 rounded w-1/3" />
                    <div className="space-y-2">
                      <div className="h-3.5 bg-neutral-850 rounded w-full" />
                      <div className="h-3.5 bg-neutral-850 rounded w-5/6" />
                      <div className="h-3.5 bg-neutral-850 rounded w-2/3" />
                    </div>
                  </div>
                )}

                {/* Final synthesized answer */}
                {answer && (
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold uppercase text-neutral-400 tracking-wider">Research Answer</h3>
                    <div className="bg-neutral-950 border border-neutral-900 p-5 rounded-xl text-neutral-200 text-sm leading-relaxed whitespace-pre-wrap">
                      {answer}
                    </div>
                  </div>
                )}

                {/* Sources list */}
                {sources.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold uppercase text-neutral-400 tracking-wider">Sources Cited</h3>
                    <ul className="space-y-2">
                      {sources.map((src, idx) => (
                        <li key={idx} className="flex items-center space-x-2">
                          <span className="text-2xs text-purple-400 bg-purple-950/45 px-2 py-0.5 border border-purple-900/50 rounded font-mono">
                            [{idx + 1}]
                          </span>
                          <a
                            href={src}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-neutral-400 hover:text-purple-400 hover:underline break-all transition-colors"
                          >
                            {src}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </main>

      {/* Page Footer */}
      <footer className="border-t border-neutral-900 bg-neutral-950 py-6 text-center text-xs text-neutral-600">
        <p>© 2026 Antigravity Research Assistant Monorepo. All rights reserved.</p>
      </footer>
    </div>
  )
}

export default App
