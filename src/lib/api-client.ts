/**
 * COMEDK Compass — Prediction Engine Client (Stage 3.5)
 *
 * Connects the frontend to the FastAPI Prediction Engine (Stage 3.4):
 * - Calls POST /api/v1/predictor/chances (or GET /api/v1/predictor/chances)
 * - Exposes "Estimated Closing Rank" (never admission probability or guaranteed rank)
 * - Strict candidate eligibility semantics: candidate_rank <= predicted_closing_rank
 * - Strictly read-only; handles 400, 404, 422, cold-starts, and network errors gracefully
 */

export type EvidenceStrength =
  | "STRONG"
  | "MODERATE"
  | "SPARSE"
  | "INSUFFICIENT_EVIDENCE";

export type ColdStartReason =
  | "UNKNOWN_COLLEGE"
  | "UNKNOWN_BRANCH"
  | "UNKNOWN_COMBINATION"
  | "UNKNOWN_CATEGORY"
  | "NO_HISTORICAL_RECORDS"
  | "NONE";

export type IntervalType =
  | "ASYMMETRIC_RELATIVE_EMPIRICAL"
  | "SYMMETRIC_RELATIVE"
  | "ADDITIVE_EMPIRICAL"
  | "VOLATILITY_ADAPTIVE_WIDE";

export type CandidateEvidenceState =
  | "NUMERICALLY_BELOW_LOWER_BOUND"
  | "WITHIN_LOWER_HALF"
  | "WITHIN_UPPER_HALF"
  | "NUMERICALLY_ABOVE_UPPER_BOUND"
  | "INSUFFICIENT_EVIDENCE";

export interface CandidateDecisionRequest {
  candidate_rank: number;
  college_id: string;
  branch_id: string;
  academic_year: number;
  round: string; // "R1" | "R3" | "R4"
  category: "GM" | "KKR";
  program_type: "ENGINEERING" | "ARCHITECTURE";
  model_type?: string;
}

export interface CandidateDecisionResponse {
  decision_id: string;
  candidate_rank: number;
  academic_year: number;
  college_id: string;
  branch_id: string;
  category: "GM" | "KKR";
  round: string;
  program_type: "ENGINEERING" | "ARCHITECTURE";
  prediction_status: "SUCCESS" | "INSUFFICIENT_EVIDENCE";
  predicted_closing_rank: number | null;
  lower_bound: number | null;
  upper_bound: number | null;
  prediction_interval: PredictionInterval | null;
  evidence_state: CandidateEvidenceState;
  explanation: string[];
  evidence_strength: EvidenceStrength;
  observation_count: number;
  latest_comparable_year: number | null;
  cold_start_reason: ColdStartReason;
  model_name: string;
  model_version: string;
  dataset_version: string;
  feature_definition_version: string;
  generated_at: string;
  evidence_trail: EvidenceItem[];
  disclaimer: string;
}

export interface PredictionInterval {
  lower_bound: number;
  upper_bound: number;
  interval_type: IntervalType;
  target_coverage: number;
  interval_width: number;
  relative_width: number;
}

export interface EvidenceItem {
  source_type: string;
  academic_year?: number;
  round_code?: string;
  closing_rank: number;
  weight?: number;
  description: string;
}

export interface PredictionRequest {
  college_id: string;
  branch_id: string;
  academic_year: number;
  round: string; // "R1" | "R3" | "R4"
  category: "GM" | "KKR";
  program_type: "ENGINEERING" | "ARCHITECTURE";
  model_type?: string;
}

export interface PredictionResult {
  prediction_id: string;
  academic_year: number;
  college_id: string;
  branch_id: string;
  category: "GM" | "KKR";
  round: string;
  program_type: "ENGINEERING" | "ARCHITECTURE";
  status: "SUCCESS" | "INSUFFICIENT_EVIDENCE";
  predicted_closing_rank: number | null;
  prediction_interval: PredictionInterval | null;
  lower_bound: number | null;
  upper_bound: number | null;
  evidence_strength: EvidenceStrength;
  observation_count: number;
  latest_comparable_year: number | null;
  cold_start_reason: ColdStartReason;
  model_name: string;
  model_version: string;
  dataset_version: string;
  feature_definition_version: string;
  generated_at: string;
  input_parameters: Record<string, unknown>;
  evidence_trail: EvidenceItem[];
  explanation: string[];
  disclaimer: string;
}

