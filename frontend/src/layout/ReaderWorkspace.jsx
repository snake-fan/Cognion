import { Document, Page, pdfjs } from 'react-pdf'
import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeHighlight from 'rehype-highlight'
import WorkspaceLayout from './WorkspaceLayout'

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

function ReaderWorkspace({
  isResizing,
  rightCollapsed,
  onResizeHandleMouseDown,
  rightStyle,
  rightSidebarRef,
  leftSidebar,
  activeProject,
  zoom,
  onZoomOut,
  onZoomIn,
  onResetZoom,
  pdfUrl,
  onPdfLoadSuccess,
  numPages,
  pageWidth,
  onTextSelection,
  pdfPanelRef,
  setRightCollapsed,
  sessions,
  currentSessionId,
  sessionPanelMode,
  sessionNotes,
  focusedSessionNoteId,
  noteGenLoading,
  setSessionPanelMode,
  onGenerateSessionNotes,
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
  onAsk
}) {
  const [editingSessionId, setEditingSessionId] = useState(null)
  const [editingSessionName, setEditingSessionName] = useState('')
  const [pendingDeleteSessionId, setPendingDeleteSessionId] = useState(null)
  const [deletePopoverPosition, setDeletePopoverPosition] = useState(null)
  const deletePopoverRef = useRef(null)
  const sessionNoteItemRefs = useRef(new Map())

  useEffect(() => {
    if (sessionPanelMode !== 'list') {
      setEditingSessionId(null)
      setPendingDeleteSessionId(null)
      setDeletePopoverPosition(null)
    }
  }, [sessionPanelMode])

  useEffect(() => {
    function onDocumentPointerDown(event) {
      if (!deletePopoverRef.current) {
        return
      }
      if (deletePopoverRef.current.contains(event.target)) {
        return
      }
      setPendingDeleteSessionId(null)
    }

    document.addEventListener('pointerdown', onDocumentPointerDown)
    return () => {
      document.removeEventListener('pointerdown', onDocumentPointerDown)
    }
  }, [])

  const pendingDeleteSession = sessions.find((session) => session.id === pendingDeleteSessionId) || null

  function startRename(session) {
    setEditingSessionId(session.id)
    setEditingSessionName(session.name)
  }

  async function commitRename() {
    if (editingSessionId === null) {
      return
    }

    const targetSession = sessions.find((session) => session.id === editingSessionId)
    const trimmedName = editingSessionName.trim()

    if (!targetSession || !trimmedName || trimmedName === targetSession.name) {
      setEditingSessionId(null)
      setEditingSessionName('')
      return
    }

    try {
      await onRenameSession(editingSessionId, trimmedName)
    } catch {
      // Parent handler already reports errors.
    } finally {
      setEditingSessionId(null)
      setEditingSessionName('')
    }
  }

  function formatSessionTime(value) {
    if (!value) {
      return '暂无更新时间'
    }

    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
      return '暂无更新时间'
    }

    return parsed.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  function getNotePreview(content) {
    const plain = (content || '').replace(/^#+\s*/gm, '').replace(/\n+/g, ' ').trim()
    if (!plain) {
      return '暂无内容'
    }
    return plain.length > 88 ? `${plain.slice(0, 88)}...` : plain
  }

  useEffect(() => {
    if (!focusedSessionNoteId || sessionPanelMode !== 'note') {
      return
    }
    const element = sessionNoteItemRefs.current.get(focusedSessionNoteId)
    if (!element) {
      return
    }
    element.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [focusedSessionNoteId, sessionNotes, sessionPanelMode])

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
            <div className="title">
              {activeProject ? `Cognion · ${activeProject.title || activeProject.name}` : 'Cognion · 论文辅助阅读'}
            </div>
            <div className="center-actions">
              <div className="zoom-controls">
                <button className="zoom-button" onClick={onZoomOut} title="缩小">
                  -
                </button>
                <span className="zoom-value">{Math.round(zoom * 100)}%</span>
                <button className="zoom-button" onClick={onZoomIn} title="放大 (Ctrl/Cmd +)">
                  +
                </button>
                <button className="zoom-fit-button" onClick={onResetZoom} title="重置适配 (Ctrl/Cmd 0)">
                  适配
                </button>
              </div>
              <button
                className="right-sidebar-toggle"
                onClick={() => setRightCollapsed((value) => !value)}
                title={rightCollapsed ? '展开 Sessions 面板' : '收起 Sessions 面板'}
                aria-label={rightCollapsed ? '展开 Sessions 面板' : '收起 Sessions 面板'}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <rect x="3" y="4" width="18" height="16" rx="2" />
                  <path d="M14 4v16" />
                  {rightCollapsed ? <path d="M10 9l-3 3 3 3" /> : <path d="M7 9l3 3-3 3" />}
                </svg>
              </button>
            </div>
          </header>

          <section className="pdf-panel" onMouseUp={onTextSelection} ref={pdfPanelRef}>
            {pdfUrl ? (
              <Document file={pdfUrl} onLoadSuccess={onPdfLoadSuccess}>
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
        rightCollapsed ? null : (
          <>
            <div className="sidebar-header right-sidebar-nav">
              <button
                className={`session-header-button ${sessionPanelMode === 'list' ? 'active' : ''}`}
                onClick={() => setSessionPanelMode('list')}
              >
                Sessions
              </button>
              <button
                className={`session-header-button ${sessionPanelMode === 'summary' ? 'active' : ''}`}
                onClick={() => setSessionPanelMode('summary')}
              >
                Summary
              </button>
              <button
                className={`session-header-button ${sessionPanelMode === 'note' ? 'active' : ''}`}
                onClick={() => setSessionPanelMode('note')}
              >
                Note
              </button>
              <button
                className="session-generate-note-button"
                onClick={() => {
                  void onGenerateSessionNotes()
                }}
                disabled={noteGenLoading || sessionLoading || !currentSessionId}
                title="基于当前 Session 生成知识点笔记"
              >
                {noteGenLoading ? '生成中...' : '生成笔记'}
              </button>
            </div>

            {sessionPanelMode === 'list' ? (
              <div className="session-list-panel">
                <button className="session-create-button" onClick={onCreateSession} disabled={sessionLoading}>
                  + 新建 Session
                </button>
                <div className="session-list-scroll">
                  {sessions.length === 0 ? (
                    <div className="chat-empty">当前论文还没有 Session。</div>
                  ) : (
                    sessions.map((session) => (
                      <div
                        key={session.id}
                        className={`session-item ${session.id === currentSessionId ? 'active' : ''}`}
                      >
                        <button
                          className="session-item-main"
                          onClick={() => onSelectSession(session.id)}
                          disabled={sessionLoading}
                        >
                          {editingSessionId === session.id ? (
                            <input
                              autoFocus
                              className="session-name-input"
                              value={editingSessionName}
                              onChange={(event) => setEditingSessionName(event.target.value)}
                              onBlur={() => {
                                void commitRename()
                              }}
                              onKeyDown={(event) => {
                                if (event.key === 'Enter') {
                                  event.preventDefault()
                                  void commitRename()
                                  return
                                }
                                if (event.key === 'Escape') {
                                  event.preventDefault()
                                  setEditingSessionId(null)
                                  setEditingSessionName('')
                                }
                              }}
                              onClick={(event) => event.stopPropagation()}
                            />
                          ) : (
                            <span
                              className="session-item-name"
                              onClick={(event) => {
                                event.preventDefault()
                                event.stopPropagation()
                              }}
                              onDoubleClick={(event) => {
                                event.preventDefault()
                                event.stopPropagation()
                                startRename(session)
                              }}
                            >
                              {session.name}
                            </span>
                          )}
                          <span className="session-item-meta">更新于 {formatSessionTime(session.updated_at)}</span>
                        </button>
                        <div className="session-delete-wrap">
                          <button
                            className="session-delete-icon"
                            aria-label="删除 Session"
                            onClick={(event) => {
                              event.preventDefault()
                              event.stopPropagation()
                              const rect = event.currentTarget.getBoundingClientRect()
                              setPendingDeleteSessionId((prev) => {
                                if (prev === session.id) {
                                  setDeletePopoverPosition(null)
                                  return null
                                }
                                setDeletePopoverPosition({
                                  top: rect.top + rect.height / 2,
                                  left: rect.left - 12
                                })
                                return session.id
                              })
                            }}
                            disabled={sessionLoading}
                          >
                            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                              <path d="M9 4h6" />
                              <path d="M5 7h14" />
                              <path d="M7 7l1 12h8l1-12" />
                              <path d="M10 11v6" />
                              <path d="M14 11v6" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
                <button className="session-back-button" onClick={() => setSessionPanelMode('chat')}>
                  返回当前对话
                </button>
              </div>
            ) : sessionPanelMode === 'summary' ? (
              <div className="session-empty-panel" />
            ) : sessionPanelMode === 'note' ? (
              <div className="session-note-panel">
                {sessionNotes.length === 0 ? (
                  <div className="chat-empty">当前 Session 暂无笔记，点击右上角“生成笔记”。</div>
                ) : (
                  <div className="session-note-list">
                    {sessionNotes.map((note) => (
                      <article
                        key={note.id}
                        ref={(element) => {
                          if (!element) {
                            sessionNoteItemRefs.current.delete(note.id)
                            return
                          }
                          sessionNoteItemRefs.current.set(note.id, element)
                        }}
                        className={`session-note-card ${focusedSessionNoteId === note.id ? 'focused' : ''}`}
                      >
                        <h4>{note.title}</h4>
                        <p>{getNotePreview(note.content)}</p>
                        <span>{formatSessionTime(note.updated_at)}</span>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            ) : (
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

            {sessionPanelMode === 'list' && pendingDeleteSession && deletePopoverPosition ? (
              <div
                ref={deletePopoverRef}
                className="session-delete-popover fixed"
                style={{
                  top: `${deletePopoverPosition.top}px`,
                  left: `${deletePopoverPosition.left}px`
                }}
              >
                <div className="session-delete-text">确认删除?</div>
                <div className="session-delete-actions">
                  <button
                    className="session-delete-btn"
                    onClick={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      setPendingDeleteSessionId(null)
                      setDeletePopoverPosition(null)
                    }}
                    disabled={sessionLoading}
                  >
                    取消
                  </button>
                  <button
                    className="session-delete-btn danger"
                    onClick={async (event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      try {
                        await onDeleteSession(pendingDeleteSession.id)
                      } catch {
                        // Parent handler already reports errors.
                      } finally {
                        setPendingDeleteSessionId(null)
                        setDeletePopoverPosition(null)
                      }
                    }}
                    disabled={sessionLoading}
                  >
                    删除
                  </button>
                </div>
              </div>
            ) : null}
          </>
        )
      }
    />
  )
}

export default ReaderWorkspace
