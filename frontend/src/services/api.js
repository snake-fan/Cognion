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

export async function fetchPapers(folderId = null) {
  const search = new URLSearchParams()
  if (folderId !== null && folderId !== undefined) {
    search.set('folder_id', String(folderId))
  }

  const response = await fetch(`${API_BASE}/papers${search.toString() ? `?${search.toString()}` : ''}`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }

  const payload = await response.json()
  return payload.papers || []
}

export async function uploadPaper(pdfFile, folderId = null) {
  const formData = new FormData()
  formData.append('pdf_file', pdfFile)
  if (folderId !== null && folderId !== undefined) {
    formData.append('folder_id', String(folderId))
  }

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

export async function fetchFolderTree() {
  const response = await fetch(`${API_BASE}/folders/tree`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.folders || []
}

export async function createFolder(name, parentId = null) {
  const formData = new FormData()
  formData.append('name', name)
  if (parentId !== null && parentId !== undefined) {
    formData.append('parent_id', String(parentId))
  }

  const response = await fetch(`${API_BASE}/folders`, {
    method: 'POST',
    body: formData
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.folder
}

export async function deleteFolder(folderId) {
  const response = await fetch(`${API_BASE}/folders/${folderId}`, {
    method: 'DELETE'
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json()
}

export async function moveFolder(folderId, targetParentId = null) {
  const formData = new FormData()
  if (targetParentId !== null && targetParentId !== undefined) {
    formData.append('target_parent_id', String(targetParentId))
  }

  const response = await fetch(`${API_BASE}/folders/${folderId}/move`, {
    method: 'PATCH',
    body: formData
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.folder
}

export async function renameFolder(folderId, name) {
  const formData = new FormData()
  formData.append('name', name)

  const response = await fetch(`${API_BASE}/folders/${folderId}/rename`, {
    method: 'PATCH',
    body: formData
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.folder
}

export async function movePaper(paperId, targetFolderId = null) {
  const formData = new FormData()
  if (targetFolderId !== null && targetFolderId !== undefined) {
    formData.append('target_folder_id', String(targetFolderId))
  }

  const response = await fetch(`${API_BASE}/papers/${paperId}/move`, {
    method: 'PATCH',
    body: formData
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.paper
}

export async function deletePaper(paperId) {
  const response = await fetch(`${API_BASE}/papers/${paperId}`, {
    method: 'DELETE'
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json()
}
