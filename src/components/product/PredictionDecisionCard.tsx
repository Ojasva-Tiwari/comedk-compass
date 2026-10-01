"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Database,
  HelpCircle,
  History,
  Info,
  Layers,
  RotateCw,
  Scale,
  ShieldAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/product/page";
import { cn } from "@/lib/utils";
import type {
  CandidateDecisionResponse,
  CandidateEvidenceState,
} from "@/lib/api-client";

export const EVIDENCE_STATE_LABELS: Record<CandidateEvidenceState, string> = {
  NUMERICALLY_BELOW_LOWER_BOUND: "Below the lower bound",
  WITHIN_LOWER_HALF: "Within the lower half of the range",
  WITHIN_UPPER_HALF: "Within the upper half of the range",
  NUMERICALLY_ABOVE_UPPER_BOUND: "Above the upper bound",
  INSUFFICIENT_EVIDENCE: "Not enough historical evidence",
};

interface PredictionDecisionCardProps {
  result: CandidateDecisionResponse | null;
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  className?: string;
}

export function PredictionDecisionCard({
  result,
  isLoading = false,
  error = null,
  onRetry,
  className,
}: PredictionDecisionCardProps) {
  const [showEvidence, setShowEvidence] = useState(false);
  const [showMetadata, setShowMetadata] = useState(false);

  // 1. Loading State
  if (isLoading) {
    return (
      <Panel className={cn("p-6 sm:p-8 animate-pulse", className)}>
        <div className="flex items-center gap-3">
          <div className="size-9 rounded-md bg-muted" />
          <div className="space-y-2">
            <div className="h-4 w-44 rounded bg-muted" />
            <div className="h-3 w-56 rounded bg-muted/60" />
          </div>
        </div>
        <div className="mt-8 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="h-20 rounded bg-muted/70" />
            <div className="h-20 rounded bg-muted/70" />
            <div className="h-20 rounded bg-muted/70" />
          </div>
          <div className="h-24 w-full rounded bg-muted/50" />
          <div className="h-20 w-full rounded bg-muted/30" />
        </div>
        <div className="mt-6 flex items-center gap-2 text-xs text-muted-foreground">
          <Scale className="size-4 animate-spin text-primary" />
          <span>Analyzing historical COMEDK data...</span>
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
              Unable to complete candidate rank evaluation
            </h3>
            <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
              {error.message ||
                "A network or processing issue prevented evaluating your rank against historical data. Please verify your selected round and parameters."}
            </p>
            {onRetry && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRetry}
                className="mt-4 gap-1.5 text-xs"
              >
                <RotateCw className="size-3.5" />
                Retry analysis
              </Button>
            )}
          </div>
        </div>
      </Panel>
    );
  }

  // 3. Empty / Initial State
  if (!result) {
    return (
      <Panel className={cn("p-8 text-center", className)}>
        <Layers className="mx-auto size-10 text-muted-foreground/60" />
        <h3 className="mt-3 text-sm font-semibold">Enter your COMEDK rank to begin</h3>
        <p className="mt-1 text-xs text-muted-foreground max-w-md mx-auto">
          Provide your rank, college, branch, counselling round and category quota to evaluate where
          your rank sits relative to the historical closing-rank range.
        </p>
      </Panel>
    );
  }

  // 4. Cold Start / Insufficient Evidence State
  if (
    result.evidence_state === "INSUFFICIENT_EVIDENCE" ||
    result.prediction_status === "INSUFFICIENT_EVIDENCE"
  ) {
    return (
      <Panel className={cn("p-6 sm:p-8 border-border bg-card", className)}>
        <div className="flex items-start gap-3">
          <div className="grid size-9 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
            <Info className="size-5" />
          </div>
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-border bg-muted px-2.5 py-0.5 font-mono text-[10px] font-semibold text-muted-foreground uppercase">
                {EVIDENCE_STATE_LABELS.INSUFFICIENT_EVIDENCE}
              </span>
              <span className="text-xs text-muted-foreground font-mono">
                {result.academic_year} · {result.round} · {result.category}
              </span>
            </div>

            <h3 className="mt-3 text-xl font-semibold tracking-tight text-foreground">
              Not enough historical evidence
            </h3>

            <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
              This college/branch/category combination does not have enough comparable historical
              observations for a responsible estimate.
            </p>

            <div className="mt-4 rounded-md border border-border bg-muted/40 p-3.5 text-xs text-muted-foreground">
              <p className="font-semibold text-foreground">
                Compass fails closed rather than substituting arbitrary guesses or ungrounded averages.
              </p>
              {result.explanation.length > 0 && (
                <ul className="mt-2 space-y-1 list-disc list-inside">
                  {result.explanation.map((item, idx) => (
                    <li key={idx} className="leading-relaxed">
                      {item}
                    </li>
                  ))}
                </ul>
              )}
              {result.cold_start_reason && result.cold_start_reason !== "NONE" && (
                <p className="mt-2 text-[11px] font-mono text-muted-foreground">
                  Cold-start code: {result.cold_start_reason}
                </p>
              )}
            </div>

            {/* Preserved Candidate Inputs */}
            <div className="mt-4 flex flex-wrap gap-3 text-xs text-muted-foreground font-mono border-t border-border pt-3">
              <span>Your Rank: <strong>{result.candidate_rank.toLocaleString("en-IN")}</strong></span>
              <span>•</span>
              <span>Year: <strong>{result.academic_year}</strong></span>
              <span>•</span>
              <span>Round: <strong>{result.round}</strong></span>
              <span>•</span>
              <span>Quota: <strong>{result.category}</strong></span>
            </div>

            <p className="mt-5 text-[11px] text-muted-foreground leading-normal border-t border-border pt-4">
              {result.disclaimer}
            </p>
          </div>
        </div>
      </Panel>
    );
  }

  // 5. Successful Candidate Decision Evaluation
  const candidateRank = result.candidate_rank;
  const predictedRank = result.predicted_closing_rank ?? 0;
  const lowerBound = result.lower_bound ?? (result.prediction_interval?.lower_bound ?? predictedRank);
  const upperBound = result.upper_bound ?? (result.prediction_interval?.upper_bound ?? predictedRank);

  // Position calculation for Range Bar:
  // Lower COMEDK rank = better rank.
  // Left: lowerBound, Center: predictedRank, Right: upperBound
  let markerPercent = 50;
  if (candidateRank < lowerBound) {
    markerPercent = 2; // Below lower bound (left of bar)
  } else if (candidateRank <= predictedRank) {
    const range = predictedRank - lowerBound;
    const fraction = range > 0 ? (candidateRank - lowerBound) / range : 0.5;
    markerPercent = Math.max(4, Math.min(48, Math.round(fraction * 50)));
  } else if (candidateRank <= upperBound) {
    const range = upperBound - predictedRank;
    const fraction = range > 0 ? (candidateRank - predictedRank) / range : 0.5;
    markerPercent = Math.max(52, Math.min(96, 50 + Math.round(fraction * 50)));
  } else {
    markerPercent = 98; // Above upper bound (right of bar)
  }

  const evidenceLabel = EVIDENCE_STATE_LABELS[result.evidence_state] || result.evidence_state;

  const accessibleRangeText = `Historical closing rank interval: Lower bound ${lowerBound.toLocaleString(
    "en-IN"
  )}, estimated closing rank ${predictedRank.toLocaleString(
    "en-IN"
  )}, upper bound ${upperBound.toLocaleString(
    "en-IN"
  )}. Your rank is ${candidateRank.toLocaleString("en-IN")}, which sits ${evidenceLabel.toLowerCase()}.`;

  return (
    <Panel className={cn("p-6 sm:p-8 border-border bg-card", className)}>
      {/* Header Badges */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md border border-border bg-muted px-2.5 py-1 text-xs font-semibold text-foreground">
            Decision Layer Analysis
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            {result.academic_year} {result.round} · {result.category}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1 rounded bg-muted px-2 py-0.5 font-mono text-[11px]">
            Evidence strength: {result.evidence_strength}
          </span>
          {result.observation_count > 0 && (
            <span className="text-[11px]">
              ({result.observation_count} historical observation
              {result.observation_count === 1 ? "" : "s"})
            </span>
          )}
        </div>
      </div>

      {/* 3 Core Metric Displays */}
      <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Metric 1: Candidate Rank */}
        <div className="rounded-lg border border-border bg-muted/20 p-4">
          <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            YOUR RANK
          </p>
          <p className="mt-1 font-mono text-2xl sm:text-3xl font-bold text-foreground">
            {candidateRank.toLocaleString("en-IN")}
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">Official COMEDK rank</p>
        </div>

        {/* Metric 2: Estimated Closing Rank */}
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
          <p className="font-mono text-[10px] uppercase tracking-wider text-primary font-semibold">
            ESTIMATED CLOSING RANK
          </p>
          <p className="mt-1 font-mono text-2xl sm:text-3xl font-bold text-foreground">
            {predictedRank.toLocaleString("en-IN")}
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">Historical point estimate</p>
        </div>

        {/* Metric 3: Historical Range */}
        <div className="rounded-lg border border-border bg-muted/20 p-4">
          <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            HISTORICAL RANGE
          </p>
          <p className="mt-1 font-mono text-lg sm:text-xl font-bold text-foreground truncate">
            {lowerBound.toLocaleString("en-IN")} — {upperBound.toLocaleString("en-IN")}
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">Uncertainty interval</p>
        </div>
      </div>

      {/* Candidate Position Summary */}
      <div className="mt-6 rounded-md border border-border bg-muted/30 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Candidate Position:
          </span>
          <span className="rounded border border-border bg-card px-2.5 py-0.5 text-xs font-semibold text-foreground">
            {evidenceLabel}
          </span>
        </div>

        <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
          {result.evidence_state === "NUMERICALLY_BELOW_LOWER_BOUND" && (
            <span>
              Your rank ({candidateRank.toLocaleString("en-IN")}) is <strong>numerically lower</strong>{" "}
              (better) than the lower bound ({lowerBound.toLocaleString("en-IN")}) of the estimated
              closing-rank range. In historical counselling, ranks in this bracket were consistently
              within the final allotment boundary.
            </span>
          )}
          {result.evidence_state === "WITHIN_LOWER_HALF" && (
            <span>
              Your rank ({candidateRank.toLocaleString("en-IN")}) is{" "}
              <strong>within the lower half</strong> of the estimated range (between the lower bound{" "}
              {lowerBound.toLocaleString("en-IN")} and the estimated closing rank{" "}
              {predictedRank.toLocaleString("en-IN")}). In historical observations, ranks in this
              interval were frequently within the eventual closing boundary.
            </span>
          )}
          {result.evidence_state === "WITHIN_UPPER_HALF" && (
            <span>
              Your rank ({candidateRank.toLocaleString("en-IN")}) is{" "}
              <strong>within the upper half</strong> of the estimated range (between the estimated
              closing rank {predictedRank.toLocaleString("en-IN")} and the upper bound{" "}
              {upperBound.toLocaleString("en-IN")}). Ranks in this interval depend heavily on
              inter-round cutoff expansion and seat volatility.
            </span>
          )}
          {result.evidence_state === "NUMERICALLY_ABOVE_UPPER_BOUND" && (
            <span>
              Your rank ({candidateRank.toLocaleString("en-IN")}) is{" "}
              <strong>numerically higher</strong> than the upper bound ({upperBound.toLocaleString("en-IN")})
              of the estimated closing-rank range. Historical cutoffs closed prior to this rank across
              comparable observations.
            </span>
          )}
        </p>
      </div>

      {/* Horizontal Range Visualization */}
      <div
        className="mt-6 rounded-lg border border-border bg-muted/20 p-4 sm:p-5"
        role="img"
        aria-label={accessibleRangeText}
      >
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Closing Rank Uncertainty Range</span>
          <span className="font-mono text-[11px]">Lower rank = Better</span>
        </div>

        {/* Visual Line Bar */}
        <div className="relative mt-8 mb-10 px-2 sm:px-4">
          {/* Main Track */}
          <div className="h-2 w-full rounded-full bg-border relative">
            {/* Interval highlight */}
            <div className="absolute inset-y-0 left-0 right-0 rounded-full bg-primary/20" />
            {/* Midpoint notch for estimate */}
            <div className="absolute top-0 bottom-0 left-1/2 w-0.5 -translate-x-1/2 bg-foreground/40" />
          </div>

          {/* Lower bound label (Left) */}
          <div className="absolute left-2 sm:left-4 -top-1.5 flex flex-col items-center">
            <span className="h-5 w-0.5 bg-foreground/60" />
            <span className="mt-2 font-mono text-xs font-semibold text-foreground">
              {lowerBound.toLocaleString("en-IN")}
            </span>
            <span className="text-[10px] text-muted-foreground">Lower Bound</span>
          </div>

          {/* Estimate label (Center) */}
          <div className="absolute left-1/2 -translate-x-1/2 -top-1.5 flex flex-col items-center">
            <span className="h-5 w-0.5 bg-primary" />
            <span className="mt-2 font-mono text-xs font-bold text-primary">
              {predictedRank.toLocaleString("en-IN")}
            </span>
            <span className="text-[10px] font-medium text-primary">Estimate</span>
          </div>

          {/* Upper bound label (Right) */}
          <div className="absolute right-2 sm:right-4 -top-1.5 flex flex-col items-center">
            <span className="h-5 w-0.5 bg-foreground/60" />
            <span className="mt-2 font-mono text-xs font-semibold text-foreground">
              {upperBound.toLocaleString("en-IN")}
            </span>
            <span className="text-[10px] text-muted-foreground">Upper Bound</span>
          </div>

          {/* Candidate Rank Marker */}
          <div
            className="absolute -top-3.5 -translate-x-1/2 flex flex-col items-center z-10"
            style={{ left: `${markerPercent}%` }}
          >
            <div className="size-4 rounded-full border-2 border-background bg-foreground shadow-sm flex items-center justify-center">
              <span className="size-1.5 rounded-full bg-background" />
            </div>
            <span className="mt-8 font-mono text-xs font-extrabold text-foreground bg-card/90 px-1.5 py-0.5 rounded border border-border shadow-xs whitespace-nowrap">
              YOUR RANK: {candidateRank.toLocaleString("en-IN")}
            </span>
          </div>
        </div>

        <p className="mt-6 text-[11px] text-muted-foreground leading-relaxed text-center sm:text-left">
          Note: In COMEDK counselling, a lower numerical rank is competitive. Ranks to the left are
          numerically lower (stricter cutoff). This interval reflects historical model uncertainty, not
          an admission guarantee.
        </p>
      </div>

      {/* Human-Readable Explanations */}
      {result.explanation.length > 0 && (
        <div className="mt-6 rounded-md border border-border bg-muted/30 p-4 text-xs space-y-2">
          <p className="font-semibold text-foreground uppercase text-[10px] tracking-wider">
            Evaluation Details
          </p>
          <ul className="space-y-1.5 list-disc list-inside text-muted-foreground leading-relaxed">
            {result.explanation.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Historical Evidence Section (Collapsible) */}
      <div className="mt-6 border-t border-border pt-4">
        <button
          type="button"
          onClick={() => setShowEvidence(!showEvidence)}
          className="flex w-full items-center justify-between py-2 text-left text-xs font-semibold text-foreground hover:text-primary transition-colors"
          aria-expanded={showEvidence}
        >
          <span className="flex items-center gap-2">
            <History className="size-3.5 text-muted-foreground" />
            How much historical evidence supports this?
          </span>
          {showEvidence ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
        </button>

        {showEvidence && (
          <div className="mt-3 space-y-3 rounded-md bg-muted/30 p-4 text-xs">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div className="rounded border border-border bg-card p-2.5">
                <span className="block text-[10px] text-muted-foreground uppercase">Historical Observations</span>
                <span className="font-mono font-semibold text-sm text-foreground">
                  {result.observation_count}
                </span>
              </div>
              <div className="rounded border border-border bg-card p-2.5">
                <span className="block text-[10px] text-muted-foreground uppercase">Latest Comparable Year</span>
                <span className="font-mono font-semibold text-sm text-foreground">
                  {result.latest_comparable_year ?? "N/A"}
                </span>
              </div>
              <div className="rounded border border-border bg-card p-2.5">
                <span className="block text-[10px] text-muted-foreground uppercase">Evidence Strength</span>
                <span className="font-mono font-semibold text-sm text-foreground">
                  {result.evidence_strength}
                </span>
              </div>
              <div className="rounded border border-border bg-card p-2.5 col-span-2 sm:col-span-3">
                <span className="block text-[10px] text-muted-foreground uppercase">Prediction Model</span>
                <span className="font-mono text-xs text-foreground">{result.model_name}</span>
              </div>
            </div>

            {/* Evidence Trail */}
            {result.evidence_trail.length > 0 && (
              <div className="pt-2 border-t border-border/60">
                <p className="font-semibold text-muted-foreground uppercase text-[10px] tracking-wider mb-2">
                  Official Historical Cutoffs Used
                </p>
                <div className="space-y-1.5">
                  {result.evidence_trail.map((ev, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between rounded border border-border bg-card px-2.5 py-1.5 font-mono text-[11px]"
                    >
                      <span className="text-muted-foreground">{ev.description}</span>
                      <span className="font-semibold text-foreground">
                        {ev.closing_rank.toLocaleString("en-IN")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Model & Provenance Details (Collapsible) */}
      <div className="mt-2">
        <button
          type="button"
          onClick={() => setShowMetadata(!showMetadata)}
          className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground py-1 transition-colors"
          aria-expanded={showMetadata}
        >
          <Database className="size-3" />
          <span>Evidence & methodology details</span>
          {showMetadata ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
        </button>

        {showMetadata && (
          <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2 rounded bg-muted/20 p-2.5 text-[10px] font-mono text-muted-foreground border border-border">
            <div>
              <span className="block text-foreground/70">Model Version</span>
              <span>{result.model_version}</span>
            </div>
            <div>
              <span className="block text-foreground/70">Dataset Version</span>
              <span>{result.dataset_version}</span>
            </div>
            <div>
              <span className="block text-foreground/70">Feature Definition</span>
              <span>{result.feature_definition_version}</span>
            </div>
            <div>
              <span className="block text-foreground/70">Generated At</span>
              <span className="truncate block" title={result.generated_at}>
                {new Date(result.generated_at).toLocaleString()}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Mandatory Disclaimer */}
      <div className="mt-6 flex items-start gap-2 border-t border-border pt-4 text-[11px] text-muted-foreground leading-normal">
        <HelpCircle className="size-3.5 shrink-0 text-muted-foreground mt-0.5" />
        <p>{result.disclaimer}</p>
      </div>
    </Panel>
  );
}
