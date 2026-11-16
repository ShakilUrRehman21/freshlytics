import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Logo from './Logo';

const ProtectedRoute = () => {
    const { isAuthenticated, loading } = useAuth();
    const location = useLocation();

    if (loading) {
        return (
            <div className="min-h-screen grid place-items-center text-leaf">
                <Logo className="animate-pulse" />
            </div>
        );
    }
    if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
    return <Outlet />;
};

export default ProtectedRoute;
