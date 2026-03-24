import { useEffect, useMemo, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeHighlight from 'rehype-highlight'
import { askWithQuote } from './services/api'
import HomeLayout from './layout/HomeLayout'
import LibraryLayout from './layout/LibraryLayout'
import WorkspaceLayout from './layout/WorkspaceLayout'

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

const PDF_PANEL_HORIZONTAL_PADDING = 28
const PROJECTS_STORAGE_KEY = 'cognion.projects'
const PRIMARY_NAV_ITEMS = [
  { key: 'library', label: '文献库', enabled: true },
  { key: 'knowledge', label: '知识库（预留）', enabled: false },
  { key: 'workspace', label: '工作流（预留）', enabled: false }
]

function createProject(file) {
  const projectId =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`

  const now = new Date().toISOString()

  return {
    id: projectId,
    name: file.name,
    createdAt: now,
    updatedAt: now,
    messages: []
  }
}

function App() {
  const [viewMode, setViewMode] = useState('home')
  const [projects, setProjects] = useState([])
  const [activeProjectId, setActiveProjectId] = useState(null)

  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [rightWidth, setRightWidth] = useState(380)
  const [isResizing, setIsResizing] = useState(false)

  const [pdfFile, setPdfFile] = useState(null)
  const [pdfUrl, setPdfUrl] = useState(null)
  const [numPages, setNumPages] = useState(0)
  const [zoom, setZoom] = useState(1)
  const [panelWidth, setPanelWidth] = useState(920)
  const pdfPanelRef = useRef(null)

  const [quote, setQuote] = useState('')
  const [expandedQuoteMessageIndex, setExpandedQuoteMessageIndex] = useState(null)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const composerRef = useRef(null)
  const messageListRef = useRef(null)
  const resizeLockRef = useRef(false)
  const rightSidebarRef = useRef(null)
  const dragWidthRef = useRef(380)
  const resizeRafRef = useRef(null)

  useEffect(() => {
    const storedProjects = window.localStorage.getItem(PROJECTS_STORAGE_KEY)
    if (!storedProjects) {
      return
    }

    try {
      const parsedProjects = JSON.parse(storedProjects)
      if (!Array.isArray(parsedProjects)) {
        return
      }
      setProjects(parsedProjects)
    } catch {
      setProjects([])
    }
  }, [])

  useEffect(() => {
    window.localStorage.setItem(PROJECTS_STORAGE_KEY, JSON.stringify(projects))
  }, [projects])

  useEffect(() => {
    if (!activeProjectId) {
      return
    }

    setProjects((prev) =>
      prev.map((project) =>
        project.id === activeProjectId
          ? {
              ...project,
              messages,
              updatedAt: new Date().toISOString()
            }
          : project
      )
    )
  }, [activeProjectId, messages])

  function canUseCssHighlights() {
    return typeof CSS !== 'undefined' && 'highlights' in CSS && typeof window.Highlight !== 'undefined'
  }

  function setPersistentHighlight(range) {
    if (!canUseCssHighlights() || !range) {
      return
    }

    const highlight = new window.Highlight(range)
    CSS.highlights.set('pdf-selection', highlight)
  }

  function clearPersistentHighlight() {
    if (!canUseCssHighlights()) {
      return
    }

    CSS.highlights.delete('pdf-selection')
  }

  useEffect(() => {
    function onMouseMove(event) {
      if (!isResizing || rightCollapsed) {
        return
      }
      const maxWidth = window.innerWidth - PDF_PANEL_HORIZONTAL_PADDING - 1000
      const minWidth = 280
      const nextWidth = window.innerWidth - event.clientX
      const clamped = Math.max(minWidth, Math.min(maxWidth, nextWidth))
      dragWidthRef.current = clamped

      if (resizeRafRef.current !== null) {
        return
      }

      resizeRafRef.current = window.requestAnimationFrame(() => {
        if (rightSidebarRef.current && !rightCollapsed) {
          rightSidebarRef.current.style.width = `${dragWidthRef.current}px`
        }
        resizeRafRef.current = null
      })
    }

    function onMouseUp() {
      if (!isResizing) {
        return
      }

      if (resizeRafRef.current !== null) {
        window.cancelAnimationFrame(resizeRafRef.current)
        resizeRafRef.current = null
      }

      const committedWidth = dragWidthRef.current
      setRightWidth(committedWidth)

      if (rightSidebarRef.current && !rightCollapsed) {
        rightSidebarRef.current.style.width = `${committedWidth}px`
      }

      if (pdfPanelRef.current) {
        const nextWidth = Math.max(
          320,
          Math.floor(pdfPanelRef.current.clientWidth - PDF_PANEL_HORIZONTAL_PADDING)
        )
        setPanelWidth(nextWidth)
      }

      resizeLockRef.current = false
      setIsResizing(false)
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)

    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)

      if (resizeRafRef.current !== null) {
        window.cancelAnimationFrame(resizeRafRef.current)
        resizeRafRef.current = null
      }
    }
  }, [isResizing, rightCollapsed])

  useEffect(() => {
    if (!isResizing) {
      return
    }

    const prevCursor = document.body.style.cursor
    const prevUserSelect = document.body.style.userSelect
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    return () => {
      document.body.style.cursor = prevCursor
      document.body.style.userSelect = prevUserSelect
    }
  }, [isResizing])

  useEffect(() => {
    return () => {
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl)
      }
    }
  }, [pdfUrl])

  useEffect(() => {
    if (!pdfPanelRef.current) {
      return
    }

    const panelElement = pdfPanelRef.current

    function updatePanelWidth() {
      if (resizeLockRef.current) {
        return
      }

      const nextWidth = Math.max(320, Math.floor(panelElement.clientWidth - PDF_PANEL_HORIZONTAL_PADDING))
      setPanelWidth(nextWidth)
    }

    updatePanelWidth()

    const resizeObserver = new ResizeObserver(updatePanelWidth)
    resizeObserver.observe(panelElement)

    return () => {
      resizeObserver.disconnect()
    }
  }, [])

  function loadPdfToWorkspace(nextFile) {
    if (!nextFile) {
      return
    }

    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl)
    }

    setPdfFile(nextFile)
    setPdfUrl(URL.createObjectURL(nextFile))
    setNumPages(0)
    setZoom(1)
    setQuote('')
    setExpandedQuoteMessageIndex(null)
    clearPersistentHighlight()
  }

  function onLibraryUpload(file) {
    const nextProject = createProject(file)
    setProjects((prev) => [nextProject, ...prev])
    setActiveProjectId(nextProject.id)
    setMessages([])
    setViewMode('workspace')
    loadPdfToWorkspace(file)
  }

  function onPrimaryNavClick(itemKey, enabled) {
    if (!enabled) {
      return
    }

    if (itemKey === 'library') {
      setViewMode('library')
    }
  }

  const primaryLevel = viewMode === 'workspace' ? 'library' : viewMode

  const leftSidebar = (
    <aside className={`left-sidebar ${leftCollapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <button className="logo-button" onClick={() => setLeftCollapsed((value) => !value)}>
          <span>Cognion</span>
        </button>
      </div>
      {!leftCollapsed && (
        <div className="sidebar-content">
          {PRIMARY_NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              className={`feature-item ${primaryLevel === item.key ? 'active' : ''} ${item.enabled ? '' : 'disabled'}`}
              onClick={() => onPrimaryNavClick(item.key, item.enabled)}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </aside>
  )

  function onOpenProject(projectId) {
    const selectedProject = projects.find((project) => project.id === projectId)
    if (!selectedProject) {
      return
    }

    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl)
    }

    setViewMode('workspace')
    setActiveProjectId(projectId)
    setMessages(selectedProject.messages || [])
    setPdfFile(null)
    setPdfUrl(null)
    setNumPages(0)
    setZoom(1)
    setQuote('')
    setExpandedQuoteMessageIndex(null)
    clearPersistentHighlight()
  }

  function onTextSelection() {
    if (isResizing || resizeLockRef.current) {
      return
    }

    const selection = window.getSelection()
    const selectedText = selection?.toString().trim() || ''

    if (selectedText.length > 0) {
      setQuote(selectedText)
      if (selection && selection.rangeCount > 0) {
        setPersistentHighlight(selection.getRangeAt(0).cloneRange())
      }
      return
    }

    setQuote('')
    clearPersistentHighlight()
  }

  async function onAsk() {
    const trimmedQuestion = question.trim()
    if (!trimmedQuestion) {
      return
    }

    const attachedQuote = quote.trim()
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        content: trimmedQuestion,
        quote: attachedQuote
      }
    ])
    setQuestion('')
    setLoading(true)

    try {
      const result = await askWithQuote({
        question: trimmedQuestion,
        quote,
        pdfFile
      })
      setMessages((prev) => [...prev, { role: 'assistant', content: result.answer }])
    } catch (error) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `请求失败：${error.message}` }])
    } finally {
      setLoading(false)
    }
  }

  function onComposerChange(event) {
    setQuestion(event.target.value)
  }

  function onComposerKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onAsk()
    }
  }

  function onResizeHandleMouseDown() {
    resizeLockRef.current = true
    dragWidthRef.current = rightSidebarRef.current
      ? Math.floor(rightSidebarRef.current.getBoundingClientRect().width)
      : rightWidth
    setIsResizing(true)
  }

  const rightStyle = useMemo(() => {
    if (rightCollapsed) {
      return { width: 92 }
    }
    return { width: rightWidth }
  }, [rightCollapsed, rightWidth])

  const pageWidth = useMemo(() => {
    return Math.max(320, Math.floor(panelWidth * zoom))
  }, [panelWidth, zoom])

  function zoomIn() {
    setZoom((value) => Math.min(2.5, Number((value + 0.1).toFixed(1))))
  }

  function zoomOut() {
    setZoom((value) => Math.max(0.5, Number((value - 0.1).toFixed(1))))
  }

  function resetZoom() {
    setZoom(1)
  }

  useEffect(() => {
    function onKeyDown(event) {
      if (!(event.ctrlKey || event.metaKey)) {
        return
      }

      if (event.key === '+' || event.key === '=' || event.key === 'Add') {
        event.preventDefault()
        zoomIn()
        return
      }

      if (event.key === '-' || event.key === '_' || event.key === 'Subtract') {
        event.preventDefault()
        zoomOut()
        return
      }

      if (event.key === '0' || event.key === 'Numpad0') {
        event.preventDefault()
        resetZoom()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [])

  useEffect(() => {
    if (!composerRef.current) {
      return
    }

    const inputElement = composerRef.current
    inputElement.style.height = 'auto'
    const lineHeight = 24
    const maxHeight = lineHeight * 4
    inputElement.style.height = `${Math.min(inputElement.scrollHeight, maxHeight)}px`
    inputElement.style.overflowY = 'hidden'
  }, [question])

  useEffect(() => {
    if (!messageListRef.current) {
      return
    }
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight
  }, [messages, loading])

  useEffect(() => {
    if (expandedQuoteMessageIndex === null) {
      return
    }

    function onDocumentPointerDown(event) {
      const targetElement = event.target instanceof Element ? event.target : null
      if (targetElement?.closest('.message-quote-bubble')) {
        return
      }
      setExpandedQuoteMessageIndex(null)
    }

    document.addEventListener('pointerdown', onDocumentPointerDown)
    return () => {
      document.removeEventListener('pointerdown', onDocumentPointerDown)
    }
  }, [expandedQuoteMessageIndex])

  if (viewMode === 'home') {
    return <HomeLayout onEnterLibrary={() => setViewMode('library')} />
  }

  if (viewMode === 'library') {
    return (
      <WorkspaceLayout
        isResizing={false}
        showRightSidebar={false}
        leftSidebar={leftSidebar}
        centerContent={
          <LibraryLayout projects={projects} onSelectFile={onLibraryUpload} onOpenProject={onOpenProject} />
        }
      />
    )
  }

  const activeProject = projects.find((project) => project.id === activeProjectId)

  return (
    <WorkspaceLayout
      isResizing={isResizing}
      rightCollapsed={rightCollapsed}
      onResizeHandleMouseDown={onResizeHandleMouseDown}
      rightStyle={rightStyle}
      rightSidebarRef={rightSidebarRef}
      leftSidebar={leftSidebar}
      centerContent={
        <main className="center-panel">
          <header className="center-header">
            <div className="title">{activeProject ? `Cognion · ${activeProject.name}` : 'Cognion · 论文辅助阅读'}</div>
            <div className="center-actions">
              <div className="zoom-controls">
                <button className="zoom-button" onClick={zoomOut} title="缩小">
                  -
                </button>
                <span className="zoom-value">{Math.round(zoom * 100)}%</span>
                <button className="zoom-button" onClick={zoomIn} title="放大 (Ctrl/Cmd +)">
                  +
                </button>
                <button className="zoom-fit-button" onClick={resetZoom} title="重置适配 (Ctrl/Cmd 0)">
                  适配
                </button>
              </div>
            </div>
          </header>

          <section className="pdf-panel" onMouseUp={onTextSelection} ref={pdfPanelRef}>
            {pdfUrl ? (
              <Document file={pdfUrl} onLoadSuccess={({ numPages }) => setNumPages(numPages)}>
                {Array.from(new Array(numPages), (_, index) => (
                  <Page key={`page_${index + 1}`} pageNumber={index + 1} width={pageWidth} />
                ))}
              </Document>
            ) : (
              <div className="empty-state">该项目尚未载入 PDF，请从文献库上传后再进入阅读。</div>
            )}
          </section>
        </main>
      }
      rightSidebar={
        <>
          <div className="sidebar-header">
            <button className="logo-button sidebar-logo-button" onClick={() => setRightCollapsed((value) => !value)}>
              Agent
            </button>
          </div>

          {rightCollapsed ? null : (
            <div className="chat-panel">
              <div className="chat-messages" ref={messageListRef}>
                {messages.length === 0 ? (
                  <div className="chat-empty">从中间 PDF 选择内容，然后在下方直接提问。</div>
                ) : (
                  messages.map((message, index) => (
                    <div key={`${message.role}-${index}`} className={`chat-message ${message.role}`}>
                      {message.role === 'user' ? (
                        <div className="user-message-stack">
                          {message.quote ? (
                            <div
                              role="button"
                              tabIndex={0}
                              className={`message-quote-bubble ${expandedQuoteMessageIndex === index ? 'expanded selected' : 'collapsed'}`}
                              onClick={() => {
                                if (expandedQuoteMessageIndex !== index) {
                                  setExpandedQuoteMessageIndex(index)
                                }
                              }}
                              onKeyDown={(event) => {
                                if (event.key === 'Enter' || event.key === ' ') {
                                  event.preventDefault()
                                  setExpandedQuoteMessageIndex(index)
                                }
                              }}
                              title={expandedQuoteMessageIndex === index ? '点击其他区域可折叠引用' : '点击展开引用'}
                            >
                              {message.quote}
                            </div>
                          ) : null}
                          <div className="message-bubble">{message.content}</div>
                        </div>
                      ) : (
                        <div className="message-content markdown-body">
                          <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex, rehypeHighlight]}>
                            {message.content}
                          </ReactMarkdown>
                        </div>
                      )}
                    </div>
                  ))
                )}
                {loading ? <div className="assistant-thinking">思考中...</div> : null}
                <div className="chat-scroll-spacer" aria-hidden="true" />
              </div>

              {quote ? <div className="quote-chip">{quote}</div> : null}
              <div className="composer-wrap">
                <textarea
                  ref={composerRef}
                  className="composer-input"
                  value={question}
                  onChange={onComposerChange}
                  onKeyDown={onComposerKeyDown}
                  rows={1}
                  placeholder="输入你的问题..."
                />

                <button className="send-button" disabled={loading || !question.trim()} onClick={onAsk} title="发送">
                  <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                    <path d="M3 20L21 12L3 4V10L15 12L3 14V20Z" fill="currentColor" />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </>
      }
    />
  )
}

export default App
