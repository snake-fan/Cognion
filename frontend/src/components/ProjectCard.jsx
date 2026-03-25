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

function ProjectCard({ project, onOpen }) {
  const title = project.title || project.name || '未命名论文'
  const authors = project.authors || '未知'
  const topic = project.research_topic || '未标注'
  const journal = project.journal || '未知'
  const publicationDate = project.publication_date || '未知'
  const updatedAt = project.updated_at || project.updatedAt

  return (
    <button type="button" className="project-card" onClick={() => onOpen(project.id)}>
      <div className="project-card-title">{title}</div>
      <div className="project-card-meta">
        <span>作者：{authors}</span>
        <span>主题：{topic}</span>
        <span>期刊：{journal}</span>
        <span>出版日期：{publicationDate}</span>
        <span>更新时间：{formatProjectTime(updatedAt)}</span>
      </div>
    </button>
  )
}

export default ProjectCard
