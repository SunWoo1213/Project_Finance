import React from 'react';
import { Navigate } from 'react-router-dom';
import useAuthStore from '../store/authStore';

const ProtectedRoute = ({ children }) => {
    const { token } = useAuthStore();

    if (!token) {
        alert("로그인이 필요한 서비스입니다.");
        return <Navigate to="/login" replace />;
    }

    return children;
};

export default ProtectedRoute;
