export const getUiCategory = (categoryKey, symbol) => {
  const normalizedSymbol = String(symbol || "").toUpperCase();

  if (categoryKey === "kr_top10") return "KR_STOCK";
  if (categoryKey === "cryptos") return "CRYPTO";
  if (categoryKey === "bonds") return normalizedSymbol.startsWith("KTB_") ? "KR_BOND" : "US_BOND";
  if (categoryKey === "commodities") return "COMMODITY";
  if (categoryKey === "macro" && normalizedSymbol === "KRW=X") return "FX";
  if (categoryKey === "macro" && normalizedSymbol === "^KS11") return "KR_STOCK";

  return "US_STOCK";
};
