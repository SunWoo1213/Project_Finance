import React, { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, BarChart3 } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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

const toHourlyPoints = (points) => {
  if (!Array.isArray(points)) return [];

  const byHour = new Map();
  points.forEach((point) => {
    const rawDate = String(point.date || "");
    const hourKey = rawDate.includes(" ") ? rawDate.slice(0, 13) : rawDate;
    byHour.set(hourKey, {
      date: rawDate,
      time: rawDate.includes(" ") ? rawDate.slice(11, 16) : rawDate,
      value: Number(point.value ?? point.close),
    });
  });

  return Array.from(byHour.values()).filter((point) => Number.isFinite(point.value));
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
  const [chartData, setChartData] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchSnapshot = async () => {
      setIsLoading(true);
      try {
        const [priceRes, historyRes] = await Promise.all([
          apiClient.get("/api/market/prices"),
          apiClient.get(`/api/market/history/${encodeURIComponent(assetTicker)}?period=1d`),
        ]);

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

        const points = Array.isArray(historyRes.data?.points)
          ? historyRes.data.points
          : Array.isArray(historyRes.data?.legacy)
          ? historyRes.data.legacy
          : [];

        setMarketInfo(matched);
        setChartData(toHourlyPoints(points));
      } catch (error) {
        console.error("Failed to load market snapshot:", error);
        setMarketInfo(null);
        setChartData([]);
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
  const strokeColor = changeValue >= 0 ? "#ef4444" : "#3b82f6";
  const displayName = resolveAssetName(assetTicker, marketInfo?.symbol, assetTicker);

  const latestPoint = useMemo(() => chartData.at(-1), [chartData]);

  if (isLoading) {
    return <div className="py-20 text-center text-slate-400">시간 단위 데이터를 불러오는 중입니다...</div>;
  }

  if (!marketInfo) {
    return <div className="py-20 text-center text-slate-400">해당 자산의 시세 데이터가 없습니다.</div>;
  }

  return (
    <div className="mx-auto flex max-w-screen-md flex-col gap-8 px-4 py-8">
      <section>
        <div className="mb-5">
          <div className="mb-2 text-sm font-semibold text-emerald-400">시간 단위 변화</div>
          <h1 className="text-3xl font-bold text-slate-100">
            {displayName}
            <span className="ml-2 align-middle text-lg font-medium text-slate-400">({formatTicker(assetTicker)})</span>
          </h1>
          <div className="mt-3 flex flex-wrap items-end gap-4">
            <span className="text-4xl font-extrabold text-slate-100">{formatPrice(marketInfo.price, meta.category)}</span>
            <span className={`pb-1 text-xl font-bold ${badge.className}`}>{badge.text}</span>
          </div>
        </div>

        <div className="relative flex h-[420px] flex-col rounded-2xl border border-slate-700 bg-slate-800/60 p-5 shadow-inner">
          <div className="mb-4 flex items-center justify-between gap-3 text-sm text-slate-400">
            <span>1일 장중 데이터</span>
            {latestPoint && <span>최근 {latestPoint.time}</span>}
          </div>

          <div className="h-[330px] w-full">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 20, right: 28, left: 6, bottom: 8 }}>
                  <XAxis dataKey="time" stroke="#94a3b8" tick={{ fontSize: 12 }} minTickGap={24} />
                  <YAxis
                    domain={["dataMin", "dataMax"]}
                    orientation="right"
                    axisLine={false}
                    tickLine={false}
                    stroke="#94a3b8"
                    tickFormatter={(value) => formatPrice(value, meta.category)}
                    tick={{ fontSize: 12 }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1e293b",
                      border: "none",
                      borderRadius: "8px",
                      color: "#f8fafc",
                    }}
                    itemStyle={{ color: strokeColor }}
                    formatter={(value) => [formatPrice(value, meta.category), "Price"]}
                    labelFormatter={(value) => `시간 ${value}`}
                  />
                  <Line type="monotone" dataKey="value" stroke={strokeColor} strokeWidth={3} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-slate-400">시간 단위 차트 데이터가 없습니다.</div>
            )}
          </div>
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
