import { Lock } from "lucide-react";
import { useState } from "react";

import { getErrorMessage } from "../../api/client";
import type { InternalNote } from "../../types";
import { formatDateTime } from "../../utils/format";
import { Button, Card, CardHeader, FieldError } from "../common/ui";

interface Props {
  notes: InternalNote[];
  onAdd: (note: string) => Promise<unknown>;
}

export function InternalNotes({ notes, onAdd }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const add = async () => {
    setBusy(true);
    setError(undefined);
    try {
      await onAdd(text.trim());
      setText("");
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="border-amber-200">
      <CardHeader title={<span className="inline-flex items-center gap-1.5"><Lock className="h-4 w-4 text-amber-600" /> Internal notes</span>} subtitle="Visible to support staff only — never shown to authors." />
      <div className="space-y-3 p-5">
        {notes.length === 0 && <p className="text-sm text-slate-500">No internal notes yet.</p>}
        {notes.map((n) => (
          <div key={n.id} className="rounded-lg bg-amber-50 px-3 py-2 text-sm">
            <p className="whitespace-pre-wrap text-slate-800">{n.note}</p>
            <p className="mt-1 text-[11px] text-amber-800/70">{n.admin_email} · {formatDateTime(n.created_at)}</p>
          </div>
        ))}
        <label htmlFor="note" className="sr-only">Add internal note</label>
        <textarea id="note" className="input min-h-[72px]" placeholder="Add an internal note…" value={text} onChange={(e) => setText(e.target.value)} maxLength={3000} />
        <FieldError message={error} />
        <div className="flex justify-end">
          <Button variant="secondary" onClick={add} loading={busy} disabled={!text.trim()}>Add note</Button>
        </div>
      </div>
    </Card>
  );
}
