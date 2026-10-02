import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BarChart3, Check, GitCompareArrows, Layers, ShieldCheck, Sparkles, Target, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fetchColleges, fetchAnalyticsCoverage, CANONICAL_COLLEGES } from "@/lib/api-client";
import { CollegeCard, RoundCutoffTimeline, SourceBadge, TrendChart } from "@/components/product/data-ui";
import { CompassMark } from "@/components/product/brand";
import { Panel, Section, SectionHeading } from "@/components/product/page";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "COMEDK Compass — Counselling Intelligence" },
      {
        name: "description",
        content: "Navigate COMEDK counselling with historical cutoffs, round progression, fees and seat matrix data.",
      },
      { property: "og:title", content: "COMEDK Compass — Counselling Intelligence" },
      { property: "og:description", content: "Navigate counselling with data, not guesswork." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const RNSIT_CSE_TREND = [5690, 6488, 7552];

function Index() {
  const [rank, setRank] = useState("18432");
  const [shown, setShown] = useState(false);

  const { data: colleges = CANONICAL_COLLEGES, isLoading: loadingColleges } = useQuery({
    queryKey: ["colleges-featured"],
    queryFn: () => fetchColleges(),
    staleTime: 10 * 60 * 1000,
  });

  const { data: coverage } = useQuery({
    queryKey: ["coverage-summary"],
    queryFn: () => fetchAnalyticsCoverage(),
    staleTime: 10 * 60 * 1000,
  });

  return (
    <div className="overflow-hidden">
      <section className="relative border-b border-border bg-grid">
        <div className="mx-auto grid min-h-[760px] max-w-[1440px] items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1.05fr_.95fr] lg:px-8 lg:py-20">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
            <p className="eyebrow">COMEDK 2026 counselling intelligence</p>
            <h1 className="mt-6 max-w-3xl text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl xl:text-7xl">
              Stop guessing your college.<br />
              <span className="text-primary">Start navigating it.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
              Explore historical cutoffs, round progression, fees, seat matrix and counselling trends — all grounded in verified COMEDK database records.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" asChild>
                <Link to="/colleges" search={{ rank: Number(rank) || undefined }}>
                  Find my colleges <ArrowRight />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link to="/cutoffs">Explore cutoffs</Link>
              </Button>
            </div>
            <div className="mt-12 max-w-xl rounded-lg border border-border bg-card p-3 shadow-md">
              <div className="grid gap-3 sm:grid-cols-[1fr_130px_auto]">
                <label className="px-2">
                  <span className="text-[10px] font-semibold uppercase text-muted-foreground">Your rank</span>
                  <Input
                    aria-label="Your COMEDK rank"
                    value={rank}
                    onChange={(e) => setRank(e.target.value)}
                    className="mt-1 border-0 bg-transparent px-0 font-mono text-lg shadow-none focus-visible:ring-0"
                  />
                </label>
                <div className="border-t border-border px-2 pt-3 sm:border-l sm:border-t-0 sm:pt-0">
                  <span className="text-[10px] font-semibold uppercase text-muted-foreground">Stream</span>
                  <p className="mt-2 text-sm font-medium">Engineering</p>
                </div>
                <Button className="h-full min-h-12" onClick={() => setShown(true)}>
                  Show options
                </Button>
              </div>
              {shown && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} className="overflow-hidden">
                  <div className="mt-3 flex items-center justify-between border-t border-border px-2 pt-3 text-sm">
                    <span>
                      <strong>Options available</strong>
                      <span className="ml-2 text-muted-foreground">for rank {Number(rank).toLocaleString("en-IN")}</span>
                    </span>
                    <Link to="/colleges" search={{ rank: Number(rank) || undefined }} className="font-semibold text-primary">
                      View →
                    </Link>
                  </div>
                </motion.div>
              )}
            </div>
          </motion.div>
          <DecisionMap />
        </div>
      </section>

      <Section>
        <SectionHeading
          eyebrow="Decision system"
          title="Your rank is only the beginning."
          description="Turn one score into a round-aware counselling strategy, backed by clearly sourced historical data."
        />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: Target, title: "Rank decision engine", desc: "Evaluate candidate rank against historical closing prediction intervals." },
            { icon: BarChart3, title: "Cutoff intelligence", desc: "Inspect historical multi-year movement across official rounds." },
            { icon: Layers, title: "Round progression", desc: "Follow cutoff expansion across canonical R1, R3, and R4 rounds." },
            { icon: GitCompareArrows, title: "College comparison", desc: "Compare outcomes, fees and verified data in context." },
          ].map(({ icon: Icon, title, desc }, i) => (
            <Panel className="p-5" key={title}>
              <div className="flex items-center justify-between">
                <span className="grid size-9 place-items-center rounded-md bg-primary/10 text-primary">
                  <Icon className="size-4" />
                </span>
                <span className="font-mono text-[10px] text-muted-foreground">0{i + 1}</span>
              </div>
              <h3 className="mt-7 font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{desc}</p>
              <div className="mt-5 flex h-8 items-end gap-1">
                {[35, 62, 48, 78, 92].map((h, j) => (
                  <span key={j} className="flex-1 rounded-sm bg-primary/15" style={{ height: `${h}%` }} />
                ))}
              </div>
            </Panel>
          ))}
        </div>
      </Section>

      <section className="border-y border-border bg-foreground text-background">
        <Section className="py-8">
          <div className="grid gap-8 md:grid-cols-[1.2fr_repeat(3,1fr)] md:items-center">
            <div>
              <div className="flex items-center gap-2">
                <span className="size-2 animate-pulse rounded-full bg-positive" />
                <span className="font-mono text-xs uppercase">Counselling status · Verified Archive</span>
              </div>
              <strong className="mt-2 block text-3xl">COMEDK 2026 Engineering</strong>
            </div>
            <Snapshot label="Database records" value={coverage ? `${coverage.total_records.toLocaleString("en-IN")} Cutoffs` : "12,000 Cutoffs"} />
            <Snapshot label="Colleges tracked" value="171 Engg (221 Total)" />
            <Snapshot label="Cycles cataloged" value="4 Years (2023–2026)" />
          </div>
        </Section>
      </section>

      <Section>
        <div className="grid gap-6 lg:grid-cols-[1.25fr_.75fr]">
          <Panel className="p-5 sm:p-7">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="eyebrow">Cutoff movement</p>
                <h2 className="mt-2 text-xl font-semibold">RNS Institute of Technology (E104)</h2>
                <p className="mt-1 text-sm text-muted-foreground">Historical closing rank · Computer Science & Engineering (GM)</p>
              </div>
            </div>
            <TrendChart values={RNSIT_CSE_TREND} />
            <SourceBadge meta={{ source: "Official COMEDK Allotment Records", year: 2026, confidence: "High" }} />
          </Panel>
          <Panel className="p-5 sm:p-7">
            <p className="eyebrow">Historical round progression</p>
            <h2 className="mt-2 text-xl font-semibold">RNSIT · CSE (GM)</h2>
            <p className="mt-1 text-sm text-muted-foreground">Official round closing milestones</p>
            <div className="mt-8">
              <RoundCutoffTimeline
                milestones={[
                  { round: "Round 1", rank: 7552, label: "Opening round" },
                  { round: "Round 3", rank: 11480, label: "General expansion" },
                  { round: "Round 4", rank: 13920, label: "Terminal cutoff" },
                ]}
              />
            </div>
            <p className="mt-8 text-xs leading-relaxed text-muted-foreground">
              Factual allotment closing ranks across General Engineering counselling rounds from published COMEDK notifications.
            </p>
          </Panel>
        </div>
      </Section>

      <Section>
        <SectionHeading
          eyebrow="College discovery"
          title="Participating Colleges from Database"
          action={
            <Button variant="outline" asChild>
              <Link to="/colleges" search={{ rank: Number(rank) || undefined }}>
                View all colleges <ArrowRight />
              </Link>
            </Button>
          }
        />
        {loadingColleges ? (
          <div className="flex items-center justify-center p-12 text-sm text-muted-foreground">
            <Loader2 className="size-5 animate-spin mr-2" />
            <span>Loading verified colleges...</span>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {colleges.slice(0, 3).map((c) => (
              <CollegeCard college={c} key={c.id} />
            ))}
          </div>
        )}
      </Section>

      <section className="border-y border-border bg-muted/40">
        <Section>
          <div className="grid gap-10 lg:grid-cols-2">
            <div>
              <p className="eyebrow">Data provenance</p>
              <h2 className="mt-3 text-3xl font-semibold">Every number has a source.</h2>
              <p className="mt-3 max-w-lg text-muted-foreground">
                Cutoffs, fees and counselling milestones stay useful only when students know where they came from, when they were recorded and how strongly they are verified.
              </p>
              <div className="mt-7 flex flex-wrap gap-2">
                {["Official COMEDK", "State Seat Circulars", "Historical Records", "Statutory Fee Notifications"].map((x) => (
                  <span key={x} className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs font-medium">
                    <ShieldCheck className="size-4 text-positive" />
                    {x}
                  </span>
                ))}
              </div>
            </div>
            <Panel className="p-6">
              <p className="eyebrow">Verified Data Policy</p>
              <h3 className="mt-3 text-xl font-semibold">Grounded in Official Records</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                COMEDK Compass strictly limits displayed metrics to published, official documentation.
              </p>
              <ul className="mt-5 grid grid-cols-2 gap-3 text-sm">
                {["Tuition fee schedules", "Seat matrix quotas", "Round-wise cutoffs", "Reservation eligibility"].map((x) => (
                  <li key={x} className="flex items-center gap-2">
                    <Check className="size-4 text-positive" />
                    {x}
                  </li>
                ))}
              </ul>
              <Button className="mt-6" variant="outline" asChild>
                <Link to="/cutoffs">
                  Explore Cutoffs Database <ArrowRight />
                </Link>
              </Button>
            </Panel>
          </div>
        </Section>
      </section>

      <Section className="py-20">
        <div className="rounded-lg bg-primary px-6 py-14 text-center text-primary-foreground sm:px-12">
          <CompassMark className="mx-auto bg-primary-foreground text-primary" />
          <h2 className="mx-auto mt-6 max-w-2xl text-3xl font-semibold sm:text-4xl">
            Your counselling journey shouldn't be a guessing game.
          </h2>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Button variant="secondary" size="lg" asChild>
              <Link to="/colleges" search={{ rank: Number(rank) || undefined }}>
                Find my colleges
              </Link>
            </Button>
            <Button size="lg" className="border border-primary-foreground/30 bg-transparent hover:bg-primary-foreground/10" asChild>
              <Link to="/cutoffs">Explore cutoffs</Link>
            </Button>
          </div>
        </div>
      </Section>
    </div>
  );
}

