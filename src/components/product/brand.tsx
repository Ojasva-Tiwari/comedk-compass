import { cn } from "@/lib/utils";

export function CompassMark({ className }: { className?: string }) {
  return <span className={cn("relative grid size-8 shrink-0 place-items-center rounded-md bg-primary text-primary-foreground shadow-sm", className)} aria-hidden="true"><svg viewBox="0 0 24 24" className="size-4" fill="none"><circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.7"/><path d="m15.7 8.3-2.05 5.35-5.35 2.05 2.05-5.35 5.35-2.05Z" fill="currentColor"/></svg></span>;
}
export function CollegeLogo({ initials, className }: { initials: string; className?: string }) { return <div className={cn("grid size-11 shrink-0 place-items-center rounded-md border border-border bg-surface-raised font-mono text-xs font-bold text-primary shadow-xs", className)}>{initials}</div>; }
