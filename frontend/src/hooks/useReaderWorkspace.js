import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  askWithQuote,
  createPaperSession,
  deletePaperSession,
  fetchPaperFile,
  fetchPaperMessages,
  fetchSessionNotes,
  fetchPaperSessions,
  generateSessionNotes,
  renamePaperSession
} from '../services/api'

const PDF_PANEL_HORIZONTAL_PADDING = 28
const CHAT_BOTTOM_THRESHOLD = 40

function useReaderWorkspace({ activeProjectId, setActiveProjectId }) {
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [rightWidth, setRightWidth] = useState(380)
  const [isResizing, setIsResizing] = useState(false)

  const [pdfFile, setPdfFile] = useState(null)
  const [pdfUrl, setPdfUrl] = useState(null)
  const [numPages, setNumPages] = useState(0)
  const [zoom, setZoom] = useState(1)
  const [panelWidth, setPanelWidth] = useState(920)
  const [pdfPanelElement, setPdfPanelElement] = useState(null)
  const pdfPanelRef = useRef(null)

  const [quote, setQuote] = useState('')
  const [expandedQuoteMessageIndex, setExpandedQuoteMessageIndex] = useState(null)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [sessionPanelMode, setSessionPanelMode] = useState('chat')
  const [sessionNotes, setSessionNotes] = useState([])
  const [noteGenLoading, setNoteGenLoading] = useState(false)
  const [sessionLoading, setSessionLoading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [showScrollToBottom, setShowScrollToBottom] = useState(false)

  const composerRef = useRef(null)
  const messageListRef = useRef(null)
  const shouldAutoScrollRef = useRef(true)
  const resizeLockRef = useRef(false)
  const rightSidebarRef = useRef(null)
  const dragWidthRef = useRef(380)
  const resizeRafRef = useRef(null)

  const updatePdfPanelRef = useCallback((element) => {
    pdfPanelRef.current = element
    setPdfPanelElement(element)
    if (element) {
      syncPanelWidth(element)
    }
  }, [])

  function measurePanelWidth(element = pdfPanelRef.current) {
    if (!element) {
      return null
    }

    return Math.max(320, Math.floor(element.clientWidth - PDF_PANEL_HORIZONTAL_PADDING))
  }

  function syncPanelWidth(element = pdfPanelRef.current) {
    const nextWidth = measurePanelWidth(element)
    if (nextWidth === null) {
      return null
    }

    setPanelWidth(nextWidth)
    return nextWidth
  }

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

  function clearReaderState({ clearPdf } = { clearPdf: true }) {
    setMessages([])
    setSessions([])
    setSessionNotes([])
    setCurrentSessionId(null)
    setSessionPanelMode('chat')
    setExpandedQuoteMessageIndex(null)
    setQuote('')
    setQuestion('')
    setLoading(false)
    setSessionLoading(false)
    shouldAutoScrollRef.current = true
    setShowScrollToBottom(false)
    clearPersistentHighlight()

    if (clearPdf) {
      setPdfFile(null)
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl)
      }
      setPdfUrl(null)
      setNumPages(0)
      setZoom(1)
    }
  }

  function onActiveProjectDeleted(deletedProjectId) {
    if (activeProjectId !== deletedProjectId) {
      return
    }

    setActiveProjectId(null)
    clearReaderState({ clearPdf: true })
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

      syncPanelWidth()

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
    if (!pdfPanelElement) {
      return
    }

    function updatePanelWidth() {
      if (resizeLockRef.current) {
        return
      }

      syncPanelWidth(pdfPanelElement)
    }

    updatePanelWidth()

    const resizeObserver = new ResizeObserver(updatePanelWidth)
    resizeObserver.observe(pdfPanelElement)

    return () => {
      resizeObserver.disconnect()
    }
  }, [pdfPanelElement])

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

  async function hydrateSessionsAndMessages(paperId, preferredSessionId = null) {
    setSessionLoading(true)
    shouldAutoScrollRef.current = true
    setShowScrollToBottom(false)
    try {
      const nextSessions = await fetchPaperSessions(paperId)
      setSessions(nextSessions)

      const resolvedSessionId =
        preferredSessionId && nextSessions.some((session) => session.id === preferredSessionId)
          ? preferredSessionId
          : (nextSessions[0]?.id ?? null)

      setCurrentSessionId(resolvedSessionId)
      setSessionPanelMode('chat')

      if (resolvedSessionId !== null) {
        const [nextMessages, nextNotes] = await Promise.all([
          fetchPaperMessages(paperId, resolvedSessionId),
          fetchSessionNotes(paperId, resolvedSessionId)
        ])
        setMessages(nextMessages)
        setSessionNotes(nextNotes)
      } else {
        setMessages([])
        setSessionNotes([])
      }
    } catch (error) {
      console.error(error)
      setSessions([])
      setCurrentSessionId(null)
      setMessages([])
      setSessionNotes([])
    } finally {
      setSessionLoading(false)
    }
  }

  async function refreshSessionNotes(paperId = activeProjectId, sessionId = currentSessionId) {
    if (!paperId || !sessionId) {
      setSessionNotes([])
      return
    }
    try {
      const nextNotes = await fetchSessionNotes(paperId, sessionId)
      setSessionNotes(nextNotes)
    } catch (error) {
      console.error(error)
      setSessionNotes([])
    }
  }

  async function openUploadedPaper(file, paperId, preferredSessionId = null) {
    setActiveProjectId(paperId)
    clearReaderState({ clearPdf: false })
    loadPdfToWorkspace(file)
    await hydrateSessionsAndMessages(paperId, preferredSessionId)
  }

  async function openExistingPaper(paperId, originalFilename = 'paper.pdf', preferredSessionId = null) {
    setActiveProjectId(paperId)
    clearReaderState({ clearPdf: true })

    const pdfBlob = await fetchPaperFile(paperId)
    await hydrateSessionsAndMessages(paperId, preferredSessionId)

    const restoredFile = new File([pdfBlob], originalFilename, {
      type: 'application/pdf'
    })
    loadPdfToWorkspace(restoredFile)
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
    if (!trimmedQuestion || !activeProjectId || !currentSessionId) {
      return
    }

    const attachedQuote = quote.trim()
    shouldAutoScrollRef.current = true
    setShowScrollToBottom(false)
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        content: trimmedQuestion,
        quote: attachedQuote,
        session_id: currentSessionId
      },
      {
        role: 'assistant',
        content: ''
      }
    ])
    setQuestion('')
    setLoading(true)

    try {
      const result = await askWithQuote({
        question: trimmedQuestion,
        quote,
        pdfFile,
        paperId: activeProjectId,
        sessionId: currentSessionId,
        onChunk: (fullText) => {
          setMessages((prev) => {
            if (prev.length === 0) {
              return prev
            }
            const next = [...prev]
            const lastIndex = next.length - 1
            if (next[lastIndex].role === 'assistant') {
              next[lastIndex] = { ...next[lastIndex], content: fullText }
              return next
            }
            return [...next, { role: 'assistant', content: fullText }]
          })
        }
      })
      if (typeof result?.answer === 'string') {
        setMessages((prev) => {
          if (prev.length === 0) {
            return prev
          }
          const next = [...prev]
          const lastIndex = next.length - 1
          if (next[lastIndex].role === 'assistant') {
            next[lastIndex] = { ...next[lastIndex], content: result.answer }
            return next
          }
          return [...next, { role: 'assistant', content: result.answer }]
        })
      }
    } catch (error) {
      setMessages((prev) => {
        const next = [...prev]
        const fallbackMessage = { role: 'assistant', content: `请求失败：${error.message}` }
        if (next.length && next[next.length - 1].role === 'assistant') {
          next[next.length - 1] = fallbackMessage
          return next
        }
        return [...next, fallbackMessage]
      })
    } finally {
      setLoading(false)
    }
  }

  function onComposerChange(event) {
    setQuestion(event.target.value)
  }

  function isMessageListNearBottom(element) {
    return element.scrollHeight - element.scrollTop - element.clientHeight <= CHAT_BOTTOM_THRESHOLD
  }

  function onMessageListScroll() {
    if (!messageListRef.current) {
      return
    }

    const nearBottom = isMessageListNearBottom(messageListRef.current)
    shouldAutoScrollRef.current = nearBottom
    setShowScrollToBottom(!nearBottom)
  }

  function scrollMessageListToBottom() {
    if (!messageListRef.current) {
      return
    }

    shouldAutoScrollRef.current = true
    setShowScrollToBottom(false)
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight
  }

  async function onSelectSession(sessionId) {
    if (!activeProjectId) {
      return
    }

    setSessionLoading(true)
    shouldAutoScrollRef.current = true
    setShowScrollToBottom(false)
    try {
      const [nextMessages, nextNotes] = await Promise.all([
        fetchPaperMessages(activeProjectId, sessionId),
        fetchSessionNotes(activeProjectId, sessionId)
      ])
      setCurrentSessionId(sessionId)
      setMessages(nextMessages)
      setSessionNotes(nextNotes)
      setExpandedQuoteMessageIndex(null)
      setSessionPanelMode('chat')
    } catch (error) {
      console.error(error)
      window.alert('切换 Session 失败')
    } finally {
      setSessionLoading(false)
    }
  }

  async function openPaperSession(paperId, sessionId, originalFilename = 'paper.pdf') {
    await openExistingPaper(paperId, originalFilename, sessionId)
    setSessionPanelMode('note')
  }

  async function onCreateSession() {
    if (!activeProjectId || sessionLoading) {
      return
    }

    setSessionLoading(true)
    try {
      const newSession = await createPaperSession(activeProjectId)
      setSessions((prev) => [newSession, ...prev])
      setCurrentSessionId(newSession.id)
      setMessages([])
      setSessionNotes([])
      setExpandedQuoteMessageIndex(null)
      setQuote('')
      clearPersistentHighlight()
      setSessionPanelMode('chat')
    } catch (error) {
      console.error(error)
      window.alert(`新建 Session 失败：${error?.message || '未知错误'}`)
    } finally {
      setSessionLoading(false)
    }
  }

  async function onRenameSession(sessionId, nextName) {
    if (!activeProjectId || sessionLoading) {
      return
    }

    const trimmedName = nextName.trim()
    if (!trimmedName) {
      return
    }

    setSessionLoading(true)
    try {
      const renamed = await renamePaperSession(activeProjectId, sessionId, trimmedName)
      setSessions((prev) =>
        prev.map((session) =>
          session.id === sessionId
            ? {
                ...session,
                ...renamed
              }
            : session
        )
      )
    } catch (error) {
      console.error(error)
      window.alert('重命名 Session 失败')
      throw error
    } finally {
      setSessionLoading(false)
    }
  }

  async function onDeleteSession(sessionId) {
    if (!activeProjectId || sessionLoading) {
      return
    }

    setSessionLoading(true)
    try {
      const result = await deletePaperSession(activeProjectId, sessionId)
      const nextSessions = await fetchPaperSessions(activeProjectId)
      setSessions(nextSessions)

      const nextSessionId =
        result.active_session_id && nextSessions.some((session) => session.id === result.active_session_id)
          ? result.active_session_id
          : (nextSessions[0]?.id ?? null)

      setCurrentSessionId(nextSessionId)

      if (nextSessionId !== null) {
        const [nextMessages, nextNotes] = await Promise.all([
          fetchPaperMessages(activeProjectId, nextSessionId),
          fetchSessionNotes(activeProjectId, nextSessionId)
        ])
        setMessages(nextMessages)
        setSessionNotes(nextNotes)
      } else {
        setMessages([])
        setSessionNotes([])
      }

      setExpandedQuoteMessageIndex(null)
      setQuote('')
      clearPersistentHighlight()
      setSessionPanelMode('list')
    } catch (error) {
      console.error(error)
      window.alert('删除 Session 失败')
      throw error
    } finally {
      setSessionLoading(false)
    }
  }

  function onComposerKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onAsk()
    }
  }

  async function onGenerateSessionNotes() {
    if (!activeProjectId || !currentSessionId || noteGenLoading || sessionLoading) {
      return
    }

    setNoteGenLoading(true)
    try {
      const result = await generateSessionNotes(activeProjectId, currentSessionId)
      const createdCount = Array.isArray(result?.created_notes) ? result.created_notes.length : 0
      const skippedCount = Array.isArray(result?.skipped_topics) ? result.skipped_topics.length : 0

      await refreshSessionNotes(activeProjectId, currentSessionId)
      window.dispatchEvent(new CustomEvent('cognion:notes-updated'))
      setSessionPanelMode('note')

      if (createdCount === 0) {
        window.alert('未生成新的知识点笔记，可能已与现有笔记重复。')
      } else if (skippedCount > 0) {
        window.alert(`已生成 ${createdCount} 条笔记，跳过 ${skippedCount} 条重复知识点。`)
      }
    } catch (error) {
      console.error(error)
      window.alert(`生成笔记失败：${error?.message || '未知错误'}`)
    } finally {
      setNoteGenLoading(false)
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
      return { width: 0, minWidth: 0, borderLeft: 'none', overflow: 'hidden' }
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
    syncPanelWidth()
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
    if (!shouldAutoScrollRef.current) {
      return
    }
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight
    setShowScrollToBottom(false)
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

  return {
    rightCollapsed,
    setRightCollapsed,
    isResizing,
    rightStyle,
    rightSidebarRef,
    onResizeHandleMouseDown,
    zoom,
    zoomIn,
    zoomOut,
    resetZoom,
    pdfUrl,
    numPages,
    setNumPages,
    pageWidth,
    onTextSelection,
    pdfPanelRef: updatePdfPanelRef,
    sessions,
    currentSessionId,
    sessionPanelMode,
    sessionNotes,
    noteGenLoading,
    setSessionPanelMode,
    onSelectSession,
    onCreateSession,
    onRenameSession,
    onDeleteSession,
    sessionLoading,
    messages,
    loading,
    expandedQuoteMessageIndex,
    setExpandedQuoteMessageIndex,
    quote,
    messageListRef,
    showScrollToBottom,
    onMessageListScroll,
    scrollMessageListToBottom,
    composerRef,
    question,
    onComposerChange,
    onComposerKeyDown,
    onGenerateSessionNotes,
    onAsk,
    openUploadedPaper,
    openExistingPaper,
    openPaperSession,
    onActiveProjectDeleted
  }
}

export default useReaderWorkspace
