import { create } from 'zustand';

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
        };
        localStorage.setItem('token', token);
        localStorage.setItem('user', JSON.stringify(nextUser));
        set({ token, user: nextUser });
    },
    logout: () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        set({ token: null, user: null });
    }
}));

export default useAuthStore;
