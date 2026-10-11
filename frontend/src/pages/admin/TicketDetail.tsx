import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { getErrorCode } from "../../api/client";
import { AIInsightsPanel } from "../../components/ai/AIInsightsPanel";
import { DraftEditor } from "../../components/ai/DraftEditor";
import { CategoryBadge, PriorityBadge, StatusBadge } from "../../components/common/Badges";
import { Card, CardHeader, EmptyState, ErrorState, PageSkeleton } from "../../components/common/ui";
import { AuthorBookPanel } from "../../components/tickets/AuthorBookPanel";
import { Conversation } from "../../components/tickets/Conversation";
import { InternalNotes } from "../../components/tickets/InternalNotes";
import { TicketControls } from "../../components/tickets/TicketControls";
import {
  useAddNote,
  useAdminTicket,
  useAssignToMe,
  useRegenerateDraft,
  useRetryAnalysis,
  useSendResponse,
  useUpdateTicket,
} from "../../features/admin/queries";
import { formatDateTime } from "../../utils/format";

export default function AdminTicketDetail() {
  const { ticketId = "" } = useParams();
  const { data, isLoading, error, refetch } = useAdminTicket(ticketId);
  const update = useUpdateTicket(ticketId);
  const assign = useAssignToMe(ticketId);
  const addNote = useAddNote(ticketId);
  const send = useSendResponse(ticketId);
  const regenerate = useRegenerateDraft(ticketId);
  const retry = useRetryAnalysis(ticketId);

  if (isLoading) return <PageSkeleton rows={6} />;
  if (error || !data) {
    if (getErrorCode(error) === "TICKET_NOT_FOUND") {
      return <Card><EmptyState title="Ticket not found" action={<Link to="/admin/tickets" className="text-brand-700 underline">Back to queue</Link>} /></Card>;
    }
    return <ErrorState error={error} onRetry={refetch} />;
  }
  const { ticket } = data;

  return (
    <>
      <Link to="/admin/tickets" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900"><ArrowLeft className="h-4 w-4" /> Queue</Link>

      <Card className="mb-6">
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 p-5">
          <h1 className="text-xl font-bold">{ticket.ticket_id}</h1>
          <PriorityBadge priority={ticket.priority} />
          <StatusBadge status={ticket.status} />
          <CategoryBadge category={ticket.category} />
          <span className="ml-auto text-xs text-slate-500">Opened {formatDateTime(ticket.created_at)}</span>
        </div>
        <div className="p-5">
          <TicketControls
            ticket={ticket}
            busy={update.isPending || assign.isPending}
            error={update.error ?? assign.error}
            onUpdate={(patch) => update.mutate(patch)}
            onAssign={() => assign.mutate()}
          />
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <AuthorBookPanel author={data.author} book={data.book} />
          <Card>
            <CardHeader title={ticket.subject} subtitle="Author's query" />
            <div className="space-y-5 p-5">
              <p className="whitespace-pre-wrap text-sm text-slate-800">{data.description}</p>
              <div className="border-t border-slate-100 pt-4">
                <Conversation messages={data.messages} viewer="ADMIN" />
              </div>
            </div>
          </Card>
        </div>
        <div className="lg:col-span-1">
          <AIInsightsPanel detail={data} onRetry={() => retry.mutate()} retrying={retry.isPending} />
        </div>
      </div>

      <div className="mt-6 space-y-6">
        <DraftEditor
          draft={data.ai_draft}
          disabled={ticket.status === "CLOSED"}
          onSend={(message, aiDraftId) => send.mutateAsync({ message, aiDraftId })}
          onRegenerate={() => regenerate.mutateAsync()}
        />
        <InternalNotes notes={data.internal_notes} onAdd={(note) => addNote.mutateAsync(note)} />
      </div>
    </>
  );
}
