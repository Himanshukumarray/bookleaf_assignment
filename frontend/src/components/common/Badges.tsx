import type { AIStatus, DecisionSource, Priority, TicketStatus } from "../../types";
import { cn } from "../../utils/cn";
import { humanize } from "../../utils/format";

const base = "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset";

const PRIORITY_STYLES: Record<Priority, string> = {
  CRITICAL: "bg-red-50 text-red-700 ring-red-600/30",
  HIGH: "bg-orange-50 text-orange-700 ring-orange-600/30",
  MEDIUM: "bg-amber-50 text-amber-700 ring-amber-600/30",
  LOW: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

const STATUS_STYLES: Record<TicketStatus, string> = {
  OPEN: "bg-blue-50 text-blue-700 ring-blue-600/30",
  IN_PROGRESS: "bg-violet-50 text-violet-700 ring-violet-600/30",
  RESOLVED: "bg-emerald-50 text-emerald-700 ring-emerald-600/30",
  CLOSED: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <span className={cn(base, PRIORITY_STYLES[priority])}>{humanize(priority)}</span>;
}

export function StatusBadge({ status }: { status: TicketStatus }) {
  return <span className={cn(base, STATUS_STYLES[status])}>{humanize(status)}</span>;
}

export function CategoryBadge({ category }: { category: string | null }) {
  return (
    <span className={cn(base, category ? "bg-brand-50 text-brand-700 ring-brand-600/20" : "bg-slate-50 text-slate-500 ring-slate-300")}>
      {category ?? "Unclassified"}
    </span>
  );
}

const SOURCE_LABEL: Record<DecisionSource, string> = {
  AI: "AI",
  RULE: "Rule-adjusted",
  MANUAL: "Manual override",
  DEFAULT: "Default",
};

export function SourceTag({ source }: { source: DecisionSource }) {
  return (
    <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide", source === "MANUAL" ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-500")}>
      {SOURCE_LABEL[source]}
    </span>
  );
}

const AI_STYLES: Record<AIStatus, string> = {
  PENDING: "bg-slate-100 text-slate-600 ring-slate-500/20",
  PROCESSING: "bg-blue-50 text-blue-700 ring-blue-600/30",
  COMPLETED: "bg-emerald-50 text-emerald-700 ring-emerald-600/30",
  FAILED: "bg-red-50 text-red-700 ring-red-600/30",
};

export function AIStatusBadge({ status }: { status: AIStatus }) {
  return <span className={cn(base, AI_STYLES[status])}>AI {humanize(status)}</span>;
}
