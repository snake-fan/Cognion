import { useEffect, useMemo, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { askWithQuote } from './services/api'

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

const FEATURE_ITEMS = ['AI 引用问答（当前）', '笔记整理（预留）', '术语解释（预留）']

function App() {
  const [activeFeature, setActiveFeature] = useState(FEATURE_ITEMS[0])
  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [rightWidth, setRightWidth] = useState(380)
  const [isResizing, setIsResizing] = useState(false)

  const [pdfFile, setPdfFile] = useState(null)
  const [pdfUrl, setPdfUrl] = useState(null)
  const [numPages, setNumPages] = useState(0)

  const [quote, setQuote] = useState('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    function onMouseMove(event) {
      if (!isResizing || rightCollapsed) {
        return
      }
      const maxWidth = 620
      const minWidth = 280
      const nextWidth = window.innerWidth - event.clientX
      const clamped = Math.max(minWidth, Math.min(maxWidth, nextWidth))
      setRightWidth(clamped)
    }

    function onMouseUp() {
      setIsResizing(false)
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)

    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [isResizing, rightCollapsed])

  useEffect(() => {
    return () => {
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl)
      }
    }
  }, [pdfUrl])

  function onUploadPdf(event) {
    const nextFile = event.target.files?.[0]
    if (!nextFile) {
      return
    }

    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl)
    }

    setPdfFile(nextFile)
    setPdfUrl(URL.createObjectURL(nextFile))
    setQuote('')
    setAnswer('')
  }

  function onTextSelection() {
    const selectedText = window.getSelection()?.toString().trim() || ''
    if (selectedText.length > 0) {
      setQuote(selectedText)
    }
  }

  async function onAsk() {
    if (!question.trim()) {
      return
    }

    setLoading(true)
    setAnswer('')

    try {
      const result = await askWithQuote({
        question,
        quote,
        pdfFile
      })
      setAnswer(result.answer)
    } catch (error) {
      setAnswer(`请求失败：${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const rightStyle = useMemo(() => {
    if (rightCollapsed) {
      return { width: 44 }
    }
    return { width: rightWidth }
  }, [rightCollapsed, rightWidth])

  return (
    <div className="app-shell">
      <aside className={`left-sidebar ${leftCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          <span>功能</span>
          <button onClick={() => setLeftCollapsed((value) => !value)}>
            {leftCollapsed ? '>' : '<'}
          </button>
        </div>
        {!leftCollapsed && (
          <div className="sidebar-content">
            {FEATURE_ITEMS.map((item) => (
              <button
                key={item}
                className={`feature-item ${activeFeature === item ? 'active' : ''}`}
                onClick={() => setActiveFeature(item)}
              >
                {item}
              </button>
            ))}
          </div>
        )}
      </aside>

      <main className="center-panel">
        <header className="center-header">
          <div className="title">Cognion · 论文辅助阅读</div>
          <label className="upload-button">
            载入 PDF
            <input type="file" accept="application/pdf" onChange={onUploadPdf} />
          </label>
        </header>

        <section className="pdf-panel" onMouseUp={onTextSelection}>
          {pdfUrl ? (
            <Document file={pdfUrl} onLoadSuccess={({ numPages }) => setNumPages(numPages)}>
              {Array.from(new Array(numPages), (_, index) => (
                <Page key={`page_${index + 1}`} pageNumber={index + 1} width={920} />
              ))}
            </Document>
          ) : (
            <div className="empty-state">请先上传论文 PDF 文件</div>
          )}
        </section>
      </main>

      {!rightCollapsed && <div className="resize-handle" onMouseDown={() => setIsResizing(true)} />}

      <aside className="right-sidebar" style={rightStyle}>
        <div className="sidebar-header">
          <span>AI 对话</span>
          <button onClick={() => setRightCollapsed((value) => !value)}>
            {rightCollapsed ? '<' : '>'}
          </button>
        </div>

        {rightCollapsed ? null : (
          <div className="chat-panel">
            <div className="field">
              <label>引用片段（从 PDF 选择后自动填充）</label>
              <textarea value={quote} onChange={(event) => setQuote(event.target.value)} rows={5} />
            </div>

            <div className="field">
              <label>询问</label>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                rows={4}
                placeholder="请输入你对引用片段的提问"
              />
            </div>

            <button className="ask-button" disabled={loading} onClick={onAsk}>
              {loading ? '分析中...' : '提交提问'}
            </button>

            <div className="answer-box">{answer || '回答会显示在这里。'}</div>
          </div>
        )}
      </aside>
    </div>
  )
}

export default App
