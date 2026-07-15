import cognionLogo from '../assets/cognion_logo_dark.png'

const GITHUB_URL = 'https://github.com/snake-fan/Cognion'

export default function LandingPage({ onGetStarted }) {
  return (
    <main className="landing-page">
      <header className="landing-nav">
        <a className="landing-brand" href="/" aria-label="Cognion 首页">
          <img src={cognionLogo} alt="" />
          <span>Cognion</span>
        </a>
        <span className="landing-nav-caption">For minds that keep growing.</span>
      </header>

      <section className="landing-panel landing-hero">
        <div className="landing-hero-content">
          <p className="landing-kicker">Cognion · AI Research Workspace</p>
          <h1>阅读，不止于读过。</h1>
          <p className="landing-lead">让论文中的新知识，真正进入你的认知系统。</p>
          <div className="landing-actions">
            <a className="landing-button landing-button-dark" href={GITHUB_URL} target="_blank" rel="noreferrer">
              GitHub <span aria-hidden="true">↗</span>
            </a>
            <button className="landing-button landing-button-light" type="button" onClick={onGetStarted}>
              进入体验 <span aria-hidden="true">→</span>
            </button>
          </div>
        </div>
        <div className="landing-scroll-cue" aria-hidden="true"><span />向下探索</div>
      </section>

      <section className="landing-panel landing-problem">
        <div className="landing-section-copy">
          <p className="landing-kicker">THE GAP AFTER READING</p>
          <h2>读完一篇论文，<br />然后呢？</h2>
          <p>摘要记住了，结论看懂了。几天后，它们又变回一页页熟悉却陌生的文字。</p>
        </div>
        <div className="landing-problem-list">
          <article><span>01</span><h3>理解没有被说清</h3><p>“好像懂了”的感觉，没有成为稳定、可复述的认识。</p></article>
          <article><span>02</span><h3>知识彼此孤立</h3><p>新方法、新假设和你的研究方向之间，缺少真实的连接。</p></article>
          <article><span>03</span><h3>阅读没有留下痕迹</h3><p>笔记成本太高，对话又稍纵即逝，思考无法持续生长。</p></article>
        </div>
      </section>

      <section className="landing-panel landing-solution">
        <div className="landing-orbit" aria-hidden="true">
          <span className="landing-orbit-ring landing-orbit-ring-one" />
          <span className="landing-orbit-ring landing-orbit-ring-two" />
          <span className="landing-orbit-core">你</span>
          <span className="landing-orbit-label label-read">阅读</span>
          <span className="landing-orbit-label label-think">思考</span>
          <span className="landing-orbit-label label-connect">连接</span>
        </div>
        <div className="landing-section-copy">
          <p className="landing-kicker">A THINKING PARTNER</p>
          <h2>AI 不替你思考。<br />它让思考发生。</h2>
          <p>Cognion 从你的提问、困惑与表达中理解你，以启发式对话陪你澄清概念、检验判断、发现新的联系。</p>
        </div>
      </section>

      <section className="landing-panel landing-product">
        <div className="landing-product-heading">
          <p className="landing-kicker">ONE CONTINUOUS WORKFLOW</p>
          <h2>从一篇论文，<br />到一片知识版图。</h2>
        </div>
        <div className="landing-product-grid">
          <article className="landing-product-card card-reading">
            <div className="landing-card-visual"><span className="paper-line wide" /><span className="paper-line" /><span className="paper-line short" /><i /></div>
            <div><span>01 · READ</span><h3>沉浸阅读</h3><p>原文、引用与对话保持在同一思考现场。</p></div>
          </article>
          <article className="landing-product-card card-dialogue">
            <div className="landing-card-visual"><b>你真正认同这个结论吗？</b><span>试着从实验假设出发，再判断一次。</span></div>
            <div><span>02 · THINK</span><h3>启发式对话</h3><p>答案不是终点，更好的问题才是。</p></div>
          </article>
          <article className="landing-product-card card-knowledge">
            <div className="landing-card-visual"><i /><i /><i /><i /><span /><span /><span /></div>
            <div><span>03 · GROW</span><h3>知识生长</h3><p>让理解沉淀为笔记，并在知识图谱中彼此连接。</p></div>
          </article>
        </div>
      </section>

      <section className="landing-panel landing-closing">
        <p className="landing-kicker">READ. THINK. CONNECT.</p>
        <h2>每一次阅读，<br />都应该改变一点什么。</h2>
        <p>不是更多信息，而是更清晰的理解、更长久的连接，以及下一次灵感发生的可能。</p>
        <button className="landing-button landing-button-dark" type="button" onClick={onGetStarted}>开始你的知识生长 <span>→</span></button>
        <footer><span>© Cognion</span><a href={GITHUB_URL} target="_blank" rel="noreferrer">Open source on GitHub ↗</a></footer>
      </section>
    </main>
  )
}
