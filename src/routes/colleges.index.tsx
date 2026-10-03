import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Building2, ChevronLeft, ChevronRight, Loader2, MapPin, Search, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState, PageHeader, Panel, Section } from "@/components/product/page";
import { fetchCollegesPaginated } from "@/lib/api-client";

interface CollegesSearchParams {
  rank?: number;
  query?: string;
  location?: string;
  branch?: string;
  page?: number;
}

export const Route = createFileRoute("/colleges/")({
  validateSearch: (search: Record<string, unknown>): CollegesSearchParams => ({
    rank:
      typeof search.rank === "number"
        ? search.rank
        : typeof search.rank === "string"
          ? parseInt(search.rank, 10) || undefined
          : undefined,
    query: typeof search.query === "string" ? search.query : undefined,
    location: typeof search.location === "string" ? search.location : undefined,
    branch: typeof search.branch === "string" ? search.branch : undefined,
    page:
      typeof search.page === "number"
        ? search.page
        : typeof search.page === "string"
          ? parseInt(search.page, 10) || 1
          : 1,
  }),
  head: () => ({
    meta: [
      { title: "COMEDK College Directory — COMEDK Compass" },
      {
        name: "description",
        content: "Explore all 221 verified COMEDK Karnataka institutions with canonical database records.",
      },
      { property: "og:title", content: "COMEDK College Directory" },
      { property: "og:description", content: "Official COMEDK college directory with real database identities." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Colleges,
});

const PAGE_SIZE = 24;

const LOCATIONS = [
  "All",
  "Bengaluru",
  "Mysuru",
  "Belagavi",
  "Mangaluru",
  "Tumakuru",
  "Hubbali",
  "Davangere",
  "Ballari",
  "Kalaburgi",
  "Hassan",
  "Shivamogga",
];

const COMMON_BRANCHES = [
  "All",
  "CSE",
  "AIML",
  "ISE",
  "ECE",
  "EEE",
  "Civil",
  "Mechanical",
];

function Colleges() {
  const searchParams = Route.useSearch();
  const navigate = Route.useNavigate();
  const candidateRank = searchParams.rank && searchParams.rank > 0 ? searchParams.rank : undefined;

  const [searchQuery, setSearchQuery] = useState(searchParams.query || "");
  const [debouncedQuery, setDebouncedQuery] = useState(searchParams.query || "");
  const [selectedLocation, setSelectedLocation] = useState(searchParams.location || "All");
  const [selectedBranch, setSelectedBranch] = useState(searchParams.branch || "CSE");
  const [page, setPage] = useState(searchParams.page || 1);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const offset = (page - 1) * PAGE_SIZE;

  const {
    data: backendData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["colleges-directory", debouncedQuery, selectedLocation, selectedBranch, candidateRank, offset],
    queryFn: () =>
      fetchCollegesPaginated({
        query: debouncedQuery.trim() || undefined,
        location: selectedLocation === "All" ? undefined : selectedLocation,
        branch: selectedBranch === "All" ? undefined : selectedBranch,
        institution_type: "ALL",
        rank: candidateRank,
        limit: PAGE_SIZE,
        offset,
      }),
    staleTime: 60 * 1000,
  });

  const totalColleges = backendData?.total ?? 0;
  const totalPages = Math.ceil(totalColleges / PAGE_SIZE) || 1;
  const collegesList = backendData?.items ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Institution Directory"
        title="Official COMEDK Participating Colleges"
        description="Browse all verified Karnataka engineering and architecture colleges with canonical identities from official COMEDK records."
      />

      <Section>
        {/* Controls: Search, Location Filter, Rank Badge */}
        <div className="mb-6 flex flex-col gap-4 rounded-xl border border-border bg-card p-4 shadow-xs sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-1 flex-wrap items-center gap-3">
            <div className="relative min-w-[260px] flex-1 sm:max-w-md">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by code (e.g. E095), name, or city..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 text-sm"
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">Location:</span>
              <Select
                value={selectedLocation}
                onValueChange={(val) => {
                  setSelectedLocation(val);
                  setPage(1);
                  navigate({ search: (prev) => ({ ...prev, location: val === "All" ? undefined : val, page: 1 }) });
                }}
              >
                <SelectTrigger className="w-28 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LOCATIONS.map((loc) => (
                    <SelectItem key={loc} value={loc} className="text-xs">
                      {loc}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">Branch:</span>
              <Select
                value={selectedBranch}
                onValueChange={(val) => {
                  setSelectedBranch(val);
                  setPage(1);
                  navigate({ search: (prev) => ({ ...prev, branch: val === "All" ? undefined : val, page: 1 }) });
                }}
              >
                <SelectTrigger className="w-28 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {COMMON_BRANCHES.map((b) => (
                    <SelectItem key={b} value={b} className="text-xs">
                      {b}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {candidateRank && (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-primary/20 bg-primary/10 px-2.5 py-1 font-mono text-xs font-semibold text-primary">
                Candidate Rank: {candidateRank.toLocaleString("en-IN")}
              </span>
            )}
            <span className="text-xs text-muted-foreground">
              Total: <strong className="font-mono text-foreground">{totalColleges}</strong> institutions cataloged{totalColleges === 221 ? " (171 Engineering)" : ""}
            </span>
          </div>
        </div>

        {/* State: Error */}
        {isError && (
          <Panel className="mb-6 flex flex-col items-center justify-center gap-3 border-destructive/20 bg-destructive/5 p-8 text-center text-destructive">
            <AlertCircle className="size-6 text-destructive" />
            <strong className="text-base font-semibold">Failed to load official college directory</strong>
            <p className="max-w-md text-xs leading-relaxed text-muted-foreground">
              {error instanceof Error ? error.message : "The COMEDK backend service is currently unreachable."}
            </p>
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              Retry Connection
            </Button>
          </Panel>
        )}

        {/* State: Loading */}
        {isLoading && (
          <div className="flex h-72 flex-col items-center justify-center gap-3 text-muted-foreground">
            <Loader2 className="size-8 animate-spin text-primary" />
            <p className="text-sm font-medium">Loading verified COMEDK institutions...</p>
          </div>
        )}

        {/* State: Empty */}
        {!isLoading && !isError && collegesList.length === 0 && (
          <EmptyState
            title="No colleges found"
            description="No participating institutions match your search query or location filter."
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSearchQuery("");
                  setSelectedLocation("All");
                  setPage(1);
                }}
              >
                Clear Filters
              </Button>
            }
          />
        )}

        {/* State: Grid of verified colleges */}
        {!isLoading && !isError && collegesList.length > 0 && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {collegesList.map((c) => (
                <Panel
                  key={c.id}
                  className="flex flex-col justify-between p-5 transition-all hover:border-primary/40 hover:shadow-sm"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2 border-b border-border pb-3">
                      <span className="rounded-md border border-primary/20 bg-primary/10 px-2 py-0.5 font-mono text-xs font-semibold text-primary">
                        {c.code}
                      </span>
                      <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                        {c.institution_type}
                      </span>
                    </div>

                    <h3 className="mt-3 text-sm font-semibold leading-snug text-foreground">
                      {c.name}
                    </h3>

                    <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                      <MapPin className="size-3.5 shrink-0 text-muted-foreground/80" />
                      <span>{c.location || "Karnataka"}</span>
                    </p>
                  </div>

                  <div className="mt-5 flex items-center justify-between border-t border-border pt-4">
                    <Button asChild size="sm" variant="ghost" className="text-xs font-medium">
                      <Link to="/colleges/$slug" params={{ slug: c.id }}>
                        College Details →
                      </Link>
                    </Button>
                  </div>
                </Panel>
              ))}
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="mt-8 flex items-center justify-between border-t border-border pt-4">
                <span className="text-xs text-muted-foreground">
                  Showing <strong className="text-foreground">{offset + 1}</strong>–
                  <strong className="text-foreground">{Math.min(offset + PAGE_SIZE, totalColleges)}</strong> of{" "}
                  <strong className="text-foreground">{totalColleges}</strong> colleges
                </span>

                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="gap-1 text-xs"
                  >
                    <ChevronLeft className="size-3.5" /> Previous
                  </Button>
                  <span className="font-mono text-xs font-semibold text-foreground">
                    Page {page} of {totalPages}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    className="gap-1 text-xs"
                  >
                    Next <ChevronRight className="size-3.5" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Section>
    </>
  );
}