export interface CollegeOption {
  id: string;
  code: string;
  name: string;
  shortName: string;
  location: string;
}

export interface BranchOption {
  id: string;
  code: string;
  name: string;
  program_type: "ENGINEERING" | "ARCHITECTURE";
}

export class PredictionApiError extends Error {
  statusCode: number;
  detail: string;

  constructor(statusCode: number, detail: string) {
    super(`Prediction API Error (${statusCode}): ${detail}`);
    this.name = "PredictionApiError";
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

// Canonical database verified seed list (used for instant loading and fallback)
export const CANONICAL_COLLEGES: CollegeOption[] = [
  {
    id: "39dd12af-12d8-445b-8a5d-66d22792a361",
    code: "E095",
    name: "R V College of Engineering-mysore Road, Bengaluru",
    shortName: "RVCE (RV College of Engineering)",
    location: "Bengaluru",
  },
  {
    id: "584b3ee8-34dc-4a07-8954-fa92ca4ba192",
    code: "E027",
    name: "BMS College of Engineering-basavanagudi, Bengaluru",
    shortName: "BMSCE (BMS College of Engineering)",
    location: "Bengaluru",
  },
  {
    id: "1840e5e2-af59-49be-88e0-563dcb74b9e5",
    code: "E077",
    name: "M.S. Ramaiah Institute of Technology-msr Nagar, Bengaluru",
    shortName: "MSRIT (Ramaiah Institute of Technology)",
    location: "Bengaluru",
  },
  {
    id: "410c3e14-7480-48e8-9e86-2dc0a36cb2c6",
    code: "E040",
    name: "Dayananda Sagar College of Engineering-kumaraswamy Layout, Bengaluru",
    shortName: "DSCE (Dayananda Sagar College of Engg)",
    location: "Bengaluru",
  },
  {
    id: "a6e0188f-8e3c-4cd3-9d7e-89140dc86428",
    code: "E104",
    name: "RNS Institute of Technology-r R Nagar Post, Bengaluru",
    shortName: "RNSIT (RNS Institute of Technology)",
    location: "Bengaluru",
  },
  {
    id: "e36a6d28-3c86-4c04-bf1f-1ed38a34769b",
    code: "E028",
    name: "BMS Institute of Technology & Management-yelahanka, Bengaluru",
    shortName: "BMSIT (BMS Institute of Technology)",
    location: "Bengaluru",
  },
  {
    id: "d16a1563-cf65-4e84-a046-a9d590d669cb",
    code: "E058",
    name: "Sri Jayachamarajendra College of Engineering (JSSSTU)-manasagangothri, Mysuru",
    shortName: "SJCE / JSSSTU Mysuru",
    location: "Mysuru",
  },
  {
    id: "e94e927d-acf2-49d9-95ea-6e7eec465b9a",
    code: "E147",
    name: "Vidyavardhaka College of Engineering-gokulam, Mysuru",
    shortName: "VVCE Mysuru",
    location: "Mysuru",
  },
  {
    id: "10ff2bc6-80ba-4808-9fd2-ec0c16e01ea6",
    code: "E001",
    name: "Acharya Institute of Technology- Soladevanahalli, Bengaluru",
    shortName: "AIT (Acharya Institute of Technology)",
    location: "Bengaluru",
  },
  {
    id: "3fa36fcd-3f95-4f59-bb37-4a7235d75533",
    code: "E012",
    name: "ATRIA Institute of Technology-hebbal, Bengaluru",
    shortName: "Atria Institute of Technology",
    location: "Bengaluru",
  },
  {
    id: "ffe18689-c698-4562-8bcd-38dbc1b8e769",
    code: "E084",
    name: "Nagarjuna College of Engineering & Technology-devanahalli Bengaluru",
    shortName: "NCET Bengaluru",
    location: "Bengaluru",
  },
  {
    id: "6b036aab-2d77-45b5-a7d3-8a6123f6eeb6",
    code: "E176",
    name: "R V College of Architecture-banashankari 6th Stage, Bengaluru",
    shortName: "RVCA (RV College of Architecture)",
    location: "Bengaluru",
  },
];

export const CANONICAL_BRANCHES: BranchOption[] = [
  {
    id: "f764a302-c117-41bb-bbd3-e2b998012107",
    code: "CS",
    name: "Computer Science & Engineering",
    program_type: "ENGINEERING",
  },
  {
    id: "63f10ebd-9557-4328-bd04-76696ddf10f1",
    code: "AI",
    name: "Artificial Intelligence & Machine Learning",
    program_type: "ENGINEERING",
  },
  {
    id: "28cbc102-cb2a-4934-b1bd-dea4fd315ebe",
    code: "AD",
    name: "Artificial Intelligence & Data Science",
    program_type: "ENGINEERING",
  },
  {
    id: "78ff2488-15f0-4ff1-a009-cb3ce4cc1513",
    code: "IS",
    name: "Information Science & Engineering",
    program_type: "ENGINEERING",
  },
  {
    id: "fc2f1466-ce5a-4281-a0af-305e5523d909",
    code: "EC",
    name: "Electronics & Communication Engineering",
    program_type: "ENGINEERING",
  },
  {
    id: "a60d7b64-3de5-4f12-9008-f09eca0afe7e",
    code: "EE",
    name: "Electrical & Electronics Engineering",
    program_type: "ENGINEERING",
  },
  {
    id: "a252bd81-cd31-4927-90ae-0d29f0833d49",
    code: "ME",
    name: "Mechanical Engineering",
    program_type: "ENGINEERING",
  },
  {
    id: "070f2138-4972-481f-8d12-53db79722d18",
    code: "AE",
    name: "Aeronautical Engineering",
    program_type: "ENGINEERING",
  },
  {
    id: "ffe8c4e3-01c2-4bc5-899e-20653cc8269a",
    code: "CV",
    name: "Civil Engineering",
    program_type: "ENGINEERING",
  },
  {
    id: "3f57b573-3b8f-4d0e-ae54-50b1ae2bdced",
    code: "AT",
    name: "Bachelor of Architecture (B.Arch)",
    program_type: "ARCHITECTURE",
  },
];

export const DEFAULT_API_TIMEOUT_MS = 10000;

/**
 * Creates an AbortSignal that aborts after timeoutMs.
 * Uses native AbortSignal.timeout when available, falling back to AbortController.
 */
export function createTimeoutSignal(timeoutMs: number = DEFAULT_API_TIMEOUT_MS): AbortSignal {
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    return AbortSignal.timeout(timeoutMs);
  }
  const controller = new AbortController();
  setTimeout(() => controller.abort(new Error("TimeoutError")), timeoutMs);
  return controller.signal;
}

const RAW_API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  "http://localhost:8000/api/v1";
const API_BASE_URL = RAW_API_BASE_URL.endsWith("/api/v1")
  ? RAW_API_BASE_URL
  : `${RAW_API_BASE_URL.replace(/\/+$/, "")}/api/v1`;

/**
 * Predict COMEDK Closing Rank via POST /api/v1/predictor/chances.
 */
export async function predictClosingRank(
  request: PredictionRequest,
  signal?: AbortSignal
): Promise<PredictionResult> {
  const url = `${API_BASE_URL}/predictor/chances`;
  const timeoutSignal = signal || createTimeoutSignal(DEFAULT_API_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(request),
      signal: timeoutSignal,
    });
  } catch (err: unknown) {
    const isTimeout =
      (err instanceof Error && (err.name === "TimeoutError" || err.name === "AbortError")) ||
      (typeof DOMException !== "undefined" && err instanceof DOMException && err.name === "TimeoutError");
    if (isTimeout) {
      throw new PredictionApiError(
        0,
        "Prediction request timed out after 10 seconds. Please check your connection and try again."
      );
    }
    const message =
      err instanceof Error ? err.message : "Failed to connect to Prediction API server.";
    throw new PredictionApiError(
      0,
      `Network connection failed: ${message}. Ensure COMEDK Compass backend is running at ${API_BASE_URL}.`
    );
  }

  if (!response.ok) {
    let detail = `Server returned status ${response.status}`;
    try {
      const errJson = await response.json();
      if (typeof errJson?.detail === "string") {
        detail = errJson.detail;
      } else if (Array.isArray(errJson?.detail)) {
        detail = errJson.detail.map((e: { msg?: string }) => e.msg ?? "").join("; ");
      }
    } catch {
      // Use fallback status text if body is not JSON
      detail = response.statusText || detail;
    }

    if (response.status === 400) {
      throw new PredictionApiError(400, detail);
    } else if (response.status === 404) {
      throw new PredictionApiError(404, detail);
    } else if (response.status === 422) {
      throw new PredictionApiError(422, `Validation error: ${detail}`);
    } else {
      throw new PredictionApiError(response.status, detail);
    }
  }

  return response.json() as Promise<PredictionResult>;
}

