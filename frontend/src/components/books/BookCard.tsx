import type { ReactNode } from "react";

import type { Book } from "../../types";
import { formatDate, formatINR, formatRoyalty, orText } from "../../utils/format";
import { Card } from "../common/ui";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-800">{children}</dd>
    </div>
  );
}

const isLive = (status: string) => status.toLowerCase().startsWith("published");

export function BookStatusPill({ status }: { status: string }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${isLive(status) ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
      {status}
    </span>
  );
}

/** Every nullable field has an explicit human fallback: "null" never reaches the screen. */
export function BookCard({ book }: { book: Book }) {
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-slate-900">{book.title}</h3>
          <p className="text-xs text-slate-500">
            {book.book_id} · {orText(book.genre, "Genre not set")}
          </p>
        </div>
        <BookStatusPill status={book.status} />
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
        <Field label="ISBN">{orText(book.isbn, "Not assigned yet")}</Field>
        <Field label="Publication date">{formatDate(book.publication_date, "Not published yet")}</Field>
        <Field label="MRP">{formatINR(book.mrp, "Not assigned")}</Field>
        <Field label="Copies sold">{book.total_copies_sold.toLocaleString("en-IN")}</Field>
        <Field label="Royalty / copy">{formatINR(book.author_royalty_per_copy, "Not assigned")}</Field>
        <Field label="Print partner">{orText(book.print_partner, "Not assigned")}</Field>
      </dl>

      <div className="mt-4 grid grid-cols-3 gap-3 rounded-lg bg-slate-50 p-3 text-center">
        <div>
          <p className="text-[11px] text-slate-500">Earned</p>
          <p className="text-sm font-bold">{formatRoyalty(book.total_royalty_earned)}</p>
        </div>
        <div>
          <p className="text-[11px] text-slate-500">Paid</p>
          <p className="text-sm font-bold text-emerald-700">{formatRoyalty(book.royalty_paid)}</p>
        </div>
        <div>
          <p className="text-[11px] text-slate-500">Pending</p>
          <p className="text-sm font-bold text-amber-700">{formatRoyalty(book.royalty_pending)}</p>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500">Last payout: {formatDate(book.last_royalty_payout_date, "No payout yet")}</p>

      <div className="mt-3">
        <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Available on</p>
        {book.available_on.length === 0 ? (
          <p className="mt-1 text-sm text-slate-500">Not listed on any platform yet</p>
        ) : (
          <div className="mt-1 flex flex-wrap gap-1.5">
            {book.available_on.map((p) => (
              <span key={p} className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{p}</span>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
