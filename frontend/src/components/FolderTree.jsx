import { useMemo, useState } from 'react'

function FolderNode({
  node,
  activeFolderIds,
  onSelect,
  onFolderDrop,
  onFolderDragStart,
  onCreateChildFolder,
  onDeleteFolder,
  onRenameFolder,
  expandedMap,
  onToggleExpand
}) {
  const isActive = activeFolderIds.includes(node.id)
  const isExpanded = expandedMap[node.id] ?? true
  const hasChildren = node.children?.length > 0
  const folderIcon = node.has_papers ? '🗂️' : '📁'
  const [isRenaming, setIsRenaming] = useState(false)
  const [renameValue, setRenameValue] = useState(node.name)
  const [renameLoading, setRenameLoading] = useState(false)

  function startRename(event) {
    event.preventDefault()
    event.stopPropagation()
    setRenameValue(node.name)
    setIsRenaming(true)
  }

  function cancelRename() {
    if (renameLoading) {
      return
    }
    setIsRenaming(false)
    setRenameValue(node.name)
  }

  async function submitRename() {
    const trimmed = renameValue.trim()
    if (!trimmed || renameLoading) {
      return
    }
    if (trimmed === node.name) {
      setIsRenaming(false)
      return
    }

    try {
      setRenameLoading(true)
      await onRenameFolder(node.id, trimmed)
      setIsRenaming(false)
    } catch {
      // keep edit mode when rename fails
    } finally {
      setRenameLoading(false)
    }
  }

  return (
    <li>
      <div
        className={`folder-node-row ${isActive ? 'active' : ''}`}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => onFolderDrop(event, node.id)}
      >
        <button
          type="button"
          className="folder-expand-toggle"
          onClick={(event) => {
            event.stopPropagation()
            if (hasChildren) {
              onToggleExpand(node.id)
            }
          }}
          title={hasChildren ? (isExpanded ? '折叠' : '展开') : ''}
        >
          {hasChildren ? (isExpanded ? '▾' : '▸') : '·'}
        </button>

        {isRenaming ? (
          <input
            className="folder-rename-input"
            value={renameValue}
            autoFocus
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => setRenameValue(event.target.value)}
            onBlur={submitRename}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                submitRename()
              }
              if (event.key === 'Escape') {
                event.preventDefault()
                cancelRename()
              }
            }}
            disabled={renameLoading}
          />
        ) : (
          <button
            type="button"
            className="folder-node"
            onClick={() => onSelect(node.id)}
            onDoubleClick={startRename}
            draggable
            onDragStart={(event) => onFolderDragStart(event, node.id)}
          >
            {folderIcon} {node.name}
          </button>
        )}

        <button
          type="button"
          className="folder-action-btn"
          title="新建子文件夹"
          onClick={(event) => {
            event.stopPropagation()
            onCreateChildFolder(node)
          }}
        >
          +
        </button>

        <button
          type="button"
          className="folder-action-btn danger"
          title="删除文件夹"
          onClick={(event) => {
            event.stopPropagation()
            onDeleteFolder(node)
          }}
        >
          ×
        </button>
      </div>

      {hasChildren && isExpanded ? (
        <ul className="folder-children">
          {node.children.map((child) => (
            <FolderNode
              key={child.id}
              node={child}
              activeFolderIds={activeFolderIds}
              onSelect={onSelect}
              onFolderDrop={onFolderDrop}
              onFolderDragStart={onFolderDragStart}
              onCreateChildFolder={onCreateChildFolder}
              onDeleteFolder={onDeleteFolder}
              onRenameFolder={onRenameFolder}
              expandedMap={expandedMap}
              onToggleExpand={onToggleExpand}
            />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

function FolderTree({
  folders,
  activeFolderIds,
  onSelectFolder,
  onFolderDrop,
  onFolderDragStart,
  onRootDrop,
  onCreateFolder,
  onDeleteFolder,
  onRenameFolder
}) {
  const [expandedMap, setExpandedMap] = useState({})

  const normalizedFolders = useMemo(() => folders || [], [folders])

  function onToggleExpand(folderId) {
    setExpandedMap((prev) => ({ ...prev, [folderId]: !(prev[folderId] ?? true) }))
  }

  return (
    <aside
      className="library-folder-tree"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onSelectFolder(null)
        }
      }}
      onDragOver={(event) => event.preventDefault()}
      onDrop={onRootDrop}
    >
      <div className="folder-tree-header">
        <span>文件夹（点击空白处回到根目录）</span>
        <button
          type="button"
          className="folder-root-create-btn"
          title="在根目录新建文件夹"
          onClick={(event) => {
            event.stopPropagation()
            onCreateFolder({ id: null, name: '根目录' })
          }}
        >
          +
        </button>
      </div>
      <ul className="folder-tree-list">
        {normalizedFolders.map((folder) => (
          <FolderNode
            key={folder.id}
            node={folder}
            activeFolderIds={activeFolderIds}
            onSelect={onSelectFolder}
            onFolderDrop={onFolderDrop}
            onFolderDragStart={onFolderDragStart}
            onCreateChildFolder={onCreateFolder}
            onDeleteFolder={onDeleteFolder}
            onRenameFolder={onRenameFolder}
            expandedMap={expandedMap}
            onToggleExpand={onToggleExpand}
          />
        ))}
      </ul>
    </aside>
  )
}

export default FolderTree
