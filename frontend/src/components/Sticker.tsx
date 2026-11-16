import { capitalize, normalizeStage } from '../lib/format';

interface Props {
    score: number;
    stage: string;
    fruit?: string;
    size?: 'sm' | 'md' | 'lg';
    animate?: boolean;
    className?: string;
}

const PALETTE: Record<string, { bg: string; fg: string; edge: string }> = {
    Fresh: { bg: 'rgb(var(--leaf))', fg: 'rgb(var(--paper))', edge: 'rgb(var(--paper) / 0.45)' },
    Good: { bg: 'rgb(var(--sprout))', fg: '#17321F', edge: 'rgb(23 50 31 / 0.35)' },
    'Use Soon': { bg: 'rgb(var(--citrus))', fg: '#3A2604', edge: 'rgb(58 38 4 / 0.35)' },
    Spoiled: { bg: 'rgb(var(--plum))', fg: '#FFF3F4', edge: 'rgb(255 243 244 / 0.45)' },
};

const SIZES = {
    sm: { w: 64, h: 46, num: 'text-[19px]', sub: 'text-[8px]', inset: 3 },
    md: { w: 104, h: 76, num: 'text-[30px]', sub: 'text-[10px]', inset: 4 },
    lg: { w: 176, h: 128, num: 'text-[54px]', sub: 'text-[13px]', inset: 6 },
};

/**
 * The produce-sticker that carries a freshness score — Freshlytics' signature mark.
 */
const Sticker = ({ score, stage, fruit, size = 'md', animate, className = '' }: Props) => {
    const s = SIZES[size];
    const c = PALETTE[normalizeStage(stage)] || PALETTE.Spoiled;
    const position = /(^|\s)absolute(\s|$)/.test(className) ? '' : 'relative';
    return (
        <div
            role="img"
            aria-label={`Freshness score ${score} out of 100, ${normalizeStage(stage)}`}
            className={`${position} shrink-0 select-none ${animate ? 'animate-stick' : ''} ${className}`}
            style={{
                width: s.w,
                height: s.h,
                transform: animate ? undefined : 'rotate(-6deg)',
                filter: 'drop-shadow(0 6px 10px rgb(var(--shadow) / 0.22))',
            }}
        >
            <div
                className="absolute inset-0 rounded-[50%] flex flex-col items-center justify-center leading-none"
                style={{
                    background: `radial-gradient(120% 90% at 30% 20%, rgb(255 255 255 / 0.22), transparent 55%), ${c.bg}`,
                    color: c.fg,
                }}
            >
                <span
                    className="absolute rounded-[50%] border border-dashed"
                    style={{ inset: s.inset, borderColor: c.edge }}
                    aria-hidden
                />
                {size !== 'sm' && fruit && (
                    <span className={`${s.sub} font-semibold opacity-80 mb-0.5`}>{capitalize(fruit)}</span>
                )}
                <span className={`font-display font-extrabold num ${s.num}`} style={{ letterSpacing: '-0.04em' }}>
                    {score}
                </span>
                {size !== 'sm' && <span className={`${s.sub} font-medium opacity-80 mt-0.5`}>freshness</span>}
            </div>
        </div>
    );
};

export default Sticker;