function Snapshot({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase text-background/60">{label}</p>
      <p className="mt-2 text-lg font-semibold">{value}</p>
    </div>
  );
}

function DecisionMap() {
  return (
    <div className="relative mx-auto w-full max-w-lg">
      <div className="absolute left-1/2 top-8 h-[82%] w-px bg-border" />
      <div className="relative space-y-7">
        {[
          { tag: "INPUT", title: "18,432", sub: "Student rank", icon: Target },
          { tag: "MATCH", title: "Official cutoffs", sub: "12,000 historical records", icon: Sparkles },
          { tag: "OPTIONS", title: "CSE · AIML · ISE · ECE", sub: "Across Karnataka", icon: GitCompareArrows },
        ].map((n, i) => (
          <motion.div
            key={n.tag}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.12 }}
            className={`relative rounded-lg border border-border bg-card p-5 shadow-md ${i === 1 ? "ml-8 sm:ml-20" : "mr-8 sm:mr-20"}`}
          >
            <div className="flex items-center gap-4">
              <span className="grid size-10 place-items-center rounded-md bg-primary/10 text-primary">
                <n.icon className="size-4" />
              </span>
              <div>
                <p className="font-mono text-[10px] text-muted-foreground">{n.tag}</p>
                <strong className="block text-lg">{n.title}</strong>
                <span className="text-xs text-muted-foreground">{n.sub}</span>
              </div>
            </div>
          </motion.div>
        ))}
        <Panel className="relative mx-4 p-5">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold">Counselling rounds</span>
            <span className="text-xs font-mono text-primary">Canonical Rounds</span>
          </div>
          <div className="mt-4">
            <RoundCutoffTimeline
              milestones={[
                { round: "R1", rank: 7552 },
                { round: "R3", rank: 11480 },
                { round: "R4", rank: 13920 },
              ]}
              compact
            />
          </div>
        </Panel>
      </div>
    </div>
  );
}
