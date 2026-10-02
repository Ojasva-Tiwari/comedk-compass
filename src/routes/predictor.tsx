import { createFileRoute } from "@tanstack/react-router";
import { useState, useId, useMemo, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  GitBranch,
  HelpCircle,
  History,
  Layers,
  RotateCw,
  Scale,
  Users,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageHeader, Panel, Section } from "@/components/product/page";
import { HistoricalCutoffCard } from "@/components/product/HistoricalCutoffCard";
import {
  CANONICAL_COLLEGES,
  CANONICAL_BRANCHES,
  fetchColleges,
  fetchBranches,
  fetchCutoffs,
} from "@/lib/api-client";

interface PredictorSearchParams {
  rank?: number;
  collegeId?: string;
  branchId?: string;
  round?: string;
  category?: string;
  year?: number;
}

export const Route = createFileRoute("/predictor")({
  validateSearch: (search: Record<string, unknown>): PredictorSearchParams => {
    return {
      rank:
        typeof search.rank === "number"
          ? search.rank
          : typeof search.rank === "string"
          ? parseInt(search.rank, 10) || undefined
          : undefined,
      collegeId: typeof search.collegeId === "string" ? search.collegeId : undefined,
      branchId: typeof search.branchId === "string" ? search.branchId : undefined,
      round: typeof search.round === "string" ? search.round : undefined,
      category: typeof search.category === "string" ? search.category : undefined,
      year:
        typeof search.year === "number"
          ? search.year
          : typeof search.year === "string"
          ? parseInt(search.year, 10) || undefined
          : undefined,
    };
  },
  head: () => ({
    meta: [
      { title: "COMEDK Historical Cutoff Analysis — COMEDK Compass" },
      {
        name: "description",
        content:
          "Analyze verified historical COMEDK closing ranks. Inspect actual cutoff progressions across rounds and academic years without predictive estimates or probabilities.",
      },
      { property: "og:title", content: "COMEDK Historical Cutoff Analysis" },
      {
        property: "og:description",
        content:
          "Factual historical closing ranks and round-wise cutoff movement from official COMEDK allotment data. Zero predictions, zero artificial probability.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: HistoricalCutoffPage,
});

function HistoricalCutoffPage() {
  const searchParams = Route.useSearch();

  const rankInputId = useId();
  const collegeSelectId = useId();
  const branchSelectId = useId();
  const yearSelectId = useId();
  const roundSelectId = useId();
  const categorySelectId = useId();

  const resolvedCollegeId = useMemo(() => {
    if (!searchParams.collegeId) return undefined;
    const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(searchParams.collegeId);
    if (isUuid) return searchParams.collegeId;
    const canonicalMatch = CANONICAL_COLLEGES.find(
      (c) => c.id === searchParams.collegeId || c.code.toLowerCase() === searchParams.collegeId?.toLowerCase()
    );
    if (canonicalMatch) return canonicalMatch.id;
    return searchParams.collegeId;
  }, [searchParams.collegeId]);

  // Control state
  const [programType, setProgramType] = useState<"ENGINEERING" | "ARCHITECTURE">("ENGINEERING");
  const [academicYear, setAcademicYear] = useState<number>(
    searchParams.year && [2023, 2024, 2025, 2026].includes(searchParams.year)
      ? searchParams.year
      : 2026
  );
  const [collegeId, setCollegeId] = useState<string>(
    resolvedCollegeId || "39dd12af-12d8-445b-8a5d-66d22792a361" // RVCE default
  );
  const [branchId, setBranchId] = useState<string>(
    searchParams.branchId || "f764a302-c117-41bb-bbd3-e2b998012107" // CS default
  );
  const [category, setCategory] = useState<"GM" | "KKR">(
    searchParams.category === "KKR" ? "KKR" : "GM"
  );
  const [round, setRound] = useState<string>(
    searchParams.round && ["R1", "KKR_SPECIAL", "R3", "R4"].includes(searchParams.round)
      ? searchParams.round
      : "R4"
  );
  const [candidateRankInput, setCandidateRankInput] = useState<string>(
    searchParams.rank && searchParams.rank > 0
      ? searchParams.rank.toLocaleString("en-IN")
      : "23,510"
  );

  useEffect(() => {
    if (resolvedCollegeId) {
      setCollegeId(resolvedCollegeId);
    }
  }, [resolvedCollegeId]);

  useEffect(() => {
    if (searchParams.rank && searchParams.rank > 0) {
      setCandidateRankInput(searchParams.rank.toLocaleString("en-IN"));
    }
  }, [searchParams.rank]);

  // Dynamic College & Branch Catalogs
  const { data: colleges = CANONICAL_COLLEGES } = useQuery({
    queryKey: ["colleges-catalog"],
    queryFn: () => fetchColleges(),
    staleTime: 10 * 60 * 1000,
  });

  const { data: branches = CANONICAL_BRANCHES } = useQuery({
    queryKey: ["branches-catalog", programType],
    queryFn: () => fetchBranches(programType),
    staleTime: 10 * 60 * 1000,
  });

  // Filter available branches by program type
  const availableBranches = useMemo(() => {
    const list = branches.filter((b) => b.program_type === programType);
    return list.length > 0
      ? list
      : CANONICAL_BRANCHES.filter((b) => b.program_type === programType);
  }, [branches, programType]);

  // Handle program type switch
  const handleProgramTypeChange = (type: "ENGINEERING" | "ARCHITECTURE") => {
    setProgramType(type);
    if (type === "ARCHITECTURE") {
      const archBranch = CANONICAL_BRANCHES.find((b) => b.program_type === "ARCHITECTURE");
      if (archBranch) setBranchId(archBranch.id);
      const archCollege = colleges.find((c) => c.code === "E176") || CANONICAL_COLLEGES.find((c) => c.code === "E176");
      if (archCollege) setCollegeId(archCollege.id);
    } else {
      const engBranch = CANONICAL_BRANCHES.find((b) => b.program_type === "ENGINEERING");
      if (engBranch) setBranchId(engBranch.id);
      const engCollege = colleges.find((c) => c.code === "E095") || CANONICAL_COLLEGES.find((c) => c.code === "E095");
      if (engCollege) setCollegeId(engCollege.id);
    }
  };

  // Handle category change: reset round if KKR_SPECIAL was selected and category is switched to GM
  const handleCategoryChange = (newCategory: "GM" | "KKR") => {
    setCategory(newCategory);
    if (newCategory === "GM" && round === "KKR_SPECIAL") {
      setRound("R4");
    }
  };

  // Rank input parsing & validation
  const cleanedRankInput = candidateRankInput.trim().replace(/,/g, "");
  const isPositiveInteger = /^\d+$/.test(cleanedRankInput) && parseInt(cleanedRankInput, 10) > 0;
  const parsedRank = isPositiveInteger ? parseInt(cleanedRankInput, 10) : null;

  const selectedCollege = useMemo(() => {
    return colleges.find((c) => c.id === collegeId) || CANONICAL_COLLEGES.find((c) => c.id === collegeId);
  }, [colleges, collegeId]);

  const selectedBranch = useMemo(() => {
    return availableBranches.find((b) => b.id === branchId) || CANONICAL_BRANCHES.find((b) => b.id === branchId);
  }, [availableBranches, branchId]);

  let rankError: string | null = null;
  if (candidateRankInput.trim().length > 0 && !isPositiveInteger) {
    if (cleanedRankInput === "0") {
      rankError = "COMEDK rank cannot be zero. Please enter a valid positive rank.";
    } else if (cleanedRankInput.startsWith("-")) {
      rankError = "COMEDK rank cannot be negative. Please enter a positive integer.";
    } else {
      rankError = "Please enter a valid positive integer rank (e.g. 23510).";
    }
  }

  // Canonical Round Options:
  // General counselling: Round 1 (R1), Round 3 (R3), Round 4 (R4).
  // Standard R2 is never available for general counselling.
  // KKR_SPECIAL is available only when KKR is selected.
  const roundOptions = useMemo(() => {
    if (category === "KKR") {
      return [
        { value: "R1", label: "Round 1" },
        { value: "KKR_SPECIAL", label: "Round 2 KKR Special Allotment" },
        { value: "R3", label: "Round 3" },
        { value: "R4", label: "Round 4" },
      ];
    }
    return [
      { value: "R1", label: "Round 1" },
      { value: "R3", label: "Round 3" },
      { value: "R4", label: "Round 4" },
    ];
  }, [category]);

  // Query 1: Exact target cutoff record for selected dimensions
  const {
    data: targetCutoffData,
    isLoading: isLoadingTarget,
    error: targetError,
    refetch: refetchTarget,
    isFetching: isFetchingTarget,
  } = useQuery({
    queryKey: [
      "historical-cutoff-target",
      collegeId,
      branchId,
      academicYear,
      round,
      category,
      programType,
    ],
    queryFn: () =>
      fetchCutoffs({
        college_id: collegeId,
        branch_id: branchId,
        academic_year: academicYear,
        round_code: round,
        category_code: category,
        program_type: programType,
        include_special_rounds: true,
        limit: 10,
      }),
    enabled: Boolean(collegeId && branchId),
    staleTime: 5 * 60 * 1000,
  });

  // Query 2: All rounds for current academic year to construct round-wise progression
  const {
    data: yearCutoffsData,
    isLoading: isLoadingYear,
    refetch: refetchYear,
  } = useQuery({
    queryKey: [
      "historical-cutoff-year",
      collegeId,
      branchId,
      academicYear,
      category,
      programType,
    ],
    queryFn: () =>
      fetchCutoffs({
        college_id: collegeId,
        branch_id: branchId,
        academic_year: academicYear,
        category_code: category,
        program_type: programType,
        include_special_rounds: true,
        limit: 50,
      }),
    enabled: Boolean(collegeId && branchId),
    staleTime: 5 * 60 * 1000,
  });

  // Query 3: Multi-year historical records across all years
  const {
    data: multiYearCutoffsData,
    isLoading: isLoadingMultiYear,
    refetch: refetchMultiYear,
  } = useQuery({
    queryKey: [
      "historical-cutoff-multiyear",
      collegeId,
      branchId,
      category,
      programType,
    ],
    queryFn: () =>
      fetchCutoffs({
        college_id: collegeId,
        branch_id: branchId,
        category_code: category,
        program_type: programType,
        include_special_rounds: true,
        limit: 200,
      }),
    enabled: Boolean(collegeId && branchId),
    staleTime: 5 * 60 * 1000,
  });

  const handleRefetchAll = () => {
    refetchTarget();
    refetchYear();
    refetchMultiYear();
  };

  const isAnyLoading = isLoadingTarget || isLoadingYear || isLoadingMultiYear;
  const isAnyFetching = isFetchingTarget;

  const targetCutoff = targetCutoffData?.items?.[0] ?? null;
  const yearCutoffs = yearCutoffsData?.items ?? [];
  const multiYearCutoffs = multiYearCutoffsData?.items ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Cutoff Analysis"
        title="Historical Cutoff Analysis"
        description="Review verified published closing ranks from official COMEDK allotment documents. Compare your rank against actual round progressions and multi-year data without model estimates or admission probabilities."
      />

      <Section className="max-w-6xl">
        <div className="grid gap-8 lg:grid-cols-[400px_1fr]">
          {/* Controls Column */}
          <div className="space-y-6">
            <Panel className="p-5 sm:p-6 space-y-5">
              <div>
                <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Scale className="size-4 text-primary" />
                  Historical Cutoff Parameters
                </h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Select choice dimensions and counselling details to inspect published COMEDK closing ranks.
                </p>
              </div>

              {/* 1. Candidate COMEDK Rank Input (Optional for comparison) */}
              <div className="space-y-1.5 border-b border-border pb-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor={rankInputId} className="text-xs font-semibold flex items-center gap-1.5">
                    <Users className="size-3.5 text-primary" />
                    Your COMEDK Rank
                  </Label>
                  <span className="text-[10px] text-muted-foreground font-mono">For comparison</span>
                </div>
                <Input
                  id={rankInputId}
                  type="text"
                  inputMode="numeric"
                  value={candidateRankInput}
                  onChange={(e) => {
                    const raw = e.target.value;
                    setCandidateRankInput(raw);
                  }}
                  onBlur={() => {
                    if (isPositiveInteger && parsedRank) {
                      setCandidateRankInput(parsedRank.toLocaleString("en-IN"));
                    }
                  }}
                  placeholder="e.g. 23510"
                  className={`font-mono text-base ${rankError ? "border-destructive focus-visible:ring-destructive" : ""}`}
                />
                {rankError ? (
                  <p className="text-[11px] text-destructive flex items-center gap-1 mt-1">
                    <AlertCircle className="size-3 shrink-0" />
                    {rankError}
                  </p>
                ) : (
                  <p className="text-[11px] text-muted-foreground">
                    Enter your rank to see factual numerical containment against the closing rank.
                  </p>
                )}
              </div>

              {/* 2. Program Type Toggle */}
              <div className="space-y-2">
                <Label className="text-xs">Program Type</Label>
                <div className="grid grid-cols-2 rounded-md bg-muted p-1 text-xs">
                  <button
                    type="button"
                    onClick={() => handleProgramTypeChange("ENGINEERING")}
                    className={`rounded py-1.5 font-medium transition-colors ${
                      programType === "ENGINEERING"
                        ? "bg-card text-foreground shadow-xs"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Engineering (B.E)
                  </button>
                  <button
                    type="button"
                    onClick={() => handleProgramTypeChange("ARCHITECTURE")}
                    className={`rounded py-1.5 font-medium transition-colors ${
                      programType === "ARCHITECTURE"
                        ? "bg-card text-foreground shadow-xs"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Architecture (B.Arch)
                  </button>
                </div>
              </div>

              {/* 3. Academic Year Selection */}
              <div className="space-y-1.5">
                <Label htmlFor={yearSelectId} className="text-xs">Academic Year</Label>
                <Select
                  value={String(academicYear)}
                  onValueChange={(val) => setAcademicYear(Number(val))}
                >
                  <SelectTrigger id={yearSelectId} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="2026">2026 (Latest Published Year)</SelectItem>
                    <SelectItem value="2025">2025 Historical Records</SelectItem>
                    <SelectItem value="2024">2024 Historical Records</SelectItem>
                    <SelectItem value="2023">2023 Historical Records</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* 4. Category Quota (Strict Isolation) */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label htmlFor={categorySelectId} className="text-xs">Category Quota</Label>
                  <span className="text-[11px] text-muted-foreground">Strict Isolation</span>
                </div>
                <div className="grid grid-cols-2 rounded-md bg-muted p-1 text-xs">
                  <button
                    type="button"
                    onClick={() => handleCategoryChange("GM")}
                    className={`rounded py-1.5 font-medium transition-colors ${
                      category === "GM"
                        ? "bg-card text-foreground shadow-xs"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    GM (General Merit)
                  </button>
                  <button
                    type="button"
                    onClick={() => handleCategoryChange("KKR")}
                    className={`rounded py-1.5 font-medium transition-colors ${
                      category === "KKR"
                        ? "bg-card text-foreground shadow-xs"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    KKR (Kalyana Karnataka)
                  </button>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  GM and KKR quotas query strictly independent historical distribution records.
                </p>
              </div>

              {/* 5. Counselling Round Selection */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label htmlFor={roundSelectId} className="text-xs">Counselling Round</Label>
                  <span className="text-[11px] text-muted-foreground font-mono">
                    {category === "KKR" ? "R1 → KKR Sp. → R3 → R4" : "Progression: R1 → R3 → R4"}
                  </span>
                </div>
                <Select value={round} onValueChange={setRound}>
                  <SelectTrigger id={roundSelectId} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {roundOptions.map((r) => (
                      <SelectItem key={r.value} value={r.value}>
                        {r.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-[11px] text-muted-foreground">
                  General engineering counselling progression skips standard Round 2.
                </p>
              </div>

              {/* 6. College Selection */}
              <div className="space-y-1.5">
                <Label htmlFor={collegeSelectId} className="text-xs flex items-center gap-1.5">
                  <Building2 className="size-3.5 text-muted-foreground" />
                  College
                </Label>
                <Select value={collegeId} onValueChange={setCollegeId}>
                  <SelectTrigger id={collegeSelectId} className="w-full truncate text-left">
                    <SelectValue placeholder={selectedCollege ? `${selectedCollege.code}: ${selectedCollege.shortName}` : "Select college"} />
                  </SelectTrigger>
                  <SelectContent className="max-h-72">
                    {colleges.map((c) => (
                      <SelectItem key={c.id} value={c.id} className="text-xs">
                        <span className="font-semibold">{c.code}:</span> {c.shortName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* 7. Branch Selection */}
              <div className="space-y-1.5">
                <Label htmlFor={branchSelectId} className="text-xs flex items-center gap-1.5">
                  <GitBranch className="size-3.5 text-muted-foreground" />
                  Branch
                </Label>
                <Select value={branchId} onValueChange={setBranchId}>
                  <SelectTrigger id={branchSelectId} className="w-full text-left truncate">
                    <SelectValue placeholder={selectedBranch ? `${selectedBranch.code}: ${selectedBranch.name}` : "Select branch"} />
                  </SelectTrigger>
                  <SelectContent className="max-h-72">
                    {availableBranches.map((b) => (
                      <SelectItem key={b.id} value={b.id} className="text-xs">
                        <span className="font-semibold font-mono">{b.code}:</span> {b.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Action Button */}
              <div className="pt-2">
                <Button
                  type="button"
                  onClick={handleRefetchAll}
                  disabled={isAnyFetching}
                  className="w-full gap-2 text-xs"
                >
                  <RotateCw className={`size-3.5 ${isAnyFetching ? "animate-spin" : ""}`} />
                  {isAnyFetching ? "Retrieving official COMEDK cutoffs..." : "Analyze Historical Cutoffs"}
                </Button>
              </div>
            </Panel>

            {/* Informational Guidance Box */}
            <div className="rounded-lg border border-border bg-muted/20 p-4 text-xs text-muted-foreground space-y-2">
              <div className="flex items-center gap-1.5 font-semibold text-foreground">
                <HelpCircle className="size-3.5 text-primary" />
                Historical Cutoff Grounding
              </div>
              <p>
                <strong>Verified Published Ranks:</strong> Every displayed cutoff is an exact record
                extracted from official COMEDK seat allotment notifications. We never predict outcomes,
                fabricate artificial uncertainty intervals, or generate probabilities.
              </p>
              <p>
                <strong>Inverse Rank Semantics:</strong> In COMEDK counselling, a lower numerical rank is
                stronger. If your rank is lower than or equal to the closing rank, your rank was numerically
                within the historical cutoff.
              </p>
            </div>
          </div>

          {/* Results Column */}
          <div className="space-y-6">
            <HistoricalCutoffCard
              targetCutoff={targetCutoff}
              yearCutoffs={yearCutoffs}
              multiYearCutoffs={multiYearCutoffs}
              candidateRank={parsedRank}
              academicYear={academicYear}
              roundCode={round}
              category={category}
              collegeName={selectedCollege?.name || selectedCollege?.shortName}
              collegeCode={selectedCollege?.code}
              branchName={selectedBranch?.name}
              branchCode={selectedBranch?.code}
              programType={programType}
              isLoading={isAnyLoading || isAnyFetching}
              error={targetError as Error | null}
              onRetry={handleRefetchAll}
            />

            {/* Factual Context Card */}
            <Panel className="p-5 sm:p-6 border-border bg-card">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    Data Integrity Standard
                  </p>
                  <h3 className="mt-1 text-sm font-semibold text-foreground">
                    Historical Cutoff Principles
                  </h3>
                </div>
                <History className="size-4 text-primary" />
              </div>

              <div className="mt-4 grid gap-4 sm:grid-cols-2 text-xs">
                <div className="rounded-md border border-border bg-muted/30 p-3.5 space-y-1.5">
                  <span className="font-semibold text-foreground flex items-center gap-1">
                    <Layers className="size-3 text-muted-foreground" />
                    Zero Synthetic Estimates
                  </span>
                  <p className="text-muted-foreground leading-relaxed">
                    We show only actual closing ranks from published COMEDK rounds. No Safe/Target/Reach,
                    no probabilities, and no model approximations.
                  </p>
                </div>

                <div className="rounded-md border border-border bg-muted/30 p-3.5 space-y-1.5">
                  <span className="font-semibold text-foreground flex items-center gap-1">
                    <Scale className="size-3 text-primary" />
                    Source Provenance & Audit Trail
                  </span>
                  <p className="text-muted-foreground leading-relaxed">
                    Every cutoff record is traceable to official COMEDK PDFs with page numbers, document
                    notifications, and immutable source versions.
                  </p>
                </div>
              </div>
            </Panel>
          </div>
        </div>
      </Section>
    </>
  );
}
