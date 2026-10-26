// Data contract with scripts/build_site.py, which injects SiteData as JSON into
// <script id="site-data" type="application/json"> and also writes it to site/data.json.

// The closed list of classes (five loop families + Surveys) comes from config/taxonomy.json
// via SiteData.taxonomy; the app never hard-codes class or branch names.
export interface TaxonomyClass {
  name: string
  short: string // Supplementary Table S1 label, e.g. "Unrolled/DC"
  letter: string // "1".."5", "S"
  icon: string
  eligible: boolean // false for Surveys (background only, not a primary record)
  definition: string
  state: string // what is iterated (survey Fig. 1)
  timescale: string
  risk: string
  subcategories: string[] // Figure 3 branches, in display order
}

export interface Paper {
  id: string
  model: string
  title: string
  url: string
  year: number
  venue: string
  venueFull: string
  authors: string[] // "First Last"
  area: string // loop family (taxonomy class)
  areaSlug: string
  areaShort: string
  letter: string
  subsection: string // Figure 3 branch of that family
  modality: string
  task: string
  loop: string // loop mechanism
  summary: string
  datasets: string
  metrics: string
  stability: string
  validation: string
  level: string // source-record L1–L4 label (metadata only)
  status: string // Published / Accepted / Preprint
  ref: string // reference number in the survey, e.g. "[24]"
  context: boolean // ‡ context-level evidence
  eligible: boolean
  code: string // repository URL or ""
  codeStatus: string
  followUp: boolean // link identified in the survey's follow-up checks (Table S10)
  stars: number | null
  doi: string
  project: string
  suggestedBy: string // GitHub username of whoever suggested the paper, or ""
}

export interface Area {
  name: string
  short: string
  slug: string
  letter: string
  eligible: boolean
  count: number
  subsections: { name: string; count: number }[]
}

export interface SiteData {
  repo: string
  repoStars: number | null // star count of this list itself, fetched at build time
  updated: string
  papers: Paper[] // already in display order
  areas: Area[] // the taxonomy classes, in canonical order (empty classes included)
  taxonomy: TaxonomyClass[]
  counts: { listed: number; primary: number; surveys: number; queued: number; context: number; withCode: number }
}

export async function loadSiteData(): Promise<SiteData> {
  const el = document.getElementById("site-data")
  if (el?.textContent && el.textContent.trim().startsWith("{")) {
    try {
      return JSON.parse(el.textContent) as SiteData
    } catch {
      /* fall through to data.json */
    }
  }
  const res = await fetch("data.json")
  if (!res.ok) throw new Error(`Could not load data.json (HTTP ${res.status})`)
  return (await res.json()) as SiteData
}

export const isPreprint = (p: Paper) => p.status === "Preprint" || /arxiv|biorxiv|medrxiv/i.test(p.venue)

// Family colour slot (1–5, 0 for surveys); matches the --fam-N tokens in index.css.
export const famIndex = (letter: string) => (/^[1-5]$/.test(letter) ? Number(letter) : 0)

export function compact(n: number): string {
  if (n < 1000) return String(n)
  return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}k`
}

export function shortAuthors(authors: string[]): string {
  const real = authors.filter((a) => !/^et al\.?$/i.test(a.trim()))
  const last = real.map((a) => a.split(" ").slice(-1)[0])
  const more = real.length < authors.length
  return last.length <= 3 && !more ? last.join(", ") : `${last.slice(0, 3).join(", ")} et al.`
}

export function bibtex(p: Paper): string {
  const first = (p.authors[0] ?? "anon").split(" ").slice(-1)[0].toLowerCase().replace(/[^a-z]/g, "")
  const word = p.title.toLowerCase().split(/\W+/).find((w) => w.length > 3) ?? "paper"
  const fields: [string, string][] = [
    ["title", `{${p.title}}`],
    ["author", p.authors.filter((a) => !/^et al\.?$/i.test(a.trim())).join(" and ") + (p.authors.some((a) => /^et al/i.test(a.trim())) ? " and others" : "")],
    ["year", String(p.year)],
    ["howpublished", p.venueFull || p.venue],
    ["url", p.url],
  ]
  if (p.doi) fields.push(["doi", p.doi])
  const body = fields.map(([k, v]) => `  ${k.padEnd(12)} = {${v}}`).join(",\n")
  return `@misc{${first}${p.year}${word},\n${body}\n}`
}
