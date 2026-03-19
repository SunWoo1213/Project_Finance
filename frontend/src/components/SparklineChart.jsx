import React from 'react';
import { LineChart, Line, ResponsiveContainer, YAxis, Tooltip } from 'recharts';
import { formatPrice } from '../utils/formatters';

export default function SparklineChart({ data, color }) {
  if (!data || data.length === 0) return null;

  const chartData = data.map((value, index) => ({ value, index }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={chartData}>
        <YAxis domain={['dataMin', 'dataMax']} hide />
        <Tooltip formatter={(value) => [formatPrice(value), "Price"]} labelFormatter={() => ""} contentStyle={{ fontSize: '10px', padding: '2px 5px' }} />
        <Line 
          type="monotone" 
          dataKey="value"  
          stroke={color} 
          strokeWidth={2} 
          dot={false} 
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
