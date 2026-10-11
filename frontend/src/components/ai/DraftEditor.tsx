import { AlertTriangle, RefreshCw, Send, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { getErrorMessage } from "../../api/client";
import type { AIDraft } from "../../types";
import { textSimilarity } from "../../utils/format";
import { Button, Card, CardHeader, FieldError } from "../common/ui";

/** A reply counts as AI-assisted while it still resembles the draft (edits are fine, a rewrite is not). */
const ASSISTED_THRESHOLD = 0.3;

interface Props {
  draft: AIDraft | null;
  disabled?: boolean;
  onSend: (message: string, aiDraftId: number | null) => Promise<unknown>;
  onRegenerate: () => Promise<unknown>;
}

export function DraftEditor({ draft, disabled, onSend, onRegenerate }: Props) {
  const [text, setText] = useState(draft?.draft ?? "");
  const [sending, setSending] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string>();

  // A new draft (regeneration / first arrival) replaces the editor content.
  useEffect(() => {
    setText(draft?.draft ?? "");
  }, [draft?.id, draft?.draft]);

  const assisted = draft !== null && text.trim().length > 0 && textSimilarity(text, draft.draft) >= ASSISTED_THRESHOLD;

  const run = async (action: () => Promise<unknown>, setBusy: (b: boolean) => void) => {
    setBusy(true);
    setError(undefined);
    try {
      await action();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const send = () =>
    run(async () => {
      await onSend(text.trim(), assisted ? draft!.id : null);
      setText("");
    }, setSending);

  return (
    <Card>
      <CardHeader
        title={<span className="inline-flex items-center gap-1.5"><Sparkles className="h-4 w-4 text-brand-600" /> Response draft</span>}
        subtitle="Review and edit before sending. Nothing is sent to the author automatically."
        action={draft && <span className="text-xs text-slate-400">{draft.model} · {draft.prompt_version}</span>}
      />
      <div className="p-5">
        {draft && draft.grounding_warnings.length > 0 && (
          <div role="alert" className="mb-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="flex items-center gap-1.5 font-semibold"><AlertTriangle className="h-4 w-4" /> Verify before sending</p>
            <ul className="mt-1 list-disc pl-5">{draft.grounding_warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          </div>
        )}
        {!draft && <p className="mb-3 text-sm text-slate-500">No AI draft available. Write your response manually, or regenerate a draft.</p>}
        <label htmlFor="draft" className="sr-only">Response to author</label>
        <textarea id="draft" className="input min-h-[200px] font-[inherit] leading-relaxed" value={text} onChange={(e) => setText(e.target.value)} disabled={disabled} maxLength={5000} placeholder="Write your response to the author…" />
        <FieldError message={error} />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <Button variant="secondary" onClick={() => run(onRegenerate, setRegenerating)} loading={regenerating} disabled={disabled}>
            <RefreshCw className="h-4 w-4" /> {draft ? "Regenerate" : "Generate draft"}
          </Button>
          <div className="flex items-center gap-3">
            {assisted && <span className="text-xs text-slate-500">Will be recorded as AI-assisted</span>}
            <Button onClick={send} loading={sending} disabled={disabled || !text.trim()}>
              <Send className="h-4 w-4" /> Send response
            </Button>
          </div>
        </div>
        {disabled && <p className="mt-2 text-xs text-slate-500">This ticket is closed. Reopen it to respond.</p>}
      </div>
    </Card>
  );
}
