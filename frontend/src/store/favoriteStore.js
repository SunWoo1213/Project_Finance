import { create } from 'zustand';

const STORAGE_KEY = 'favoriteAssets';

const normalizeSymbol = (symbol) => String(symbol || '').trim();

const normalizeFavorite = (asset) => {
  const symbol = normalizeSymbol(asset?.symbol);
  if (!symbol) return null;

  return {
    symbol,
    name: asset?.name || asset?.label || symbol,
    categoryKey: asset?.categoryKey || null,
  };
};

const readStoredFavorites = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    if (!Array.isArray(parsed)) return [];

    return parsed.map(normalizeFavorite).filter(Boolean);
  } catch {
    return [];
  }
};

const writeStoredFavorites = (favorites) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
};

const useFavoriteStore = create((set, get) => ({
  favorites: readStoredFavorites(),
  isFavorite: (symbol) => {
    const normalized = normalizeSymbol(symbol);
    return get().favorites.some((favorite) => favorite.symbol === normalized);
  },
  toggleFavorite: (asset) => {
    const favorite = normalizeFavorite(asset);
    if (!favorite) return;

    const exists = get().favorites.some((item) => item.symbol === favorite.symbol);
    const favorites = exists
      ? get().favorites.filter((item) => item.symbol !== favorite.symbol)
      : [favorite, ...get().favorites.filter((item) => item.symbol !== favorite.symbol)];

    writeStoredFavorites(favorites);
    set({ favorites });
  },
  removeFavorite: (symbol) => {
    const normalized = normalizeSymbol(symbol);
    const favorites = get().favorites.filter((item) => item.symbol !== normalized);
    writeStoredFavorites(favorites);
    set({ favorites });
  },
}));

export default useFavoriteStore;
