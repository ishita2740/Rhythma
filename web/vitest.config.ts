import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Kept separate from vite.config.ts so the dev/build config stays free of
// test-only settings, and so `vitest` can be run without loading the app's
// plugin chain in any different order than the app itself uses.
export default defineConfig({
  plugins: [react()],
  test: {
    // The components under test touch the DOM (forms, navigation, focus),
    // so a browser-like environment is required rather than 'node'.
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setupTests.ts'],
    css: false,
    // `restoreMocks` puts spied-on originals back after each test;
    // `clearMocks` resets call history. Both on, so a test can never pass
    // because of a mock another test left configured.
    clearMocks: true,
    restoreMocks: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/main.tsx',
        'src/test/**',
        'src/**/*.d.ts',
        'src/i18n/locales/**',
      ],
    },
  },
});
