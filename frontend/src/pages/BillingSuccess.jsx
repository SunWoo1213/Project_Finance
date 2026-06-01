import { useEffect } from "react";
import { Link } from "react-router-dom";

import useAuthStore from "../store/authStore";
import useSubscriptionStore from "../store/subscriptionStore";

export default function BillingSuccess() {
  const { token } = useAuthStore();
  const { fetchMe, tier, status, isLoading } = useSubscriptionStore();

  useEffect(() => {
    if (token) {
      fetchMe(token);
    }
  }, [fetchMe, token]);

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center">
      <div className="rounded-2xl border border-slate-700 bg-slate-800/70 p-8">
        <h1 className="text-2xl font-bold text-slate-50">결제 확인 중입니다</h1>
        <p className="mt-4 text-sm leading-6 text-slate-300">
          결제 성공 페이지에 도착해도 권한은 결제 제공자의 webhook으로 확인된 서버 상태를 기준으로 반영됩니다.
        </p>
        <div className="mt-5 rounded-xl bg-slate-900/60 p-4 text-sm text-slate-300">
          {isLoading ? "구독 상태를 다시 확인하고 있습니다..." : `현재 상태: ${tier} / ${status}`}
        </div>
        <Link
          to="/"
          className="mt-6 inline-flex rounded-xl bg-emerald-500 px-5 py-3 text-sm font-bold text-slate-950 transition-colors hover:bg-emerald-400"
        >
          홈으로 이동
        </Link>
      </div>
    </div>
  );
}
