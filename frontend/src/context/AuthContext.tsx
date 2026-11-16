import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from 'react';
import api, { TOKEN_KEY, User } from '../api';

interface AuthContextType {
    user: User | null;
    token: string | null;
    login: (token: string, user?: User | null) => Promise<void>;
    logout: () => void;
    setUser: (u: User) => void;
    isAuthenticated: boolean;
    loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
    const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState<boolean>(!!localStorage.getItem(TOKEN_KEY));

    useEffect(() => {
        if (!token || user) {
            setLoading(false);
            return;
        }
        let cancelled = false;
        setLoading(true);
        api.get<User>('/auth/me')
            .then((res) => !cancelled && setUser(res.data))
            .catch(() => {
                if (cancelled) return;
                localStorage.removeItem(TOKEN_KEY);
                setToken(null);
            })
            .finally(() => !cancelled && setLoading(false));
        return () => {
            cancelled = true;
        };
    }, [token, user]);

    const login = useCallback(async (newToken: string, u?: User | null) => {
        localStorage.setItem(TOKEN_KEY, newToken);
        if (u) setUser(u);
        setToken(newToken);
    }, []);

    const logout = useCallback(() => {
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
    }, []);

    return (
        <AuthContext.Provider
            value={{ user, token, login, logout, setUser, isAuthenticated: !!token, loading }}
        >
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
    return ctx;
};
