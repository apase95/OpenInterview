export default function Home() {
  return <>
    <header className="border-b border-border"><nav className="relative mx-auto flex min-h-12 max-w-[1328px] items-center justify-between gap-6 px-6 [@media(max-width:760px)]:flex-wrap [@media(max-width:760px)]:gap-3 [@media(max-width:760px)]:px-4 [@media(max-width:760px)]:py-2" aria-label="Main navigation">
      <a className="inline-flex shrink-0 items-center gap-2.5 text-[18px] font-semibold [@media(max-width:760px)]:text-base" href="/" aria-label="OpenInterview home"><span className="block size-6 overflow-hidden" aria-hidden="true"><img className="block h-6 w-[130.4px] max-w-none" src="/images/logo.svg" alt="" width="163" height="30" /></span><span>OpenInterview</span></a>
      <div className="flex items-center gap-[30px] [@media(max-width:760px)]:gap-4"><a className="inline-flex min-h-9 items-center text-sm leading-5 font-normal text-muted" href="/roles">Roles</a><AccountControl /></div>
    </nav></header>
    <main className="mx-auto max-w-[1200px] pb-16">
      <section className="pt-[66px] pb-14 text-center [@media(max-width:760px)]:px-5 [@media(max-width:760px)]:py-[42px]" aria-labelledby="title">
        <h1 className="my-[26px] bg-[linear-gradient(#f3ecff,#be9be7)] bg-clip-text text-[84px] leading-none tracking-[-3px] text-transparent [@media(max-width:760px)]:text-[52px] [@media(max-width:760px)]:tracking-[-2px]" id="title">Start with a<br />conversation.</h1>
        <p className="my-8 text-[21px] text-muted">Explore a candidate demo. No live AI or official interview.</p>
        <div className="flex justify-center gap-3.5 [@media(max-width:760px)]:flex-wrap"><a className="inline-flex min-h-[46px] min-w-[158px] items-center justify-center rounded-[10px] border border-[#b28bdd] bg-brand px-[27px] py-3.5 text-sm leading-normal" href="/roles">View roles</a><a className="inline-flex min-h-[46px] items-center justify-center rounded-[10px] border border-[#89709f] bg-[#1a1227] px-[27px] py-3.5 text-sm leading-normal" href="/roles#invitation">I have an invitation</a></div>
      </section>
      <section className="rounded-3xl border border-[#70478e] bg-[radial-gradient(ellipse_at_center,#2b1644,#100b1b_85%)] p-[27px] [@media(max-width:760px)]:mx-4" aria-label="Example interview preview">
        <div className="flex items-center justify-between text-sm leading-normal text-muted"><span>Voice interview</span></div>
        <div className="mt-8 mb-10 text-center"><img className="inline-block" src="/images/robot.svg" alt="Purple interview robot" width="230" height="230" /></div>
        <div className="flex items-center justify-between text-[13px] text-muted"><span>Interview language: Vietnamese</span></div>
      </section>
    </main>
  </>;
}
import AccountControl from './auth-ui/AccountControl';
