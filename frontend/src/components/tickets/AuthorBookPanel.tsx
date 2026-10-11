import type { Author, Book } from "../../types";
import { formatDate, formatINR, formatRoyalty, orText } from "../../utils/format";
import { BookStatusPill } from "../books/BookCard";
import { Card, CardHeader } from "../common/ui";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 py-1 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value}</dd>
    </div>
  );
}

export function AuthorBookPanel({ author, book }: { author: Author; book: Book | null }) {
  return (
    <Card>
      <CardHeader title="Author & book" />
      <div className="grid gap-6 p-5 md:grid-cols-2">
        <dl className="divide-y divide-slate-100">
          <Row label="Author" value={`${author.name} (${author.author_id})`} />
          <Row label="Email" value={author.email} />
          <Row label="Phone" value={orText(author.phone, "Not provided")} />
          <Row label="City" value={orText(author.city, "Not provided")} />
          <Row label="Joined" value={formatDate(author.joined_date)} />
        </dl>
        {book ? (
          <dl className="divide-y divide-slate-100">
            <div className="flex items-center justify-between py-1 text-sm">
              <dt className="font-semibold text-slate-900">{book.title}</dt>
              <dd><BookStatusPill status={book.status} /></dd>
            </div>
            <Row label="ISBN" value={orText(book.isbn, "Not assigned yet")} />
            <Row label="Published" value={formatDate(book.publication_date, "Not published yet")} />
            <Row label="MRP" value={formatINR(book.mrp, "Not assigned")} />
            <Row label="Copies sold" value={String(book.total_copies_sold)} />
            <Row label="Royalty paid / pending" value={`${formatRoyalty(book.royalty_paid)} / ${formatRoyalty(book.royalty_pending)}`} />
            <Row label="Last payout" value={formatDate(book.last_royalty_payout_date, "No payout yet")} />
            <Row label="Print partner" value={orText(book.print_partner, "Not assigned")} />
            <Row label="Platforms" value={book.available_on.length ? book.available_on.join(", ") : "None listed"} />
          </dl>
        ) : (
          <p className="self-center rounded-lg bg-slate-50 p-4 text-sm text-slate-600">General / account-level query — no specific book selected.</p>
        )}
      </div>
    </Card>
  );
}
