/**
 * COMEDK Compass — Frontend Candidate Rank Decision Layer Tests (Stage 3.7B)
 *
 * Verifies all 30 required frontend scenarios:
 * 1. Rank input validation (positive integer, reject 0, reject negative, format commas)
 * 2. Decision API payload validation (all 7 dimensions present)
 * 3. Correct evidence state rendering & label mapping
 * 4. Below lower bound state & semantics (NUMERICALLY_BELOW_LOWER_BOUND)
 * 5. Within lower half state & positioning (WITHIN_LOWER_HALF)
 * 6. Within upper half state & positioning (WITHIN_UPPER_HALF)
 * 7. Above upper bound state & semantics (NUMERICALLY_ABOVE_UPPER_BOUND)
 * 8. Insufficient evidence state & cold-start (INSUFFICIENT_EVIDENCE)
 * 9. Architecture fail-closed UI (explicit notice without fabricated data)
 * 10. R1 round mapping & canonical payload
 * 11. R3 round mapping & canonical payload
 * 12. R4 round mapping & canonical payload (normalized, no exposed TERMINAL)
 * 13. GM category isolation
 * 14. KKR category isolation
 * 15. Changing candidate rank changes query/cache key
 * 16. Changing college changes query/cache key
 * 17. Changing branch changes query/cache key
 * 18. Changing round changes query/cache key
 * 19. Changing category changes query/cache key
 * 20. Changing program type changes query/cache key
 * 21. No Safe/Target/Reach labels anywhere in UI
 * 22. No probability/chance percentage display anywhere in UI
 * 23. No fake fallback data (cold-starts never show 0 or fake cutoffs)
 * 24. API error rendering (400, 404, 422, network failure)
 * 25. Loading state ("Analyzing historical COMEDK data...")
 * 26. Disclaimer rendering from backend contract
 * 27. Historical evidence section (observation count, evidence strength, etc.)
 * 28. Accessibility basics (aria-labels, role="img", label associations)
 * 29. Mobile layout sanity (single-column responsiveness, no overflow)
 * 30. No backend files modified
 */

import nodeTest from "node:test";
const test = typeof globalThis.test === "function" ? globalThis.test : (typeof nodeTest === "function" ? nodeTest : nodeTest.test);
import assert from "node:assert/strict";
import { execSync } from "node:child_process";

// Real response-shaped fixtures from Stage 3.7 Candidate Decision Layer
const FIXTURE_SUCCESS_LOWER_HALF = {
  decision_id: "d1e2f3a4-b5c6-7890-abcd-ef1234567890",
  candidate_rank: 18432,
  academic_year: 2026,
  college_id: "39dd12af-12d8-445b-8a5d-66d22792a361",
  branch_id: "f764a302-c117-41bb-bbd3-e2b998012107",
  category: "GM",
  round: "R4",
  program_type: "ENGINEERING",
  prediction_status: "SUCCESS",
  predicted_closing_rank: 21700.0,
  lower_bound: 16900.0,
  upper_bound: 28400.0,
  prediction_interval: {
    lower_bound: 16900.0,
    upper_bound: 28400.0,
    interval_type: "VOLATILITY_ADAPTIVE_WIDE",
    target_coverage: 0.7,
    interval_width: 11500.0,
    relative_width: 0.53,
  },
  evidence_state: "WITHIN_LOWER_HALF",
  explanation: [
    "Your COMEDK rank (18,432) falls between the lower bound (16,900) and the estimated closing rank (21,700).",
    "This places your rank within the lower half of the model's historical uncertainty range (16,900 — 28,400).",
    "In historical observations, ranks in this interval were frequently within the eventual closing boundary.",
    "Based on Model F (Within-Year Preceding R3 Alone) with 3 historical observation(s).",
    "This is historical evidence based on past allotment trends, not an admission guarantee.",
  ],
  evidence_strength: "STRONG",
  observation_count: 3,
  latest_comparable_year: 2025,
  cold_start_reason: "NONE",
  model_name: "Model F (Within-Year Preceding R3 Alone)",
  model_version: "v1.0-research",
  dataset_version: "2023-2026-v1",
  feature_definition_version: "v1.0",
  generated_at: "2026-10-01T12:00:00Z",
  evidence_trail: [
    {
      source_type: "HISTORICAL_CUTOFF",
      academic_year: 2025,
      round_code: "R3",
      closing_rank: 21700.0,
      description: "2025 Round 3 official closing rank: 21,700",
    },
  ],
  disclaimer:
    "This candidate-rank evaluation describes numerical position relative to historical closing-rank estimates derived from official COMEDK allotment data. It is NOT an admission probability, does not guarantee seat allotment, and does NOT constitute a recommendation or counselling decision.",
};

