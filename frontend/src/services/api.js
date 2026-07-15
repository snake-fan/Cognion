const API_BASE = import.meta.env.VITE_API_BASE || '/api'
let accessToken = null
let refreshPromise = null

export function setAccessToken(token) {
  accessToken = token || null
}

async function readError(response) {
  try {
    const payload = await response.json()
    return payload?.detail || `Request failed: ${response.status}`
  } catch {
    return `Request failed: ${response.status}`
  }
}

async function nativeFetch(path, options = {}) {
  return window.fetch(path, { credentials: 'include', ...options })
}

export async function refreshSession() {
  if (!refreshPromise) {
    refreshPromise = nativeFetch(`${API_BASE}/auth/refresh`, { method: 'POST' })
      .then(async (response) => {
        if (!response.ok) {
          setAccessToken(null)
          throw new Error(await readError(response))
        }
        const payload = await response.json()
        setAccessToken(payload.access_token)
        return payload.user
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

export async function apiFetch(path, options = {}, retry = true) {
  const headers = new Headers(options.headers || {})
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }
  const response = await nativeFetch(path, { ...options, headers })
  if (response.status !== 401 || !retry || String(path).includes('/auth/')) {
    return response
  }
  try {
    await refreshSession()
  } catch {
    window.dispatchEvent(new CustomEvent('cognion:auth-expired'))
    return response
  }
  return apiFetch(path, options, false)
}

async function authJson(path, body) {
  const response = await nativeFetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.status === 204 ? null : response.json()
}

export async function registerUser(email, password) {
  return authJson('/auth/register', { email, password })
}

export async function verifyEmail(token) {
  const payload = await authJson('/auth/verify-email', { token })
  setAccessToken(payload.access_token)
  return payload.user
}

export async function verifyEmailCode(email, code) {
  const payload = await authJson('/auth/verify-email-code', { email, code })
  setAccessToken(payload.access_token)
  return payload.user
}

export async function resendVerification(email) {
  return authJson('/auth/resend-verification', { email })
}

export async function loginUser(email, password) {
  const payload = await authJson('/auth/login', { email, password })
  setAccessToken(payload.access_token)
  return payload.user
}

export async function logoutUser() {
  await nativeFetch(`${API_BASE}/auth/logout`, { method: 'POST' })
  setAccessToken(null)
}

export async function forgotPassword(email) {
  return authJson('/auth/forgot-password', { email })
}

export async function resetPassword(token, newPassword) {
  return authJson('/auth/reset-password', { token, new_password: newPassword })
}

export async function updateUserMetadata(metadata) {
  const response = await apiFetch(`${API_BASE}/users/me/metadata`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(metadata)
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function changeUserPassword(currentPassword, newPassword) {
  const response = await apiFetch(`${API_BASE}/users/me/change-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function deleteUserAccount(password) {
  const response = await apiFetch(`${API_BASE}/users/me`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password })
  })
  if (!response.ok) throw new Error(await readError(response))
  setAccessToken(null)
  return response.json()
}

export async function askWithQuote({ question, quote, pdfFile, paperId, sessionId, onChunk }) {
  const formData = new FormData()
  formData.append('question', question)
  formData.append('quote', quote || '')
  formData.append('stream', '1')
  if (paperId) {
    formData.append('paper_id', String(paperId))
  }
  if (sessionId) {
    formData.append('session_id', String(sessionId))
  }
  if (pdfFile) {
    formData.append('pdf_file', pdfFile)
  }

  const response = await apiFetch(`${API_BASE}/ask`, {
    method: 'POST',
    body: formData
  })

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }

  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('text/event-stream') || !response.body) {
    return response.json()
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let fullAnswer = ''
  let donePayload = null

  function handleEventBlock(block) {
    const lines = block.split('\n')
    let eventName = 'message'
    const dataLines = []

    for (const rawLine of lines) {
      const line = rawLine.trimEnd()
      if (!line) {
        continue
      }
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim()
        continue
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }

    if (dataLines.length === 0) {
      return
    }

    const dataText = dataLines.join('\n')
    let payload = {}
    try {
      payload = JSON.parse(dataText)
    } catch {
      payload = { delta: dataText }
    }

    if (eventName === 'chunk') {
      const delta = typeof payload.delta === 'string' ? payload.delta : ''
      if (!delta) {
        return
      }
      fullAnswer += delta
      if (typeof onChunk === 'function') {
        onChunk(fullAnswer, delta)
      }
      return
    }

    if (eventName === 'done') {
      donePayload = payload
      if (typeof payload.answer === 'string') {
        fullAnswer = payload.answer
        if (typeof onChunk === 'function') {
          onChunk(fullAnswer, '')
        }
      }
      return
    }

    if (eventName === 'error') {
      const detail = typeof payload.detail === 'string' && payload.detail ? payload.detail : 'Stream failed'
      throw new Error(detail)
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })

    let separatorIndex = buffer.indexOf('\n\n')
    while (separatorIndex !== -1) {
      const block = buffer.slice(0, separatorIndex)
      buffer = buffer.slice(separatorIndex + 2)
      handleEventBlock(block)
      separatorIndex = buffer.indexOf('\n\n')
    }

    if (done) {
      break
    }
  }

  if (buffer.trim()) {
    handleEventBlock(buffer)
  }

  return { answer: fullAnswer, session: donePayload?.session || null }
}

export async function fetchPapers(folderId = null, { includeAll = false } = {}) {
  const search = new URLSearchParams()
  if (includeAll) {
    search.set('include_all', '1')
  }
  if (folderId !== null && folderId !== undefined) {
    search.set('folder_id', String(folderId))
  }

  const response = await apiFetch(`${API_BASE}/papers${search.toString() ? `?${search.toString()}` : ''}`)
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

  const response = await apiFetch(`${API_BASE}/papers/upload`, {
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
  const response = await apiFetch(`${API_BASE}/papers/${paperId}/file`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.blob()
}

export async function fetchPaperMessages(paperId, sessionId = null) {
  const search = new URLSearchParams()
  if (sessionId !== null && sessionId !== undefined) {
    search.set('session_id', String(sessionId))
  }

  const response = await apiFetch(
    `${API_BASE}/papers/${paperId}/messages${search.toString() ? `?${search.toString()}` : ''}`
  )
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.messages || []
}

export async function fetchPaperSessions(paperId) {
  const response = await apiFetch(`${API_BASE}/papers/${paperId}/sessions`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.sessions || []
}

export async function createPaperSession(paperId, name = '') {
  const trimmedName = name.trim()
  const requestInit = { method: 'POST' }

  if (trimmedName) {
    const formData = new FormData()
    formData.append('name', trimmedName)
    requestInit.body = formData
  }

  const response = await apiFetch(`${API_BASE}/papers/${paperId}/sessions`, requestInit)
  if (!response.ok) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = payload?.detail ? ` - ${payload.detail}` : ''
    } catch {
      detail = ''
    }
    throw new Error(`Create session failed: ${response.status}${detail}`)
  }
  const payload = await response.json()
  return payload.session
}

export async function renamePaperSession(paperId, sessionId, name) {
  const formData = new FormData()
  formData.append('name', name)

  const response = await apiFetch(`${API_BASE}/papers/${paperId}/sessions/${sessionId}`, {
    method: 'PATCH',
    body: formData
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.session
}

export async function deletePaperSession(paperId, sessionId) {
  const response = await apiFetch(`${API_BASE}/papers/${paperId}/sessions/${sessionId}`, {
    method: 'DELETE'
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json()
}

export async function fetchSessionNotes(paperId, sessionId) {
  const response = await apiFetch(`${API_BASE}/papers/${paperId}/sessions/${sessionId}/notes`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.notes || []
}

export async function generateSessionNotes(paperId, sessionId, { folderId = null, maxPoints = null } = {}) {
  const search = new URLSearchParams()
  if (folderId !== null && folderId !== undefined) {
    search.set('folder_id', String(folderId))
  }
  if (maxPoints !== null && maxPoints !== undefined) {
    search.set('max_points', String(maxPoints))
  }

  const query = search.toString()

  const response = await apiFetch(
    `${API_BASE}/papers/${paperId}/sessions/${sessionId}/notes/generate${query ? `?${query}` : ''}`,
    {
      method: 'POST'
    }
  )

  if (!response.ok) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = payload?.detail ? ` - ${payload.detail}` : ''
    } catch {
      detail = ''
    }
    throw new Error(`Generate session notes failed: ${response.status}${detail}`)
  }

  return response.json()
}

export async function fetchSessionNoteGenerationStatus(paperId, sessionId) {
  const response = await apiFetch(`${API_BASE}/papers/${paperId}/sessions/${sessionId}/notes/generate/status`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json()
}

export async function fetchFolderTree() {
  const response = await apiFetch(`${API_BASE}/folders/tree`)
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

  const response = await apiFetch(`${API_BASE}/folders`, {
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
  const response = await apiFetch(`${API_BASE}/folders/${folderId}`, {
    method: 'DELETE'
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json()
}

export async function moveFolder(folderId, targetParentId = null) {
  const requestInit = { method: 'PATCH' }
  if (targetParentId !== null && targetParentId !== undefined) {
    const formData = new FormData()
    formData.append('target_parent_id', String(targetParentId))
    requestInit.body = formData
  }

  const response = await apiFetch(`${API_BASE}/folders/${folderId}/move`, requestInit)
  if (!response.ok) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = payload?.detail ? ` - ${payload.detail}` : ''
    } catch {
      detail = ''
    }
    throw new Error(`Request failed: ${response.status}${detail}`)
  }
  const payload = await response.json()
  return payload.folder
}

export async function renameFolder(folderId, name) {
  const formData = new FormData()
  formData.append('name', name)

  const response = await apiFetch(`${API_BASE}/folders/${folderId}/rename`, {
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
  const requestInit = { method: 'PATCH' }
  if (targetFolderId !== null && targetFolderId !== undefined) {
    const formData = new FormData()
    formData.append('target_folder_id', String(targetFolderId))
    requestInit.body = formData
  }

  const response = await apiFetch(`${API_BASE}/papers/${paperId}/move`, requestInit)
  if (!response.ok) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = payload?.detail ? ` - ${payload.detail}` : ''
    } catch {
      detail = ''
    }
    throw new Error(`Request failed: ${response.status}${detail}`)
  }
  const payload = await response.json()
  return payload.paper
}

export async function deletePaper(paperId) {
  const response = await apiFetch(`${API_BASE}/papers/${paperId}`, {
    method: 'DELETE'
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json()
}

export async function fetchNoteFolderTree() {
  const response = await apiFetch(`${API_BASE}/notes/folders/tree`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.folders || []
}

export async function createNoteFolder(name, parentId = null) {
  const formData = new FormData()
  formData.append('name', name)
  if (parentId !== null && parentId !== undefined) {
    formData.append('parent_id', String(parentId))
  }

  const response = await apiFetch(`${API_BASE}/notes/folders`, {
    method: 'POST',
    body: formData
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.folder
}

export async function moveNoteFolder(folderId, targetParentId = null) {
  const requestInit = { method: 'PATCH' }
  if (targetParentId !== null && targetParentId !== undefined) {
    const formData = new FormData()
    formData.append('target_parent_id', String(targetParentId))
    requestInit.body = formData
  }

  const response = await apiFetch(`${API_BASE}/notes/folders/${folderId}/move`, requestInit)
  if (!response.ok) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = payload?.detail ? ` - ${payload.detail}` : ''
    } catch {
      detail = ''
    }
    throw new Error(`Request failed: ${response.status}${detail}`)
  }
  const payload = await response.json()
  return payload.folder
}

export async function renameNoteFolder(folderId, name) {
  const formData = new FormData()
  formData.append('name', name)

  const response = await apiFetch(`${API_BASE}/notes/folders/${folderId}/rename`, {
    method: 'PATCH',
    body: formData
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const payload = await response.json()
  return payload.folder
}

export async function deleteNoteFolder(folderId) {
  const response = await apiFetch(`${API_BASE}/notes/folders/${folderId}`, {
    method: 'DELETE'
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json()
}

export async function fetchNotes(folderId = null) {
  const search = new URLSearchParams()
  if (folderId !== null && folderId !== undefined) {
    search.set('folder_id', String(folderId))
  }

  const response = await apiFetch(`${API_BASE}/notes${search.toString() ? `?${search.toString()}` : ''}`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }

  const payload = await response.json()
  return payload.notes || []
}

export async function fetchKnowledgeGraph() {
  const response = await apiFetch(`${API_BASE}/knowledge-graph`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }

  return response.json()
}

export async function createNote({ title, content = '', folderId = null, paperId = null, sessionId = null }) {
  const formData = new FormData()
  formData.append('title', title)
  formData.append('content', content)
  if (folderId !== null && folderId !== undefined) {
    formData.append('folder_id', String(folderId))
  }
  if (paperId !== null && paperId !== undefined) {
    formData.append('paper_id', String(paperId))
  }
  if (sessionId !== null && sessionId !== undefined) {
    formData.append('session_id', String(sessionId))
  }

  const response = await apiFetch(`${API_BASE}/notes`, {
    method: 'POST',
    body: formData
  })
  if (!response.ok) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = payload?.detail ? ` - ${payload.detail}` : ''
    } catch {
      detail = ''
    }
    throw new Error(`Request failed: ${response.status}${detail}`)
  }

  const payload = await response.json()
  return payload.note
}

export async function updateNote(noteId, { title, content, paperId, sessionId }) {
  const formData = new FormData()
  if (title !== undefined) {
    formData.append('title', title)
  }
  if (content !== undefined) {
    formData.append('content', content)
  }
  if (paperId !== undefined) {
    formData.append('paper_id', String(paperId === null ? 0 : paperId))
  }
  if (sessionId !== undefined) {
    formData.append('session_id', String(sessionId === null ? 0 : sessionId))
  }

  const response = await apiFetch(`${API_BASE}/notes/${noteId}`, {
    method: 'PATCH',
    body: formData
  })
  if (!response.ok) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = payload?.detail ? ` - ${payload.detail}` : ''
    } catch {
      detail = ''
    }
    throw new Error(`Request failed: ${response.status}${detail}`)
  }

  const payload = await response.json()
  return payload.note
}

export async function moveNote(noteId, targetFolderId = null) {
  const requestInit = { method: 'PATCH' }
  if (targetFolderId !== null && targetFolderId !== undefined) {
    const formData = new FormData()
    formData.append('target_folder_id', String(targetFolderId))
    requestInit.body = formData
  }

  const response = await apiFetch(`${API_BASE}/notes/${noteId}/move`, requestInit)
  if (!response.ok) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = payload?.detail ? ` - ${payload.detail}` : ''
    } catch {
      detail = ''
    }
    throw new Error(`Request failed: ${response.status}${detail}`)
  }
  const payload = await response.json()
  return payload.note
}

export async function deleteNote(noteId) {
  const response = await apiFetch(`${API_BASE}/notes/${noteId}`, {
    method: 'DELETE'
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json()
}
