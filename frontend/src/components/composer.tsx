import { useState } from "react";
import { ArrowUp, LoaderCircle, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function Composer({ busy, hasFormValues = false, onSend, onStop }: {
  busy: boolean;
  hasFormValues?: boolean;
  onSend: (text: string) => void | Promise<void>;
  onStop?: () => void;
}) {
  const [text, setText] = useState("");
  const canSend = Boolean(text.trim() || hasFormValues);

  return (
    <div className="shrink-0 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 sm:px-8 sm:pb-6">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!canSend || busy) return;
          const input = text.trim();
          setText("");
          void onSend(input);
        }}
        className="pure-capsule mx-auto flex max-w-2xl items-center gap-2 rounded-full p-1.5 pl-4 sm:pl-5 transition-all duration-200 focus-within:shadow-[0_12px_40px_-6px_rgba(25,35,28,0.1)] focus-within:bg-white/95"
      >
        <Textarea
          aria-label="旅行需求"
          placeholder="写下关于这次旅行的任何想法…"
          rows={1}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
          className="max-h-32 min-h-6 flex-1 resize-none border-0 bg-transparent py-1 text-sm leading-relaxed shadow-none focus-visible:ring-0 placeholder:text-muted-foreground/45"
        />
        {busy && onStop ? (
          <Button type="button" size="icon" variant="ghost" onClick={onStop}
            className="size-9 shrink-0 rounded-full bg-black/[0.04] text-foreground hover:bg-black/[0.08]">
            <span className="sr-only">停止</span>
            <Square className="size-3 fill-current" />
          </Button>
        ) : (
          <Button type="submit" size="icon" disabled={!canSend || busy}
            className="size-9 shrink-0 rounded-full bg-primary text-white shadow-xs hover:bg-primary/95 transition-all duration-200 active:scale-95 disabled:opacity-30 disabled:pointer-events-none">
            <span className="sr-only">发送</span>
            {busy ? <LoaderCircle className="size-4 animate-spin" /> : <ArrowUp className="size-4 stroke-[2.2]" />}
          </Button>
        )}
      </form>
    </div>
  );
}
