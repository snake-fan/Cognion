import { useEffect, useMemo, useState } from 'react'
import {
  createFolder,
  deleteFolder,
  deletePaper,
  fetchFolderTree,
  fetchPapers,
  moveFolder,
  movePaper,
  renameFolder
} from '../services/api'

function findFolderName(nodes, folderId) {
  for (const node of nodes) {
    if (node.id === folderId) {
      return node.name
    }
    if (node.children?.length) {
      const childHit = findFolderName(node.children, folderId)
      if (childHit) {
        return childHit
      }
    }
  }
  return null
}

function useLibraryData({ activeProjectId, onActiveProjectDeleted }) {
  const [projects, setProjects] = useState([])
  const [libraryLoading, setLibraryLoading] = useState(false)
  const [folders, setFolders] = useState([])
  const [selectedFolderId, setSelectedFolderId] = useState(null)
  const [folderCreateTarget, setFolderCreateTarget] = useState(null)
  const [folderCreateName, setFolderCreateName] = useState('')
  const [folderCreateLoading, setFolderCreateLoading] = useState(false)
  const [deleteDialog, setDeleteDialog] = useState(null)
  const [deleteDialogLoading, setDeleteDialogLoading] = useState(false)

  useEffect(() => {
    async function loadInitialData() {
      try {
        const [papers, folderTree] = await Promise.all([fetchPapers(), fetchFolderTree()])
        setProjects(papers)
        setFolders(folderTree)
      } catch {
        setProjects([])
        setFolders([])
      }
    }

    loadInitialData()
  }, [])

  async function refreshFolders() {
    try {
      const nextFolders = await fetchFolderTree()
      setFolders(nextFolders)
    } catch (error) {
      console.error(error)
    }
  }

  async function refreshPapers(folderId = selectedFolderId) {
    try {
      const nextPapers = await fetchPapers(folderId)
      setProjects(nextPapers)
    } catch (error) {
      console.error(error)
      setProjects([])
    }
  }

  async function onSelectFolder(folderId) {
    setSelectedFolderId(folderId)
    await refreshPapers(folderId)
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
      if (dragType === 'paper') {
        await movePaper(dragId, targetFolderId)
        await refreshFolders()
        await refreshPapers(selectedFolderId)
      }

      if (dragType === 'folder') {
        await moveFolder(Number(dragId), targetFolderId)
        await refreshFolders()
        await refreshPapers(selectedFolderId)
      }
    } catch (error) {
      console.error(error)
      window.alert('拖拽移动失败')
    }
  }

  function onProjectDragStart(event, projectId) {
    event.dataTransfer.setData('cognion-drag-type', 'paper')
    event.dataTransfer.setData('cognion-drag-id', String(projectId))
  }

  function onFolderDragStart(event, folderId) {
    event.dataTransfer.setData('cognion-drag-type', 'folder')
    event.dataTransfer.setData('cognion-drag-id', String(folderId))
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
      if (dragType === 'paper') {
        await movePaper(dragId, null)
        await refreshFolders()
        await refreshPapers(selectedFolderId)
      }
      if (dragType === 'folder') {
        await moveFolder(Number(dragId), null)
        await refreshFolders()
        await refreshPapers(selectedFolderId)
      }
    } catch (error) {
      console.error(error)
      const detail = error instanceof Error ? error.message : ''
      window.alert(detail ? `移动到根目录失败\n${detail}` : '移动到根目录失败')
    }
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
      await createFolder(trimmedName, folderCreateTarget.id)
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
      message: '这会连带删除其子目录、其中论文及数据库记录，操作不可恢复。'
    })
  }

  async function onRenameFolder(folderId, name) {
    const trimmedName = name.trim()
    if (!trimmedName) {
      return
    }

    try {
      await renameFolder(folderId, trimmedName)
      await refreshFolders()
      await refreshPapers(selectedFolderId)
    } catch (error) {
      console.error(error)
      window.alert('重命名失败')
      throw error
    }
  }

  async function onDeleteProject(project) {
    const projectTitle = project.title || project.name || '未命名论文'
    setDeleteDialog({
      type: 'project',
      payload: project,
      title: `删除论文「${projectTitle}」`,
      message: '将同时删除原文件、对话历史和数据库记录。'
    })
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
        await deleteFolder(folder.id)
        if (selectedFolderId === folder.id || activeFolderIds.includes(folder.id)) {
          setSelectedFolderId(null)
          await refreshPapers(null)
        } else {
          await refreshPapers(selectedFolderId)
        }
        await refreshFolders()
      }

      if (deleteDialog.type === 'project') {
        const project = deleteDialog.payload
        await deletePaper(project.id)
        await refreshFolders()
        await refreshPapers(selectedFolderId)
        if (activeProjectId === project.id) {
          onActiveProjectDeleted(project.id)
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
  const activeFolderIds = useMemo(() => (selectedFolderId === null ? [] : [selectedFolderId]), [selectedFolderId])

  return {
    projects,
    setProjects,
    libraryLoading,
    setLibraryLoading,
    folders,
    refreshFolders,
    selectedFolderId,
    selectedFolderName,
    activeFolderIds,
    folderCreateTarget,
    folderCreateName,
    folderCreateLoading,
    deleteDialog,
    deleteDialogLoading,
    setFolderCreateName,
    onSelectFolder,
    onFolderDrop,
    onFolderDragStart,
    onRootDrop,
    onProjectDragStart,
    onCreateFolder,
    onCancelCreateFolder,
    onConfirmCreateFolder,
    onDeleteFolder,
    onRenameFolder,
    onDeleteProject,
    onCancelDeleteDialog,
    onConfirmDeleteDialog
  }
}

export default useLibraryData
