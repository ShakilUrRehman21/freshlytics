import { FormEvent, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import api, { errorMessage } from '../api';
import AuthShell from '../components/AuthShell';
import { useAuth } from '../context/AuthContext';

const Login = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { login, isAuthenticated } = useAuth();
    const navigate = useNavigate();
    const from = (useLocation().state as { from?: string } | null)?.from || '/';

    if (isAuthenticated) return <Navigate to={from} replace />;

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        try {
            const form = new URLSearchParams({ username: email, password });
            const res = await api.post('/auth/login', form, {
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            });
            await login(res.data.access_token, res.data.user);
            navigate(from, { replace: true });
        } catch (err) {
            setError(errorMessage(err, 'Sign in failed. Check your email and password.'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <AuthShell
            title="Welcome back"
            subtitle={
                <>
                    New here?{' '}
                    <Link to="/register" className="text-leaf font-semibold underline-offset-4 hover:underline">
                        Create an account
                    </Link>
                </>
            }
        >
            <form className="space-y-5" onSubmit={handleSubmit} noValidate={false}>
                {error && (
                    <p role="alert" className="rounded-xl bg-plum/10 text-plum px-4 py-3 text-sm">
                        {error}
                    </p>
                )}
                <div>
                    <label className="label" htmlFor="email">Email</label>
                    <input id="email" type="email" autoComplete="email" required value={email}
                        onChange={(e) => setEmail(e.target.value)} className="field" placeholder="you@example.com" />
                </div>
                <div>
                    <label className="label" htmlFor="password">Password</label>
                    <input id="password" type="password" autoComplete="current-password" required value={password}
                        onChange={(e) => setPassword(e.target.value)} className="field" />
                </div>
                <button type="submit" disabled={loading} className="btn-primary w-full !h-12">
                    {loading ? 'Signing in…' : 'Sign in'}
                </button>
            </form>
        </AuthShell>
    );
};

export default Login;
