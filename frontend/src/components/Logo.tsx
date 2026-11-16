const Logo = ({ className = '', mono = false }: { className?: string; mono?: boolean }) => (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
        <svg width="34" height="26" viewBox="0 0 34 26" aria-hidden>
            <ellipse cx="17" cy="13" rx="16" ry="12" fill={mono ? 'currentColor' : 'rgb(var(--sprout))'} />
            <path d="M10 16.5c3.5-8.5 11-9.5 14.5-9.5-1 7-6.5 11.5-14.5 9.5z" fill={mono ? 'rgb(var(--rail))' : '#17321F'} />
            <path d="M11 16c3-2.5 6-4.5 9.5-6" stroke={mono ? 'currentColor' : 'rgb(var(--sprout))'} strokeWidth="1.2" fill="none" strokeLinecap="round" />
        </svg>
        <span className="font-display font-bold text-[21px] tracking-tight">Freshlytics</span>
    </span>
);

export default Logo;
