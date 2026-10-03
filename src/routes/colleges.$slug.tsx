import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  BookmarkPlus,
  CheckCircle2,
  ChevronRight,
  GitCompareArrows,
  HelpCircle,
  History,
  Info,
  MapPin,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CollegeLogo } from "@/components/product/brand";
import { SourceBadge } from "@/components/product/data-ui";
import { EmptyState, Panel, Section, SectionHeading } from "@/components/product/page";
import {
  CANONICAL_COLLEGES,
  CANONICAL_BRANCHES,
  CANONICAL_ROUND_NAMES,
  CANONICAL_CATEGORY_NAMES,
  fetchCollegeById,
  fetchCollegesPaginated,
  fetchCutoffs,
  fetchFees,
  fetchBranches,
} from "@/lib/api-client";

interface ResolvedCollege {
  id: string;
  code: string;
  name: string;
  original_name: string;
  location: string;
  institution_type: string;
  accent: string;
}

export const Route = createFileRoute("/colleges/$slug")({
  loader: async ({ params }): Promise<{ college: ResolvedCollege }> => {
    const slugOrId = params.slug;
    const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(slugOrId);

    if (isUuid) {
      try {
        const data = await fetchCollegeById(slugOrId);
        return {
          college: {
            id: data.id,
            code: data.code,
            name: data.name,
            original_name: data.original_name,
            location: data.location || "Karnataka",
            institution_type: data.institution_type,
            accent: data.code.slice(0, 2),
          },
        };
      } catch {
        // Fallback to checking canonical list
      }
    }

    // Check canonical verified colleges
    const canonical = CANONICAL_COLLEGES.find(
      (c) =>
        c.id.toLowerCase() === slugOrId.toLowerCase() ||
        c.code.toLowerCase() === slugOrId.toLowerCase() ||
        c.shortName.toLowerCase().includes(slugOrId.toLowerCase())
    );
    if (canonical) {
      return {
        college: {
          id: canonical.id,
          code: canonical.code,
          name: canonical.name,
          original_name: canonical.name,
          location: canonical.location,
          institution_type: "ENGINEERING",
          accent: canonical.code.slice(0, 2),
        },
      };
    }

    // Attempt backend search by slug/code/query
    try {
      const res = await fetchCollegesPaginated({ query: slugOrId, limit: 1 });
      if (res.items.length > 0) {
        const item = res.items[0];
        return {
          college: {
            id: item.id,
            code: item.code,
            name: item.name,
            original_name: item.original_name,
            location: item.location || "Karnataka",
            institution_type: item.institution_type,
            accent: item.code.slice(0, 2),
          },
        };
      }
    } catch {
      // not found
    }

    throw notFound();
  },
  head: ({ loaderData }) => ({
    meta: [
      {
        title: loaderData
          ? `${loaderData.college.code} — ${loaderData.college.name} — COMEDK Compass`
          : "College Not Found — COMEDK Compass",
      },
      {
        name: "description",
        content: loaderData
          ? `Verified cutoffs, official fees, and counselling data for ${loaderData.college.name}.`
          : "Verified COMEDK college data.",
      },
      { property: "og:title", content: loaderData?.college.name ?? "College Information" },
      {
        property: "og:description",
        content: "Official COMEDK allotment closing ranks and published fee structure.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: CollegeDetail,
  notFoundComponent: () => (
    <Section>
      <Panel className="p-10 text-center">
        <p className="text-base font-semibold">College not found in verified database records.</p>
        <Button className="mt-4" asChild variant="outline">
          <Link to="/colleges">Browse College Directory</Link>
        </Button>
      </Panel>
    </Section>
  ),
});

function CollegeDetail() {
  const { college } = Route.useLoaderData();
  const [candidateRank, setCandidateRank] = useState<number>(18432);

  // 1. Fetch verified fee records from backend
  const { data: feesData, isLoading: feesLoading } = useQuery({
    queryKey: ["college-fees", college.id],
    queryFn: () => fetchFees({ college_id: college.id, limit: 10 }),
    staleTime: 5 * 60 * 1000,
  });

  // 2. Fetch verified cutoff records from backend (fetch full list for the college)
  const { data: cutoffsData, isLoading: cutoffsLoading } = useQuery({
    queryKey: ["college-cutoffs", college.id],
    queryFn: () => fetchCutoffs({ college_id: college.id, limit: 200 }),
    staleTime: 5 * 60 * 1000,
  });

  // 3. Fetch branches catalog for joining
  const { data: branches = CANONICAL_BRANCHES } = useQuery({
    queryKey: ["branches-catalog"],
    queryFn: () => fetchBranches("ENGINEERING"),
    staleTime: 10 * 60 * 1000,
  });

  const branchMap = useMemo(() => {
    const map = new Map<string, { code: string; name: string }>();
    branches.forEach((b) => {
      map.set(b.id, { code: b.code, name: b.name });
    });
    return map;
  }, [branches]);

  const [tableBranchFilter, setTableBranchFilter] = useState<string>("ALL");

  const verifiedFees = feesData?.items ?? [];
  const verifiedCutoffs = cutoffsData?.items ?? [];

  const filteredCutoffs = useMemo(() => {
    if (tableBranchFilter === "ALL") return verifiedCutoffs;
    return verifiedCutoffs.filter((c) => {
      const br = branchMap.get(c.branch_id);
      return br?.code === tableBranchFilter || c.branch_id === tableBranchFilter;
    });
  }, [verifiedCutoffs, tableBranchFilter, branchMap]);

  // Lowest closing rank among published cutoffs for reference
  const lowestCutoff = verifiedCutoffs.length > 0
    ? Math.min(...verifiedCutoffs.map((c) => c.closing_rank))
    : null;

  const isRankWithinBoundary = lowestCutoff !== null ? candidateRank <= lowestCutoff : null;

  return (
    <>
      <header className="border-b border-border bg-background">
        <Section className="py-8">
          <Link
            to="/colleges"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-3" /> College Directory
          </Link>

          <div className="mt-5 flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-4">
              <CollegeLogo initials={college.accent} className="size-16 text-lg" />
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-md border border-primary/20 bg-primary/10 px-2 py-0.5 font-mono text-xs font-semibold text-primary">
                    {college.code}
                  </span>
                  <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                    {college.name}
                  </h1>
                </div>
                <p className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <MapPin className="size-3.5" />
                  <span>{college.location}</span>
                  <span className="text-border">·</span>
                  <span>{college.institution_type}</span>
                </p>
              </div>
            </div>

            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => toast.success(`Saved ${college.code} to your shortlist`)}
              >
                <BookmarkPlus className="size-4" /> Shortlist
              </Button>
              <Button asChild size="sm">
                <Link to="/compare" search={{ colleges: college.id }}>
                  <GitCompareArrows className="size-4" /> Compare
                </Link>
              </Button>
            </div>
          </div>
        </Section>
      </header>

      <Section>
        {/* Metric Cards from verified database records */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Panel className="p-5">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Official Institution Code
            </span>
            <strong className="mt-2 block font-mono text-2xl font-bold text-foreground">
              {college.code}
            </strong>
            <span className="text-[11px] text-muted-foreground">Official COMEDK code</span>
          </Panel>

          <Panel className="p-5">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Official Annual Tuition Fee
            </span>
            <strong className="mt-2 block font-mono text-2xl font-bold text-foreground">
              {feesLoading
                ? "..."
                : verifiedFees.length > 0 && verifiedFees[0].tuition_fee
                ? `₹${Number(verifiedFees[0].tuition_fee).toLocaleString("en-IN")}`
                : "Official Circular"}
            </strong>
            <span className="text-[11px] text-muted-foreground">From published fee circulars</span>
          </Panel>

          <Panel className="p-5">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Verified Cutoff Records
            </span>
            <strong className="mt-2 block font-mono text-2xl font-bold text-foreground">
              {cutoffsLoading ? "..." : verifiedCutoffs.length}
            </strong>
            <span className="text-[11px] text-muted-foreground">Observed allotment points</span>
          </Panel>

          <Panel className="p-5">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Institution Category
            </span>
            <strong className="mt-2 block text-xl font-bold text-foreground">
              {college.institution_type}
            </strong>
            <span className="text-[11px] text-muted-foreground">Karnataka state allotment</span>
          </Panel>
        </div>

        {/* Candidate Rank Positioning vs Official Cutoffs */}
        <div className="mt-10 grid gap-6 lg:grid-cols-[1.2fr_.8fr]">
          {/* Real Cutoff Table */}
          <Panel className="p-6">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
              <div>
                <p className="eyebrow">Verified Allotment Cutoffs</p>
                <h2 className="mt-1 text-lg font-semibold text-foreground">
                  Published Closing Ranks
                </h2>
              </div>
              <div className="flex items-center gap-2">
                <Select value={tableBranchFilter} onValueChange={setTableBranchFilter}>
                  <SelectTrigger className="w-36 h-7 text-[11px]">
                    <SelectValue placeholder="All Branches" />
                  </SelectTrigger>
                  <SelectContent className="max-h-56">
                    <SelectItem value="ALL" className="text-xs">
                      All Branches
                    </SelectItem>
                    {branches.map((b) => (
                      <SelectItem key={b.id} value={b.code} className="text-xs">
                        <span className="font-semibold font-mono">{b.code}:</span> {b.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <SourceBadge meta={{ source: "Official COMEDK", year: 2026, confidence: "High" }} />
              </div>
            </div>

            {cutoffsLoading ? (
              <p className="py-8 text-center text-xs text-muted-foreground">Loading verified cutoff records...</p>
            ) : filteredCutoffs.length === 0 ? (
              <p className="py-8 text-center text-xs text-muted-foreground">
                No published cutoff records found for this selection.
              </p>
            ) : (
              <div className="mt-4 max-h-80 overflow-y-auto overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/60 text-[10px] uppercase text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2">Year</th>
                      <th className="px-3 py-2">Branch</th>
                      <th className="px-3 py-2">Round</th>
                      <th className="px-3 py-2">Category</th>
                      <th className="px-3 py-2 text-right">Closing Rank</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {filteredCutoffs.slice(0, 30).map((c) => {
                      const br = branchMap.get(c.branch_id);
                      const catCode = CANONICAL_CATEGORY_NAMES[c.category_id] || "GM";
                      return (
                        <tr key={c.id}>
                          <td className="px-3 py-2.5 font-medium font-mono text-muted-foreground">{c.academic_year}</td>
                          <td className="px-3 py-2.5 font-medium">
                            <span className="font-mono text-[11px] font-semibold bg-muted px-1.5 py-0.5 rounded border border-border">
                              {br?.code || "ENG"}
                            </span>
                            <span className="ml-1.5 text-muted-foreground text-[11px] truncate max-w-[120px] inline-block align-bottom">
                              {br?.name || "Program"}
                            </span>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="rounded bg-muted/40 px-1.5 py-0.5 font-mono text-[11px]">
                              {CANONICAL_ROUND_NAMES[c.round_id]?.name || "Official Round"}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 font-mono text-xs">{catCode}</td>
                          <td className="px-3 py-2.5 text-right font-mono font-semibold text-foreground">
                            {c.closing_rank.toLocaleString("en-IN")}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {/* Test Candidate Rank Form */}
          <Panel className="flex flex-col justify-between p-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="rounded-md border border-primary/20 bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                  Decision Layer
                </span>
                <span className="text-[11px] text-muted-foreground">Non-speculative</span>
              </div>

              <h2 className="text-lg font-semibold text-foreground">
                Evaluate Your Rank
              </h2>

              <label className="block text-xs text-muted-foreground">
                Enter your COMEDK rank:
                <Input
                  type="number"
                  value={candidateRank}
                  onChange={(e) => setCandidateRank(Number(e.target.value))}
                  className="mt-1 font-mono text-base"
                />
              </label>

              {lowestCutoff !== null && (
                <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground">
                  {isRankWithinBoundary ? (
                    <p className="text-foreground">
                      Your rank (<strong className="font-mono">{candidateRank.toLocaleString("en-IN")}</strong>) is{" "}
                      <strong className="text-positive">numerically within</strong> this college's strictest historical cutoff boundary (
                      <strong className="font-mono">{lowestCutoff.toLocaleString("en-IN")}</strong>).
                    </p>
                  ) : (
                    <p>
                      Your rank (<strong className="font-mono">{candidateRank.toLocaleString("en-IN")}</strong>) is{" "}
                      numerically beyond the strictest historical cutoff (
                      <strong className="font-mono">{lowestCutoff.toLocaleString("en-IN")}</strong>). Check subsequent rounds or allied branches.
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Removed Analyze button */}
          </Panel>
        </div>

        {/* Factual Fee Section from Backend */}
        <div className="mt-10">
          <SectionHeading
            eyebrow="Official Fees"
            title="Published COMEDK Tuition & College Fees"
            description="Fee amounts extracted from published COMEDK seat allocation circulars. Hostel fees vary by institution."
          />

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel className="p-6">
              <p className="eyebrow">Verified Fee Schedule</p>
              {feesLoading ? (
                <p className="mt-4 text-xs text-muted-foreground">Loading fee records...</p>
              ) : verifiedFees.length === 0 ? (
                <p className="mt-4 text-xs text-muted-foreground">
                  Official fee records not cataloged for this institution.
                </p>
              ) : (
                <div className="mt-4 space-y-3">
                  {verifiedFees.slice(0, 3).map((f) => (
                    <div key={f.id} className="flex items-center justify-between border-b border-border pb-2 text-xs">
                      <div>
                        <span className="font-semibold text-foreground">Academic Year {f.academic_year}</span>
                        <p className="text-[11px] text-muted-foreground">Tuition Fee</p>
                      </div>
                      <div className="font-mono text-sm font-semibold text-foreground">
                        ₹{Number(f.tuition_fee || f.total_fee).toLocaleString("en-IN")}
                      </div>
                    </div>
                  ))}
                  <div className="mt-3 flex items-start gap-2 text-[11px] text-muted-foreground">
                    <Info className="size-3.5 shrink-0 text-primary" />
                    <span>Hostel and transport fees are determined independently by college management.</span>
                  </div>
                </div>
              )}
            </Panel>

            <Panel className="p-6">
              <p className="eyebrow">Placements Data Disclosure</p>
              <div className="mt-4 rounded-lg border border-border bg-muted/20 p-4 text-xs leading-relaxed text-muted-foreground">
                <div className="flex items-center gap-2 font-semibold text-foreground">
                  <HelpCircle className="size-4 text-muted-foreground" />
                  <span>Official Policy Notice</span>
                </div>
                <p className="mt-2">
                  COMEDK does not audit, compile, or publish institutional placement statistics (average/highest packages) in counselling notifications.
                  To avoid misleading students with fabricated salary figures, COMEDK Compass does not publish unverified placement claims.
                </p>
                <p className="mt-2">
                  Please consult individual institution NIRF documentation or autonomous audit reports directly.
                </p>
              </div>
            </Panel>
          </div>
        </div>

        {/* Student Reviews Status */}
        <div className="mt-10">
          <SectionHeading
            eyebrow="Community Submissions"
            title="Verified Student Data"
            description="Independent campus reports submitted by enrolled students."
          />
          <Panel className="p-6 text-center text-xs text-muted-foreground">
            <CheckCircle2 className="mx-auto size-6 text-muted-foreground/60" />
            <p className="mt-2 font-medium text-foreground">No student reviews recorded yet</p>
            <p className="mt-1">
              Currently displaying official COMEDK allotment cutoffs and regulatory fee circulars only.
            </p>
          </Panel>
        </div>
      </Section>
    </>
  );
}
