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
  return (
    <button type="button" className="project-card" onClick={() => onOpen(project.id)}>
      <div className="project-card-title">{project.name}</div>
      <div className="project-card-meta">
        <span>更新时间：{formatProjectTime(project.updatedAt)}</span>
        <span>{project.messages?.length || 0} 条对话</span>
      </div>
    </button>
  )
}

export default ProjectCard
