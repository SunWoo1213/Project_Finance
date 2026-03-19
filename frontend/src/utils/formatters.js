export const formatPrice = (value, category = "US_STOCK") => {
  if (value === null || value === undefined) return "";
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);

  if (category === "US_BOND" || category === "KR_BOND") {
    return `${num.toFixed(3)}%`;
  }

  if (category === "COMMODITY") {
    return `$${num.toFixed(2)}`;
  }

  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
};

export const formatPercent = (value) => {
  if (value === null || value === undefined) return "";
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  const formatted = Math.abs(num).toFixed(2);
  const sign = num > 0 ? "+" : num < 0 ? "-" : "";
  return `${sign}${formatted}%`;
};

export const formatChangeBadge = (value) => {
  const num = Number(value ?? 0);
  const absText = `${Math.abs(num).toFixed(2)}%`;
  if (num > 0) return { text: `▲ ${absText}`, className: "text-red-500" };
  if (num < 0) return { text: `▼ ${absText}`, className: "text-blue-500" };
  return { text: `0.00%`, className: "text-slate-400" };
};

export const formatMarketCap = (value, category = "US_STOCK") => {
  if (value === null || value === undefined || Number(value) === 0) return "-";
  const num = Number(value);
  if (Number.isNaN(num) || num <= 0) return "-";

  if (category === "KR_STOCK") {
    if (num >= 1e12) return `${(num / 1e12).toFixed(2)}조 ₩`;
    if (num >= 1e8) return `${(num / 1e8).toFixed(0)}억 ₩`;
    return `${num.toLocaleString("ko-KR")}원`;
  }

  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
  return `$${num.toLocaleString("en-US")}`;
};

export const formatTicker = (ticker) => {
  if (!ticker) return "";
  return String(ticker).replace(".KS", "").replace(".KQ", "");
};
