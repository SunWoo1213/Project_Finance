import { create } from 'zustand';

const getInitialUser = () => {
    try {
        const stored = localStorage.getItem('user');
        return stored ? JSON.parse(stored) : null;
    } catch {
        return null;
    }
};

const useAuthStore = create((set) => ({
    token: localStorage.getItem('token') || null,
    user: getInitialUser(),
    login: (token, user) => {
        localStorage.setItem('token', token);
        localStorage.setItem('user', JSON.stringify(user));
        set({ token, user });
    },
    logout: () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        set({ token: null, user: null });
    }
}));

export default useAuthStore;
