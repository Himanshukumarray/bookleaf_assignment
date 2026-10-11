import { BookCard } from "../../components/books/BookCard";
import { Card, EmptyState, ErrorState, PageHeader, PageSkeleton } from "../../components/common/ui";
import { useBooks } from "../../features/author/queries";

export default function Books() {
  const { data, isLoading, error, refetch } = useBooks();
  return (
    <>
      <PageHeader title="My Books" description="Publication status, sales and royalty details for each of your titles." />
      {isLoading && <PageSkeleton />}
      {error && <ErrorState error={error} onRetry={refetch} />}
      {data && data.length === 0 && <Card><EmptyState title="No books yet" description="Books appear here once your manuscript is registered with BookLeaf." /></Card>}
      {data && data.length > 0 && (
        <div className="grid gap-5 xl:grid-cols-2">
          {data.map((b) => <BookCard key={b.book_id} book={b} />)}
        </div>
      )}
    </>
  );
}
