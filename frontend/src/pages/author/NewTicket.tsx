import { zodResolver } from "@hookform/resolvers/zod";
import { Paperclip } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { getErrorMessage } from "../../api/client";
import { Button, Card, FieldError, PageHeader } from "../../components/common/ui";
import { useBooks } from "../../features/author/queries";
import { useCreateTicket } from "../../features/tickets/queries";

const GENERAL = "__general__";

const schema = z.object({
  book: z.string().min(1, "Choose a book or General / Account Level"),
  subject: z.string().trim().min(3, "Subject must be at least 3 characters").max(300),
  description: z.string().trim().min(10, "Please describe your query in at least 10 characters").max(5000),
});
type FormValues = z.infer<typeof schema>;

export default function NewTicket() {
  const navigate = useNavigate();
  const books = useBooks();
  const create = useCreateTicket();
  const [fileName, setFileName] = useState<string>();
  const [serverError, setServerError] = useState<string>();
  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { book: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(undefined);
    try {
      const ticket = await create.mutateAsync({
        book_id: values.book === GENERAL ? null : values.book,
        subject: values.subject,
        description: values.description,
      });
      navigate(`/author/tickets/${ticket.ticket_id}`);
    } catch (e) {
      setServerError(getErrorMessage(e));
    }
  });

  return (
    <>
      <PageHeader title="Submit a support query" description="Tell us what you need. Our team (with a little AI help) will get back to you." />
      <Card className="max-w-2xl p-6">
        <form onSubmit={onSubmit} noValidate className="space-y-5">
          <div>
            <label htmlFor="book" className="label">Which book is this about?</label>
            <select id="book" className="input" {...register("book")} disabled={books.isLoading}>
              <option value="">Select…</option>
              <option value={GENERAL}>General / Account Level</option>
              {books.data?.map((b) => <option key={b.book_id} value={b.book_id}>{b.title} ({b.book_id})</option>)}
            </select>
            <FieldError message={errors.book?.message} />
          </div>
          <div>
            <label htmlFor="subject" className="label">Subject</label>
            <input id="subject" className="input" placeholder="e.g. ISBN on Amazon doesn't match my book" {...register("subject")} />
            <FieldError message={errors.subject?.message} />
          </div>
          <div>
            <label htmlFor="description" className="label">Details</label>
            <textarea id="description" className="input min-h-[160px]" placeholder="What happened, and what outcome are you hoping for?" {...register("description")} />
            <FieldError message={errors.description?.message} />
          </div>
          <div>
            <span className="label">Attachment (optional)</span>
            <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-slate-300 px-3 py-3 text-sm text-slate-600 hover:bg-slate-50">
              <Paperclip className="h-4 w-4" />
              {fileName ?? "Choose a photo or document"}
              <input type="file" className="sr-only" onChange={(e) => setFileName(e.target.files?.[0]?.name)} />
            </label>
            <p className="mt-1 text-xs text-slate-500">Attachment upload isn't enabled in this version. Mention what you'd attach in your description and the team will follow up.</p>
          </div>
          {serverError && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{serverError}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => navigate(-1)}>Cancel</Button>
            <Button type="submit" loading={create.isPending}>Submit query</Button>
          </div>
        </form>
      </Card>
    </>
  );
}
