export const ASSET_NAMES = {
  // Indices
  "^GSPC": "S&P 500",
  "^NDX": "나스닥 100",
  "^KS11": "코스피",
  "^KQ11": "코스닥",

  // Crypto
  "BTC-USD": "비트코인",
  "ETH-USD": "이더리움",
  "SOL-USD": "솔라나",
  "Bitcoin": "비트코인",
  "Ethereum": "이더리움",

  // Commodities
  "GC=F": "금 (Gold)",
  "SI=F": "은 (Silver)",
  "CL=F": "WTI 원유",
  "XAU": "금 (Gold)",
  "XAG": "은 (Silver)",
  "Gold": "금 (Gold)",
  "Silver": "은 (Silver)",

  // US bonds / yields
  "^IRX": "미국 3개월물 국채",
  "^FVX": "미국 5년물 국채",
  "^TNX": "미국 10년물 국채",
  "^TYX": "미국 30년물 국채",
  "DGS2MO": "미국 2개월물 국채",
  "DGS1": "미국 1년물 국채",
  "DGS10": "미국 10년물 국채",
  "DGS30": "미국 30년물 국채",
  "US 2M Treasury": "미국 2개월물 국채",
  "US 1Y Treasury": "미국 1년물 국채",
  "US 10Y Treasury": "미국 10년물 국채",
  "US 30Y Treasury": "미국 30년물 국채",

  // KR bonds (ECOS item code)
  "0101500": "한국 1년물 국채",
  "0102000": "한국 10년물 국채",
  "KR_BOND_1Y": "한국 1년물 국채",
  "KR_BOND_3Y": "한국 3년물 국채",
  "KR_BOND_10Y": "한국 10년물 국채",
  "KTB_1Y": "한국 1년물 국고채 수익률",
  "KTB_3Y": "한국 3년물 국고채 수익률",
  "KTB_5Y": "한국 5년물 국고채 수익률",
  "KTB_10Y": "한국 10년물 국고채 수익률",
  "KTB_20Y": "한국 20년물 국고채 수익률",
  "KR 1Y Treasury": "한국 1년물 국채",
  "KR 10Y Treasury": "한국 10년물 국채",

  // US stocks
  "AAPL": "애플",
  "MSFT": "마이크로소프트",
  "NVDA": "엔비디아",
  "GOOGL": "알파벳",
  "AMZN": "아마존",
  "META": "메타",
  "BRK-B": "버크셔 해서웨이",
  "LLY": "일라이 릴리",
  "AVGO": "브로드컴",
  "TSLA": "테슬라",

  // KR stocks
  "005930": "삼성전자",
  "000660": "SK하이닉스",
  "373220": "LG에너지솔루션",
  "207940": "삼성바이오로직스",
  "005380": "현대차",
  "000270": "기아",
  "068270": "셀트리온",
  "005490": "POSCO홀딩스",
  "035420": "NAVER",
  "105560": "KB금융",
  "005930.KS": "삼성전자",
  "000660.KS": "SK하이닉스",
  "373220.KS": "LG에너지솔루션",
  "207940.KS": "삼성바이오로직스",
  "005380.KS": "현대차",
  "000270.KS": "기아",
  "068270.KS": "셀트리온",
  "005490.KS": "POSCO홀딩스",
  "035420.KS": "NAVER",
  "105560.KS": "KB금융",
  "Samsung Electronics": "삼성전자",
  "SK Hynix": "SK하이닉스",
  "LG Energy Solution": "LG에너지솔루션",
  "Samsung Biologics": "삼성바이오로직스",
  "Hyundai Motor": "현대차",
  "Kia": "기아",
  "Celltrion": "셀트리온",
  "POSCO Holdings": "POSCO홀딩스",
  "KB Financial Group": "KB금융",
};

export const resolveAssetName = (...keys) => {
  for (const key of keys) {
    if (!key) continue;
    if (ASSET_NAMES[key]) return ASSET_NAMES[key];
    const stripped = String(key).replace(".KS", "").replace(".KQ", "");
    if (ASSET_NAMES[stripped]) return ASSET_NAMES[stripped];
  }
  const fallback = keys.find(Boolean);
  return fallback ? String(fallback).replace(".KS", "").replace(".KQ", "") : "";
};
