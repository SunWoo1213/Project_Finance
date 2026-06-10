import { create } from "zustand";

import { apiClient, authHeader } from "../utils/apiClient";

const defaultEntitlements = {
  can_view_reports: false,
  can_use_chatbot: false,
  can_use_notifications: false,
};

const initialState = {
  tier: "FREE",
  status: "NONE",
  currentPeriodStart: null,
  currentPeriodEnd: null,
  cancelAtPeriodEnd: false,
  entitlements: defaultEntitlements,
  isLoading: false,
  error: null,
};

const useSubscriptionStore = create((set) => ({
  ...initialState,
  clear: () => set({ ...initialState }),
  fetchMe: async (token) => {
    if (!token) {
      set({ ...initialState });
      return null;
    }

    set({ isLoading: true, error: null });
    try {
      const { data } = await apiClient.get("/api/billing/me", {
        headers: authHeader(token),
      });
      const entitlements = data.entitlements || defaultEntitlements;
      set({
        tier: data.tier || "FREE",
        status: data.status || "NONE",
        currentPeriodStart: data.current_period_start || null,
        currentPeriodEnd: data.current_period_end || null,
        cancelAtPeriodEnd: Boolean(data.cancel_at_period_end),
        entitlements,
        isLoading: false,
        error: null,
      });
      return data;
    } catch (error) {
      set({
        ...initialState,
        error: error?.response?.data?.detail || "구독 정보를 불러오지 못했습니다.",
      });
      return null;
    }
  },
}));

export default useSubscriptionStore;
