import { Trash2, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import api, { errorMessage, Scan } from '../api';
import { capitalize, formatShelfLife, fullDate, normalizeStage, stageTone } from '../lib/format';
import { ImageToggle } from './ResultPanel';
import Sticker from './Sticker';

interface Props {
    scanId: number | null;
    onClose: () => void;
    onDeleted: (id: number) => void;
}

const ScanDialog = ({ scanId, onClose, onDeleted }: Props) => {
    const ref = useRef<HTMLDialogElement>(null);
    const [scan, setScan] = useState<Scan | null>(null);
    const [notes, setNotes] = useState('');
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        const d = ref.current;
        if (!d) return;
        if (scanId != null) {
            if (!d.open) d.showModal();
            setScan(null);
            setError('');
            setSaved(false);
            api.get<Scan>(`/history/${scanId}`)
                .then((r) => {
                    setScan(r.data);
                    setNotes(r.data.notes || '');
                })
                .catch((e) => setError(errorMessage(e)));
        } else if (d.open) d.close();
    }, [scanId]);

    const saveNotes = async () => {
        if (!scan) return;
        try {
            await api.patch(`/history/${scan.id}`, { notes });
            setSaved(true);
        } catch (e) {
            setError(errorMessage(e));
        }
    };

    const remove = async () => {
        if (!scan) return;
        try {
            await api.delete(`/history/${scan.id}`);
            onDeleted(scan.id);
            onClose();
        } catch (e) {
            setError(errorMessage(e));
        }
    };

    const tone = scan ? stageTone(scan.freshness_stage) : null;
    const shelf = scan ? formatShelfLife(scan.shelf_life_hours) : null;

    return (
        <dialog
            ref={ref}
            onClose={onClose}
            onClick={(e) => e.target === ref.current && onClose()}
            className="backdrop:bg-[rgb(13_22_17/0.55)] backdrop:backdrop-blur-sm bg-transparent p-0 m-auto w-[min(760px,calc(100vw-24px))] max-h-[calc(100vh-24px)]"
        >
            <div className="panel p-5 sm:p-7 text-ink overflow-y-auto max-h-[calc(100vh-24px)]">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <h2 className="font-display font-extrabold text-[30px] leading-none">
                            {scan ? capitalize(scan.fruit_type) : 'Loading scan…'}
                        </h2>
                        {scan && <p className="text-sm text-muted mt-2">Scanned {fullDate(scan.created_at)}</p>}
                    </div>
                    <button onClick={onClose} className="h-10 w-10 grid place-items-center rounded-full hover:bg-sunken" aria-label="Close">
                        <X size={20} />
                    </button>
                </div>

                {error && <p role="alert" className="mt-4 rounded-xl bg-plum/10 text-plum px-4 py-3 text-sm">{error}</p>}

                {scan && tone && shelf && (
                    <div className="mt-6 grid sm:grid-cols-[240px_1fr] gap-7">
                        <ImageToggle photo={scan.thumbnail || ''} heatmap={scan.heatmap} alt={scan.fruit_type} />
                        <div>
                            <div className="flex items-center gap-5">
                                <Sticker score={scan.freshness_score} stage={scan.freshness_stage} fruit={scan.fruit_type} size="md" />
                                <div>
                                    <p className={`font-display font-extrabold text-[28px] leading-none ${tone.text}`}>
                                        {normalizeStage(scan.freshness_stage)}
                                    </p>
                                    <p className="mt-2 text-muted">
                                        {scan.shelf_life_hours <= 0.5 ? 'Past its best when scanned' : `${shelf.value} ${shelf.unit} left at the time of scanning`}
                                    </p>
                                </div>
                            </div>
                            <dl className="mt-6 grid grid-cols-2 gap-y-3 gap-x-6 text-sm">
                                <dt className="text-muted">Stored</dt>
                                <dd>{scan.storage_type === 'fridge' ? 'Fridge' : 'Counter'}</dd>
                                <dt className="text-muted">Temperature</dt>
                                <dd className="num">{scan.temperature != null ? `${scan.temperature} °C` : 'Not recorded'}</dd>
                                <dt className="text-muted">Humidity</dt>
                                <dd className="num">{scan.humidity != null ? `${scan.humidity}%` : 'Not recorded'}</dd>
                                <dt className="text-muted">Decay detected</dt>
                                <dd className="num">{scan.rot_probability != null ? `${Math.round(scan.rot_probability * 100)}%` : 'Not recorded'}</dd>
                                <dt className="text-muted">Fruit chosen by</dt>
                                <dd>{scan.fruit_source === 'user' ? 'You' : 'Auto-detect'}</dd>
                            </dl>

                            <label htmlFor="notes" className="label mt-6">Notes</label>
                            <textarea id="notes" value={notes} onChange={(e) => { setNotes(e.target.value); setSaved(false); }}
                                rows={2} className="field !h-auto py-2.5 resize-none" placeholder="Where you bought it, batch, etc." />
                            <div className="mt-4 flex flex-wrap gap-3">
                                <button className="btn-primary !h-10" onClick={saveNotes} disabled={saved || notes === (scan.notes || '')}>
                                    {saved ? 'Notes saved' : 'Save notes'}
                                </button>
                                <button className="btn-danger !h-10" onClick={remove}>
                                    <Trash2 size={16} /> Delete scan
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </dialog>
    );
};

export default ScanDialog;
