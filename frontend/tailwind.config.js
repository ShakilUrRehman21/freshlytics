/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
    content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                paper: v('paper'),        // page background
                surface: v('surface'),    // raised panels
                sunken: v('sunken'),      // wells, inputs
                ink: v('ink'),            // primary text
                muted: v('muted'),        // secondary text
                line: v('line'),          // hairlines
                leaf: v('leaf'),          // brand / fresh
                leafsoft: v('leafsoft'),
                sprout: v('sprout'),      // light green highlight
                citrus: v('citrus'),      // use soon
                plum: v('plum'),          // spoiled
                rail: v('rail'),          // nav rail
            },
            fontFamily: {
                display: ['"Bricolage Grotesque Variable"', '"Bricolage Grotesque"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                sans: ['"Instrument Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
            },
            borderRadius: {
                panel: '22px',
            },
            boxShadow: {
                lift: '0 1px 0 rgb(var(--line) / 0.6), 0 12px 32px -18px rgb(var(--shadow) / 0.35)',
            },
        },
    },
    plugins: [],
};
