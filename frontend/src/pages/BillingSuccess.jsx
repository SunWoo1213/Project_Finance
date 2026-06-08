import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import useAuthStore from "../store/authStore";
import useSubscriptionStore from "../store/subscriptionStore";
import { apiClient, authHeader } from "../utils/apiClient";

export default function BillingSuccess() {
  const { token } = useAuthStore();
  const { fetchMe, tier, status, isLoading } = useSubscriptionStore();
  const [searchParams] = useSearchParams();
  const [pollCount, setPollCount] = useState(0);
  const [finalizeMessage, setFinalizeMessage] = useState("");
  const [finalizeAttempted, setFinalizeAttempted] = useState(false);

  const isActivePaid = useMemo(() => ["PLUS", "PRO"].includes(tier) && status === "ACTIVE", [status, tier]);
  const tossAuthParams = useMemo(
    () => ({
      provider: searchParams.get("provider"),
      intentId: searchParams.get("intent_id"),
      authKey: searchParams.get("authKey"),
      customerKey: searchParams.get("customerKey"),
    }),
    [searchParams]
  );

  useEffect(() => {
    const isTossRedirect =
      tossAuthParams.provider === "toss" && tossAuthParams.intentId && tossAuthParams.authKey && tossAuthParams.customerKey;
    if (!token || !isTossRedirect || finalizeAttempted) {
      return;
    }

    let canceled = false;
    const finalizeTossBilling = async () => {
      setFinalizeAttempted(true);
      try {
        await apiClient.post(
          "/api/billing/toss/billing-key",
          {
            intent_id: tossAuthParams.intentId,
            authKey: tossAuthParams.authKey,
            customerKey: tossAuthParams.customerKey,
          },
          { headers: authHeader(token) }
        );
        if (!canceled) {
          setFinalizeMessage("결제 승인 결과를 확인했습니다.");
          await fetchMe(token);
        }
      } catch (error) {
        if (!canceled) {
          setFinalizeMessage(error?.response?.data?.detail || "결제 인증 후 서버 승인 단계가 완료되지 않았습니다.");
        }
      }
    };

    finalizeTossBilling();

    return () => {
      canceled = true;
    };
  }, [fetchMe, finalizeAttempted, token, tossAuthParams]);

  useEffect(() => {
    if (!token || isActivePaid || pollCount >= 6) {
      return undefined;
    }

    let canceled = false;
    const timeoutId = window.setTimeout(async () => {
      if (canceled) return;
      await fetchMe(token);
      setPollCount((count) => count + 1);
    }, pollCount === 0 ? 0 : 3000);

    return () => {
      canceled = true;
      window.clearTimeout(timeoutId);
    };
  }, [fetchMe, isActivePaid, pollCount, token]);

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center">
      <div className="rounded-2xl border border-slate-700 bg-slate-800/70 p-8">
        <h1 className="text-2xl font-bold text-slate-50">결제 확인 중입니다</h1>
        <p className="mt-4 text-sm leading-6 text-slate-300">
          결제 성공 페이지에 도착해도 권한은 결제 제공자의 webhook으로 확인된 서버 상태를 기준으로 반영됩니다.
        </p>
        {finalizeMessage && (
          <div className="mt-5 rounded-xl border border-amber-400/30 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
            {finalizeMessage}
          </div>
        )}
        <div className="mt-5 rounded-xl bg-slate-900/60 p-4 text-sm text-slate-300">
          {isLoading
            ? "구독 상태를 다시 확인하고 있습니다..."
            : isActivePaid
              ? `구독이 활성화되었습니다: ${tier} / ${status}`
              : `확인 대기 중입니다: ${tier} / ${status}`}
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