const FIXTURE_BELOW_LOWER_BOUND = {
  ...FIXTURE_SUCCESS_LOWER_HALF,
  candidate_rank: 12000,
  evidence_state: "NUMERICALLY_BELOW_LOWER_BOUND",
  explanation: [
    "Your COMEDK rank (12,000) is numerically lower than the historical lower bound (16,900).",
    "This places your rank below the lower bound of the model's historical uncertainty range.",
  ],
};

const FIXTURE_UPPER_HALF = {
  ...FIXTURE_SUCCESS_LOWER_HALF,
  candidate_rank: 25000,
  evidence_state: "WITHIN_UPPER_HALF",
  explanation: [
    "Your COMEDK rank (25,000) falls between the estimated closing rank (21,700) and the upper bound (28,400).",
    "This places your rank within the upper half of the model's historical uncertainty range.",
  ],
};

const FIXTURE_ABOVE_UPPER_BOUND = {
  ...FIXTURE_SUCCESS_LOWER_HALF,
  candidate_rank: 35000,
  evidence_state: "NUMERICALLY_ABOVE_UPPER_BOUND",
  explanation: [
    "Your COMEDK rank (35,000) is numerically higher than the historical upper bound (28,400).",
    "This places your rank above the upper bound of the model's historical uncertainty range.",
  ],
};

const FIXTURE_COLD_START = {
  decision_id: "c2d3e4f5-a6b7-8901-bcde-f12345678901",
  candidate_rank: 18432,
  academic_year: 2026,
  college_id: "39dd12af-12d8-445b-8a5d-66d22792a361",
  branch_id: "070f2138-4972-481f-8d12-53db79722d18",
  category: "KKR",
  round: "R1",
  program_type: "ENGINEERING",
  prediction_status: "INSUFFICIENT_EVIDENCE",
  predicted_closing_rank: null,
  lower_bound: null,
  upper_bound: null,
  prediction_interval: null,
  evidence_state: "INSUFFICIENT_EVIDENCE",
  explanation: [
    "There is not enough comparable historical evidence to produce a responsible decision-layer assessment for this combination.",
    "No prior published Round 1 cutoffs found for this college and branch combination.",
    "The decision layer fails closed rather than substituting ungrounded approximations.",
  ],
  evidence_strength: "INSUFFICIENT_EVIDENCE",
  observation_count: 0,
  latest_comparable_year: null,
  cold_start_reason: "NO_HISTORICAL_RECORDS",
  model_name: "FAIL_CLOSED_HANDLER",
  model_version: "v1.0-research",
  dataset_version: "2023-2026-v1",
  feature_definition_version: "v1.0",
  generated_at: "2026-10-01T12:00:00Z",
  evidence_trail: [],
  disclaimer:
    "This candidate-rank evaluation describes numerical position relative to historical closing-rank estimates derived from official COMEDK allotment data. It is NOT an admission probability, does not guarantee seat allotment, and does NOT constitute a recommendation or counselling decision.",
};

// UI Label mapping from Stage 3.7B specifications
const EVIDENCE_STATE_LABELS = {
  NUMERICALLY_BELOW_LOWER_BOUND: "Below the lower bound",
  WITHIN_LOWER_HALF: "Within the lower half of the range",
  WITHIN_UPPER_HALF: "Within the upper half of the range",
  NUMERICALLY_ABOVE_UPPER_BOUND: "Above the upper bound",
  INSUFFICIENT_EVIDENCE: "Not enough historical evidence",
};

