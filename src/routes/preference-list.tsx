import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  GripVertical,
  Plus,
  ShieldAlert,
  Sparkles,
  Trash2,
  ChevronUp,
  ChevronDown,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fetchColleges, CANONICAL_COLLEGES } from "@/lib/api-client";
import { CollegeLogo } from "@/components/product/brand";
import { PageHeader, Panel, Section } from "@/components/product/page";

export type PreferencePriority = "High" | "Medium" | "Standard";

export interface Preference {
  id: string;
  collegeId: string;
  branch: string;
  priority: PreferencePriority;
}

const initial: Preference[] = [
  { id: "1", collegeId: "39dd12af-12d8-445b-8a5d-66d22792a361", branch: "CSE", priority: "High" },
  { id: "2", collegeId: "584b3ee8-34dc-4a07-8954-fa92ca4ba192", branch: "CSE", priority: "High" },
  { id: "3", collegeId: "1840e5e2-af59-49be-88e0-563dcb74b9e5", branch: "ISE", priority: "Medium" },
  { id: "4", collegeId: "a6e0188f-8e3c-4cd3-9d7e-89140dc86428", branch: "CSE", priority: "Medium" },
  { id: "5", collegeId: "e36a6d28-3c86-4c04-bf1f-1ed38a34769b", branch: "AIML", priority: "Standard" },
];

const COMMON_BRANCHES = [
  "CSE (Computer Science)",
  "AIML (AI & Machine Learning)",
  "ISE (Information Science)",
  "ECE (Electronics & Comm)",
  "Data Science",
  "EEE (Electrical & Electronics)",
  "Mechanical",
  "Civil",
];

