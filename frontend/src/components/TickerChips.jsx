import { formatTicker } from '../utils/formatters';
import { resolveAssetName } from '../utils/constants';

export default function TickerChips({ marketData, selectedTicker, setSelectedTicker }) {
  if (!marketData) {
    return (
      <div className="overflow-x-auto whitespace-nowrap hide-scrollbar py-2 px-2 -mx-2">
        <div className="flex gap-3">
          <div className="animate-pulse w-24 h-10 bg-slate-800 rounded-full"></div>
          <div className="animate-pulse w-24 h-10 bg-slate-800 rounded-full"></div>
          <div className="animate-pulse w-24 h-10 bg-slate-800 rounded-full"></div>
        </div>
      </div>
    );
  }

  const tickers = Object.keys(marketData);

  return (
    <div className="overflow-x-auto whitespace-nowrap hide-scrollbar py-2 px-2 -mx-2">
      <div className="flex gap-3">
        {tickers.map(ticker => (
          <button
            key={ticker}
            onClick={() => setSelectedTicker(ticker)}
            className={`px-5 py-2.5 rounded-full font-semibold transition-all duration-300 
              ${selectedTicker === ticker 
                ? 'bg-slate-50 text-slate-900 shadow-md transform scale-105' 
                : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200'}`}
          >
            {resolveAssetName(ticker, formatTicker(ticker))}
          </button>
        ))}
      </div>
    </div>
  );
}
