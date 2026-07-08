import { useState, useEffect } from 'react'

/**
 * App is the main dashboard component for the Multi-Agent Research Assistant.
 * 
 * In Phase 2, it manages:
 * 1. Diagnostic connection checks to /health.
 * 2. Form submission to POST /research.
 * 3. Multi-agent orchestration visualizer:
 *    - Renders the planner agent's structured sub-questions first.
 *    - Uses a timed transition to simulate/reveal the final synthesis step.
 *    - Renders the final answer and cited sources.
 */
function App() {
  // Connection diagnostics
  const [healthStatus, setHealthStatus] = useState('checking')
  const [lastChecked, setLastChecked] = useState(null)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Research form and graph states
  const [query, setQuery] = useState('')
  const [plan, setPlan] = useState([])
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState([])
  const [isResearching, setIsResearching] = useState(false)
  const [isSynthesizing, setIsSynthesizing] = useState(false)
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
   * Submits a user query to the backend agent graph endpoint.
   * 
   * Triggers the planner node, captures the sub-questions plan, and
   * performs a timed reveal to simulate synthesis of findings.
   */
  const handleResearchSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return

    setIsResearching(true)
    setIsSynthesizing(false)
    setResearchError('')
    setPlan([])
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
      
      // Update plan immediately so the user can inspect the generated sub-questions
      setPlan(data.plan || [])
      
      // Enter the synthesis phase to show the student the planning step happening
      setIsSynthesizing(true)
      
      // Give the user time to read the plan questions before rendering the final answer
      setTimeout(() => {
        setAnswer(data.answer)
        setSources(data.sources || [])
        setIsSynthesizing(false)
      }, 2000)

    } catch (err) {
      console.error('Error running research graph:', err)
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
      {/* Header */}
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

      {/* Grid workspace */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-10 grid md:grid-cols-3 gap-8">
        
        {/* Left diagnostic sidebar */}
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
            <h3 className="font-semibold text-neutral-300">Phase 2: LangGraph Orchestration</h3>
            <p>• **Planner Node**: Breaks queries into a Pydantic-enforced list of sub-questions.</p>
            <p>• **Research Node**: Runs the Research Agent sequentially on each sub-question.</p>
            <p>• **Synthesis Node**: Synthesizes the final answer using gathered sub-question findings.</p>
          </div>
        </section>

        {/* Right main client workspace */}
        <section className="md:col-span-2 space-y-6">
          <div className="bg-neutral-900 border border-neutral-850 rounded-2xl p-6 md:p-8 shadow-lg space-y-6">
            <div className="space-y-1">
              <h2 className="text-xl font-bold text-white">Ask the Research Assistant</h2>
              <p className="text-sm text-neutral-400 leading-normal">
                Input a query. The orchestrator will formulate a research plan and compile findings from sub-questions.
              </p>
            </div>

            {/* Research query input form */}
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
                    placeholder="Compare the population growth of India and China..."
                    disabled={isResearching || isSynthesizing}
                    className="flex-1 bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 text-sm text-white placeholder-neutral-600 focus:outline-none focus:border-purple-500 disabled:opacity-50 transition-colors"
                  />
                  
                  <button
                    id="submit-btn"
                    type="submit"
                    disabled={isResearching || isSynthesizing || !query.trim()}
                    className="bg-white hover:bg-neutral-200 text-neutral-950 font-semibold px-6 py-3 rounded-xl transition-all active:scale-95 disabled:opacity-40 disabled:pointer-events-none cursor-pointer flex items-center justify-center space-x-2"
                  >
                    {isResearching || isSynthesizing ? (
                      <>
                        <svg className="animate-spin h-4 w-4 text-neutral-950" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span>Processing...</span>
                      </>
                    ) : (
                      <span>Search</span>
                    )}
                  </button>
                </div>
              </div>
            </form>

            {/* Error notifications */}
            {researchError && (
              <div className="p-4 bg-rose-950/40 border border-rose-900/60 rounded-xl text-rose-300 text-sm leading-normal animate-fadeIn">
                <strong>Error:</strong> {researchError}
              </div>
            )}

            {/* Orchestration status card & results */}
            {(isResearching || plan.length > 0 || answer) && (
              <div className="border-t border-neutral-850 pt-6 space-y-6">
                
                {/* 1. Planner Node State Display */}
                {(isResearching && plan.length === 0) && (
                  <div className="space-y-4">
                    <h3 className="text-xs font-semibold uppercase text-neutral-500 tracking-wider flex items-center space-x-2">
                      <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                      <span>Planner Node Active</span>
                    </h3>
                    <div className="flex items-center space-x-2 text-sm text-neutral-450 italic">
                      Formulating research plan and generating sub-questions...
                    </div>
                  </div>
                )}

                {plan.length > 0 && (
                  <div className="space-y-3 bg-neutral-950/50 border border-neutral-900 p-5 rounded-xl">
                    <h3 className="text-xs font-semibold uppercase text-purple-400 tracking-wider flex items-center justify-between">
                      <span>Research Plan (Generated Sub-Questions)</span>
                      <span className="text-2xs bg-purple-950 border border-purple-900 text-purple-300 px-2 py-0.5 rounded-full font-mono">
                        planner_agent
                      </span>
                    </h3>
                    <ul className="space-y-2">
                      {plan.map((question, index) => (
                        <li key={index} className="flex items-start space-x-3 text-sm text-neutral-350">
                          <span className="text-purple-400 font-semibold font-mono mt-0.5">Q{index + 1}:</span>
                          <span>{question}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 2. Research & Synthesis Node Loading State */}
                {isSynthesizing && (
                  <div className="space-y-3 p-5 bg-neutral-950/30 border border-neutral-900/40 border-dashed rounded-xl animate-pulse">
                    <h3 className="text-xs font-semibold uppercase text-neutral-550 tracking-wider flex items-center space-x-2">
                      <span className="h-2 w-2 rounded-full bg-purple-500 animate-ping" />
                      <span>Research & Synthesis Node Active</span>
                    </h3>
                    <p className="text-xs text-neutral-500 italic">
                      Executing research agent sequentially on sub-questions and synthesizing findings...
                    </p>
                  </div>
                )}

                {/* 3. Final Synthesized Answer */}
                {answer && (
                  <div className="space-y-3 animate-fadeIn">
                    <h3 className="text-sm font-semibold uppercase text-neutral-400 tracking-wider">Final Synthesized Answer</h3>
                    <div className="bg-neutral-950 border border-neutral-900 p-5 rounded-xl text-neutral-200 text-sm leading-relaxed whitespace-pre-wrap">
                      {answer}
                    </div>
                  </div>
                )}

                {/* 4. Cited Sources */}
                {(sources.length > 0 && answer) && (
                  <div className="space-y-3 animate-fadeIn">
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

      {/* Footer */}
      <footer className="border-t border-neutral-900 bg-neutral-950 py-6 text-center text-xs text-neutral-600">
        <p>© 2026 Antigravity Research Assistant Monorepo. All rights reserved.</p>
      </footer>
    </div>
  )
}

export default App
