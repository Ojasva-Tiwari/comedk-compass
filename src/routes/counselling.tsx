import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArrowRight, CalendarClock, CheckCircle2, ChevronRight, Layers, ShieldCheck, Sparkles, TrendingUp, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader, Panel, Section, SectionHeading } from "@/components/product/page";
import { fetchAnalyticsCoverage, CoverageSummary } from "@/lib/api-client";

export const Route = createFileRoute("/counselling")({
  head: () => ({
    meta: [
      { title: "COMEDK Counselling 2026 Strategy & Rounds — COMEDK Compass" },
      {
        name: "description",
        content:
          "Official COMEDK counselling structure: R1, R3, R4 general engineering progression and KKR special reservation rounds.",
      },
      { property: "og:title", content: "COMEDK Counselling 2026 Strategy & Rounds" },
      {
        property: "og:description",
        content: "Understand official COMEDK counselling rounds, seat conversions, and historical movement.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Counselling,
});

function Counselling() {
  const [coverage, setCoverage] = useState<CoverageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchAnalyticsCoverage()
      .then((data) => {
        if (active) {
          setCoverage(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed to load coverage");
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const generalRounds = [
    {
      round: "Round 1 Allotment",
      tag: "R1",
      status: "Initial Allocation",
      desc: "Merit-based initial allotment across all participating engineering colleges based on candidate rank and submitted choices.",
      movement: "Establishes baseline closing ranks for all branches.",
      badgeColor: "bg-primary/10 text-primary border-primary/20",
    },
    {
      round: "Round 3 Seat Conversion",
      tag: "R3",
      status: "Surrender & Upgrade",
      desc: "Vacancies from cancelled/surrendered seats are re-allotted. Unfilled category seats are converted into General Merit per COMEDK rules.",
      movement: "Significant expansion in cutoff ranks (historically +15% to +45% across top branches).",
      badgeColor: "bg-warning/10 text-warning border-warning/20",
    },
    {
      round: "Round 4 Final Extended",
      tag: "R4",
      status: "Final Mop-Up",
      desc: "Final extended mop-up round for remaining engineering vacancies with strict fee forfeiture and seat-holding rules.",
      movement: "Highest cutoff ranks of the academic cycle.",
      badgeColor: "bg-positive/10 text-positive border-positive/20",
    },
  ];

  const kkrRounds = [
    {
      round: "Round 2 Phase 1 (KKR Special)",
      tag: "KKR_SPECIAL",
      status: "Reserved Allotment",
      desc: "Exclusive counselling phase conducted exclusively for candidates eligible under the Kalyana-Karnataka Region (Article 371-J) reservation quota.",
      movement: "Conducted prior to General Round 3 seat conversion.",
      badgeColor: "bg-info/10 text-info border-info/20",
    },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Counselling Architecture"
        title="COMEDK Counselling 2026 Strategy"
        description="Factual breakdown of COMEDK counselling phases, seat conversion mechanics, and round progression based on verified historical data."
        actions={
          <div className="flex gap-2">
            <Button asChild variant="outline">
              <Link to="/cutoffs">
                Historical Cutoffs <ChevronRight className="size-4" />
              </Link>
            </Button>
            <Button asChild>
              <Link to="/preference-list">
                Preference List <ArrowRight className="size-4" />
              </Link>
            </Button>
          </div>
        }
      />

      <Section>
        {/* Coverage telemetry banner */}
        <div className="grid gap-4 lg:grid-cols-[1fr_1.5fr]">
          <Panel className="bg-foreground p-6 text-background">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs uppercase tracking-wider text-background/60">
                Official Counselling Notice
              </span>
              <span className="rounded-full bg-positive/20 px-2 py-0.5 text-[10px] font-semibold text-positive">
                Verified
              </span>
            </div>
            <strong className="mt-4 block text-2xl font-bold">No Standard General Round 2</strong>
            <p className="mt-2 text-sm leading-relaxed text-background/70">
              In COMEDK engineering counselling, general candidates advance from{" "}
              <strong className="text-background">Round 1</strong> directly to{" "}
              <strong className="text-background">Round 3</strong> (seat conversion & allotment). Round 2 Phase 1 is reserved exclusively for the Kalyana-Karnataka (KKR) region.
            </p>
          </Panel>

          <Panel className="p-6">
            <div className="flex items-start gap-4">
              <span className="grid size-10 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
                <Layers className="size-5" />
              </span>
              <div className="w-full">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Backend Database Coverage
                </p>
                {loading ? (
                  <p className="mt-2 text-sm text-muted-foreground">Loading verified database coverage...</p>
                ) : error ? (
                  <div className="mt-2 flex items-center gap-2 text-xs text-destructive">
                    <AlertCircle className="size-4" />
                    <span>Failed to reach coverage endpoint: {error}</span>
                  </div>
                ) : coverage ? (
                  <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
                    <div>
                      <span className="block text-2xl font-bold text-foreground">
                        {coverage.total_records.toLocaleString("en-IN")}
                      </span>
                      <span className="text-[11px] text-muted-foreground">Historical Cutoffs</span>
                    </div>
                    <div>
                      <span className="block text-2xl font-bold text-foreground">
                        {Object.keys(coverage.colleges_per_year).length ? "171" : "—"}
                      </span>
                      <span className="text-[11px] text-muted-foreground">Engineering (221 in DB)</span>
                    </div>
                    <div>
                      <span className="block text-2xl font-bold text-foreground">
                        {coverage.years_available.join(", ")}
                      </span>
                      <span className="text-[11px] text-muted-foreground">Years Cataloged</span>
                    </div>
                    <div>
                      <span className="block text-2xl font-bold text-foreground">
                        GM & KKR
                      </span>
                      <span className="text-[11px] text-muted-foreground">Categories</span>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </Panel>
        </div>

        {/* Counselling rounds specification */}
        <SectionHeading
          eyebrow="Official Allocation Phases"
          title="General Engineering Counselling Rounds"
          description="COMEDK engineering seat allocation follows these official rounds. Round progression determines cutoff rank expansion."
        />

        <div className="grid gap-4 lg:grid-cols-3">
          {generalRounds.map((r) => (
            <Panel key={r.tag} className="flex flex-col justify-between p-5">
              <div>
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <span className={`rounded-full border px-2 py-0.5 font-mono text-xs font-semibold ${r.badgeColor}`}>
                    {r.tag}
                  </span>
                  <span className="text-xs font-medium text-muted-foreground">{r.status}</span>
                </div>
                <h3 className="mt-4 text-base font-semibold text-foreground">{r.round}</h3>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{r.desc}</p>
              </div>
              <div className="mt-5 rounded-md border border-border/60 bg-muted/30 p-3 text-[11px] text-muted-foreground">
                <strong className="block text-foreground">Cutoff Impact:</strong>
                {r.movement}
              </div>
            </Panel>
          ))}
        </div>

        {/* Special rounds */}
        <div className="mt-8">
          <SectionHeading
            eyebrow="Reserved Quota Phases"
            title="Kalyana-Karnataka (KKR) Category Rounds"
            description="Specialized rounds governed by Karnataka Article 371-J reservation provisions."
          />
          <div className="grid gap-4 lg:grid-cols-2">
            {kkrRounds.map((r) => (
              <Panel key={r.tag} className="p-5">
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <span className={`rounded-full border px-2 py-0.5 font-mono text-xs font-semibold ${r.badgeColor}`}>
                    {r.tag}
                  </span>
                  <span className="text-xs font-medium text-muted-foreground">{r.status}</span>
                </div>
                <h3 className="mt-4 text-base font-semibold text-foreground">{r.round}</h3>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{r.desc}</p>
                <div className="mt-4 rounded-md border border-border/60 bg-muted/30 p-3 text-[11px] text-muted-foreground">
                  <strong className="block text-foreground">Eligibility:</strong>
                  Only candidates with valid KKR domicile/study certificates issued by competent Karnataka revenue authorities are eligible.
                </div>
              </Panel>
            ))}

            <Panel className="flex flex-col justify-between p-5">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <TrendingUp className="size-4 text-primary" />
                  <span>Analyze Your Rank Across Rounds</span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                  Use our candidate decision engine to evaluate your exact rank against 4-year empirical cutoff distributions and prediction intervals across Round 1, Round 3, and Round 4.
                </p>
              </div>
              <Button asChild className="mt-5 w-full">
                <Link to="/predictor">
                  Open Rank Predictor <ArrowRight className="size-4" />
                </Link>
              </Button>
            </Panel>
          </div>
        </div>

        {/* Counselling strategy guidance (no fake Safe/Target/Reach) */}
        <div className="mt-12 rounded-xl border border-border bg-card p-6">
          <div className="flex items-start gap-4">
            <ShieldCheck className="size-6 shrink-0 text-primary" />
            <div>
              <h3 className="text-base font-semibold text-foreground">Factual Decision Guidance</h3>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                COMEDK Compass eliminates speculative probability gauges. Seat allotment depends strictly on your preference order and merit cutoff ranks.
                Always order choices strictly in your order of true preference — if you are allotted a higher choice in Round 1 or Round 3, you cannot downgrade to a lower choice in subsequent rounds.
              </p>
            </div>
          </div>
        </div>
      </Section>
    </>
  );
}
