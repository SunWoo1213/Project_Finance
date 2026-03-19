import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { formatTicker } from '../utils/formatters';
import { resolveAssetName } from '../utils/constants';

export default function PriceCard({ selectedTicker, priceInfo, isLoading }) {
  if (isLoading || !priceInfo) {
    return (
      <div className="bg-slate-800 rounded-[2rem] p-8 shadow-2xl relative overflow-hidden group">
        <div className="animate-pulse flex flex-col gap-4">
          <div className="h-6 w-32 bg-slate-700 rounded"></div>
          <div className="h-16 w-48 bg-slate-700 rounded"></div>
          <div className="h-8 w-24 bg-slate-700 rounded-full"></div>
        </div>
      </div>
    );
  }

  const { price, change_pct } = priceInfo;
  
  const isPositive = change_pct > 0;
  const isNegative = change_pct < 0;
  
  const colorClass = isPositive ? 'text-red-500' : isNegative ? 'text-blue-500' : 'text-slate-400';
  const bgColorClass = isPositive ? 'bg-red-500/10' : isNegative ? 'bg-blue-500/10' : 'bg-slate-500/10';
  const effectColorClass = isPositive ? 'bg-red-500/20' : isNegative ? 'bg-blue-500/20' : 'bg-slate-500/20';
  const Icon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;
  
  return (
    <div className="bg-slate-800 rounded-[2rem] p-8 shadow-2xl relative overflow-hidden group">
      <div className={`absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 rounded-full ${effectColorClass} blur-3xl opacity-50 group-hover:opacity-70 transition-all duration-500`} />
      
      <div className="relative z-10 flex flex-col gap-2">
        <span className="text-slate-400 font-medium tracking-wide">
          {resolveAssetName(selectedTicker, formatTicker(selectedTicker))}
        </span>
        
        <div className="flex items-baseline gap-4 mt-2">
          <h2 className="text-6xl font-extrabold tracking-tight text-white">
            {price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </h2>
        </div>

        <div className={`inline-flex items-center gap-1.5 mt-2 ${bgColorClass} ${colorClass} px-3 py-1.5 rounded-full w-fit`}>
          <Icon size={18} strokeWidth={2.5} />
          <span className="font-bold">{change_pct > 0 ? '+' : ''}{change_pct.toFixed(2)}%</span>
        </div>
      </div>
    </div>
  );
}
