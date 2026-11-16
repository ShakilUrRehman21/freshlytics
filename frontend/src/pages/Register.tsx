import { FormEvent, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import api, { errorMessage } from '../api';
import AuthShell from '../components/AuthShell';
import { useAuth } from '../context/AuthContext';

const Register = () => {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { login, isAuthenticated } = useAuth();
    const navigate = useNavigate();

    if (isAuthenticated) return <Navigate to="/" replace />;

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setError('');
        if (password.length < 6) {
            setError('Use at least 6 characters for your password.');
            return;
        }
        setLoading(true);
        try {
            const res = await api.post('/auth/register', { name, email, password });
            await login(res.data.access_token, res.data.user);
            navigate('/scan', { replace: true });
        } catch (err) {
            setError(errorMessage(err, "Couldn't create your account. Try again."));
        } finally {
            setLoading(false);
        }
    };

    return (
        <AuthShell
            title="Create your account"
            subtitle={
                <>
                    Already have one?{' '}
                    <Link to="/login" className="text-leaf font-semibold underline-offset-4 hover:underline">
                        Sign in
                    </Link>
                </>
            }
        >
            <form className="space-y-5" onSubmit={handleSubmit}>
                {error && (
                    <p role="alert" className="rounded-xl bg-plum/10 text-plum px-4 py-3 text-sm">
                        {error}
                    </p>
                )}
                <div>
                    <label className="label" htmlFor="name">Your name</label>
                    <input id="name" type="text" autoComplete="name" required value={name}
                        onChange={(e) => setName(e.target.value)} className="field" />
                </div>
                <div>
                    <label className="label" htmlFor="email">Email</label>
                    <input id="email" type="email" autoComplete="email" required value={email}
                        onChange={(e) => setEmail(e.target.value)} className="field" placeholder="you@example.com" />
                </div>
                <div>
                    <label className="label" htmlFor="password">Password</label>
                    <input id="password" type="password" autoComplete="new-password" required minLength={6} value={password}
                        onChange={(e) => setPassword(e.target.value)} className="field" />
                    <p className="text-xs text-muted mt-1.5">At least 6 characters.</p>
                </div>
                <button type="submit" disabled={loading} className="btn-primary w-full !h-12">
                    {loading ? 'Creating account…' : 'Create account'}
                </button>
            </form>
        </AuthShell>
    );
};

export default Register;
