import { Camera, Home, ImagePlus, RotateCcw, Snowflake, X } from 'lucide-react';
import { DragEvent, useCallback, useEffect, useRef, useState } from 'react';
import api, { errorMessage, Prediction, Storage } from '../api';
import ResultPanel from '../components/ResultPanel';
import { capitalize } from '../lib/format';
import { listFruits, useAutoFruits } from '../lib/modelInfo';

const PREFS_KEY = 'freshlytics_scan_prefs';
type Prefs = { fruit: string; storage: Storage; temperature: number; humidity: number };
const DEFAULT_PREFS: Prefs = { fruit: 'auto', storage: 'room', temperature: 22, humidity: 60 };

function loadPrefs(): Prefs {
    try {
        return { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') };
    } catch {
        return DEFAULT_PREFS;
    }
}

const ScanPage = () => {
    const [file, setFile] = useState<File | null>(null);
    const [preview, setPreview] = useState<string | null>(null);
    const [cameraOn, setCameraOn] = useState(false);
    const [dragging, setDragging] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [result, setResult] = useState<Prediction | null>(null);
    const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
    const autoFruits = useAutoFruits();

    const videoRef = useRef<HTMLVideoElement>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const fruitRef = useRef<HTMLFieldSetElement>(null);
    const resultRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        try {
            localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
        } catch {
            /* ignore */
        }
    }, [prefs]);

    const stopCamera = useCallback(() => {
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        setCameraOn(false);
    }, []);

    useEffect(() => () => stopCamera(), [stopCamera]);
    useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

    const acceptFile = useCallback((f: File | undefined | null) => {
        if (!f) return;
        if (!f.type.startsWith('image/')) {
            setError("That's not an image. Choose a JPG, PNG or WebP photo.");
            return;
        }
        if (f.size > 8 * 1024 * 1024) {
            setError('That photo is larger than 8 MB. Choose a smaller one.');
            return;
        }
        setError('');
        setResult(null);
        setFile(f);
        setPreview(URL.createObjectURL(f));
    }, []);

    // Paste an image from the clipboard
    useEffect(() => {
        const onPaste = (e: ClipboardEvent) => {
            const item = Array.from(e.clipboardData?.items || []).find((i) => i.type.startsWith('image/'));
            if (item) acceptFile(item.getAsFile());
        };
        window.addEventListener('paste', onPaste);
        return () => window.removeEventListener('paste', onPaste);
    }, [acceptFile]);

    const startCamera = async () => {
        setError('');
        setResult(null);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 } },
            });
            streamRef.current = stream;
            setCameraOn(true);
            requestAnimationFrame(() => {
                if (videoRef.current) videoRef.current.srcObject = stream;
            });
        } catch {
            setError("Couldn't open the camera. Allow camera access in your browser, or upload a photo instead.");
        }
    };

    const capture = () => {
        const v = videoRef.current;
        if (!v || !v.videoWidth) return;
        const canvas = document.createElement('canvas');
        canvas.width = v.videoWidth;
        canvas.height = v.videoHeight;
        canvas.getContext('2d')?.drawImage(v, 0, 0);
        canvas.toBlob((blob) => {
            if (blob) acceptFile(new File([blob], 'camera.jpg', { type: 'image/jpeg' }));
            stopCamera();
        }, 'image/jpeg', 0.92);
    };

    const onDrop = (e: DragEvent) => {
        e.preventDefault();
        setDragging(false);
        acceptFile(e.dataTransfer.files?.[0]);
    };

    const reset = () => {
        setFile(null);
        setPreview(null);
        setResult(null);
        setError('');
    };

    const [noFruit, setNoFruit] = useState(false);
    const analyze = async (force = false) => {
        if (!file) return;
        setNoFruit(false);
        setLoading(true);
        setError('');
        const form = new FormData();
        form.append('file', file);
        form.append('storage_type', prefs.storage);
        form.append('temperature', String(prefs.temperature));
        form.append('humidity', String(prefs.humidity));
        form.append('fruit_hint', prefs.fruit);
        if (force) form.append('force', 'true');
        try {
            const res = await api.post<Prediction>('/predict', form);
            setResult(res.data);
            requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
        } catch (err) {
            const detail = (err as { response?: { data?: { detail?: { code?: string } } } })?.response?.data?.detail;
            setNoFruit(detail?.code === 'no_fruit');
            setError(errorMessage(err, "The scan didn't go through. Try again."));
        } finally {
            setLoading(false);
        }
    };

    const setStorage = (s: Storage) =>
        setPrefs((p) => ({ ...p, storage: s, temperature: s === 'fridge' ? 4 : 22, humidity: s === 'fridge' ? 90 : 60 }));

    return (
        <div>
            <header className="mb-7">
                <h1 className="font-display font-extrabold text-[38px] sm:text-[44px] leading-none">Scan a fruit</h1>
                <p className="mt-3 text-muted max-w-[60ch]">
                    Photograph one whole, uncut fruit filling most of the frame, in good light. Cut or peeled fruit isn't supported. You can also paste an image.
                </p>
            </header>

            <div className="grid lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)] gap-6">
                {/* Image stage */}
                <section
                    className={`relative panel overflow-hidden min-h-[360px] sm:min-h-[440px] flex ${dragging ? 'ring-2 ring-leaf' : ''}`}
                    onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={onDrop}
                    aria-label="Photo"
                >
                    {!preview && !cameraOn && (
                        <div className="m-3 flex-1 rounded-[16px] border-2 border-dashed border-line flex flex-col items-center justify-center text-center px-6 py-10">
                            <div className="h-16 w-16 rounded-full bg-leafsoft text-leaf grid place-items-center mb-5">
                                <ImagePlus size={28} />
                            </div>
                            <p className="font-display font-bold text-[22px]">{dragging ? 'Drop to add the photo' : 'Drop a photo here'}</p>
                            <p className="text-muted text-sm mt-1">JPG, PNG or WebP, up to 8 MB</p>
                            <div className="mt-6 flex flex-wrap justify-center gap-3">
                                <button className="btn-primary" onClick={() => inputRef.current?.click()}>
                                    <ImagePlus size={18} /> Choose photo
                                </button>
                                <button className="btn-ghost" onClick={startCamera}>
                                    <Camera size={18} /> Use camera
                                </button>
                            </div>
                            <input ref={inputRef} type="file" accept="image/*" className="hidden"
                                onChange={(e) => { acceptFile(e.target.files?.[0]); e.target.value = ''; }} />
                        </div>
                    )}

                    {cameraOn && (
                        <div className="relative flex-1 bg-black">
                            <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-cover" />
                            <div className="absolute inset-0 grid place-items-center pointer-events-none" aria-hidden>
                                <div className="w-[62%] aspect-[4/3] rounded-[50%] border-2 border-white/60 border-dashed" />
                            </div>
                            <div className="absolute bottom-5 inset-x-0 flex items-center justify-center gap-6">
                                <button onClick={stopCamera} className="h-12 w-12 rounded-full bg-black/50 text-white grid place-items-center" aria-label="Close camera">
                                    <X size={22} />
                                </button>
                                <button onClick={capture} className="h-[72px] w-[72px] rounded-full bg-white grid place-items-center ring-4 ring-white/40" aria-label="Take photo">
                                    <span className="h-[58px] w-[58px] rounded-full border-2 border-black/15" />
                                </button>
                                <span className="w-12" />
                            </div>
                        </div>
                    )}

                    {preview && !cameraOn && (
                        <div className="relative flex-1 bg-sunken">
                            <img src={preview} alt="Selected fruit" className="absolute inset-0 w-full h-full object-contain p-3" />
                            {loading && (
                                <div className="absolute inset-0 overflow-hidden" aria-hidden>
                                    <div className="scan-beam absolute inset-x-0 h-24 -mt-12 bg-gradient-to-b from-transparent via-[rgb(var(--sprout)/0.45)] to-transparent" />
                                </div>
                            )}
                            {!loading && (
                                <button onClick={reset} className="absolute top-3 right-3 btn-ghost !h-9 !px-3 bg-surface/90 backdrop-blur text-sm">
                                    <RotateCcw size={15} /> Change photo
                                </button>
                            )}
                        </div>
                    )}
                </section>

                {/* Conditions */}
                <section className="panel p-5 sm:p-6 flex flex-col justify-between">
                    <fieldset ref={fruitRef} tabIndex={-1} className="focus:outline-none">
                        <legend className="font-display font-bold text-[19px]">Which fruit?</legend>
                        <p className="text-sm text-muted mt-0.5">Freshlytics is trained on {listFruits(autoFruits)} only. Other fruits won't give reliable results.</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                            {['auto', ...autoFruits].map((f) => (
                                <button key={f} type="button" className="chip" aria-pressed={prefs.fruit === f}
                                    onClick={() => setPrefs((p) => ({ ...p, fruit: f }))}>
                                    {f === 'auto' ? 'Auto-detect' : capitalize(f)}
                                </button>
                            ))}
                        </div>
                    </fieldset>

                    <fieldset className="mt-7">
                        <legend className="font-display font-bold text-[19px]">Where is it kept?</legend>
                        <div className="mt-3 grid grid-cols-2 gap-2">
                            {([['room', 'Counter', Home], ['fridge', 'Fridge', Snowflake]] as const).map(([v, label, Icon]) => (
                                <button key={v} type="button" onClick={() => setStorage(v)} aria-pressed={prefs.storage === v}
                                    className={`h-14 rounded-2xl border flex items-center justify-center gap-2 font-medium transition-colors ${
                                        prefs.storage === v ? 'border-leaf bg-leafsoft text-leaf' : 'border-line hover:border-leaf/50'
                                    }`}>
                                    <Icon size={18} /> {label}
                                </button>
                            ))}
                        </div>
                    </fieldset>

                    <div className="mt-6 space-y-5">
                        <div>
                            <div className="flex justify-between items-baseline">
                                <label htmlFor="temp" className="text-sm font-medium">Temperature</label>
                                <span className="font-display font-bold num">{prefs.temperature} °C</span>
                            </div>
                            <input id="temp" type="range" min={-2} max={40} step={1} value={prefs.temperature}
                                onChange={(e) => setPrefs((p) => ({ ...p, temperature: Number(e.target.value) }))}
                                className="w-full mt-2.5" />
                        </div>
                        <div>
                            <div className="flex justify-between items-baseline">
                                <label htmlFor="hum" className="text-sm font-medium">Humidity</label>
                                <span className="font-display font-bold num">{prefs.humidity}%</span>
                            </div>
                            <input id="hum" type="range" min={10} max={100} step={5} value={prefs.humidity}
                                onChange={(e) => setPrefs((p) => ({ ...p, humidity: Number(e.target.value) }))}
                                className="w-full mt-2.5" />
                        </div>
                    </div>

                    {error && (
                        <p role="alert" className="mt-6 rounded-xl bg-plum/10 text-plum px-4 py-3 text-sm">
                            {error}
                            {noFruit && (
                                <button className="block mt-1.5 font-semibold underline underline-offset-2" onClick={() => analyze(true)}>
                                    It is a fruit, check anyway
                                </button>
                            )}
                        </p>
                    )}

                    <button onClick={() => analyze()} disabled={!file || loading} className="btn-primary !h-[52px] w-full mt-8 text-[16px]">
                        {loading ? 'Checking freshness…' : file ? 'Check freshness' : 'Add a photo to start'}
                    </button>
                </section>
            </div>

            <div ref={resultRef} className="scroll-mt-6 mt-6">
                {result && (
                    <ResultPanel
                        key={result.scan_id}
                        result={result}
                        onPickFruit={() => {
                            fruitRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            fruitRef.current?.focus();
                        }}
                    />
                )}
            </div>
        </div>
    );
};

export default ScanPage;
