import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useMemo, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Building2, Check, ExternalLink, HelpCircle, MapPin, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CollegeLogo } from "@/components/product/brand";
import { PageHeader, Panel, Section } from "@/components/product/page";
import { CANONICAL_COLLEGES, fetchColleges, fetchCutoffs, fetchFees, CollegeOption } from "@/lib/api-client";

interface CompareSearchParams {
  colleges?: string;
}

export const Route = createFileRoute("/compare")({
  validateSearch: (search: Record<string, unknown>): CompareSearchParams => ({
    colleges: typeof search.colleges === "string" ? search.colleges : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Compare COMEDK Colleges — COMEDK Compass" },
      {
        name: "description",
        content: "Compare official COMEDK engineering cutoffs, verified fee schedules, and institution details side by side.",
      },
      { property: "og:title", content: "Compare COMEDK Colleges" },
      { property: "og:description", content: "Side-by-side comparison of verified COMEDK institutions." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Compare,
});

function Compare() {
  const searchParams = Route.useSearch();
  const navigate = Route.useNavigate();

  const { data: collegesList = CANONICAL_COLLEGES } = useQuery({
    queryKey: ["colleges-catalog-compare"],
    queryFn: () => fetchColleges(),
    staleTime: 10 * 60 * 1000,
  });

  const defaultIds = useMemo(() => {
    if (searchParams.colleges) {
      const parsed = searchParams.colleges.split(",").map((s) => s.trim()).filter(Boolean);
      if (parsed.length > 0) return parsed;
    }
    return [
      "39dd12af-12d8-445b-8a5d-66d22792a361", // RVCE
      "584b3ee8-34dc-4a07-8954-fa92ca4ba192", // BMSCE
    ];
  }, [searchParams.colleges]);

  const [ids, setIds] = useState<string[]>(defaultIds);

  const { data: metricsData } = useQuery({
    queryKey: ["compare-metrics-data", ids],
    queryFn: async () => {
      const results: Record<string, { latestCutoff: number | null; annualFee: number | null }> = {};
      await Promise.all(
        ids.map(async (collegeId) => {
          let latestCutoff: number | null = null;
          let annualFee: number | null = null;
          try {
            const cutoffs = await fetchCutoffs({ college_id: collegeId, limit: 1 });
            if (cutoffs.items.length > 0) {
              latestCutoff = cutoffs.items[0].closing_rank;
            }
          } catch {
            // non-fatal
          }
          try {
            const fees = await fetchFees({ college_id: collegeId, limit: 1 });
            if (fees.items.length > 0) {
              annualFee = fees.items[0].total_fee || fees.items[0].tuition_fee;
            }
          } catch {
            // non-fatal
          }
          results[collegeId] = { latestCutoff, annualFee };
        })
      );
      return results;
    },
    enabled: ids.length > 0,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (searchParams.colleges) {
      const parsed = searchParams.colleges.split(",").map((s) => s.trim()).filter(Boolean);
      if (parsed.length > 0) setIds(parsed);
    }
  }, [searchParams.colleges]);

  const selectedColleges = useMemo(() => {
    return ids
      .map((id) => {
        const found = collegesList.find(
          (c) =>
            c.id.toLowerCase() === id.toLowerCase() ||
            c.code.toLowerCase() === id.toLowerCase() ||
            c.shortName.toLowerCase().includes(id.toLowerCase())
        );
        if (found) return found;
        const canonical = CANONICAL_COLLEGES.find((c) => c.id === id || c.code.toLowerCase() === id.toLowerCase());
        return canonical ?? null;
      })
      .filter((c): c is CollegeOption => Boolean(c));
  }, [ids, collegesList]);

  const update = (index: number, newId: string) => {
    const next = [...ids];
    next[index] = newId;
    setIds(next);
    navigate({
      search: { colleges: next.join(",") },
      replace: true,
    });
  };

  const addCollegeSlot = () => {
    const unused = collegesList.find((c) => !ids.includes(c.id));
    if (!unused) return;
    const next = [...ids, unused.id];
    setIds(next);
    navigate({
      search: { colleges: next.join(",") },
      replace: true,
    });
  };

  const removeCollegeSlot = (index: number) => {
    if (ids.length <= 1) return;
    const next = ids.filter((_, i) => i !== index);
    setIds(next);
    navigate({
      search: { colleges: next.join(",") },
      replace: true,
    });
  };

  return (
    <>
      <PageHeader
        eyebrow="Side-by-Side Analysis"
        title="Compare Verified Institutions"
        description="Review official COMEDK codes, campus locations, tuition fees, and latest historical closing cutoffs."
        actions={
          ids.length < 4 ? (
            <Button size="sm" variant="outline" onClick={addCollegeSlot}>
              + Add College
            </Button>
          ) : undefined
        }
      />

      <Section>
        {/* Notice on Factual Policy */}
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-border bg-muted/20 p-4 text-xs leading-relaxed text-muted-foreground">
          <HelpCircle className="size-4 shrink-0 text-primary mt-0.5" />
          <div>
            <strong className="text-foreground">Official Data Transparency Notice:</strong> All metrics displayed below reflect verified COMEDK seat allocation PDFs and regulatory fee circulars. Self-reported placement packages and speculative rankings are excluded.
          </div>
        </div>

        <div className="overflow-x-auto">
          <div className="min-w-[700px]">
            {/* Header Column Selectors */}
            <div
              className="sticky top-16 z-20 grid border-b border-border bg-background py-4"
              style={{
                gridTemplateColumns: `180px repeat(${selectedColleges.length}, minmax(200px, 1fr))`,
              }}
            >
              <div className="self-end px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Institution
              </div>

              {selectedColleges.map((c, i) => (
                <div className="px-3" key={c.id}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <CollegeLogo initials={c.code.slice(0, 2)} className="size-8 text-xs" />
                      <div className="min-w-0">
                        <strong className="block truncate text-sm font-semibold text-foreground">
                          {c.code}
                        </strong>
                        <p className="truncate text-xs text-muted-foreground">{c.location}</p>
                      </div>
                    </div>

                    {selectedColleges.length > 2 && (
                      <button
                        type="button"
                        onClick={() => removeCollegeSlot(i)}
                        className="text-xs text-muted-foreground hover:text-destructive"
                        title="Remove column"
                      >
                        ✕
                      </button>
                    )}
                  </div>

                  <Select value={c.id} onValueChange={(newId) => update(i, newId)}>
                    <SelectTrigger className="mt-3 h-8 text-xs">
                      <SelectValue placeholder={c.shortName} />
                    </SelectTrigger>
                    <SelectContent className="max-h-72">
                      {collegesList.map((x) => (
                        <SelectItem value={x.id} key={x.id} className="text-xs">
                          {x.shortName}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ))}
            </div>

            {/* Comparison Rows */}
            <Panel className="overflow-hidden rounded-t-none">
              {/* Row 1: Official Code */}
              <div
                className="grid border-b border-border text-xs"
                style={{
                  gridTemplateColumns: `180px repeat(${selectedColleges.length}, minmax(200px, 1fr))`,
                }}
              >
                <div className="p-4 font-medium text-muted-foreground">Official Code</div>
                {selectedColleges.map((c) => (
                  <div className="border-l border-border p-4 font-mono font-semibold text-foreground" key={c.id}>
                    {c.code}
                  </div>
                ))}
              </div>

              {/* Row 2: Location */}
              <div
                className="grid border-b border-border text-xs"
                style={{
                  gridTemplateColumns: `180px repeat(${selectedColleges.length}, minmax(200px, 1fr))`,
                }}
              >
                <div className="p-4 font-medium text-muted-foreground">Campus Location</div>
                {selectedColleges.map((c) => (
                  <div className="border-l border-border p-4 text-foreground" key={c.id}>
                    {c.location || "Karnataka"}
                  </div>
                ))}
              </div>

              {/* Row 3: Latest CSE Benchmark Cutoff */}
              <div
                className="grid border-b border-border text-xs"
                style={{
                  gridTemplateColumns: `180px repeat(${selectedColleges.length}, minmax(200px, 1fr))`,
                }}
              >
                <div className="p-4 font-medium text-muted-foreground">
                  Latest Cutoff Rank
                  <span className="block text-[10px] text-muted-foreground">Official Records</span>
                </div>
                {selectedColleges.map((c) => {
                  const m = metricsData?.[c.id];
                  return (
                    <div className="border-l border-border p-4" key={c.id}>
                      {m?.latestCutoff ? (
                        <strong className="font-mono text-sm text-foreground">
                          {m.latestCutoff.toLocaleString("en-IN")}
                        </strong>
                      ) : (
                        <Link to="/cutoffs" className="text-xs text-primary hover:underline">
                          Browse Cutoffs →
                        </Link>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Row 4: Annual Tuition Fee */}
              <div
                className="grid border-b border-border text-xs"
                style={{
                  gridTemplateColumns: `180px repeat(${selectedColleges.length}, minmax(200px, 1fr))`,
                }}
              >
                <div className="p-4 font-medium text-muted-foreground">
                  Annual Tuition Fee
                  <span className="block text-[10px] text-muted-foreground">Official Circular</span>
                </div>
                {selectedColleges.map((c) => {
                  const m = metricsData?.[c.id];
                  return (
                    <div className="border-l border-border p-4 font-mono text-sm font-semibold text-foreground" key={c.id}>
                      {m?.annualFee ? `₹${(m.annualFee / 100000).toFixed(2)}L` : "Official Schedule"}
                    </div>
                  );
                })}
              </div>

              {/* Row 5: Actions */}
              <div
                className="grid text-xs"
                style={{
                  gridTemplateColumns: `180px repeat(${selectedColleges.length}, minmax(200px, 1fr))`,
                }}
              >
                <div className="p-4 font-medium text-muted-foreground">Candidate Actions</div>
                {selectedColleges.map((c) => (
                  <div className="border-l border-border p-4 flex flex-col gap-2" key={c.id}>
                    <Button asChild size="sm" variant="outline" className="w-full justify-start text-xs gap-1.5">
                      <Link to="/predictor" search={{ collegeId: c.id, round: "R1", category: "GM" }}>
                        <Sparkles className="size-3 text-primary" /> Evaluate in Predictor
                      </Link>
                    </Button>
                    <Button asChild size="sm" variant="ghost" className="w-full justify-start text-xs gap-1.5">
                      <Link to="/colleges/$slug" params={{ slug: c.id }}>
                        <ExternalLink className="size-3" /> Full Profile
                      </Link>
                    </Button>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      </Section>
    </>
  );
}
