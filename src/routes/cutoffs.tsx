import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  Building2,
  ChevronLeft,
  ChevronRight,
  Database,
  GitBranch,
  History,
  Info,
  Loader2,
  RotateCw,
  Search,
  TrendingUp,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  fetchCutoffs,
  fetchColleges,
  fetchBranches,
  CANONICAL_COLLEGES,
  CANONICAL_BRANCHES,
  CANONICAL_ROUND_NAMES,
  CANONICAL_CATEGORY_NAMES,
} from "@/lib/api-client";
import { PageHeader, Panel, Section } from "@/components/product/page";

interface CutoffsSearchParams {
  year?: number | string;
  category?: "GM" | "KKR";
  round?: string;
  branchId?: string;
  collegeId?: string;
}

export const Route = createFileRoute("/cutoffs")({
  validateSearch: (search: Record<string, unknown>): CutoffsSearchParams => {
    return {
      year:
        typeof search.year === "number"
          ? search.year
          : typeof search.year === "string"
          ? parseInt(search.year, 10) || undefined
          : undefined,
      category:
        search.category === "KKR" ? "KKR" : search.category === "GM" ? "GM" : undefined,
      round: typeof search.round === "string" ? search.round : undefined,
      branchId: typeof search.branchId === "string" ? search.branchId : undefined,
      collegeId: typeof search.collegeId === "string" ? search.collegeId : undefined,
    };
  },
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
        content: "Round-by-round cutoff intelligence and historical progressions for Karnataka colleges.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: CutoffsPage,
});

