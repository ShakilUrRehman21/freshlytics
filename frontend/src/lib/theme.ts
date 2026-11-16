import { useEffect, useState } from 'react';

export type Theme = 'light' | 'dark' | 'system';
const KEY = 'freshlytics_theme';

function apply(theme: Theme) {
    const dark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('dark', dark);
}

export function useTheme() {
    const [theme, setTheme] = useState<Theme>(() => {
        try {
            return (localStorage.getItem(KEY) as Theme) || 'system';
        } catch {
            return 'system';
        }
    });

    useEffect(() => {
        apply(theme);
        try {
            if (theme === 'system') localStorage.removeItem(KEY);
            else localStorage.setItem(KEY, theme);
        } catch {
            /* storage unavailable */
        }
        if (theme !== 'system') return;
        const mq = window.matchMedia('(prefers-color-scheme: dark)');
        const onChange = () => apply('system');
        mq.addEventListener('change', onChange);
        return () => mq.removeEventListener('change', onChange);
    }, [theme]);

    const isDark = () => document.documentElement.classList.contains('dark');
    const toggle = () => setTheme(isDark() ? 'light' : 'dark');
    return { theme, setTheme, toggle, isDark };
}
