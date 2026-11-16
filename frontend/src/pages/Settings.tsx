import { Monitor, Moon, Sun } from 'lucide-react';
import { FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { errorMessage, User } from '../api';
import { useAuth } from '../context/AuthContext';
import { fullDate } from '../lib/format';
import { Theme, useTheme } from '../lib/theme';

const Status = ({ msg }: { msg: { ok: boolean; text: string } | null }) =>
    msg ? (
        <p role="status" className={`text-sm mt-3 ${msg.ok ? 'text-leaf' : 'text-plum'}`}>{msg.text}</p>
    ) : null;

const Section = ({ title, children, desc }: { title: string; desc?: string; children: React.ReactNode }) => (
    <section className="panel p-5 sm:p-7 grid md:grid-cols-[240px_1fr] gap-4 md:gap-10">
        <div>
            <h2 className="font-display font-bold text-[20px]">{title}</h2>
            {desc && <p className="text-sm text-muted mt-1">{desc}</p>}
        </div>
        <div className="max-w-md">{children}</div>
    </section>
);

const Settings = () => {
    const { user, setUser, logout } = useAuth();
    const { theme, setTheme } = useTheme();
    const navigate = useNavigate();

    const [name, setName] = useState(user?.name || '');
    const [nameMsg, setNameMsg] = useState<{ ok: boolean; text: string } | null>(null);
    const [pw, setPw] = useState({ current: '', next: '' });
    const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);
    const [confirmClear, setConfirmClear] = useState(false);
    const [clearMsg, setClearMsg] = useState<{ ok: boolean; text: string } | null>(null);

    useEffect(() => { if (user) setName(user.name); }, [user]);

    const saveName = async (e: FormEvent) => {
        e.preventDefault();
        try {
            const r = await api.patch<User>('/auth/me', { name });
            setUser(r.data);
            setNameMsg({ ok: true, text: 'Name saved.' });
        } catch (err) {
            setNameMsg({ ok: false, text: errorMessage(err) });
        }
    };

    const changePw = async (e: FormEvent) => {
        e.preventDefault();
        try {
            await api.post('/auth/me/password', { current_password: pw.current, new_password: pw.next });
            setPw({ current: '', next: '' });
            setPwMsg({ ok: true, text: 'Password changed.' });
        } catch (err) {
            setPwMsg({ ok: false, text: errorMessage(err) });
        }
    };

    const clearHistory = async () => {
        try {
            await api.delete('/history');
            setConfirmClear(false);
            setClearMsg({ ok: true, text: 'All scans deleted.' });
        } catch (err) {
            setClearMsg({ ok: false, text: errorMessage(err) });
        }
    };

    const themes: [Theme, string, typeof Sun][] = [['light', 'Light', Sun], ['dark', 'Dark', Moon], ['system', 'Match device', Monitor]];

    return (
        <div>
            <h1 className="font-display font-extrabold text-[38px] sm:text-[44px] leading-none">Settings</h1>
            {user && <p className="mt-3 text-muted">Signed in as {user.email}, member since {fullDate(user.created_at).split(',').slice(0, 2).join(',')}.</p>}

            <div className="mt-8 space-y-5">
                <Section title="Profile" desc="Shown in your greeting and the sidebar.">
                    <form onSubmit={saveName}>
                        <label htmlFor="name" className="label">Name</label>
                        <div className="flex gap-3">
                            <input id="name" className="field" value={name} required maxLength={80}
                                onChange={(e) => { setName(e.target.value); setNameMsg(null); }} />
                            <button className="btn-primary shrink-0" disabled={!name.trim() || name === user?.name}>Save name</button>
                        </div>
                        <Status msg={nameMsg} />
                    </form>
                </Section>

                <Section title="Appearance">
                    <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Theme">
                        {themes.map(([v, label, Icon]) => (
                            <button key={v} role="radio" aria-checked={theme === v} onClick={() => setTheme(v)}
                                className={`h-20 rounded-2xl border flex flex-col items-center justify-center gap-1.5 text-sm font-medium transition-colors ${
                                    theme === v ? 'border-leaf bg-leafsoft text-leaf' : 'border-line hover:border-leaf/50'
                                }`}>
                                <Icon size={19} /> {label}
                            </button>
                        ))}
                    </div>
                </Section>

                <Section title="Password">
                    <form onSubmit={changePw} className="space-y-4">
                        <div>
                            <label htmlFor="cur" className="label">Current password</label>
                            <input id="cur" type="password" autoComplete="current-password" className="field" required
                                value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} />
                        </div>
                        <div>
                            <label htmlFor="new" className="label">New password</label>
                            <input id="new" type="password" autoComplete="new-password" className="field" required minLength={6}
                                value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} />
                        </div>
                        <button className="btn-ghost" disabled={!pw.current || pw.next.length < 6}>Change password</button>
                        <Status msg={pwMsg} />
                    </form>
                </Section>

                <Section title="Your data" desc="Scans are stored with a small thumbnail of each photo.">
                    {!confirmClear ? (
                        <button className="btn-danger" onClick={() => { setConfirmClear(true); setClearMsg(null); }}>Delete all scans</button>
                    ) : (
                        <div className="rounded-2xl bg-plum/10 p-4">
                            <p className="text-sm">This permanently deletes every scan and photo in your history.</p>
                            <div className="mt-3 flex gap-3">
                                <button className="btn !h-10 bg-plum text-white hover:bg-plum/90" onClick={clearHistory}>Delete all scans</button>
                                <button className="btn-ghost !h-10" onClick={() => setConfirmClear(false)}>Keep them</button>
                            </div>
                        </div>
                    )}
                    <Status msg={clearMsg} />
                    <button className="btn-ghost mt-6" onClick={() => { logout(); navigate('/login'); }}>Sign out</button>
                </Section>
            </div>
        </div>
    );
};

export default Settings;