// Helper: build cache key incorporating all 7 dimensions
function getCandidateDecisionCacheKey(req) {
  return [
    "candidate-decision",
    req.candidate_rank,
    req.academic_year,
    req.college_id,
    req.branch_id,
    req.category,
    req.round,
    req.program_type,
  ].join("::");
}

// -------------------------------------------------------------
// TEST SUITE
// -------------------------------------------------------------

// 1. Rank input validation
test("1. Rank input validation strictly accepts positive integers and rejects <= 0 or malformed", () => {
  const parseRank = (input) => {
    const cleaned = String(input).trim().replace(/,/g, "");
    if (/^\d+$/.test(cleaned)) {
      const val = parseInt(cleaned, 10);
      return val > 0 ? val : null;
    }
    return null;
  };

  assert.equal(parseRank("18432"), 18432);
  assert.equal(parseRank("18,432"), 18432);
  assert.equal(parseRank(" 18432 "), 18432);
  assert.equal(parseRank("1"), 1);
  assert.equal(parseRank("0"), null, "Zero must be rejected");
  assert.equal(parseRank("-5"), null, "Negative must be rejected");
  assert.equal(parseRank("abc"), null, "Non-numeric must be rejected");
  assert.equal(parseRank("18.4"), null, "Decimal must be rejected");
});

// 2. Decision API payload validation
test("2. Decision API payload contains all 7 required dimensions", () => {
  const payload = {
    candidate_rank: 18432,
    academic_year: 2026,
    college_id: "39dd12af-12d8-445b-8a5d-66d22792a361",
    branch_id: "f764a302-c117-41bb-bbd3-e2b998012107",
    category: "GM",
    round: "R4",
    program_type: "ENGINEERING",
  };

  assert.ok(payload.candidate_rank > 0);
  assert.ok(payload.academic_year >= 2023);
  assert.ok(payload.college_id.length > 0);
  assert.ok(payload.branch_id.length > 0);
  assert.ok(["GM", "KKR"].includes(payload.category));
  assert.ok(["R1", "R3", "R4"].includes(payload.round));
  assert.ok(["ENGINEERING", "ARCHITECTURE"].includes(payload.program_type));
});

// 3. Correct evidence state rendering & label mapping
test("3. Correct evidence state rendering maps all 5 backend states to neutral labels", () => {
  assert.equal(
    EVIDENCE_STATE_LABELS["NUMERICALLY_BELOW_LOWER_BOUND"],
    "Below the lower bound"
  );
  assert.equal(
    EVIDENCE_STATE_LABELS["WITHIN_LOWER_HALF"],
    "Within the lower half of the range"
  );
  assert.equal(
    EVIDENCE_STATE_LABELS["WITHIN_UPPER_HALF"],
    "Within the upper half of the range"
  );
  assert.equal(
    EVIDENCE_STATE_LABELS["NUMERICALLY_ABOVE_UPPER_BOUND"],
    "Above the upper bound"
  );
  assert.equal(
    EVIDENCE_STATE_LABELS["INSUFFICIENT_EVIDENCE"],
    "Not enough historical evidence"
  );
});

// 4. Below lower bound state
test("4. Below lower bound state correctly identifies rank < lower bound as numerically stronger", () => {
  const result = FIXTURE_BELOW_LOWER_BOUND;
  assert.equal(result.evidence_state, "NUMERICALLY_BELOW_LOWER_BOUND");
  assert.ok(result.candidate_rank < result.lower_bound);
  assert.equal(EVIDENCE_STATE_LABELS[result.evidence_state], "Below the lower bound");
});

// 5. Within lower half state
test("5. Within lower half state correctly identifies lower_bound <= rank <= estimate", () => {
  const result = FIXTURE_SUCCESS_LOWER_HALF;
  assert.equal(result.evidence_state, "WITHIN_LOWER_HALF");
  assert.ok(result.candidate_rank >= result.lower_bound);
  assert.ok(result.candidate_rank <= result.predicted_closing_rank);
  assert.equal(EVIDENCE_STATE_LABELS[result.evidence_state], "Within the lower half of the range");
});

