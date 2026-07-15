import { useRef } from 'react'

function HomeUploadPanel({ onSelectFile, label = '点击上传 PDF 文件' }) {
  const inputRef = useRef(null)

  function onFileChange(event) {
    const selectedFile = event.target.files?.[0]
    if (!selectedFile) {
      return
    }
    onSelectFile(selectedFile)
    event.target.value = ''
  }

  function onTriggerSelect() {
    inputRef.current?.click()
  }

  function onKeyDown(event) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onTriggerSelect()
    }
  }

  return (
    <>
      <button
        type="button"
        className="home-upload-panel"
        onClick={onTriggerSelect}
        onKeyDown={onKeyDown}
        aria-label="上传 PDF 文件"
      >
        <span className="home-upload-plus" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M12 16V4M7 9l5-5 5 5M5 14v5h14v-5" /></svg>
        </span>
        <span className="home-upload-text">{label}</span>
        <span className="home-upload-hint">点击选择 PDF 文件，开始新的阅读</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="home-upload-input"
        onChange={onFileChange}
      />
    </>
  )
}

export default HomeUploadPanel
