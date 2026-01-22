import { defineConfig } from 'vite'

export default defineConfig({
    build: {
        outDir: 'dist',
        rollupOptions: {
            output: {
                entryFileNames: 'widget.js',
                assetFileNames: 'style.css', // Force specific name for CSS
            },
        },
    },
})
