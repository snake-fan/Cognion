function formatProjectTime(isoTime) {
  if (!isoTime) {
    return '刚刚更新'
  }

  const timestamp = new Date(isoTime)
  if (Number.isNaN(timestamp.getTime())) {
    return '最近更新'
  }

  return timestamp.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function ProjectCard({ project, onOpen, onDragStart, onDelete }) {
  const title = project.title || project.name || '未命名论文'
  const authors = project.authors || '未知'
  const topic = project.research_topic || '未标注'
  const journal = project.journal || '未知'
  const publicationDate = project.publication_date || '未知'
  const updatedAt = project.updated_at || project.updatedAt

  return (
    <article
      className="project-card"
      role="button"
      tabIndex={0}
      onClick={() => onOpen(project.id)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen(project.id)
        }
      }}
      draggable
      onDragStart={(event) => onDragStart(event, project.id)}
    >
      <div className="project-card-topline">
        <span className="project-file-icon"><svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6" /></svg></span>
        <span className="project-topic">{topic}</span>
      </div>
      <div className="project-card-title">{title}</div>
      <div className="project-card-meta">
        <span>作者：{authors}</span>
        <span>期刊：{journal}</span>
        <span>{publicationDate} · 更新于 {formatProjectTime(updatedAt)}</span>
      </div>
      <button
        type="button"
        className="project-delete-button"
        title="删除论文"
        onClick={(event) => {
          event.stopPropagation()
          onDelete(project)
        }}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13" /></svg>
      </button>
    </article>
  )
}

export default ProjectCard
