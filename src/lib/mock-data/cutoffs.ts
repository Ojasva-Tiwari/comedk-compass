import type { CutoffRecord } from "./types";
const base = [
  ["rvce", "CSE", [1210, 1460, 1675, 1842]], ["bmsce", "CSE", [3150, 3620, 4210, 4721]],
  ["msrit", "CSE", [4380, 5010, 5680, 6230]], ["dsce", "CSE", [8420, 9680, 11240, 12860]],
  ["rnsit", "CSE", [12120, 14980, 17640, 19120]], ["bmsit", "AIML", [14210, 16980, 19760, 22140]],
  ["nie", "CSE", [10420, 12710, 15180, 17240]], ["jss", "ISE", [9160, 10830, 12820, 14310]],
] as const;
export const cutoffs: CutoffRecord[] = base.map(([collegeId, branch, rounds]) => ({ collegeId, branch, year: 2025, category: "GM", rounds: [...rounds], source: { source: "Official COMEDK", year: 2025, confidence: "High" } }));
export const rnsitTrends = {
  CSE: [22640, 21180, 20420, 19120, 18480], AIML: [29420, 27610, 25190, 23240, 22160],
  ISE: [26520, 24840, 23110, 21480, 20620], ECE: [38940, 36720, 34510, 32210, 30940],
};
export const trendYears = [2022, 2023, 2024, 2025, 2026];
