import { useEffect, useState } from "react";
import toast from "react-hot-toast";

import PlanBadge from "../components/PlanBadge";
import useAuthStore from "../store/authStore";
import useSubscriptionStore from "../store/subscriptionStore";
import { apiClient, authHeader } from "../utils/apiClient";

const FALLBACK_PLANS = [
  {
    tier: "FREE",
    name: "Free",
    monthly_price_krw: 0,
    can_view_reports: false,
    can_use_chatbot: false,
    description: "시장 데이터와 커뮤니티 읽기 중심의 기본 플랜입니다.",
  },
  {
    tier: "PLUS",
    name: "Plus",
    monthly_price_krw: 1000,
    can_view_reports: true,
    can_use_chatbot: false,
    description: "저장된 스케줄 AI 리포트를 볼 수 있습니다.",
  },
  {
    tier: "PRO",
    name: "Pro",
    monthly_price_krw: 3000,
    can_view_reports: true,
    can_use_chatbot: true,
    description: "AI 리포트와 챗봇을 모두 사용할 수 있습니다.",
  },
];

function formatPrice(value) {
  return `${Number(value || 0).toLocaleString("ko-KR")}원`;
}

export default function Pricing() {
  const { token } = useAuthStore();
  const { tier: currentTier } = useSubscriptionStore();
  const [plans, setPlans] = useState(FALLBACK_PLANS);
  const [isLoading, setIsLoading] = useState(true);
  const [checkoutTier, setCheckoutTier] = useState(null);

  useEffect(() => {
    const loadPlans = async () => {
      try {
        const { data } = await apiClient.get("/api/billing/plans");
        setPlans(Array.isArray(data) ? data : FALLBACK_PLANS);
      } catch (error) {
        console.error("Failed to load billing plans:", error);
        setPlans(FALLBACK_PLANS);
      } finally {
        setIsLoading(false);
      }
    };

    loadPlans();
  }, []);

  const startCheckout = async (planTier) => {
    if (!token) {
      toast.error("로그인 후 구독을 시작할 수 있습니다.");
      return;
    }
    if (planTier === "FREE") return;

    setCheckoutTier(planTier);
    try {
      const { data } = await apiClient.post(
        "/api/billing/checkout",
        {
          tier: planTier,
          success_url: `${window.location.origin}/billing/success`,
          cancel_url: `${window.location.origin}/billing/cancel`,
        },
        { headers: authHeader(token) }
      );
      if (data?.checkout_url) {
        window.location.assign(data.checkout_url);
        return;
      }
      toast("결제 세션을 만들었지만 이동할 URL이 없습니다.");
    } catch (error) {
      if (error?.response?.status === 503) {
        toast.error("결제 제공자 설정이 아직 준비되지 않았습니다.");
      } else {
        toast.error(error?.response?.data?.detail || "결제 준비가 아직 완료되지 않았습니다.");
      }
    } finally {
      setCheckoutTier(null);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-50">요금제</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
          AI 리포트는 저장된 스케줄 리포트만 제공하며, 사용자 요청이나 결제 상태 변경이 새 리포트 생성을 트리거하지 않습니다.
        </p>
      </div>

      {isLoading ? (
        <div className="rounded-2xl border border-slate-700 bg-slate-800/60 p-8 text-center text-slate-300">
          요금제를 불러오는 중입니다...
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {plans.map((plan) => {
            const isCurrent = plan.tier === currentTier;
            const isPaid = plan.tier !== "FREE";
            return (
              <section key={plan.tier} className="flex flex-col rounded-2xl border border-slate-700 bg-slate-800/70 p-5">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <h2 className="text-xl font-bold text-slate-50">{plan.name}</h2>
                  <PlanBadge tier={plan.tier} />
                </div>
                <div className="mb-4">
                  <span className="text-3xl font-extrabold text-slate-50">{formatPrice(plan.monthly_price_krw)}</span>
                  <span className="ml-1 text-sm text-slate-400">/ 월</span>
                </div>
                <p className="min-h-12 text-sm leading-6 text-slate-300">{plan.description}</p>
                <div className="mt-5 space-y-2 text-sm text-slate-300">
                  <div>{plan.can_view_reports ? "AI 리포트 이용 가능" : "AI 리포트 이용 불가"}</div>
                  <div>{plan.can_use_chatbot ? "챗봇 이용 가능" : "챗봇 이용 불가"}</div>
                </div>
                <button
                  type="button"
                  disabled={!isPaid || isCurrent || checkoutTier === plan.tier}
                  onClick={() => startCheckout(plan.tier)}
                  className="mt-6 rounded-xl bg-emerald-500 px-4 py-3 text-sm font-bold text-slate-950 transition-colors hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                >
                  {isCurrent ? "현재 플랜" : isPaid ? (checkoutTier === plan.tier ? "준비 중..." : "구독 시작") : "기본 플랜"}
                </button>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
