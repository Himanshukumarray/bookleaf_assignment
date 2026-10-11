import { Link } from "react-router-dom";

import { Button, Card, CardHeader, ErrorState, PageHeader, PageSkeleton, Stat } from "../../components/common/ui";
import { TicketTable } from "../../components/tickets/TicketTable";
import { useAuthorDashboard } from "../../features/author/queries";
import { useAuth } from "../../hooks/useAuth";
import { formatRoyalty } from "../../utils/format";

export default function AuthorDashboard() {
  const { user } = useAuth();
  const { data, isLoading, error, refetch } = useAuthorDashboard();

  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorState error={error} onRetry={refetch} />;

  const maxCount = Math.max(1, ...data.book_status_overview.map((s) => s.count));
  return (
    <>
      <PageHeader
        title={`Welcome back, ${user?.author?.name.split(" ")[0] ?? "author"}`}
        description="Your books, royalties and support requests at a glance."
        actions={<Link to="/author/tickets/new"><Button>New support query</Button></Link>}
      />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Stat label="Books" value={data.total_books} />
        <Stat label="Open tickets" value={data.open_tickets} tone={data.open_tickets > 0 ? "warn" : "default"} />
        <Stat label="Royalty earned" value={formatRoyalty(data.total_royalty_earned)} />
        <Stat label="Royalty paid" value={formatRoyalty(data.total_royalty_paid)} tone="good" />
        <Stat label="Royalty pending" value={formatRoyalty(data.total_royalty_pending)} hint="Balances under ₹1,000 roll over to the next quarter" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Recent tickets" action={<Link to="/author/tickets" className="text-sm font-medium text-brand-700 hover:underline">View all</Link>} />
          {data.recent_tickets.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-slate-500">No tickets yet — we're here whenever you need us.</p>
          ) : (
            <TicketTable tickets={data.recent_tickets} />
          )}
        </Card>
        <Card>
          <CardHeader title="Book status overview" />
          <ul className="space-y-3 p-5">
            {data.book_status_overview.length === 0 && <li className="text-sm text-slate-500">No books on your account yet.</li>}
            {data.book_status_overview.map((s) => (
              <li key={s.status}>
                <div className="flex justify-between text-sm"><span>{s.status}</span><span className="font-semibold">{s.count}</span></div>
                <div className="mt-1 h-1.5 rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-500" style={{ width: `${(s.count / maxCount) * 100}%` }} /></div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
