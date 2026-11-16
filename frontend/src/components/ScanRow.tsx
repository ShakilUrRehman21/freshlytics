import { Scan } from '../api';
import { capitalize, formatShelfLife, normalizeStage, relativeTime, stageTone } from '../lib/format';
import Sticker from './Sticker';

export const Thumb = ({ src, alt, className = '' }: { src?: string | null; alt: string; className?: string }) =>
    src ? (
        <img src={src} alt={alt} className={`object-cover bg-sunken ${className}`} loading="lazy" />
    ) : (
        <div className={`bg-sunken ${className}`} aria-hidden />
    );

const ScanRow = ({ scan, onClick }: { scan: Scan; onClick?: () => void }) => {
    const shelf = formatShelfLife(scan.shelf_life_hours);
    const tone = stageTone(scan.freshness_stage);
    return (
        <button
            onClick={onClick}
            className="w-full flex items-center gap-4 py-3 text-left rounded-xl hover:bg-sunken/60 px-2 -mx-2 transition-colors"
        >
            <Thumb src={scan.thumbnail} alt={scan.fruit_type} className="h-12 w-12 rounded-xl shrink-0" />
            <div className="min-w-0 flex-1">
                <p className="font-semibold truncate">{capitalize(scan.fruit_type)}</p>
                <p className="text-sm text-muted truncate">
                    <span className={tone.text}>{normalizeStage(scan.freshness_stage)}</span>, {relativeTime(scan.created_at)}
                </p>
            </div>
            <div className="text-right shrink-0">
                <p className="font-display font-bold num">{shelf.value} <span className="text-sm font-medium text-muted">{shelf.unit}</span></p>
                <p className="text-xs text-muted">left</p>
            </div>
            <Sticker score={scan.freshness_score} stage={scan.freshness_stage} size="sm" />
        </button>
    );
};

export default ScanRow;
