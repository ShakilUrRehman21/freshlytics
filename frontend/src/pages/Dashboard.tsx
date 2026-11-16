import { ScanLine } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bar, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import api, { Analytics, errorMessage } from '../api';
import ScanDialog from '../components/ScanDialog';
import ScanRow, { Thumb } from '../components/ScanRow';
import Sticker from '../components/Sticker';
import { useAuth } from '../context/AuthContext';
import { capitalize, formatShelfLife, stageTone } from '../lib/format';

function greeting() {
    const h = new Date().getHours();
    return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
}

const ChartTip = ({ active, payload, label }: { active?: boolean; payload?: { dataKey: string; value: number | null }[]; label?: string }) => {
    if (!active || !payload?.length) return null;
    const f = payload.find((p) => p.dataKey === 'avg_freshness')?.value;
    const n = payload.find((p) => p.dataKey === 'scans')?.value ?? 0;
    return (
        <div className="rounded-xl bg-surface border border-line px-3 py-2 text-sm shadow-lift">
            <p className="font-semibold">{label}</p>
            <p className="text-muted">{n} {n === 1 ? 'scan' : 'scans'}{f != null ? `, average freshness ${f}` : ''}</p>
        </div>
    );
};

const Dashboard = () => {
    const { user } = useAuth();
    const [stats, setStats] = useState<Analytics | null>(null);
    const [error, setError] = useState('');
    const [openId, setOpenId] = useState<number | null>(null);

    const load = useCallback(() => {
        api.get<Analytics>('/analytics', { params: { days: 14, tz_offset: new Date().getTimezoneOffset() } })
            .then((r) => setStats(r.data))
            .catch((e) => setError(errorMessage(e, "Couldn't load your overview.")));
    }, []);
    useEffect(load, [load]);

    const first = user?.name?.split(' ')[0];

    if (error) {
        return (
            <div className="panel p-8 max-w-xl">
                <h1 className="font-display font-bold text-2xl">Overview unavailable</h1>
                <p className="mt-2 text-muted">{error}</p>
                <button className="btn-ghost mt-5" onClick={() => { setError(''); load(); }}>Try again</button>
            </div>
        );
    }

    if (!stats) {
        return (
            <div className="space-y-6 animate-pulse" aria-busy>
                <div className="h-12 w-2/3 rounded-xl bg-sunken" />
                <div className="h-48 rounded-panel bg-sunken" />
                <div className="h-72 rounded-panel bg-sunken" />
            </div>
        );
    }

    if (stats.total_scans === 0) {
        return (
            <div className="max-w-2xl">
                <h1 className="font-display font-extrabold text-[40px] sm:text-[52px] leading-[1.02]">
                    {greeting()}{first ? `, ${first}` : ''}.
                </h1>
                <p className="mt-4 text-[17px] text-muted max-w-[52ch]">
                    Scan your first fruit to see its freshness score and how long it has left. Your overview fills in as you go.
                </p>
                <Link to="/scan" className="btn-primary mt-8 !h-12 text-[16px]">
                    <ScanLine size={19} /> Scan your first fruit
                </Link>
                <div className="mt-14 flex items-end gap-4" aria-hidden>
                    <Sticker score={92} stage="Fresh" fruit="apple" size="md" />
                    <Sticker score={57} stage="Good" fruit="banana" size="md" className="rotate-3" />
                    <Sticker score={34} stage="Use Soon" fruit="mango" size="md" />
                </div>
            </div>
        );
    }

    const urgent = stats.at_risk.filter((s) => s.shelf_life_hours < 24).length;
    const summary =
        urgent > 0
            ? `${urgent} ${urgent === 1 ? 'item needs' : 'items need'} using within a day.`
            : stats.at_risk.length > 0
              ? `${stats.at_risk.length} ${stats.at_risk.length === 1 ? 'item has' : 'items have'} less than two days left.`
              : 'Everything you scanned recently is in good shape.';
    const maxFruit = Math.max(...stats.fruit_distribution.map((f) => f.value), 1);
    const stageTotal = stats.stage_distribution.reduce((a, s) => a + s.value, 0) || 1;

    return (
        <div>
            <header className="flex flex-wrap items-end justify-between gap-4">
                <div>
                    <h1 className="font-display font-extrabold text-[38px] sm:text-[48px] leading-[1.02]">
                        {greeting()}{first ? `, ${first}` : ''}.
                    </h1>
                    <p className="mt-3 text-[17px] text-muted">{summary}</p>
                </div>
                <Link to="/scan" className="btn-primary"><ScanLine size={18} /> New scan</Link>
            </header>

            {/* Eat-first shelf: the most useful thing on the page */}
            <section className="mt-8" aria-labelledby="eat-first">
                <h2 id="eat-first" className="font-display font-bold text-[22px]">Eat these first</h2>
                {stats.at_risk.length === 0 ? (
                    <p className="mt-2 text-muted">Nothing you've scanned is close to spoiling.</p>
                ) : (
                    <ul className="mt-4 flex gap-4 overflow-x-auto pb-2 -mx-1 px-1 snap-x">
                        {stats.at_risk.map((s) => {
                            const shelf = formatShelfLife(s.shelf_life_hours);
                            const tone = stageTone(s.freshness_stage);
                            return (
                                <li key={s.id} className="snap-start shrink-0">
                                    <button onClick={() => setOpenId(s.id)} className="panel w-[220px] p-3 text-left hover:border-leaf/40 transition-colors">
                                        <div className="relative">
                                            <Thumb src={s.thumbnail} alt={s.fruit_type} className="w-full aspect-[4/3] rounded-2xl" />
                                            <Sticker score={s.freshness_score} stage={s.freshness_stage} size="sm" className="absolute -bottom-3 -right-1" />
                                        </div>
                                        <p className="mt-3 font-semibold">{capitalize(s.fruit_type)}</p>
                                        <p className={`text-sm font-medium ${tone.text}`}>
                                            {s.shelf_life_hours <= 0.5 ? 'Past its best' : `${shelf.value} ${shelf.unit} left`}
                                        </p>
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </section>

            <div className="mt-8 grid xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-6">
                <section className="panel p-5 sm:p-6" aria-labelledby="trend">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <h2 id="trend" className="font-display font-bold text-[20px]">Last {stats.period_days} days</h2>
                        <p className="text-sm text-muted">
                            Bars show scans per day, the line shows average freshness.
                        </p>
                    </div>
                    <div className="h-64 mt-4 -ml-3">
                        <ResponsiveContainer width="100%" height="100%">
                            <ComposedChart data={stats.trend} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                                <XAxis dataKey="label" tickLine={false} axisLine={false} interval="preserveStartEnd"
                                    tick={{ fill: 'rgb(var(--muted))', fontSize: 12 }} minTickGap={24} />
                                <YAxis yAxisId="f" domain={[0, 100]} tickLine={false} axisLine={false} width={36}
                                    tick={{ fill: 'rgb(var(--muted))', fontSize: 12 }} ticks={[0, 50, 100]} />
                                <YAxis yAxisId="n" orientation="right" hide allowDecimals={false} />
                                <Tooltip content={<ChartTip />} cursor={{ fill: 'rgb(var(--sunken))' }} />
                                <Bar yAxisId="n" dataKey="scans" fill="rgb(var(--leafsoft))" radius={[6, 6, 0, 0]} maxBarSize={22} />
                                <Line yAxisId="f" dataKey="avg_freshness" type="monotone" stroke="rgb(var(--leaf))" strokeWidth={2.5}
                                    dot={{ r: 3.5, fill: 'rgb(var(--leaf))', strokeWidth: 0 }} connectNulls />
                            </ComposedChart>
                        </ResponsiveContainer>
                    </div>
                    <dl className="mt-5 pt-5 border-t border-line grid grid-cols-2 sm:grid-cols-4 gap-4">
                        <div>
                            <dt className="text-sm text-muted">Total scans</dt>
                            <dd className="font-display font-bold text-[26px] num">{stats.total_scans}</dd>
                        </div>
                        <div>
                            <dt className="text-sm text-muted">Today</dt>
                            <dd className="font-display font-bold text-[26px] num">{stats.scans_today}</dd>
                        </div>
                        <div>
                            <dt className="text-sm text-muted">Average freshness</dt>
                            <dd className="font-display font-bold text-[26px] num">
                                {Math.round(stats.avg_freshness)}
                                {stats.freshness_change != null && (
                                    <span className={`ml-2 text-sm font-sans font-semibold ${stats.freshness_change >= 0 ? 'text-leaf' : 'text-plum'}`}>
                                        {stats.freshness_change >= 0 ? '+' : ''}{stats.freshness_change}
                                    </span>
                                )}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-sm text-muted">Under a day left</dt>
                            <dd className={`font-display font-bold text-[26px] num ${stats.high_risk_count ? 'text-plum' : ''}`}>{stats.high_risk_count}</dd>
                        </div>
                    </dl>
                </section>

                <section className="panel p-5 sm:p-6" aria-labelledby="mix">
                    <h2 id="mix" className="font-display font-bold text-[20px]">Condition of everything scanned</h2>
                    <div className="mt-4 flex h-4 rounded-full overflow-hidden bg-sunken" role="img"
                        aria-label={stats.stage_distribution.map((s) => `${s.name}: ${s.value}`).join(', ')}>
                        {stats.stage_distribution.filter((s) => s.value > 0).map((s) => (
                            <div key={s.name} className={`${stageTone(s.name).bg} h-full border-r-2 border-surface last:border-r-0`}
                                style={{ width: `${(s.value / stageTotal) * 100}%` }} />
                        ))}
                    </div>
                    <ul className="mt-3 grid grid-cols-2 gap-y-1.5 text-sm">
                        {stats.stage_distribution.map((s) => (
                            <li key={s.name} className="flex items-center gap-2">
                                <span className={`h-2.5 w-2.5 rounded-full ${stageTone(s.name).bg}`} />
                                {s.name} <span className="text-muted num">{s.value}</span>
                            </li>
                        ))}
                    </ul>

                    <h3 className="font-display font-bold text-[17px] mt-7">By fruit</h3>
                    <ul className="mt-3 space-y-2.5">
                        {stats.fruit_distribution.map((f) => (
                            <li key={f.name} className="grid grid-cols-[72px_1fr_28px] items-center gap-3 text-sm">
                                <span>{capitalize(f.name)}</span>
                                <span className="h-2 rounded-full bg-sunken overflow-hidden">
                                    <span className="block h-full bg-leaf/80 rounded-full" style={{ width: `${(f.value / maxFruit) * 100}%` }} />
                                </span>
                                <span className="text-right text-muted num">{f.value}</span>
                            </li>
                        ))}
                    </ul>
                </section>
            </div>

            <section className="panel p-5 sm:p-6 mt-6" aria-labelledby="recent">
                <div className="flex items-baseline justify-between">
                    <h2 id="recent" className="font-display font-bold text-[20px]">Recent scans</h2>
                    <Link to="/history" className="text-sm font-semibold text-leaf hover:underline underline-offset-4">See all</Link>
                </div>
                <div className="mt-2 divide-y divide-line">
                    {stats.recent_scans.map((s) => <ScanRow key={s.id} scan={s} onClick={() => setOpenId(s.id)} />)}
                </div>
            </section>

            <ScanDialog scanId={openId} onClose={() => setOpenId(null)} onDeleted={() => load()} />
        </div>
    );
};

export default Dashboard;
