export const FRUITS = ['apple', 'banana', 'orange', 'mango', 'grapes', 'guava', 'pomegranate', 'strawberry', 'lime', 'jujube'] as const;

export const capitalize = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

/** 52 → "2 days", 7 → "7 hours", 0 → "Now" */
export function formatShelfLife(hours: number): { value: string; unit: string; sentence: string } {
    if (hours <= 0.5) return { value: '0', unit: 'hours', sentence: 'past its best' };
    if (hours < 24) {
        const h = Math.round(hours);
        return { value: String(h), unit: h === 1 ? 'hour' : 'hours', sentence: `about ${h} ${h === 1 ? 'hour' : 'hours'}` };
    }
    const days = hours / 24;
    const d = days < 10 ? Math.round(days * 2) / 2 : Math.round(days);
    const txt = Number.isInteger(d) ? String(d) : d.toFixed(1);
    return { value: txt, unit: d === 1 ? 'day' : 'days', sentence: `about ${txt} ${d === 1 ? 'day' : 'days'}` };
}

export function relativeTime(iso: string): string {
    const t = new Date(iso).getTime();
    const diff = (Date.now() - t) / 1000;
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} d ago`;
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function fullDate(iso: string): string {
    return new Date(iso).toLocaleString(undefined, {
        month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
    });
}

const LEGACY: Record<string, string> = { Ripe: 'Good', Overripe: 'Use Soon', Rotten: 'Spoiled' };
export const normalizeStage = (s: string) => LEGACY[s] || s;

/** Tailwind colour tokens for each freshness stage. */
export function stageTone(stage: string) {
    switch (normalizeStage(stage)) {
        case 'Fresh':
            return { text: 'text-leaf', bg: 'bg-leaf', soft: 'bg-leafsoft', ring: 'ring-leaf/30', hex: 'var(--leaf)' };
        case 'Good':
            return { text: 'text-leaf', bg: 'bg-sprout', soft: 'bg-leafsoft', ring: 'ring-sprout/40', hex: 'var(--sprout)' };
        case 'Use Soon':
            return { text: 'text-citrus', bg: 'bg-citrus', soft: 'bg-citrus/15', ring: 'ring-citrus/40', hex: 'var(--citrus)' };
        default:
            return { text: 'text-plum', bg: 'bg-plum', soft: 'bg-plum/10', ring: 'ring-plum/30', hex: 'var(--plum)' };
    }
}

export const STAGE_ORDER = ['Fresh', 'Good', 'Use Soon', 'Spoiled'] as const;
