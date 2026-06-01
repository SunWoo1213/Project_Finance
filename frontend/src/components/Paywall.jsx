import { Link } from "react-router-dom";

export default function Paywall({
  title = "구독이 필요한 기능입니다.",
  description = "Plus 또는 Pro 플랜에서 저장된 AI 리포트를 확인할 수 있습니다.",
  actionLabel = "요금제 보기",
  showLogin = false,
}) {
  return (
    <div className="relative z-20 w-full max-w-md rounded-2xl border border-emerald-300/30 bg-slate-900/95 p-6 text-center shadow-2xl shadow-black/30">
      <h3 className="text-xl font-bold text-slate-50">{title}</h3>
      <p className="mt-3 text-sm leading-6 text-slate-300">{description}</p>
      <div className="mt-5 flex flex-wrap justify-center gap-3">
        {showLogin && (
          <Link
            to="/login"
            className="rounded-xl bg-emerald-500 px-5 py-3 text-sm font-bold text-slate-950 transition-colors hover:bg-emerald-400"
          >
            로그인
          </Link>
        )}
        <Link
          to="/pricing"
          className="rounded-xl border border-slate-600 px-5 py-3 text-sm font-bold text-slate-100 transition-colors hover:border-emerald-300 hover:text-emerald-200"
        >
          {actionLabel}
        </Link>
      </div>
    </div>
  );
}
