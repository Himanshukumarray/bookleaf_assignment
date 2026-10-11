import { AlertTriangle, BookMarked, RefreshCw, Sparkles } from "lucide-react";

import type { AdminTicketDetail } from "../../types";
import { formatPercent } from "../../utils/format";
import { AIStatusBadge, CategoryBadge, PriorityBadge, SourceTag } from "../common/Badges";
import { Button, Card, CardHeader } from "../common/ui";

function ConfidenceBar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-slate-400">No confidence (not model-decided)</span>;
  return (
    <div className="flex items-center gap-2" aria-label={`Confidence ${formatPercent(value)}`}>
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200">
        <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="text-xs font-semibold text-slate-700">{formatPercent(value)}</span>
    </div>
  );
}

interface Props {
  detail: AdminTicketDetail;
  onRetry: () => void;
  retrying: boolean;
}

/** Short, explainable AI output only: category, priority, confidences, one-line reason, sources. */
export function AIInsightsPanel({ detail, onRetry, retrying }: Props) {
  const { ticket } = detail;
  const failed = ticket.ai_status === "FAILED";
  const working = ticket.ai_status === "PENDING" || ticket.ai_status === "PROCESSING";

  return (
    <Card>
      <CardHeader title={<span className="inline-flex items-center gap-1.5"><Sparkles className="h-4 w-4 text-brand-600" /> AI Insights</span>} action={<AIStatusBadge status={ticket.ai_status} />} />
      <div className="space-y-4 p-5">
        {failed && (
          <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="flex items-center gap-1.5 font-semibold"><AlertTriangle className="h-4 w-4" /> AI assistance temporarily unavailable.</p>
            <p className="mt-1">You can respond manually — category, priority, status and replies all still work.</p>
            <Button variant="secondary" className="mt-3" onClick={onRetry} loading={retrying}>
              <RefreshCw className="h-4 w-4" /> Retry AI analysis
            </Button>
          </div>
        )}
        {working && <p className="text-sm text-slate-500">AI analysis in progress… this page updates automatically.</p>}

        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Category</p>
          <div className="mt-1 flex items-center justify-between gap-2">
            <CategoryBadge category={ticket.category} />
            <SourceTag source={ticket.category_source} />
          </div>
          <div className="mt-2"><ConfidenceBar value={ticket.category_confidence} /></div>
        </div>

        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Priority</p>
          <div className="mt-1 flex items-center justify-between gap-2">
            <PriorityBadge priority={ticket.priority} />
            <SourceTag source={ticket.priority_source} />
          </div>
          <div className="mt-2"><ConfidenceBar value={ticket.priority_confidence} /></div>
        </div>

        {ticket.needs_human_attention && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-xs font-medium text-red-700">AI flagged this ticket as needing human attention.</p>
        )}

        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Reason</p>
          <p className="mt-1 text-sm text-slate-700">{detail.ai_reasoning ?? "No AI reasoning available."}</p>
        </div>

        <div>
          <p className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-slate-400"><BookMarked className="h-3.5 w-3.5" /> Knowledge used</p>
          {detail.knowledge_used.length === 0 ? (
            <p className="mt-1 text-sm text-slate-500">None yet.</p>
          ) : (
            <ul className="mt-1 flex flex-wrap gap-1.5">
              {detail.knowledge_used.map((k) => (
                <li key={k.section} className="rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">{k.title}</li>
              ))}
            </ul>
          )}
        </div>

        {detail.ai_runs.length > 0 && (
          <details className="text-xs text-slate-500">
            <summary className="cursor-pointer font-medium text-slate-600">AI run log ({detail.ai_runs.length})</summary>
            <ul className="mt-2 space-y-1">
              {detail.ai_runs.map((r) => (
                <li key={r.id} className="flex justify-between gap-2">
                  <span>{r.operation} · {r.status.toLowerCase()}{r.attempts > 1 ? ` · ${r.attempts} tries` : ""}{r.error_type ? ` · ${r.error_type}` : ""}</span>
                  <span>{r.latency_ms}ms · {r.input_tokens}/{r.output_tokens} tok</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </Card>
  );
}
