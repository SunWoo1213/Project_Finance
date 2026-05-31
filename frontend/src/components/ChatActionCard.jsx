import { ArrowRight, LockKeyhole } from "lucide-react";

export default function ChatActionCard({ action, onAction }) {
  if (!action) return null;

  return (
    <button
      type="button"
      onClick={() => onAction(action)}
      disabled={!action.url}
      className="group flex w-full items-start justify-between gap-3 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-left transition-colors hover:border-emerald-400/70 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
    >
      <span className="min-w-0">
        <span className="flex items-center gap-2 text-sm font-semibold text-slate-100">
          {action.requires_auth && <LockKeyhole size={14} className="shrink-0 text-amber-300" />}
          {action.label}
        </span>
        {action.reason && <span className="mt-1 block text-xs leading-5 text-slate-400">{action.reason}</span>}
      </span>
      <ArrowRight size={16} className="mt-1 shrink-0 text-slate-500 transition-colors group-hover:text-emerald-300" />
    </button>
  );
}
