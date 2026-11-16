import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    // read VITE_* variables from the project-root .env as well
    envDir: '..',
    server: {
        port: 3000,
        open: true,
    },
});
