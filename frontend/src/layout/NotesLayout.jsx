import { useEffect, useMemo, useRef, useState } from 'react'
import FolderTree from '../components/FolderTree'
import MarkdownContent from '../components/MarkdownContent'
import { fetchPaperSessions } from '../services/api'

const USER_STATE_LABELS = {
  mentioned: '仅提及',
  exposed: '已接触',
  confused: '存在困惑',
  partial_understanding: '部分理解',
  understood: '基本理解',
  misaligned: '理解偏差'
}

const NOTES_LIST_DEFAULT_WIDTH = 400
const NOTES_LIST_MIN_WIDTH = 220
const NOTES_PREVIEW_MIN_WIDTH = 360
const NOTES_RESIZE_HANDLE_WIDTH = 8

function NotesLayout({
  loading,
  folders,
  notes,
  papers,
  sessions,
  selectedFolderName,
  selectedNote,
  activeFolderIds,
  onSelectFolder,
  onFolderDrop,
  onFolderDragStart,
  onRootDrop,
  onCreateFolder,
  onDeleteFolder,
  onRenameFolder,
  onCreateNote,
  onSelectNote,
  onSaveNote,
  onRenameNote,
  onDeleteNote,
  onNoteDragStart,
  folderCreateTarget,
  folderCreateName,
  folderCreateLoading,
  onFolderCreateNameChange,
  onCancelCreateFolder,
  onConfirmCreateFolder,
  deleteDialog,
  deleteDialogLoading,
  onCancelDeleteDialog,
  onConfirmDeleteDialog
}) {
  const [draftTitle, setDraftTitle] = useState('')
  const [draftContent, setDraftContent] = useState('')
  const [draftPaperId, setDraftPaperId] = useState('')
  const [draftSessionId, setDraftSessionId] = useState('')
  const [availableSessions, setAvailableSessions] = useState([])
  const [saveLoading, setSaveLoading] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [renamingNoteId, setRenamingNoteId] = useState(null)
  const [renameValue, setRenameValue] = useState('')
  const [renameLoading, setRenameLoading] = useState(false)
  const [notesListWidth, setNotesListWidth] = useState(NOTES_LIST_DEFAULT_WIDTH)
  const [isResizingNotes, setIsResizingNotes] = useState(false)
  const notesMainPanelRef = useRef(null)
  const paperTitleMap = useMemo(() => {
    return new Map((papers || []).map((paper) => [String(paper.id), paper.title || '未命名论文']))
  }, [papers])

  useEffect(() => {
    setDraftTitle(selectedNote?.title || '')
    setDraftContent(selectedNote?.content || '')
    setDraftPaperId(selectedNote?.paper_id ? String(selectedNote.paper_id) : '')
    setDraftSessionId(selectedNote?.session_id ? String(selectedNote.session_id) : '')
    setAvailableSessions(sessions || [])
    setEditMode(false)
  }, [selectedNote?.id])

  useEffect(() => {
    async function loadPaperSessions() {
      if (!draftPaperId) {
        setAvailableSessions([])
        return
      }

      try {
        const nextSessions = await fetchPaperSessions(draftPaperId)
        setAvailableSessions(nextSessions)
      } catch (error) {
        console.error(error)
        setAvailableSessions([])
      }
    }

    loadPaperSessions()
  }, [draftPaperId])

  const currentSessions = useMemo(() => {
    if (!draftPaperId) {
      return []
    }
    return availableSessions
  }, [availableSessions, draftPaperId])

  useEffect(() => {
    if (!isResizingNotes) {
      return undefined
    }

    function resizeNotesPanels(event) {
      const panel = notesMainPanelRef.current
      if (!panel) {
        return
      }

      const rect = panel.getBoundingClientRect()
      const maxWidth = Math.max(
        NOTES_LIST_MIN_WIDTH,
        rect.width - NOTES_PREVIEW_MIN_WIDTH - NOTES_RESIZE_HANDLE_WIDTH
      )
      const nextWidth = Math.min(Math.max(event.clientX - rect.left, NOTES_LIST_MIN_WIDTH), maxWidth)
      setNotesListWidth(nextWidth)
    }

    function stopResizingNotes() {
      setIsResizingNotes(false)
    }

    document.body.classList.add('notes-panel-resizing')
    window.addEventListener('mousemove', resizeNotesPanels)
    window.addEventListener('mouseup', stopResizingNotes)

    return () => {
      document.body.classList.remove('notes-panel-resizing')
      window.removeEventListener('mousemove', resizeNotesPanels)
      window.removeEventListener('mouseup', stopResizingNotes)
    }
  }, [isResizingNotes])

  async function onSaveDraft() {
    if (!selectedNote || saveLoading) {
      return
    }

    try {
      setSaveLoading(true)
      await onSaveNote(selectedNote.id, {
        title: draftTitle,
        content: draftContent,
        paperId: draftPaperId || null,
        sessionId: draftSessionId ? Number(draftSessionId) : null
      })
    } catch (error) {
      console.error(error)
      window.alert('保存笔记失败')
    } finally {
      setSaveLoading(false)
    }
  }

  function startRename(note) {
    setRenamingNoteId(note.id)
    setRenameValue(note.title || '')
  }

  function cancelRename() {
    if (renameLoading) {
      return
    }
    setRenamingNoteId(null)
    setRenameValue('')
  }

  async function submitRename(note) {
    const trimmed = renameValue.trim()
    if (!trimmed || renameLoading) {
      return
    }

    if (trimmed === note.title) {
      setRenamingNoteId(null)
      return
    }

    try {
      setRenameLoading(true)
      await onRenameNote(note.id, trimmed)
      setRenamingNoteId(null)
    } catch {
      // keep input for retry when request fails
    } finally {
      setRenameLoading(false)
    }
  }

  function getNoteSummary(note) {
    return note?.summary || note?.cognitive_state?.mental_model || ''
  }

  function getNoteStateLabel(note) {
    const state = note?.cognitive_state?.state
    return USER_STATE_LABELS[state] || ''
  }

  return (
    <main className="library-page notes-page">
      <section className="library-title-row">
        <h1 className="library-title">笔记</h1>
        <p className="library-subtitle">每条笔记可绑定 paper 与 session，用于后续快速跳转。</p>
      </section>

      {editMode && selectedNote ? (
        <section className="notes-edit-fullscreen">
          <div className="notes-editor-panel notes-editor-panel-fullscreen">
            <div className="notes-editor-toolbar">
              <input
                className="floating-create-input notes-title-input"
                value={draftTitle}
                onChange={(event) => setDraftTitle(event.target.value)}
                placeholder="笔记标题"
                readOnly={!editMode}
              />
              <select
                className="floating-create-input notes-select"
                value={draftPaperId}
                onChange={(event) => {
                  setDraftPaperId(event.target.value)
                  setDraftSessionId('')
                }}
                disabled={!editMode}
              >
                <option value="">不绑定论文</option>
                {draftPaperId && !paperTitleMap.has(draftPaperId) ? (
                  <option value={draftPaperId}>{`(ID: ${draftPaperId})`}</option>
                ) : null}
                {papers.map((paper) => (
                  <option key={paper.id} value={paper.id}>
                    #{paper.id} {paper.title}
                  </option>
                ))}
              </select>
              <select
                className="floating-create-input notes-select"
                value={draftSessionId}
                onChange={(event) => setDraftSessionId(event.target.value)}
                disabled={!editMode || !draftPaperId}
              >
                <option value="">不绑定会话</option>
                {currentSessions.map((session) => (
                  <option key={session.id} value={session.id}>
                    #{session.id} {session.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="floating-create-btn primary"
                onClick={onSaveDraft}
                disabled={!editMode || saveLoading}
              >
                {saveLoading ? '保存中...' : '保存'}
              </button>
              <button
                type="button"
                className="floating-create-btn"
                onClick={() => setEditMode((value) => !value)}
              >
                退出编辑
              </button>
            </div>
            <div className="notes-path-line">md 文件路径：{selectedNote.file_path}</div>
            <div className="notes-split-editor">
              <div className="notes-source-panel">
                <div className="notes-pane-title">Markdown 源码</div>
                <textarea
                  className="notes-textarea"
                  value={draftContent}
                  onChange={(event) => setDraftContent(event.target.value)}
                  placeholder="请输入 markdown 内容"
                />
              </div>
              <div className="notes-preview-panel markdown-body">
                <div className="notes-pane-title">渲染预览</div>
                <MarkdownContent>{draftContent || '暂无内容'}</MarkdownContent>
              </div>
            </div>
          </div>
        </section>
      ) : (
        <section className="library-workspace notes-workspace">
          <FolderTree
            folders={folders}
            activeFolderIds={activeFolderIds}
            onSelectFolder={onSelectFolder}
            onFolderDrop={onFolderDrop}
            onFolderDragStart={onFolderDragStart}
            onRootDrop={onRootDrop}
            onCreateFolder={onCreateFolder}
            onDeleteFolder={onDeleteFolder}
            onRenameFolder={onRenameFolder}
          />

          <section
            className={`notes-main-panel ${isResizingNotes ? 'resizing' : ''}`}
            ref={notesMainPanelRef}
            style={{ '--notes-list-width': `${notesListWidth}px` }}
          >
          <div className="notes-list-panel">
            <div className="notes-list-header">
              <span>当前目录：{selectedFolderName || '根目录'}</span>
              <button type="button" className="floating-create-btn primary" onClick={onCreateNote}>
                新建笔记
              </button>
            </div>
            {loading ? <div className="library-loading">正在加载笔记...</div> : null}
            <div className="notes-list-scroll">
              {notes.length === 0 ? <div className="project-empty">当前目录暂无笔记</div> : null}
              {notes.map((note) => (
                <div
                  key={note.id}
                  className={`note-list-item ${selectedNote?.id === note.id ? 'active' : ''}`}
                  draggable={renamingNoteId !== note.id}
                  onDragStart={(event) => {
                    if (renamingNoteId === note.id) {
                      event.preventDefault()
                      return
                    }
                    onNoteDragStart(event, note.id)
                  }}
                >
                  {renamingNoteId === note.id ? (
                    <input
                      className="note-rename-input"
                      value={renameValue}
                      autoFocus
                      onClick={(event) => event.stopPropagation()}
                      onChange={(event) => setRenameValue(event.target.value)}
                      onBlur={() => submitRename(note)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault()
                          submitRename(note)
                        }
                        if (event.key === 'Escape') {
                          event.preventDefault()
                          cancelRename()
                        }
                      }}
                      disabled={renameLoading}
                    />
                  ) : (
                    <button
                      type="button"
                      className="note-list-main"
                      onClick={() => onSelectNote(note.id)}
                      onDoubleClick={() => startRename(note)}
                    >
                      <div className="note-list-title">{note.title}</div>
                      <div className="note-list-meta">
                        {note.paper_id
                          ? `Paper ${paperTitleMap.get(String(note.paper_id)) || `(ID: ${note.paper_id})`}`
                          : '不绑定论文'}
                        {' | '}
                        {note.session_id ? `Session #${note.session_id}` : '不绑定会话'}
                        {getNoteStateLabel(note) ? ` | ${getNoteStateLabel(note)}` : ''}
                      </div>
                      {getNoteSummary(note) ? <div className="note-list-summary">{getNoteSummary(note)}</div> : null}
                    </button>
                  )}
                  <button type="button" className="session-delete-icon" onClick={() => onDeleteNote(note)}>
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div
            className="notes-panel-resize-handle"
            role="separator"
            aria-orientation="vertical"
            aria-label="调整笔记列表和预览区域宽度"
            onMouseDown={(event) => {
              event.preventDefault()
              setIsResizingNotes(true)
            }}
          />

          <div className="notes-editor-panel">
            {!selectedNote ? (
              <div className="empty-state">请选择一个笔记进行编辑</div>
            ) : (
              <>
                <div className="notes-editor-toolbar">
                  <input
                    className="floating-create-input notes-title-input"
                    value={draftTitle}
                    onChange={(event) => setDraftTitle(event.target.value)}
                    placeholder="笔记标题"
                    readOnly={!editMode}
                  />
                  <select
                    className="floating-create-input notes-select"
                    value={draftPaperId}
                    onChange={(event) => {
                      setDraftPaperId(event.target.value)
                      setDraftSessionId('')
                    }}
                    disabled={!editMode}
                  >
                    <option value="">不绑定论文</option>
                    {draftPaperId && !paperTitleMap.has(draftPaperId) ? (
                      <option value={draftPaperId}>{`(ID: ${draftPaperId})`}</option>
                    ) : null}
                    {papers.map((paper) => (
                      <option key={paper.id} value={paper.id}>
                        #{paper.id} {paper.title}
                      </option>
                    ))}
                  </select>
                  <select
                    className="floating-create-input notes-select"
                    value={draftSessionId}
                    onChange={(event) => setDraftSessionId(event.target.value)}
                    disabled={!editMode || !draftPaperId}
                  >
                    <option value="">不绑定会话</option>
                    {currentSessions.map((session) => (
                      <option key={session.id} value={session.id}>
                        #{session.id} {session.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="floating-create-btn primary"
                    onClick={onSaveDraft}
                    disabled={!editMode || saveLoading}
                  >
                    {saveLoading ? '保存中...' : '保存'}
                  </button>
                  <button
                    type="button"
                    className="floating-create-btn"
                    onClick={() => setEditMode((value) => !value)}
                  >
                    {editMode ? '退出编辑' : '进入编辑'}
                  </button>
                </div>
                <div className="notes-path-line">md 文件路径：{selectedNote.file_path}</div>
                {selectedNote.summary ? <div className="notes-path-line">摘要：{selectedNote.summary}</div> : null}
                {getNoteStateLabel(selectedNote) ? (
                  <div className="notes-path-line">
                    认知状态：{getNoteStateLabel(selectedNote)}
                    {typeof selectedNote.cognitive_state?.confidence === 'number'
                      ? ` · 信心 ${selectedNote.cognitive_state.confidence.toFixed(2)}`
                      : ''}
                  </div>
                ) : null}
                {Array.isArray(selectedNote.follow_up_questions) && selectedNote.follow_up_questions.length > 0 ? (
                  <div className="notes-path-line">
                    后续思考：{selectedNote.follow_up_questions.join(' / ')}
                  </div>
                ) : null}
                <div className="notes-preview-panel markdown-body notes-preview-only">
                  <MarkdownContent>{selectedNote.content || '暂无内容'}</MarkdownContent>
                </div>
              </>
            )}
          </div>
          </section>
        </section>
      )}

      {folderCreateTarget ? (
        <div className="floating-create-folder" role="dialog" aria-modal="true">
          <div className="floating-create-card">
            <div className="floating-create-title">
              {folderCreateTarget.id === null ? '新建根目录文件夹' : '新建子文件夹'}
            </div>
            <div className="floating-create-subtitle">父目录：{folderCreateTarget.name}</div>
            <input
              className="floating-create-input"
              value={folderCreateName}
              onChange={(event) => onFolderCreateNameChange(event.target.value)}
              placeholder="输入文件夹名称"
              autoFocus
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  onConfirmCreateFolder()
                }
                if (event.key === 'Escape') {
                  event.preventDefault()
                  onCancelCreateFolder()
                }
              }}
            />
            <div className="floating-create-actions">
              <button
                type="button"
                className="floating-create-btn"
                onClick={onCancelCreateFolder}
                disabled={folderCreateLoading}
              >
                取消
              </button>
              <button
                type="button"
                className="floating-create-btn primary"
                onClick={onConfirmCreateFolder}
                disabled={folderCreateLoading || !folderCreateName.trim()}
              >
                {folderCreateLoading ? '创建中...' : '确定'}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {deleteDialog ? (
        <div className="floating-confirm-delete" role="dialog" aria-modal="true">
          <div className="floating-confirm-card">
            <div className="floating-confirm-title">{deleteDialog.title}</div>
            <div className="floating-confirm-message">{deleteDialog.message}</div>
            <div className="floating-confirm-actions">
              <button
                type="button"
                className="floating-create-btn"
                onClick={onCancelDeleteDialog}
                disabled={deleteDialogLoading}
              >
                取消
              </button>
              <button
                type="button"
                className="floating-create-btn danger"
                onClick={onConfirmDeleteDialog}
                disabled={deleteDialogLoading}
              >
                {deleteDialogLoading ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  )
}

export default NotesLayout