function CutoffsPage() {
  const searchParams = Route.useSearch();

  const [academicYear, setAcademicYear] = useState<number | "ALL">(
    searchParams.year && [2023, 2024, 2025, 2026].includes(Number(searchParams.year))
      ? Number(searchParams.year)
      : 2026
  );
  const [category, setCategory] = useState<"GM" | "KKR">(
    searchParams.category === "KKR" ? "KKR" : "GM"
  );
  const [roundCode, setRoundCode] = useState<string>(
    searchParams.round || "ALL"
  );
  const [branchFilter, setBranchFilter] = useState<string>(
    searchParams.branchId || "ALL"
  );
  const [collegeFilter, setCollegeFilter] = useState<string>(
    searchParams.collegeId || "ALL"
  );
  const [collegeSearchQuery, setCollegeSearchQuery] = useState<string>("");
  const [page, setPage] = useState<number>(0);
  const pageSize = 50;

  // Catalogs for joining & filters
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

  // College lookup map
  const collegeMap = useMemo(() => {
    const map = new Map<string, { code: string; name: string; shortName?: string; slug?: string }>();
    colleges.forEach((c) => {
      const cleanShortName = (c.shortName || c.name.split("-")[0]?.trim() || "").replace(/^[E]\d+\s*[-:]\s*/i, "").trim();
      map.set(c.id, {
        code: c.code,
        name: c.name,
        shortName: cleanShortName || c.name,
        slug: c.code.toLowerCase(),
      });
    });
    return map;
  }, [colleges]);

  // Branch lookup map
  const branchMap = useMemo(() => {
    const map = new Map<string, { code: string; name: string }>();
    branches.forEach((b) => {
      map.set(b.id, { code: b.code, name: b.name });
    });
    return map;
  }, [branches]);

  // Resolve selected college object
  const selectedCollege = useMemo(() => {
    if (collegeFilter === "ALL") return null;
    return (
      colleges.find(
        (c) => c.id === collegeFilter || c.code.toLowerCase() === collegeFilter.toLowerCase()
      ) || null
    );
  }, [collegeFilter, colleges]);

  const selectedCollegeId = selectedCollege ? selectedCollege.id : undefined;

  // Resolve selected branch object
  const selectedBranch = useMemo(() => {
    if (branchFilter === "ALL") return null;
    return (
      branches.find(
        (b) => b.id === branchFilter || b.code.toUpperCase() === branchFilter.toUpperCase()
      ) || null
    );
  }, [branchFilter, branches]);

  const selectedBranchId = selectedBranch ? selectedBranch.id : undefined;

  // Filtered colleges list for select dropdown
  const filteredColleges = useMemo(() => {
    if (!collegeSearchQuery.trim()) return colleges;
    const q = collegeSearchQuery.toLowerCase().trim();
    return colleges.filter(
      (c) =>
        c.code.toLowerCase().includes(q) ||
        c.name.toLowerCase().includes(q) ||
        (c.shortName && c.shortName.toLowerCase().includes(q))
    );
  }, [colleges, collegeSearchQuery]);

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
      if (academicYear === 2023) {
        return [
          { value: "ALL", label: "All General Rounds" },
          { value: "R1", label: "Round 1 (R1)" },
          { value: "R2_PHASE2", label: "Round 2 Phase 2" },
          { value: "R3", label: "Round 3 (R3)" },
          { value: "CONSOLIDATED_FINAL", label: "Consolidated Final" },
          { value: "MOCK", label: "Mock Round" },
        ];
      }
      return [
        { value: "ALL", label: "All Published Rounds" },
        { value: "R1", label: "Round 1 (R1)" },
        { value: "R3", label: "Round 3 (R3)" },
        { value: "R4", label: "Round 4 (R4)" },
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

  // Query 1: Backend Cutoffs Global Table (preserves all records, no synthetic grouping)
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: [
      "cutoffs-data",
      academicYear,
      category,
      roundCode,
      selectedBranchId,
      selectedCollegeId,
      page,
    ],
    queryFn: () =>
      fetchCutoffs({
        academic_year: academicYear === "ALL" ? undefined : academicYear,
        category_code: category,
        round_code: roundCode !== "ALL" ? roundCode : undefined,
        branch_id: selectedBranchId,
        college_id: selectedCollegeId,
        include_special_rounds: category === "KKR" || roundCode === "KKR_SPECIAL",
        limit: pageSize,
        offset: page * pageSize,
      }),
    staleTime: 5 * 60 * 1000,
  });

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const totalPages = Math.ceil(total / pageSize);

  // Query 2: Specific Choice Historical Progression (active when both College + Branch are selected)
  const isChoiceSelected = Boolean(selectedCollegeId && selectedBranchId);

  const {
    data: choiceProgressionData,
    isLoading: isProgressionLoading,
  } = useQuery({
    queryKey: [
      "choice-progression-cutoffs",
      selectedCollegeId,
      selectedBranchId,
      category,
    ],
    queryFn: () =>
      fetchCutoffs({
        college_id: selectedCollegeId,
        branch_id: selectedBranchId,
        category_code: category,
        include_special_rounds: true,
        limit: 100,
      }),
    enabled: isChoiceSelected,
    staleTime: 5 * 60 * 1000,
  });

  const progressionItems = choiceProgressionData?.items ?? [];

  // Group choice progression records by academic year
  const progressionByYear = useMemo(() => {
    const years = [2026, 2025, 2024, 2023];
    const result: Record<number, Record<string, number>> = {};

    years.forEach((yr) => {
      result[yr] = {};
    });

    progressionItems.forEach((rec) => {
      const yr = rec.academic_year;
      if (!result[yr]) result[yr] = {};
      const rCode =
        CANONICAL_ROUND_NAMES[rec.round_id]?.code ||
        rec.row_identifier?.split("_")[4] ||
        rec.round_id;
      result[yr][rCode] = rec.closing_rank;
    });

    return result;
  }, [progressionItems]);

  const handleYearChange = (yearStr: string) => {
    if (yearStr === "ALL") {
      setAcademicYear("ALL");
    } else {
      setAcademicYear(Number(yearStr));
    }
    setRoundCode("ALL");
    setPage(0);
  };

  const handleCategoryChange = (cat: "GM" | "KKR") => {
    setCategory(cat);
    setRoundCode("ALL");
    setPage(0);
  };

  const handleResetFilters = () => {
    setAcademicYear(2026);
    setCategory("GM");
    setRoundCode("ALL");
    setBranchFilter("ALL");
    setCollegeFilter("ALL");
    setCollegeSearchQuery("");
    setPage(0);
  };

  const hasActiveFilters =
    academicYear !== 2026 ||
    category !== "GM" ||
    roundCode !== "ALL" ||
    branchFilter !== "ALL" ||
    collegeFilter !== "ALL";

  return (
    <>
      <PageHeader
        eyebrow="Cutoff Explorer"
        title="Official COMEDK Allotment Cutoffs"
        description="Factual round-wise closing ranks from published COMEDK allotment archives across 2023–2026. Every record is verified with college and branch identifiers."
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

        {/* Global Filter Bar */}
        <Panel className="mb-6 p-4 sm:p-5 space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            {/* 1. Academic Year */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Year
              </span>
              <Select value={String(academicYear)} onValueChange={handleYearChange}>
                <SelectTrigger className="w-28 text-xs font-mono">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="2026">2026</SelectItem>
                  <SelectItem value="2025">2025</SelectItem>
                  <SelectItem value="2024">2024</SelectItem>
                  <SelectItem value="2023">2023</SelectItem>
                  <SelectItem value="ALL">All Years</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* 2. Category Quota */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Category
              </span>
              <div className="flex rounded-md bg-muted p-1 text-xs">
                {(["GM", "KKR"] as const).map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => handleCategoryChange(c)}
                    className={`rounded px-3 py-1.5 font-semibold transition-colors ${
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

            {/* 3. Counselling Round */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Round
              </span>
              <Select
                value={roundCode}
                onValueChange={(r) => {
                  setRoundCode(r);
                  setPage(0);
                }}
              >
                <SelectTrigger className="w-48 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {roundOptions.map((opt) => (
                    <SelectItem value={opt.value} key={opt.value} className="text-xs">
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 4. College Filter */}
            <div className="flex flex-col gap-1 flex-1 min-w-[240px]">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                <Building2 className="size-3" /> College
              </span>
              <Select
                value={selectedCollege ? selectedCollege.id : "ALL"}
                onValueChange={(c) => {
                  setCollegeFilter(c);
                  setPage(0);
                }}
              >
                <SelectTrigger className="w-full text-xs text-left truncate">
                  <SelectValue
                    placeholder="All Colleges (221 Institutions)"
                  />
                </SelectTrigger>
                <SelectContent className="max-h-72">
                  <div className="p-2 border-b border-border">
                    <div className="flex items-center gap-1.5 rounded-md border border-input bg-muted/30 px-2 py-1">
                      <Search className="size-3.5 text-muted-foreground shrink-0" />
                      <Input
                        type="text"
                        placeholder="Search college code or name..."
                        value={collegeSearchQuery}
                        onChange={(e) => setCollegeSearchQuery(e.target.value)}
                        className="h-6 border-0 bg-transparent p-0 text-xs shadow-none focus-visible:ring-0"
                      />
                    </div>
                  </div>
                  <SelectItem value="ALL" className="text-xs font-semibold">
                    All Colleges (221 Institutions)
                  </SelectItem>
                  {filteredColleges.map((c) => (
                    <SelectItem key={c.id} value={c.id} className="text-xs">
                      <span className="font-semibold font-mono">{c.code}:</span>{" "}
                      {(c.shortName || c.name.split("-")[0]?.trim() || "").replace(/^[E]\d+\s*[-:]\s*/i, "").trim()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 5. Branch Filter */}
            <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                <GitBranch className="size-3" /> Branch
              </span>
              <Select
                value={selectedBranch ? selectedBranch.id : "ALL"}
                onValueChange={(b) => {
                  setBranchFilter(b);
                  setPage(0);
                }}
              >
                <SelectTrigger className="w-full text-xs text-left truncate">
                  <SelectValue
                    placeholder="All Branches"
                  />
                </SelectTrigger>
                <SelectContent className="max-h-72">
                  <SelectItem value="ALL" className="text-xs font-semibold">
                    All Branches
                  </SelectItem>
                  {branches.map((b) => (
                    <SelectItem key={b.id} value={b.id} className="text-xs">
                      <span className="font-semibold font-mono">{b.code}:</span> {b.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Clear Filters Button */}
            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleResetFilters}
                className="text-xs h-9 gap-1 text-muted-foreground hover:text-foreground"
              >
                <X className="size-3.5" /> Clear
              </Button>
            )}

            {/* Record Count Badge */}
            <div className="ml-auto flex items-center gap-2 self-center text-xs text-muted-foreground font-mono">
              <Database className="size-3.5 text-primary" />
              <span>{total.toLocaleString("en-IN")} published records</span>
            </div>
          </div>
        </Panel>

        {/* Historical R1 / R3 / R4 Progression Panel (Shown when College + Branch are selected) */}
        {isChoiceSelected && selectedCollege && selectedBranch && (
          <Panel className="mb-6 p-5 sm:p-6 border-primary/20 bg-primary/5 space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-primary uppercase">
                    Historical Cutoff Progression
                  </span>
                  <span className="rounded-md border border-border bg-muted px-2 py-0.5 font-mono text-[10px] font-medium text-muted-foreground">
                    {category === "GM" ? "General Merit (GM)" : "Kalyana-Karnataka (KKR)"}
                  </span>
                </div>
                <h3 className="mt-2 text-base sm:text-lg font-bold text-foreground">
                  {selectedCollege.code}: {selectedCollege.name}
                </h3>
                <p className="text-xs sm:text-sm text-muted-foreground">
                  Branch: <strong className="text-foreground font-mono">{selectedBranch.code}</strong> — {selectedBranch.name}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Button asChild size="sm" className="gap-1.5 text-xs">
                  <Link
                    to="/predictor"
                    search={{
                      collegeId: selectedCollege.id,
                      branchId: selectedBranch.id,
                      year: academicYear === "ALL" ? 2026 : academicYear,
                      category,
                    }}
                  >
                    <History className="size-3.5" />
                    Analyze in Cutoff Tool →
                  </Link>
                </Button>
              </div>
            </div>

            {isProgressionLoading ? (
              <div className="py-6 flex items-center justify-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="size-4 animate-spin text-primary" />
                <span>Loading round progression for {selectedCollege.code} - {selectedBranch.code}...</span>
              </div>
            ) : progressionItems.length === 0 ? (
              <div className="py-6 text-center text-xs text-muted-foreground">
                <p className="font-semibold text-foreground">No historical allotment records published for this choice.</p>
                <p className="mt-1">
                  This branch may not have had seats offered or allotted in the selected counselling cycles.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* 2026 Canonical Progression (R1 -> R3 -> R4) */}
                <div>
                  <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5 mb-2.5">
                    <TrendingUp className="size-3.5 text-primary" />
                    2026 Counselling Round-Wise Movement ({category})
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {/* Round 1 */}
                    <div className="rounded-lg border border-border bg-card p-3.5">
                      <span className="text-[10px] font-semibold text-muted-foreground uppercase">
                        Round 1
                      </span>
                      <div className="mt-1.5 text-lg font-bold font-mono text-foreground">
                        {progressionByYear[2026]?.["R1"]
                          ? progressionByYear[2026]["R1"].toLocaleString("en-IN")
                          : "Not Available"}
                      </div>
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        Initial allotment baseline
                      </p>
                    </div>

                    {/* Round 3 */}
                    <div className="rounded-lg border border-border bg-card p-3.5">
                      <span className="text-[10px] font-semibold text-muted-foreground uppercase">
                        Round 3
                      </span>
                      <div className="mt-1.5 text-lg font-bold font-mono text-foreground">
                        {progressionByYear[2026]?.["R3"]
                          ? progressionByYear[2026]["R3"].toLocaleString("en-IN")
                          : "Not Available"}
                      </div>
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        {progressionByYear[2026]?.["R1"] && progressionByYear[2026]?.["R3"] ? (
                          <span className="text-positive font-semibold font-mono">
                            +{Math.abs(progressionByYear[2026]["R3"] - progressionByYear[2026]["R1"]).toLocaleString("en-IN")} ranks from R1
                          </span>
                        ) : (
                          "Movement from R1"
                        )}
                      </p>
                    </div>

                    {/* Round 4 */}
                    <div className="rounded-lg border border-border bg-card p-3.5">
                      <span className="text-[10px] font-semibold text-muted-foreground uppercase">
                        Round 4 (Final)
                      </span>
                      <div className="mt-1.5 text-lg font-bold font-mono text-foreground">
                        {progressionByYear[2026]?.["R4"]
                          ? progressionByYear[2026]["R4"].toLocaleString("en-IN")
                          : "Not Available"}
                      </div>
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        {progressionByYear[2026]?.["R3"] && progressionByYear[2026]?.["R4"] ? (
                          <span className="text-positive font-semibold font-mono">
                            +{Math.abs(progressionByYear[2026]["R4"] - progressionByYear[2026]["R3"]).toLocaleString("en-IN")} ranks from R3
                          </span>
                        ) : (
                          "Final allotment boundary"
                        )}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Multi-Year Progression History Table */}
                <div className="overflow-x-auto rounded-lg border border-border bg-card">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-muted/60 text-[10px] uppercase font-semibold text-muted-foreground">
                      <tr>
                        <th className="px-3.5 py-2.5">Academic Year</th>
                        <th className="px-3.5 py-2.5">Round 1</th>
                        <th className="px-3.5 py-2.5">
                          {category === "KKR" ? "KKR Special" : "Round 2 Phase 2"}
                        </th>
                        <th className="px-3.5 py-2.5">Round 3</th>
                        <th className="px-3.5 py-2.5 text-right">Round 4 / Final</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {[2026, 2025, 2024, 2023].map((yr) => {
                        const yrData = progressionByYear[yr] || {};
                        const r1Val = yrData["R1"];
                        const r2Val = category === "KKR" ? yrData["KKR_SPECIAL"] : yrData["R2_PHASE2"];
                        const r3Val = yrData["R3"];
                        const r4Val = yrData["R4"] || yrData["CONSOLIDATED_FINAL"];

                        const hasAny = r1Val || r2Val || r3Val || r4Val;
                        if (!hasAny) return null;

                        return (
                          <tr key={yr} className="hover:bg-muted/30">
                            <td className="px-3.5 py-2 font-semibold font-mono">{yr}</td>
                            <td className="px-3.5 py-2 font-mono">
                              {r1Val ? r1Val.toLocaleString("en-IN") : <span className="text-muted-foreground/60">—</span>}
                            </td>
                            <td className="px-3.5 py-2 font-mono">
                              {r2Val ? r2Val.toLocaleString("en-IN") : <span className="text-muted-foreground/60">—</span>}
                            </td>
                            <td className="px-3.5 py-2 font-mono">
                              {r3Val ? r3Val.toLocaleString("en-IN") : <span className="text-muted-foreground/60">—</span>}
                            </td>
                            <td className="px-3.5 py-2 font-mono font-bold text-right text-foreground">
                              {r4Val ? r4Val.toLocaleString("en-IN") : <span className="text-muted-foreground/60">—</span>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </Panel>
        )}

        {/* Global Cutoffs Table: Preserves all legitimate records with College and Branch columns */}
        <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-xs">
          <table className="w-full min-w-[840px] text-sm">
            <thead className="bg-muted/60 text-left text-xs font-semibold text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium w-20">Year</th>
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
                  <td colSpan={7} className="p-12 text-center text-muted-foreground">
                    <div className="flex items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin text-primary" />
                      <span>Loading verified COMEDK cutoffs...</span>
                    </div>
                  </td>
                </tr>
              ) : isError ? (
                <tr>
                  <td colSpan={7} className="p-12 text-center text-destructive">
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
                  <td colSpan={7} className="p-12 text-center">
                    <p className="text-sm font-medium">No published cutoffs found for this combination.</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Try selecting another round, college, or category quota.
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
                    <tr key={row.id} className="border-t border-border hover:bg-muted/30 transition-colors">
                      {/* 1. Year Column */}
                      <td className="px-4 py-3.5 font-mono font-medium text-xs text-muted-foreground">
                        {row.academic_year}
                      </td>

                      {/* 2. College Column */}
                      <td className="px-4 py-3.5">
                        <Link
                          to="/colleges/$slug"
                          params={{ slug: college?.slug || college?.code || row.college_id }}
                          className="font-semibold text-foreground hover:text-primary transition-colors flex items-center gap-1.5"
                        >
                          <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-muted border border-border">
                            {college?.code || "INST"}
                          </span>
                          <span className="truncate max-w-xs">
                            {college?.shortName || (college?.name ? college.name.split("-")[0]?.trim() : row.college_id.slice(0, 8))}
                          </span>
                        </Link>
                        <p className="text-[11px] text-muted-foreground truncate max-w-sm mt-0.5">
                          {college?.name || "Official Karnataka Institution"}
                        </p>
                      </td>

                      {/* 3. Branch Column */}
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-xs font-semibold bg-muted px-1.5 py-0.5 rounded border border-border">
                            {branch?.code || "ENG"}
                          </span>
                          <span className="text-xs text-foreground font-medium truncate max-w-[200px]">
                            {branch?.name || "Engineering Program"}
                          </span>
                        </div>
                      </td>

                      {/* 4. Round Column */}
                      <td className="px-4 py-3.5">
                        <span className="rounded-md border border-border bg-muted/40 px-2 py-0.5 font-mono text-xs text-foreground">
                          {roundMeta?.name || row.row_identifier?.split("_")[4] || "Official Round"}
                        </span>
                      </td>

                      {/* 5. Category Column */}
                      <td className="px-4 py-3.5">
                        <span className="rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary font-mono">
                          {catCode}
                        </span>
                      </td>

                      {/* 6. Closing Rank Column */}
                      <td className="px-4 py-3.5 text-right font-mono font-bold text-foreground text-sm">
                        {row.closing_rank.toLocaleString("en-IN")}
                      </td>

                      {/* 7. Source / Status Column */}
                      <td className="px-4 py-3.5 text-xs text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <Database className="size-3 text-positive shrink-0" />
                          <span>Official COMEDK</span>
                          {row.page_number && (
                            <span className="font-mono text-[10px] text-muted-foreground">
                              · p.{row.page_number}
                            </span>
                          )}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
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
