import { Send } from "lucide-react";
import { useState } from "react";

import { getErrorMessage } from "../../api/client";
import { Button, FieldError } from "../common/ui";

interface Props {
  onSend: (message: string) => Promise<unknown>;
  disabled?: boolean;
  disabledReason?: string;
  placeholder?: string;
}

export function MessageComposer({ onSend, disabled, disabledReason, placeholder = "Write a reply…" }: Props) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string>();

  if (disabled) return <p className="rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-600">{disabledReason}</p>;

  const submit = async () => {
    if (!text.trim()) return;
    setSending(true);
    setError(undefined);
    try {
      await onSend(text.trim());
      setText("");
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSending(false);
    }
  };

  return (
    <div>
      <label htmlFor="reply" className="sr-only">Reply</label>
      <textarea id="reply" className="input min-h-[96px]" value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder} maxLength={5000} />
      <FieldError message={error} />
      <div className="mt-2 flex justify-end">
        <Button onClick={submit} loading={sending} disabled={!text.trim()}>
          <Send className="h-4 w-4" /> Send
        </Button>
      </div>
    </div>
  );
}
