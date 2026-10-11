import { Link } from "react-router-dom";

import { Button, Card, EmptyState, ErrorState, PageHeader, PageSkeleton } from "../../components/common/ui";
import { TicketTable } from "../../components/tickets/TicketTable";
import { useTickets } from "../../features/tickets/queries";

export default function Tickets() {
  const { data, isLoading, error, refetch } = useTickets();
  return (
    <>
      <PageHeader title="My Tickets" description="Every query you've sent and where it stands." actions={<Link to="/author/tickets/new"><Button>New query</Button></Link>} />
      {isLoading && <PageSkeleton />}
      {error && <ErrorState error={error} onRetry={refetch} />}
      {data && (
        <Card>
          {data.length === 0 ? (
            <EmptyState title="No tickets yet" description="When you submit a query it will show up here, with live status updates." action={<Link to="/author/tickets/new"><Button>Submit a query</Button></Link>} />
          ) : (
            <TicketTable tickets={data} />
          )}
        </Card>
      )}
    </>
  );
}
