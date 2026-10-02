"use client";

import { useState } from "react";
import {
  AlertCircle,
  Building2,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Database,
  FileText,
  GitBranch,
  HelpCircle,
  History,
  Info,
  Layers,
  RotateCw,
  Scale,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/product/page";
import { cn } from "@/lib/utils";
import {
  type CutoffRecordItem,
  CANONICAL_ROUND_NAMES,
  CANONICAL_CATEGORY_NAMES,
} from "@/lib/api-client";

interface HistoricalCutoffCardProps {
  targetCutoff: CutoffRecordItem | null;
  yearCutoffs: CutoffRecordItem[];
  multiYearCutoffs: CutoffRecordItem[];
  candidateRank: number | null;
  academicYear: number;
  roundCode: string;
  category: "GM" | "KKR";
  collegeName?: string;
  collegeCode?: string;
  branchName?: string;
  branchCode?: string;
  programType: "ENGINEERING" | "ARCHITECTURE";
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  className?: string;
}

export function HistoricalCutoffCard({
  targetCutoff,
  yearCutoffs,
  multiYearCutoffs,
  candidateRank,
  academicYear,
  roundCode,
  category,
  collegeName,
  collegeCode,
  branchName,
  branchCode,
  programType,
  isLoading = false,
  error = null,
  onRetry,
  className,
}: HistoricalCutoffCardProps) {
  const [showProvenance, setShowProvenance] = useState(false);
  const [showProgressionDetails, setShowProgressionDetails] = useState(true);

  // 1. Loading State
  if (isLoading) {
    return (
      <Panel className={cn("p-6 sm:p-8 animate-pulse", className)}>
        <div className="flex items-center gap-3">
          <div className="size-9 rounded-md bg-muted" />
          <div className="space-y-2">
            <div className="h-4 w-48 rounded bg-muted" />
            <div className="h-3 w-64 rounded bg-muted/60" />
          </div>
        </div>
        <div className="mt-8 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="h-24 rounded bg-muted/70" />
            <div className="h-24 rounded bg-muted/70" />
            <div className="h-24 rounded bg-muted/70" />
          </div>
          <div className="h-28 w-full rounded bg-muted/50" />
          <div className="h-32 w-full rounded bg-muted/30" />
        </div>
        <div className="mt-6 flex items-center gap-2 text-xs text-muted-foreground">
          <RotateCw className="size-4 animate-spin text-primary" />
          <span>Retrieving verified official COMEDK cutoff records...</span>
        </div>
      </Panel>
    );
  }

  // 2. Error State
  if (error) {
    return (
      <Panel className={cn("border-destructive/30 bg-destructive/5 p-6 sm:p-8", className)}>
        <div className="flex items-start gap-3">
          <ShieldAlert className="size-5 shrink-0 text-destructive mt-0.5" />
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-destructive">
              Unable to load historical cutoff data
            </h3>
            <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
              {error.message ||
                "A network or processing issue prevented retrieving cutoff records from the database. Please verify your selected parameters."}
            </p>
            {onRetry && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRetry}
                className="mt-4 gap-1.5 text-xs"
              >
                <RotateCw className="size-3.5" />
                Retry query
              </Button>
            )}
          </div>
        </div>
      </Panel>
    );
  }

  // Helper for round label
  const getRoundLabel = (code: string) => {
    switch (code) {
      case "R1":
        return "Round 1";
      case "R3":
        return "Round 3";
      case "R4":
        return "Round 4";
      case "MOCK":
        return "Mock Allotment";
      case "KKR_SPECIAL":
        return "Round 2 KKR Special Allotment";
      case "R2_PHASE2":
        return "Round 2 Phase 2";
      case "CONSOLIDATED_FINAL":
        return "Consolidated Cutoff After All Rounds";
      default:
        return code;
    }
  };

  const selectedRoundLabel = getRoundLabel(roundCode);

  // 3. No Data Available for this Specific Selection
  if (!targetCutoff) {
    return (
      <Panel className={cn("p-6 sm:p-8 border-border bg-card", className)}>
        <div className="flex items-start gap-3">
          <div className="grid size-9 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
            <Info className="size-5 text-muted-foreground" />
          </div>
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-border bg-muted px-2.5 py-0.5 font-mono text-[10px] font-semibold text-muted-foreground uppercase">
                Historical Data Notice
              </span>
              <span className="text-xs text-muted-foreground font-mono">
                {academicYear} · {selectedRoundLabel} · {category}
              </span>
            </div>

            <h3 className="mt-3 text-lg font-semibold tracking-tight text-foreground">
              Historical cutoff data is not available for this selection.
            </h3>

            <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
              No official COMEDK allotment record was published for{" "}
              <strong>{collegeName || collegeCode || "this college"}</strong> ·{" "}
              <strong>{branchName || branchCode || "this branch"}</strong> in{" "}
              <strong>{academicYear} {selectedRoundLabel} ({category})</strong>.
            </p>

            <div className="mt-4 rounded-md border border-border bg-muted/40 p-3.5 text-xs text-muted-foreground space-y-2">
              <p className="font-semibold text-foreground">
                Why this happens:
              </p>
              <ul className="space-y-1 list-disc list-inside">
                <li>This choice may not have had seats offered or allotted in {selectedRoundLabel}.</li>
                <li>In COMEDK engineering counselling, General Merit has no standard Round 2 allotments (progression is R1 → R3 → R4).</li>
                <li>In accordance with Compass design principles, we show only verified published data and never fabricate estimated ranks or synthetic cutoffs.</li>
              </ul>
            </div>

            {candidateRank && candidateRank > 0 && (
              <div className="mt-4 flex flex-wrap gap-3 text-xs text-muted-foreground font-mono border-t border-border pt-3">
                <span>Your Rank: <strong>{candidateRank.toLocaleString("en-IN")}</strong></span>
                <span>•</span>
                <span>Year: <strong>{academicYear}</strong></span>
                <span>•</span>
                <span>Round: <strong>{selectedRoundLabel}</strong></span>
                <span>•</span>
                <span>Quota: <strong>{category}</strong></span>
              </div>
            )}
          </div>
        </div>
      </Panel>
    );
  }

  // 4. Data Available: Calculations & Metrics
  const closingRank = targetCutoff.closing_rank;
  const hasCandidateRank = candidateRank !== null && candidateRank > 0;
  const difference = hasCandidateRank ? Math.abs(candidateRank - closingRank) : null;
  const isWithinClosingRank = hasCandidateRank ? candidateRank <= closingRank : null;

  // Number line visualization bounds
  const maxRankForScale = hasCandidateRank
    ? Math.max(closingRank, candidateRank) * 1.15
    : closingRank * 1.25;

  const closingRankPercent = Math.max(4, Math.min(96, Math.round((closingRank / maxRankForScale) * 100)));
  const candidateRankPercent = hasCandidateRank
    ? Math.max(4, Math.min(96, Math.round((candidateRank / maxRankForScale) * 100)))
    : null;

  const accessibleText = hasCandidateRank
    ? `Official ${academicYear} ${selectedRoundLabel} closing rank for ${category} quota is ${closingRank.toLocaleString(
        "en-IN"
      )}. Your rank is ${candidateRank.toLocaleString("en-IN")}, which is ${
        isWithinClosingRank
          ? `numerically within the closing rank by ${difference?.toLocaleString("en-IN")} ranks.`
          : `numerically beyond the closing rank by ${difference?.toLocaleString("en-IN")} ranks.`
      }`
    : `Official ${academicYear} ${selectedRoundLabel} closing rank for ${category} quota is ${closingRank.toLocaleString(
        "en-IN"
      )}.`;

  // Filter and sort progression for the current academic year
  // General counselling sequence: R1, R3, R4 (or KKR_SPECIAL for KKR)
  const progressionOrder = ["MOCK", "R1", "KKR_SPECIAL", "R2_PHASE2", "R3", "R4", "CONSOLIDATED_FINAL"];
  const sortedYearCutoffs = [...yearCutoffs].sort((a, b) => {
    const codeA = CANONICAL_ROUND_NAMES[a.round_id]?.code || "";
    const codeB = CANONICAL_ROUND_NAMES[b.round_id]?.code || "";
    const idxA = progressionOrder.indexOf(codeA);
    const idxB = progressionOrder.indexOf(codeB);
    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    return a.closing_rank - b.closing_rank;
  });

  // Multi-year progression: aggregate highest round / terminal round for each distinct year
  const multiYearByYear = new Map<number, CutoffRecordItem[]>();
  multiYearCutoffs.forEach((item) => {
    const list = multiYearByYear.get(item.academic_year) || [];
    list.push(item);
    multiYearByYear.set(item.academic_year, list);
  });

  const availableYears = Array.from(multiYearByYear.keys()).sort((a, b) => b - a);

  return (
    <Panel className={cn("p-6 sm:p-8 border-border bg-card", className)}>
      {/* 1. Header Badges */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md border border-primary/20 bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">
            Official Historical Cutoff
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            {academicYear} {selectedRoundLabel} · {category}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
          <span className="inline-flex items-center gap-1 rounded bg-muted px-2 py-0.5 text-[11px]">
            <CheckCircle2 className="size-3 text-emerald-600 dark:text-emerald-400" />
            Verified Allotment Record
          </span>
        </div>
      </div>

      {/* 2. Main Metric Cards (Section 3) */}
      <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Metric 1: Actual Closing Rank */}
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 sm:p-5">
          <p className="font-mono text-[10px] uppercase tracking-wider text-primary font-semibold">
            ACTUAL CLOSING RANK
          </p>
          <p className="mt-1 font-mono text-3xl sm:text-4xl font-bold text-foreground tracking-tight">
            {closingRank.toLocaleString("en-IN")}
          </p>
          <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
            <span>{academicYear} {selectedRoundLabel} · {category}</span>
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground/80 font-mono">
            Source: Official COMEDK cutoff data
          </p>
        </div>

        {/* Metric 2: Your COMEDK Rank */}
        <div className="rounded-lg border border-border bg-muted/20 p-4 sm:p-5">
          <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            YOUR COMEDK RANK
          </p>
          <p className="mt-1 font-mono text-3xl sm:text-4xl font-bold text-foreground tracking-tight">
            {hasCandidateRank ? candidateRank?.toLocaleString("en-IN") : "—"}
          </p>
          <p className="mt-2 text-[11px] text-muted-foreground">
            {hasCandidateRank ? "Official candidate rank" : "Enter rank to compare"}
          </p>
          <p className="mt-1 text-[10px] text-muted-foreground/80 font-mono">
            Candidate merit position
          </p>
        </div>

        {/* Metric 3: Difference from Closing Rank */}
        <div
          className={cn(
            "rounded-lg border p-4 sm:p-5",
            hasCandidateRank
              ? isWithinClosingRank
                ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-950 dark:text-emerald-100"
                : "border-amber-500/30 bg-amber-500/5 text-amber-950 dark:text-amber-100"
              : "border-border bg-muted/20"
          )}
        >
          <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            DIFFERENCE FROM CLOSING RANK
          </p>
          <p className="mt-1 font-mono text-3xl sm:text-4xl font-bold tracking-tight">
            {hasCandidateRank && difference !== null
              ? difference.toLocaleString("en-IN")
              : "—"}
          </p>
          <p className="mt-2 text-[11px]">
            {hasCandidateRank
              ? isWithinClosingRank
                ? "Ranks within cutoff boundary"
                : "Ranks beyond cutoff boundary"
              : "Numerical comparison"}
          </p>
          <p className="mt-1 text-[10px] text-muted-foreground font-mono">
            {hasCandidateRank
              ? isWithinClosingRank
                ? "Rank ≤ Closing Rank"
                : "Rank > Closing Rank"
              : "Absolute difference"}
          </p>
        </div>
      </div>

      {/* 3. Numerical Comparison Statement (Section 6) */}
      {hasCandidateRank && (
        <div
          className={cn(
            "mt-6 rounded-md border p-4 text-xs leading-relaxed",
            isWithinClosingRank
              ? "border-emerald-500/30 bg-emerald-500/10 text-foreground"
              : "border-border bg-muted/40 text-foreground"
          )}
        >
          <div className="flex items-start gap-2.5">
            {isWithinClosingRank ? (
              <CheckCircle2 className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />
            ) : (
              <Info className="size-4 shrink-0 text-muted-foreground mt-0.5" />
            )}
            <div className="space-y-1">
              <p className="font-semibold text-sm">
                {isWithinClosingRank ? (
                  <span>
                    Your rank ({candidateRank.toLocaleString("en-IN")}) was{" "}
                    <strong>numerically within</strong> the {academicYear} {selectedRoundLabel}{" "}
                    closing rank ({closingRank.toLocaleString("en-IN")}).
                  </span>
                ) : (
                  <span>
                    Your rank ({candidateRank.toLocaleString("en-IN")}) was{" "}
                    <strong>numerically beyond</strong> the {academicYear} {selectedRoundLabel}{" "}
                    closing rank ({closingRank.toLocaleString("en-IN")}) by{" "}
                    <strong>{difference?.toLocaleString("en-IN")} ranks</strong>.
                  </span>
                )}
              </p>
              <p className="text-muted-foreground">
                {isWithinClosingRank
                  ? `In ${academicYear} COMEDK counselling, candidates with rank up to ${closingRank.toLocaleString(
                      "en-IN"
                    )} were admitted to this college/branch in ${selectedRoundLabel} under the ${category} quota.`
                  : `In ${academicYear} COMEDK counselling, allotments for this college/branch in ${selectedRoundLabel} (${category}) closed at rank ${closingRank.toLocaleString(
                      "en-IN"
                    )}.`}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 4. Neutral Numerical Number-Line Visual (Section 6) */}
      <div
        className="mt-6 rounded-lg border border-border bg-muted/20 p-4 sm:p-5"
        role="img"
        aria-label={accessibleText}
      >
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="font-semibold text-foreground flex items-center gap-1.5">
            <Scale className="size-3.5 text-primary" />
            Historical Numerical Comparison
          </span>
          <span className="font-mono text-[11px]">Rank 1 (Best) → Higher Number (Weaker)</span>
        </div>

        {/* Visual Line Bar */}
        <div className="relative mt-9 mb-10 px-2 sm:px-4">
          {/* Main Track */}
          <div className="h-2 w-full rounded-full bg-border relative">
            {/* Cutoff Allotment Zone (1 to closingRank) */}
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-primary/20"
              style={{ width: `${closingRankPercent}%` }}
            />
          </div>

          {/* Actual Closing Rank Marker */}
          <div
            className="absolute -top-3.5 -translate-x-1/2 flex flex-col items-center z-10"
            style={{ left: `${closingRankPercent}%` }}
          >
            <div className="size-4 rounded-full border-2 border-background bg-primary shadow-sm flex items-center justify-center">
              <span className="size-1.5 rounded-full bg-background" />
            </div>
            <span className="mt-1 font-mono text-[11px] font-bold text-primary bg-card/90 px-1.5 py-0.5 rounded border border-border shadow-xs whitespace-nowrap">
              CUTOFF: {closingRank.toLocaleString("en-IN")}
            </span>
            <span className="text-[10px] text-muted-foreground whitespace-nowrap">
              {academicYear} {selectedRoundLabel}
            </span>
          </div>

          {/* Candidate Rank Marker (if provided) */}
          {hasCandidateRank && candidateRankPercent !== null && (
            <div
              className="absolute -top-3.5 -translate-x-1/2 flex flex-col items-center z-20"
              style={{ left: `${candidateRankPercent}%` }}
            >
              <div className="size-4 rounded-full border-2 border-background bg-foreground shadow-sm flex items-center justify-center">
                <span className="size-1.5 rounded-full bg-background" />
              </div>
              <span className="mt-8 font-mono text-[11px] font-extrabold text-foreground bg-card/90 px-1.5 py-0.5 rounded border border-border shadow-xs whitespace-nowrap">
                YOUR RANK: {candidateRank.toLocaleString("en-IN")}
              </span>
            </div>
          )}
        </div>

        <p className="mt-8 text-[11px] text-muted-foreground leading-relaxed text-center sm:text-left">
          Note: This diagram illustrates historical numerical containment. A lower rank represents a
          numerically stronger merit position. No admission guarantees or subjective probabilities are
          implied.
        </p>
      </div>

      {/* 5. Historical Round Progression (Section 4) */}
      <div className="mt-6 rounded-lg border border-border bg-card p-4 sm:p-5">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <History className="size-4 text-primary" />
              {academicYear} Counselling Round Progression
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Round-by-round historical cutoff progression for {category} quota.
            </p>
          </div>
          <span className="text-[10px] font-mono rounded bg-muted px-2 py-0.5 text-muted-foreground">
            R1 → R3 → R4
          </span>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-border text-[11px] font-mono uppercase text-muted-foreground">
                <th className="py-2 pr-4 font-semibold">Counselling Round</th>
                <th className="py-2 px-4 font-semibold text-right">Actual Closing Rank</th>
                <th className="py-2 px-4 font-semibold text-right">Inter-Round Movement</th>
                <th className="py-2 pl-4 font-semibold text-right">Comparison to Your Rank</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sortedYearCutoffs.length > 0 ? (
                sortedYearCutoffs.map((item, idx) => {
                  const meta = CANONICAL_ROUND_NAMES[item.round_id];
                  const code = meta?.code || "";
                  const label = meta?.name || getRoundLabel(code);
                  const isCurrent = code === roundCode || item.round_id === targetCutoff.round_id;

                  // Inter-round delta from previous round
                  let deltaText = "—";
                  if (idx > 0) {
                    const prevRank = sortedYearCutoffs[idx - 1].closing_rank;
                    const delta = item.closing_rank - prevRank;
                    if (delta > 0) {
                      deltaText = `+${delta.toLocaleString("en-IN")} ranks expansion`;
                    } else if (delta < 0) {
                      deltaText = `${delta.toLocaleString("en-IN")} ranks contraction`;
                    } else {
                      deltaText = "Unchanged";
                    }
                  }

                  // Candidate comparison
                  let candidateComp = "—";
                  if (hasCandidateRank) {
                    const diff = Math.abs(candidateRank - item.closing_rank);
                    if (candidateRank <= item.closing_rank) {
                      candidateComp = `Within by ${diff.toLocaleString("en-IN")}`;
                    } else {
                      candidateComp = `Beyond by ${diff.toLocaleString("en-IN")}`;
                    }
                  }

                  return (
                    <tr
                      key={item.id}
                      className={cn(
                        "transition-colors",
                        isCurrent ? "bg-primary/5 font-semibold" : "hover:bg-muted/30"
                      )}
                    >
                      <td className="py-2.5 pr-4">
                        <div className="flex items-center gap-2">
                          {isCurrent && (
                            <span className="size-1.5 rounded-full bg-primary shrink-0" />
                          )}
                          <span className={isCurrent ? "text-primary font-semibold" : "text-foreground"}>
                            {label}
                          </span>
                          {code === "KKR_SPECIAL" && (
                            <span className="rounded bg-amber-500/10 px-1.5 py-0.2 text-[10px] text-amber-700 dark:text-amber-300 font-mono">
                              Special Quota
                            </span>
                          )}
                          {code === "MOCK" && (
                            <span className="rounded bg-muted px-1.5 py-0.2 text-[10px] text-muted-foreground font-mono">
                              Trial
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-sm font-semibold text-foreground">
                        {item.closing_rank.toLocaleString("en-IN")}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-muted-foreground text-[11px]">
                        {deltaText}
                      </td>
                      <td
                        className={cn(
                          "py-2.5 pl-4 text-right font-mono text-[11px]",
                          hasCandidateRank
                            ? candidateRank <= item.closing_rank
                              ? "text-emerald-700 dark:text-emerald-400 font-medium"
                              : "text-muted-foreground"
                            : "text-muted-foreground"
                        )}
                      >
                        {candidateComp}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={4} className="py-4 text-center text-muted-foreground">
                    Data not available for this round
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground border-t border-border pt-2.5">
          <span>General engineering counselling sequence: Round 1 → Round 3 → Round 4.</span>
          <span className="font-mono">Standard Round 2 does not exist for general engineering</span>
        </div>
      </div>

      {/* 6. Multi-Year Historical Cutoff Table (Section 5) */}
      <div className="mt-6 rounded-lg border border-border bg-card p-4 sm:p-5">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <Calendar className="size-4 text-primary" />
              Multi-Year Historical Closing Ranks
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Verified final/terminal allotment closing ranks across published years (no interpolation).
            </p>
          </div>
          <span className="text-[10px] font-mono rounded bg-muted px-2 py-0.5 text-muted-foreground">
            {availableYears.length} Years Available
          </span>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {availableYears.map((year) => {
            const records = multiYearByYear.get(year) || [];
            // Pick terminal or highest round for that year
            const terminalRecord = [...records].sort((a, b) => {
              const codeA = CANONICAL_ROUND_NAMES[a.round_id]?.code || "";
              const codeB = CANONICAL_ROUND_NAMES[b.round_id]?.code || "";
              const idxA = progressionOrder.indexOf(codeA);
              const idxB = progressionOrder.indexOf(codeB);
              return idxB - idxA;
            })[0];

            if (!terminalRecord) return null;
            const rCode = CANONICAL_ROUND_NAMES[terminalRecord.round_id]?.code || "";
            const rLabel = CANONICAL_ROUND_NAMES[terminalRecord.round_id]?.name || getRoundLabel(rCode);
            const isSelectedYear = year === academicYear;

            return (
              <div
                key={year}
                className={cn(
                  "rounded-md border p-3.5 space-y-1.5 transition-colors",
                  isSelectedYear
                    ? "border-primary/40 bg-primary/5 shadow-xs"
                    : "border-border bg-muted/20"
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-sm text-foreground">
                    {year}
                  </span>
                  <span className="text-[10px] font-mono rounded bg-muted px-1.5 py-0.5 text-muted-foreground">
                    {rCode}
                  </span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-xs text-muted-foreground truncate" title={rLabel}>
                    {rLabel}
                  </span>
                  <span className="font-mono text-base font-bold text-foreground">
                    {terminalRecord.closing_rank.toLocaleString("en-IN")}
                  </span>
                </div>
                {hasCandidateRank && (
                  <p
                    className={cn(
                      "text-[10px] font-mono text-right pt-1 border-t border-border/40",
                      candidateRank <= terminalRecord.closing_rank
                        ? "text-emerald-700 dark:text-emerald-400"
                        : "text-muted-foreground"
                    )}
                  >
                    {candidateRank <= terminalRecord.closing_rank
                      ? `Within by ${(terminalRecord.closing_rank - candidateRank).toLocaleString("en-IN")}`
                      : `Beyond by ${(candidateRank - terminalRecord.closing_rank).toLocaleString("en-IN")}`}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 7. Source & Audit Provenance (Section 10) */}
      <div className="mt-6 border-t border-border pt-4">
        <button
          type="button"
          onClick={() => setShowProvenance(!showProvenance)}
          className="flex w-full items-center justify-between py-2 text-left text-xs font-semibold text-foreground hover:text-primary transition-colors"
          aria-expanded={showProvenance}
        >
          <span className="flex items-center gap-2">
            <Database className="size-3.5 text-muted-foreground" />
            Official Source & Verification Provenance
          </span>
          {showProvenance ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
        </button>

        {showProvenance && (
          <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2.5 rounded-md bg-muted/20 p-3.5 text-[11px] font-mono text-muted-foreground border border-border">
            <div>
              <span className="block text-foreground/70 font-semibold">Source Document</span>
              <span>Official COMEDK Allotment PDF</span>
            </div>
            <div>
              <span className="block text-foreground/70 font-semibold">Row Identifier</span>
              <span>{targetCutoff.row_identifier || "Direct Matrix Match"}</span>
            </div>
            <div>
              <span className="block text-foreground/70 font-semibold">Page Number</span>
              <span>{targetCutoff.page_number ? `Page ${targetCutoff.page_number}` : "Verified Allotment"}</span>
            </div>
            <div>
              <span className="block text-foreground/70 font-semibold">Audit Status</span>
              <span className="text-emerald-700 dark:text-emerald-400 font-semibold">
                {targetCutoff.status} · Immutable
              </span>
            </div>
            <div className="col-span-2 sm:col-span-4 pt-2 border-t border-border/50 text-[10px]">
              <span className="block text-foreground/70 font-semibold">Source Version ID</span>
              <span className="break-all">{targetCutoff.source_version_id}</span>
            </div>
          </div>
        )}
      </div>

      {/* 8. Mandatory Disclaimer */}
      <div className="mt-6 flex items-start gap-2 border-t border-border pt-4 text-[11px] text-muted-foreground leading-normal">
        <HelpCircle className="size-3.5 shrink-0 text-muted-foreground mt-0.5" />
        <p>
          Historical cutoffs represent verified past allotment data released by COMEDK. Counselling
          allotments vary year-over-year based on applicant volume, seat matrix adjustments, and choice
          patterns. Historical numerical containment is provided strictly for informational analysis and
          does not constitute an admission guarantee or predicted outcome.
        </p>
      </div>
    </Panel>
  );
}
