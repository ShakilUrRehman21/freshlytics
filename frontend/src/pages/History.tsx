import { ScanLine } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errorMessage, Scan } from '../api';
import ScanDialog from '../components/ScanDialog';
import { Thumb } from '../components/ScanRow';
import Sticker from '../components/Sticker';
import { useAutoFruits } from '../lib/modelInfo';
import { capitalize, formatShelfLife, normalizeStage, relativeTime, STAGE_ORDER, stageTone } from '../lib/format';

const PAGE = 24;

const HistoryPage = () => {
    const [scans, setScans] = useState<Scan[]>([]);
    const [total, setTotal] = useState(0);
    const [fruit, setFruit] = useState('');
    const [stage, setStage] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [openId, setOpenId] = useState<number | null>(null);
    const autoFruits = useAutoFruits();

    const load = useCallback(async (skip = 0) => {
        setLoading(true);
        setError('');
        const params = { fruit: fruit || undefined, stage: stage || undefined };
        try {
            const [list, count] = await Promise.all([
                api.get<Scan[]>('/history', { params: { ...params, skip, limit: PAGE } }),
                api.get<{ count: number }>('/history/count', { params }),
            ]);
            setScans((prev) => (skip ? [...prev, ...list.data] : list.data));
            setTotal(count.data.count);
        } catch (e) {
            setError(errorMessage(e, "Couldn't load your scans."));
        } finally {
            setLoading(false);
        }
    }, [fruit, stage]);

    useEffect(() => { load(0); }, [load]);

    const filtered = fruit || stage;

    return (
        <div>
            <header className="flex flex-wrap items-end justify-between gap-4">
                <div>
                    <h1 className="font-display font-extrabold text-[38px] sm:text-[44px] leading-none">History</h1>
                    <p className="mt-3 text-muted">
                        {total} {total === 1 ? 'scan' : 'scans'}{filtered ? ' match these filters' : ' so far'}.
                    </p>
                </div>
                <div className="flex flex-wrap gap-3">
                    <label className="sr-only" htmlFor="f-fruit">Fruit</label>
                    <select id="f-fruit" value={fruit} onChange={(e) => setFruit(e.target.value)} className="field !w-auto !h-10 pr-8">
                        <option value="">All fruit</option>
                        {autoFruits.map((f) => <option key={f} value={f}>{capitalize(f)}</option>)}
                    </select>
                    <label className="sr-only" htmlFor="f-stage">Condition</label>
                    <select id="f-stage" value={stage} onChange={(e) => setStage(e.target.value)} className="field !w-auto !h-10 pr-8">
                        <option value="">Any condition</option>
                        {STAGE_ORDER.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                </div>
            </header>

            {error && <p role="alert" className="mt-6 rounded-xl bg-plum/10 text-plum px-4 py-3 text-sm">{error}</p>}

            {!loading && !error && scans.length === 0 && (
                <div className="panel mt-8 p-10 text-center">
                    <p className="font-display font-bold text-[22px]">{filtered ? 'No scans match these filters' : 'No scans yet'}</p>
                    <p className="text-muted mt-2">{filtered ? 'Try a different fruit or condition.' : 'Every fruit you check is saved here with its photo and score.'}</p>
                    {!filtered && <Link to="/scan" className="btn-primary mt-6"><ScanLine size={18} /> Scan a fruit</Link>}
                </div>
            )}

            <ul className="mt-8 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-5">
                {scans.map((s) => {
                    const shelf = formatShelfLife(s.shelf_life_hours);
                    return (
                        <li key={s.id}>
                            <button onClick={() => setOpenId(s.id)} className="panel w-full p-3 text-left hover:border-leaf/40 transition-colors">
                                <div className="relative">
                                    <Thumb src={s.thumbnail} alt={s.fruit_type} className="w-full aspect-square rounded-2xl" />
                                    <Sticker score={s.freshness_score} stage={s.freshness_stage} size="sm" className="absolute -bottom-3 -right-1" />
                                </div>
                                <p className="mt-3 font-semibold">{capitalize(s.fruit_type)}</p>
                                <p className="text-sm">
                                    <span className={stageTone(s.freshness_stage).text}>{normalizeStage(s.freshness_stage)}</span>
                                    <span className="text-muted">, {s.shelf_life_hours <= 0.5 ? 'past its best' : `${shelf.value} ${shelf.unit} left`}</span>
                                </p>
                                <p className="text-xs text-muted mt-1">{relativeTime(s.created_at)}</p>
                            </button>
                        </li>
                    );
                })}
                {loading && Array.from({ length: scans.length ? 4 : 8 }).map((_, i) => (
                    <li key={`sk${i}`} className="rounded-panel bg-sunken aspect-[3/4] animate-pulse" aria-hidden />
                ))}
            </ul>

            {!loading && scans.length < total && (
                <div className="mt-8 text-center">
                    <button className="btn-ghost" onClick={() => load(scans.length)}>Show more</button>
                </div>
            )}

            <ScanDialog
                scanId={openId}
                onClose={() => setOpenId(null)}
                onDeleted={(id) => { setScans((p) => p.filter((s) => s.id !== id)); setTotal((t) => t - 1); }}
            />
        </div>
    );
};

export default HistoryPage;