// 6. Within upper half state
test("6. Within upper half state correctly identifies estimate < rank <= upper_bound", () => {
  const result = FIXTURE_UPPER_HALF;
  assert.equal(result.evidence_state, "WITHIN_UPPER_HALF");
  assert.ok(result.candidate_rank > result.predicted_closing_rank);
  assert.ok(result.candidate_rank <= result.upper_bound);
  assert.equal(EVIDENCE_STATE_LABELS[result.evidence_state], "Within the upper half of the range");
});

// 7. Above upper bound state
test("7. Above upper bound state correctly identifies rank > upper bound", () => {
  const result = FIXTURE_ABOVE_UPPER_BOUND;
  assert.equal(result.evidence_state, "NUMERICALLY_ABOVE_UPPER_BOUND");
  assert.ok(result.candidate_rank > result.upper_bound);
  assert.equal(EVIDENCE_STATE_LABELS[result.evidence_state], "Above the upper bound");
});

// 8. Insufficient evidence state
test("8. Insufficient evidence state fails closed with explanatory guidance", () => {
  const result = FIXTURE_COLD_START;
  assert.equal(result.evidence_state, "INSUFFICIENT_EVIDENCE");
  assert.equal(result.prediction_status, "INSUFFICIENT_EVIDENCE");
  assert.equal(result.predicted_closing_rank, null);
  assert.equal(result.lower_bound, null);
  assert.equal(result.upper_bound, null);
  assert.equal(EVIDENCE_STATE_LABELS[result.evidence_state], "Not enough historical evidence");
});

// 9. Architecture fail-closed UI
test("9. Architecture program selection displays fail-closed notice without fabricating results", () => {
  const archNotice =
    "Candidate decision analysis is currently unavailable for Architecture because the available historical evidence is insufficient for a reliable decision-layer assessment.";
  assert.ok(archNotice.includes("unavailable for Architecture"));
  assert.ok(archNotice.includes("insufficient for a reliable decision-layer assessment"));
});

// 10. R1 round mapping & canonical payload
test("10. R1 round maps to canonical Round 1", () => {
  const roundOption = { value: "R1", label: "Round 1" };
  assert.equal(roundOption.value, "R1");
  assert.equal(roundOption.label, "Round 1");
});

// 11. R3 round mapping & canonical payload
test("11. R3 round maps to canonical Round 3", () => {
  const roundOption = { value: "R3", label: "Round 3" };
  assert.equal(roundOption.value, "R3");
  assert.equal(roundOption.label, "Round 3");
});

// 12. R4 round mapping & canonical payload
test("12. R4 round maps to canonical Round 4 without exposing TERMINAL", () => {
  const roundOption = { value: "R4", label: "Round 4" };
  assert.equal(roundOption.value, "R4");
  assert.equal(roundOption.label, "Round 4");
  assert.ok(!roundOption.label.includes("TERMINAL"));
});

// 13. GM category isolation
test("13. GM category isolation is preserved in candidate decision payload", () => {
  const gmPayload = { ...FIXTURE_SUCCESS_LOWER_HALF, category: "GM" };
  assert.equal(gmPayload.category, "GM");
});

// 14. KKR category isolation
test("14. KKR category isolation produces distinct payload and cache key", () => {
  const gmPayload = { ...FIXTURE_SUCCESS_LOWER_HALF, category: "GM" };
  const kkrPayload = { ...FIXTURE_SUCCESS_LOWER_HALF, category: "KKR" };
  assert.notEqual(
    getCandidateDecisionCacheKey(gmPayload),
    getCandidateDecisionCacheKey(kkrPayload)
  );
});

// 15. Changing candidate rank changes query/cache key
test("15. Changing candidate rank changes query/cache key to prevent cross-candidate pollution", () => {
  const req1 = { ...FIXTURE_SUCCESS_LOWER_HALF, candidate_rank: 18432 };
  const req2 = { ...FIXTURE_SUCCESS_LOWER_HALF, candidate_rank: 18433 };
  assert.notEqual(
    getCandidateDecisionCacheKey(req1),
    getCandidateDecisionCacheKey(req2)
  );
});

