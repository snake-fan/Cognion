const API_BASE = 'http://127.0.0.1:8000/api'

export async function askWithQuote({ question, quote, pdfFile }) {
  const formData = new FormData()
  formData.append('question', question)
  formData.append('quote', quote || '')
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
