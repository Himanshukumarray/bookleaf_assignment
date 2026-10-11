import { Link } from "react-router-dom";

import { Card, CardHeader, ErrorState, PageHeader, PageSkeleton, Stat } from "../../components/common/ui";
import { useAdminDashboard } from "../../features/admin/queries";
import { humanize, timeAgo } from "../../utils/format";

export default function AdminDashboard() {
  const { data, isLoading, error, refetch } = useAdminDashboard();
  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorState error={error} onRetry={refetch} />;

  const max = Math.max(1, ...data.by_category.map((c) => c.count));
  return (
    <>
      <PageHeader title="Support dashboard" description="Live view of the ticket queue." />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <Stat label="Open" value={data.open_tickets} />
        <Stat label="Unresolved" value={data.unresolved_tickets} />
        <Stat label="Critical" value={data.critical_tickets} tone={data.critical_tickets ? "danger" : "default"} />
        <Stat label="High priority" value={data.high_priority_tickets} tone={data.high_priority_tickets ? "warn" : "default"} />
        <Stat label="Unassigned" value={data.unassigned_tickets} />
        <Stat label="AI failures" value={data.ai_failed_tickets} tone={data.ai_failed_tickets ? "warn" : "default"} hint="Handle manually or retry" />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Tickets by category" action={<Link to="/admin/tickets" className="text-sm font-medium text-brand-700 hover:underline">Open queue</Link>} />
          <ul className="space-y-3 p-5">
            {data.by_category.length === 0 && <li className="text-sm text-slate-500">No tickets yet.</li>}
            {data.by_category.map((c) => (
              <li key={c.category ?? "none"}>
                <div className="flex justify-between text-sm"><span>{c.category ?? "Unclassified"}</span><span className="font-semibold">{c.count}</span></div>
                <div className="mt-1 h-1.5 rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-500" style={{ width: `${(c.count / max) * 100}%` }} /></div>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Recent activity" />
          <ul className="divide-y divide-slate-100">
            {data.recent_activity.length === 0 && <li className="px-5 py-6 text-sm text-slate-500">Nothing yet.</li>}
            {data.recent_activity.map((a, i) => (
              <li key={i} className="flex items-center justify-between gap-3 px-5 py-2.5 text-sm">
                <span>
                  <Link to={`/admin/tickets/${a.ticket_id}`} className="font-medium text-brand-700 hover:underline">{a.ticket_id}</Link>{" "}
                  <span className="text-slate-600">{humanize(a.event_type.replace(/\./g, "_"))}{a.new_value ? ` → ${a.new_value}` : ""}</span>
                </span>
                <span className="shrink-0 text-xs text-slate-400">{timeAgo(a.created_at)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
