import { Link } from "react-router-dom";

import type { Ticket } from "../../types";
import { formatDate, timeAgo } from "../../utils/format";
import { CategoryBadge, PriorityBadge, StatusBadge } from "../common/Badges";

export function TicketTable({ tickets }: { tickets: Ticket[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-100 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            {["Ticket", "Book", "Subject", "Category", "Priority", "Status", "Created", "Last update"].map((h) => (
              <th key={h} scope="col" className="whitespace-nowrap px-4 py-2.5">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tickets.map((t) => (
            <tr key={t.ticket_id} className="hover:bg-slate-50">
              <td className="whitespace-nowrap px-4 py-3 font-medium">
                <Link to={`/author/tickets/${t.ticket_id}`} className="text-brand-700 hover:underline">{t.ticket_id}</Link>
              </td>
              <td className="px-4 py-3 text-slate-600">{t.book?.title ?? "General / Account"}</td>
              <td className="max-w-xs truncate px-4 py-3">{t.subject}</td>
              <td className="px-4 py-3"><CategoryBadge category={t.category} /></td>
              <td className="px-4 py-3"><PriorityBadge priority={t.priority} /></td>
              <td className="px-4 py-3"><StatusBadge status={t.status} /></td>
              <td className="whitespace-nowrap px-4 py-3 text-slate-500">{formatDate(t.created_at)}</td>
              <td className="whitespace-nowrap px-4 py-3 text-slate-500">{timeAgo(t.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
