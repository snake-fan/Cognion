import { Document, Page, pdfjs } from 'react-pdf'
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

export default ReaderWorkspace
