import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import SparklineChart from '../components/SparklineChart';
import { formatChangeBadge, formatMarketCap, formatPrice, formatTicker } from '../utils/formatters';
import { resolveAssetName } from '../utils/constants';

export default function CategoryView({ categoryKey, title }) {
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const response = await axios.get('http://localhost:8000/api/market/prices');
        const categoryData = response.data[categoryKey] || {};
        
        const list = Object.entries(categoryData).map(([label, info]) => ({
          label,
          ...info
        }));
        
        list.sort((a, b) => (b.marketCap || 0) - (a.marketCap || 0));
        setItems(list);
      } catch (error) {
        console.error(`Failed to fetch ${title} data:`, error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [categoryKey, title]);

  if (isLoading) {
    return <div className="text-center py-20 text-slate-400">Loading {title}...</div>;
  }

  const uiCategory =
    categoryKey === 'kr_top10'
      ? 'KR_STOCK'
      : categoryKey === 'bonds'
      ? 'US_BOND'
      : categoryKey === 'commodities'
      ? 'COMMODITY'
      : 'US_STOCK';

  return (
    <div className="max-w-screen-xl mx-auto py-8 px-4">
      <h2 className="text-2xl font-bold mb-6">{title}</h2>
      <div className="flex flex-col gap-3">
        {items.map((data) => {
          const changeValue = data.changePercent ?? data.change_pct ?? 0;
          const badge = formatChangeBadge(changeValue);
          const strokeColor = changeValue >= 0 ? '#ef4444' : '#3b82f6';
          const marketCap = Number(data.marketCap ?? 0);
          const isMacro = marketCap <= 0 || uiCategory === 'US_BOND' || uiCategory === 'COMMODITY';

          return (
            <div 
              key={data.symbol}
              onClick={() => navigate(`/detail/${data.symbol}`)}
              className="bg-slate-800 rounded-xl p-4 hover:bg-slate-700 cursor-pointer transition shadow-md flex items-center justify-between"
            >
              <div className="flex flex-col w-1/4">
                <h3 className="text-lg font-bold text-slate-200">
                  {resolveAssetName(data.symbol, data.label)}
                </h3>
                <span className="text-sm text-slate-400">{formatTicker(data.symbol)}</span>
              </div>
              
              <div className="h-12 w-1/3">
                <SparklineChart data={data.history_prices} color={strokeColor} />
              </div>

              <div className="flex flex-col items-end w-1/4">
                <div className="text-lg font-bold">
                  {formatPrice(data.price, uiCategory)}
                </div>
                <div className={`text-sm font-semibold ${badge.className}`}>
                  {badge.text}
                </div>
                {isMacro ? (
                  <div className="mt-1 rounded-full bg-slate-700 px-2 py-0.5 text-[11px] text-slate-300">
                    거시 지표
                  </div>
                ) : (
                  <div className="text-xs text-slate-400 mt-1">
                    {formatMarketCap(marketCap, uiCategory)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
