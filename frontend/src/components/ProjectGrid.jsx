import ProjectCard from './ProjectCard'

function ProjectGrid({ projects, onOpenProject, onProjectDragStart, onDeleteProject }) {
  if (projects.length === 0) {
    return <div className="project-empty"><span>PDF</span><strong>这里还没有文献</strong><p>上传第一篇论文，开启你的知识积累。</p></div>
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
