export type Chance = "Strong" | "Possible" | "Reach" | "Low";
export type SourceKind = "Official COMEDK" | "Verified Student" | "Historical Data" | "Institution Source";

export interface SourceMeta { source: SourceKind; year: number; confidence?: "High" | "Moderate" | "Limited"; verifiedCount?: number; }
export interface Branch { code: string; name: string; }
export interface CutoffRecord { collegeId: string; branch: string; year: number; category: string; rounds: [number, number, number, number]; source: SourceMeta; }
export interface FeeRecord { collegeId: string; tuition: number; hostel: number; other: number; source: SourceMeta; }
export interface PlacementRecord { collegeId: string; median: number; average: number; highest: number; source: SourceMeta; }
export interface ProbabilityRecord { collegeId: string; branch: string; rank: number; rounds: [number, number, number, number]; confidence: "High" | "Moderate" | "Limited"; }
export interface StudentSubmission { id: string; collegeId: string; branch: string; batch: number; feeRange: [number, number]; placementMedian: number; confirmedBy: number; note: string; }
export interface College { id: string; code?: string; slug: string; shortName: string; name: string; location: string; type: "Private" | "Autonomous"; established: number; branches: string[]; branchCutoffs?: Record<string, number>; latestCutoff?: number; annualFee: number; hostelFee: number; medianPackage: number; roi: number; chance: Chance; verified: boolean; accent: string; }
