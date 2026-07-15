import HomeUploadPanel from '../components/HomeUploadPanel'
import FolderTree from '../components/FolderTree'
import ProjectGrid from '../components/ProjectGrid'

function LibraryLayout({
  projects,
  loading,
  selectedFolderName,
  folders,
  onSelectFile,
  onOpenProject,
  onSelectFolder,
  onFolderDrop,
  onFolderDragStart,
  onRootDrop,
  onProjectDragStart,
  onCreateFolder,
  folderCreateTarget,
  folderCreateName,
  folderCreateLoading,
  onFolderCreateNameChange,
  onCancelCreateFolder,
  onConfirmCreateFolder,
  onDeleteFolder,
  onRenameFolder,
  onDeleteProject,
  activeFolderIds,
  deleteDialog,
  deleteDialogLoading,
  onCancelDeleteDialog,
  onConfirmDeleteDialog
}) {
  return (
    <main className="library-page">
      <section className="library-title-row">
        <div>
          <span className="library-eyebrow">YOUR RESEARCH LIBRARY</span>
          <h1 className="library-title">文献库</h1>
          <p className="library-subtitle">整理、阅读，并连接你的每一份研究材料。</p>
        </div>
        <div className="library-count"><strong>{projects.length}</strong><span>篇文献</span></div>
      </section>

      <section className="library-workspace">
        <FolderTree
          folders={folders}
          activeFolderIds={activeFolderIds}
          onSelectFolder={onSelectFolder}
          onFolderDrop={onFolderDrop}
          onFolderDragStart={onFolderDragStart}
          onRootDrop={onRootDrop}
          onCreateFolder={onCreateFolder}
          onDeleteFolder={onDeleteFolder}
          onRenameFolder={onRenameFolder}
        />

        <div className="library-projects">
          <div className="library-projects-header"><span>当前位置</span><strong>{selectedFolderName || '全部文献'}</strong></div>
          <HomeUploadPanel
            onSelectFile={onSelectFile}
            label={`上传到 ${selectedFolderName || '根目录'}`}
          />
          {loading ? <div className="library-loading">正在解析论文元信息，请稍候...</div> : null}
          <ProjectGrid
            projects={projects}
            onOpenProject={onOpenProject}
            onProjectDragStart={onProjectDragStart}
            onDeleteProject={onDeleteProject}
          />
        </div>
      </section>

      {folderCreateTarget ? (
        <div className="floating-create-folder" role="dialog" aria-modal="true">
          <div className="floating-create-card">
            <div className="floating-create-title">
              {folderCreateTarget.id === null ? '新建根目录文件夹' : '新建子文件夹'}
            </div>
            <div className="floating-create-subtitle">父目录：{folderCreateTarget.name}</div>
            <input
              className="floating-create-input"
              value={folderCreateName}
              onChange={(event) => onFolderCreateNameChange(event.target.value)}
              placeholder="输入文件夹名称"
              autoFocus
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  onConfirmCreateFolder()
                }
                if (event.key === 'Escape') {
                  event.preventDefault()
                  onCancelCreateFolder()
                }
              }}
            />
            <div className="floating-create-actions">
              <button
                type="button"
                className="floating-create-btn"
                onClick={onCancelCreateFolder}
                disabled={folderCreateLoading}
              >
                取消
              </button>
              <button
                type="button"
                className="floating-create-btn primary"
                onClick={onConfirmCreateFolder}
                disabled={folderCreateLoading || !folderCreateName.trim()}
              >
                {folderCreateLoading ? '创建中...' : '确定'}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {deleteDialog ? (
        <div className="floating-confirm-delete" role="dialog" aria-modal="true">
          <div className="floating-confirm-card">
            <div className="floating-confirm-title">{deleteDialog.title}</div>
            <div className="floating-confirm-message">{deleteDialog.message}</div>
            <div className="floating-confirm-actions">
              <button
                type="button"
                className="floating-create-btn"
                onClick={onCancelDeleteDialog}
                disabled={deleteDialogLoading}
              >
                取消
              </button>
              <button
                type="button"
                className="floating-create-btn danger"
                onClick={onConfirmDeleteDialog}
                disabled={deleteDialogLoading}
              >
                {deleteDialogLoading ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  )
}

export default LibraryLayout
