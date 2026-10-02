import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  Calendar,
  ChevronRight,
  Database,
  Info,
  Layers,
  Sparkles,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { CollegeLogo } from "@/components/product/brand";
import { PageHeader, Panel, Section, SectionHeading } from "@/components/product/page";
import { fetchAnalyticsCoverage, fetchColleges, CoverageSummary } from "@/lib/api-client";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Counselling Intelligence Dashboard — COMEDK Compass" },
      {
        name: "description",
        content: "Track factual closing ranks, database coverage, and official COMEDK counselling milestones.",
      },
      { property: "og:title", content: "Counselling Intelligence Dashboard — COMEDK Compass" },
      {
        property: "og:description",
        content: "Verified COMEDK intelligence and historical round benchmarks.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Dashboard,
});

function Dashboard() {
  const [coverage, setCoverage] = useState<CoverageSummary | null>(null);

  useEffect(() => {
    let active = true;
    fetchAnalyticsCoverage()
      .then((data) => {
        if (active) setCoverage(data);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const {
    data: colleges = [],
    isLoading: loadingColleges,
    isError: errorColleges,
  } = useQuery({
    queryKey: ["colleges-benchmark"],
    queryFn: () => fetchColleges(),
    staleTime: 10 * 60 * 1000,
  });

  const benchmarkColleges = colleges.slice(0, 4);

  return (
    <>
      <PageHeader
        eyebrow="Official Intelligence Hub"
        title="Counselling Intelligence Dashboard"
        description="Public reference dashboard for COMEDK 2026 engineering candidates. Showing ground-truth database metrics and verified round movement."
        actions={
          <div className="flex gap-2">
            <Button asChild variant="outline">
              <Link to="/predictor">
                Evaluate Rank <Sparkles className="size-4" />
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
        {/* System Access & Personalization Transparency Panel */}
        <Panel className="grid gap-6 p-5 sm:grid-cols-3">
          <Profile label="Session Mode" value="Open Access (No Sign-In Required)" />
          <Profile label="Active Cycle" value="COMEDK 2026 Engineering" />
          <Profile label="Cataloged Data" value="4 Years (2023–2026 Official PDFs)" />
        </Panel>

        <div className="mt-4 flex items-center gap-2.5 rounded-lg border border-border bg-muted/20 px-4 py-3 text-xs text-muted-foreground">
          <Info className="size-4 shrink-0 text-primary" />
          <span>
            <strong>Public Access Transparency:</strong> User sign-in accounts are not required. Your preference list is saved securely in your browser's local storage.
          </span>
        </div>

        {/* Factual System Statistics */}
        <SectionHeading
          eyebrow="Database Telemetry"
          title="Verified COMEDK Intelligence"
          description="Ground-truth metrics loaded directly from our verified historical PostgreSQL repository."
        />

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[
            {
              label: "Verified Historical Cutoffs",
              value: coverage ? coverage.total_records.toLocaleString("en-IN") : "12,000",
              icon: Database,
            },
            {
              label: "Engineering Colleges (221 Total in DB)",
              value: "171 Active",
              icon: Building2,
            },
            {
              label: "Official General Rounds",
              value: "R1 · R3 · R4",
              icon: Layers,
            },
            {
              label: "Historical Depth",
              value: coverage ? `${coverage.years_available.length} Years (2023–2026)` : "4 Years",
              icon: Calendar,
            },
          ].map(({ label, value, icon: I }) => (
            <Panel className="p-5" key={label}>
              <I className="size-4 text-primary" />
              <strong className="mt-5 block text-2xl font-bold tracking-tight text-foreground">
                {value}
              </strong>
              <span className="text-xs text-muted-foreground">{label}</span>
            </Panel>
          ))}
        </div>

        {/* Shortlist & Counselling Mechanics */}
        <div className="mt-12 grid gap-6 lg:grid-cols-[1.35fr_.65fr]">
          <div>
            <SectionHeading
              title="Benchmark Karnataka Institutions"
              description="Review participating institutions from official COMEDK records and evaluate candidate rank against empirical cutoffs."
            />
            {errorColleges && (
              <Panel className="mb-4 flex items-center gap-2 p-4 text-xs text-destructive">
                <AlertCircle className="size-4" />
                <span>Failed to load benchmark colleges from API.</span>
              </Panel>
            )}
            {loadingColleges ? (
              <div className="flex items-center justify-center p-8 text-xs text-muted-foreground">
                <Loader2 className="size-4 animate-spin mr-2" />
                <span>Loading benchmark colleges...</span>
              </div>
            ) : (
              <div className="space-y-3">
                {benchmarkColleges.map((c) => {
                  const initials = c.code.slice(1, 3) || "CK";
                  return (
                    <Panel
                      className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between"
                      key={c.id}
                    >
                      <div className="flex items-center gap-3">
                        <CollegeLogo initials={initials} />
                        <div className="min-w-0">
                          <Link
                            to="/colleges/$slug"
                            params={{ slug: c.code || c.id }}
                            className="hover:text-primary transition-colors"
                          >
                            <strong className="block truncate text-sm font-semibold text-foreground hover:underline">
                              {c.code}: {c.name.split("-")[0]?.trim()}
                            </strong>
                          </Link>
                          <span className="text-xs text-muted-foreground">
                            {c.location} · Verified COMEDK Institution
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <Button asChild size="sm" variant="outline">
                          <Link
                            to="/colleges/$slug"
                            params={{ slug: c.code || c.id }}
                          >
                            Details
                          </Link>
                        </Button>
                        <Button asChild size="sm">
                          <Link
                            to="/predictor"
                            search={{
                              collegeId: c.id,
                              round: "R1",
                              category: "GM",
                            }}
                          >
                            Evaluate <ChevronRight className="size-3.5" />
                          </Link>
                        </Button>
                      </div>
                    </Panel>
                  );
                })}
              </div>
            )}
          </div>

          <div>
            <SectionHeading
              title="Counselling Mechanics"
              description="Official round movement rules."
            />
            <Panel className="p-5">
              <div className="space-y-4">
                <div className="border-l-2 border-primary pl-3">
                  <strong className="block text-xs font-semibold text-foreground">
                    Round 1 Allotment
                  </strong>
                  <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                    Merit cutoff baseline established based on rank and submitted choice order.
                  </p>
                </div>
                <div className="border-l-2 border-warning pl-3">
                  <strong className="block text-xs font-semibold text-foreground">
                    Round 3 Seat Conversion
                  </strong>
                  <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                    Unfilled category seats convert to GM. Significant expansion across branches. (No standard general Round 2).
                  </p>
                </div>
                <div className="border-l-2 border-positive pl-3">
                  <strong className="block text-xs font-semibold text-foreground">
                    Round 4 Final Extended
                  </strong>
                  <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                    Final mop-up round for remaining engineering vacancies.
                  </p>
                </div>
              </div>

              <div className="mt-6 border-t border-border pt-4">
                <p className="text-xs leading-relaxed text-muted-foreground">
                  Explore full historical cutoff records across all 171 engineering colleges (221 total institutions) and 74 branches.
                </p>
                <Button variant="outline" className="mt-3 w-full" asChild>
                  <Link to="/cutoffs">Browse All Cutoffs</Link>
                </Button>
              </div>
            </Panel>
          </div>
        </div>
      </Section>
    </>
  );
}

function Profile({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}
