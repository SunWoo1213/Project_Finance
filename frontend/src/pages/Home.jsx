import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import SparklineChart from '../components/SparklineChart';
import { formatPrice, formatPercent } from '../utils/formatters';

export default function Home() {
  const [marketData, setMarketData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/market/prices');
        const indices = response.data.macro || {};
        setMarketData(indices);
      } catch (error) {
        console.error('Failed to fetch market data:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  const targetIndices = [
    { label: 'S&P 500', ticker: '^GSPC' },
    { label: 'Nasdaq 100', ticker: '^NDX' },
    { label: 'KOSPI', ticker: '^KS11' },
    { label: 'KOSDAQ', ticker: '^KQ11' }
  ];

  if (isLoading) {
    return <div className="text-center py-20 text-slate-400">Loading market data...</div>;
  }

  return (
    <div className="max-w-screen-xl mx-auto py-8">
      <h2 className="text-2xl font-bold mb-6 px-2">주요 지수</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 px-2">
        {targetIndices.map(({ label, ticker }) => {
          const data = marketData ? marketData[label] : null;
          if (!data) return null;

          const isPositive = data.change_pct >= 0;
          const colorClass = isPositive ? 'text-red-500' : 'text-blue-500';
          const strokeColor = isPositive ? '#ef4444' : '#3b82f6';

          return (
            <div 
              key={ticker}
              onClick={() => navigate(`/detail/${ticker}`)}
              className="bg-slate-800 rounded-2xl p-5 hover:bg-slate-700 cursor-pointer transition shadow-lg flex flex-col justify-between"
            >
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-lg font-bold text-slate-200">{label}</h3>
                  <div className="text-xl font-bold mt-1">
                    {formatPrice(data.price)}
                  </div>
                </div>
                <div className={`text-lg font-semibold ${colorClass}`}>
                  {formatPercent(data.change_pct)}
                </div>
              </div>
              
              <div className="h-24 w-full">
                <SparklineChart data={data.history_prices} color={strokeColor} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
