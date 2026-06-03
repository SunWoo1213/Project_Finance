import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ExternalLink, Newspaper } from 'lucide-react';
import { apiClient } from '../utils/apiClient';
import { formatPrice, formatPercent } from '../utils/formatters';

export default function Home() {
  const [marketData, setMarketData] = useState(null);
  const [globalNews, setGlobalNews] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [priceResult, newsResult] = await Promise.allSettled([
          apiClient.get('/api/market/prices'),
          apiClient.get('/api/market/news'),
        ]);

        if (priceResult.status !== 'fulfilled') {
          throw priceResult.reason;
        }

        const indices = priceResult.value.data.macro || {};
        const newsPayload = newsResult.status === 'fulfilled' ? newsResult.value.data : {};
        const newsItems = Object.values(newsPayload || {})
          .flatMap((group) => Object.entries(group || {}))
          .flatMap(([label, payload]) =>
            (payload.items || []).map((item) => ({
              ...item,
              assetLabel: label,
              symbol: payload.symbol,
            }))
          )
          .filter((item) => item.title || item.link);
        const dedupedNews = Array.from(
          new Map(newsItems.map((item) => [item.link || `${item.assetLabel}:${item.title}`, item])).values()
        );
        setMarketData(indices);
        setGlobalNews(dedupedNews.slice(0, 8));
      } catch (error) {
        console.error('Failed to fetch market data:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  const targetIndices = [
    { label: 'S&P 500', dataKey: 'S&P 500', ticker: '^GSPC', category: 'US_STOCK' },
    { label: 'Nasdaq 100', dataKey: 'Nasdaq 100', ticker: '^NDX', category: 'US_STOCK' },
    { label: '원/달러 환율', dataKey: 'USDKRW', ticker: 'KRW=X', category: 'FX' },
    { label: 'KOSPI', dataKey: 'KOSPI', ticker: '^KS11', category: 'KR_STOCK' }
  ];

  if (isLoading) {
    return <div className="text-center py-20 text-slate-400">Loading market data...</div>;
  }

  return (
    <div className="max-w-screen-xl mx-auto py-8">
      <h2 className="text-2xl font-bold mb-6 px-2">주요 지수·환율</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 px-2">
        {targetIndices.map(({ label, dataKey, ticker, category }) => {
          const data = marketData ? marketData[dataKey] : null;
          if (!data) return null;

          const isPositive = data.change_pct >= 0;
          const colorClass = isPositive ? 'text-red-500' : 'text-blue-500';

          return (
            <div
              key={ticker}
              onClick={() => navigate(`/market/${encodeURIComponent(ticker)}`)}
              className="bg-slate-800 rounded-2xl p-5 hover:bg-slate-700 cursor-pointer transition shadow-lg flex items-center justify-between"
            >
              <div>
                <h3 className="text-lg font-bold text-slate-200">{label}</h3>
                <div className="text-2xl font-bold mt-1">
                  {formatPrice(data.price, category)}
                </div>
              </div>
              <div className={`text-xl font-semibold ${colorClass}`}>
                {formatPercent(data.change_pct)}
              </div>
            </div>
          );
        })}
      </div>

      <section className="mt-10 px-2">
        <div className="mb-4 flex items-center gap-2">
          <Newspaper size={22} className="text-emerald-400" />
          <h2 className="text-2xl font-bold">세계 주요 글로벌 뉴스</h2>
        </div>

        {globalNews.length === 0 ? (
          <div className="rounded-2xl border border-slate-700 bg-slate-800/60 p-6 text-center text-slate-400">
            표시할 글로벌 뉴스가 없습니다.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {globalNews.map((item, index) => (
              <a
                key={`${item.link || item.title}-${index}`}
                href={item.link || '#'}
                target="_blank"
                rel="noreferrer"
                className="rounded-xl border border-slate-700 bg-slate-800/70 p-4 transition hover:border-emerald-400/70 hover:bg-slate-800"
              >
                <div className="mb-2 flex items-start justify-between gap-3">
                  <h3 className="line-clamp-2 text-sm font-semibold leading-6 text-slate-100">{item.title}</h3>
                  {item.link && <ExternalLink size={15} className="mt-1 shrink-0 text-slate-500" />}
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                  <span>{item.source || 'unknown'}</span>
                  {item.assetLabel && <span>· {item.assetLabel}</span>}
                </div>
              </a>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
