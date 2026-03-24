import { useRef } from 'react'

function HomeUploadPanel({ onSelectFile }) {
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
          +
        </span>
        <span className="home-upload-text">点击上传 PDF 文件</span>
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