/**
 * Evaluate Candidate Rank Decision Layer via POST /api/v1/predictor/decision.
 * Evaluates candidate rank descriptively against the historical prediction interval.
 */
export async function evaluateCandidateDecision(
  request: CandidateDecisionRequest,
  signal?: AbortSignal
): Promise<CandidateDecisionResponse> {
  const url = `${API_BASE_URL}/predictor/decision`;
  const timeoutSignal = signal || createTimeoutSignal(DEFAULT_API_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(request),
      signal: timeoutSignal,
    });
  } catch (err: unknown) {
    const isTimeout =
      (err instanceof Error && (err.name === "TimeoutError" || err.name === "AbortError")) ||
      (typeof DOMException !== "undefined" && err instanceof DOMException && err.name === "TimeoutError");
    if (isTimeout) {
      throw new PredictionApiError(
        0,
        "Candidate decision analysis timed out after 10 seconds. Please try again."
      );
    }
    const message =
      err instanceof Error ? err.message : "Failed to connect to Prediction API server.";
    throw new PredictionApiError(
      0,
      `Couldn't reach the COMEDK Compass analysis service. Please try again. (${message})`
    );
  }

  if (!response.ok) {
    let detail = `Server returned status ${response.status}`;
    try {
      const errJson = await response.json();
      if (typeof errJson?.detail === "string") {
        detail = errJson.detail;
      } else if (Array.isArray(errJson?.detail)) {
        detail = errJson.detail.map((e: { msg?: string }) => e.msg ?? "").join("; ");
      }
    } catch {
      detail = response.statusText || detail;
    }

    if (response.status === 400) {
      const isRoundErr = detail.toLowerCase().includes("round") || detail.toLowerCase().includes("r2");
      const msg = isRoundErr
        ? `This counselling round is not supported. (${detail})`
        : detail;
      throw new PredictionApiError(400, msg);
    } else if (response.status === 404) {
      let msg = detail;
      if (detail.toLowerCase().includes("college")) {
        msg = `College not found. (${detail})`;
      } else if (detail.toLowerCase().includes("branch")) {
        msg = `Branch not found. (${detail})`;
      }
      throw new PredictionApiError(404, msg);
    } else if (response.status === 422) {
      throw new PredictionApiError(422, `Validation error: ${detail}`);
    } else {
      throw new PredictionApiError(response.status, detail);
    }
  }

  return response.json() as Promise<CandidateDecisionResponse>;
}

