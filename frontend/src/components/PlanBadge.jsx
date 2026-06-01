const BADGE_STYLES = {
  FREE: "border-slate-600 bg-slate-800 text-slate-300",
  PLUS: "border-cyan-300/60 bg-cyan-300/10 text-cyan-200",
  PRO: "border-emerald-300/60 bg-emerald-300/10 text-emerald-200",
};

export default function PlanBadge({ tier = "FREE", isLoading = false }) {
  const label = isLoading ? "확인 중" : tier;
  const className = BADGE_STYLES[tier] || BADGE_STYLES.FREE;

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold ${className}`}>
      {label}
    </span>
  );
}
