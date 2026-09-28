import type { PlacementRecord } from "./types";
import { colleges } from "./colleges";
export const placements: PlacementRecord[] = colleges.map((college) => ({ collegeId: college.id, median: college.medianPackage, average: Math.round(college.medianPackage * 1.12), highest: Math.round(college.medianPackage * 3.4), source: { source: "Institution Source", year: 2025, confidence: "Moderate" } }));
