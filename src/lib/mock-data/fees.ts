import type { FeeRecord } from "./types";
import { colleges } from "./colleges";
export const fees: FeeRecord[] = colleges.map((college) => ({ collegeId: college.id, tuition: college.annualFee, hostel: college.hostelFee, other: 28000, source: { source: college.verified ? "Verified Student" : "Institution Source", year: 2025, confidence: college.verified ? "High" : "Moderate", verifiedCount: college.verified ? 8 : undefined } }));
