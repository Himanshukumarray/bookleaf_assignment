import { AlertTriangle, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { AIStatusBadge, CategoryBadge, PriorityBadge, StatusBadge } from "../../components/common/Badges";
import { Button, Card, EmptyState, ErrorState, PageHeader, Skeleton } from "../../components/common/ui";
import { useQueue } from "../../features/admin/queries";
import { CATEGORIES, PRIORITIES, STATUSES, type Category, type Priority, type QueueFilters, type TicketStatus } from "../../types";
import { humanize, timeAgo } from "../../utils/format";

const PAGE_SIZE = 20;

export default function TicketQueue() {
  const [filters, setFilters] = useState<QueueFilters>({ sort: "urgency", page: 1, page_size: PAGE_SIZE });
  const { data, isLoading, isFetching, error, refetch } = useQueue(filters);
  const set = (patch: Partial<QueueFilters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <>
      <PageHeader title="Ticket queue" description="Sorted by urgency: unresolved first, then priority, with older tickets boosted." />
      <Card className="mb-4 p-4">
        <div className="grid gap-3 md:grid-cols-4 lg:grid-cols-6">
          <div className="relative md:col-span-2">
            <label htmlFor="q" className="sr-only">Search</label>
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input id="q" className="input pl-9" placeholder="Search subject, text, ID…" value={filters.q ?? ""} onChange={(e) => set({ q: e.target.value })} />
          </div>
          <Select label="Status" value={filters.status ?? ""} onChange={(v) => set({ status: v as TicketStatus | "" })} options={STATUSES.map((s) => [s, humanize(s)])} />
          <Select label="Category" value={filters.category ?? ""} onChange={(v) => set({ category: v as Category | "" })} options={CATEGORIES.map((c) => [c, c])} />
          <Select label="Priority" value={filters.priority ?? ""} onChange={(v) => set({ priority: v as Priority | "" })} options={PRIORITIES.map((p) => [p, humanize(p)])} />
          <Select label="Assignment" value={filters.assignment ?? ""} onChange={(v) => set({ assignment: v as QueueFilters["assignment"] })} options={[["unassigned", "Unassigned"], ["assigned", "Assigned"], ["me", "Assigned to me"]]} />
          <div>
            <label htmlFor="author" className="sr-only">Author</label>
            <input id="author" className="input" placeholder="Author name / AUTH001" value={filters.author ?? ""} onChange={(e) => set({ author: e.target.value })} />
          </div>
          <div>
            <label htmlFor="book" className="sr-only">Book</label>
            <input id="book" className="input" placeholder="Book ID (BK001)" value={filters.book ?? ""} onChange={(e) => set({ book: e.target.value })} />
          </div>
          <div>
            <label htmlFor="from" className="sr-only">Created from</label>
            <input id="from" type="date" className="input" value={filters.date_from ?? ""} onChange={(e) => set({ date_from: e.target.value })} title="Created from" />
          </div>
          <div>
            <label htmlFor="to" className="sr-only">Created to</label>
            <input id="to" type="date" className="input" value={filters.date_to ?? ""} onChange={(e) => set({ date_to: e.target.value })} title="Created to" />
          </div>
          <Select label="Sort" value={filters.sort ?? "urgency"} allowAll={false} onChange={(v) => set({ sort: v as QueueFilters["sort"] })} options={[["urgency", "Most urgent"], ["newest", "Newest"], ["oldest", "Oldest"], ["updated", "Recently updated"]]} />
          <Button variant="ghost" onClick={() => setFilters({ sort: "urgency", page: 1, page_size: PAGE_SIZE })}>Clear filters</Button>
        </div>
      </Card>

      {error && <ErrorState error={error} onRetry={refetch} />}
      <Card className={isFetching && !isLoading ? "opacity-70 transition-opacity" : ""}>
        {isLoading ? (
          <div className="space-y-2 p-4">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
        ) : data && data.items.length === 0 ? (
          <EmptyState title="No tickets match these filters" description="Try clearing a filter or searching for something else." />
        ) : (
          data && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-100 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <tr>{["Ticket", "Author / Book", "Subject", "Category", "Priority", "Status", "Assignee", "Age"].map((h) => <th key={h} scope="col" className="whitespace-nowrap px-4 py-2.5">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((t) => (
                    <tr key={t.ticket_id} className="hover:bg-slate-50">
                      <td className="whitespace-nowrap px-4 py-3 font-medium"><Link className="text-brand-700 hover:underline" to={`/admin/tickets/${t.ticket_id}`}>{t.ticket_id}</Link></td>
                      <td className="px-4 py-3"><p className="font-medium">{t.author.name}</p><p className="text-xs text-slate-500">{t.book?.title ?? "General / Account"}</p></td>
                      <td className="max-w-xs px-4 py-3">
                        <p className="truncate">{t.subject}</p>
                        <div className="mt-1 flex items-center gap-1.5">
                          {t.ai_status === "FAILED" && <AIStatusBadge status={t.ai_status} />}
                          {t.needs_human_attention && <span className="inline-flex items-center gap-0.5 text-[11px] font-medium text-red-600"><AlertTriangle className="h-3 w-3" /> Needs attention</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3"><CategoryBadge category={t.category} /></td>
                      <td className="px-4 py-3"><PriorityBadge priority={t.priority} /></td>
                      <td className="px-4 py-3"><StatusBadge status={t.status} /></td>
                      <td className="px-4 py-3 text-slate-600">{t.assigned_admin_email ?? <span className="text-slate-400">Unassigned</span>}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-slate-500">{timeAgo(t.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
        {data && data.total > 0 && (
          <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-500">
            <span>{data.total} ticket{data.total === 1 ? "" : "s"}</span>
            <div className="flex items-center gap-2">
              <Button variant="secondary" aria-label="Previous page" disabled={(filters.page ?? 1) <= 1} onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))}><ChevronLeft className="h-4 w-4" /></Button>
              <span>Page {filters.page ?? 1} of {totalPages}</span>
              <Button variant="secondary" aria-label="Next page" disabled={(filters.page ?? 1) >= totalPages} onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}><ChevronRight className="h-4 w-4" /></Button>
            </div>
          </div>
        )}
      </Card>
    </>
  );
}

function Select({ label, value, options, onChange, allowAll = true }: { label: string; value: string; options: [string, string][]; onChange: (v: string) => void; allowAll?: boolean }) {
  return (
    <div>
      <label className="sr-only" htmlFor={`f-${label}`}>{label}</label>
      <select id={`f-${label}`} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        {allowAll && <option value="">{label}: all</option>}
        {options.map(([v, text]) => <option key={v} value={v}>{text}</option>)}
      </select>
    </div>
  );
}
