import { useEffect, useRef, useState } from "react";
import { Loader2, RotateCcw, Send, Trash2, X } from "lucide-react";

import useChatStore from "../store/chatStore";
import ChatMessageList from "./ChatMessageList";

const SUGGESTIONS = ["삼성전자 보고서 보여줘", "오늘 환율 어디서 봐?", "미국 주식 TOP10 보여줘", "댓글은 어떻게 남겨?"];

export default function ChatbotPanel({ chatContext, token, onClose, onAction }) {
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);
  const { messages, isSending, error, sendMessage, retryLast, clear } = useChatStore();

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isSending, error]);

  const submitMessage = async (value = input) => {
    const text = value.trim();
    if (!text) return;
    setInput("");
    await sendMessage(text, chatContext, token);
  };

  return (
    <section className="fixed inset-x-3 bottom-20 z-50 flex max-h-[78vh] flex-col overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl shadow-black/40 sm:inset-x-auto sm:right-6 sm:w-[400px]">
      <header className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <div>
          <h2 className="text-sm font-bold text-slate-100">Project Finance 챗봇</h2>
          <p className="text-xs text-slate-500">금융 데이터와 앱 이동을 도와드립니다.</p>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={clear}
            className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100"
            title="대화 지우기"
          >
            <Trash2 size={17} />
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100"
            title="닫기"
          >
            <X size={18} />
          </button>
        </div>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <ChatMessageList messages={messages} onAction={onAction} />

        {messages.length <= 1 && (
          <div className="mt-4 grid gap-2">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => submitMessage(suggestion)}
                className="rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2 text-left text-xs text-slate-300 transition-colors hover:border-emerald-400/60 hover:text-slate-100"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        {isSending && (
          <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-400">
            <Loader2 size={14} className="animate-spin" />
            답변을 준비하는 중입니다.
          </div>
        )}

        {error && (
          <div className="mt-3 rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100">
            <p>{typeof error === "string" ? error : "응답을 불러오지 못했습니다. 다시 시도해주세요."}</p>
            <button
              type="button"
              onClick={retryLast}
              disabled={isSending}
              className="mt-2 inline-flex items-center gap-2 rounded-lg bg-red-400/20 px-3 py-1.5 text-xs font-semibold text-red-100 hover:bg-red-400/30 disabled:opacity-50"
            >
              <RotateCcw size={14} />
              다시 시도
            </button>
          </div>
        )}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          submitMessage();
        }}
        className="border-t border-slate-800 bg-slate-950 p-3"
      >
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="예: 테슬라 리포트 보여줘"
            disabled={isSending}
            className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 outline-none transition-colors focus:border-emerald-400 disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={isSending || !input.trim()}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500 text-slate-950 transition-colors hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
            title="보내기"
          >
            {isSending ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </div>
      </form>
    </section>
  );
}