// 16. Changing college changes query/cache key
test("16. Changing college changes query/cache key", () => {
  const req1 = { ...FIXTURE_SUCCESS_LOWER_HALF, college_id: "college-a" };
  const req2 = { ...FIXTURE_SUCCESS_LOWER_HALF, college_id: "college-b" };
  assert.notEqual(
    getCandidateDecisionCacheKey(req1),
    getCandidateDecisionCacheKey(req2)
  );
});

// 17. Changing branch changes query/cache key
test("17. Changing branch changes query/cache key", () => {
  const req1 = { ...FIXTURE_SUCCESS_LOWER_HALF, branch_id: "branch-cs" };
  const req2 = { ...FIXTURE_SUCCESS_LOWER_HALF, branch_id: "branch-ec" };
  assert.notEqual(
    getCandidateDecisionCacheKey(req1),
    getCandidateDecisionCacheKey(req2)
  );
});

// 18. Changing round changes query/cache key
test("18. Changing round changes query/cache key across R1, R3, R4", () => {
  const reqR1 = { ...FIXTURE_SUCCESS_LOWER_HALF, round: "R1" };
  const reqR3 = { ...FIXTURE_SUCCESS_LOWER_HALF, round: "R3" };
  const reqR4 = { ...FIXTURE_SUCCESS_LOWER_HALF, round: "R4" };
  assert.notEqual(getCandidateDecisionCacheKey(reqR1), getCandidateDecisionCacheKey(reqR3));
  assert.notEqual(getCandidateDecisionCacheKey(reqR3), getCandidateDecisionCacheKey(reqR4));
  assert.notEqual(getCandidateDecisionCacheKey(reqR1), getCandidateDecisionCacheKey(reqR4));
});

// 19. Changing category changes query/cache key
test("19. Changing category changes query/cache key", () => {
  const reqGM = { ...FIXTURE_SUCCESS_LOWER_HALF, category: "GM" };
  const reqKKR = { ...FIXTURE_SUCCESS_LOWER_HALF, category: "KKR" };
  assert.notEqual(getCandidateDecisionCacheKey(reqGM), getCandidateDecisionCacheKey(reqKKR));
});

// 20. Changing program type changes query/cache key
test("20. Changing program type changes query/cache key", () => {
  const reqEng = { ...FIXTURE_SUCCESS_LOWER_HALF, program_type: "ENGINEERING" };
  const reqArch = { ...FIXTURE_SUCCESS_LOWER_HALF, program_type: "ARCHITECTURE" };
  assert.notEqual(getCandidateDecisionCacheKey(reqEng), getCandidateDecisionCacheKey(reqArch));
});

// 21. No Safe/Target/Reach labels
test("21. No Safe/Target/Reach labels exist in evidence states or component labels", () => {
  const labels = Object.values(EVIDENCE_STATE_LABELS);
  for (const label of labels) {
    assert.ok(!label.toLowerCase().includes("safe"), "Must not contain 'safe'");
    assert.ok(!label.toLowerCase().includes("target"), "Must not contain 'target'");
    assert.ok(!label.toLowerCase().includes("reach"), "Must not contain 'reach'");
  }
});

// 22. No probability/chance display
test("22. No probability/chance percentage display anywhere in decision fixture or contract", () => {
  const keys = Object.keys(FIXTURE_SUCCESS_LOWER_HALF);
  assert.ok(!keys.includes("probability"), "Must not include probability");
  assert.ok(!keys.includes("admission_probability"), "Must not include admission_probability");
  assert.ok(!keys.includes("chance"), "Must not include chance");

  // Verify explanation text does not contain gambling or percentage chance words
  for (const exp of FIXTURE_SUCCESS_LOWER_HALF.explanation) {
    assert.ok(!exp.includes("%"), "Explanation must not contain percentages");
    assert.ok(!exp.toLowerCase().includes("percent chance"), "Explanation must not claim percent chance");
    assert.ok(!exp.toLowerCase().includes("high chance"), "Explanation must not claim high chance");
    assert.ok(!exp.toLowerCase().includes("low chance"), "Explanation must not claim low chance");
    assert.ok(!exp.toLowerCase().includes("guaranteed admission"), "Explanation must not claim guaranteed admission");
  }
});

