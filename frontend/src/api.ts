/// <reference types="vite/client" />
import axios, { AxiosError } from 'axios';

export const TOKEN_KEY = 'freshlytics_token';

const getBaseUrl = (): string => {
    let url = (import.meta.env.VITE_API_URL || 'https://freshlytics-api.onrender.com/api/v1').trim();
    url = url.replace(/\/+$/, '');
    if (!url.endsWith('/api/v1')) {
        url = `${url}/api/v1`;
    }
    return url;
};

const api = axios.create({
    baseURL: getBaseUrl(),
    timeout: 60000,
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
        if (error.response?.status === 401) {
            localStorage.removeItem(TOKEN_KEY);
            const path = window.location.pathname;
            if (path !== '/login' && path !== '/register') window.location.href = '/login';
        }
        return Promise.reject(error);
    },
);

/** Turn any API/network error into one readable sentence. */
export function errorMessage(err: unknown, fallback = 'Something went wrong. Try again.'): string {
    const e = err as AxiosError<{ detail?: unknown }>;
    if (e?.response?.data?.detail) {
        const d = e.response.data.detail;
        if (typeof d === 'string') return d;
        if (typeof d === 'object' && d && 'message' in d) return String((d as { message: unknown }).message);
        if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg).replace(/^Value error, /, '');
    }
    if (e?.code === 'ECONNABORTED') return 'The server took too long to respond.';
    if (e?.message === 'Network Error') return "Can't reach the Freshlytics server. Check that the backend is running on port 8000.";
    return fallback;
}

export interface User {
    id: number;
    email: string;
    name: string;
    role: string;
    created_at: string;
}

export type Stage = 'Fresh' | 'Good' | 'Use Soon' | 'Spoiled';
export type Storage = 'room' | 'fridge';

export interface Scan {
    id: number;
    fruit_type: string;
    freshness_stage: Stage | string;
    freshness_score: number;
    shelf_life_hours: number;
    temperature?: number | null;
    humidity?: number | null;
    confidence?: number | null;
    rot_probability?: number | null;
    storage_type?: Storage | null;
    fruit_source?: string | null;
    thumbnail?: string | null;
    heatmap?: string | null;
    notes?: string | null;
    created_at: string;
}

export interface Prediction {
    scan_id: number;
    created_at: string;
    fruit: string;
    fruit_source: 'model' | 'user';
    detected_fruit: string;
    fruit_confidence: number;
    fruit_uncertain: boolean;
    freshness_stage: Stage;
    stage_description: string;
    freshness_score: number;
    rot_probability: number;
    shelf_life_hours: number;
    ai_confidence: number;
    storage_type: Storage;
    temperature: number | null;
    humidity: number | null;
    recommendations: string[];
    ideal_conditions: { temperature: string; humidity: string };
    thumbnail: string;
    heatmap: string;
}

export interface Analytics {
    total_scans: number;
    scans_today: number;
    avg_freshness: number;
    high_risk_count: number;
    freshness_change: number | null;
    period_days: number;
    fruit_distribution: { name: string; value: number }[];
    stage_distribution: { name: Stage; value: number }[];
    trend: { date: string; label: string; scans: number; avg_freshness: number | null }[];
    recent_scans: Scan[];
    at_risk: Scan[];
}

export interface FruitGuide {
    fruit: string;
    room_days: number;
    fridge_days: number;
    ideal_temp: string;
    ideal_humidity: string;
    tip: string;
    auto_detected: boolean;
}

export default api;