export const Route = createFileRoute("/preference-list")({
  head: () => ({
    meta: [
      { title: "Preference List Builder — COMEDK Compass" },
      {
        name: "description",
        content: "Build and organize your COMEDK choice filling preference list with verified college identities.",
      },
      { property: "og:title", content: "COMEDK Preference List Builder" },
      {
        property: "og:description",
        content: "Organize candidate choice filling order with verified COMEDK institutions.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: PreferenceList,
});

function PreferenceList() {
  const [items, setItems] = useState<Preference[]>(initial);
  const [dragged, setDragged] = useState<number | null>(null);
  const [selectedCollegeId, setSelectedCollegeId] = useState<string>("");
  const [selectedBranch, setSelectedBranch] = useState<string>("CSE (Computer Science)");
  const [showAddForm, setShowAddForm] = useState(false);

  // Fetch real college catalogue from backend
  const { data: colleges = CANONICAL_COLLEGES } = useQuery({
    queryKey: ["colleges-catalog"],
    queryFn: () => fetchColleges(),
    staleTime: 10 * 60 * 1000,
  });

  const collegesMap = useMemo(() => {
    const map = new Map<
      string,
      { code: string; name: string; shortName: string; accent: string; slug: string }
    >();
    colleges.forEach((c) => {
      map.set(c.id, {
        code: c.code,
        name: c.name,
        shortName: c.shortName,
        accent: c.code.slice(1, 3) || "CK",
        slug: c.code.toLowerCase(),
      });
    });
    return map;
  }, [colleges]);

  useEffect(() => {
    const saved = window.localStorage.getItem("compass-preferences-v2");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) setItems(parsed);
      } catch {
        window.localStorage.removeItem("compass-preferences-v2");
      }
    }
  }, []);

  const save = (next: Preference[]) => {
    setItems(next);
    window.localStorage.setItem("compass-preferences-v2", JSON.stringify(next));
  };

  const move = (from: number, to: number) => {
    if (to < 0 || to >= items.length) return;
    const next = [...items];
    const [item] = next.splice(from, 1);
    if (!item) return;
    next.splice(to, 0, item);
    save(next);
  };

  const addPreference = () => {
    const targetCollegeId = selectedCollegeId || colleges[0]?.id;
    if (!targetCollegeId) {
      toast.error("Please select a college");
      return;
    }

    const shortBranch = selectedBranch.split(" ")[0] ?? "CSE";

    save([
      ...items,
      {
        id: crypto.randomUUID(),
        collegeId: targetCollegeId,
        branch: shortBranch,
        priority: "Standard",
      },
    ]);
    setShowAddForm(false);
    toast.success("Preference added to list");
  };

  const togglePriority = (id: string) => {
    const next = items.map((item) => {
      if (item.id !== id) return item;
      const nextPriority: PreferencePriority =
        item.priority === "High"
          ? "Medium"
          : item.priority === "Medium"
          ? "Standard"
          : "High";
      return { ...item, priority: nextPriority };
    });
    save(next);
  };

  return (
    <>
      <PageHeader
        eyebrow="Choice Filling Workspace"
        title="Preference List Builder"
        description={`Your list contains ${items.length} choices. Drag or use arrows to reorder your official preference hierarchy.`}
        actions={
          <Button onClick={() => setShowAddForm((v) => !v)}>
            <Plus className="size-4" /> {showAddForm ? "Cancel" : "Add College"}
          </Button>
        }
      />

      <Section>
        {showAddForm && (
          <Panel className="mb-6 border-primary/20 bg-primary/5 p-4">
            <h3 className="text-sm font-semibold text-foreground">Add College Choice to Preference List</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Select any participating Karnataka institution from verified COMEDK database.
            </p>
            <div className="mt-3 flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-3">
              <div className="w-full sm:flex-1 sm:min-w-[200px]">
                <Select
                  value={selectedCollegeId || colleges[0]?.id || ""}
                  onValueChange={setSelectedCollegeId}
                >
                  <SelectTrigger className="w-full bg-background">
                    <SelectValue placeholder="Select college" />
                  </SelectTrigger>
                  <SelectContent className="max-h-72">
                    {colleges.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.code}: {c.name.split("-")[0]?.trim()}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="w-full sm:w-56">
                <Select value={selectedBranch} onValueChange={setSelectedBranch}>
                  <SelectTrigger className="w-full bg-background">
                    <SelectValue placeholder="Select branch" />
                  </SelectTrigger>
                  <SelectContent>
                    {COMMON_BRANCHES.map((b) => (
                      <SelectItem key={b} value={b}>
                        {b}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <Button onClick={addPreference} className="w-full sm:w-auto shrink-0">
                <Plus className="size-3.5 mr-1" /> Add to List
              </Button>
            </div>
          </Panel>
        )}

        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="space-y-2">
            {items.map((item, index) => {
              const college = collegesMap.get(item.collegeId);
              return (
                <Panel
                  key={item.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 transition-opacity"
                  draggable
                  onDragStart={() => setDragged(index)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => {
                    if (dragged !== null) move(dragged, index);
                    setDragged(null);
                  }}
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <div className="flex flex-col items-center shrink-0">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-5 p-0 text-muted-foreground hover:text-foreground"
                        onClick={() => move(index, index - 1)}
                        disabled={index === 0}
                        aria-label="Move choice up"
                      >
                        <ChevronUp className="size-3.5" />
                      </Button>
                      <GripVertical className="size-3.5 cursor-grab text-muted-foreground" />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-5 p-0 text-muted-foreground hover:text-foreground"
                        onClick={() => move(index, index + 1)}
                        disabled={index === items.length - 1}
                        aria-label="Move choice down"
                      >
                        <ChevronDown className="size-3.5" />
                      </Button>
                    </div>

                    <span className="w-6 font-mono text-xs font-semibold text-muted-foreground shrink-0">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <CollegeLogo initials={college?.accent || "CK"} className="size-8 shrink-0 text-[10px]" />
                    <div className="min-w-0 flex-1">
                      <Link
                        to="/colleges/$slug"
                        params={{ slug: college?.slug || college?.code || item.collegeId }}
                        className="hover:text-primary transition-colors"
                      >
                        <strong className="block truncate text-xs sm:text-sm font-semibold text-foreground hover:underline">
                          {college?.shortName || item.collegeId.slice(0, 8)} · {item.branch}
                        </strong>
                      </Link>
                      <span className="text-[11px] text-muted-foreground truncate block">
                        {college?.name || "Official Karnataka Institution"}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between sm:justify-end gap-2 shrink-0 border-t border-border/40 pt-2 sm:border-t-0 sm:pt-0">
                    <button
                      type="button"
                      onClick={() => togglePriority(item.id)}
                      className={`cursor-pointer rounded-full px-2.5 py-0.5 text-[10px] font-semibold transition-transform active:scale-95 ${
                        item.priority === "High"
                          ? "bg-primary/10 text-primary border border-primary/20"
                          : item.priority === "Medium"
                          ? "bg-warning/10 text-warning border border-warning/20"
                          : "bg-muted text-muted-foreground border border-border"
                      }`}
                      title="Click to change your priority level (High / Medium / Standard)"
                    >
                      {item.priority} Priority
                    </button>

                    <Button asChild variant="ghost" size="icon" className="size-8" title="Analyze with Rank Predictor">
                      <Link
                        to="/predictor"
                        search={{
                          collegeId: item.collegeId,
                          round: "R1",
                          category: "GM",
                        }}
                      >
                        <Sparkles className="size-4 text-muted-foreground" />
                      </Link>
                    </Button>

                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      onClick={() => save(items.filter((x) => x.id !== item.id))}
                      aria-label={`Remove ${college?.shortName || "preference"}`}
                    >
                      <Trash2 className="size-4 text-muted-foreground hover:text-destructive" />
                    </Button>
                  </div>
                </Panel>
              );
            })}
          </div>

          <div className="space-y-4">
            <Panel className="p-5">
              <p className="eyebrow">Preference Hierarchy</p>
              <p className="mt-1 text-xs text-muted-foreground">
                User-defined ranking distribution across your customized priority levels. (Click any badge on the left to adjust).
              </p>
              {(["High", "Medium", "Standard"] as const).map((tier) => {
                const count = items.filter((i) => i.priority === tier).length;
                return (
                  <div className="mt-4" key={tier}>
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-foreground">{tier} Priority</span>
                      <strong className="font-mono">{count}</strong>
                    </div>
                    <div className="mt-1.5 h-1.5 rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${Math.min(100, count * 25)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </Panel>

            <div className="flex gap-3 rounded-lg border border-warning/20 bg-warning/5 p-4 text-xs leading-relaxed text-muted-foreground">
              <ShieldAlert className="size-4 shrink-0 text-warning" />
              <p>
                COMEDK allocates seats sequentially from choice 01 downward. If you are allotted any choice, all lower choices are permanently eliminated for that round.
              </p>
            </div>
          </div>
        </div>
      </Section>
    </>
  );
}
