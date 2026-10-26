// The five loop families by update timescale and system scope (after the survey's Fig. 1):
// recurrent/equilibrium updates at the centre, deployment and lifelong updates at the perimeter.
// Family names, counts, iterated state and timescale all come from the site data (config/taxonomy.json),
// and colours from the --fam-N tokens, so the figure follows every palette and dark mode.
import type { Area, TaxonomyClass } from "@/data"

const CX = 214
const CY = 212
const R0 = 50 // centre disc
const BAND = 28

const FILL = ["fill-fam-0/10", "fill-fam-1/15", "fill-fam-2/15", "fill-fam-3/15", "fill-fam-4/15", "fill-fam-5/15"]
const STROKE = ["stroke-fam-0", "stroke-fam-1", "stroke-fam-2", "stroke-fam-3", "stroke-fam-4", "stroke-fam-5"]
const SOLID = ["fill-fam-0", "fill-fam-1", "fill-fam-2", "fill-fam-3", "fill-fam-4", "fill-fam-5"]

export function LoopFigure({ taxonomy, areas }: { taxonomy: TaxonomyClass[]; areas: Area[] }) {
  const families = taxonomy.filter((c) => c.eligible).slice(0, 5)
  const count = (name: string) => areas.find((a) => a.name === name)?.count ?? 0
  const outer = R0 + BAND * families.length
  return (
    <figure className="m-0">
      <div className="-mx-1 overflow-x-auto px-1">
        <svg viewBox="0 0 700 440" className="h-auto w-full min-w-[540px] sm:min-w-0" role="img" aria-labelledby="loopfig-title loopfig-desc">
          <title id="loopfig-title">The five loop families</title>
          <desc id="loopfig-desc">
            Concentric bands, from the centre outwards: {families.map((f) => `${f.name} (${f.timescale})`).join("; ")}.
            Each band is one loop family; the loop runs longer and its risk grows towards the perimeter.
          </desc>

          {/* bands, outermost first so inner ones sit on top */}
          {[...families].reverse().map((f) => {
            const i = Number(f.letter)
            const r = R0 + BAND * i
            return (
              <g key={f.name}>
                <circle cx={CX} cy={CY} r={r} className="fill-card" />
                <circle cx={CX} cy={CY} r={r} className={`${FILL[i]} ${STROKE[i]}`} strokeWidth={1.5} />
              </g>
            )
          })}
          <circle cx={CX} cy={CY} r={R0} className="fill-card stroke-border" strokeWidth={1.5} />
          <text x={CX} y={CY - 6} textAnchor="middle" className="fill-foreground font-serif text-[17px] italic">
            s<tspan baselineShift="sub" fontSize="0.7em">k+1</tspan> =
          </text>
          <text x={CX} y={CY + 16} textAnchor="middle" className="fill-foreground font-serif text-[17px] italic">
            Φ(s<tspan baselineShift="sub" fontSize="0.7em">k</tspan>, g<tspan baselineShift="sub" fontSize="0.7em">k</tspan>)
          </text>

          {/* numbered badges on each band */}
          {families.map((f) => {
            const i = Number(f.letter)
            const rm = R0 + BAND * (i - 0.5)
            const a = (-62 * Math.PI) / 180
            const x = CX + rm * Math.cos(a)
            const y = CY + rm * Math.sin(a)
            return (
              <g key={f.name}>
                <circle cx={x} cy={y} r={10} className={SOLID[i]} />
                <text x={x} y={y + 4.5} textAnchor="middle" className="fill-background font-mono text-[12px] font-semibold">{f.letter}</text>
              </g>
            )
          })}

          {/* repeated-update arrow around the perimeter */}
          <path
            d={`M ${CX - outer - 8} ${CY + 30} A ${outer + 8} ${outer + 8} 0 0 1 ${CX - 30} ${CY - outer - 8}`}
            className="fill-none stroke-muted-foreground"
            strokeWidth={1.5}
            strokeDasharray="4 4"
          />
          <path d={`M ${CX - 30} ${CY - outer - 8} l -9 -5 l 1 10 z`} className="fill-muted-foreground" />

          <text x={CX} y={CY + outer + 22} textAnchor="middle" className="fill-muted-foreground font-mono text-[12px]">
            centre: inside one forward pass · edge: in deployment
          </text>

          {/* legend */}
          <text x={452} y={40} className="fill-muted-foreground font-mono text-[11.5px] uppercase tracking-[0.12em]">
            what is iterated · how often
          </text>
          {families.map((f, k) => {
            const i = Number(f.letter)
            const y = 76 + k * 68
            return (
              <g key={f.name}>
                <circle cx={462} cy={y - 5} r={10} className={SOLID[i]} />
                <text x={462} y={y - 0.5} textAnchor="middle" className="fill-background font-mono text-[12px] font-semibold">{f.letter}</text>
                <text x={482} y={y} className="fill-foreground font-sans text-[15px] font-semibold">
                  {f.short}
                  <tspan dx={8} className="fill-muted-foreground font-mono text-[12px] font-normal">n = {count(f.name)}</tspan>
                </text>
                <text x={482} y={y + 19} className="fill-muted-foreground font-sans text-[12.5px]">{f.state}</text>
                <text x={482} y={y + 36} className="fill-muted-foreground font-mono text-[11.5px]">{f.timescale}</text>
              </g>
            )
          })}
        </svg>
      </div>
    </figure>
  )
}
