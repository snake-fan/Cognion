import { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react'
import {
  askWithQuote,
  createFolder,
  deleteFolder,
  deletePaper,
  fetchFolderTree,
  fetchPaperFile,
  fetchPaperMessages,
  fetchPapers,
  moveFolder,
  movePaper,
  renameFolder,
  uploadPaper
} from './services/api'

const PDF_PANEL_HORIZONTAL_PADDING = 28
const PRIMARY_NAV_ITEMS = [
  { key: 'library', label: '文献库', enabled: true },
  { key: 'knowledge', label: '知识库（预留）', enabled: false },
  { key: 'workspace', label: '工作流（预留）', enabled: false }
]

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

  async function onLibraryUpload(file) {
    setLibraryLoading(true)
    try {
      const createdPaper = await uploadPaper(file, selectedFolderId)
      setProjects((prev) => [createdPaper, ...prev.filter((paper) => paper.id !== createdPaper.id)])
      setActiveProjectId(createdPaper.id)
      setMessages([])
      setViewMode('workspace')
      loadPdfToWorkspace(file)
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
    setPdfFile(null)
    setPdfUrl(null)
    setNumPages(0)
    setZoom(1)
    setQuote('')
    setExpandedQuoteMessageIndex(null)
    clearPersistentHighlight()

    try {
      const [pdfBlob, paperMessages] = await Promise.all([
        fetchPaperFile(projectId),
        fetchPaperMessages(projectId)
      ])

      setMessages(paperMessages)

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
        pdfFile,
        paperId: activeProjectId
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
