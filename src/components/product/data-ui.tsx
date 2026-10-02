"use client";
import { Link } from "@tanstack/react-router";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BadgeCheck, Database, ShieldCheck, TrendingDown, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
export interface SourceMeta {
  source: string;
  year?: number;
  confidence?: "High" | "Medium" | "Low";
  verifiedCount?: number;
}
import { CollegeLogo } from "./brand";

export function SourceBadge({ meta, compact=false }: { meta: SourceMeta; compact?: boolean }) { return <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground"><Database className="size-3" />{meta.source}{!compact && ` · ${meta.year}`}{meta.verifiedCount ? ` × ${meta.verifiedCount}` : ""}</span>; }
export function VerificationBadge() { return <span className="inline-flex items-center gap-1 rounded-full border border-positive/25 bg-positive/8 px-2 py-1 text-[10px] font-semibold uppercase text-positive"><BadgeCheck className="size-3"/>Verified data</span>; }

export function FactualBadge({ label, variant = "default" }: { label: string; variant?: "default" | "positive" | "muted" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        variant === "positive"
          ? "border-positive/20 bg-positive/10 text-positive"
          : variant === "muted"
          ? "border-border bg-muted text-muted-foreground"
          : "border-primary/20 bg-primary/10 text-primary"
      )}
    >
      {label}
    </span>
  );
}

export function SourcedMetric({ value,label,meta,highlight=false }: { value:string;label:string;meta:SourceMeta;highlight?:boolean }) { return <div className="min-w-0"><div className={cn("text-2xl font-semibold tracking-tight",highlight&&"text-primary")}>{value}</div><div className="mt-1 text-sm text-muted-foreground">{label}</div><div className="mt-2"><SourceBadge meta={meta}/></div></div>; }

export interface RoundMilestone {
  round: string;
  rank?: number | null;
  label?: string;
}

export function RoundCutoffTimeline({ milestones, compact=false }: { milestones: RoundMilestone[]; compact?: boolean }) {
  return (
    <div className={cn("grid gap-2", compact ? "grid-cols-3" : "grid-cols-1 sm:grid-cols-3")}>
      {milestones.map((m, index) => (
        <div key={index} className="relative min-w-0 rounded-md border border-border bg-card p-2 text-xs">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="font-semibold text-foreground">{m.round}</span>
            {m.label && <span className="text-[10px]">{m.label}</span>}
          </div>
          <p className="mt-1 font-mono text-sm font-semibold text-primary">
            {m.rank ? m.rank.toLocaleString("en-IN") : "—"}
          </p>
        </div>
      ))}
    </div>
  );
}
export function TrendChart({ values, height = 260 }: { values: number[]; height?: number }) {
  const data = values.map((rank, index) => ({ year: 2024 + index, rank }));
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 12, right: 8, left: -12, bottom: 0 }}>
          <defs>
            <linearGradient id="rankFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.2} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis dataKey="year" axisLine={false} tickLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
          <YAxis reversed axisLine={false} tickLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
          <Tooltip contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 12 }} formatter={(v) => [Number(v).toLocaleString("en-IN"), "Closing rank"]} />
          <Area type="monotone" dataKey="rank" stroke="var(--primary)" strokeWidth={2} fill="url(#rankFill)" animationDuration={700} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export interface CollegeCardData {
  id: string;
  code: string;
  name: string;
  shortName?: string;
  location: string;
  accent?: string;
  slug?: string;
  type?: string;
  branches?: string[];
  verified?: boolean;
}

export function CollegeCard({
  college,
  compact = false,
}: {
  college: CollegeCardData;
  compact?: boolean;
}) {
  const initials = college.accent || college.code.slice(1, 3) || "CK";
  const slug = college.slug || college.code || college.id;
  const branches = college.branches ?? ["CSE", "ISE", "ECE", "AIML"];

  return (
    <article className="group flex h-full flex-col justify-between rounded-lg border border-border bg-card p-4 shadow-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md">
      <div>
        <div className="flex items-start justify-between gap-3">
          <CollegeLogo initials={initials} />
          <VerificationBadge />
        </div>
        <div className="mt-4">
          <p className="font-mono text-xs font-semibold text-primary">
            {college.code} · {college.shortName || college.name.split("-")[0]?.trim()}
          </p>
          <h3 className="mt-1 font-semibold leading-snug">{college.name}</h3>
          <p className="mt-1 text-xs text-muted-foreground">{college.location}</p>
        </div>
        <div className="mt-4 flex flex-wrap gap-1.5">
          {branches.slice(0, compact ? 3 : 4).map((b) => (
            <span
              key={b}
              className="rounded border border-border bg-muted/50 px-1.5 py-0.5 font-mono text-[10px]"
            >
              {b}
            </span>
          ))}
        </div>
      </div>

      <div>
        <div className="mt-5 grid grid-cols-2 gap-4 border-y border-border py-3 text-xs">
          <div>
            <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">
              Institution Code
            </span>
            <strong className="font-mono text-sm">{college.code}</strong>
          </div>
          <div>
            <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">
              Allotment Status
            </span>
            <span className="font-semibold text-positive">Official COMEDK</span>
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between">
          <Link
            to="/colleges/$slug"
            params={{ slug }}
            className="text-xs font-semibold text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
          >
            View profile →
          </Link>
          <Link
            to="/predictor"
            search={{ collegeId: college.id, round: "R1", category: "GM" }}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Analyze rank →
          </Link>
        </div>
      </div>
    </article>
  );
}
export function TrendDelta({ value }: { value:number }) { const up=value>0; return <span className={cn("inline-flex items-center gap-1 text-xs font-medium",up?"text-positive":"text-negative")}>{up?<TrendingUp className="size-3"/>:<TrendingDown className="size-3"/>}{Math.abs(value)}%</span>; }
export function DataNotice({ children }: {children:string}) { return <div className="flex gap-2 rounded-md border border-info/20 bg-info/5 p-3 text-xs text-muted-foreground"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-info"/><p>{children}</p></div>; }
