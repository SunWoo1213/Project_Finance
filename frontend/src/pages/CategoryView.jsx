import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Star } from 'lucide-react';
import SparklineChart from '../components/SparklineChart';
import useAuthStore from '../store/authStore';
import useFavoriteStore from '../store/favoriteStore';
import { apiClient } from '../utils/apiClient';
import { getUiCategory } from '../utils/assetCategories';
import { formatChangeBadge, formatMarketCap, formatPrice, formatTicker } from '../utils/formatters';
import { resolveAssetName } from '../utils/constants';

export default function CategoryView({ categoryKey, title }) {
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const { token } = useAuthStore();
  const { favorites, isFavorite, toggleFavorite, removeFavorite, isSyncing, syncError } = useFavoriteStore();

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const response = await apiClient.get('/api/market/prices');
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

  return (
    <div className="max-w-screen-xl mx-auto py-8 px-4">
      <h2 className="text-2xl font-bold mb-6">{title}</h2>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="flex flex-col gap-3">
          {items.map((data) => {
            const uiCategory = getUiCategory(categoryKey, data.symbol);
            const changeValue = data.changePercent ?? data.change_pct ?? 0;
            const badge = formatChangeBadge(changeValue);
            const strokeColor = changeValue >= 0 ? '#ef4444' : '#3b82f6';
            const marketCap = Number(data.marketCap ?? 0);
            const isMacro = marketCap <= 0 || uiCategory === 'US_BOND' || uiCategory === 'COMMODITY';
            const displayName = resolveAssetName(data.symbol, data.label);
            const favorited = isFavorite(data.symbol);

            return (
              <div 
                key={data.symbol}
                onClick={() => navigate(`/detail/${encodeURIComponent(data.symbol)}`)}
                className="flex cursor-pointer items-center gap-4 rounded-xl bg-slate-800 p-4 shadow-md transition hover:bg-slate-700"
              >
                <div className="flex min-w-0 flex-1 flex-col">
                  <h3 className="truncate text-lg font-bold text-slate-200">
                    {displayName}
                  </h3>
                  <span className="text-sm text-slate-400">{formatTicker(data.symbol)}</span>
                </div>
                
                <div className="hidden h-12 min-w-40 flex-[1.4] sm:block">
                  <SparklineChart data={data.history_prices} color={strokeColor} category={uiCategory} />
                </div>

                <div className="flex min-w-32 flex-col items-end">
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
                    <div className="mt-1 text-xs text-slate-400">
                      {formatMarketCap(marketCap, uiCategory)}
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  aria-pressed={favorited}
                  title={favorited ? '즐겨찾기 해제' : '즐겨찾기 추가'}
                  onClick={(event) => {
                    event.stopPropagation();
                    toggleFavorite({
                      symbol: data.symbol,
                      name: displayName,
                      categoryKey,
                    });
                  }}
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border transition-colors ${
                    favorited
                      ? 'border-amber-300/60 bg-amber-300/10 text-amber-300'
                      : 'border-slate-600 text-slate-400 hover:border-amber-300/60 hover:text-amber-300'
                  }`}
                >
                  <Star size={19} fill={favorited ? 'currentColor' : 'none'} />
                </button>
              </div>
            );
          })}
        </div>

        <aside className="self-start rounded-xl border border-slate-700 bg-slate-800/70 p-4 lg:sticky lg:top-6">
          <div className="mb-3 flex items-center gap-2">
            <Star size={18} className="text-amber-300" fill="currentColor" />
            <h3 className="text-base font-bold text-slate-100">즐겨찾기</h3>
          </div>

          {token && (
            <div className="mb-3 rounded-lg border border-slate-700/70 bg-slate-900/35 p-3 text-xs text-slate-400">
              <div>{isSyncing ? '계정 즐겨찾기 동기화 중...' : '계정 즐겨찾기와 동기화됩니다.'}</div>
              {syncError && <div className="mt-1 text-amber-300">{syncError}</div>}
              <Link to="/mypage" className="mt-2 inline-flex text-emerald-300 hover:text-emerald-200">
                알림 설정
              </Link>
            </div>
          )}

          {favorites.length === 0 ? (
            <p className="py-6 text-sm leading-6 text-slate-400">
              자산 오른쪽 별을 눌러 관심 자산을 모아보세요.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {favorites.map((favorite) => (
                <div
                  key={favorite.symbol}
                  className="group flex items-center gap-2 rounded-lg border border-slate-700/70 bg-slate-900/35 p-3 transition-colors hover:border-emerald-400/60"
                >
                  <button
                    type="button"
                    onClick={() => navigate(`/detail/${encodeURIComponent(favorite.symbol)}`)}
                    className="min-w-0 flex-1 text-left"
                  >
                    <div className="truncate text-sm font-semibold text-slate-100">
                      {resolveAssetName(favorite.symbol, favorite.name)}
                    </div>
                    <div className="mt-0.5 text-xs text-slate-500">{formatTicker(favorite.symbol)}</div>
                  </button>
                  <button
                    type="button"
                    title="즐겨찾기 해제"
                    onClick={() => removeFavorite(favorite.symbol)}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-amber-300 transition-colors hover:bg-slate-700"
                  >
                    <Star size={16} fill="currentColor" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
