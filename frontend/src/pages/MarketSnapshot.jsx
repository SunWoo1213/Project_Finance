import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, BarChart3 } from "lucide-react";

import { apiClient } from "../utils/apiClient";
import { resolveAssetName } from "../utils/constants";
import { formatChangeBadge, formatPrice, formatTicker } from "../utils/formatters";

const SNAPSHOT_META = {
  "^GSPC": {
    dashboardTitle: "미국 주식 대쉬보드",
    dashboardPath: "/category/us_top10",
    dashboardDescription: "S&P 500과 함께 미국 대형주 흐름을 확인합니다.",
    category: "US_STOCK",
  },
  "^NDX": {
    dashboardTitle: "미국 주식 대쉬보드",
    dashboardPath: "/category/us_top10",
    dashboardDescription: "Nasdaq 100과 함께 미국 성장주 흐름을 확인합니다.",
    category: "US_STOCK",
  },
  "KRW=X": {
    dashboardTitle: "주요 지수·환율 대쉬보드",
    dashboardPath: "/category/macro",
    dashboardDescription: "원/달러 환율과 글로벌 지수 흐름을 함께 봅니다.",
    category: "FX",
  },
  "^KS11": {
    dashboardTitle: "한국 주식 대쉬보드",
    dashboardPath: "/category/kr_top10",
    dashboardDescription: "KOSPI와 함께 국내 대표 종목 흐름을 확인합니다.",
    category: "KR_STOCK",
  },
};

const normalizeTicker = (value) => {
  try {
    return decodeURIComponent(String(value || "").trim());
  } catch {
    return String(value || "").trim();
  }
};

export default function MarketSnapshot() {
  const { ticker } = useParams();
  const assetTicker = normalizeTicker(ticker);
  const meta = SNAPSHOT_META[assetTicker] || {
    dashboardTitle: "전체 자산 대쉬보드",
    dashboardPath: "/category/macro",
    dashboardDescription: "관련 시장 데이터를 확인합니다.",
    category: "US_STOCK",
  };

  const [marketInfo, setMarketInfo] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchSnapshot = async () => {
      setIsLoading(true);
      try {
        const priceRes = await apiClient.get("/api/market/prices");

        let matched = null;
        Object.values(priceRes.data || {}).some((group) =>
          Object.values(group || {}).some((info) => {
            if (info.symbol === assetTicker) {
              matched = info;
              return true;
            }
            return false;
          })
        );

        setMarketInfo(matched);
      } catch (error) {
        console.error("Failed to load market snapshot:", error);
        setMarketInfo(null);
      } finally {
        setIsLoading(false);
      }
    };

    if (assetTicker) {
      fetchSnapshot();
    }
  }, [assetTicker]);

  const changeValue = marketInfo?.changePercent ?? marketInfo?.change_pct ?? 0;
  const badge = formatChangeBadge(changeValue);
  const displayName = resolveAssetName(assetTicker, marketInfo?.symbol, assetTicker);

  if (isLoading) {
    return <div className="py-20 text-center text-slate-400">시세 데이터를 불러오는 중입니다...</div>;
  }

  if (!marketInfo) {
    return <div className="py-20 text-center text-slate-400">해당 자산의 시세 데이터가 없습니다.</div>;
  }

  return (
    <div className="mx-auto flex max-w-screen-md flex-col gap-8 px-4 py-8">
      <section>
        <div className="mb-2 text-sm font-semibold text-emerald-400">현재 시세</div>
        <h1 className="text-3xl font-bold text-slate-100">
          {displayName}
          <span className="ml-2 align-middle text-lg font-medium text-slate-400">({formatTicker(assetTicker)})</span>
        </h1>
        <div className="mt-3 flex flex-wrap items-end gap-4">
          <span className="text-4xl font-extrabold text-slate-100">{formatPrice(marketInfo.price, meta.category)}</span>
          <span className={`pb-1 text-xl font-bold ${badge.className}`}>{badge.text}</span>
        </div>
      </section>

      <section>
        <Link
          to={meta.dashboardPath}
          className="flex items-center justify-between gap-4 rounded-2xl border border-slate-700 bg-slate-800 p-5 transition hover:border-emerald-400/70 hover:bg-slate-700"
        >
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-300">
              <BarChart3 size={23} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-100">{meta.dashboardTitle}</h2>
              <p className="mt-1 text-sm leading-6 text-slate-400">{meta.dashboardDescription}</p>
            </div>
          </div>
          <ArrowRight size={21} className="shrink-0 text-slate-400" />
        </Link>
      </section>
    </div>
  );
}
