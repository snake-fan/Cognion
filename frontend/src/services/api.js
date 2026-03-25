const API_BASE = 'http://127.0.0.1:8000/api'

export async function askWithQuote({ question, quote, pdfFile, paperId }) {
  const formData = new FormData()
  formData.append('question', question)
  formData.append('quote', quote || '')
  if (paperId) {
    formData.append('paper_id', String(paperId))
  }
  if (pdfFile) {
    formData.append('pdf_file', pdfFile)
  }

  const response = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    body: formData
  })

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }

  return response.json()
}

export async function fetchPapers() {
  const response = await fetch(`${API_BASE}/papers`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }

  const payload = await response.json()
  return payload.papers || []
}

export async function uploadPaper(pdfFile) {
  const formData = new FormData()
  formData.append('pdf_file', pdfFile)

  const response = await fetch(`${API_BASE}/papers/upload`, {
    method: 'POST',
    body: formData
  })

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }

  const payload = await response.json()
  return payload.paper
}

export async function fetchPaperFile(paperId) {
  const response = await fetch(`${API_BASE}/papers/${paperId}/file`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.blob()
}

export async function fetchPaperMessages(paperId) {
  const response = await fetch(`${API_BASE}/papers/${paperId}/messages`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.messages || []
}
