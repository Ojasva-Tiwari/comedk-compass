import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ChevronLeft, ChevronRight, Database, Loader2, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  fetchCutoffs,
  fetchColleges,
  fetchBranches,
  CANONICAL_COLLEGES,
  CANONICAL_BRANCHES,
  CANONICAL_ROUND_NAMES,
  CANONICAL_CATEGORY_NAMES,
} from "@/lib/api-client";
import { PageHeader, Panel, Section, EmptyState } from "@/components/product/page";

export const Route = createFileRoute("/cutoffs")({
  head: () => ({
    meta: [
      { title: "COMEDK Cutoff Explorer — COMEDK Compass" },
      {
        name: "description",
        content:
          "Official round-wise COMEDK engineering cutoffs by college, branch, year and category from verified allotment records.",
      },
      { property: "og:title", content: "COMEDK Cutoff Explorer" },
      {
        property: "og:description",
        content: "Round-by-round cutoff intelligence for Karnataka colleges.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: CutoffsPage,
});

function CutoffsPage() {
  const [academicYear, setAcademicYear] = useState<number>(2026);
  const [category, setCategory] = useState<"GM" | "KKR">("GM");
  const [roundCode, setRoundCode] = useState<string>("ALL");
  const [branchFilter, setBranchFilter] = useState<string>("ALL");
  const [collegeFilter, setCollegeFilter] = useState<string>("ALL");
  const [page, setPage] = useState<number>(0);
  const pageSize = 50;

  // Catalogs for joining
  const { data: colleges = CANONICAL_COLLEGES } = useQuery({
    queryKey: ["colleges-catalog"],
    queryFn: () => fetchColleges(),
    staleTime: 10 * 60 * 1000,
  });

  const { data: branches = CANONICAL_BRANCHES } = useQuery({
    queryKey: ["branches-catalog"],
    queryFn: () => fetchBranches("ENGINEERING"),
    staleTime: 10 * 60 * 1000,
  });

  const collegeMap = useMemo(() => {
    const map = new Map<string, { code: string; name: string; slug?: string }>();
    colleges.forEach((c) => {
      map.set(c.id, { code: c.code, name: c.name, slug: c.code.toLowerCase() });
    });
    return map;
  }, [colleges]);

  const branchMap = useMemo(() => {
    const map = new Map<string, { code: string; name: string }>();
    branches.forEach((b) => {
      map.set(b.id, { code: b.code, name: b.name });
    });
    return map;
  }, [branches]);

  // Round options based on selected year and category
  const roundOptions = useMemo(() => {
    if (category === "GM") {
      if (academicYear === 2026) {
        return [
          { value: "ALL", label: "All General Rounds" },
          { value: "R1", label: "Round 1 (R1)" },
          { value: "R3", label: "Round 3 (R3)" },
          { value: "R4", label: "Round 4 (R4)" },
          { value: "MOCK", label: "Mock Round" },
        ];
      }
      if (academicYear === 2025) {
        return [
          { value: "ALL", label: "All General Rounds" },
          { value: "R4", label: "Round 4 (R4)" },
        ];
      }
      if (academicYear === 2024) {
        return [
          { value: "ALL", label: "All General Rounds" },
          { value: "R1", label: "Round 1 (R1)" },
          { value: "R2_PHASE2", label: "Round 2 Phase 2" },
          { value: "R3", label: "Round 3 (R3)" },
          { value: "MOCK", label: "Mock Round" },
        ];
      }
      return [
        { value: "ALL", label: "All General Rounds" },
        { value: "R1", label: "Round 1 (R1)" },
        { value: "R2_PHASE2", label: "Round 2 Phase 2" },
        { value: "R3", label: "Round 3 (R3)" },
        { value: "CONSOLIDATED_FINAL", label: "Consolidated Final" },
        { value: "MOCK", label: "Mock Round" },
      ];
    } else {
      // KKR category
      if (academicYear === 2026) {
        return [
          { value: "ALL", label: "All KKR Cutoffs" },
          { value: "KKR_SPECIAL", label: "Round 2 KKR Special" },
          { value: "R1", label: "Round 1 (R1)" },
          { value: "R3", label: "Round 3 (R3)" },
          { value: "R4", label: "Round 4 (R4)" },
          { value: "MOCK", label: "Mock Round" },
        ];
      }
      if (academicYear === 2025) {
        return [
          { value: "ALL", label: "All KKR Cutoffs" },
          { value: "R4", label: "Round 4 (R4)" },
        ];
      }
      return [
        { value: "ALL", label: "All KKR Cutoffs" },
        { value: "KKR_SPECIAL", label: "Round 2 KKR Special" },
        { value: "R1", label: "Round 1 (R1)" },
        { value: "R2_PHASE2", label: "Round 2 Phase 2" },
        { value: "R3", label: "Round 3 (R3)" },
        { value: "MOCK", label: "Mock Round" },
      ];
    }
  }, [academicYear, category]);

  // Selected branch UUID if filtering by branch code
  const selectedBranchId = useMemo(() => {
    if (branchFilter === "ALL") return undefined;
    const match = branches.find((b) => b.code === branchFilter);
    return match ? match.id : undefined;
  }, [branchFilter, branches]);

  // Query backend cutoffs
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["cutoffs-data", academicYear, category, roundCode, selectedBranchId, collegeFilter, page],
    queryFn: () =>
      fetchCutoffs({
        academic_year: academicYear,
        category_code: category,
        round_code: roundCode !== "ALL" ? roundCode : undefined,
        branch_id: selectedBranchId,
        college_id: collegeFilter !== "ALL" ? collegeFilter : undefined,
        include_special_rounds: category === "KKR" || roundCode === "KKR_SPECIAL",
        limit: pageSize,
        offset: page * pageSize,
      }),
    staleTime: 5 * 60 * 1000,
  });

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const totalPages = Math.ceil(total / pageSize);

  const handleYearChange = (yearStr: string) => {
    setAcademicYear(Number(yearStr));
    setRoundCode("ALL");
    setPage(0);
  };

  const handleCategoryChange = (cat: "GM" | "KKR") => {
    setCategory(cat);
    setRoundCode("ALL");
    setPage(0);
  };

  return (
    <>
      <PageHeader
        eyebrow="Cutoff explorer"
        title="Official COMEDK allotment cutoffs."
        description="Factual round-wise closing ranks from published COMEDK allotment PDFs across 2023–2026. No synthetic data, no fabricated general Round 2."
      />
      <Section>
        {isError && (
          <Panel className="mb-6 flex items-center justify-between border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive">
            <div className="flex items-center gap-3">
              <AlertCircle className="size-4 shrink-0" />
              <span>Failed to fetch cutoffs from backend. ({error instanceof Error ? error.message : "Error"})</span>
            </div>
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              <RotateCw className="size-3 mr-1" /> Retry
            </Button>
          </Panel>
        )}

        <Panel className="mb-6 flex flex-wrap items-center gap-3 p-4">
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-semibold uppercase text-muted-foreground">Year</span>
            <Select value={String(academicYear)} onValueChange={handleYearChange}>
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="2026">2026</SelectItem>
                <SelectItem value="2025">2025</SelectItem>
                <SelectItem value="2024">2024</SelectItem>
                <SelectItem value="2023">2023</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-semibold uppercase text-muted-foreground">Category</span>
            <div className="flex rounded-md bg-muted p-1">
              {(["GM", "KKR"] as const).map((c) => (
                <button
                  key={c}
                  onClick={() => handleCategoryChange(c)}
                  className={`rounded px-3 py-1.5 text-xs font-semibold transition-colors ${
                    category === c
                      ? "bg-card text-foreground shadow-xs"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {c === "GM" ? "General Merit (GM)" : "Kalyana-Karnataka (KKR)"}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-semibold uppercase text-muted-foreground">Round</span>
            <Select value={roundCode} onValueChange={(r) => { setRoundCode(r); setPage(0); }}>
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {roundOptions.map((opt) => (
                  <SelectItem value={opt.value} key={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-semibold uppercase text-muted-foreground">Branch</span>
            <Select value={branchFilter} onValueChange={(b) => { setBranchFilter(b); setPage(0); }}>
              <SelectTrigger className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All branches</SelectItem>
                <SelectItem value="CS">CS (Computer Science)</SelectItem>
                <SelectItem value="AI">AI (AIML)</SelectItem>
                <SelectItem value="AD">AD (Data Science)</SelectItem>
                <SelectItem value="IS">IS (Information Science)</SelectItem>
                <SelectItem value="EC">EC (Electronics)</SelectItem>
                <SelectItem value="EE">EE (Electrical)</SelectItem>
                <SelectItem value="ME">ME (Mechanical)</SelectItem>
                <SelectItem value="CV">CV (Civil)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-semibold uppercase text-muted-foreground">College</span>
            <Select value={collegeFilter} onValueChange={(c) => { setCollegeFilter(c); setPage(0); }}>
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="max-h-72">
                <SelectItem value="ALL">All colleges</SelectItem>
                {colleges.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.code}: {c.name.split("-")[0]?.trim()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="ml-auto flex items-center gap-2 self-end text-xs text-muted-foreground">
            <Database className="size-3.5" />
            <span>{total.toLocaleString("en-IN")} published records</span>
          </div>
        </Panel>

        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">College</th>
                <th className="px-4 py-3 font-medium">Branch</th>
                <th className="px-4 py-3 font-medium">Round</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium text-right">Closing Rank</th>
                <th className="px-4 py-3 font-medium">Source / Status</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="p-12 text-center text-muted-foreground">
                    <div className="flex items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin text-primary" />
                      <span>Loading published COMEDK {academicYear} cutoffs...</span>
                    </div>
                  </td>
                </tr>
              ) : isError ? (
                <tr>
                  <td colSpan={6} className="p-12 text-center text-destructive">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <AlertCircle className="size-6 text-destructive" />
                      <p className="font-semibold">Unable to load cutoff data from server</p>
                      <p className="text-xs text-muted-foreground max-w-md">
                        {error instanceof Error ? error.message : "The backend service is temporarily unavailable."}
                      </p>
                      <Button variant="outline" size="sm" onClick={() => refetch()} className="mt-2 text-foreground">
                        <RotateCw className="mr-1.5 size-3.5" /> Try Again
                      </Button>
                    </div>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-12 text-center">
                    <p className="text-sm font-medium">No published cutoffs found for this combination.</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Try selecting another round or switching category.
                    </p>
                  </td>
                </tr>
              ) : (
                items.map((row) => {
                  const college = collegeMap.get(row.college_id);
                  const branch = branchMap.get(row.branch_id);
                  const roundMeta = CANONICAL_ROUND_NAMES[row.round_id];
                  const catCode = CANONICAL_CATEGORY_NAMES[row.category_id] || category;

                  return (
                    <tr key={row.id} className="border-t border-border hover:bg-muted/30">
                      <td className="px-4 py-3.5">
                        <Link
                          to="/colleges/$slug"
                          params={{ slug: college?.slug || college?.code || row.college_id }}
                          className="font-semibold hover:text-primary"
                        >
                          {college?.code ? `${college.code}: ` : ""}{college?.name ? college.name.split("-")[0]?.trim() : row.college_id.slice(0, 8)}
                        </Link>
                        <p className="text-xs text-muted-foreground truncate max-w-sm">
                          {college?.name || "Official Karnataka Institution"}
                        </p>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-xs font-semibold bg-muted px-1.5 py-0.5 rounded">
                          {branch?.code || "ENG"}
                        </span>
                        <span className="ml-2 text-xs text-muted-foreground">
                          {branch?.name || "Engineering Program"}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="rounded-md border border-border bg-muted/40 px-2 py-0.5 font-mono text-xs">
                          {roundMeta?.name || row.row_identifier?.split("_")[4] || "Official Round"}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                          {catCode}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-right font-mono font-semibold text-foreground">
                        {row.closing_rank.toLocaleString("en-IN")}
                      </td>
                      <td className="px-4 py-3.5 text-xs text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <Database className="size-3 text-positive" />
                          <span>Official COMEDK · {row.academic_year}</span>
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
            <div>
              Showing {page * pageSize + 1}–{Math.min(total, (page + 1) * pageSize)} of {total.toLocaleString("en-IN")} records
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                <ChevronLeft className="size-3 mr-1" /> Previous
              </Button>
              <span className="font-mono">
                Page {page + 1} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
              >
                Next <ChevronRight className="size-3 ml-1" />
              </Button>
            </div>
          </div>
        )}
      </Section>
    </>
  );
}
