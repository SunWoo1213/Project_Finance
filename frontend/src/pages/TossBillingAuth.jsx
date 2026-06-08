import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import useAuthStore from "../store/authStore";
import { apiClient, authHeader } from "../utils/apiClient";
import { loadTossPaymentsSdk } from "../utils/tossPayments";

export default function TossBillingAuth() {
  const { token } = useAuthStore();
  const [searchParams] = useSearchParams();
  const intentId = searchParams.get("intent_id") || "";
  const [statusText, setStatusText] = useState("결제 인증을 준비하고 있습니다...");
  const [errorText, setErrorText] = useState("");

  const canStart = useMemo(() => Boolean(token && intentId), [intentId, token]);

  useEffect(() => {
    if (!token) {
      setErrorText("로그인 후 결제 인증을 계속할 수 있습니다.");
      return undefined;
    }
    if (!intentId) {
      setErrorText("결제 인증 정보가 없습니다.");
      return undefined;
    }

    let canceled = false;

    const startBillingAuth = async () => {
      try {
        const { data } = await apiClient.get(`/api/billing/checkout/${encodeURIComponent(intentId)}`, {
          headers: authHeader(token),
        });
        if (canceled) return;

        setStatusText("토스페이먼츠 결제창을 여는 중입니다...");
        const TossPayments = await loadTossPaymentsSdk();
        if (!TossPayments) {
          throw new Error("Toss Payments SDK is unavailable.");
        }

        const tossPayments = TossPayments(data.client_key);
        const payment = tossPayments.payment({ customerKey: data.customer_key });
        await payment.requestBillingAuth({
          method: "CARD",
          successUrl: data.success_url,
          failUrl: data.fail_url,
        });
      } catch (error) {
        if (canceled) return;
        const detail = error?.response?.data?.detail;
        setErrorText(detail || "토스페이먼츠 결제 인증을 시작하지 못했습니다.");
      }
    };

    startBillingAuth();

    return () => {
      canceled = true;
    };
  }, [intentId, token]);

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center">
      <div className="rounded-2xl border border-slate-700 bg-slate-800/70 p-8">
        <h1 className="text-2xl font-bold text-slate-50">토스페이먼츠 결제 인증</h1>
        <p className="mt-4 text-sm leading-6 text-slate-300">
          {errorText || (canStart ? statusText : "결제 인증을 계속할 수 없습니다.")}
        </p>
        {errorText && (
          <Link
            to="/pricing"
            className="mt-6 inline-flex rounded-xl bg-emerald-500 px-5 py-3 text-sm font-bold text-slate-950 transition-colors hover:bg-emerald-400"
          >
            요금제로 돌아가기
          </Link>
        )}
      </div>
    </div>
  );
}