/**
 * Fetch colleges list from backend with fallback to canonical seed list.
 */
export async function fetchColleges(query?: string, signal?: AbortSignal): Promise<CollegeOption[]> {
  try {
    const params = new URLSearchParams({ limit: "200" });
    if (query) params.set("query", query);
    const timeoutSignal = signal || createTimeoutSignal(DEFAULT_API_TIMEOUT_MS);
    const response = await fetch(`${API_BASE_URL}/colleges?${params.toString()}`, {
      signal: timeoutSignal,
    });
    if (response.ok) {
      const data = await response.json();
      if (Array.isArray(data?.items) && data.items.length > 0) {
        return data.items.map((c: { id: string; code: string; name: string; location: string }) => ({
          id: c.id,
          code: c.code,
          name: c.name,
          shortName: `${c.code}: ${c.name.split("-")[0]?.trim() || c.name}`,
          location: c.location,
        }));
      }
    }
  } catch {
    // Graceful fallback to static verified canonical list
  }

  if (!query) return CANONICAL_COLLEGES;
  const q = query.toLowerCase();
  return CANONICAL_COLLEGES.filter(
    (c) =>
      c.name.toLowerCase().includes(q) ||
      c.code.toLowerCase().includes(q) ||
      c.shortName.toLowerCase().includes(q)
  );
}

/**
 * Fetch branches list from backend with fallback to canonical seed list.
 */
