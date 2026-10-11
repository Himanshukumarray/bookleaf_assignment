import { UserCheck } from "lucide-react";

import { getErrorMessage } from "../../api/client";
import { CATEGORIES, PRIORITIES, STATUSES, type AdminTicketSummary, type Category, type Priority, type TicketStatus, type TicketUpdate } from "../../types";
import { humanize } from "../../utils/format";
import { Button } from "../common/ui";

interface Props {
  ticket: AdminTicketSummary;
  busy: boolean;
  error: unknown;
  onUpdate: (update: TicketUpdate) => void;
  onAssign: () => void;
}

/** Manual controls: always available, whether or not AI worked. Changes are recorded as MANUAL. */
export function TicketControls({ ticket, busy, error, onUpdate, onAssign }: Props) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div>
        <label htmlFor="ctl-status" className="label">Status</label>
        <select id="ctl-status" className="input w-40" value={ticket.status} disabled={busy} onChange={(e) => onUpdate({ status: e.target.value as TicketStatus })}>
          {STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
        </select>
      </div>
      <div>
        <label htmlFor="ctl-priority" className="label">Priority</label>
        <select id="ctl-priority" className="input w-36" value={ticket.priority} disabled={busy} onChange={(e) => onUpdate({ priority: e.target.value as Priority })}>
          {PRIORITIES.map((p) => <option key={p} value={p}>{humanize(p)}</option>)}
        </select>
      </div>
      <div>
        <label htmlFor="ctl-category" className="label">Category</label>
        <select id="ctl-category" className="input w-64" value={ticket.category ?? ""} disabled={busy} onChange={(e) => e.target.value && onUpdate({ category: e.target.value as Category })}>
          {!ticket.category && <option value="">Unclassified — choose…</option>}
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="secondary" onClick={onAssign} disabled={busy}>
          <UserCheck className="h-4 w-4" /> {ticket.assigned_admin_email ? "Reassign to me" : "Assign to me"}
        </Button>
        <span className="text-xs text-slate-500">{ticket.assigned_admin_email ? `Assigned: ${ticket.assigned_admin_email}` : "Unassigned"}</span>
      </div>
      {error !== null && error !== undefined && <p role="alert" className="w-full text-xs text-red-600">{getErrorMessage(error)}</p>}
    </div>
  );
}
