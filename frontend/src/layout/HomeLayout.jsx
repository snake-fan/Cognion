function HomeLayout({ onEnterLibrary }) {
  return (
    <main className="landing-page">
      <section className="landing-hero">
        <h1 className="landing-title">Cognion</h1>
        <p className="landing-subtitle">
          智能文献阅读与对话工作台
          <br />
          开始你的阅读体验
        </p>
        <button type="button" className="landing-enter-button" onClick={onEnterLibrary}>
          进入体验
        </button>
      </section>
    </main>
  )
}

export default HomeLayout
