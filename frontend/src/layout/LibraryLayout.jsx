import HomeUploadPanel from '../components/HomeUploadPanel'
import ProjectGrid from '../components/ProjectGrid'

function LibraryLayout({ projects, onSelectFile, onOpenProject, loading }) {
  return (
    <main className="library-page">
      <section className="library-hero">
        <h1 className="library-title">文献库</h1>
        <p className="library-subtitle">上传一个 PDF 开始新项目，或从下方卡片继续之前的对话。</p>
        <HomeUploadPanel onSelectFile={onSelectFile} />
        {loading ? <div className="library-loading">正在解析论文元信息，请稍候...</div> : null}
      </section>

      <section className="library-projects">
        <div className="library-projects-header">历史 PDF 项目</div>
        <ProjectGrid projects={projects} onOpenProject={onOpenProject} />
      </section>
    </main>
  )
}

export default LibraryLayout
