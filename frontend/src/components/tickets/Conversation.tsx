import { Sparkles } from "lucide-react";
import { useEffect, useRef } from "react";

import type { AdminMessage, Message } from "../../types";
import { cn } from "../../utils/cn";
import { formatDateTime } from "../../utils/format";

type AnyMessage = Message | AdminMessage;

/** `viewer` decides which side is "me". Admins additionally see the AI-assisted marker. */
export function Conversation({ messages, viewer }: { messages: AnyMessage[]; viewer: "AUTHOR" | "ADMIN" }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }, [messages.length]);

  if (messages.length === 0) {
    return <p className="px-2 py-6 text-center text-sm text-slate-500">No replies yet. The support team will respond here.</p>;
  }
  return (
    <ul className="space-y-3" aria-live="polite" aria-label="Conversation">
      {messages.map((m) => {
        const mine = m.sender_role === viewer;
        const aiAssisted = viewer === "ADMIN" && "is_ai_assisted" in m && m.is_ai_assisted;
        return (
          <li key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
            <div className={cn("max-w-[85%] rounded-2xl px-4 py-2.5 text-sm shadow-sm", mine ? "rounded-br-sm bg-brand-600 text-white" : "rounded-bl-sm border border-slate-200 bg-white text-slate-800")}>
              <p className={cn("mb-1 flex items-center gap-1.5 text-[11px] font-semibold", mine ? "text-brand-100" : "text-slate-500")}>
                {m.sender_label} · {formatDateTime(m.created_at)}
                {aiAssisted && (
                  <span className="inline-flex items-center gap-0.5 rounded bg-white/20 px-1 py-0.5 text-[10px]"><Sparkles className="h-3 w-3" /> AI-assisted</span>
                )}
              </p>
              <p className="whitespace-pre-wrap break-words">{m.message}</p>
            </div>
          </li>
        );
      })}
      <div ref={endRef} />
    </ul>
  );
}
