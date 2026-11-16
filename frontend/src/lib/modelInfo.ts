import { useEffect, useState } from 'react';
import api from '../api';
import { capitalize } from './format';

let cache: string[] | null = null;

/** Fruits the server's model recognises automatically (falls back to the original three). */
export function useAutoFruits(): string[] {
    const [fruits, setFruits] = useState<string[]>(cache || ['apple', 'banana', 'orange']);
    useEffect(() => {
        if (cache) return;
        api.get('/predict/info')
            .then((r) => {
                cache = r.data.auto_detected_fruits as string[];
                setFruits(cache);
            })
            .catch(() => undefined);
    }, []);
    return fruits;
}

/** ['apple','banana','mango'] -> "apples, bananas and mangoes" */
export function listFruits(fruits: string[]): string {
    const plural = (f: string) => (f === 'grapes' ? 'grapes' : f === 'mango' ? 'mangoes' : f === 'strawberry' ? 'strawberries' : `${f}s`);
    const names = fruits.map((f) => plural(f));
    if (names.length <= 1) return capitalize(names[0] || '');
    return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}
