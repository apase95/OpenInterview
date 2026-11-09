export default function Home() {
  return <>
    <header><nav className="demo-nav" aria-label="Main navigation">
      <a className="brand" href="/" aria-label="OpenInterview home"><span className="brand-mark" aria-hidden="true"><img src="/images/logo.svg" alt="" width="163" height="30" /></span><span>OpenInterview</span></a>
      <div><a href="/roles">Roles</a><AccountControl /></div>
    </nav></header>
    <main>
      <section className="hero" aria-labelledby="title">
        <h1 id="title">Start with a<br />conversation.</h1>
        <p className="subtitle">Explore a candidate demo. No live AI or official interview.</p>
        <div className="actions"><a className="button primary" href="/roles">View roles</a><a className="button secondary" href="/roles#invitation">I have an invitation</a></div>
      </section>
      <section className="preview" aria-label="Example interview preview">
        <div className="preview-row"><span>Voice interview</span></div>
        <div className="robot"><img src="/images/robot.svg" alt="Purple interview robot" width="230" height="230" /></div>
        <div className="preview-row"><span>Interview language: Vietnamese</span></div>
      </section>
    </main>
  </>;
}
import AccountControl from './auth-ui/AccountControl';
