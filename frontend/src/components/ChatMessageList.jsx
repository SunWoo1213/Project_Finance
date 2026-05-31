import ChatActionCard from "./ChatActionCard";

export default function ChatMessageList({ messages, onAction }) {
  return (
    <div className="flex flex-col gap-3">
      {messages.map((message) => {
        const isUser = message.role === "user";
        return (
          <div key={message.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[88%] rounded-2xl px-3 py-2 text-sm leading-6 shadow-sm ${
                isUser
                  ? "rounded-br-md bg-emerald-500 text-slate-950"
                  : "rounded-bl-md border border-slate-700 bg-slate-800 text-slate-100"
              }`}
            >
              <p className="whitespace-pre-wrap">{message.content}</p>

              {!isUser && message.cards?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {message.cards.slice(0, 4).map((card) => (
                    <span
                      key={`${card.type}-${card.ticker || card.route || card.name}`}
                      className="rounded-full bg-slate-900/80 px-2.5 py-1 text-xs text-slate-300"
                    >
                      {card.name || card.ticker || card.category}
                    </span>
                  ))}
                </div>
              )}

              {!isUser && message.actions?.length > 0 && (
                <div className="mt-3 space-y-2">
                  {message.actions.map((action, index) => (
                    <ChatActionCard key={`${action.label}-${index}`} action={action} onAction={onAction} />
                  ))}
                </div>
              )}

              {!isUser && message.disclaimer && <p className="mt-3 text-[11px] leading-5 text-slate-500">{message.disclaimer}</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
