import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";

import useAuthStore from "../store/authStore";
import useSubscriptionStore from "../store/subscriptionStore";

export default function BillingCancel() {
  const { token } = useAuthStore();
  const { fetchMe, tier, status, isLoading } = useSubscriptionStore();
  const [searchParams] = useSearchParams();
  const failCode = searchParams.get("code");
  const failMessage = searchParams.get("message");

  useEffect(() => {
    if (token) {
      fetchMe(token);
    }
  }, [fetchMe, token]);

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center">
      <div className="rounded-2xl border border-slate-700 bg-slate-800/70 p-8">
        <h1 className="text-2xl font-bold text-slate-50">결제가 중단되었습니다</h1>
        <p className="mt-4 text-sm leading-6 text-slate-300">
          결제가 완료되지 않았거나 사용자가 결제 화면을 닫았습니다. 현재 구독 권한은 변경되지 않습니다.
        </p>
        {(failCode || failMessage) && (
          <div className="mt-5 rounded-xl border border-amber-400/30 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
            {[failCode, failMessage].filter(Boolean).join(" / ")}
          </div>
        )}
        <div className="mt-5 rounded-xl bg-slate-900/60 p-4 text-sm text-slate-300">
          {isLoading ? "현재 구독 상태를 확인하고 있습니다..." : `현재 상태: ${tier} / ${status}`}
        </div>
        <div className="mt-6 flex justify-center gap-3">
          <Link
            to="/pricing"
            className="rounded-xl bg-emerald-500 px-5 py-3 text-sm font-bold text-slate-950 transition-colors hover:bg-emerald-400"
          >
            요금제 다시 보기
          </Link>
          <Link
            to="/"
            className="rounded-xl border border-slate-600 px-5 py-3 text-sm font-bold text-slate-100 transition-colors hover:border-emerald-300 hover:text-emerald-200"
          >
            홈으로 이동
          </Link>
        </div>
      </div>
    </div>
  );
}
