import { useState, useEffect } from 'react'
import { marked } from 'marked'

/**
 * App is the root dashboard for the Multi-Agent Research Assistant (Phase 5).
 *
 * It manages:
 * 1. Diagnostic connection checks to /health.
 * 2. File uploads to /documents/upload.
 * 3. Form submissions to POST /research.
 * 4. Progressive 6-node graph visualizer (planner -> research|document -> combine -> writer -> reviewer).
 * 5. Structured evidence cards and compiled markdown report.
 * 6. ReviewerAgent verdict panel with Approve / Reject buttons (human-in-the-loop).
 */
function App() {
  // Connection diagnostics
  const [healthStatus, setHealthStatus] = useState('checking')
  const [lastChecked, setLastChecked] = useState(null)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Document ingestion upload states
  const [uploading, setUploading] = useState(false)
  const [uploadSuccess, setUploadSuccess] = useState('')
  const [uploadError, setUploadError] = useState('')

  // Research form and graph states
  const [query, setQuery] = useState('')
  const [plan, setPlan] = useState([])
  const [evidence, setEvidence] = useState([])
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState([])
  const [finalReport, setFinalReport] = useState('')
  // Phase 5: reviewer verdict and human-decision state
  const [reportId, setReportId] = useState('')
  const [reviewVerdict, setReviewVerdict] = useState(null)   // {approved, issues}
  const [humanDecision, setHumanDecision] = useState(null)   // 'approved' | 'rejected' | null
  const [isApproving, setIsApproving] = useState(false)
  
  // Phase 6 Unified Execution statuses
  const [nodeStatuses, setNodeStatuses] = useState({
    planner: 'pending',        // 'pending' | 'in-progress' | 'completed'
    research: 'pending',
    document: 'pending',
    combine: 'pending',
    writer: 'pending',
    reviewer: 'pending',
    human_review: 'pending'
  })
  const [isGraphRunning, setIsGraphRunning] = useState(false)
  const [researchError, setResearchError] = useState('')

  // Phase 7 Cost Tracking states
  const [totalCost, setTotalCost] = useState(0.0)
  const [tokensInput, setTokensInput] = useState(0)
  const [tokensOutput, setTokensOutput] = useState(0)

  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  /**
   * Diagnostic connection checker.
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
   * File upload handler for text or PDF files.
   */
  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    setUploading(true)
    setUploadSuccess('')
    setUploadError('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${API_BASE_URL}/documents/upload`, {
        method: 'POST',
        body: formData
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Ingestion failed.')
      }

      const data = await res.json()
      setUploadSuccess(data.message || `Successfully ingested ${file.name}`)
    } catch (err) {
      console.error('File upload failed:', err)
      setUploadError(err.message || 'Upload connection failed.')
    } finally {
      setUploading(false)
      // Reset input value so same file can be selected again
      e.target.value = ''
    }
  }

  /**
   * Submits query to research graph endpoint.
   * 
   * Triggers planning step, parallel research/RAG steps, analyst merge step,
   * and final synthesized response reveal.
   */
  /**
   * Submits query to GET /research/stream Server-Sent Events (SSE) endpoint.
   * 
   * Opens a persistent connection that receives node start and finish events
   * in real-time, mapping them to the progressive workflow monitor.
   */
  const handleResearchSubmit = (e) => {
    e.preventDefault()
    if (!query.trim()) return

    // 1. Reset all local state variables
    setPlan([])
    setEvidence([])
    setAnswer('')
    setFinalReport('')
    setSources([])
    setResearchError('')
    setReportId('')
    setReviewVerdict(null)
    setHumanDecision(null)
    setTotalCost(0.0)
    setTokensInput(0)
    setTokensOutput(0)

    // Reset workflow monitor node statuses
    setNodeStatuses({
      planner: 'pending',
      research: 'pending',
      document: 'pending',
      combine: 'pending',
      writer: 'pending',
      reviewer: 'pending',
      human_review: 'pending'
    })
    setIsGraphRunning(true)

    // 2. Build the SSE connection URL
    const url = `${API_BASE_URL}/research/stream?query=${encodeURIComponent(query.trim())}`
    const eventSource = new EventSource(url)

    // 3. Register message event handler to process real-time updates
    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        const eventName = payload.event

        if (eventName === 'start') {
          // Received session UUID from the server
          setReportId(payload.report_id || '')
        } 
        
        else if (eventName === 'node_start') {
          // Transition the specific node to in-progress status
          const node = payload.node
          setNodeStatuses((prev) => ({ ...prev, [node]: 'in-progress' }))
          
          // Special case: planner node start maps to clearing plan array
          if (node === 'planner') {
            setPlan([])
          }
          // Special case: parallel research branches
          if (node === 'research' || node === 'document') {
            setNodeStatuses((prev) => ({
              ...prev,
              research: prev.research === 'completed' ? 'completed' : 'in-progress',
              document: prev.document === 'completed' ? 'completed' : 'in-progress'
            }))
          }
        } 
        
        else if (eventName === 'node_finish') {
          // Transition the specific node to completed status
          const node = payload.node
          const data = payload.data || {}
          setNodeStatuses((prev) => ({ ...prev, [node]: 'completed' }))

          // Special case: parallel branches should both show completed
          if (node === 'research' || node === 'document') {
            setNodeStatuses((prev) => ({ ...prev, [node]: 'completed' }))
          }

          // Real-time cost and token counts update
          if (data.accumulated_cost_usd !== undefined) setTotalCost(data.accumulated_cost_usd)
          if (data.accumulated_tokens_input !== undefined) setTokensInput(data.accumulated_tokens_input)
          if (data.accumulated_tokens_output !== undefined) setTokensOutput(data.accumulated_tokens_output)

          // Populate step-specific output data in real-time
          if (node === 'planner') {
            setPlan(data.plan || [])
          } else if (node === 'combine') {
            setEvidence(data.evidence || [])
            setSources(data.sources || [])
          } else if (node === 'writer') {
            setFinalReport(data.final_report || '')
          } else if (node === 'reviewer') {
            setReviewVerdict(data.review_verdict || null)
          }
        } 
        
        else if (eventName === 'paused') {
          // Hit the human-in-the-loop interrupt block
          const data = payload.data || {}
          setReviewVerdict(data.review_verdict || null)
          setNodeStatuses((prev) => ({ ...prev, human_review: 'in-progress' }))
          if (data.accumulated_cost_usd !== undefined) setTotalCost(data.accumulated_cost_usd)
          if (data.accumulated_tokens_input !== undefined) setTokensInput(data.accumulated_tokens_input)
          if (data.accumulated_tokens_output !== undefined) setTokensOutput(data.accumulated_tokens_output)
          setIsGraphRunning(false)
        } 
        
        else if (eventName === 'done') {
          // Graph completed execution (approved or rejected)
          const data = payload.data || {}
          setHumanDecision(data.human_decision || 'approved')
          setFinalReport(data.final_report || '')
          setSources(data.sources || [])
          setNodeStatuses((prev) => ({ ...prev, human_review: 'completed' }))
          if (data.accumulated_cost_usd !== undefined) setTotalCost(data.accumulated_cost_usd)
          if (data.accumulated_tokens_input !== undefined) setTokensInput(data.accumulated_tokens_input)
          if (data.accumulated_tokens_output !== undefined) setTokensOutput(data.accumulated_tokens_output)
          setIsGraphRunning(false)
          eventSource.close()
        } 
        
        else if (eventName === 'error') {
          setResearchError(payload.status || 'An error occurred during graph execution.')
          setIsGraphRunning(false)
          eventSource.close()
        }
      } catch (err) {
        console.error('Failed to parse SSE event data:', err)
      }
    }

    eventSource.onerror = (err) => {
      console.error('SSE connection error:', err)
      setResearchError('Connection to server lost. Please retry.')
      setIsGraphRunning(false)
      eventSource.close()
    }
  }

  useEffect(() => {
    checkBackendHealth()
  }, [])

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col font-sans selection:bg-purple-500/30 selection:text-purple-200">
      {/* Navigation Header */}
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

      {/* Main Workspace Layout */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-10 grid md:grid-cols-3 gap-8">
        
        {/* Left Side Panel (Diagnostics & File Ingestion) */}
        <section className="space-y-6 md:col-span-1">
          {/* File Uploader Card */}
          <div className="bg-neutral-900 border border-neutral-850 rounded-2xl p-6 shadow-md space-y-4">
            <div>
              <h2 className="text-sm font-semibold uppercase text-neutral-400 tracking-wider">Document Indexing</h2>
              <p className="text-2xs text-neutral-500 leading-normal mt-1">
                Upload custom reference PDFs or TXT files to ingest them into the pgvector semantic database.
              </p>
            </div>

            <div className="space-y-3">
              <label 
                htmlFor="file-upload" 
                className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-neutral-800 rounded-xl cursor-pointer bg-neutral-950/40 hover:bg-neutral-950 hover:border-neutral-700 transition-all duration-200 group"
              >
                <div className="flex flex-col items-center justify-center pt-5 pb-6 text-center px-4">
                  {uploading ? (
                    <>
                      <svg className="animate-spin h-6 w-6 text-purple-400 mb-2" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <p className="text-xs text-neutral-400">Embedding document chunks...</p>
                    </>
                  ) : (
                    <>
                      <svg className="w-6 h-6 text-neutral-600 group-hover:text-purple-400 transition-colors mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                      <p className="text-xs text-neutral-400 font-medium">Select a PDF or TXT file</p>
                      <p className="text-3xs text-neutral-600 mt-1">PDF, TXT up to 10MB</p>
                    </>
                  )}
                </div>
                <input 
                  id="file-upload" 
                  type="file" 
                  accept=".pdf,.txt" 
                  disabled={uploading} 
                  onChange={handleFileUpload} 
                  className="hidden" 
                />
              </label>

              {/* Upload statuses */}
              {uploadSuccess && (
                <div className="p-3 bg-emerald-950/40 border border-emerald-900/60 rounded-xl text-emerald-400 text-2xs animate-fadeIn leading-relaxed">
                  ✓ {uploadSuccess}
                </div>
              )}
              {uploadError && (
                <div className="p-3 bg-rose-950/40 border border-rose-900/60 rounded-xl text-rose-400 text-2xs animate-fadeIn leading-relaxed">
                  ✗ {uploadError}
                </div>
              )}
            </div>
          </div>

          {/* Connection Diagnostics Card */}
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

              <button
                type="button"
                onClick={checkBackendHealth}
                disabled={isRefreshing}
                className="w-full text-xs font-medium bg-neutral-800 hover:bg-neutral-700 text-white py-2 rounded-lg cursor-pointer transition-colors"
              >
                {isRefreshing ? 'Checking...' : 'Ping Gateway'}
              </button>
            </div>
          </div>
          
          <div className="bg-neutral-900 border border-neutral-850 rounded-2xl p-6 shadow-md text-xs text-neutral-450 space-y-3 leading-relaxed">
            <h3 className="font-semibold text-neutral-300">Phase 3: Parallel Agents</h3>
            <p>• Runs the Web search and RAG Document lookup in parallel.</p>
            <p>• Invokes the AnalystAgent node to merge context and clean claims.</p>
            <p>• Fuses web links and PDF page citations dynamically.</p>
          </div>
        </section>

        {/* Right Main Client Panel (Agent Interactions & Results) */}
        <section className="md:col-span-2 space-y-6">
          <div className="bg-neutral-900 border border-neutral-850 rounded-2xl p-6 md:p-8 shadow-lg space-y-6">
            <div className="space-y-1">
              <h2 className="text-xl font-bold text-white">Ask the Orchestrated Assistant</h2>
              <p className="text-sm text-neutral-400 leading-normal">
                Input a query. The orchestrator will retrieve findings concurrently from the web and your indexed docs.
              </p>
            </div>

            {/* Research Query input form */}
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
                    placeholder="Compare the GDP goals in uploaded reports vs current web stats..."
                    disabled={isGraphRunning}
                    className="flex-1 bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 text-sm text-white placeholder-neutral-600 focus:outline-none focus:border-purple-500 disabled:opacity-50 transition-colors"
                  />
                  
                  <button
                    id="submit-btn"
                    type="submit"
                    disabled={isGraphRunning || !query.trim()}
                    className="bg-white hover:bg-neutral-200 text-neutral-950 font-semibold px-6 py-3 rounded-xl transition-all active:scale-95 disabled:opacity-40 disabled:pointer-events-none cursor-pointer flex items-center justify-center space-x-2"
                  >
                    {isGraphRunning ? (
                      <>
                        <svg className="animate-spin h-4 w-4 text-neutral-950" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span>Running...</span>
                      </>
                    ) : (
                      <span>Search</span>
                    )}
                  </button>
                </div>
              </div>
            </form>

            {/* Error alerts */}
            {researchError && (
              <div className="p-4 bg-rose-950/40 border border-rose-900/60 rounded-xl text-rose-300 text-sm leading-normal">
                <strong>Error:</strong> {researchError}
              </div>
            )}

            {/* State Graph Visualizer & Results board */}
            {(isGraphRunning || plan.length > 0 || evidence.length > 0 || finalReport) && (
              <div className="border-t border-neutral-850 pt-6 space-y-6">
                
                {/* 1. LangGraph State Visualization Panel — 6 nodes */}
                <div className="bg-neutral-950/60 border border-neutral-900 rounded-xl p-5 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-900 pb-3.5">
                    <h3 className="text-xs font-semibold uppercase text-neutral-400 tracking-wider">
                      LangGraph Workflow Monitor
                    </h3>
                    {tokensInput > 0 && (
                      <div className="flex flex-wrap items-center gap-3 text-3xs font-mono text-neutral-450 bg-neutral-900/60 px-3 py-1.5 rounded-lg border border-neutral-850">
                        <span>Input: <strong className="text-neutral-300">{tokensInput.toLocaleString()}</strong> tkn</span>
                        <span>Output: <strong className="text-neutral-300">{tokensOutput.toLocaleString()}</strong> tkn</span>
                        <span className="text-purple-400 font-semibold bg-purple-950/40 px-2 py-0.5 rounded border border-purple-900/50">
                          Cost: ${totalCost.toFixed(6)}
                        </span>
                      </div>
                    )}
                  </div>
                  
                  <div className="grid grid-cols-6 gap-2 text-center text-xs">
                    {/* Planner Node */}
                    <div className={`p-3 rounded-xl border transition-all ${
                      nodeStatuses.planner === 'in-progress' ? 'bg-amber-950/40 border-amber-500 text-amber-300 animate-pulse' :
                      nodeStatuses.planner === 'completed' ? 'bg-purple-950/30 border-purple-800/80 text-purple-300' : 'bg-neutral-900/40 border-neutral-850 text-neutral-600'
                    }`}>
                      <div className="font-semibold">planner</div>
                      <div className="text-3xs mt-1 text-neutral-500">Node</div>
                    </div>

                    {/* Research Node */}
                    <div className={`p-3 rounded-xl border transition-all ${
                      nodeStatuses.research === 'in-progress' ? 'bg-indigo-950/50 border-indigo-500 text-indigo-300 animate-pulse' :
                      nodeStatuses.research === 'completed' ? 'bg-purple-950/30 border-purple-800/80 text-purple-300' : 'bg-neutral-900/40 border-neutral-850 text-neutral-600'
                    }`}>
                      <div className="font-semibold">research</div>
                      <div className="text-3xs mt-1 text-neutral-500">Parallel (Web)</div>
                    </div>

                    {/* Document Node */}
                    <div className={`p-3 rounded-xl border transition-all ${
                      nodeStatuses.document === 'in-progress' ? 'bg-cyan-950/50 border-cyan-500 text-cyan-300 animate-pulse' :
                      nodeStatuses.document === 'completed' ? 'bg-purple-950/30 border-purple-800/80 text-purple-300' : 'bg-neutral-900/40 border-neutral-850 text-neutral-600'
                    }`}>
                      <div className="font-semibold">document</div>
                      <div className="text-3xs mt-1 text-neutral-500">Parallel (RAG)</div>
                    </div>

                    {/* Combine Node */}
                    <div className={`p-3 rounded-xl border transition-all ${
                      nodeStatuses.combine === 'in-progress' ? 'bg-emerald-950/40 border-emerald-500 text-emerald-300 animate-pulse' :
                      nodeStatuses.combine === 'completed' ? 'bg-purple-950/30 border-purple-800/80 text-purple-300' : 'bg-neutral-900/40 border-neutral-850 text-neutral-600'
                    }`}>
                      <div className="font-semibold">combine</div>
                      <div className="text-3xs mt-1 text-neutral-500">Merge (Analyst)</div>
                    </div>

                    {/* Writer Node */}
                    <div className={`p-3 rounded-xl border transition-all ${
                      nodeStatuses.writer === 'in-progress' ? 'bg-fuchsia-950/40 border-fuchsia-500 text-fuchsia-300 animate-pulse' :
                      nodeStatuses.writer === 'completed' ? 'bg-purple-950/30 border-purple-800/80 text-purple-300' : 'bg-neutral-900/40 border-neutral-850 text-neutral-600'
                    }`}>
                      <div className="font-semibold">writer</div>
                      <div className="text-3xs mt-1 text-neutral-500">Report</div>
                    </div>

                    {/* Reviewer Node */}
                    <div className={`p-3 rounded-xl border transition-all ${
                      nodeStatuses.reviewer === 'in-progress' ? 'bg-orange-950/50 border-orange-500 text-orange-300 animate-pulse' :
                      nodeStatuses.reviewer === 'completed' && reviewVerdict?.approved === false ? 'bg-rose-950/40 border-rose-700 text-rose-300' :
                      nodeStatuses.reviewer === 'completed' && reviewVerdict?.approved === true ? 'bg-green-950/40 border-green-700 text-green-300' :
                      'bg-neutral-900/40 border-neutral-850 text-neutral-600'
                    }`}>
                      <div className="font-semibold">reviewer</div>
                      <div className="text-3xs mt-1 text-neutral-500">Fact-Check</div>
                    </div>
                  </div>
                </div>

                {/* 2. Research Plan Details */}
                {plan.length > 0 && (
                  <div className="space-y-3 p-5 bg-neutral-950/30 border border-neutral-900 rounded-xl">
                    <h3 className="text-xs font-semibold uppercase text-neutral-400 tracking-wider">
                      Structured Research Sub-Questions
                    </h3>
                    <ul className="space-y-2">
                      {plan.map((q, idx) => (
                        <li key={idx} className="flex items-start space-x-3 text-sm text-neutral-350">
                          <span className="text-purple-400 font-mono font-semibold mt-0.5">Q{idx + 1}:</span>
                          <span>{q}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 3. Merged Evidence Board */}
                {evidence.length > 0 && (
                  <div className="space-y-4">
                    <h3 className="text-xs font-semibold uppercase text-neutral-400 tracking-wider flex items-center justify-between">
                      <span>Consolidated Analyst Evidence Board</span>
                      <span className="text-2xs bg-purple-950 border border-purple-900 text-purple-300 px-2 py-0.5 rounded-full font-mono">
                        analyst_agent
                      </span>
                    </h3>
                    
                    <div className="grid gap-3.5">
                      {evidence.map((item, idx) => (
                        <div key={idx} className="bg-neutral-900/60 border border-neutral-850 rounded-xl p-4 flex flex-col md:flex-row md:items-start justify-between gap-3 text-sm">
                          <div className="space-y-1 flex-1">
                            <div className="text-neutral-250 leading-relaxed">
                              <span className="text-neutral-500 font-mono mr-1.5">[{idx + 1}]</span>
                              {item.claim}
                            </div>
                            <div className="text-xs text-neutral-500">
                              Citation: <strong className="text-neutral-400 break-all font-mono text-3xs">{item.source}</strong>
                            </div>
                          </div>

                          <div className="shrink-0 flex items-center md:justify-end">
                            <span className={`text-2xs font-mono font-bold uppercase px-2 py-0.5 rounded-md border ${
                              item.source_type === 'document' 
                                ? 'bg-cyan-950/40 border-cyan-800 text-cyan-400' 
                                : 'bg-indigo-950/40 border-indigo-800 text-indigo-400'
                            }`}>
                              {item.source_type}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 4. Reviewer Verdict Panel */}
                {reviewVerdict && (
                  <div className={`rounded-xl border p-5 space-y-3 ${
                    reviewVerdict.approved
                      ? 'bg-green-950/20 border-green-800/60'
                      : 'bg-rose-950/20 border-rose-800/60'
                  }`}>
                    <h3 className="text-xs font-semibold uppercase tracking-wider flex items-center gap-2"
                        style={{color: reviewVerdict.approved ? '#4ade80' : '#f87171'}}>
                      <span>{reviewVerdict.approved ? '✅' : '⚠️'}</span>
                      <span>Reviewer Verdict — {reviewVerdict.approved ? 'Approved for Human Review' : 'Issues Found'}</span>
                    </h3>

                    {!reviewVerdict.approved && reviewVerdict.issues?.length > 0 && (
                      <ul className="space-y-1.5 pl-1">
                        {reviewVerdict.issues.map((issue, idx) => (
                          <li key={idx} className="flex items-start gap-2 text-sm text-rose-300">
                            <span className="text-rose-500 font-mono shrink-0 mt-0.5">#{idx + 1}</span>
                            <span>{issue}</span>
                          </li>
                        ))}
                      </ul>
                    )}

                    {/* Human-in-the-loop buttons — only shown when awaiting a decision */}
                    {humanDecision === null && reportId && (
                      <div className="flex items-center gap-3 pt-2">
                        <p className="text-xs text-neutral-500 flex-1">Awaiting your decision before this report is finalized.</p>
                        <button
                          id="btn-approve-report"
                          disabled={isApproving}
                          onClick={async () => {
                            setIsApproving(true)
                            try {
                              const res = await fetch(`${API_BASE_URL}/report/${reportId}/approve`, { method: 'POST' })
                              const d = await res.json()
                              setHumanDecision(d.human_decision)
                            } catch(e) { console.error('Approve failed', e) }
                            setIsApproving(false)
                          }}
                          className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-green-900/60 border border-green-700 text-green-300 hover:bg-green-800/70 transition-all disabled:opacity-50"
                        >
                          {isApproving ? 'Approving…' : '✅ Approve'}
                        </button>
                        <button
                          id="btn-reject-report"
                          disabled={isApproving}
                          onClick={async () => {
                            setIsApproving(true)
                            try {
                              const res = await fetch(`${API_BASE_URL}/report/${reportId}/reject`, { method: 'POST' })
                              const d = await res.json()
                              setHumanDecision(d.human_decision)
                            } catch(e) { console.error('Reject failed', e) }
                            setIsApproving(false)
                          }}
                          className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-rose-900/60 border border-rose-700 text-rose-300 hover:bg-rose-800/70 transition-all disabled:opacity-50"
                        >
                          ❌ Reject
                        </button>
                      </div>
                    )}

                    {/* Show final decision badge once the human has acted */}
                    {humanDecision && (
                      <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${
                        humanDecision === 'approved'
                          ? 'bg-green-950/50 border-green-700 text-green-300'
                          : 'bg-rose-950/50 border-rose-700 text-rose-300'
                      }`}>
                        {humanDecision === 'approved' ? '✅ FINAL — Human Approved' : '❌ REJECTED by Human'}
                      </div>
                    )}
                  </div>
                )}

                {/* 5. Compiled Report — with FINAL/REJECTED badge */}
                {(finalReport || answer) && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold uppercase text-neutral-400 tracking-wider">
                        Compiled Research Report
                      </h3>
                      {humanDecision === 'approved' && (
                        <span className="text-2xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-green-950/50 border border-green-700 text-green-300">
                          ✅ Final
                        </span>
                      )}
                      {humanDecision === 'rejected' && (
                        <span className="text-2xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-rose-950/50 border border-rose-700 text-rose-300">
                          ❌ Rejected
                        </span>
                      )}
                    </div>
                    {finalReport ? (
                      <div
                        className={`bg-neutral-950 border p-6 rounded-xl text-neutral-200 text-sm leading-relaxed research-report ${
                          humanDecision === 'rejected' ? 'border-rose-900/60 opacity-60' : 'border-neutral-900'
                        }`}
                        dangerouslySetInnerHTML={{ __html: marked.parse(finalReport) }}
                      />
                    ) : (
                      <div className="bg-neutral-950 border border-neutral-900 p-5 rounded-xl text-neutral-200 text-sm leading-relaxed whitespace-pre-wrap">
                        {answer}
                      </div>
                    )}
                  </div>
                )}

                {/* 6. Unique Source links */}
                {(sources.length > 0 && (finalReport || answer)) && (
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold uppercase text-neutral-400 tracking-wider">Unique Citations</h3>
                    <ul className="space-y-1.5">
                      {sources.map((src, idx) => (
                        <li key={idx} className="flex items-center space-x-2">
                          <span className="text-2xs text-purple-400 bg-purple-950/45 px-2 py-0.5 border border-purple-900/50 rounded font-mono">
                            {idx + 1}
                          </span>
                          <span className="text-xs text-neutral-450 break-all">
                            {src.startsWith('http') ? (
                              <a href={src} target="_blank" rel="noopener noreferrer" className="hover:text-purple-400 hover:underline">
                                {src}
                              </a>
                            ) : (
                              <span>Document reference: {src}</span>
                            )}
                          </span>
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
