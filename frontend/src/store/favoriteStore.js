import { create } from 'zustand';
import { apiClient, authHeader } from '../utils/apiClient';

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

const fromServerFavorite = (favorite) =>
  normalizeFavorite({
    symbol: favorite?.symbol,
    name: favorite?.name,
    categoryKey: favorite?.categoryKey,
  });

const getStoredToken = () => localStorage.getItem('token') || null;

const useFavoriteStore = create((set, get) => ({
  favorites: readStoredFavorites(),
  isSyncing: false,
  syncError: null,
  isFavorite: (symbol) => {
    const normalized = normalizeSymbol(symbol);
    return get().favorites.some((favorite) => favorite.symbol === normalized);
  },
  syncWithServer: async (token) => {
    if (!token) {
      set({ isSyncing: false, syncError: null });
      return get().favorites;
    }

    set({ isSyncing: true, syncError: null });
    try {
      const localFavorites = readStoredFavorites();
      const endpoint = localFavorites.length > 0 ? '/api/favorites/import-local' : '/api/favorites';
      const options = { headers: authHeader(token) };
      const response = localFavorites.length > 0
        ? await apiClient.post(endpoint, { favorites: localFavorites }, options)
        : await apiClient.get(endpoint, options);
      const favorites = response.data.map(fromServerFavorite).filter(Boolean);
      writeStoredFavorites(favorites);
      set({ favorites, isSyncing: false, syncError: null });
      return favorites;
    } catch (error) {
      set({
        isSyncing: false,
        syncError: error?.response?.data?.detail || '즐겨찾기를 동기화하지 못했습니다.',
      });
      return get().favorites;
    }
  },
  toggleFavorite: async (asset) => {
    const favorite = normalizeFavorite(asset);
    if (!favorite) return;

    const exists = get().favorites.some((item) => item.symbol === favorite.symbol);
    const favorites = exists
      ? get().favorites.filter((item) => item.symbol !== favorite.symbol)
      : [favorite, ...get().favorites.filter((item) => item.symbol !== favorite.symbol)];

    writeStoredFavorites(favorites);
    set({ favorites });

    const token = getStoredToken();
    if (!token) return;

    try {
      if (exists) {
        await apiClient.delete(`/api/favorites/${encodeURIComponent(favorite.symbol)}`, {
          headers: authHeader(token),
        });
      } else {
        await apiClient.post(
          '/api/favorites',
          {
            symbol: favorite.symbol,
            name: favorite.name,
            categoryKey: favorite.categoryKey,
            source: 'manual',
          },
          { headers: authHeader(token) }
        );
      }
      set({ syncError: null });
    } catch (error) {
      set({ syncError: error?.response?.data?.detail || '즐겨찾기 서버 반영에 실패했습니다.' });
    }
  },
  addFavorite: async (asset) => {
    const favorite = normalizeFavorite(asset);
    if (!favorite) return;

    const favorites = [favorite, ...get().favorites.filter((item) => item.symbol !== favorite.symbol)];
    writeStoredFavorites(favorites);
    set({ favorites });

    const token = getStoredToken();
    if (!token) return;

    try {
      await apiClient.post(
        '/api/favorites',
        {
          symbol: favorite.symbol,
          name: favorite.name,
          categoryKey: favorite.categoryKey,
          source: 'manual',
        },
        { headers: authHeader(token) }
      );
      set({ syncError: null });
    } catch (error) {
      set({ syncError: error?.response?.data?.detail || '즐겨찾기 서버 반영에 실패했습니다.' });
    }
  },
  removeFavorite: async (symbol) => {
    const normalized = normalizeSymbol(symbol);
    const favorites = get().favorites.filter((item) => item.symbol !== normalized);
    writeStoredFavorites(favorites);
    set({ favorites });

    const token = getStoredToken();
    if (!token || !normalized) return;

    try {
      await apiClient.delete(`/api/favorites/${encodeURIComponent(normalized)}`, {
        headers: authHeader(token),
      });
      set({ syncError: null });
    } catch (error) {
      set({ syncError: error?.response?.data?.detail || '즐겨찾기 서버 반영에 실패했습니다.' });
    }
  },
}));

export default useFavoriteStore;
