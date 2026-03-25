import ProjectCard from './ProjectCard'

function ProjectGrid({ projects, onOpenProject, onProjectDragStart, onDeleteProject }) {
  if (projects.length === 0) {
    return <div className="project-empty">暂无历史 PDF 项目，先上传一个文件开始吧。</div>
  }

  return (
    <div className="project-grid">
      {projects.map((project) => (
        <ProjectCard
          key={project.id}
          project={project}
          onOpen={onOpenProject}
          onDragStart={onProjectDragStart}
          onDelete={onDeleteProject}
        />
      ))}
    </div>
  )
}

export default ProjectGrid