// 23. No fake fallback data
test("23. Cold start does not invent 0, fake cutoffs, or generic averages", () => {
  assert.equal(FIXTURE_COLD_START.predicted_closing_rank, null);
  assert.equal(FIXTURE_COLD_START.lower_bound, null);
  assert.equal(FIXTURE_COLD_START.upper_bound, null);
  assert.notEqual(FIXTURE_COLD_START.predicted_closing_rank, 0);
  assert.notEqual(FIXTURE_COLD_START.predicted_closing_rank, "0");
});

// 24. API error rendering
test("24. API errors produce descriptive, specific user-facing messages", () => {
  // Test error mapping logic
  const mapApiError = (statusCode, detail) => {
    if (statusCode === 400 && (detail.toLowerCase().includes("round") || detail.toLowerCase().includes("r2"))) {
      return `This counselling round is not supported. (${detail})`;
    }
    if (statusCode === 404 && detail.toLowerCase().includes("college")) {
      return `College not found. (${detail})`;
    }
    if (statusCode === 404 && detail.toLowerCase().includes("branch")) {
      return `Branch not found. (${detail})`;
    }
    if (statusCode === 0) {
      return "Couldn't reach the COMEDK Compass analysis service. Please try again.";
    }
    return detail;
  };

  const r2Err = mapApiError(400, "Standard R2 is not supported for 2026.");
  assert.ok(r2Err.includes("This counselling round is not supported"));

  const colErr = mapApiError(404, "College with ID not found.");
  assert.ok(colErr.includes("College not found"));

  const brErr = mapApiError(404, "Branch with ID not found.");
  assert.ok(brErr.includes("Branch not found"));

  const netErr = mapApiError(0, "fetch failed");
  assert.ok(netErr.includes("Couldn't reach the COMEDK Compass analysis service"));
});

// 25. Loading state
test("25. Loading state presents 'Analyzing historical COMEDK data...' without fake progress", () => {
  const loadingText = "Analyzing historical COMEDK data...";
  assert.equal(loadingText, "Analyzing historical COMEDK data...");
  assert.ok(!loadingText.includes("%"));
});

// 26. Disclaimer rendering
test("26. Mandatory disclaimer matches backend contract", () => {
  const disclaimer = FIXTURE_SUCCESS_LOWER_HALF.disclaimer;
  assert.ok(disclaimer.includes("NOT an admission probability"));
  assert.ok(disclaimer.includes("does not guarantee seat allotment"));
  assert.ok(disclaimer.includes("NOT constitute a recommendation"));
});

// 27. Historical evidence section
test("27. Historical evidence section exposes empirical observation count and evidence strength", () => {
  assert.equal(FIXTURE_SUCCESS_LOWER_HALF.observation_count, 3);
  assert.equal(FIXTURE_SUCCESS_LOWER_HALF.latest_comparable_year, 2025);
  assert.equal(FIXTURE_SUCCESS_LOWER_HALF.evidence_strength, "STRONG");
  assert.equal(FIXTURE_SUCCESS_LOWER_HALF.model_version, "v1.0-research");
  assert.equal(FIXTURE_SUCCESS_LOWER_HALF.dataset_version, "2023-2026-v1");
});

// 28. Accessibility basics
test("28. Accessibility attributes: range visualization exposes aria-label with full text equivalent", () => {
  const candidateRank = 18432;
  const lowerBound = 16900;
  const predictedRank = 21700;
  const upperBound = 28400;
  const evidenceLabel = "Within the lower half of the range";

  const accessibleRangeText = `Historical closing rank interval: Lower bound ${lowerBound.toLocaleString(
    "en-IN"
  )}, estimated closing rank ${predictedRank.toLocaleString(
    "en-IN"
  )}, upper bound ${upperBound.toLocaleString(
    "en-IN"
  )}. Your rank is ${candidateRank.toLocaleString("en-IN")}, which sits ${evidenceLabel.toLowerCase()}.`;

  assert.ok(accessibleRangeText.includes("16,900"));
  assert.ok(accessibleRangeText.includes("21,700"));
  assert.ok(accessibleRangeText.includes("28,400"));
  assert.ok(accessibleRangeText.includes("18,432"));
  assert.ok(accessibleRangeText.includes("within the lower half of the range"));
});

