import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { getErrorCode } from "../../api/client";
import { CategoryBadge, PriorityBadge, StatusBadge } from "../../components/common/Badges";
import { Card, CardHeader, EmptyState, ErrorState, PageSkeleton } from "../../components/common/ui";
import { Conversation } from "../../components/tickets/Conversation";
import { MessageComposer } from "../../components/tickets/MessageComposer";
import { useMessages, usePostMessage, useTicket } from "../../features/tickets/queries";
import { formatDateTime } from "../../utils/format";

export default function AuthorTicketDetail() {
  const { ticketId = "" } = useParams();
  const ticket = useTicket(ticketId);
  const messages = useMessages(ticketId);
  const post = usePostMessage(ticketId);

  if (ticket.isLoading) return <PageSkeleton />;
  if (ticket.error || !ticket.data) {
    if (getErrorCode(ticket.error) === "TICKET_NOT_FOUND") {
      return <Card><EmptyState title="Ticket not found" description="It may not exist, or it belongs to another account." action={<Link to="/author/tickets" className="text-brand-700 underline">Back to my tickets</Link>} /></Card>;
    }
    return <ErrorState error={ticket.error} onRetry={ticket.refetch} />;
  }
  const t = ticket.data;

  return (
    <>
      <Link to="/author/tickets" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900"><ArrowLeft className="h-4 w-4" /> My tickets</Link>
      <Card>
        <div className="border-b border-slate-100 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-lg font-bold">{t.ticket_id}</h1>
            <StatusBadge status={t.status} />
            <PriorityBadge priority={t.priority} />
            <CategoryBadge category={t.category} />
          </div>
          <h2 className="mt-2 text-base font-semibold">{t.subject}</h2>
          <p className="mt-1 text-xs text-slate-500">{t.book ? t.book.title : "General / Account Level"} · opened {formatDateTime(t.created_at)}</p>
          <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{t.description}</p>
        </div>
        <CardHeader title="Conversation" subtitle="New replies appear automatically." />
        <div className="space-y-4 bg-slate-50/60 p-5">
          {messages.isLoading ? <PageSkeleton rows={2} /> : messages.error ? <ErrorState error={messages.error} onRetry={messages.refetch} /> : <Conversation messages={messages.data ?? []} viewer="AUTHOR" />}
        </div>
        <div className="border-t border-slate-100 p-5">
          <MessageComposer
            onSend={(text) => post.mutateAsync(text)}
            disabled={t.status === "CLOSED"}
            disabledReason="This ticket is closed. Please submit a new query if you need more help."
            placeholder="Add a reply or more details…"
          />
        </div>
      </Card>
    </>
  );
}
