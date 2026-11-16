import { Droplets, Home, Snowflake, Thermometer } from 'lucide-react';
import { useEffect, useState } from 'react';
import api, { errorMessage, FruitGuide } from '../api';
import Sticker from '../components/Sticker';
import { capitalize } from '../lib/format';

const STAGES = [
    { label: 'Fresh', range: '80–100', score: 92, text: 'No visible decay. Store normally.' },
    { label: 'Good', range: '55–79', score: 66, text: 'Minor ageing. Plan to eat in the next few days.' },
    { label: 'Use Soon', range: '30–54', score: 41, text: 'Eat, cook or freeze within a day or two.' },
    { label: 'Spoiled', range: '0–29', score: 9, text: 'Rot or mould present. Discard the affected piece.' },
];

const Guide = () => {
    const [guide, setGuide] = useState<FruitGuide[]>([]);
    const [error, setError] = useState('');

    useEffect(() => {
        api.get('/predict/info').then((r) => setGuide((r.data.guide as FruitGuide[]).filter((g) => g.auto_detected))).catch((e) => setError(errorMessage(e)));
    }, []);

    const maxDays = Math.max(...guide.map((g) => g.fridge_days), 1);

    return (
        <div>
            <header>
                <h1 className="font-display font-extrabold text-[38px] sm:text-[44px] leading-none">Storage guide</h1>
                <p className="mt-3 text-muted max-w-[62ch]">
                    How long fresh fruit typically lasts and where to keep it. Freshlytics uses these figures, adjusted for
                    each scan's condition and temperature, to estimate time left.
                </p>
            </header>

            <section className="mt-9" aria-labelledby="scores">
                <h2 id="scores" className="font-display font-bold text-[22px]">Reading a freshness score</h2>
                <ul className="mt-5 grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
                    {STAGES.map((s) => (
                        <li key={s.label} className="panel p-5 flex items-center gap-4">
                            <Sticker score={s.score} stage={s.label} size="sm" />
                            <div>
                                <p className="font-semibold">{s.label} <span className="text-muted font-normal num">{s.range}</span></p>
                                <p className="text-sm text-muted mt-0.5">{s.text}</p>
                            </div>
                        </li>
                    ))}
                </ul>
            </section>

            <section className="mt-10" aria-labelledby="fruits">
                <h2 id="fruits" className="font-display font-bold text-[22px]">By fruit</h2>
                {error && <p role="alert" className="mt-4 rounded-xl bg-plum/10 text-plum px-4 py-3 text-sm">{error}</p>}
                <div className="mt-5 space-y-4">
                    {guide.map((g) => (
                        <article key={g.fruit} className="panel p-5 sm:p-6 grid md:grid-cols-[180px_1fr_1fr] gap-5 md:gap-8">
                            <div>
                                <h3 className="font-display font-extrabold text-[26px] leading-none">{capitalize(g.fruit)}</h3>
                                <p className="text-sm text-muted mt-2">Supported by the current model</p>
                            </div>
                            <div className="space-y-3">
                                {([['Counter', g.room_days, Home], ['Fridge', g.fridge_days, Snowflake]] as const).map(([label, days, Icon]) => (
                                    <div key={label} className="grid grid-cols-[86px_1fr_64px] items-center gap-3 text-sm">
                                        <span className="flex items-center gap-1.5 text-muted"><Icon size={15} /> {label}</span>
                                        <span className="h-2.5 rounded-full bg-sunken overflow-hidden">
                                            <span className={`block h-full rounded-full ${label === 'Fridge' ? 'bg-leaf' : 'bg-sprout'}`}
                                                style={{ width: `${(days / maxDays) * 100}%` }} />
                                        </span>
                                        <span className="font-semibold num text-right">{days} days</span>
                                    </div>
                                ))}
                                <p className="text-sm text-muted flex flex-wrap gap-x-5 gap-y-1 pt-1">
                                    <span className="flex items-center gap-1.5"><Thermometer size={15} /> Ideal {g.ideal_temp}</span>
                                    <span className="flex items-center gap-1.5"><Droplets size={15} /> {g.ideal_humidity} humidity</span>
                                </p>
                            </div>
                            <p className="text-[15px] max-w-[52ch] md:border-l md:border-line md:pl-8">{g.tip}</p>
                        </article>
                    ))}
                    {!guide.length && !error && Array.from({ length: 3 }).map((_, i) => (
                        <div key={i} className="h-32 rounded-panel bg-sunken animate-pulse" aria-hidden />
                    ))}
                </div>
            </section>

            <section className="mt-10 panel p-6 max-w-3xl">
                <h2 className="font-display font-bold text-[20px]">How estimates are made</h2>
                <p className="mt-3 text-[15px] text-muted leading-relaxed">
                    A ResNet50V2 network trained on about 11,000 photos of fresh and rotten fruit measures visible decay — bruising,
                    mould, discolouration — and gives the freshness score. Time left starts from the typical shelf life above, shrinks
                    as decay increases, and roughly halves for every 10 °C warmer than the reference temperature. Treat it as a guide,
                    and trust your nose: anything slimy, fizzy or fuzzy should go.
                </p>
            </section>
        </div>
    );
};

export default Guide;
