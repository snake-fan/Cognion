import { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react'
import cognionLogo from './assets/cognion_logo_light.png'
import {
  askWithQuote,
  createPaperSession,
  createFolder,
  deletePaperSession,
  deleteFolder,
  deletePaper,
  fetchFolderTree,
  fetchPaperFile,
  fetchPaperMessages,
  fetchPaperSessions,
  fetchPapers,
  moveFolder,
  movePaper,
  renamePaperSession,
  renameFolder,
  uploadPaper
} from './services/api'

const PDF_PANEL_HORIZONTAL_PADDING = 28
const PRIMARY_NAV_ITEMS = [
  { key: 'library', label: '文献库', enabled: true },
  { key: 'knowledge', label: '知识库（预留）', enabled: false },
  { key: 'workspace', label: '工作流（预留）', enabled: false }
]

const NAV_ICONS = {
  library: (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H18a2 2 0 0 1 2 2v13.5a2.5 2.5 0 0 0-2.5-2.5H5.5A1.5 1.5 0 0 0 4 17.5z" />
      <path d="M4 17.5A1.5 1.5 0 0 1 5.5 16H18" />
      <path d="M8 7h7" />
      <path d="M8 10h7" />
    </svg>
  ),
  knowledge: (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="8.5" r="3.5" />
      <path d="M7 14.5a5 5 0 0 1 10 0" />
      <path d="M8 19h8" />
      <path d="M10 22h4" />
    </svg>
  ),
  workspace: (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <rect x="3" y="4" width="6" height="6" rx="1.2" />
      <rect x="15" y="4" width="6" height="6" rx="1.2" />
      <rect x="9" y="14" width="6" height="6" rx="1.2" />
      <path d="M9 7h6" />
      <path d="M12 10v4" />
    </svg>
  )
}

const HomeLayout = lazy(() => import('./layout/HomeLayout'))
const LibraryLayout = lazy(() => import('./layout/LibraryLayout'))
const WorkspaceLayout = lazy(() => import('./layout/WorkspaceLayout'))
const ReaderWorkspace = lazy(() => import('./layout/ReaderWorkspace'))

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
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [sessionPanelMode, setSessionPanelMode] = useState('chat')
  const [sessionLoading, setSessionLoading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [libraryLoading, setLibraryLoading] = useState(false)
  const [folders, setFolders] = useState([])
  const [selectedFolderId, setSelectedFolderId] = useState(null)
  const [folderCreateTarget, setFolderCreateTarget] = useState(null)
  const [folderCreateName, setFolderCreateName] = useState('')
  const [folderCreateLoading, setFolderCreateLoading] = useState(false)
  const [deleteDialog, setDeleteDialog] = useState(null)
  const [deleteDialogLoading, setDeleteDialogLoading] = useState(false)
  const composerRef = useRef(null)
  const messageListRef = useRef(null)
  const resizeLockRef = useRef(false)
  const rightSidebarRef = useRef(null)
  const dragWidthRef = useRef(380)
  const resizeRafRef = useRef(null)

  useEffect(() => {
    async function loadInitialData() {
      try {
        const [papers, folderTree] = await Promise.all([fetchPapers(), fetchFolderTree()])
        setProjects(papers)
        setFolders(folderTree)
      } catch {
        setProjects([])
        setFolders([])
      }
    }

    loadInitialData()
  }, [])

  async function refreshFolders() {
    try {
      const nextFolders = await fetchFolderTree()
      setFolders(nextFolders)
    } catch (error) {
      console.error(error)
    }
  }

  async function refreshPapers(folderId = selectedFolderId) {
    try {
      const nextPapers = await fetchPapers(folderId)
      setProjects(nextPapers)
    } catch (error) {
      console.error(error)
      setProjects([])
    }
  }

  async function onSelectFolder(folderId) {
    setSelectedFolderId(folderId)
    await refreshPapers(folderId)
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

  async function hydrateSessionsAndMessages(paperId, preferredSessionId = null) {
    setSessionLoading(true)
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
        const nextMessages = await fetchPaperMessages(paperId, resolvedSessionId)
        setMessages(nextMessages)
      } else {
        setMessages([])
      }
    } catch (error) {
      console.error(error)
      setSessions([])
      setCurrentSessionId(null)
      setMessages([])
    } finally {
      setSessionLoading(false)
    }
  }

  async function onLibraryUpload(file) {
    setLibraryLoading(true)
    try {
      const createdPaper = await uploadPaper(file, selectedFolderId)
      setProjects((prev) => [createdPaper, ...prev.filter((paper) => paper.id !== createdPaper.id)])
      setActiveProjectId(createdPaper.id)
      setMessages([])
      setSessions([])
      setCurrentSessionId(null)
      setSessionPanelMode('chat')
      setViewMode('workspace')
      loadPdfToWorkspace(file)
      await hydrateSessionsAndMessages(createdPaper.id)
    } catch (error) {
      console.error(error)
    } finally {
      setLibraryLoading(false)
    }
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

  function findFolderName(nodes, folderId) {
    for (const node of nodes) {
      if (node.id === folderId) {
        return node.name
      }
      if (node.children?.length) {
        const childHit = findFolderName(node.children, folderId)
        if (childHit) {
          return childHit
        }
      }
    }
    return null
  }

  const selectedFolderName = selectedFolderId === null ? '根目录' : findFolderName(folders, selectedFolderId)
  const activeFolderIds = selectedFolderId === null ? [] : [selectedFolderId]

  const leftSidebar = (
    <aside className={`left-sidebar ${leftCollapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <button className="logo-button" onClick={() => setLeftCollapsed((value) => !value)}>
          <img className="logo-image" src={cognionLogo} alt="Cognion" />
        </button>
      </div>
      <div className="sidebar-content">
        {PRIMARY_NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            className={`feature-item ${primaryLevel === item.key ? 'active' : ''} ${item.enabled ? '' : 'disabled'}`}
            onClick={() => onPrimaryNavClick(item.key, item.enabled)}
            title={item.label}
            aria-label={item.label}
          >
            <span className="feature-item-icon">{NAV_ICONS[item.key]}</span>
            {!leftCollapsed ? <span className="feature-item-label">{item.label}</span> : null}
          </button>
        ))}
      </div>
    </aside>
  )

  async function onOpenProject(projectId) {
    const selectedProject = projects.find((project) => project.id === projectId)
    if (!selectedProject) {
      return
    }

    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl)
    }

    setViewMode('workspace')
    setActiveProjectId(projectId)
    setMessages([])
    setSessions([])
    setCurrentSessionId(null)
    setSessionPanelMode('chat')
    setPdfFile(null)
    setPdfUrl(null)
    setNumPages(0)
    setZoom(1)
    setQuote('')
    setExpandedQuoteMessageIndex(null)
    clearPersistentHighlight()

    try {
      const pdfBlob = await fetchPaperFile(projectId)
      await hydrateSessionsAndMessages(projectId)

      const restoredFile = new File([pdfBlob], selectedProject.original_filename || 'paper.pdf', {
        type: 'application/pdf'
      })
      loadPdfToWorkspace(restoredFile)
    } catch (error) {
      console.error(error)
    }
  }

  async function onFolderDrop(event, targetFolderId) {
    event.preventDefault()
    const dragType = event.dataTransfer.getData('cognion-drag-type')
    const dragId = event.dataTransfer.getData('cognion-drag-id')
    if (!dragType || !dragId) {
      return
    }

    try {
      if (dragType === 'paper') {
        await movePaper(Number(dragId), targetFolderId)
        await refreshPapers(selectedFolderId)
      }

      if (dragType === 'folder') {
        await moveFolder(Number(dragId), targetFolderId)
        await refreshFolders()
        await refreshPapers(selectedFolderId)
      }
    } catch (error) {
      console.error(error)
      window.alert('拖拽移动失败')
    }
  }

  function onProjectDragStart(event, projectId) {
    event.dataTransfer.setData('cognion-drag-type', 'paper')
    event.dataTransfer.setData('cognion-drag-id', String(projectId))
  }

  function onFolderDragStart(event, folderId) {
    event.dataTransfer.setData('cognion-drag-type', 'folder')
    event.dataTransfer.setData('cognion-drag-id', String(folderId))
  }

  async function onRootDrop(event) {
    event.preventDefault()
    const dragType = event.dataTransfer.getData('cognion-drag-type')
    const dragId = event.dataTransfer.getData('cognion-drag-id')
    if (!dragType || !dragId) {
      return
    }

    try {
      if (dragType === 'paper') {
        await movePaper(Number(dragId), null)
        await refreshPapers(selectedFolderId)
      }
      if (dragType === 'folder') {
        await moveFolder(Number(dragId), null)
        await refreshFolders()
        await refreshPapers(selectedFolderId)
      }
    } catch (error) {
      console.error(error)
      window.alert('移动到根目录失败')
    }
  }

  async function onCreateFolder(parentFolder) {
    setFolderCreateTarget(parentFolder)
    setFolderCreateName('')
  }

  function onCancelCreateFolder() {
    if (folderCreateLoading) {
      return
    }
    setFolderCreateTarget(null)
    setFolderCreateName('')
  }

  async function onConfirmCreateFolder() {
    const trimmedName = folderCreateName.trim()
    if (!folderCreateTarget || !trimmedName || folderCreateLoading) {
      return
    }

    try {
      setFolderCreateLoading(true)
      await createFolder(trimmedName, folderCreateTarget.id)
      await refreshFolders()
      setFolderCreateTarget(null)
      setFolderCreateName('')
    } catch (error) {
      console.error(error)
      window.alert('新建子文件夹失败')
    } finally {
      setFolderCreateLoading(false)
    }
  }

  async function onDeleteFolder(folder) {
    setDeleteDialog({
      type: 'folder',
      payload: folder,
      title: `删除文件夹「${folder.name}」`,
      message: '这会连带删除其子目录、其中论文及数据库记录，操作不可恢复。'
    })
  }

  async function onRenameFolder(folderId, name) {
    const trimmedName = name.trim()
    if (!trimmedName) {
      return
    }

    try {
      await renameFolder(folderId, trimmedName)
      await refreshFolders()
      await refreshPapers(selectedFolderId)
    } catch (error) {
      console.error(error)
      window.alert('重命名失败')
      throw error
    }
  }

  async function onDeleteProject(project) {
    const projectTitle = project.title || project.name || '未命名论文'
    setDeleteDialog({
      type: 'project',
      payload: project,
      title: `删除论文「${projectTitle}」`,
      message: '将同时删除原文件、对话历史和数据库记录。'
    })
  }

  function onCancelDeleteDialog() {
    if (deleteDialogLoading) {
      return
    }
    setDeleteDialog(null)
  }

  async function onConfirmDeleteDialog() {
    if (!deleteDialog || deleteDialogLoading) {
      return
    }

    try {
      setDeleteDialogLoading(true)

      if (deleteDialog.type === 'folder') {
        const folder = deleteDialog.payload
        await deleteFolder(folder.id)
        if (selectedFolderId === folder.id || activeFolderIds.includes(folder.id)) {
          setSelectedFolderId(null)
          await refreshPapers(null)
        } else {
          await refreshPapers(selectedFolderId)
        }
        await refreshFolders()
      }

      if (deleteDialog.type === 'project') {
        const project = deleteDialog.payload
        await deletePaper(project.id)
        await refreshPapers(selectedFolderId)
        if (activeProjectId === project.id) {
          setActiveProjectId(null)
          setPdfFile(null)
          if (pdfUrl) {
            URL.revokeObjectURL(pdfUrl)
          }
          setPdfUrl(null)
          setMessages([])
          setSessions([])
          setCurrentSessionId(null)
          setSessionPanelMode('chat')
        }
      }

      setDeleteDialog(null)
    } catch (error) {
      console.error(error)
      window.alert('删除失败')
    } finally {
      setDeleteDialogLoading(false)
    }
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
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        content: trimmedQuestion,
        quote: attachedQuote,
        session_id: currentSessionId
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
        sessionId: currentSessionId
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

  async function onSelectSession(sessionId) {
    if (!activeProjectId) {
      return
    }

    setSessionLoading(true)
    try {
      const nextMessages = await fetchPaperMessages(activeProjectId, sessionId)
      setCurrentSessionId(sessionId)
      setMessages(nextMessages)
      setExpandedQuoteMessageIndex(null)
      setSessionPanelMode('chat')
    } catch (error) {
      console.error(error)
      window.alert('切换 Session 失败')
    } finally {
      setSessionLoading(false)
    }
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
        const nextMessages = await fetchPaperMessages(activeProjectId, nextSessionId)
        setMessages(nextMessages)
      } else {
        setMessages([])
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
    return (
      <Suspense fallback={<div className="empty-state">加载中...</div>}>
        <HomeLayout onEnterLibrary={() => setViewMode('library')} />
      </Suspense>
    )
  }

  if (viewMode === 'library') {
    return (
      <Suspense fallback={<div className="empty-state">加载中...</div>}>
        <WorkspaceLayout
          isResizing={false}
          showRightSidebar={false}
          leftSidebar={leftSidebar}
          centerContent={
            <LibraryLayout
              projects={projects}
              onSelectFile={onLibraryUpload}
              onOpenProject={onOpenProject}
              loading={libraryLoading}
              selectedFolderId={selectedFolderId}
              selectedFolderName={selectedFolderName}
              activeFolderIds={activeFolderIds}
              folders={folders}
              onSelectFolder={onSelectFolder}
              onFolderDrop={onFolderDrop}
              onFolderDragStart={onFolderDragStart}
              onRootDrop={onRootDrop}
              onProjectDragStart={onProjectDragStart}
              onCreateFolder={onCreateFolder}
              folderCreateTarget={folderCreateTarget}
              folderCreateName={folderCreateName}
              folderCreateLoading={folderCreateLoading}
              onFolderCreateNameChange={setFolderCreateName}
              onCancelCreateFolder={onCancelCreateFolder}
              onConfirmCreateFolder={onConfirmCreateFolder}
              onDeleteFolder={onDeleteFolder}
              onRenameFolder={onRenameFolder}
              onDeleteProject={onDeleteProject}
              deleteDialog={deleteDialog}
              deleteDialogLoading={deleteDialogLoading}
              onCancelDeleteDialog={onCancelDeleteDialog}
              onConfirmDeleteDialog={onConfirmDeleteDialog}
            />
          }
        />
      </Suspense>
    )
  }

  const activeProject = projects.find((project) => project.id === activeProjectId)

  return (
    <Suspense fallback={<div className="empty-state">加载中...</div>}>
      <ReaderWorkspace
        isResizing={isResizing}
        rightCollapsed={rightCollapsed}
        onResizeHandleMouseDown={onResizeHandleMouseDown}
        rightStyle={rightStyle}
        rightSidebarRef={rightSidebarRef}
        leftSidebar={leftSidebar}
        activeProject={activeProject}
        zoom={zoom}
        onZoomOut={zoomOut}
        onZoomIn={zoomIn}
        onResetZoom={resetZoom}
        pdfUrl={pdfUrl}
        onPdfLoadSuccess={({ numPages: nextNumPages }) => setNumPages(nextNumPages)}
        numPages={numPages}
        pageWidth={pageWidth}
        onTextSelection={onTextSelection}
        pdfPanelRef={pdfPanelRef}
        setRightCollapsed={setRightCollapsed}
        sessions={sessions}
        currentSessionId={currentSessionId}
        sessionPanelMode={sessionPanelMode}
        setSessionPanelMode={setSessionPanelMode}
        onSelectSession={onSelectSession}
        onCreateSession={onCreateSession}
        onRenameSession={onRenameSession}
        onDeleteSession={onDeleteSession}
        sessionLoading={sessionLoading}
        messages={messages}
        loading={loading}
        expandedQuoteMessageIndex={expandedQuoteMessageIndex}
        setExpandedQuoteMessageIndex={setExpandedQuoteMessageIndex}
        quote={quote}
        messageListRef={messageListRef}
        composerRef={composerRef}
        question={question}
        onComposerChange={onComposerChange}
        onComposerKeyDown={onComposerKeyDown}
        onAsk={onAsk}
      />
    </Suspense>
  )
}

export default App
