import { useEffect, useState } from "react"
import { ArrowRight, BookOpen, GitPullRequest, Plus, Quote, Star } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Explorer } from "@/components/Explorer"
import { LoopFigure } from "@/components/LoopFigure"
import { GitHubMark } from "@/components/Papers"
import { ThemePicker } from "@/components/ThemePicker"
import { compact, famIndex, loadSiteData, type SiteData } from "@/data"
import { cn } from "@/lib/utils"

declare global {
  interface Window {
    __amjBootDone?: () => void
  }
}

function Logo() {
  return (
    <svg viewBox="0 0 30 30" className="size-6" aria-hidden>
      <circle cx="15" cy="15" r="10" fill="none" className="stroke-primary" strokeWidth="3.2" strokeDasharray="48 15" />
      <path d="M23.5 4.5 L26.5 11 L19.5 10.5 z" className="fill-target" />
      <circle cx="15" cy="15" r="3.2" className="fill-target" />
    </svg>
  )
}

// Websites cannot star a repository for the visitor (GitHub requires the visitor's own sign-in),
// so the button opens the repository, where Star is one click away.
function useLiveStars(repo: string, initial: number | null) {
  const [stars, setStars] = useState(initial)
  useEffect(() => setStars(initial), [initial])
  useEffect(() => {
    const m = repo.match(/github\.com\/([^/]+)\/([^/#?]+)/)
    if (!m) return
    fetch(`https://api.github.com/repos/${m[1]}/${m[2]}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => typeof d?.stargazers_count === "number" && setStars(d.stargazers_count))
      .catch(() => {})
  }, [repo])
  return stars
}

function StarButton({ repo, stars, size = "sm", label = "Star" }: {
  repo: string; stars: number | null; size?: "sm" | "lg"; label?: string
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <a
          href={repo}
          target="_blank"
          rel="noreferrer"
          aria-label={`${label.includes("GitHub") ? label : `${label} on GitHub`}${stars !== null ? `, ${stars} stars` : ""}`}
          className={cn(
            "inline-flex items-stretch overflow-hidden rounded-md border bg-background font-medium shadow-sm transition-colors hover:border-primary/60",
            size === "lg" ? "h-10 text-sm" : "h-8 text-xs",
          )}
        >
          <span className={cn("flex items-center gap-1.5 hover:bg-accent", size === "lg" ? "px-4" : "px-2.5")}>
            <Star className={cn("fill-target text-target", size === "lg" ? "size-4" : "size-3.5")} />
            {label}
          </span>
          {stars !== null && (
            <span className={cn("flex items-center border-l bg-muted/60 font-mono tabular-nums", size === "lg" ? "px-3" : "px-2")}>
              {compact(stars)}
            </span>
          )}
        </a>
      </TooltipTrigger>
      <TooltipContent>Opens the repository on GitHub, where Star is one click</TooltipContent>
    </Tooltip>
  )
}

function Header({ repo, stars }: { repo: string; stars: number | null }) {
  return (
    <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
        <a href="#top" className="flex items-center gap-2.5 font-semibold tracking-tight">
          <Logo />
          <span className="hidden sm:inline">Awesome Looped Models <span className="font-normal text-muted-foreground">for Medical Imaging</span></span>
          <span className="sm:hidden">Looped Models</span>
        </a>
        <nav className="hidden items-center gap-1 text-sm md:flex" aria-label="Sections">
          <Button asChild variant="ghost" size="sm"><a href="#papers">Papers</a></Button>
          <Button asChild variant="ghost" size="sm"><a href="#what-is-a-loop">What is a loop?</a></Button>
          <Button asChild variant="ghost" size="sm"><a href="#contribute">Contribute</a></Button>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Button asChild variant="ghost" size="icon" className="h-8 w-8" aria-label="GitHub repository">
            <a href={repo} target="_blank" rel="noreferrer">
              <GitHubMark />
            </a>
          </Button>
          <StarButton repo={repo} stars={stars} />
          <ThemePicker />
        </div>
      </div>
    </header>
  )
}

function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="flex flex-col gap-1 border-l pl-4 first:border-l-0 first:pl-0">
      <span className="font-mono text-2xl font-medium tabular-nums tracking-tight">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}

function Hero({ data, stars }: { data: SiteData; stars: number | null }) {
  const years = data.papers.map((p) => p.year)
  return (
    <section id="top" className="grid items-center gap-12 pb-16 pt-12 lg:grid-cols-[1fr_1.05fr] lg:pt-20">
      <div className="flex min-w-0 flex-col gap-6">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-muted-foreground">
          Survey companion list <span className="mx-1 text-primary">·</span> updated {data.updated}
        </p>
        <h1 className="font-serif text-5xl leading-[1.02] tracking-tight sm:text-6xl lg:text-7xl">
          Awesome <em className="text-primary">Looped</em> Models for Medical Imaging
        </h1>
        <p className="max-w-xl text-lg leading-relaxed text-muted-foreground">
          Papers and code in which a medical imaging model, its training data or the deployed system is updated by
          <span className="text-foreground"> repeated computation</span> rather than a single forward pass: recurrent and
          equilibrium networks, unrolled reconstruction, test-time adaptation, data-feedback training, and human,
          deployment and lifelong loops.
        </p>
        <div className="flex flex-wrap gap-x-6 gap-y-4">
          <Stat value={data.papers.length} label="papers" />
          <Stat value={data.counts.primary} label="primary records" />
          <Stat value={data.counts.withCode} label="with code" />
          <Stat value={`${Math.min(...years)}–${Math.max(...years)}`} label="years covered" />
        </div>
        <div className="flex flex-wrap gap-3">
          <Button asChild size="lg" className="gap-2">
            <a href="#papers">
              Browse papers <ArrowRight />
            </a>
          </Button>
          <StarButton repo={data.repo} stars={stars} size="lg" label="Star on GitHub" />
          <Button asChild size="lg" variant="ghost" className="gap-2">
            <a href={`${data.repo}/issues/new?template=add-paper.yml`} target="_blank" rel="noreferrer">
              <Plus /> Suggest a paper
            </a>
          </Button>
        </div>
      </div>
      <div className="min-w-0 rounded-xl border bg-card p-5 sm:p-7">
        <LoopFigure taxonomy={data.taxonomy} areas={data.areas} />
      </div>
    </section>
  )
}

const FAM_TEXT = ["text-fam-0", "text-fam-1", "text-fam-2", "text-fam-3", "text-fam-4", "text-fam-5"]
const FAM_BORDER = ["border-l-fam-0", "border-l-fam-1", "border-l-fam-2", "border-l-fam-3", "border-l-fam-4", "border-l-fam-5"]

function Sub({ children }: { children: React.ReactNode }) {
  return <sub className="text-[0.7em]">{children}</sub>
}

function About({ taxonomy, counts }: { taxonomy: SiteData["taxonomy"]; counts: SiteData["counts"] }) {
  return (
    <section id="what-is-a-loop" className="grid gap-10 border-t py-16 lg:grid-cols-[1fr_1.15fr]">
      <div className="flex flex-col gap-4">
        <h2 className="font-serif text-4xl tracking-tight">What is a looped model?</h2>
        <p className="max-w-prose leading-relaxed text-muted-foreground">
          A feed-forward network maps an input to an output once. Many medical imaging methods instead refine a result
          through iteration: reconstruction networks alternate a learned prior with physics-based data consistency,
          segmentation models adapt to each new scan, semi-supervised pipelines feed their own predictions back as
          labels, and deployed systems are corrected by clinicians or recalibrated after a scanner change.
        </p>
        <p className="max-w-prose leading-relaxed text-muted-foreground">
          The survey describes every loop by four elements: the <span className="text-foreground">state</span> that is
          iterated, the <span className="text-foreground">operator</span> that updates it, the{" "}
          <span className="text-foreground">feedback</span> that closes the loop, and the{" "}
          <span className="text-foreground">stopping rule</span>.
        </p>
        <div className="rounded-lg border bg-card px-5 py-4 text-center font-serif text-2xl italic tracking-tight">
          s<Sub>k+1</Sub> = Φ(s<Sub>k</Sub>, g<Sub>k</Sub>; θ),&ensp; g<Sub>k</Sub> = G(s<Sub>k</Sub>, I<Sub>k</Sub>)
          <p className="mt-2 font-sans text-xs not-italic text-muted-foreground">
            I<Sub>k</Sub>: measurements, a test image, unlabeled data, an annotator or a deployment stream
          </p>
        </div>
        <p className="max-w-prose text-sm leading-relaxed text-muted-foreground">
          Families differ in what s is, where g comes from and how long one iteration takes. Code badges marked * were
          found in the survey's follow-up checks rather than in the curated record; ‡ marks the {counts.context} records the
          survey's audit judged to be context-level evidence. Venues in italics are preprints.
        </p>
      </div>
      <div className="flex flex-col gap-3">
        <h3 className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
          Survey taxonomy: five loop families + surveys
        </h3>
        {taxonomy.map((c) => {
          const f = famIndex(c.letter)
          return (
            <div key={c.name} className={cn("flex gap-4 rounded-lg border border-l-4 bg-card p-4", FAM_BORDER[f])}>
              <span className={cn("mt-0.5 w-4 shrink-0 font-mono text-sm font-semibold", FAM_TEXT[f])} aria-hidden>{c.letter}</span>
              <div className="min-w-0">
                <p className="font-medium">
                  {c.name}
                  {!c.eligible && <span className="ml-2 text-xs font-normal text-muted-foreground">background only, not counted as primary records</span>}
                </p>
                <p className="mt-0.5 text-sm text-muted-foreground">{c.definition}</p>
                {c.state && (
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    <span className="text-foreground">Iterates</span> {c.state} · <span className="text-foreground">timescale</span> {c.timescale} ·{" "}
                    <span className="text-foreground">risk</span> {c.risk}
                  </p>
                )}
                <p className="mt-1.5 font-mono text-[11px] text-muted-foreground">{c.subcategories.join(" · ")}</p>
              </div>
            </div>
          )
        })}
        {counts.queued > 0 && (
          <p className="text-sm text-muted-foreground">
            {counts.queued} more papers are awaiting a maintainer's classification and are not listed yet.
          </p>
        )}
      </div>
    </section>
  )
}

function Cite({ repo }: { repo: string }) {
  const bib = `@misc{saswato2026looped,
  title  = {Looped Models for Medical Imaging: A Survey of Iterative
            Architectures, Test-Time Adaptation, and Feedback},
  author = {Saswato, Aritra Islam and Karim, Labiba Faiza and Khan, Md. Misbah
            and Khan, Nishan and Ahmed, Istiak and Ahmed, Galib and
            Sanjid, Kazi Shahriar and Hossain, Md. Tanzim and Uddin, M. Monir},
  year   = {2026},
  note   = {Preprint, October 2026}
}`
  return (
    <section id="cite" className="grid gap-8 border-t py-16 lg:grid-cols-[1fr_1.15fr]">
      <div className="flex flex-col gap-3">
        <h2 className="font-serif text-4xl tracking-tight">Cite the survey</h2>
        <p className="max-w-prose text-muted-foreground">
          This list accompanies <em className="text-foreground">Looped Models for Medical Imaging: A Survey of Iterative
          Architectures, Test-Time Adaptation, and Feedback</em> (Big-Matrix Lab, North South University). The survey's
          curated corpus runs to 22 October 2026; it is curated rather than exhaustive.
        </p>
        <p className="text-sm text-muted-foreground">
          To cite the list itself, use{" "}
          <a className="underline underline-offset-4 hover:text-foreground" href={`${repo}/blob/main/CITATION.cff`}>CITATION.cff</a>.
        </p>
      </div>
      <pre className="overflow-x-auto rounded-lg border bg-muted p-4 font-mono text-[12px] leading-relaxed">{bib}</pre>
    </section>
  )
}

function Contribute({ repo }: { repo: string }) {
  const items = [
    { icon: Plus, title: "Suggest a paper", body: "Open an issue with the Add a paper form.", href: `${repo}/issues/new?template=add-paper.yml` },
    { icon: GitPullRequest, title: "Open a pull request", body: "Add a row to data/papers.csv; the site rebuilds itself.", href: `${repo}/blob/main/CONTRIBUTING.md` },
    { icon: Quote, title: "Classification guide", body: "How a paper is placed on the survey's Figure 3.", href: `${repo}/blob/main/docs/classification-guide.md` },
  ]
  return (
    <section id="contribute" className="border-t py-16">
      <h2 className="font-serif text-4xl tracking-tight">Contribute</h2>
      <p className="mt-2 max-w-prose text-muted-foreground">
        Know a looped model for medical imaging that belongs here, or spotted a wrong link? Corrections are as valuable as additions.
      </p>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {items.map(({ icon: Icon, title, body, href }) => (
          <a key={title} href={href} target="_blank" rel="noreferrer"
            className="group flex flex-col gap-2 rounded-lg border bg-card p-5 transition-colors hover:border-primary/50">
            <Icon className="size-5 text-primary" />
            <span className="font-medium group-hover:underline">{title}</span>
            <span className="text-sm text-muted-foreground">{body}</span>
          </a>
        ))}
      </div>
    </section>
  )
}

function Footer({ repo }: { repo: string }) {
  return (
    <footer className="border-t py-10 text-sm text-muted-foreground">
      <div className="flex flex-col gap-2 sm:flex-row sm:justify-between">
        <span className="flex items-center gap-2">
          <BookOpen className="size-4" /> Generated from{" "}
          <a className="underline underline-offset-4 hover:text-foreground" href={`${repo}/blob/main/data/papers.csv`}>data/papers.csv</a>
        </span>
        <span>
          List released under{" "}
          <a className="underline underline-offset-4 hover:text-foreground" href="https://creativecommons.org/publicdomain/zero/1.0/">CC0 1.0</a>.
          Papers and code keep their own licenses.
        </span>
      </div>
    </footer>
  )
}

function Loading() {
  return (
    <div className="grid gap-4 py-16 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-56 rounded-lg" />)}
    </div>
  )
}

export default function App() {
  const [data, setData] = useState<SiteData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadSiteData().then(setData).catch((e: Error) => setError(e.message))
  }, [])

  // Dismiss the boot loader (index.html) once the app has rendered and the fonts are in,
  // waiting at most 1.5 s for fonts so a slow font server never holds the page back.
  useEffect(() => {
    if (!data && !error) return
    const fontsReady = Promise.race([document.fonts?.ready, new Promise((r) => setTimeout(r, 1500))])
    fontsReady.then(() => requestAnimationFrame(() => window.__amjBootDone?.()))
  }, [data, error])

  const repo = data?.repo ?? "https://github.com/Big-Matrix-R-And-D-Lab/Awesome-Looped-Models-for-Medical-Imaging"
  const stars = useLiveStars(repo, data?.repoStars ?? null)
  return (
    <>
      <Header repo={repo} stars={stars} />
      <main className="mx-auto max-w-7xl px-4 sm:px-6">
        {error && <p className="py-16 text-destructive">Could not load the paper list: {error}</p>}
        {!data && !error && <Loading />}
        {data && (
          <>
            <Hero data={data} stars={stars} />
            <About taxonomy={data.taxonomy} counts={data.counts} />
            <div className="border-t pt-16">
              <Explorer papers={data.papers} areas={data.areas} />
            </div>
            <Cite repo={repo} />
            <Contribute repo={repo} />
          </>
        )}
        <Footer repo={repo} />
      </main>
    </>
  )
}