export async function fetchBranches(
  programType: "ENGINEERING" | "ARCHITECTURE" = "ENGINEERING",
  signal?: AbortSignal
): Promise<BranchOption[]> {
  try {
    const params = new URLSearchParams({
      limit: "200",
      program_type: programType,
      is_canonical: "true",
    });
    const timeoutSignal = signal || createTimeoutSignal(DEFAULT_API_TIMEOUT_MS);
    const response = await fetch(`${API_BASE_URL}/branches?${params.toString()}`, {
      signal: timeoutSignal,
    });
    if (response.ok) {
      const data = await response.json();
      if (Array.isArray(data?.items) && data.items.length > 0) {
        return data.items.map((b: { id: string; code: string; name: string; program_type: "ENGINEERING" | "ARCHITECTURE" }) => ({
          id: b.id,
          code: b.code,
          name: b.name,
          program_type: b.program_type,
        }));
      }
    }
  } catch {
    // Graceful fallback to static verified canonical list
  }

  return CANONICAL_BRANCHES.filter((b) => b.program_type === programType);
}

export interface CutoffRecordItem {
  id: string;
  college_id: string;
  branch_id: string;
  category_id: string;
  round_id: string;
  source_version_id: string;
  academic_year: number;
  opening_rank: number | null;
  closing_rank: number;
  page_number?: number | null;
  row_identifier?: string | null;
  status: string;
  created_at: string;
}

