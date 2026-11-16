import { AlertTriangle, Droplets, Snowflake, Thermometer } from 'lucide-react';
import { useState } from 'react';
import { Prediction } from '../api';
import { capitalize, formatShelfLife, stageTone } from '../lib/format';
import Sticker from './Sticker';
import { listFruits, useAutoFruits } from '../lib/modelInfo';

interface Props {
    result: Prediction;
    onPickFruit?: () => void;
}

export const ImageToggle = ({ photo, heatmap, alt }: { photo: string; heatmap?: string | null; alt: string }) => {
    const [view, setView] = useState<'photo' | 'map'>('photo');
    return (
        <div>
            <div className="relative aspect-square rounded-2xl overflow-hidden bg-sunken">
                <img src={view === 'map' && heatmap ? heatmap : photo} alt={alt} className="w-full h-full object-cover" />
            </div>
            {heatmap && (
                <div className="mt-2 inline-flex rounded-full bg-sunken p-1 text-[13px] font-medium" role="group" aria-label="Image view">
                    {(['photo', 'map'] as const).map((v) => (
                        <button
                            key={v}
                            onClick={() => setView(v)}
                            aria-pressed={view === v}
                            className={`px-3 h-7 rounded-full transition-colors ${view === v ? 'bg-surface text-ink shadow-sm' : 'text-muted'}`}
                        >
                            {v === 'photo' ? 'Photo' : 'Decay map'}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
};

const ResultPanel = ({ result, onPickFruit }: Props) => {
    const autoFruits = useAutoFruits();
    const tone = stageTone(result.freshness_stage);
    const shelf = formatShelfLife(result.shelf_life_hours);
    const storageLabel = result.storage_type === 'fridge' ? 'in the fridge' : 'at room temperature';

    return (
        <article className="panel p-5 sm:p-7" aria-live="polite">
            <div className="grid sm:grid-cols-[minmax(0,220px)_1fr] gap-6 sm:gap-8">
                <ImageToggle photo={result.thumbnail} heatmap={result.heatmap} alt={`Scanned ${result.fruit}`} />

                <div className="min-w-0">
                    <div className="flex items-start gap-5">
                        <Sticker score={result.freshness_score} stage={result.freshness_stage} fruit={result.fruit} size="md" animate />
                        <div className="pt-1 min-w-0">
                            <h2 className={`font-display font-extrabold text-[34px] leading-none ${tone.text}`}>
                                {result.freshness_stage}
                            </h2>
                            <p className="mt-2 text-muted text-[15px] max-w-[42ch]">{result.stage_description}</p>
                        </div>
                    </div>

                    <div className="mt-7 flex flex-wrap items-end gap-x-3 gap-y-1">
                        {result.shelf_life_hours <= 0.5 ? (
                            <span className={`font-display font-extrabold text-[44px] leading-[0.9] ${tone.text}`}>Past its best</span>
                        ) : (
                            <>
                                <span className="font-display font-extrabold text-[64px] leading-[0.85] num">{shelf.value}</span>
                                <span className="font-display text-[22px] font-semibold pb-1">{shelf.unit} left</span>
                            </>
                        )}
                    </div>
                    <p className="mt-2 text-sm text-muted">
                        Estimated for {capitalize(result.fruit).toLowerCase()} stored {storageLabel}
                        {result.temperature != null ? ` at ${result.temperature} °C` : ''}
                        {result.humidity != null ? `, ${result.humidity}% humidity` : ''}.
                    </p>

                    <dl className="mt-6 grid grid-cols-2 gap-4 max-w-[420px]">
                        <div>
                            <dt className="text-sm text-muted">Decay detected</dt>
                            <dd className="mt-1.5">
                                <div className="h-2 rounded-full bg-sunken overflow-hidden">
                                    <div className={`h-full rounded-full ${tone.bg} transition-[width] duration-700`}
                                        style={{ width: `${Math.max(3, result.rot_probability * 100)}%` }} />
                                </div>
                                <span className="text-sm font-semibold num">{Math.round(result.rot_probability * 100)}%</span>
                            </dd>
                        </div>
                        <div>
                            <dt className="text-sm text-muted">Model certainty</dt>
                            <dd className="mt-1.5">
                                <div className="h-2 rounded-full bg-sunken overflow-hidden">
                                    <div className="h-full rounded-full bg-ink/70" style={{ width: `${result.ai_confidence * 100}%` }} />
                                </div>
                                <span className="text-sm font-semibold num">{Math.round(result.ai_confidence * 100)}%</span>
                            </dd>
                        </div>
                    </dl>

                    <p className="mt-5 text-sm text-muted">
                        {result.fruit_source === 'user'
                            ? <>Fruit set to <strong className="text-ink">{capitalize(result.fruit)}</strong> by you.</>
                            : result.detected_fruit === 'other'
                              ? <><strong className="text-ink">Not one of the supported items.</strong> The freshness score is a rough guide and shelf life uses general produce values.</>
                              : <>Recognised as <strong className="text-ink">{capitalize(result.detected_fruit)}</strong> ({Math.round(result.fruit_confidence * 100)}% sure).</>}
                    </p>
                    {result.fruit_uncertain && result.detected_fruit !== 'other' && (
                        <div className="mt-3 flex gap-2.5 rounded-xl bg-citrus/15 text-ink px-3.5 py-3 text-sm">
                            <AlertTriangle size={17} className="text-citrus shrink-0 mt-0.5" />
                            <p>
                                Automatic recognition covers {listFruits(autoFruits)}. If this is something else,{' '}
                                {onPickFruit ? (
                                    <button className="font-semibold underline underline-offset-2" onClick={onPickFruit}>choose the fruit</button>
                                ) : 'choose the fruit'}{' '}
                                and scan again for an accurate shelf life. The freshness score still applies.
                            </p>
                        </div>
                    )}
                </div>
            </div>

            <div className="mt-8 pt-6 border-t border-line grid md:grid-cols-[1fr_auto] gap-6">
                <div>
                    <h3 className="font-display font-bold text-[19px]">What to do</h3>
                    <ul className="mt-3 space-y-2.5">
                        {result.recommendations.map((r, i) => (
                            <li key={i} className="flex gap-3 text-[15px] max-w-[64ch]">
                                <span className={`mt-2 h-2 w-2 rounded-full shrink-0 ${i === 0 ? tone.bg : 'bg-line'}`} aria-hidden />
                                {r}
                            </li>
                        ))}
                    </ul>
                </div>
                <div className="rounded-2xl bg-sunken px-5 py-4 text-sm min-w-[210px] self-start">
                    <p className="font-semibold">Ideal storage for {result.fruit}</p>
                    <p className="mt-2 flex items-center gap-2 text-muted"><Thermometer size={15} /> {result.ideal_conditions.temperature}</p>
                    <p className="mt-1 flex items-center gap-2 text-muted"><Droplets size={15} /> {result.ideal_conditions.humidity} humidity</p>
                    {result.storage_type === 'fridge' && (
                        <p className="mt-1 flex items-center gap-2 text-muted"><Snowflake size={15} /> Currently refrigerated</p>
                    )}
                </div>
            </div>
        </article>
    );
};

export default ResultPanel;
