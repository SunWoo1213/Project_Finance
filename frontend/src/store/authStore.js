import { create } from 'zustand';

import useFavoriteStore from './favoriteStore';

const getUserIdFromToken = (token) => {
    if (!token) return null;
    try {
        const encodedPayload = (token.split('.')[1] || '').replace(/-/g, '+').replace(/_/g, '/');
        const paddedPayload = encodedPayload.padEnd(encodedPayload.length + ((4 - (encodedPayload.length % 4)) % 4), '=');
        const payload = JSON.parse(atob(paddedPayload));
        const id = Number(payload?.sub);
        return Number.isFinite(id) ? id : null;
    } catch {
        return null;
    }
};

const getInitialUser = () => {
    try {
        const stored = localStorage.getItem('user');
        if (!stored) return null;
        const user = JSON.parse(stored);
        if (user?.id) return user;
        const id = getUserIdFromToken(localStorage.getItem('token'));
        return id ? { ...user, id } : user;
    } catch {
        return null;
    }
};

const useAuthStore = create((set) => ({
    token: localStorage.getItem('token') || null,
    user: getInitialUser(),
    login: (token, user) => {
        const nextUser = {
            ...user,
            id: user?.id ?? getUserIdFromToken(token),
            nickname_confirmed: Boolean(user?.nickname_confirmed || user?.profile_complete),
            profile_complete: Boolean(user?.profile_complete || user?.nickname_confirmed),
        };
        localStorage.setItem('token', token);
        localStorage.setItem('user', JSON.stringify(nextUser));
        set({ token, user: nextUser });
    },
    updateUser: (patch) => {
        set((state) => {
            const nextUser = {
                ...(state.user || {}),
                ...patch,
                nickname_confirmed: Boolean(patch?.nickname_confirmed ?? patch?.profile_complete ?? state.user?.nickname_confirmed),
                profile_complete: Boolean(patch?.profile_complete ?? patch?.nickname_confirmed ?? state.user?.profile_complete),
            };
            localStorage.setItem('user', JSON.stringify(nextUser));
            return { user: nextUser };
        });
    },
    logout: () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        set({ token: null, user: null });
        useFavoriteStore.getState().clearFavorites();
    }
}));

export default useAuthStore;