export interface PaginatedCutoffsResponse {
  items: CutoffRecordItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface CutoffFilters {
  college_id?: string;
  branch_id?: string;
  category_code?: string;
  round_code?: string;
  academic_year?: number;
  institution_type?: string;
  program_type?: string;
  include_special_rounds?: boolean;
  limit?: number;
  offset?: number;
}

export async function fetchCutoffs(
  filters: CutoffFilters = {},
  signal?: AbortSignal
): Promise<PaginatedCutoffsResponse> {
  const params = new URLSearchParams();
  if (filters.college_id) params.set("college_id", filters.college_id);
  if (filters.branch_id) params.set("branch_id", filters.branch_id);
  if (filters.category_code) params.set("category_code", filters.category_code);
  if (filters.round_code && filters.round_code !== "ALL") params.set("round_code", filters.round_code);
  if (filters.academic_year) params.set("academic_year", String(filters.academic_year));
  if (filters.program_type) params.set("program_type", filters.program_type);
  if (filters.institution_type) params.set("institution_type", filters.institution_type);
  if (filters.include_special_rounds) params.set("include_special_rounds", "true");
  params.set("limit", String(filters.limit ?? 50));
  params.set("offset", String(filters.offset ?? 0));

  const timeoutSignal = signal || createTimeoutSignal(DEFAULT_API_TIMEOUT_MS);
  const response = await fetch(`${API_BASE_URL}/cutoffs?${params.toString()}`, {
    signal: timeoutSignal,
  });

  if (!response.ok) {
    throw new Error(`Cutoffs API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export interface CoverageSummary {
  years_available: number[];
  total_records: number;
  published_records: number;
  superseded_records: number;
  records_per_year: Record<string, number>;
  total_records_per_year: Record<string, number>;
  records_per_round: Record<string, Record<string, number>>;
  records_per_category: Record<string, number>;
  records_per_program_type: Record<string, number>;
  colleges_per_year: Record<string, number>;
  branches_per_year: Record<string, number>;
  observation_depth_counts: Record<string, number>;
}

export async function fetchAnalyticsCoverage(
  signal?: AbortSignal
): Promise<CoverageSummary> {
  const timeoutSignal = signal || createTimeoutSignal(DEFAULT_API_TIMEOUT_MS);
  const response = await fetch(`${API_BASE_URL}/analytics/coverage`, {
    signal: timeoutSignal,
  });
  if (!response.ok) {
    throw new Error(`Coverage API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export interface RoundProgressionMetric {
  academic_year: number;
  from_round: string;
  to_round: string;
  program_type: string;
  category: string;
  count: number;
  mean_expansion: number;
  median_expansion: number;
  min_expansion: number;
  max_expansion: number;
}

export async function fetchAnalyticsProgression(
  params?: { academic_year?: number; category?: string; program_type?: string },
  signal?: AbortSignal
): Promise<RoundProgressionMetric[]> {
  const query = new URLSearchParams();
  if (params?.academic_year) query.set("academic_year", String(params.academic_year));
  if (params?.category) query.set("category", params.category);
  if (params?.program_type) query.set("program_type", params.program_type);

  const timeoutSignal = signal || createTimeoutSignal(DEFAULT_API_TIMEOUT_MS);
  const response = await fetch(`${API_BASE_URL}/analytics/progression?${query.toString()}`, {
    signal: timeoutSignal,
  });
  if (!response.ok) {
    throw new Error(`Progression API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export interface PaginatedCollegesResponse {
  items: Array<{
    id: string;
    code: string;
    name: string;
    original_name: string;
    location: string | null;
    institution_type: string;
  }>;
  total: number;
  limit: number;
  offset: number;
}

export async function fetchCollegesPaginated(
  params: { query?: string; location?: string; branch?: string; institution_type?: string; rank?: number; limit?: number; offset?: number } = {},
  signal?: AbortSignal
): Promise<PaginatedCollegesResponse> {
  const q = new URLSearchParams();
  if (params.query) q.set("query", params.query);
  if (params.location && params.location !== "All") q.set("location", params.location);
  if (params.institution_type && params.institution_type !== "ALL") q.set("institution_type", params.institution_type);
  if (params.rank) q.set("rank", String(params.rank));
  q.set("limit", String(params.limit ?? 50));
  q.set("offset", String(params.offset ?? 0));

  const timeoutSignal = signal || createTimeoutSignal(DEFAULT_API_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}/colleges?${q.toString()}`, {
      signal: timeoutSignal,
    });
    if (response.ok) {
      return await response.json();
    }
  } catch {
    // Graceful fallback to static verified canonical list
  }

  // Fallback filtering using the more detailed mock data
  const { colleges: mockColleges } = await import("./mock-data/colleges.js");
  
  let filtered = [...mockColleges];
  
  if (params.query) {
    const query = params.query.toLowerCase();
    filtered = filtered.filter(
      (c) =>
        c.name.toLowerCase().includes(query) ||
        c.code.toLowerCase().includes(query) ||
        c.shortName.toLowerCase().includes(query)
    );
  }
  
  if (params.location && params.location !== "All") {
    filtered = filtered.filter((c) => c.location.toLowerCase().includes(params.location!.toLowerCase()));
  }

  if (params.branch && params.branch !== "All") {
    filtered = filtered.filter((c) => c.branches?.includes(params.branch!));
  }

  if (params.rank && params.rank > 0) {
    // Rank cutoff logic using branchCutoffs
    filtered = filtered.filter((c) => {
      if (!c.branchCutoffs) return false;
      
      if (params.branch && params.branch !== "All") {
        // If a specific branch is selected, use its cutoff
        const branchCutoff = c.branchCutoffs[params.branch];
        return branchCutoff !== undefined && params.rank! <= branchCutoff;
      } else {
        // If no branch is selected ("All"), candidate is eligible if their rank is <= the highest cutoff across any branch
        const maxCutoff = Math.max(...Object.values(c.branchCutoffs));
        return params.rank! <= maxCutoff;
      }
    });
  }

  const offset = params.offset ?? 0;
  const limit = params.limit ?? 50;
  const paginated = filtered.slice(offset, offset + limit);

  return {
    items: paginated.map((c) => ({
      id: c.id,
      code: c.code,
      name: c.name,
      original_name: c.name,
      location: c.location,
      institution_type: c.type || "Private",
    })),
    total: filtered.length,
    limit,
    offset,
  };
}

export interface CollegeDetailResponse {
  id: string;
  code: string;
  name: string;
  original_name: string;
  location: string | null;
  institution_type: string;
  aliases: Array<{ id: string; alias_name: string; alias_type: string }>;
}

export async function fetchCollegeById(
  id: string,
  signal?: AbortSignal
): Promise<CollegeDetailResponse> {
  const timeoutSignal = signal || createTimeoutSignal(DEFAULT_API_TIMEOUT_MS);
  const response = await fetch(`${API_BASE_URL}/colleges/${id}`, {
    signal: timeoutSignal,
  });
  if (!response.ok) {
    throw new Error(`College API error (${response.status}): ${response.statusText}`);
  }
  return response.json();
}

export interface FeeItem {
  id: string;
  college_id: string;
  branch_id: string;
  academic_year: number;
  total_fee: number;
  tuition_fee: number;
  other_fee: number;
  currency: string;
  status: string;
}

export async function fetchFees(
  params: { college_id?: string; branch_id?: string; academic_year?: number; limit?: number; offset?: number } = {},
  signal?: AbortSignal
): Promise<{ items: FeeItem[]; total: number; limit: number; offset: number }> {
  const q = new URLSearchParams();
  if (params.college_id) q.set("college_id", params.college_id);
  if (params.branch_id) q.set("branch_id", params.branch_id);
  if (params.academic_year) q.set("academic_year", String(params.academic_year));
  q.set("limit", String(params.limit ?? 50));
  q.set("offset", String(params.offset ?? 0));

  const timeoutSignal = signal || createTimeoutSignal(DEFAULT_API_TIMEOUT_MS);
  const response = await fetch(`${API_BASE_URL}/fees?${q.toString()}`, {
    signal: timeoutSignal,
  });
  if (!response.ok) {
    throw new Error(`Fees API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export const CANONICAL_ROUND_NAMES: Record<string, { code: string; name: string }> = {
  '78f87192-5386-4df6-a54b-e5e57fb712d8': { code: 'MOCK', name: 'Mock Round' },
  'ff3c19b5-027b-4449-897c-ef8ae4ae5af8': { code: 'R1', name: 'Round 1' },
  '38004d93-2b40-4dec-bb90-edafb172cb53': { code: 'R3', name: 'Round 3' },
  '78c58b8f-b542-4bd1-864a-e40f97b836dd': { code: 'R4', name: 'Round 4' },
  'd1642b1f-cb0c-4cfa-9427-ec536a50a9ff': { code: 'KKR_SPECIAL', name: 'Round 2 KKR Special' },
  '2b4697cc-7a1f-4792-a6a1-5651fd3d804a': { code: 'KKR_SPECIAL', name: 'Round 2 KKR Special' },
  '39549ee6-e728-4cb6-b4a6-ca9a497cb531': { code: 'MOCK', name: 'Mock Round' },
  '196e6bd1-3882-4ad9-ade9-1e48261d7136': { code: 'R1', name: 'Round 1' },
  'fb8806ed-1882-446f-aa6e-ef977d0a1301': { code: 'R3', name: 'Round 3' },
  '96ff6480-2d9a-418b-b10e-852f2a843cf3': { code: 'R4', name: 'Round 4' },
  '921b4ecd-dc98-4a19-8839-19eaa9dcb1cc': { code: 'MOCK', name: 'Mock Round' },
  'c3ff3c33-d177-40b8-8c29-1e8c53fee5f2': { code: 'R1', name: 'Round 1' },
  '8df78fb6-cb22-403a-a692-055eba716c71': { code: 'KKR_SPECIAL', name: 'Round 2 Phase 1 KKR Special' },
  '34c8db58-815f-4c24-b2c0-135006e15f53': { code: 'R2_PHASE2', name: 'Round 2 Phase 2' },
  '3504bb6f-cd2e-409e-a6fe-dcebba30e2bd': { code: 'R3', name: 'Round 3' },
  '17f92449-84b8-4360-97db-b3d2d0f9fca6': { code: 'MOCK', name: 'Mock Round' },
  '9c23bce8-2246-43d7-8525-61880169ac82': { code: 'R1', name: 'Round 1' },
  '19e9d5a2-6c8e-4456-bf9a-7c17907b0772': { code: 'KKR_SPECIAL', name: 'Round 2 Phase 1 KKR Special' },
  '7389bbf3-8b7d-4b70-89d0-a7c93ccbd42c': { code: 'R2_PHASE2', name: 'Round 2 Phase 2' },
  '750afbff-9b68-452f-90c4-9fd13effe1f8': { code: 'R3', name: 'Round 3' },
  '6ed62206-3e7b-43d2-aa4c-e33353a66bc9': { code: 'CONSOLIDATED_FINAL', name: 'Consolidated Final' },
};

export const CANONICAL_CATEGORY_NAMES: Record<string, string> = {
  '9b3e9c4b-a84d-44b8-be1c-e4e98ec0ff19': 'GM',
  '855fe321-1aa3-4d64-8d1b-570b39f5f80f': 'KKR',
  'ef36472c-0902-4d4f-876d-cdb1c3d7624b': 'HKR',
};
