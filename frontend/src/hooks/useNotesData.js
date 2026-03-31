import { useEffect, useMemo, useState } from 'react'
import {
  createNote,
  createNoteFolder,
  deleteNote,
  deleteNoteFolder,
  fetchNoteFolderTree,
  fetchNotes,
  fetchPaperSessions,
  fetchPapers,
  moveNote,
  moveNoteFolder,
  renameNoteFolder,
  updateNote
} from '../services/api'

function findFolderName(nodes, folderId) {
  for (const node of nodes) {
    if (node.id === folderId) {
      return node.name
    }
    if (node.children?.length) {
      const hit = findFolderName(node.children, folderId)
      if (hit) {
        return hit
      }
    }
  }
  return null
}

function useNotesData({ activePaperId, activeSessionId }) {
  const [notes, setNotes] = useState([])
  const [folders, setFolders] = useState([])
  const [papers, setPapers] = useState([])
  const [sessions, setSessions] = useState([])
  const [selectedFolderId, setSelectedFolderId] = useState(null)
  const [selectedNoteId, setSelectedNoteId] = useState(null)
  const [loading, setLoading] = useState(false)

  const [folderCreateTarget, setFolderCreateTarget] = useState(null)
  const [folderCreateName, setFolderCreateName] = useState('')
  const [folderCreateLoading, setFolderCreateLoading] = useState(false)
  const [deleteDialog, setDeleteDialog] = useState(null)
  const [deleteDialogLoading, setDeleteDialogLoading] = useState(false)

  const selectedNote = useMemo(
    () => notes.find((note) => note.id === selectedNoteId) || null,
    [notes, selectedNoteId]
  )

  useEffect(() => {
    async function loadInitialData() {
      setLoading(true)
      try {
        const [nextNotes, nextFolders, nextPapers] = await Promise.all([
          fetchNotes(null),
          fetchNoteFolderTree(),
          fetchPapers(null, { includeAll: true })
        ])
        setNotes(nextNotes)
        setFolders(nextFolders)
        setPapers(nextPapers)
      } catch (error) {
        console.error(error)
      } finally {
        setLoading(false)
      }
    }

    loadInitialData()
  }, [])

  useEffect(() => {
    function onExternalNotesUpdated() {
      void refreshFolders()
      void refreshPapers()
      void refreshNotes(selectedFolderId)
    }

    window.addEventListener('cognion:notes-updated', onExternalNotesUpdated)
    return () => {
      window.removeEventListener('cognion:notes-updated', onExternalNotesUpdated)
    }
  }, [selectedFolderId])

  useEffect(() => {
    if (!selectedNoteId && notes.length > 0) {
      setSelectedNoteId(notes[0].id)
    }
    if (notes.length === 0) {
      setSelectedNoteId(null)
    }
  }, [notes, selectedNoteId])

  useEffect(() => {
    async function loadSessionsForPaper() {
      if (!selectedNote?.paper_id) {
        setSessions([])
        return
      }
      try {
        const nextSessions = await fetchPaperSessions(selectedNote.paper_id)
        setSessions(nextSessions)
      } catch (error) {
        console.error(error)
        setSessions([])
      }
    }

    loadSessionsForPaper()
  }, [selectedNote?.paper_id])

  async function refreshFolders() {
    try {
      const nextFolders = await fetchNoteFolderTree()
      setFolders(nextFolders)
    } catch (error) {
      console.error(error)
    }
  }

  async function refreshNotes(folderId = selectedFolderId) {
    try {
      const nextNotes = await fetchNotes(folderId)
      setNotes(nextNotes)
    } catch (error) {
      console.error(error)
      setNotes([])
    }
  }

  async function refreshPapers() {
    try {
      const nextPapers = await fetchPapers(null, { includeAll: true })
      setPapers(nextPapers)
    } catch (error) {
      console.error(error)
    }
  }

  async function onSelectFolder(folderId) {
    setSelectedFolderId(folderId)
    await refreshNotes(folderId)
  }

  function onSelectNote(noteId) {
    setSelectedNoteId(noteId)
  }

  async function onCreateNote() {
    const fallbackPaperId = activePaperId ?? null
    const fallbackSessionId = activeSessionId ?? null
    const created = await createNote({
      title: `笔记 ${new Date().toLocaleString()}`,
      content: '# 新笔记\n\n',
      folderId: selectedFolderId,
      paperId: fallbackPaperId,
      sessionId: fallbackSessionId
    })

    await refreshNotes(selectedFolderId)
    await refreshFolders()
    await refreshPapers()
    setSelectedNoteId(created.id)
  }

  async function onSaveNote(noteId, payload) {
    const updated = await updateNote(noteId, payload)
    setNotes((prev) => prev.map((note) => (note.id === noteId ? updated : note)))
    return updated
  }

  async function onRenameNote(noteId, name) {
    const trimmedName = name.trim()
    if (!trimmedName) {
      return
    }

    try {
      await onSaveNote(noteId, { title: trimmedName })
    } catch (error) {
      console.error(error)
      window.alert('重命名笔记失败')
      throw error
    }
  }

  async function onDeleteNote(note) {
    setDeleteDialog({
      type: 'note',
      payload: note,
      title: `删除笔记「${note.title}」`,
      message: '将同时删除对应 md 文件和数据库记录，操作不可恢复。'
    })
  }

  async function onCreateFolder(parentFolder) {
    setFolderCreateTarget(parentFolder)
    setFolderCreateName('')
  }

  function onCancelCreateFolder() {
    if (folderCreateLoading) {
      return
    }
    setFolderCreateTarget(null)
    setFolderCreateName('')
  }

  async function onConfirmCreateFolder() {
    const trimmedName = folderCreateName.trim()
    if (!folderCreateTarget || !trimmedName || folderCreateLoading) {
      return
    }

    try {
      setFolderCreateLoading(true)
      await createNoteFolder(trimmedName, folderCreateTarget.id)
      await refreshFolders()
      setFolderCreateTarget(null)
      setFolderCreateName('')
    } catch (error) {
      console.error(error)
      window.alert('新建子文件夹失败')
    } finally {
      setFolderCreateLoading(false)
    }
  }

  async function onDeleteFolder(folder) {
    setDeleteDialog({
      type: 'folder',
      payload: folder,
      title: `删除文件夹「${folder.name}」`,
      message: '这会连带删除其子目录、其中笔记及数据库记录，操作不可恢复。'
    })
  }

  async function onRenameFolder(folderId, name) {
    const trimmedName = name.trim()
    if (!trimmedName) {
      return
    }

    try {
      await renameNoteFolder(folderId, trimmedName)
      await refreshFolders()
      await refreshNotes(selectedFolderId)
    } catch (error) {
      console.error(error)
      window.alert('重命名失败')
      throw error
    }
  }

  async function onFolderDrop(event, targetFolderId) {
    event.preventDefault()
    event.stopPropagation()
    const dragType = event.dataTransfer.getData('cognion-drag-type')
    const dragId = event.dataTransfer.getData('cognion-drag-id')
    if (!dragType || !dragId) {
      return
    }

    try {
      if (dragType === 'note') {
        await moveNote(Number(dragId), targetFolderId)
        await refreshFolders()
        await refreshNotes(selectedFolderId)
      }

      if (dragType === 'note-folder') {
        await moveNoteFolder(Number(dragId), targetFolderId)
        await refreshFolders()
        await refreshNotes(selectedFolderId)
      }
    } catch (error) {
      console.error(error)
      window.alert('拖拽移动失败')
    }
  }

  function onFolderDragStart(event, folderId) {
    event.dataTransfer.setData('cognion-drag-type', 'note-folder')
    event.dataTransfer.setData('cognion-drag-id', String(folderId))
  }

  function onNoteDragStart(event, noteId) {
    event.dataTransfer.setData('cognion-drag-type', 'note')
    event.dataTransfer.setData('cognion-drag-id', String(noteId))
  }

  async function onRootDrop(event) {
    event.preventDefault()
    event.stopPropagation()
    const dragType = event.dataTransfer.getData('cognion-drag-type')
    const dragId = event.dataTransfer.getData('cognion-drag-id')
    if (!dragType || !dragId) {
      return
    }

    try {
      if (dragType === 'note') {
        await moveNote(Number(dragId), null)
        await refreshFolders()
        await refreshNotes(selectedFolderId)
      }
      if (dragType === 'note-folder') {
        await moveNoteFolder(Number(dragId), null)
        await refreshFolders()
        await refreshNotes(selectedFolderId)
      }
    } catch (error) {
      console.error(error)
      window.alert('移动到根目录失败')
    }
  }

  function onCancelDeleteDialog() {
    if (deleteDialogLoading) {
      return
    }
    setDeleteDialog(null)
  }

  async function onConfirmDeleteDialog() {
    if (!deleteDialog || deleteDialogLoading) {
      return
    }

    try {
      setDeleteDialogLoading(true)
      if (deleteDialog.type === 'folder') {
        const folder = deleteDialog.payload
        await deleteNoteFolder(folder.id)
        if (selectedFolderId === folder.id || activeFolderIds.includes(folder.id)) {
          setSelectedFolderId(null)
          await refreshNotes(null)
        } else {
          await refreshNotes(selectedFolderId)
        }
        await refreshFolders()
      }

      if (deleteDialog.type === 'note') {
        const note = deleteDialog.payload
        await deleteNote(note.id)
        await refreshFolders()
        await refreshNotes(selectedFolderId)
        if (selectedNoteId === note.id) {
          setSelectedNoteId(null)
        }
      }

      setDeleteDialog(null)
    } catch (error) {
      console.error(error)
      window.alert('删除失败')
    } finally {
      setDeleteDialogLoading(false)
    }
  }

  const selectedFolderName = useMemo(
    () => (selectedFolderId === null ? '根目录' : findFolderName(folders, selectedFolderId)),
    [folders, selectedFolderId]
  )

  const activeFolderIds = useMemo(() => {
    if (selectedFolderId === null) {
      return []
    }

    const path = []
    function walk(nodes, currentPath = []) {
      for (const node of nodes) {
        const nextPath = [...currentPath, node.id]
        if (node.id === selectedFolderId) {
          path.push(...nextPath)
          return true
        }
        if (node.children?.length && walk(node.children, nextPath)) {
          return true
        }
      }
      return false
    }

    walk(folders)
    return path
  }, [folders, selectedFolderId])

  return {
    loading,
    folders,
    notes,
    papers,
    sessions,
    selectedFolderId,
    selectedFolderName,
    selectedNote,
    activeFolderIds,
    folderCreateTarget,
    folderCreateName,
    folderCreateLoading,
    deleteDialog,
    deleteDialogLoading,
    setFolderCreateName,
    onSelectFolder,
    onSelectNote,
    onCreateNote,
    onSaveNote,
    onRenameNote,
    onDeleteNote,
    onFolderDrop,
    onFolderDragStart,
    onRootDrop,
    onNoteDragStart,
    onCreateFolder,
    onCancelCreateFolder,
    onConfirmCreateFolder,
    onDeleteFolder,
    onRenameFolder,
    onCancelDeleteDialog,
    onConfirmDeleteDialog
  }
}

export default useNotesData
