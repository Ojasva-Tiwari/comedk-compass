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
import type { PredictionResult } from "@/lib/api-client";
export { PredictionDecisionCard, EVIDENCE_STATE_LABELS } from "./PredictionDecisionCard";

interface PredictionCardProps {
  result: PredictionResult | null;
  isLoading?: boolean;
  error?: Error | null;
  candidateRank?: number | null;
  onRetry?: () => void;
  className?: string;
}

export function PredictionCard({
  result,
  isLoading = false,
  error = null,
  candidateRank = null,
  onRetry,
  className,
}: PredictionCardProps) {
  const [showEvidence, setShowEvidence] = useState(false);
  const [showMetadata, setShowMetadata] = useState(false);

  // 1. Loading State
  if (isLoading) {
    return (
      <Panel className={cn("p-6 sm:p-8 animate-pulse", className)}>
        <div className="flex items-center gap-3">
          <div className="size-9 rounded-md bg-muted" />
          <div className="space-y-2">
            <div className="h-4 w-36 rounded bg-muted" />
            <div className="h-3 w-48 rounded bg-muted/60" />
          </div>
        </div>
        <div className="mt-8 space-y-4">
          <div className="h-12 w-48 rounded bg-muted" />
          <div className="h-8 w-full rounded bg-muted/50" />
          <div className="h-20 w-full rounded bg-muted/30" />
        </div>
        <div className="mt-6 flex items-center gap-2 text-xs text-muted-foreground">
          <Scale className="size-4 animate-spin text-primary" />
          <span>Analyzing historical COMEDK cutoffs from the official Compass dataset...</span>
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
              Unable to compute closing rank estimate
            </h3>
            <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
              {error.message ||
                "A network or processing issue prevented generating the statistical estimate. Please verify your selected round and college parameters."}
            </p>
            {onRetry && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRetry}
                className="mt-4 gap-1.5 text-xs"
              >
                <RotateCw className="size-3.5" />
                Retry calculation
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
        <h3 className="mt-3 text-sm font-semibold">Select options to see closing rank estimate</h3>
        <p className="mt-1 text-xs text-muted-foreground max-w-md mx-auto">
          Choose a college, branch, counselling round and quota to inspect historical evidence and
          estimated closing rank bounds.
        </p>
      </Panel>
    );
  }

  // 4. Cold Start / Insufficient Evidence State
  if (result.status === "INSUFFICIENT_EVIDENCE") {
    return (
      <Panel className={cn("p-6 sm:p-8 border-border bg-card", className)}>
        <div className="flex items-start gap-3">
          <div className="grid size-9 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
            <Info className="size-5" />
          </div>
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-border bg-muted px-2.5 py-0.5 font-mono text-[10px] font-semibold text-muted-foreground uppercase">
                Status: Insufficient Evidence
              </span>
              <span className="text-xs text-muted-foreground font-mono">
                {result.round} · {result.category}
              </span>
            </div>

            <h3 className="mt-3 text-xl font-semibold tracking-tight">
              Not enough historical evidence
            </h3>

            <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
              We don't have sufficient comparable COMEDK cutoff data for this college, branch,
              category and round to generate a responsible estimate.
            </p>

            <div className="mt-4 rounded-md border border-border bg-muted/40 p-3.5 text-xs text-muted-foreground">
              <p className="font-semibold text-foreground">
                This is intentional — Compass does not guess when evidence is weak.
              </p>
              {result.explanation.length > 0 && (
                <ul className="mt-2 space-y-1 list-disc list-inside">
                  {result.explanation.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              )}
              {result.cold_start_reason && result.cold_start_reason !== "NONE" && (
                <p className="mt-2 text-[11px] font-mono text-muted-foreground">
                  Reason code: {result.cold_start_reason}
                </p>
              )}
            </div>

            <p className="mt-5 text-[11px] text-muted-foreground leading-normal border-t border-border pt-4">
              {result.disclaimer}
            </p>
          </div>
        </div>
      </Panel>
    );
  }

  // 5. Successful Prediction State
  const predictedRank = result.predicted_closing_rank ?? 0;
  const lowerBound = result.lower_bound ?? (result.prediction_interval?.lower_bound ?? predictedRank);
  const upperBound = result.upper_bound ?? (result.prediction_interval?.upper_bound ?? predictedRank);

  // Uncertainty interval position percentage (clamped between 5% and 95%)
  const span = upperBound - lowerBound;
  const dotPercent =
    span > 0
      ? Math.max(5, Math.min(95, Math.round(((predictedRank - lowerBound) / span) * 100)))
      : 50;

  // Candidate comparison semantics: candidate_rank <= predicted_closing_rank
  const isCandidateEligible =
    candidateRank !== null && candidateRank > 0 && candidateRank <= predictedRank;

  return (
    <Panel className={cn("p-6 sm:p-8 border-border bg-card", className)}>
      {/* Header Badges */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md border border-primary/20 bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">
            Estimated Cutoff
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            {result.academic_year} {result.round} · {result.category}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1 rounded bg-muted px-2 py-0.5 font-mono text-[11px]">
            Evidence: {result.evidence_strength}
          </span>
          {result.observation_count > 0 && (
            <span className="text-[11px]">
              ({result.observation_count} historical observation
              {result.observation_count === 1 ? "" : "s"})
            </span>
          )}
        </div>
      </div>

      {/* Main Closing Rank Display */}
      <div className="mt-6">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Estimated Closing Rank
        </p>
        <div className="mt-2 flex flex-wrap items-baseline gap-3">
          <h2 className="font-mono text-4xl font-semibold tracking-tight sm:text-5xl text-foreground">
            {predictedRank.toLocaleString("en-IN")}
          </h2>
          <span className="text-xs text-muted-foreground">
            {result.round === "R4" || result.round === "TERMINAL"
              ? "Terminal allotment estimate"
              : `${result.round} closing estimate`}
          </span>
        </div>
      </div>

      {/* Visual Uncertainty Range */}
      <div className="mt-8 rounded-lg border border-border bg-muted/30 p-4 sm:p-5">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Historical estimate range</span>
          <span className="font-mono text-[11px]">Model uncertainty range</span>
        </div>

        {/* Range Bar Graphic */}
        <div className="relative mt-7 mb-7 px-2">
          {/* Track line */}
          <div className="h-1.5 w-full rounded-full bg-border relative">
            {/* Interval highlight */}
            <div className="absolute inset-y-0 left-0 right-0 rounded-full bg-primary/25" />
          </div>

          {/* Lower bound notch */}
          <div className="absolute left-2 -top-1.5 flex flex-col items-center">
            <span className="h-4 w-0.5 bg-muted-foreground/60" />
            <span className="mt-2 font-mono text-xs font-medium text-muted-foreground">
              {lowerBound.toLocaleString("en-IN")}
            </span>
            <span className="text-[10px] text-muted-foreground">Lower (stricter)</span>
          </div>

          {/* Point Estimate Marker */}
          <div
            className="absolute -top-2.5 -translate-x-1/2 flex flex-col items-center"
            style={{ left: `${dotPercent}%` }}
          >
            <span
              className="size-5 rounded-full border-2 border-background bg-primary shadow-sm"
              aria-label={`Point estimate: ${predictedRank.toLocaleString("en-IN")}`}
            />
            <span className="mt-1 font-mono text-xs font-bold text-foreground">
              {predictedRank.toLocaleString("en-IN")}
            </span>
            <span className="text-[10px] font-medium text-primary">Estimate</span>
          </div>

          {/* Upper bound notch */}
          <div className="absolute right-2 -top-1.5 flex flex-col items-center">
            <span className="h-4 w-0.5 bg-muted-foreground/60" />
            <span className="mt-2 font-mono text-xs font-medium text-muted-foreground">
              {upperBound.toLocaleString("en-IN")}
            </span>
            <span className="text-[10px] text-muted-foreground">Upper (expanded)</span>
          </div>
        </div>

        <p className="mt-6 text-[11px] text-muted-foreground leading-relaxed text-center sm:text-left">
          Note: This interval reflects historical COMEDK round movement and volatility. It is a
          statistical projection, not a guaranteed admission bracket.
        </p>
      </div>

      {/* Candidate Rank Comparison (if provided) */}
      {candidateRank !== null && candidateRank > 0 && (
        <div className="mt-5 rounded-md border border-border bg-card p-3.5 text-xs">
          <div className="flex items-start gap-2">
            <Scale className="size-4 shrink-0 text-muted-foreground mt-0.5" />
            <div>
              <p className="text-foreground">
                <strong>Your Rank:</strong>{" "}
                <span className="font-mono font-semibold">{candidateRank.toLocaleString("en-IN")}</span>
              </p>
              <p className="mt-1 text-muted-foreground">
                {isCandidateEligible ? (
                  <span>
                    Your rank is <strong>numerically within</strong> the estimated closing rank
                    boundary ({predictedRank.toLocaleString("en-IN")}). In historical counselling, ranks
                    at or below the closing cutoff were eligible for allotment.
                  </span>
                ) : (
                  <span>
                    Your rank is <strong>numerically higher</strong> than the estimated closing rank
                    boundary ({predictedRank.toLocaleString("en-IN")}). In historical counselling, cutoffs
                    closed prior to this rank.
                  </span>
                )}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Historical Context & Evidence Section */}
      <div className="mt-6 border-t border-border pt-4">
        <button
          type="button"
          onClick={() => setShowEvidence(!showEvidence)}
          className="flex w-full items-center justify-between py-2 text-left text-xs font-semibold text-foreground hover:text-primary transition-colors"
          aria-expanded={showEvidence}
        >
          <span className="flex items-center gap-2">
            <History className="size-3.5 text-muted-foreground" />
            How was this estimated?
          </span>
          {showEvidence ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
        </button>

        {showEvidence && (
          <div className="mt-3 space-y-3 rounded-md bg-muted/30 p-4 text-xs">
            {/* Explanations */}
            <div>
              <p className="font-semibold text-muted-foreground uppercase text-[10px] tracking-wider">
                Methodology & Context
              </p>
              <ul className="mt-2 space-y-1.5 list-disc list-inside text-muted-foreground">
                {result.explanation.map((item, idx) => (
                  <li key={idx} className="leading-relaxed">
                    {item}
                  </li>
                ))}
              </ul>
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

      {/* Model & Provenance Details (Secondary) */}
      <div className="mt-2">
        <button
          type="button"
          onClick={() => setShowMetadata(!showMetadata)}
          className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground py-1 transition-colors"
          aria-expanded={showMetadata}
        >
          <Database className="size-3" />
          <span>Model specification & dataset metadata</span>
          {showMetadata ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
        </button>

        {showMetadata && (
          <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2 rounded bg-muted/20 p-2.5 text-[10px] font-mono text-muted-foreground border border-border">
            <div>
              <span className="block text-foreground/70">Model</span>
              <span className="truncate block" title={result.model_name}>
                {result.model_name}
              </span>
            </div>
            <div>
              <span className="block text-foreground/70">Model Version</span>
              <span>{result.model_version}</span>
            </div>
            <div>
              <span className="block text-foreground/70">Dataset Version</span>
              <span>{result.dataset_version}</span>
            </div>
            <div>
              <span className="block text-foreground/70">Latest Historical Year</span>
              <span>{result.latest_comparable_year ?? "N/A"}</span>
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
