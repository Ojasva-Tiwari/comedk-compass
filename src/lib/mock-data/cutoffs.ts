import type { CutoffRecord } from "./types";
const base = [
  ["39dd12af-12d8-445b-8a5d-66d22792a361", "CSE", [1210, 1460, 1675, 1842]], ["584b3ee8-34dc-4a07-8954-fa92ca4ba192", "CSE", [3150, 3620, 4210, 4721]],
  ["1840e5e2-af59-49be-88e0-563dcb74b9e5", "CSE", [4380, 5010, 5680, 6230]], ["410c3e14-7480-48e8-9e86-2dc0a36cb2c6", "CSE", [8420, 9680, 11240, 12860]],
  ["a6e0188f-8e3c-4cd3-9d7e-89140dc86428", "CSE", [12120, 14980, 17640, 19120]], ["e36a6d28-3c86-4c04-bf1f-1ed38a34769b", "AIML", [14210, 16980, 19760, 22140]],
  ["4533f514-1e54-4a78-a591-9915c3552e27", "CSE", [10420, 12710, 15180, 17240]], ["d16a1563-cf65-4e84-a046-a9d590d669cb", "ISE", [9160, 10830, 12820, 14310]],
] as const;
export const cutoffs: CutoffRecord[] = base.map(([collegeId, branch, rounds]) => ({ collegeId, branch, year: 2025, category: "GM", rounds: [...rounds], source: { source: "Official COMEDK", year: 2025, confidence: "High" } }));
export const rnsitTrends = {
  CSE: [22640, 21180, 20420, 19120, 18480], AIML: [29420, 27610, 25190, 23240, 22160],
  ISE: [26520, 24840, 23110, 21480, 20620], ECE: [38940, 36720, 34510, 32210, 30940],
};
export const trendYears = [2022, 2023, 2024, 2025, 2026];
