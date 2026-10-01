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

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  "http://localhost:8000/api/v1";

/**
 * Predict COMEDK Closing Rank via POST /api/v1/predictor/chances.
 */
export async function predictClosingRank(
  request: PredictionRequest
): Promise<PredictionResult> {
  const url = `${API_BASE_URL}/predictor/chances`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(request),
    });
  } catch (err: unknown) {
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
  request: CandidateDecisionRequest
): Promise<CandidateDecisionResponse> {
  const url = `${API_BASE_URL}/predictor/decision`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(request),
    });
  } catch (err: unknown) {
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
export async function fetchColleges(query?: string): Promise<CollegeOption[]> {
  try {
    const params = new URLSearchParams({ limit: "200" });
    if (query) params.set("query", query);
    const response = await fetch(`${API_BASE_URL}/colleges?${params.toString()}`);
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
  programType: "ENGINEERING" | "ARCHITECTURE" = "ENGINEERING"
): Promise<BranchOption[]> {
  try {
    const params = new URLSearchParams({
      limit: "200",
      program_type: programType,
      is_canonical: "true",
    });
    const response = await fetch(`${API_BASE_URL}/branches?${params.toString()}`);
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
