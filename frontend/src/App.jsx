import { Suspense, lazy, useState } from 'react'
import cognionLogo from './assets/cognion_logo_light.png'
import SidebarNav from './components/SidebarNav'
import useLibraryData from './hooks/useLibraryData'
import useKnowledgeGraphData from './hooks/useKnowledgeGraphData'
import useNotesData from './hooks/useNotesData'
import useReaderWorkspace from './hooks/useReaderWorkspace'
import { uploadPaper } from './services/api'

const PRIMARY_NAV_ITEMS = [
  { key: 'library', label: '文献库', enabled: true },
  { key: 'notes', label: '笔记', enabled: true },
  { key: 'knowledge', label: '知识图谱', enabled: true },
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
  notes: (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M6 3.5h9l3 3V20a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 5 20V5A1.5 1.5 0 0 1 6.5 3.5z" />
      <path d="M15 3.5V7h3" />
      <path d="M8 10h8" />
      <path d="M8 13h8" />
      <path d="M8 16h5" />
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
const NotesLayout = lazy(() => import('./layout/NotesLayout'))
const KnowledgeGraphLayout = lazy(() => import('./layout/KnowledgeGraphLayout'))
const WorkspaceLayout = lazy(() => import('./layout/WorkspaceLayout'))
const ReaderWorkspace = lazy(() => import('./layout/ReaderWorkspace'))

function App() {
  const [viewMode, setViewMode] = useState('home')
  const [activeProjectId, setActiveProjectId] = useState(null)
  const [focusedSessionNoteId, setFocusedSessionNoteId] = useState(null)

  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const {
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
    pdfPanelRef,
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
  } = useReaderWorkspace({
    activeProjectId,
    setActiveProjectId
  })

  const {
    projects,
    setProjects,
    libraryLoading,
    setLibraryLoading,
    folders,
    refreshFolders,
    selectedFolderId,
    selectedFolderName,
    activeFolderIds,
    folderCreateTarget,
    folderCreateName,
    folderCreateLoading,
    deleteDialog,
    deleteDialogLoading,
    setFolderCreateName,
    onSelectFolder,
    onFolderDrop,
    onFolderDragStart,
    onRootDrop,
    onProjectDragStart,
    onCreateFolder,
    onCancelCreateFolder,
    onConfirmCreateFolder,
    onDeleteFolder,
    onRenameFolder,
    onDeleteProject,
    onCancelDeleteDialog,
    onConfirmDeleteDialog
  } = useLibraryData({
    activeProjectId,
    onActiveProjectDeleted
  })

  const {
    loading: notesLoading,
    folders: noteFolders,
    notes,
    papers: notePapers,
    sessions: noteSessions,
    selectedFolderName: selectedNoteFolderName,
    selectedNote,
    activeFolderIds: activeNoteFolderIds,
    folderCreateTarget: noteFolderCreateTarget,
    folderCreateName: noteFolderCreateName,
    folderCreateLoading: noteFolderCreateLoading,
    deleteDialog: noteDeleteDialog,
    deleteDialogLoading: noteDeleteDialogLoading,
    setFolderCreateName: setNoteFolderCreateName,
    onSelectFolder: onSelectNoteFolder,
    onSelectNote,
    openNoteById,
    onCreateNote,
    onSaveNote,
    onRenameNote,
    onDeleteNote,
    onFolderDrop: onNoteFolderDrop,
    onFolderDragStart: onNoteFolderDragStart,
    onRootDrop: onNoteRootDrop,
    onNoteDragStart,
    onCreateFolder: onCreateNoteFolder,
    onCancelCreateFolder: onCancelCreateNoteFolder,
    onConfirmCreateFolder: onConfirmCreateNoteFolder,
    onDeleteFolder: onDeleteNoteFolder,
    onRenameFolder: onRenameNoteFolder,
    onCancelDeleteDialog: onCancelNoteDeleteDialog,
    onConfirmDeleteDialog: onConfirmNoteDeleteDialog
  } = useNotesData({
    activePaperId: activeProjectId,
    activeSessionId: currentSessionId
  })

  const {
    loading: knowledgeLoading,
    query: knowledgeQuery,
    setQuery: setKnowledgeQuery,
    selectedPaperId: knowledgePaperFilter,
    setSelectedPaperId: setKnowledgePaperFilter,
    selectedSessionId: knowledgeSessionFilter,
    setSelectedSessionId: setKnowledgeSessionFilter,
    selectedUnitType: knowledgeUnitTypeFilter,
    setSelectedUnitType: setKnowledgeUnitTypeFilter,
    focusNeighborsOnly,
    setFocusNeighborsOnly,
    expansionDepth: knowledgeExpansionDepth,
    setExpansionDepth: setKnowledgeExpansionDepth,
    sortMode: knowledgeSortMode,
    setSortMode: setKnowledgeSortMode,
    unitTypeOptions: knowledgeUnitTypeOptions,
    units: knowledgeUnits,
    edges: knowledgeEdges,
    selectedUnit: selectedKnowledgeUnit,
    relatedNotes: knowledgeNotes,
    neighboringUnits: knowledgeNeighboringUnits,
    paperMap: knowledgePaperMap,
    sessionMap: knowledgeSessionMap,
    positions: knowledgePositions,
    neighborUnitIds,
    moveUnit: moveKnowledgeUnit,
    resetLayout: resetKnowledgeLayout,
    refreshGraph: refreshKnowledgeGraph,
    onSelectUnit: onSelectKnowledgeUnit
  } = useKnowledgeGraphData({
    isActive: viewMode === 'knowledge'
  })

  async function onLibraryUpload(file) {
    setLibraryLoading(true)
    try {
      const createdPaper = await uploadPaper(file, selectedFolderId)
      setProjects((prev) => [createdPaper, ...prev.filter((paper) => paper.id !== createdPaper.id)])
      await refreshFolders()
      setViewMode('workspace')
      await openUploadedPaper(file, createdPaper.id)
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

    if (itemKey === 'notes') {
      setViewMode('notes')
    }

    if (itemKey === 'knowledge') {
      refreshKnowledgeGraph()
      setViewMode('knowledge')
    }
  }

  const primaryLevel = viewMode

  const leftSidebar = (
    <SidebarNav
      collapsed={leftCollapsed}
      onToggleCollapsed={setLeftCollapsed}
      logoSrc={cognionLogo}
      items={PRIMARY_NAV_ITEMS}
      icons={NAV_ICONS}
      activeKey={primaryLevel}
      onItemClick={onPrimaryNavClick}
    />
  )

  async function onOpenProject(projectId) {
    const selectedProject = projects.find((project) => project.id === projectId)
    if (!selectedProject) {
      return
    }

    setViewMode('workspace')

    try {
      await openExistingPaper(projectId, selectedProject.original_filename || 'paper.pdf')
    } catch (error) {
      console.error(error)
    }
  }

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

  if (viewMode === 'notes') {
    return (
      <Suspense fallback={<div className="empty-state">加载中...</div>}>
        <WorkspaceLayout
          isResizing={false}
          showRightSidebar={false}
          leftSidebar={leftSidebar}
          centerContent={
            <NotesLayout
              loading={notesLoading}
              folders={noteFolders}
              notes={notes}
              papers={notePapers}
              sessions={noteSessions}
              selectedFolderName={selectedNoteFolderName}
              selectedNote={selectedNote}
              activeFolderIds={activeNoteFolderIds}
              onSelectFolder={onSelectNoteFolder}
              onFolderDrop={onNoteFolderDrop}
              onFolderDragStart={onNoteFolderDragStart}
              onRootDrop={onNoteRootDrop}
              onCreateFolder={onCreateNoteFolder}
              onDeleteFolder={onDeleteNoteFolder}
              onRenameFolder={onRenameNoteFolder}
              onCreateNote={onCreateNote}
              onSelectNote={onSelectNote}
              onSaveNote={onSaveNote}
              onRenameNote={onRenameNote}
              onDeleteNote={onDeleteNote}
              onNoteDragStart={onNoteDragStart}
              folderCreateTarget={noteFolderCreateTarget}
              folderCreateName={noteFolderCreateName}
              folderCreateLoading={noteFolderCreateLoading}
              onFolderCreateNameChange={setNoteFolderCreateName}
              onCancelCreateFolder={onCancelCreateNoteFolder}
              onConfirmCreateFolder={onConfirmCreateNoteFolder}
              deleteDialog={noteDeleteDialog}
              deleteDialogLoading={noteDeleteDialogLoading}
              onCancelDeleteDialog={onCancelNoteDeleteDialog}
              onConfirmDeleteDialog={onConfirmNoteDeleteDialog}
            />
          }
        />
      </Suspense>
    )
  }

  if (viewMode === 'knowledge') {
    return (
      <Suspense fallback={<div className="empty-state">加载中...</div>}>
        <WorkspaceLayout
          isResizing={false}
          showRightSidebar={false}
          leftSidebar={leftSidebar}
          centerContent={
            <KnowledgeGraphLayout
              loading={knowledgeLoading}
              query={knowledgeQuery}
              onQueryChange={setKnowledgeQuery}
              selectedPaperId={knowledgePaperFilter}
              onPaperFilterChange={setKnowledgePaperFilter}
              selectedSessionId={knowledgeSessionFilter}
              onSessionFilterChange={setKnowledgeSessionFilter}
              selectedUnitType={knowledgeUnitTypeFilter}
              onUnitTypeFilterChange={setKnowledgeUnitTypeFilter}
              focusNeighborsOnly={focusNeighborsOnly}
              onFocusNeighborsToggle={setFocusNeighborsOnly}
              expansionDepth={knowledgeExpansionDepth}
              onExpansionDepthChange={setKnowledgeExpansionDepth}
              sortMode={knowledgeSortMode}
              onSortModeChange={setKnowledgeSortMode}
              unitTypeOptions={knowledgeUnitTypeOptions}
              units={knowledgeUnits}
              edges={knowledgeEdges}
              positions={knowledgePositions}
              selectedUnit={selectedKnowledgeUnit}
              relatedNotes={knowledgeNotes}
              neighboringUnits={knowledgeNeighboringUnits}
              paperMap={knowledgePaperMap}
              sessionMap={knowledgeSessionMap}
              neighborUnitIds={neighborUnitIds}
              onSelectUnit={onSelectKnowledgeUnit}
              onMoveUnit={moveKnowledgeUnit}
              onResetLayout={resetKnowledgeLayout}
              onOpenNote={async (noteId) => {
                setViewMode('notes')
                await openNoteById(noteId)
              }}
              onOpenSession={async (note) => {
                if (!note?.paper_id || !note?.session_id) {
                  return
                }
                setFocusedSessionNoteId(note.id)
                setViewMode('workspace')
                const paper = knowledgePaperMap.get(note.paper_id)
                await openPaperSession(note.paper_id, note.session_id, paper?.original_filename || 'paper.pdf')
              }}
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
        sessionNotes={sessionNotes}
        focusedSessionNoteId={focusedSessionNoteId}
        noteGenLoading={noteGenLoading}
        setSessionPanelMode={setSessionPanelMode}
        onGenerateSessionNotes={onGenerateSessionNotes}
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
