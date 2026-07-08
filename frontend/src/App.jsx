import { useState, useEffect } from 'react'

/**
 * App is the root component of the Multi-Agent Research Assistant frontend.
 * 
 * It manages the connection state to the FastAPI backend and provides
 * a premium dashboard UI. Verifying this connection is the key milestone of Phase 0.
 */
function App() {
  const [healthStatus, setHealthStatus] = useState('checking')
  const [lastChecked, setLastChecked] = useState(null)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Use VITE_API_URL if configured, otherwise fallback to local development port 8000.
  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  /**
   * Fetches the server status from the backend's /health endpoint.
   * 
   * This logic exists to prove that the frontend and backend can successfully
   * communicate across origins during development.
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
      // Add a slight artificial delay for smooth transition and micro-animation feedback
      setTimeout(() => {
        setIsRefreshing(false)
      }, 500)
    }
  }

  // Trigger health check on initial load.
  useEffect(() => {
    checkBackendHealth()
  }, [])

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col font-sans selection:bg-purple-500/30 selection:text-purple-200">
      {/* Header section with branding */}
      <header className="border-b border-neutral-800 bg-neutral-900/50 backdrop-blur-md sticky top-0 z-50">
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
          <div className="flex items-center space-x-4">
            <span className="text-xs px-2.5 py-1 rounded-full bg-neutral-800 border border-neutral-700 text-neutral-400">
              Phase 0: Plumbing
            </span>
          </div>
        </div>
      </header>

      {/* Main dashboard content container */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-12 flex flex-col justify-center">
        <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-8 md:p-12 shadow-2xl relative overflow-hidden group">
          {/* Subtle background gradient glow */}
          <div className="absolute -top-40 -right-40 w-96 h-96 bg-purple-600/10 rounded-full blur-3xl group-hover:bg-purple-600/15 transition-all duration-700" />
          <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl group-hover:bg-indigo-600/15 transition-all duration-700" />

          <div className="relative z-10 space-y-8">
            <div className="text-center md:text-left space-y-2">
              <h2 className="text-3xl font-bold tracking-tight text-white">System Status Connection</h2>
              <p className="text-neutral-400 text-base max-w-lg">
                This diagnostic dashboard verifies the communication channel between the React client and the FastAPI backend.
              </p>
            </div>

            {/* Health status visualization card */}
            <div className="grid md:grid-cols-2 gap-6 items-center border-t border-b border-neutral-800/80 py-8">
              <div className="space-y-4">
                <div className="text-sm font-medium text-neutral-500 uppercase tracking-wider">
                  Target Service Endpoint
                </div>
                <div className="flex items-center space-x-2 bg-neutral-950 px-4 py-3 rounded-xl border border-neutral-800 w-fit">
                  <span className="font-mono text-sm text-purple-400">{API_BASE_URL}/health</span>
                </div>
              </div>

              <div className="space-y-4">
                <div className="text-sm font-medium text-neutral-500 uppercase tracking-wider">
                  Connection Health
                </div>
                <div className="flex items-center space-x-3">
                  {/* Status Indicator Lights */}
                  {healthStatus === 'checking' && (
                    <>
                      <span className="relative flex h-4 w-4">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-4 w-4 bg-amber-500"></span>
                      </span>
                      <span className="font-medium text-amber-400">Verifying Connection...</span>
                    </>
                  )}
                  {healthStatus === 'connected' && (
                    <>
                      <span className="relative flex h-4 w-4">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-4 w-4 bg-emerald-500"></span>
                      </span>
                      <span className="font-medium text-emerald-400">Connected to Backend</span>
                    </>
                  )}
                  {(healthStatus === 'disconnected' || healthStatus === 'unhealthy') && (
                    <>
                      <span className="relative flex h-4 w-4">
                        <span className="relative inline-flex rounded-full h-4 w-4 bg-rose-500"></span>
                      </span>
                      <span className="font-medium text-rose-500">Connection Failed</span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* User actions and timestamps */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="text-sm text-neutral-400">
                {lastChecked ? (
                  <span>Last Checked: <strong className="text-neutral-200">{lastChecked}</strong></span>
                ) : (
                  <span>Status check pending...</span>
                )}
              </div>

              <button
                id="refresh-btn"
                type="button"
                onClick={checkBackendHealth}
                disabled={isRefreshing}
                className="w-full sm:w-auto flex items-center justify-center space-x-2 px-6 py-3 rounded-xl bg-white text-neutral-950 font-medium hover:bg-neutral-200 active:scale-95 disabled:opacity-50 disabled:pointer-events-none transition-all duration-200 cursor-pointer shadow-lg shadow-white/5"
              >
                <svg
                  className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M21 21v-5h-.581m0 0a8.003 8.003 0 11-15.357-2"
                  />
                </svg>
                <span>{isRefreshing ? 'Checking...' : 'Check Status'}</span>
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-neutral-900 bg-neutral-950 py-6 text-center text-xs text-neutral-600">
        <p>© 2026 Antigravity Research Assistant Monorepo. All rights reserved.</p>
      </footer>
    </div>
  )
}

export default App
