export default function Home() {
  return <>
    <header><nav className="h-14 flex items-center justify-between" aria-label="Main navigation">
      <a href="/" aria-label="OpenInterview home"><img src="/images/logo.svg" alt="OpenInterview" width="163" height="30" /></a>
      <div><a href="/roles">Roles</a><a className="button secondary" href="/login">Sign in</a></div>
    </nav></header>
    <main>
      <section className="hero" aria-labelledby="title">
        <h1 id="title">Start with a<br />conversation.</h1>
        <p className="subtitle">AI leads a short interview. Recruiters review the evidence.</p>
        <div className="actions"><a className="button primary" href="/roles">View roles</a><a className="button secondary" href="/roles">I have an invitation</a></div>
      </section>
      <section className="preview" aria-label="Example interview preview">
        <div className="preview-row"><span>Voice interview</span></div>
        <div className="robot"><img src="/images/robot.svg" alt="Purple interview robot" width="230" height="230" /></div>
        <div className="preview-row"><span>Interview language: Vietnamese</span></div>
      </section>
    </main>
  </>;
}
