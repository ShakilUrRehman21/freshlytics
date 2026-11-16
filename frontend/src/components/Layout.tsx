import { BookOpen, History, LayoutGrid, LogOut, Moon, ScanLine, Settings, Sun } from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../lib/theme';
import Logo from './Logo';

const NAV = [
    { name: 'Overview', path: '/', icon: LayoutGrid, end: true },
    { name: 'Scan', path: '/scan', icon: ScanLine },
    { name: 'History', path: '/history', icon: History },
    { name: 'Storage guide', path: '/guide', icon: BookOpen },
    { name: 'Settings', path: '/settings', icon: Settings },
];

const Layout = () => {
    const { user, logout } = useAuth();
    const { toggle, isDark } = useTheme();
    const [dark, setDark] = useState(isDark());
    const navigate = useNavigate();

    const onToggle = () => {
        toggle();
        setDark(!dark);
    };
    const onLogout = () => {
        logout();
        navigate('/login');
    };
    const initials = (user?.name || user?.email || '?')
        .split(/\s+/)
        .map((p) => p[0])
        .join('')
        .slice(0, 2)
        .toUpperCase();

    return (
        <div className="min-h-screen lg:pl-[248px]">
            {/* Desktop rail */}
            <aside className="hidden lg:flex fixed inset-y-0 left-0 w-[248px] flex-col bg-rail text-[#E4EFDD] px-5 py-6">
                <Logo className="px-2 text-[#F2F7EC]" />

                <nav className="mt-10 space-y-1" aria-label="Main">
                    {NAV.map(({ name, path, icon: Icon, end }) => (
                        <NavLink
                            key={path}
                            to={path}
                            end={end}
                            className={({ isActive }) =>
                                `flex items-center gap-3 h-11 px-3 rounded-xl text-[15px] font-medium transition-colors ${
                                    isActive ? 'bg-[#E4EFDD] text-[#17321F]' : 'text-[#C4D6BD] hover:bg-white/5 hover:text-white'
                                }`
                            }
                        >
                            <Icon size={19} strokeWidth={1.9} />
                            {name}
                        </NavLink>
                    ))}
                </nav>

                <NavLink
                    to="/scan"
                    className="mt-8 rounded-2xl bg-[rgb(var(--sprout))] text-[#17321F] p-4 block hover:brightness-105 transition"
                >
                    <p className="font-display font-bold text-[17px] leading-tight">Check a fruit</p>
                    <p className="text-[13px] mt-1 opacity-80">Snap or upload a photo for a freshness score in seconds.</p>
                </NavLink>

                <div className="mt-auto pt-6 border-t border-white/10 flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-[#E4EFDD] text-[#17321F] grid place-items-center font-display font-bold text-sm">
                        {initials}
                    </div>
                    <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-white truncate">{user?.name || 'Loading…'}</p>
                        <p className="text-xs text-[#9DB596] truncate">{user?.email}</p>
                    </div>
                    <button
                        onClick={onToggle}
                        className="h-9 w-9 grid place-items-center rounded-lg text-[#C4D6BD] hover:bg-white/10"
                        aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
                        title={dark ? 'Light mode' : 'Dark mode'}
                    >
                        {dark ? <Sun size={17} /> : <Moon size={17} />}
                    </button>
                    <button
                        onClick={onLogout}
                        className="h-9 w-9 grid place-items-center rounded-lg text-[#C4D6BD] hover:bg-white/10"
                        aria-label="Sign out"
                        title="Sign out"
                    >
                        <LogOut size={17} />
                    </button>
                </div>
            </aside>

            {/* Mobile header */}
            <header className="lg:hidden sticky top-0 z-20 bg-rail text-[#F2F7EC] h-14 px-4 flex items-center justify-between">
                <Logo />
                <div className="flex items-center gap-1">
                    <button onClick={onToggle} className="h-9 w-9 grid place-items-center rounded-lg hover:bg-white/10" aria-label="Toggle theme">
                        {dark ? <Sun size={18} /> : <Moon size={18} />}
                    </button>
                    <button onClick={onLogout} className="h-9 w-9 grid place-items-center rounded-lg hover:bg-white/10" aria-label="Sign out">
                        <LogOut size={18} />
                    </button>
                </div>
            </header>

            <main className="px-4 sm:px-6 lg:px-10 pt-6 lg:pt-10 pb-28 lg:pb-12 max-w-[1240px]">
                <Outlet />
            </main>

            {/* Mobile tab bar */}
            <nav
                className="lg:hidden fixed bottom-0 inset-x-0 z-20 bg-surface/95 backdrop-blur border-t border-line grid grid-cols-5 pb-[env(safe-area-inset-bottom)]"
                aria-label="Main"
            >
                {NAV.map(({ name, path, icon: Icon, end }) => (
                    <NavLink
                        key={path}
                        to={path}
                        end={end}
                        className={({ isActive }) =>
                            `flex flex-col items-center justify-center gap-0.5 h-16 text-[11px] font-medium ${
                                isActive ? 'text-leaf' : 'text-muted'
                            }`
                        }
                    >
                        <Icon size={20} />
                        {name === 'Storage guide' ? 'Guide' : name}
                    </NavLink>
                ))}
            </nav>
        </div>
    );
};

export default Layout;