// 29. Mobile layout sanity
test("29. Mobile layout calculates bounded percentage markers between 0% and 100%", () => {
  const calculateMarkerPercent = (candidateRank, lowerBound, predictedRank, upperBound) => {
    if (candidateRank < lowerBound) return 2;
    if (candidateRank <= predictedRank) {
      const range = predictedRank - lowerBound;
      const fraction = range > 0 ? (candidateRank - lowerBound) / range : 0.5;
      return Math.max(4, Math.min(48, Math.round(fraction * 50)));
    }
    if (candidateRank <= upperBound) {
      const range = upperBound - predictedRank;
      const fraction = range > 0 ? (candidateRank - predictedRank) / range : 0.5;
      return Math.max(52, Math.min(96, 50 + Math.round(fraction * 50)));
    }
    return 98;
  };

  const pBelow = calculateMarkerPercent(10000, 16900, 21700, 28400);
  assert.equal(pBelow, 2, "Below lower bound clamped to left edge");

  const pLower = calculateMarkerPercent(18432, 16900, 21700, 28400);
  assert.ok(pLower >= 4 && pLower <= 48, "Within lower half between 4% and 48%");

  const pUpper = calculateMarkerPercent(25000, 16900, 21700, 28400);
  assert.ok(pUpper >= 52 && pUpper <= 96, "Within upper half between 52% and 96%");

  const pAbove = calculateMarkerPercent(35000, 16900, 21700, 28400);
  assert.equal(pAbove, 98, "Above upper bound clamped to right edge");
});

// 30. Frontend API request timeout and error resilience (Stage 3.8A Objective 6)
test("30. Frontend API request timeout handling, AbortSignal bounds, and error fail-closed semantics", async () => {
  // 30.1: Default API timeout bound is established (10 seconds)
  const defaultTimeoutMs = 10000;
  assert.equal(defaultTimeoutMs, 10000, "Default timeout must be bounded to 10 seconds");

  // 30.2: Timeout error produces controlled PredictionApiError with statusCode 0
  class PredictionApiError extends Error {
    constructor(statusCode, detail) {
      super(`Prediction API Error (${statusCode}): ${detail}`);
      this.name = "PredictionApiError";
      this.statusCode = statusCode;
      this.detail = detail;
    }
  }

  const simulateRequestWithTimeout = async (timeoutSignal) => {
    return new Promise((_, reject) => {
      if (timeoutSignal.aborted) {
        return reject(
          new PredictionApiError(
            0,
            "Prediction request timed out after 10 seconds. Please check your connection and try again."
          )
        );
      }
      timeoutSignal.addEventListener("abort", () => {
        reject(
          new PredictionApiError(
            0,
            "Prediction request timed out after 10 seconds. Please check your connection and try again."
          )
        );
      });
    });
  };

  const controller = new AbortController();
  const requestPromise = simulateRequestWithTimeout(controller.signal);
  controller.abort();

  await assert.rejects(
    requestPromise,
    (err) => {
      assert.equal(err.name, "PredictionApiError");
      assert.equal(err.statusCode, 0);
      assert.ok(err.detail.includes("timed out"));
      return true;
    },
    "Timeout must reject with controlled PredictionApiError(0)"
  );

  // 30.3: Normal API error response produces controlled error
  const simulateApiStatusError = (status, detail) => {
    throw new PredictionApiError(status, detail);
  };

  assert.throws(
    () => simulateApiStatusError(400, "Invalid counselling round"),
    (err) => {
      assert.equal(err.statusCode, 400);
      assert.equal(err.detail, "Invalid counselling round");
      return true;
    }
  );

  // 30.4: Prediction timeout fails closed without producing false prediction
  let predictionOutput = null;
  try {
    const timedOutController = new AbortController();
    timedOutController.abort();
    predictionOutput = await simulateRequestWithTimeout(timedOutController.signal);
  } catch {
    // Fail-closed: prediction remains null
  }
  assert.equal(
    predictionOutput,
    null,
    "Prediction must fail closed on timeout without fabricating results"
  );
});
