import type { FeeRecord } from "./types";
import { colleges } from "./colleges";
export const fees: FeeRecord[] = colleges.map((college) => ({ collegeId: college.id, tuition: college.annualFee, hostel: college.hostelFee, other: 28000, source: college.verified ? { source: "Verified Student", year: 2025, confidence: "High", verifiedCount: 8 } : { source: "Institution Source", year: 2025, confidence: "Moderate" } }));
