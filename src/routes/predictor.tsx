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
  Sparkles,
  Users,
  AlertCircle,
  Info,
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
import { PredictionDecisionCard } from "@/components/product/PredictionDecisionCard";
import {
  CANONICAL_COLLEGES,
  CANONICAL_BRANCHES,
  fetchColleges,
  fetchBranches,
  evaluateCandidateDecision,
  type CandidateDecisionRequest,
} from "@/lib/api-client";

interface PredictorSearchParams {
  rank?: number;
  collegeId?: string;
  branchId?: string;
  round?: string;
  category?: string;
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
    };
  },
  head: () => ({
    meta: [
      { title: "COMEDK Candidate Rank Decision Analysis — COMEDK Compass" },
      {
        name: "description",
        content:
          "Evidence-based candidate rank decision layer for COMEDK. Evaluate your rank against historical closing-rank prediction intervals without arbitrary probability percentages.",
      },
      { property: "og:title", content: "COMEDK Candidate Rank Decision Analysis" },
      {
        property: "og:description",
        content:
          "Descriptive position analysis relative to historical COMEDK cutoffs. No Safe/Target/Reach, no admission promises.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: PredictorPage,
});

function PredictorPage() {
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
  const [academicYear, setAcademicYear] = useState<number>(2026);
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
    searchParams.round && ["R1", "R3", "R4"].includes(searchParams.round)
      ? searchParams.round
      : "R4"
  );
  const [candidateRankInput, setCandidateRankInput] = useState<string>(
    searchParams.rank && searchParams.rank > 0
      ? searchParams.rank.toLocaleString("en-IN")
      : "18,432"
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

  // Rank input parsing & validation: positive integer, > 0
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
      rankError = "Please enter a valid positive integer rank (e.g. 18432).";
    }
  }

  // Canonical Round Options:
  // General counselling: Round 1 (R1), Round 3 (R3), Round 4 (R4).
  // Standard R2 is never available for general counselling.
  // KKR_SPECIAL is never a general counselling round.
  // TERMINAL is not exposed in main selector; R4 is used canonically.
  const roundOptions = [
    { value: "R1", label: "Round 1" },
    { value: "R3", label: "Round 3" },
    { value: "R4", label: "Round 4" },
  ];

  // TanStack Query for Candidate Rank Decision Layer:
  // Cache key includes all 7 dimensions for strict data isolation.
  const queryPayload: CandidateDecisionRequest = {
    candidate_rank: parsedRank || 1,
    college_id: collegeId,
    branch_id: branchId,
    academic_year: academicYear,
    round,
    category,
    program_type: programType,
  };

  const {
    data: decision,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: [
      "candidate-decision",
      parsedRank,
      academicYear,
      collegeId,
      branchId,
      category,
      round,
      programType,
    ],
    queryFn: () => evaluateCandidateDecision(queryPayload),
    enabled: Boolean(parsedRank && parsedRank > 0 && programType === "ENGINEERING"),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <>
      <PageHeader
        eyebrow="Decision Layer"
        title="Candidate Rank Analysis"
        description="Evaluate your COMEDK rank relative to historical closing-rank prediction intervals. Understand where your rank sits against past cutoffs without misleading admission guarantees."
      />

      <Section className="max-w-6xl">
        <div className="grid gap-8 lg:grid-cols-[400px_1fr]">
          {/* Controls Column */}
          <div className="space-y-6">
            <Panel className="p-5 sm:p-6 space-y-5">
              <div>
                <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Scale className="size-4 text-primary" />
                  Candidate & Choice Parameters
                </h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Enter your rank and target choice dimensions to analyze historical interval containment.
                </p>
              </div>

              {/* 1. Candidate COMEDK Rank Input (Primary Input) */}
              <div className="space-y-1.5 border-b border-border pb-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor={rankInputId} className="text-xs font-semibold flex items-center gap-1.5">
                    <Users className="size-3.5 text-primary" />
                    Your COMEDK Rank
                  </Label>
                  <span className="text-[10px] text-muted-foreground font-mono">Required</span>
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
                    // Format rank with commas when valid
                    if (isPositiveInteger && parsedRank) {
                      setCandidateRankInput(parsedRank.toLocaleString("en-IN"));
                    }
                  }}
                  placeholder="e.g. 18432"
                  className={`font-mono text-base ${rankError ? "border-destructive focus-visible:ring-destructive" : ""}`}
                />
                {rankError ? (
                  <p className="text-[11px] text-destructive flex items-center gap-1 mt-1">
                    <AlertCircle className="size-3 shrink-0" />
                    {rankError}
                  </p>
                ) : (
                  <p className="text-[11px] text-muted-foreground">
                    Enter your official COMEDK rank.
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

              {/* 3. Academic Year */}
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
                    <SelectItem value="2026">2026 (Active Counselling Year)</SelectItem>
                    <SelectItem value="2027">2027 (Forward Planning)</SelectItem>
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
                    onClick={() => setCategory("GM")}
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
                    onClick={() => setCategory("KKR")}
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

              {/* 5. Counselling Round Selection (Canonical R1, R3, R4) */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label htmlFor={roundSelectId} className="text-xs">Counselling Round</Label>
                  <span className="text-[11px] text-muted-foreground font-mono">Progression: R1→R3→R4</span>
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
                  General engineering counselling progression skips standard R2.
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

              {/* Analyze Action Button */}
              <div className="pt-2">
                <Button
                  type="button"
                  onClick={() => refetch()}
                  disabled={!isPositiveInteger || isFetching || programType === "ARCHITECTURE"}
                  className="w-full gap-2 text-xs"
                >
                  <RotateCw className={`size-3.5 ${isFetching ? "animate-spin" : ""}`} />
                  {isFetching ? "Analyzing historical COMEDK data..." : "Analyze Candidate Rank"}
                </Button>
              </div>
            </Panel>

            {/* Informational Guidance Box */}
            <div className="rounded-lg border border-border bg-muted/20 p-4 text-xs text-muted-foreground space-y-2">
              <div className="flex items-center gap-1.5 font-semibold text-foreground">
                <HelpCircle className="size-3.5 text-primary" />
                Understanding the Decision Layer
              </div>
              <p>
                <strong>Descriptive Positioning:</strong> The decision layer evaluates where your rank
                sits relative to the model's calibrated uncertainty interval [L, U] and closing rank estimate.
              </p>
              <p>
                <strong>Inverse Rank Semantics:</strong> A lower numerical rank represents a stronger
                rank in COMEDK counselling. Ranks below the lower bound are numerically stronger than
                the historical cutoff floor.
              </p>
            </div>
          </div>

          {/* Results Column */}
          <div className="space-y-6">
            {programType === "ARCHITECTURE" ? (
              <Panel className="p-6 sm:p-8 border-border bg-card">
                <div className="flex items-start gap-3">
                  <div className="grid size-9 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
                    <Info className="size-5 text-primary" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-foreground">
                      Architecture Decision Analysis Unavailable
                    </h3>
                    <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                      Candidate decision analysis is currently unavailable for Architecture because the
                      available historical evidence is insufficient for a reliable decision-layer
                      assessment.
                    </p>
                    <div className="mt-4 rounded-md border border-border bg-muted/40 p-3.5 text-xs text-muted-foreground">
                      <p className="font-semibold text-foreground">
                        Why this happens:
                      </p>
                      <p className="mt-1">
                        Architecture cutoffs are governed by NATA scores and have sparse multi-year
                        allotment progressions. In accordance with Compass design principles, the
                        system fails closed rather than fabricating ungrounded estimates.
                      </p>
                    </div>
                  </div>
                </div>
              </Panel>
            ) : !isPositiveInteger ? (
              <Panel className="p-8 text-center border-dashed">
                <Users className="mx-auto size-10 text-muted-foreground/60" />
                <h3 className="mt-3 text-sm font-semibold text-foreground">
                  Enter your COMEDK Rank to run analysis
                </h3>
                <p className="mt-1 text-xs text-muted-foreground max-w-md mx-auto">
                  Provide a valid positive rank in the input field above, select your counselling round
                  and college, then click Analyze.
                </p>
              </Panel>
            ) : (
              <PredictionDecisionCard
                result={decision ?? null}
                isLoading={isLoading || isFetching}
                error={error as Error | null}
                onRetry={() => refetch()}
              />
            )}

            {/* Factual Context Card */}
            <Panel className="p-5 sm:p-6 border-border bg-card">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    Evidence-Based Guidance
                  </p>
                  <h3 className="mt-1 text-sm font-semibold text-foreground">
                    Decision Layer Framework
                  </h3>
                </div>
                <Sparkles className="size-4 text-primary" />
              </div>

              <div className="mt-4 grid gap-4 sm:grid-cols-2 text-xs">
                <div className="rounded-md border border-border bg-muted/30 p-3.5 space-y-1.5">
                  <span className="font-semibold text-foreground flex items-center gap-1">
                    <Layers className="size-3 text-muted-foreground" />
                    Objective Interval Boundaries
                  </span>
                  <p className="text-muted-foreground leading-relaxed">
                    Evaluates candidate position relative to the lower bound, estimate, and upper bound.
                    No subjective ratings or probabilities.
                  </p>
                </div>

                <div className="rounded-md border border-border bg-muted/30 p-3.5 space-y-1.5">
                  <span className="font-semibold text-foreground flex items-center gap-1">
                    <History className="size-3 text-primary" />
                    Empirical Grounding
                  </span>
                  <p className="text-muted-foreground leading-relaxed">
                    Estimates are anchored in official published COMEDK cutoffs with walk-forward
                    historical validation.
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
